"""Tests for rates.py. The rows here are made up by hand to test the arithmetic: not results."""
import pandas as pd
import pytest
from scipy.stats import binomtest

from rates import cell, summarise, wilson, workload_test


@pytest.mark.parametrize("k,n", [(0, 1068), (1, 1068), (81, 263), (534, 1068),
                                 (1067, 1068), (1068, 1068), (3, 10)])
def test_wilson_matches_scipy(k, n):
    ci = binomtest(k, n).proportion_ci(method="wilson")      # independent implementation
    assert wilson(k, n) == pytest.approx((ci.low, ci.high), abs=1e-12)


def test_wilson_zero_failures_still_has_an_upper_limit():
    low, high = wilson(0, 1068)
    assert low == 0 and 0.003 < high < 0.004


def test_wilson_half_at_1068_is_about_3_percent():
    # CLAUDE.md sample sizes: n = 1,068 gives +/- 3% at p = 0.5
    low, high = wilson(534, 1068)
    assert (high - low) / 2 == pytest.approx(0.03, abs=0.001)


def test_wilson_no_runs_is_an_error():
    with pytest.raises(ValueError):
        wilson(0, 0)


def frame(rows):
    return pd.DataFrame(rows, columns=["unit", "workload", "outcome"])


def test_cell_counts_failures():
    rows = frame([("pc", "w1", o) for o in ["masked", "masked", "sdc", "crash", "hang", "detected"]])
    c = cell(rows)
    assert c["runs"] == 6 and c["failures"] == 3 and c["failure_rate"] == 0.5
    assert c["masked"] == 2 and c["detected"] == 1


def test_not_injected_is_left_out():
    rows = frame([("pc", "w1", "sdc"), ("pc", "w1", "masked"), ("pc", "w1", "not_injected")])
    s = summarise(rows)
    assert s["runs"] == 3 and s["not_injected"] == 1
    assert s["units"]["pc"]["all_workloads"]["runs"] == 2


def test_workload_test_finds_a_clear_difference():
    rows = frame([("pc", "w1", "sdc")] * 50 + [("pc", "w1", "masked")] * 50 +
                 [("pc", "w2", "sdc")] * 5 + [("pc", "w2", "masked")] * 95)
    t = workload_test(rows)
    assert t["p"] < 0.001 and t["dof"] == 1 and t["min_expected"] >= 5


def test_workload_test_gives_up_when_nothing_failed():
    rows = frame([("counters", "w1", "masked")] * 10 + [("counters", "w2", "masked")] * 10)
    assert workload_test(rows) is None


def test_workload_test_needs_two_workloads():
    rows = frame([("pc", "w1", "sdc"), ("pc", "w1", "masked")])
    assert workload_test(rows) is None
