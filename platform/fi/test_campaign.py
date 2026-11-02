"""Tests for the campaign planner (sampling). No simulator needed."""
from campaign import cell_seed, plan
from descriptor import Site

SITES = [Site("pc", "cpu.reg_pc", b, ()) for b in range(1, 32)] + \
        [Site("regfile", f"cpu.cpuregs[{w}]", b, ()) for w in range(1, 32) for b in range(32)]
GOLDEN = {"w1": {"cycles": 1000}, "w2": {"cycles": 500}}
EXP = {"name": "t", "study": "seu", "workloads": ["w1", "w2"], "units": "all",
       "runs_per_cell": 50, "seed": 7}


def test_plan_size_and_ids_unique():
    jobs = plan(EXP, SITES, GOLDEN)
    assert len(jobs) == 2 * 2 * 50
    assert len({j["run_id"] for j in jobs}) == len(jobs)


def test_same_seed_same_plan():
    a = [(j["site"], j["cycle"]) for j in plan(EXP, SITES, GOLDEN)]
    b = [(j["site"], j["cycle"]) for j in plan(EXP, SITES, GOLDEN)]
    assert a == b


def test_other_seed_other_plan():
    a = [(j["site"], j["cycle"]) for j in plan(EXP, SITES, GOLDEN)]
    b = [(j["site"], j["cycle"]) for j in plan({**EXP, "seed": 8}, SITES, GOLDEN)]
    assert a != b


def test_adding_a_workload_does_not_change_other_cells():
    small = plan({**EXP, "workloads": ["w2"]}, SITES, GOLDEN)
    big = [j for j in plan(EXP, SITES, GOLDEN) if j["workload"] == "w2"]
    assert [(j["site"], j["cycle"]) for j in small] == [(j["site"], j["cycle"]) for j in big]


def test_sites_stay_in_unit_and_cycles_in_range():
    for j in plan(EXP, SITES, GOLDEN):
        assert j["site"].unit == j["unit"]
        assert 0 <= j["cycle"] < GOLDEN[j["workload"]]["cycles"]


def test_cell_seed_is_stable():
    # must never change between Python runs or machines (sha256, not hash())
    assert cell_seed(1, "w2_qsort", "pc") == cell_seed(1, "w2_qsort", "pc")
    assert cell_seed(1, "w2_qsort", "pc") != cell_seed(1, "w2_qsort", "alu")
