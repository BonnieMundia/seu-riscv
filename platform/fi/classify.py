"""Outcome classifier: compare one faulty run with the golden (fault-free) run.

Written by Claude at Boniface's request (6 Nov 2026), for Boniface to review. Tests:
platform/fi/test_classify.py (make fi-test). Spec:

Inputs
  run     dict from injector.run(): keys status ("done" | "trap" | "hang"), cycles (int),
          outputs (list of hex strings), bad_addr (bool), injected (bool)
  golden  dict with the fault-free "outputs" (list of hex strings) and "cycles" (int),
          e.g. one entry of studies/seu/results/golden_runs.json
  detected  True if a protection mechanism raised its flag during the run (variants
          H1-H5; always False for H0)

Return exactly one of these strings, checking the rules IN THIS ORDER:
  1. "not_injected" if the flip never happened (the program ended before the cycle)
  2. "detected"     if detected is True
  3. "crash"        if the core trapped (status "trap")
  4. "hang"         if the run hit the time limit (status "hang"; the runner sets the
                    limit to 2 x golden cycles, so this is the "> 2x golden" rule)
  5. "masked"       if it finished with exactly the golden outputs (same values, same
                    order, same count) - even if it took a different number of cycles
  6. "sdc"          otherwise (finished, but wrong or missing or extra outputs)
Any other status: raise ValueError.
"""

OUTCOMES = ("not_injected", "detected", "crash", "hang", "masked", "sdc")


def classify(run, golden, detected=False):
    if not run["injected"]:
        return "not_injected"
    if detected:
        return "detected"
    status = run["status"]
    if status == "trap":
        return "crash"
    if status == "hang":
        return "hang"
    if status != "done":
        raise ValueError(f"unknown status: {status}")
    return "masked" if run["outputs"] == golden["outputs"] else "sdc"
