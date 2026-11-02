"""Tests for classify.py (pure Python, no simulator needed). Run: make fi-test"""
import pytest

from classify import OUTCOMES, classify

GOLDEN = {"outputs": ["cbf43926", "0a6e4633"], "cycles": 119032}


def run(status="done", outputs=("cbf43926", "0a6e4633"), cycles=119032, injected=True):
    return {"status": status, "cycles": cycles, "outputs": list(outputs),
            "bad_addr": False, "injected": injected}


def test_masked_same_outputs():
    assert classify(run(), GOLDEN) == "masked"


def test_masked_even_if_slower():
    assert classify(run(cycles=119500), GOLDEN) == "masked"


def test_sdc_wrong_value():
    assert classify(run(outputs=("cbf43926", "0a6e4632")), GOLDEN) == "sdc"


def test_sdc_missing_output():
    assert classify(run(outputs=("cbf43926",)), GOLDEN) == "sdc"


def test_sdc_extra_output():
    assert classify(run(outputs=("cbf43926", "0a6e4633", "0a6e4633")), GOLDEN) == "sdc"


def test_sdc_wrong_order():
    assert classify(run(outputs=("0a6e4633", "cbf43926")), GOLDEN) == "sdc"


def test_crash():
    assert classify(run(status="trap", outputs=()), GOLDEN) == "crash"


def test_hang():
    assert classify(run(status="hang", cycles=238064), GOLDEN) == "hang"


def test_not_injected_wins():
    assert classify(run(injected=False), GOLDEN, detected=True) == "not_injected"


def test_detected_beats_crash():
    assert classify(run(status="trap"), GOLDEN, detected=True) == "detected"


def test_unknown_status():
    with pytest.raises(ValueError):
        classify(run(status="error"), GOLDEN)


def test_always_a_known_outcome():
    for status in ("done", "trap", "hang"):
        assert classify(run(status=status), GOLDEN) in OUTCOMES
