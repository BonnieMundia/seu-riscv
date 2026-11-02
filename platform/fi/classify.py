"""Outcome classifier: compare one faulty run with the golden (fault-free) run.

EXERCISE FOR BONIFACE (trainer rule 5) - write classify() below, then run
    make fi-test
until every test in platform/fi/test_classify.py passes (make fi-test: 29 passed). Spec:

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

Hint: rules 1-4 are one `if` each; rule 5 is a single list comparison.
"""

OUTCOMES = ("not_injected", "detected", "crash", "hang", "masked", "sdc")


def classify(run, golden, detected=False):
    raise NotImplementedError("Boniface: write me (see the docstring above)")
