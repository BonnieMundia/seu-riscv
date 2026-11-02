#!/usr/bin/env python3
"""Load and check a target descriptor (which bits may be hit, and which unit they belong to).

A descriptor (YAML, one per study + variant) points to the Yosys flip-flop list and
sorts every flip-flop bit into a unit, or excludes it with a reason. This file turns it
into a flat list of fault sites that the injector and the campaign runner use.

The check is strict on purpose: a bit that is in no unit, or in two units, is an error.
Otherwise a typo in a pattern would silently drop bits from the study and change every
per-unit failure rate.

Usage:
  descriptor.py studies/seu/targets/soc_h0.yaml      # check + print a summary table
"""
import argparse
import fnmatch
import json
import os
import sys
from collections import namedtuple

import yaml

# One fault site = one flip-flop. `also` = other bits of the same signal held by the
# same flip-flop (see platform/synth/list_ffs.py); the injector flips them together.
Site = namedtuple("Site", "unit signal bit also")


def load(path):
    with open(path) as f:
        desc = yaml.safe_load(f)
    with open(os.path.join(os.path.dirname(path), desc["ff_list"])) as f:
        ff = json.load(f)
    return desc, ff


def match_unit(signal, units):
    hits = [u for u, pats in units.items() if any(fnmatch.fnmatchcase(signal, p) for p in pats)]
    return hits


def sites(desc, ff):
    """Return the list of Site, or exit with every problem found."""
    errors = []
    excl = {}
    for e in desc.get("exclude", []):
        excl.setdefault(e["signal"], set()).update(e.get("bits", ["*"]))
    known = {f["signal"] for f in ff["ffs"]}
    for s in excl:
        if s not in known:
            errors.append(f"exclude: {s} is not in the flip-flop list")
    units = desc["units"]
    for u, pats in units.items():
        for p in pats:
            if not any(fnmatch.fnmatchcase(s, p) for s in known):
                errors.append(f"unit {u}: pattern {p} matches no flip-flop")

    out = []
    for f in ff["ffs"]:
        sig, gone = f["signal"], excl.get(f["signal"], set())
        if "*" in gone:
            continue
        hits = match_unit(sig, units)
        if len(hits) != 1:
            errors.append(f"{sig}: in {len(hits)} units {hits} (must be exactly 1)")
            continue
        also = f.get("also", {})
        for b in f["bits"]:
            if b not in gone:
                out.append(Site(hits[0], sig, b, tuple(also.get(str(b), ()))))
        for b in gone - set(f["bits"]):
            errors.append(f"exclude: {sig}[{b}] is not a flip-flop bit")

    mems = {m["name"]: m for m in ff["memories"]}
    for name, spec in desc.get("memories", {}).items():
        if name not in mems:
            errors.append(f"memory {name} is not in the flip-flop list")
            continue
        if "exclude" in spec:
            continue
        lo, hi = spec["words"]
        m = mems[name]
        if not (m["offset"] <= lo <= hi < m["offset"] + m["depth"]):
            errors.append(f"memory {name}: words {lo}..{hi} outside 0..{m['depth'] - 1}")
            continue
        for w in range(lo, hi + 1):
            for b in range(m["width"]):
                out.append(Site(spec["unit"], f"{name}[{w}]", b, ()))
    for name in mems:
        if name not in desc.get("memories", {}):
            errors.append(f"memory {name}: not assigned to a unit and not excluded")

    if errors:
        sys.exit("descriptor check FAILED:\n  " + "\n  ".join(errors))
    return out


def summary(desc, ff, out):
    units = list(desc["units"]) + sorted({s.unit for s in out} - set(desc["units"]))
    excluded = ff["ff_bits"] - sum(1 for s in out if "[" not in s.signal)
    print(f"{'unit':10s} {'signals':>7s} {'bits':>5s}")
    for u in units:
        mine = [s for s in out if s.unit == u]
        print(f"{u:10s} {len({s.signal.split('[')[0] for s in mine}):7d} {len(mine):5d}")
    print(f"{'total':10s} {'':7s} {len(out):5d}   "
          f"(flip-flop bits excluded: {excluded}; shared flip-flops: "
          f"{sum(1 for s in out if s.also)})")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("descriptor")
    args = ap.parse_args()
    desc, ff = load(args.descriptor)
    out = sites(desc, ff)
    summary(desc, ff, out)
    print("descriptor check PASS")


if __name__ == "__main__":
    main()
