# Platform + studies: migration plan

Status: **EXECUTED on Mon 2 Nov 2026** (brought forward from 9 Nov after Gate 1 was
signed off), on branch `restructure`, merged into main by fast-forward; tag
`pre-restructure` marks the old layout. Sections 3–6 are kept as the record of what was
done. Differences from the plan: `hello.c` and `isa_test.c` are platform test programs
with expected outputs in `platform/tests/sw/tests_ref.py`; `platform/tests/programs.py` is
the one place that knows where programs and references live; `make golden` replaces
`make check` (kept as an alias).
After execution this file becomes the platform description (descriptors, classifier hook,
results schema, trace export); those sections are stubs until the injector exists.

## 1. Where the repo is today (2 Nov 2026)

Flat single-study layout. What exists: PicoRV32 (pinned, unmodified), SoC + testbench,
crt0/link/common runtime, hello + W1, Python output references, `make check` (outputs +
cycle budget + golden_runs.json). Empty placeholders: model/ fi/ synth/ viz/ analysis/
results/ paper/ rtl/variants/. No injector, runner, ISS, cocotb or Yosys listing yet, so
nothing needs refactoring to the descriptor model: those are built directly in platform/.

## 2. Target layout (deviations from the brief are marked ★)

```
platform/
  rtl/picorv32/   picorv32.v (+ COPYING, the upstream ISC licence) + UPSTREAM_COMMIT
  rtl/soc/        soc.v, tb_soc.v
  sw/runtime/  ★  crt0.S, link.ld, common.h   (shared by SEU W1-W5 and HDC W6/W7)
  model/          Python RV32I golden ISS
  fi/  stats/  synth/  viz/  web_export/
  tests/          check_golden.py (was tb/check_workloads.py), sw/hello.c, cocotb tests
  requirements.lock
studies/seu/  {sw/, sw/ref/, rtl/variants/, targets/, experiments/, analysis/, results/, paper/, docs/}
studies/hdc/  (skeleton already on main since 2 Nov)
docs/         environment.md, platform.md, learning/ ★ (training walkthroughs stay repo-level)
```
★ `platform/sw/runtime/`: not in the brief, but both studies' C workloads need the same
startup code, linker script and output/done protocol. One copy avoids drift.

## 3. Exact moves (`git mv`, keeps history)

```bash
git tag pre-restructure
git switch -c restructure                      # work on a branch; main untouched until tests pass

mkdir -p platform/rtl/picorv32 platform/rtl/soc platform/sw/runtime platform/tests/sw \
         studies/seu/sw/ref studies/seu/rtl studies/seu/docs

# platform: RTL
git mv rtl/picorv32.v            platform/rtl/picorv32/picorv32.v
git mv docs/picorv32_commit.txt  platform/rtl/picorv32/UPSTREAM_COMMIT
cp ~/picorv32/COPYING platform/rtl/picorv32/COPYING && git add platform/rtl/picorv32/COPYING
git mv rtl/soc.v                 platform/rtl/soc/soc.v
git mv tb/tb_soc.v               platform/rtl/soc/tb_soc.v
# platform: runtime + tests
git mv sw/crt0.S                 platform/sw/runtime/crt0.S
git mv sw/link.ld                platform/sw/runtime/link.ld
git mv sw/common.h               platform/sw/runtime/common.h
git mv sw/hello.c                platform/tests/sw/hello.c
git mv tb/check_workloads.py     platform/tests/check_golden.py
# platform: empty placeholders (and whatever G1 week adds to them)
git mv model                     platform/model          # ISS written this week lands here
git mv fi                        platform/fi
git mv synth                     platform/synth
git mv viz                       platform/viz
# SEU study
git mv sw/w*.c                   studies/seu/sw/         # w1_matmul.c ... w5 (all present after G1)
git mv sw/ref/workloads.py       studies/seu/sw/ref/workloads.py
git mv rtl/variants              studies/seu/rtl/variants
git mv analysis                  studies/seu/analysis
git mv results                   studies/seu/results     # golden_runs.json
git mv paper                     studies/seu/paper
git mv docs/decisions.md         studies/seu/docs/decisions.md
git mv docs/log.md               studies/seu/docs/log.md
git mv tb/cocotb                 platform/tests/cocotb   # lockstep test (RTL vs ISS)
git mv sw/isa_test.c             platform/tests/sw/isa_test.c
# model/rv32i_iss.py moves with `git mv model platform/model` above
```
Files created during G1 week that are not listed above are placed by the same rule:
core-agnostic → `platform/`, SEU-specific → `studies/seu/`. Re-check with
`git status` and `git ls-files rtl sw tb` (must be empty) before committing.

## 4. Path updates

| file | change |
|---|---|
| `Makefile` | `RTL := platform/rtl/picorv32/picorv32.v platform/rtl/soc/soc.v`; `TB := platform/rtl/soc/tb_soc.v`; new `STUDY ?= seu`; ELF rule finds `studies/$(STUDY)/sw/$(PROG).c` or `platform/tests/sw/$(PROG).c`; `-Iplatform/sw/runtime`; `-T platform/sw/runtime/link.ld`; build dir `build/$(STUDY)/`; targets `golden STUDY=…` (replaces `check`), `smoke`, `campaign`, `figures`, `synth` (stubs until they exist) |
| `check_golden.py` | `--study` argument; imports `studies/<study>/sw/ref/workloads.py`; writes `studies/<study>/results/golden_runs.json` |
| `.gitignore` | `build/`; keep `obj_dir/`; `studies/*/results/raw/` already present |
| `CLAUDE.md`, `README.md`, `docs/learning/*.md` | update paths and commands |
| `docs/environment.md` | point to `platform/rtl/picorv32/UPSTREAM_COMMIT` |
| `platform/requirements.lock` | `~/.venv/bin/pip freeze` (current shared venv, unchanged versions) |

## 5. Tests to re-run (all must match pre-move results exactly)

1. `make sim PROG=hello` → `OUT 00c0ffee`, `DONE cycles=191`.
2. `make golden STUDY=seu` → W1–W5 PASS, cycle counts **identical** to the pre-move
   `results/golden_runs.json` (`diff` the two files: no differences).
3. Icarus cross-check of W1 → same OUT and cycles.
4. `make lockstep` (cocotb RTL-vs-ISS) on W1–W5 + isa_test → PASS.
5. `git ls-files rtl sw tb model fi synth viz analysis results paper` → empty.
6. Fresh clone into the scratchpad + `make golden STUDY=seu` → PASS (no stray absolute paths).

## 6. Commit, rollback, follow-ups

- All tests pass → `git switch main && git merge --ff-only restructure`, commit message
  `[platform] Restructure into platform + studies`, push, append STATUS.md, tell Session HDC
  to rebase `hdc` (its files are only under `studies/hdc/`, so no conflicts expected).
- Any test fails and isn't fixed within the day → stay on the old layout: `git switch main`
  (main was never touched; the `pre-restructure` tag marks it). Delete or keep the branch
  for later. No history rewrite on main is ever needed, because main only moves by fast-forward.
- Brief's stop rule: if by **Wed 11 Nov** golden checks still fail after the move, abandon
  it, keep the old layout, keep HDC code only under `studies/hdc/`, and report to Boniface.

## 7. Platform description (filled in after migration / injector work)

- Target descriptor (YAML/JSON): top module, clock/reset, done/trap/output signals,
  timeout factor, unit groups → signal paths + bit ranges (generated from Yosys FF list). TBD.
- Outcome classifier hook: base classes masked / SDC / crash-trap / hang / detected;
  studies register extra sub-outcomes (HDC: class-SDC). TBD.
- Results schema: run_id (study-prefixed), study, variant, workload, unit, signal, bit,
  cycle, outcome, sub_outcome, cycles_run, detected, seed, tool versions. TBD.
- Trace/diff export: per-cycle FF dump of golden + faulty over a window → JSON diff
  (schema in platform/web_export/SCHEMA.md). TBD (after G2).
