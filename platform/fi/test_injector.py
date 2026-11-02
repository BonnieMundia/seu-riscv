"""Tests for the Verilator injector (needs `make fi` and the workload hex files).

What they prove:
  - fault-free runs reproduce studies/seu/results/golden_runs.json exactly
    (same outputs, same cycle count -> the harness counts cycles like tb_soc.v);
  - a flip changes exactly the requested bits, at the requested cycle;
  - runs are deterministic (same flip -> same result).
"""
import json
import os

import pytest

from descriptor import Site
from injector import ROOT, run

GOLDEN = json.load(open(os.path.join(ROOT, "studies/seu/results/golden_runs.json")))
HEX = os.path.join(ROOT, "build/seu/{}.hex")
W2 = HEX.format("w2_qsort")
LIMIT = 2 * GOLDEN["w2_qsort"]["cycles"]


@pytest.mark.parametrize("w", sorted(GOLDEN))
def test_fault_free_matches_golden(w):
    r = run(HEX.format(w), 2 * GOLDEN[w]["cycles"])
    assert r["status"] == "done" and not r["injected"]
    assert r["outputs"] == GOLDEN[w]["outputs"]
    assert r["cycles"] == GOLDEN[w]["cycles"]


def test_flip_hits_the_right_bit_at_the_right_cycle():
    # count_cycle counts clock cycles since reset, so at cycle 1000 it must read 1000
    r = run(W2, LIMIT, Site("counters", "cpu.count_cycle", 63, ()), cycle=1000)
    assert r["before"] == f"{1000:016x}"
    assert r["after"] == f"{(1 << 63) | 1000:016x}"


def test_shared_flip_flop_flips_all_bits():
    site = Site("decoder", "cpu.decoded_imm_j", 20, tuple(range(21, 32)))
    r = run(W2, LIMIT, site, cycle=10000)
    assert int(r["before"], 16) ^ int(r["after"], 16) == 0xFFF00000


def test_regfile_word():
    r = run(W2, LIMIT, Site("regfile", "cpu.cpuregs[2]", 4, ()), cycle=10000)
    assert int(r["before"], 16) ^ int(r["after"], 16) == 1 << 4


def test_after_end_is_not_injected():
    r = run(W2, LIMIT, Site("pc", "cpu.reg_pc", 5, ()), cycle=LIMIT + 1)
    assert not r["injected"] and r["outputs"] == GOLDEN["w2_qsort"]["outputs"]


def test_deterministic():
    site = Site("pc", "cpu.reg_next_pc", 2, ())
    assert run(W2, LIMIT, site, cycle=10000) == run(W2, LIMIT, site, cycle=10000)


def test_bad_bit_is_an_error():
    with pytest.raises(RuntimeError):
        run(W2, LIMIT, Site("pc", "cpu.reg_pc", 40, ()), cycle=10)
