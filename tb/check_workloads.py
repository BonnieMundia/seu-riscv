"""Build and run every workload on the RTL, and compare against the Python reference.

Usage:  make check        (or: python tb/check_workloads.py [workload ...])

For each workload in sw/ref/workloads.py:
  1. `make sw PROG=<name>` builds the ELF + hex,
  2. the Verilator simulation runs it and prints OUT / DONE|TRAP|HANG lines,
  3. the OUT values are compared with the Python reference.
Writes results/golden_runs.json (outputs + cycle counts of the fault-free runs);
the fault-injection "Hang" rule (> 2x golden cycles) will read the cycles from there.
"""

import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "sw" / "ref"))
from workloads import WORKLOADS  # noqa: E402

SIM = ROOT / "obj_dir" / "Vtb_soc"
MAX_CYCLES = 1_000_000


def run(name):
    subprocess.run(["make", "-s", "sw", f"PROG={name}"], cwd=ROOT, check=True)
    hexfile = ROOT / "sw" / "build" / f"{name}.hex"
    out = subprocess.run(
        [str(SIM), f"+hex={hexfile}", f"+max_cycles={MAX_CYCLES}"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout
    outs = [int(v, 16) for v in re.findall(r"^OUT ([0-9a-f]{8})$", out, re.M)]
    end = re.search(r"^(DONE|TRAP|HANG) cycles=(\d+)$", out, re.M)
    return outs, end.group(1), int(end.group(2))


def main():
    names = sys.argv[1:] or list(WORKLOADS)
    subprocess.run(["make", "-s", str(SIM.relative_to(ROOT))], cwd=ROOT, check=True)
    golden, failures = {}, 0
    print(f"{'workload':<14} {'status':<6} {'cycles':>9}  result")
    for name in names:
        expected = WORKLOADS[name]()
        outs, status, cycles = run(name)
        ok = status == "DONE" and outs == expected
        failures += not ok
        verdict = "PASS" if ok else (
            f"FAIL expected {[f'{v:08x}' for v in expected]} got {[f'{v:08x}' for v in outs]}")
        print(f"{name:<14} {status:<6} {cycles:>9}  {verdict}")
        golden[name] = {"outputs": [f"{v:08x}" for v in outs], "status": status,
                        "cycles": cycles, "match_reference": ok}
    results = ROOT / "results" / "golden_runs.json"
    results.write_text(json.dumps(golden, indent=2) + "\n")
    print(f"wrote {results.relative_to(ROOT)}")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
