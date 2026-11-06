#!/usr/bin/env python3
"""Turn a campaign CSV into failure rates with 95% Wilson intervals, and chi-square tests.

    rates.py studies/seu/results/raw/e1.csv      # prints tables, writes <name>_rates.json

Failure = sdc + crash + hang. "masked" is not a failure; "detected" (hardened variants) is
counted on its own; "not_injected" runs are left out of every rate (the flip never happened,
so they say nothing about the design) and their number is reported.

Why Wilson and not "p +/- 1.96*sqrt(p(1-p)/n)": the simple formula gives an interval of width
zero at 0 failures, as if 0 out of 1,068 proved the rate is exactly 0, and it can go below 0.
Wilson stays inside [0, 1] and still gives an honest upper limit when nothing failed.
"""
import argparse
import json
import math
import os
from statistics import NormalDist

import pandas as pd
from scipy.stats import chi2_contingency

Z = NormalDist().inv_cdf(0.975)                 # 1.95996...: 95% two-sided
FAILURES = ("sdc", "crash", "hang")
SHOWN = ("masked", "sdc", "crash", "hang", "detected")


def wilson(k, n, z=Z):
    """95% Wilson score interval for k successes out of n: (low, high)."""
    if n == 0:
        raise ValueError("no runs")
    p = k / n
    z2 = z * z
    centre = (p + z2 / (2 * n)) / (1 + z2 / n)
    half = z * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n)) / (1 + z2 / n)
    # exact at the edges (rounding could otherwise give -1e-17)
    low = 0.0 if k == 0 else centre - half
    high = 1.0 if k == n else centre + half
    return low, high


def cell(rows):
    """Counts and rates for one group of rows."""
    counts = {o: int((rows["outcome"] == o).sum()) for o in SHOWN}
    n = sum(counts.values())
    failed = sum(counts[o] for o in FAILURES)
    low, high = wilson(failed, n)
    return {"runs": n, **counts, "failures": failed, "failure_rate": failed / n,
            "ci95": [low, high]}


def workload_test(rows):
    """Does the failure rate of one unit differ between workloads? Chi-square, failed vs not.

    Returns None when the test cannot say anything: all runs failed or none did, or fewer than
    two workloads. `min_expected` below 5 means the chi-square approximation is unreliable.
    """
    failed = rows["outcome"].isin(FAILURES)
    table = pd.crosstab(rows["workload"], failed)
    if table.shape[0] < 2 or table.shape[1] < 2:
        return None
    chi2, p, dof, expected = chi2_contingency(table, correction=False)
    return {"chi2": float(chi2), "dof": int(dof), "p": float(p),
            "min_expected": float(expected.min())}


def summarise(df):
    used = df[df["outcome"] != "not_injected"]
    units = {}
    for u, rows in used.groupby("unit"):
        units[u] = {"all_workloads": cell(rows),
                    "workloads": {w: cell(r) for w, r in rows.groupby("workload")},
                    "workload_test": workload_test(rows)}
    return {"runs": len(df), "not_injected": len(df) - len(used), "units": units}


def percent(x):
    return f"{100 * x:6.2f}%"


def report(s):
    print(f"{s['runs']} runs, {s['not_injected']} not injected (left out)\n")
    print(f"{'unit':10s} {'workload':15s} {'runs':>6s} {'failed':>6s} {'rate':>7s}  95% Wilson")
    for u, d in sorted(s["units"].items(), key=lambda kv: -kv[1]["all_workloads"]["failure_rate"]):
        for w, c in sorted(d["workloads"].items()) + [("ALL", d["all_workloads"])]:
            lo, hi = c["ci95"]
            print(f"{u:10s} {w:15s} {c['runs']:6d} {c['failures']:6d} {percent(c['failure_rate'])}"
                  f"  [{percent(lo)}, {percent(hi)}]")
    print("\nDoes the failure rate differ between workloads? (chi-square, per unit)")
    for u, d in sorted(s["units"].items()):
        t = d["workload_test"]
        if t is None:
            print(f"{u:10s} not testable (all runs had the same result, or one workload)")
        else:
            note = "" if t["min_expected"] >= 5 else "  (min expected < 5: unreliable)"
            print(f"{u:10s} chi2={t['chi2']:.2f} dof={t['dof']} p={t['p']:.3g}{note}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("csv")
    args = ap.parse_args()
    s = summarise(pd.read_csv(args.csv))
    report(s)
    out = os.path.join(os.path.dirname(os.path.dirname(args.csv)),
                       os.path.basename(args.csv).replace(".csv", "_rates.json"))
    with open(out, "w") as f:
        json.dump(s, f, indent=1)
        f.write("\n")
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
