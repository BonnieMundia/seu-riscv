"""One place that knows where programs and their expected outputs live.

    workloads, tests = load(study)
workloads: name -> reference function, from studies/<study>/sw/ref/workloads.py
           (a study without that file yet has no workloads);
tests:     name -> expected-output function, from platform/tests/sw/tests_ref.py.
"""

import importlib.util
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]


def _module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load(study):
    ref = ROOT / "studies" / study / "sw" / "ref" / "workloads.py"
    workloads = _module(ref, f"{study}_workloads").WORKLOADS if ref.exists() else {}
    tests = _module(ROOT / "platform" / "tests" / "sw" / "tests_ref.py", "tests_ref").TESTS
    return workloads, tests


def build_dir(study):
    return ROOT / "build" / study


def golden_path(study):
    return ROOT / "studies" / study / "results" / "golden_runs.json"
