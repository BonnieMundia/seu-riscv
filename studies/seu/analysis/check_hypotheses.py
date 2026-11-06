#!/usr/bin/env python3
"""Judge the approved E1 hypotheses (studies/seu/docs/hypotheses.md) from the raw CSV.

    check_hypotheses.py [studies/seu/results/raw/e1.csv]

Prints one verdict per hypothesis and writes studies/seu/results/e1_hypotheses.json.
"Exploratory" numbers at the end were not predicted in advance and are labelled so.
"""
import json
import os
import sys

import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "platform", "stats"))
sys.path.insert(0, os.path.join(ROOT, "platform", "fi"))
import descriptor
from rates import FAILURES, summarise, wilson

ALPHA = 0.05 / 7                                  # Bonferroni: one test per unit


def above(a, b):
    """True if interval a lies entirely above interval b."""
    return a[0] > b[1]


def share(rows, outcome):
    k, n = int((rows["outcome"] == outcome).sum()), len(rows)
    return {"k": k, "n": n, "share": k / n, "ci95": list(wilson(k, n))}


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        ROOT, "studies/seu/results/raw/e1.csv")
    df = pd.read_csv(path)
    s = summarise(df)["units"]
    pooled = {u: d["all_workloads"] for u, d in s.items()}
    workloads = sorted(df["workload"].unique())
    out = {}

    # H1: counters never fail
    k = pooled["counters"]["failures"]
    out["H1"] = {"supported": k == 0, "failures": k, "runs": pooled["counters"]["runs"],
                 "ci95": pooled["counters"]["ci95"]}

    # H2: control above every other unit, on every workload
    bad = [(w, u) for w in workloads for u in s if u != "control" and not above(
        s["control"]["workloads"][w]["ci95"], s[u]["workloads"][w]["ci95"])]
    out["H2"] = {"supported": not bad, "not_separated": bad}

    # H3: largest failure share per unit
    fails = df[df["outcome"].isin(FAILURES)]
    largest = {}
    for u in ("control", "regfile", "alu"):
        rows = fails[fails["unit"] == u]
        c = rows["outcome"].value_counts()
        largest[u] = {"largest": c.idxmax(), **{o: int(c.get(o, 0)) for o in FAILURES}}
    out["H3"] = {"supported": largest["control"]["largest"] == "hang"
                 and largest["regfile"]["largest"] == "sdc"
                 and largest["alu"]["largest"] == "sdc", "units": largest}

    # H4: pc above regfile, alu, memif, counters
    bad = [u for u in ("regfile", "alu", "memif", "counters")
           if not above(pooled["pc"]["ci95"], pooled[u]["ci95"])]
    out["H4"] = {"supported": not bad, "not_separated": bad,
                 "pc": pooled["pc"]["ci95"]}

    # H5: pc low bits vs high bits
    pc = df[df["unit"] == "pc"]
    low, high = pc[pc["bit"].between(2, 9)], pc[pc["bit"].between(16, 31)]
    h5 = {"low": {o: share(low, o) for o in ("sdc", "crash")},
          "high": {o: share(high, o) for o in ("sdc", "crash")}}
    h5["sdc_supported"] = above(h5["low"]["sdc"]["ci95"], h5["high"]["sdc"]["ci95"])
    h5["crash_supported"] = above(h5["high"]["crash"]["ci95"], h5["low"]["crash"]["ci95"])
    h5["supported"] = h5["sdc_supported"] and h5["crash_supported"]
    out["H5"] = h5

    # H6: regfile differs between workloads (Bonferroni)
    t = s["regfile"]["workload_test"]
    out["H6"] = {"supported": t["p"] < ALPHA, "alpha": ALPHA, **t}

    # H7: regfile below control
    out["H7"] = {"supported": above(pooled["control"]["ci95"], pooled["regfile"]["ci95"]),
                 "control": pooled["control"]["ci95"], "regfile": pooled["regfile"]["ci95"]}

    # Exploratory (not predicted): which units give the most failures per chip?
    desc, ff = descriptor.load(os.path.join(ROOT, "studies/seu/targets/soc_h0.yaml"))
    bits = {}
    for site in descriptor.sites(desc, ff):
        bits[site.unit] = bits.get(site.unit, 0) + 1
    weight = {u: bits[u] * pooled[u]["failure_rate"] for u in pooled}
    total = sum(weight.values())
    explore = {"share_of_failures_per_chip": {
        u: {"bits": bits[u], "rate": pooled[u]["failure_rate"], "share": weight[u] / total}
        for u in sorted(weight, key=weight.get, reverse=True)},
        "workload_tests": {u: d["workload_test"] for u, d in s.items()},
        "bad_addr_by_outcome": {o: int(n) for o, n in df[df["bad_addr"] == 1]["outcome"].value_counts().items()},
        "outcomes_pooled": {u: {o: int(((df["unit"] == u) & (df["outcome"] == o)).sum())
                                for o in ("masked",) + FAILURES} for u in s}}
    result = {"hypotheses": out, "exploratory": explore}

    for h in sorted(out):
        print(f"{h}: {'SUPPORTED' if out[h]['supported'] else 'CONTRADICTED'}  "
              + json.dumps({k: v for k, v in out[h].items() if k != 'supported'}))
    print("\nexploratory:", json.dumps(explore, indent=1))
    dest = os.path.join(ROOT, "studies/seu/results/e1_hypotheses.json")
    with open(dest, "w") as f:
        json.dump(result, f, indent=1, default=str)
        f.write("\n")
    print("wrote", dest)


if __name__ == "__main__":
    main()
