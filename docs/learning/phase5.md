# Phase 5 walkthrough: from runs to numbers (Gate 2, statistics)

Goal: turn a campaign CSV into failure rates that can be defended, and write down what we
expect **before** we look. Commands: `make stats-test`, `make rates EXP=<name>`.

---

## 1. What a campaign measures

Each run is one random flip: a random flip-flop of the unit at a random cycle. Its result
is either a failure (SDC, crash or hang) or not. So a cell of 1,068 runs is like tossing a
coin 1,068 times, and the failure rate is an **estimate** of the true chance. Another seed
would give a slightly different number, so every rate needs an interval saying how
far off it could be.

## 2. Wilson interval: `platform/stats/rates.py`, `wilson()`

The formula most people know is `p ± 1.96·√(p(1−p)/n)`. It fails exactly where we need it.
With 0 failures out of 1,068, p = 0 and the interval is [0, 0], as if the true rate were
proved to be zero. Near 0 it can also go below 0.

The **Wilson** interval comes from solving the same normal approximation the other way
round: "which true rates would make what I saw unsurprising?" The result stays inside
[0, 1] and gives a real upper limit at 0 failures, about 3.84/(n + 3.84), or 0.36% for
n = 1,068. That matters for this study: the counters should give 0 failures.

In the code, `centre` is p pulled slightly toward 0.5, and `half` is the half-width. The
two `if` lines make the edges exactly 0 and 1 (rounding could otherwise give −1e−17).

`1.96` is not typed in: `NormalDist().inv_cdf(0.975)` computes it. 95% in the middle leaves
2.5% in each tail, so the value is at the 97.5% point.

## 3. Definitions used in `cell()` and `summarise()`

- **Failure rate** = (SDC + crash + hang) / (runs that were injected).
- `detected` is counted separately. It only appears with the hardened variants.
- `not_injected` is left out of every rate and its count is printed. It should be 0,
  because cycles are drawn below the golden cycle count. If it is not 0, look into it.
- The rate is **per flip in that unit**, not per unit. `regfile` has 992 bits and `control`
  has 20. A low per-flip rate in a big unit can still mean more failures per chip. To compare
  chips, multiply the rate by the bit count. Keep the two ideas apart in the paper.

## 4. Chi-square: does a unit behave differently per workload? (RQ1)

`workload_test()` builds a table with one row per workload and two columns (failed, not
failed), then asks: if all workloads had the same true rate, how surprising is this table?
A small `p` means "surprising", so the workloads probably differ.

- It returns `None` if every run had the same result (for example counters with 0 failures):
  there is nothing to compare, and SciPy would refuse the table.
- It reports `min_expected`. The test is only trustworthy when each expected count is
  at least about 5, so the report warns below that.
- We run one test per unit, 7 in all. Testing many things makes a lucky p < 0.05 more
  likely, so `hypotheses.md` uses p < 0.05/7 (the **Bonferroni** correction).

## 5. Tests: `platform/stats/test_rates.py`

15 tests. The most useful one compares `wilson()` with SciPy's own implementation
(`binomtest(...).proportion_ci(method="wilson")`) on seven cases, including 0 and n. Two
independent implementations agreeing to 12 decimals is strong evidence. Another checks
that n = 1,068 at p = 0.5 gives ±3%, the figure in CLAUDE.md. The rows in the tests are made
up to check arithmetic. They are not results.

## 6. Why hypotheses come first: `studies/seu/docs/hypotheses.md`

If you look at the data and then explain it, almost any pattern seems obvious afterwards.
Writing predictions first, with the test that will judge them, lets a reviewer see which
findings were predicted and which were noticed later. It is a **draft for you to review**,
and it records honestly that we had already seen a few single flips.

## 7. The E1 plan: `studies/seu/experiments/e1.yaml`

5 workloads × 7 units × 1,068 = **37,380 runs**. The plan was checked without running
anything: it produces exactly 37,380 unique run ids, and `make campaign EXP=e1` stops at the
guard. Do not change the seed after the campaign has started.

## 7b. E1 results (6 Nov 2026)

Ran from a clean commit (4d97e70) on 8 workers in 119 s. Checks: 37,380 unique runs, 1,068 in
every cell, 0 `not_injected`, every hang stopped at exactly 2 × golden cycles, and 350 randomly
chosen rows replayed one by one gave the same outcome and cycle count.

| unit | bits | failure rate, pooled [95% Wilson] |
|---|---|---|
| control | 20 | 64.2% [62.9, 65.5] |
| pc | 62 | 46.8% [45.4, 48.1] |
| regfile | 992 | 29.9% [28.7, 31.2] |
| memif | 107 | 13.9% [13.0, 14.9] |
| decoder | 125 | 13.5% [12.6, 14.5] |
| alu | 133 | 12.3% [11.4, 13.2] |
| counters | 128 | 0.0% [0.0, 0.07] |

**Two rankings, two answers.** Per flip, control is worst. Per chip, the regfile gives 76.8%
of failures, because it has 992 bits (rate × bits, assuming each bit is equally likely to be hit).
This is the point of RQ2: hardening the regfile (H2) and hardening control (H3) fix different
things. That per-chip figure is exploratory, and it assumes a regfile bit is as easy to upset as a
flip-flop. A real regfile is often built differently, so this needs stating in the paper.

**Why the regfile depends on the workload.** Its rate runs from 15.2% (W2) to 43.2% (W4). pc shows
no workload effect (p = 0.58). That is a candidate explanation, not yet a measured one:
a register matters only while it holds a value that will be read later, and that time differs
per workload, while the PC is in use all the time in every workload.

Verdicts: `studies/seu/docs/hypotheses.md`. All 7 supported, with the caveat there.

---

## 8. Do it yourself

1. **Predict, then compute.** What is the Wilson upper limit for 0 failures in 5,340 runs
   (H1)? Use 3.84/(n + 3.84), then check:
   `cd platform/stats && ~/.venv/bin/python -c "from rates import wilson; print(wilson(0, 5340))"`.
   *Expect:* about 0.00072, or 0.072%.
2. **See the simple formula fail.** For k = 2, n = 100 compute `p ± 1.96√(p(1−p)/n)` by hand,
   then run `wilson(2, 100)`. *Expect:* simple low limit is below 0 (about −0.007); Wilson's
   is above 0 (about 0.0055).
3. **Break a test.** On a `play/` branch, change `z2 / (2 * n)` to `z2 / n` in `wilson()` and
   run `make stats-test`. *Expect:* `test_wilson_matches_scipy` fails. Then `git restore`.
4. **Review `hypotheses.md`.** For each row, say whether you agree with the reason. Change
   anything you disagree with, then approve it. Viva practice: why does H1 say "stop and
   investigate" instead of just reporting the number?

5. **Re-derive a number.** `make rates EXP=e1`, then check by hand that regfile gives 76.8% of
   failures: multiply each unit's rate by its bits, then take regfile's share of the total.
6. **Replay one row.** Pick any `sdc` row in `studies/seu/results/raw/e1.csv` and rerun it
   with `./obj_dir_fi/Vinject` using its `signal`, `bit` and `cycle`, with
   `+max_cycles=` set to 2 × that workload's golden cycles. *Expect:* the same `cycles_run`, and an output
   different from golden. If `also` is not empty, add those bits to `+bits=`.

## 9. Sources

- **Wilson, E. B. (1927)**, "Probable Inference, the Law of Succession, and Statistical
  Inference", *Journal of the American Statistical Association*.
  doi:10.1080/01621459.1927.10502953
- **Brown, Cai, DasGupta (2001)**, "Interval Estimation for a Binomial Proportion",
  *Statistical Science*: why the simple interval is unreliable and Wilson is
  recommended. doi:10.1214/ss/1009213286
- **SciPy docs**: `scipy.stats.binomtest`, `scipy.stats.chi2_contingency`:
  https://docs.scipy.org/doc/scipy/reference/stats.html
- Beginner-friendly: Wikipedia, "Binomial proportion confidence interval".
