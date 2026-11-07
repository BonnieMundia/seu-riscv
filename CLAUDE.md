# CLAUDE.md — shared platform + two studies (SEU, HDC)

Fully open-source SIMULATION study (no FPGA/hardware) of soft errors in RISC-V.
- **Track SEU** (priority): "Workload-aware selective hardening of an open-source RISC-V
  core against single-event upsets". Owned by Session SEU.
- **Track HDC**: "Where is hyperdimensional computing actually vulnerable?" Owned by
  Session HDC. Its plan: studies/hdc/docs/PLAN.md.

## Roles (check `pwd` + `git rev-parse --abbrev-ref HEAD` at session start)
- `~/Documents/GitHub/seu-riscv` on `main` → **Session SEU**. Only SEU commits to main.
- `~/Documents/GitHub/seu-riscv-hdc` on `hdc` → **Session HDC**: commits only under
  studies/hdc/ (+ its own viz library target); rebases hdc onto main each session.
- Anything else → stop and ask Boniface.
- Ownership: platform/, Makefile, CI, docs/ (repo-level), CLAUDE.md, viz App target,
  studies/seu/ → SEU. studies/hdc/ → HDC. Platform changes requested by HDC go to
  `../seu-riscv-coord/REQUESTS.md` (what, why, smallest compatible change, test).
- Coordination folder `~/Documents/GitHub/seu-riscv-coord/` (outside git): STATUS.md
  (append a dated block every session), REQUESTS.md, cpu_budget.json (10 cores: SEU 8 /
  HDC 2), locks/ (campaign + synth.lock). At session start read STATUS + REQUESTS, then
  report role, current gate/phase, open requests, next three tasks.
- Commit prefixes: [platform], [seu], [hdc]. Never commit results > 50 MB.

## Who / how to work
- Boniface (github.com/BonnieMundia), EEE/Telecom graduate, Kenya; CCNA, JNCIA. Strong in
  Python + networking; new to Verilog/hardware. Boniface reviews every gate.
- Explain hardware in plain, simple language. Small steps; run commands yourself, read
  errors, fix, report briefly. Report failures, contradicted hypotheses, slips plainly.
- NEVER edit platform/rtl/picorv32/picorv32.v (pinned upstream, ISC licence in COPYING).
- Ask before: deleting files, force-push, history rewrite on main, creating anything on
  GitHub, installing anything (brew/pip/nix/npm), downloads > 1 GB, campaigns > 1,000
  runs, any LibreLane run, editing a file another session owns.
- Golden first: no injection until a program/variant passes its golden/lockstep check.
- Never invent numbers. Figures only from code; every rate with a 95% Wilson interval.
- Log every design choice in studies/<study>/docs/decisions.md (dated, one line); session
  notes in studies/<study>/docs/log.md; hypotheses.md written before campaigns.

## Act as trainer / supervisor (Boniface must be able to run and defend everything)
For EVERY code addition: (1) explain what it does, why, and what breaks without it, in
plain words; (2) give 2–4 "do it yourself" tasks (predict → run → compare) with expected
results; (3) cite sources you have checked exist, primary first (spec, PicoRV32
README/source, tool manuals) with section names; (4) write it in docs/learning/<phase>.md
and link it in the turn summary; (5) where it is a good learning step, let Boniface write the
code first and review it; (6) experiments on `play/*` branches or undone with `git restore`.

## Machine / tools
- MacBook Air M5 (fanless: long campaigns throttle), macOS, zsh, Homebrew. No `nproc`:
  `sysctl -n hw.ncpu`. GitHub: github.com/BonnieMundia/seu-riscv. Push over HTTPS with
  `git -c credential.helper='!/opt/homebrew/bin/gh auth git-credential' push` (SSH key has
  a passphrase).
- Verilator 5.052, Icarus 13, Yosys 0.69, RISC-V GCC 16.1 (`riscv64-unknown-elf-`,
  `-march=rv32i -mabi=ilp32`), cocotb 2.1. Versions: docs/environment.md.
- Python venv `~/.venv` (to be pinned in platform/requirements.lock). Upstream clones:
  `~/picorv32`, `~/faultergeist`. LibreLane NOT installed yet (needed by Gate 3).

## Repo layout (since 2 Nov 2026; plan + rationale in docs/platform.md)
- platform/rtl/picorv32/ (upstream, COPYING, UPSTREAM_COMMIT) · platform/rtl/soc/ (soc.v,
  tb_soc.v) · platform/sw/runtime/ (crt0.S, link.ld, common.h) · platform/model/
  (rv32i_iss.py golden ISS) · platform/tests/ (check_golden.py, programs.py,
  cocotb/test_lockstep.py, sw/ hello + isa_test + tests_ref.py) · platform/{fi, stats,
  synth, viz, web_export}/ (to come).
- studies/seu/{sw/ (w1–w5 + ref/workloads.py), rtl/variants/, targets/, experiments/,
  analysis/, results/ (golden_runs.json), paper/, docs/ (decisions.md, log.md)}.
- studies/hdc/ (Session HDC). docs/ = environment.md, platform.md, learning/ (walkthroughs).
- Build outputs: build/<study>/ (ELF, hex, .dis), obj_dir/ — git-ignored.

## Common commands (STUDY=seu by default)
- `make sw PROG=x` / `make sim PROG=x` — build / run x.c (study sw/ or platform tests).
- `make golden` (alias `check`) — run the study's workloads vs Python reference + 10k–200k
  cycle budget; writes studies/$(STUDY)/results/golden_runs.json.
- `make lockstep [W=x]` — cocotb: RTL must match the golden ISS per instruction (PCs via
  launch_next_insn, register writes, stores) for workloads + platform tests.
- `make gate1` = golden + lockstep. `make wave PROG=x` — VCD. `make clean`.
- Add a workload: studies/<study>/sw/x.c + function in studies/<study>/sw/ref/workloads.py.

## SEU study
- RQ1: per-bit failure rate per unit (regfile, PC, control state, decoder, ALU/operand
  regs, memory interface, counters), by workload. RQ2: selective protection vs full TMR,
  cost in area/power/fmax (SKY130). RQ3 (opt.): 1,068-run vs 20,000-run campaigns.
- Workloads (frozen at G1; cycles): W1 matmul 147,409 · W2 qsort 33,800 · W3 CRC-32
  119,032 · W4 attitude filter 192,392 · W5 ADS-B CRC-24 150,997.
- Variants (studies/seu/rtl/variants/): H0 none · H1 regfile parity · H2 regfile SEC-DED
  (39,32) · H3 TMR on PC + control state · H4 = H2 + H3 · H5 full TMR. Use `(* keep *)`,
  check Yosys cell counts grow; inject into parity/ECC bits and voters too.
- Experiments: E1 5 workloads × 7 units × 1,068 · E2 H1–H5 on W1, W4 × 2,401 · E3 PC unit
  on W2 × 20,000 · E4 (opt.) Faultergeist random vs physics-timed.
- Outcomes vs golden run: masked · SDC · crash/trap · hang (> 2× golden cycles) · detected.
- Assumptions: RAM ECC-protected, never injected; single bit flips only (no SET/MBU).
- Memory map: RAM 0x0000_0000–0x0000_FFFF (stack top 0x1_0000) · output 0x1000_0000 ·
  done 0x1000_0004. PicoRV32 config: studies/seu/docs/decisions.md (authoritative).
- Sample sizes (Leveugle, p = 0.5, 95%): 1,068 = ±3%; 2,401 = ±2%; 9,604 = ±1%.

## Platform design rules (docs/platform.md)
Core-agnostic injector driven by a per-study target descriptor (signals, unit groups from
the Yosys FF list) · pluggable outcome classifier (HDC adds class-SDC) · one results
schema (run_id study-prefixed, …, seed, tool versions) · trace/diff export (per-cycle FF
dump golden vs faulty → JSON) · viz/ is a Swift package, one library target per study.

## Schedule
- G1 Fri 6 Nov: RTL matches golden on W1–W5 — **met 2 Nov, signed off by Boniface**.
- Platform migration: done 2 Nov (brought forward from 9 Nov).
- G2 Fri 27 Nov: injector in platform/fi works; E1 done. E1 run 6 Nov (37,380 runs, hypotheses checked);
  **signed off by Boniface 7 Nov**.
- G3 Fri 18 Dec: H1–H5, E2, E3, LibreLane numbers. G4 Fri 1 Jan 2027: figures, paper
  draft, README, demo (4–8 Jan buffer). HDC timeline: studies/hdc/docs/PLAN.md.
- If Boniface reports < ~12 h/week: drop E4 and H5 full synthesis first, then HDC RQ4.

SEU guide: https://docs.google.com/document/d/1t9a1Frq3CjUYv-uu5GcToXZN4ZKm7fQ0y-AldAXlERQ/edit
