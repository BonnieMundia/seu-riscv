"""Python side of the fault injector: run the Verilator harness (inject.cpp) once.

    from injector import run
    run("build/seu/w2_qsort.hex", max_cycles=67600)                       # fault-free
    run("build/seu/w2_qsort.hex", 67600, site=s, cycle=10000)             # one flip

`site` is a descriptor.Site: the flip-flop's main bit plus any `also` bits are flipped
together. The result is the harness's JSON line as a dict (status, cycles, outputs,
bad_addr, injected, before, after). Deciding masked / SDC / ... is classify.py's job.
"""
import json
import os
import subprocess

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
BINARY = os.path.join(ROOT, "obj_dir_fi", "Vinject")       # built by `make fi`


def run(hexfile, max_cycles, site=None, cycle=None, binary=BINARY):
    args = [binary, f"+hex={hexfile}", f"+max_cycles={max_cycles}"]
    if site is not None:
        bits = (site.bit,) + tuple(site.also)
        args += [f"+sig={site.signal}", f"+bits={','.join(map(str, bits))}", f"+cycle={cycle}"]
    p = subprocess.run(args, capture_output=True, text=True, cwd=ROOT)
    lines = [l for l in p.stdout.splitlines() if l.startswith("{")]
    if not lines:
        raise RuntimeError(f"no result from {' '.join(args)}:\n{p.stdout}{p.stderr}")
    result = json.loads(lines[-1])
    if result["status"] == "error":
        raise RuntimeError(f"{result['error']} ({' '.join(args)})")
    return result
