#!/usr/bin/env python3
"""Run a fault-injection campaign described by an experiment file; one CSV row per run.

    campaign.py studies/seu/experiments/smoke.yaml [--jobs N] [--confirm]

Experiment file (YAML):
    name: smoke                 # used in run_id and file names
    study: seu
    variant: h0                 # descriptor = studies/<study>/targets/soc_<variant>.yaml
    workloads: [w2_qsort]       # must be in studies/<study>/results/golden_runs.json
    units: [pc, regfile]        # or "all"
    runs_per_cell: 10           # one cell = one (workload, unit) pair
    seed: 1

Sampling (statistical fault injection, Leveugle et al. 2009): for each cell, `runs_per_cell`
times pick a fault site uniformly among the unit's flip-flops and a cycle uniformly in
[0, golden cycles). Each cell has its own random generator, seeded from (seed, workload,
unit), so adding a workload never changes the samples of another.

Safety rules (CLAUDE.md):
  - more than 1,000 runs needs --confirm (Boniface approves big campaigns);
  - parallel workers default to this study's share in ../seu-riscv-coord/cpu_budget.json;
  - a lock file in ../seu-riscv-coord/locks/ stops two campaigns running at once.

Output: studies/<study>/results/raw/<name>.csv (+ <name>.meta.json with tool versions).
Re-running the same command resumes: rows already in the CSV are not run again.
"""
import argparse
import csv
import hashlib
import json
import os
import random
import subprocess
import sys
import time
from multiprocessing import Pool

import yaml

import descriptor
from classify import classify
from injector import ROOT, run

COORD = os.path.join(ROOT, "..", "seu-riscv-coord")
CONFIRM_ABOVE = 1000
FIELDS = ["run_id", "study", "variant", "workload", "unit", "signal", "bit", "also",
          "cycle", "outcome", "sub_outcome", "status", "cycles_run", "bad_addr",
          "detected", "seed"]


def cell_seed(seed, workload, unit):
    """A stable 64-bit seed per cell (Python's hash() changes between runs; sha256 does not)."""
    digest = hashlib.sha256(f"{seed}/{workload}/{unit}".encode()).digest()
    return int.from_bytes(digest[:8], "little")


def plan(exp, sites, golden):
    """List of run descriptions, in a fixed order."""
    units = sorted({s.unit for s in sites}) if exp["units"] == "all" else exp["units"]
    jobs = []
    for w in exp["workloads"]:
        for u in units:
            pool = [s for s in sites if s.unit == u]
            if not pool:
                sys.exit(f"unit {u} has no fault sites")
            seed = cell_seed(exp["seed"], w, u)
            rng = random.Random(seed)
            for i in range(exp["runs_per_cell"]):
                site = rng.choice(pool)
                cycle = rng.randrange(golden[w]["cycles"])
                jobs.append({"run_id": f"{exp['study']}-{exp['name']}-{w}-{u}-{i:05d}",
                             "workload": w, "unit": u, "site": site, "cycle": cycle,
                             "seed": seed})
    return jobs


def execute(job):
    """Runs in a worker process: one injection -> one CSV row."""
    g = job["golden"]
    r = run(job["hex"], 2 * g["cycles"], site=job["site"], cycle=job["cycle"])
    s = job["site"]
    return {
        "run_id": job["run_id"], "study": job["study"], "variant": job["variant"],
        "workload": job["workload"], "unit": job["unit"], "signal": s.signal, "bit": s.bit,
        "also": " ".join(map(str, s.also)), "cycle": job["cycle"],
        "outcome": classify(r, g, detected=False), "sub_outcome": "",
        "status": r["status"], "cycles_run": r["cycles"], "bad_addr": int(r["bad_addr"]),
        "detected": 0, "seed": job["seed"],
    }


def tool_versions():
    def out(cmd):
        try:
            return subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT).stdout.strip()
        except OSError:
            return "unknown"
    return {"git_commit": out(["git", "rev-parse", "HEAD"]),
            "git_dirty": bool(out(["git", "status", "--porcelain", "--untracked-files=no"])),
            "verilator": out(["verilator", "--version"]),
            "python": sys.version.split()[0]}


def default_jobs(study):
    try:
        with open(os.path.join(COORD, "cpu_budget.json")) as f:
            return int(json.load(f)[study])
    except (OSError, KeyError, ValueError):
        return 1


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("experiment")
    ap.add_argument("--jobs", type=int, help="parallel workers (default: cpu_budget.json)")
    ap.add_argument("--confirm", action="store_true", help=f"allow more than {CONFIRM_ABOVE} runs")
    args = ap.parse_args()

    with open(args.experiment) as f:
        exp = yaml.safe_load(f)
    study, variant = exp["study"], exp["variant"]
    desc, ff = descriptor.load(os.path.join(ROOT, f"studies/{study}/targets/soc_{variant}.yaml"))
    sites = descriptor.sites(desc, ff)
    with open(os.path.join(ROOT, f"studies/{study}/results/golden_runs.json")) as f:
        golden = json.load(f)
    for w in exp["workloads"]:
        hexfile = os.path.join(ROOT, f"build/{study}/{w}.hex")
        if w not in golden or not os.path.exists(hexfile):
            sys.exit(f"{w}: needs a golden run and {hexfile} (run `make golden`)")

    jobs = plan(exp, sites, golden)
    if len(jobs) > CONFIRM_ABOVE and not args.confirm:
        sys.exit(f"{len(jobs)} runs > {CONFIRM_ABOVE}: ask Boniface, then add --confirm")

    rawdir = os.path.join(ROOT, f"studies/{study}/results/raw")
    os.makedirs(rawdir, exist_ok=True)
    out_csv = os.path.join(rawdir, f"{exp['name']}.csv")
    done = set()
    if os.path.exists(out_csv):
        with open(out_csv) as f:
            done = {row["run_id"] for row in csv.DictReader(f)}
    todo = [j for j in jobs if j["run_id"] not in done]
    for j in todo:
        j.update(study=study, variant=variant, golden=golden[j["workload"]],
                 hex=os.path.join(ROOT, f"build/{study}/{j['workload']}.hex"))

    lock = os.path.join(COORD, "locks", f"campaign-{study}.lock")
    os.makedirs(os.path.dirname(lock), exist_ok=True)
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        sys.exit(f"another campaign is running ({lock}); delete it only if it is stale")
    with os.fdopen(fd, "w") as f:
        f.write(f"{exp['name']} pid={os.getpid()} started={time.strftime('%Y-%m-%d %H:%M')}\n")

    try:
        meta = {"experiment": exp, "runs_planned": len(jobs), **tool_versions()}
        with open(out_csv.replace(".csv", ".meta.json"), "w") as f:
            json.dump(meta, f, indent=1)
        n_jobs = args.jobs or default_jobs(study)
        print(f"{exp['name']}: {len(jobs)} runs planned, {len(done)} already done, "
              f"{len(todo)} to run on {n_jobs} workers -> {os.path.relpath(out_csv, ROOT)}")
        t0 = time.time()
        new_file = not os.path.exists(out_csv)
        with open(out_csv, "a", newline="") as f, Pool(n_jobs) as pool:
            w = csv.DictWriter(f, FIELDS)
            if new_file:
                w.writeheader()
            for i, row in enumerate(pool.imap_unordered(execute, todo, chunksize=4), 1):
                w.writerow(row)
                f.flush()                      # a crash or Ctrl-C loses at most a few runs
                if i % 100 == 0 or i == len(todo):
                    print(f"  {i}/{len(todo)} runs, {time.time() - t0:.0f} s", flush=True)
    finally:
        os.remove(lock)


if __name__ == "__main__":
    main()
