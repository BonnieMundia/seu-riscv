#!/usr/bin/env python3
"""List every flip-flop bit (and every memory) of a design, using Yosys.

Why: the fault injector must know *which* bits exist in real hardware. A Verilog
`reg` is not always a flip-flop: synthesis removes regs that are constant or never
used (e.g. PicoRV32's mem_instr, which our SoC never reads). We therefore ask Yosys
which flip-flops survive optimisation and record them with their RTL names.

Steps:
  1. Yosys: read the RTL, flatten the hierarchy (names become "cpu.reg_pc"), run the
     coarse part of `synth` (optimisations, no gate mapping), write JSON.
  2. Python: for every FF cell, map each output (Q) bit back to a signal name + bit.
     One wire can have several names (e.g. PicoRV32 `assign dbg_mem_addr = mem_addr`);
     we keep the name declared as `reg` in the source, because that is the variable
     the simulator stores and the injector can overwrite.
     One flip-flop can also drive several bits of a reg: Yosys merges bits that always
     hold the same value (PicoRV32 decoded_imm_j[31:20] are all copies of the sign bit).
     In hardware that is ONE flip-flop, so it is listed once, with the other RTL bits
     under "also"; the injector must flip all of them together.
  3. Memories (register file, RAM) are listed separately with width and depth.

Usage:
  list_ffs.py --top soc --out ff_list.json file1.v file2.v ...
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from collections import defaultdict

REG_DECL = re.compile(r"\breg\b")


def run_yosys(top, files, json_path):
    script = (f"read_verilog {' '.join(files)}; "
              f"synth -flatten -nofsm -top {top} -run :fine; "
              f"write_json {json_path}")
    subprocess.run(["yosys", "-q", "-p", script], check=True)
    version = subprocess.run(["yosys", "-V"], capture_output=True, text=True).stdout.strip()
    return version


def declared_as_reg(src, cache):
    """src is 'file:line.col-line.col'; True if that source line declares a reg."""
    path, pos = src.rsplit(":", 1)
    line = int(pos.split(".")[0])
    if path not in cache:
        with open(path) as f:
            cache[path] = f.read().splitlines()
    return bool(REG_DECL.search(cache[path][line - 1]))


def ff_bits(module):
    """Yield [(signal, bit), ...] per flip-flop output bit of a flattened module:
    the reg bits that this one flip-flop holds (usually exactly one)."""
    names = defaultdict(list)                       # Yosys bit id -> [(name, index, src)]
    for name, net in module["netnames"].items():
        if net.get("hide_name"):
            continue                                # internal $auto names
        offset = net.get("offset", 0)
        for i, b in enumerate(net["bits"]):
            if isinstance(b, int):                  # "0"/"1"/"x" are constants
                names[b].append((name, i + offset, net["attributes"].get("src", "")))
    cache = {}
    for cell in module["cells"].values():
        if "dff" not in cell["type"]:
            continue
        for b in cell["connections"]["Q"]:
            cands = names.get(b)
            if not cands:
                sys.exit(f"flip-flop output bit {b} has no public name")
            regs = sorted((c[0], c[1]) for c in cands if c[2] and declared_as_reg(c[2], cache))
            if len({name for name, _ in regs}) != 1:
                sys.exit(f"cannot choose one reg for flip-flop bit {b}: {cands}")
            yield regs


def memories(module):
    for cell in module["cells"].values():
        if cell["type"].startswith("$mem"):
            p = cell["parameters"]
            yield {"name": p["MEMID"].lstrip("\\"),
                   "width": int(p["WIDTH"], 2), "depth": int(p["SIZE"], 2),
                   "offset": int(p["OFFSET"], 2)}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--top", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("files", nargs="+")
    args = ap.parse_args()

    with tempfile.TemporaryDirectory() as tmp:
        js = os.path.join(tmp, "design.json")
        version = run_yosys(args.top, args.files, js)
        with open(js) as f:
            module = json.load(f)["modules"][args.top]

    bits = defaultdict(list)
    also = defaultdict(dict)
    for regs in ff_bits(module):
        sig, bit = regs[0]
        bits[sig].append(bit)
        if len(regs) > 1:
            also[sig][str(bit)] = [b for _, b in regs[1:]]
    ffs = []
    for s, b in sorted(bits.items()):
        entry = {"signal": s, "bits": sorted(b)}
        if also[s]:
            entry["also"] = also[s]               # same flip-flop also drives these bits
        ffs.append(entry)
    out = {
        "top": args.top,
        "yosys": version,
        "sources": [os.path.relpath(f) for f in args.files],
        "ff_bits": sum(len(f["bits"]) for f in ffs),
        "ffs": ffs,
        "memories": sorted(memories(module), key=lambda m: m["name"]),
    }
    with open(args.out, "w") as f:
        json.dump(out, f, indent=1)
        f.write("\n")
    print(f"{args.out}: {out['ff_bits']} flip-flop bits in {len(ffs)} signals, "
          f"{len(out['memories'])} memories")


if __name__ == "__main__":
    main()
