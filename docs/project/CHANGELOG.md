# Project documents: version log

Three documents live here (rule set by Boniface, 2 Nov 2026):
1. `technical.md`: in-depth technical documentation
2. `summary.md`: plain-language summary for non-engineers
3. `seu-riscv-deck.pptx`: slide deck (visual collage of stages and results)

Source of truth is the repo. Numbers are only copied from repo files, never invented.
On "update docs": re-read the repo from the commit below onwards (`git log dbbaa48..HEAD`),
add what changed, bump the version, and add an entry here listing the changes.

## v1 (2 Nov 2026) — repo at `dbbaa48`
First version of all three documents. Covers everything up to Gate 1 sign-off:
- Week 0 setup, Phase 1 hello-world SoC (191 cycles), tool versions.
- Workloads W1–W5 with golden outputs and cycle counts (`studies/seu/results/golden_runs.json`) and the design decisions behind them (`studies/seu/docs/decisions.md`).
- Python RV32I golden model, cocotb lockstep check, isa_test (37/37 instructions), planted-bug test.
- Gate 1 met and signed off 2 Nov 2026; platform migration done the same day.
- Planned work (injector, H0–H5, E1–E4, synthesis, deliverables) included and marked PLANNED, with no results.
- Gaps noted: no literature review, hypotheses.md or LibreLane version in the repo yet.
