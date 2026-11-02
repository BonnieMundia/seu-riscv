"""Build and run every workload of a study on the RTL, and compare against its Python reference.

Usage:  make golden STUDY=seu   (or: python platform/tests/check_golden.py --study seu [workload ...])

For each workload in studies/<study>/sw/ref/workloads.py:
  1. `make sw STUDY=<study> PROG=<name>` builds the ELF + hex into build/<study>/,
  2. the Verilator simulation runs it and prints OUT / DONE|TRAP|HANG lines,
  3. the OUT values are compared with the Python reference, and the cycle count with
     the 10k-200k budget.
Writes studies/<study>/results/golden_runs.json (outputs + cycle counts of the
fault-free runs); the fault-injection "Hang" rule (> 2x golden cycles) reads it.
"""

import argparse
import json
import re
import subprocess
import sys

from programs import ROOT, build_dir, golden_path, load

SIM = ROOT / "obj_dir" / "Vtb_soc"
MAX_CYCLES = 1_000_000
BUDGET = (10_000, 200_000)  # project scope: each workload runs 10k-200k cycles


def run(study, name):
    subprocess.run(["make", "-s", "sw", f"STUDY={study}", f"PROG={name}"], cwd=ROOT, check=True)
    hexfile = build_dir(study) / f"{name}.hex"
    out = subprocess.run(
        [str(SIM), f"+hex={hexfile}", f"+max_cycles={MAX_CYCLES}"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout
    outs = [int(v, 16) for v in re.findall(r"^OUT ([0-9a-f]{8})$", out, re.M)]
    end = re.search(r"^(DONE|TRAP|HANG) cycles=(\d+)$", out, re.M)
    return outs, end.group(1), int(end.group(2))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--study", default="seu")
    ap.add_argument("workloads", nargs="*")
    args = ap.parse_args()
    WORKLOADS, _ = load(args.study)
    if not WORKLOADS:
        sys.exit(f"study {args.study!r} has no workloads yet "
                 f"(studies/{args.study}/sw/ref/workloads.py missing)")
    names = args.workloads or list(WORKLOADS)
    subprocess.run(["make", "-s", str(SIM.relative_to(ROOT))], cwd=ROOT, check=True)
    golden, failures = {}, 0
    print(f"{'workload':<14} {'status':<6} {'cycles':>9}  result")
    for name in names:
        expected = WORKLOADS[name]()
        outs, status, cycles = run(args.study, name)
        correct = status == "DONE" and outs == expected
        in_budget = BUDGET[0] <= cycles <= BUDGET[1]
        ok = correct and in_budget
        failures += not ok
        if not correct:
            verdict = (f"FAIL expected {[f'{v:08x}' for v in expected]}"
                       f" got {[f'{v:08x}' for v in outs]}")
        elif not in_budget:
            verdict = f"FAIL correct, but outside the {BUDGET[0]:,}-{BUDGET[1]:,} cycle budget"
        else:
            verdict = "PASS"
        print(f"{name:<14} {status:<6} {cycles:>9}  {verdict}")
        golden[name] = {"outputs": [f"{v:08x}" for v in outs], "status": status,
                        "cycles": cycles, "match_reference": correct,
                        "in_budget": in_budget}
    results = golden_path(args.study)
    results.write_text(json.dumps(golden, indent=2) + "\n")
    print(f"wrote {results.relative_to(ROOT)}")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
