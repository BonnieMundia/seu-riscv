# CLAUDE.md — seu-riscv

Workload-aware selective hardening of an open-source RISC-V core against single-event
upsets: a fully open-source simulation study. SIMULATION ONLY (no FPGA/hardware).

## Who / how to work
- Boniface (github.com/BonnieMundia), entry-level backend engineer, Kenya. BSc Telecom +
  EEE, CCNA, JNCIA. Strong in Python + networking; NEW to Verilog/hardware.
- Explain hardware steps in plain, simple language. No fancy wording.
- Work in small steps; run commands yourself, read errors, fix, report briefly.
- NEVER edit rtl/picorv32.v (upstream copy). Our changes go in our own files.
- Ask before anything destructive (deleting files, force-push, rewriting history) and
  before creating anything on GitHub.
- Commit after each working milestone with a clear message.
- Never invent numbers/results. Check source (README, --help, docs) or ask.
- Log every design choice in docs/decisions.md (dated, one line); weekly notes in docs/log.md.

## Machine / tools
- MacBook Air M5 (Apple Silicon), macOS, zsh, Homebrew. No `nproc`: use `sysctl -n hw.ncpu`.
- Verilator, Icarus, Yosys, RISC-V GCC (prefix `riscv64-unknown-elf-`, compile with
  `-march=rv32i -mabi=ilp32`). Versions in docs/environment.md.
- Python venv: `~/.venv` (cocotb, numpy, pandas, scipy, matplotlib, pyelftools, jupyter).
- Upstream clones: `~/picorv32` (commit in docs/picorv32_commit.txt), `~/faultergeist`.
- LibreLane (via Nix) for SKY130 synthesis — install location still to confirm.

## Research questions
- RQ1: Which units (register file, PC, control state, decoder, ALU/operand regs, memory
  interface, counters) have the highest failure rate per bit; how does it vary by workload?
- RQ2: How much do selective protections reduce failures vs full TMR, and at what cost in
  area, power, Fmax on SkyWater 130 nm?
- RQ3 (optional): How close are small campaigns (1,068 runs) to a large one (20,000)?

## Workloads (sw/; C, 10k–200k cycles, each ends by writing a checksum to the output port)
- W1 8x8 integer matrix multiply (compute) · W2 quicksort of 64 ints (branches)
- W3 CRC-32 over 1 KB (memory + bit ops) · W4 fixed-point attitude filter, 200 steps
- W5 Mode S / ADS-B CRC-24 check on sample frames
- RV32I has no MUL: software multiply comes from libgcc (rv32i/ilp32 multilib exists).

## Hardened variants (rtl/variants/, later)
- H0 baseline · H1 parity per regfile word (trap on mismatch) · H2 Hamming SEC-DED (39,32)
  on regfile · H3 TMR on PC + control state · H4 = H2 + H3 · H5 full TMR (3 cores + voter)
- Yosys merges identical copies: use `(* keep *)` and check cell counts grow.
- Inject into parity/ECC bits and voters too.

## Fault outcomes (vs fault-free golden run)
Masked (right answer) · SDC (wrong answer, no trap) · Crash/trap · Hang (> 2x golden
cycles) · Detected/corrected (protection flag fired).

## Key assumptions (keep consistent)
- RAM is assumed ECC-protected and is NOT injected. Targets = core flip-flops + register file.
- Single bit flips only (no SET, no MBU) in the main study.

## Memory map (SoC, rtl/soc.v)
- 0x0000_0000–0x0000_FFFF : 64 KB RAM (program + stack), stack top 0x0001_0000
- 0x1000_0000 : output port (each write logged as a result)
- 0x1000_0004 : done port (any write ends the run)
- PicoRV32 config: see docs/decisions.md (authoritative).

## Architecture (built over the coming weeks)
1. C workloads -> ELF (RISC-V GCC) -> hex (sw/elf2hex.py).
2. Python RV32I golden model (model/, ~300 lines, pyelftools): outputs + instruction trace.
3. cocotb (tb/): RTL must match golden model exactly on all workloads before any FI.
4. Route A (main) FI: Verilator C++ harness, `--vpi --public-flat-rw`; args +sig +bit
   +cycle +elf; clock to cycle t, flip bit via VPI (regfile: vpi_handle_by_index), run to
   done/trap/timeout, print one JSON line. fi/run_campaign.py runs thousands in parallel
   (multiprocessing) -> CSV: run_id, variant, workload, unit, signal, bit, cycle, outcome,
   cycles_run, detected.
5. Route B (cross-check): Antmicro Faultergeist (VPI plugin; random, Weibull, Bendel).
6. Synthesis (synth/): Yosys `stat` (quick) + LibreLane on SKY130: area, power, timing.
7. Analysis (analysis/): failure rates with 95% Wilson intervals, chi-square tests ->
   results/summary.json for a SwiftUI visualizer (viz/).

Sample sizes (Leveugle, p=0.5, 95%): 1,068 = ±3%; 2,401 = ±2%; 9,604 = ±1%.

## Repo layout
rtl/ (picorv32.v upstream, soc.v, variants/) · sw/ · model/ · tb/ · fi/ · synth/ ·
results/ · analysis/ · viz/ · docs/ · paper/

## Common commands
- `make sw` — build sw/hello.elf + hex · `make sim` — Verilator build + run
- `make clean` — remove build outputs

## Schedule (main project Mon 12 Oct 2026 – Fri 1 Jan 2027)
- Week 1 (12–16 Oct): hello-world SoC running, repo pushed, papers 1–5 read.
- Gate 1, Fri 6 Nov: RTL matches golden model on W1–W5; scope frozen.
- Gate 2, Fri 27 Nov: baseline campaign E1 complete.
- Gate 3, Fri 18 Dec: variant campaigns E2/E3 + synthesis numbers.
- Gate 4, Fri 1 Jan: paper draft, README, demo video.
- Side project (4–22 Jan 2027): HDC bearing-fault classifier (CWRU), Verilog inference
  core, bit-flip robustness test.

Full guide: https://docs.google.com/document/d/1t9a1Frq3CjUYv-uu5GcToXZN4ZKm7fQ0y-AldAXlERQ/edit
