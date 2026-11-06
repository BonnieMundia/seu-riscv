# Hypotheses for E1 (baseline campaign)

Status: **APPROVED by Boniface, 6 Nov 2026, before E1 ran.**
Written 6 Nov 2026, before any E1 run.

**Honest note on what was already seen.** These predictions are not fully blind. Before
writing them we had seen about a dozen hand-picked flips on W2 (docs/learning/phase4.md §4b)
and the 70-run smoke campaign on W2 (10 runs per unit, same counts in the plumbing check
and in `make smoke`). Neither has real statistical weight, but both can bias a prediction,
and the paper must say so.

Rules: a hypothesis is judged by the 95% Wilson intervals and the tests named below. A
contradicted hypothesis stays in this file, is marked contradicted, and is reported plainly.
"Failure" = SDC + crash + hang. A rate is per flip in the unit: P(failure | one random flip
in a random flip-flop of that unit at a random cycle).

| # | Prediction | Reason (from the design) | Judged by |
|---|---|---|---|
| H1 | `counters` has **zero** failures in all 5 workloads. | No workload reads `rdcycle`/`rdinstret`, so the value can never reach an output. | 0 failures in 5,340 runs. Any failure means a bug in the injector or a wrong assumption: stop and investigate. |
| H2 | `control` has the highest failure rate of the 7 units, on every workload. | `cpu_state` is one-hot and used every cycle; a second bit set can leave the state machine stuck. | Its Wilson interval lies above every other unit's, per workload. |
| H3 | `control` failures are mostly hangs; `regfile` and `alu` failures are mostly SDC. | A broken state machine stops; a wrong data value flows on to the answer. | Largest outcome share per unit, all workloads pooled. |
| H4 | `pc` failure rate is above `regfile`, `alu`, `memif` and `counters`. | Both PC registers are read at every instruction boundary, while most register words are idle at any moment. | Non-overlapping Wilson intervals, all workloads pooled. |
| H5 | In `pc`, low bits (2–9) give a larger SDC share than high bits (16–31), and high bits give a larger crash share. | A low bit lands on a real instruction nearby; a high bit lands outside the 64 KB RAM, where reads return 0, an illegal instruction. | Two-proportion comparison with Wilson intervals on the `bit` column. Bits 10–15 stay in the program's address space only in part, so they are left out. |
| H6 | `regfile` failure rate differs between workloads. | Workloads use different numbers of registers for different lengths of time. | Chi-square across the 5 workloads, p < 0.05 / 7 (Bonferroni, one test per unit). |
| H7 | `regfile` per-flip rate is below `control`, even though it has by far the most bits. | Most words are unused or about to be overwritten at any moment. | Non-overlapping Wilson intervals, all workloads pooled. |

Not predicted in advance: the order of `decoder`, `alu` and `memif`, because we have no
strong design reason for one. Any statement about their order is exploratory.

## Verdicts (E1, 6 Nov 2026)

From `studies/seu/analysis/check_hypotheses.py` (numbers: `studies/seu/results/e1_hypotheses.json`,
37,380 runs at commit 4d97e70). Failure rates are all workloads pooled unless stated.

| # | Verdict | Evidence |
|---|---|---|
| H1 | Supported | counters: 0 failures in 5,340 runs, 95% upper limit 0.07% |
| H2 | Supported | control's interval is above every other unit on all 5 workloads (64.2% pooled) |
| H3 | Supported | largest failure type: control hang 2,244 of 3,429; regfile SDC 922 of 1,599; alu SDC 540 of 656 |
| H4 | Supported | pc 46.8% [45.4, 48.1], above regfile 29.9% [28.7, 31.2], memif, alu, counters |
| H5 | Supported | low bits: SDC 22.4%, crash 12.2%; high bits: SDC 0 of 2,738, crash 47.8% |
| H6 | Supported | regfile chi2 = 357, dof 4, p = 5.4e-76 (limit 0.00714) |
| H7 | Supported | regfile 29.9% is below control 64.2%; intervals do not overlap |

All seven supported is not proof of good foresight: see the note at the top of this file.

Exploratory, not predicted:
- If every bit is equally likely to be hit, the regfile gives 76.8% of a chip's failures, because
  of its 992 bits, although control has the highest rate per flip. Control gives 3.3%.
- Workload effect passes the 0.05/7 limit for control (p = 5.1e-10) and memif (p = 0.0036), as well as
  regfile. alu (p = 0.011), decoder (p = 0.063) and pc (p = 0.58) do not.
