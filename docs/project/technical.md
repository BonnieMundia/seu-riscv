# seu-riscv: Technical documentation

**Workload-aware selective hardening of an open-source RISC-V core against single-event upsets: a fully open-source simulation study.**

| | |
|---|---|
| Doc version | v1 (2 Nov 2026) |
| Repo state described | `main` at commit `dbbaa48` ("[seu] Log Gate 1 sign-off and platform migration"), 2 Nov 2026 |
| Project stage | Gate 1 met and signed off (2 Nov 2026, due Fri 6 Nov). Gate 2 work (fault injector, E1) not started. |
| Rule | Every number below is copied from a repo file; the source file is named next to it. Anything not yet built is marked **PLANNED**. |

---

## 1. Purpose and research questions

A single-event upset (SEU) is one stored bit flipped by a particle strike. Nothing is damaged, but the stored value is wrong until overwritten. The study asks which parts of a small RISC-V CPU actually matter when that happens, and what the cheapest protection is. Everything is simulation; no FPGA or radiation testing. (Source: `README.md`, `CLAUDE.md`.)

- **RQ1, where it breaks.** Per-bit failure rate per unit (register file, PC, control state, decoder, ALU/operand registers, memory interface, counters), by workload.
- **RQ2, what fixes it cheaply.** Selective protection (parity, SEC-DED, partial TMR) against full TMR, with cost in area, power and fmax on SkyWater 130 nm.
- **RQ3 (optional), how many runs are enough.** A 1,068-run campaign against a 20,000-run campaign on one unit.

**Fault model and assumptions** (`studies/seu/docs/decisions.md`, 2026-10-08):
- Single bit flips only in core flip-flops and the register file. No SETs, no multi-bit upsets.
- RAM is assumed ECC-protected and is never a fault target.

---

## 2. Architecture

### 2.1 Hardware under test

**Core:** PicoRV32, upstream commit `ef203c2b0a3fb793280f5114941416c425c5b461` (`platform/rtl/picorv32/UPSTREAM_COMMIT`), copied unchanged under its ISC licence. It is never edited; all project logic lives in separate files.

**Core configuration** (set explicitly in `platform/rtl/soc/soc.v`; authoritative list in `decisions.md`, 2026-10-08):

| Parameter group | Setting | Why |
|---|---|---|
| ISA | `ENABLE_MUL=0`, `ENABLE_FAST_MUL=0`, `ENABLE_DIV=0`, `COMPRESSED_ISA=0` | Plain RV32I |
| Disabled features | `ENABLE_IRQ=0`, `ENABLE_PCPI=0`, `ENABLE_TRACE=0` | Not needed; inputs tied to 0 so Verilator, Icarus and Yosys see the same hardware |
| Counters | `ENABLE_COUNTERS=1`, `ENABLE_COUNTERS64=1` | "Counters" is an RQ1 unit |
| Traps | `CATCH_MISALIGN=1`, `CATCH_ILLINSN=1` | So faults can appear as crash/trap |
| Register file | `ENABLE_REGS_16_31=1`, `ENABLE_REGS_DUALPORT=1`, `REGS_INIT_ZERO=0` | Full 32 registers; no reset of the regfile (realistic hardware) |
| Datapath | `TWO_STAGE_SHIFT=1`, `BARREL_SHIFTER=0`, `TWO_CYCLE_COMPARE=0`, `TWO_CYCLE_ALU=0`, `LATCHED_MEM_RDATA=0` | Small core |
| Reset | `PROGADDR_RESET=0x0`, `STACKADDR=0x0001_0000` | Matches memory map |

**SoC** (`platform/rtl/soc/soc.v`, 122 lines): PicoRV32 + 64 KB RAM + two ports.

| Address | Function |
|---|---|
| `0x0000_0000`–`0x0000_FFFF` | 64 KB RAM (program + stack; stack top `0x1_0000`) |
| `0x1000_0000` | Output port: every write is logged as a result (`OUT <hex>`) |
| `0x1000_0004` | Done port: any write ends the run |
| anything else | Reads return 0; sticky `bad_addr` flag goes high |

Memory interface: native PicoRV32 valid/ready. Every request is answered one cycle after `mem_valid` (registered `mem_ready` and `mem_rdata`), with no further wait states.

**Testbench** (`platform/rtl/soc/tb_soc.v`): holds reset for 5 cycles, counts clock edges from reset release, and prints `OUT`, `DONE|TRAP|HANG cycles=<n>` and a one-time `WARN bad_addr`. Plusargs: `+hex=`, `+max_cycles=` (default 1,000,000), `+vcd`. This cycle definition is the one used for golden cycle counts and for the hang rule.

### 2.2 Software runtime (`platform/sw/runtime/`)

- `crt0.S`: zeroes x1 and x3–x31, sets `sp = 0x10000`, clears `.bss`, calls `main`, writes `main`'s return value to the done port. Needed because PicoRV32 does not reset its register file.
- `link.ld`: places the program at address 0 in the 64 KB RAM.
- `common.h`: `report()` (volatile write to the output port), `xorshift32()` (seeded pseudo-random generator using only shifts and XORs, so no multiply needed), `mix()` (checksum step: rotate left 5, XOR; order-sensitive).
- Toolchain: `riscv64-unknown-elf-gcc -march=rv32i -mabi=ilp32 -O2 -nostdlib -ffreestanding`, linked with `-lgcc` for software multiply/divide.
- Program image: `objcopy -O verilog --verilog-data-width=4` (word addresses, one little-endian 32-bit word per entry), loaded with `$readmemh`. Verified on binutils 2.46.

### 2.3 Golden model (`platform/model/rv32i_iss.py`, 243 lines)

A Python RV32I instruction-set simulator of the SoC. It loads the ELF's `PT_LOAD` segments with pyelftools, copies PicoRV32's reset state (`pc = 0`, `x2 = 0x10000`), the memory map, ports and traps (ECALL/EBREAK, illegal instruction, misaligned access or jump target). FENCE and counter CSRs are deliberately not modelled and raise `NotImplementedError`.

### 2.4 Repository layout (since 2 Nov 2026, `docs/platform.md`)

```
platform/        shared, core-agnostic
  rtl/picorv32/  upstream core (untouched) + COPYING + UPSTREAM_COMMIT
  rtl/soc/       soc.v, tb_soc.v
  sw/runtime/    crt0.S, link.ld, common.h
  model/         rv32i_iss.py (golden ISS)
  tests/         check_golden.py, programs.py, list_programs.py,
                 cocotb/test_lockstep.py, sw/ (hello.c, isa_test.c, tests_ref.py)
  fi/ stats/ synth/ viz/ web_export/   PLANNED (empty)
  requirements.lock   119 pinned Python packages
studies/seu/     this study
  sw/            w1–w5 C workloads + ref/workloads.py (Python references)
  results/       golden_runs.json
  docs/          decisions.md, log.md
  rtl/variants/ targets/ experiments/ analysis/ paper/   PLANNED (empty)
studies/hdc/     second study (HDC), skeleton only, separate branch
docs/            environment.md, platform.md, learning/phase1–3.md
```

Status per platform folder (`platform/README.md`): `rtl/picorv32`, `rtl/soc`, `sw/runtime`, `model`, `tests`, `requirements.lock` **done**; `fi` (G2), `stats`, `synth`, `viz`, `web_export` **to do**.

---

## 3. Workloads (frozen at Gate 1)

Each workload builds inputs from a fixed seed, does the work, reduces the result to a checksum with `mix()`, writes it to the output port and returns. Each has an independent Python reference in `studies/seu/sw/ref/workloads.py`. A 10k–200k cycle budget per workload is enforced by `make check`.

| ID | Workload | What it does | Outputs (golden) | Cycles |
|---|---|---|---|---|
| W1 | `w1_matmul` | 8×8 matrix multiply (512 software multiplies via libgcc `__mulsi3`), inputs 0..255 | `36c7bde8` | 147,409 |
| W2 | `w2_qsort` | Recursive quicksort (Lomuto, last-element pivot) of 64 signed int32, seed `0x51ED5EED`; reference = Python `sorted()` | `9c86f267` | 33,800 |
| W3 | `w3_crc32` | CRC-32/ISO-HDLC (zlib) with a 16-entry nibble table; CRC of "123456789", then CRC of 1 KB from seed `0x0BADF00D` | `cbf43926`, `0a6e4633` | 119,032 |
| W4 | `w4_attitude` | 3-axis complementary filter + PD attitude hold, Q16.16, dt = 1/64 s, 200 steps, no multiplies | `8ec3e146` | 192,392 |
| W5 | `w5_adsb_crc24` | Mode S / ADS-B DF17 CRC-24 (generator `0x1FFF409`) syndrome check on 32 frames (4 real, 14 synthetic, 14 one-bit-corrupted) | `00000012` (18 valid), `32f0a6da` | 150,997 |

Sources: outputs and cycles from `studies/seu/results/golden_runs.json`; descriptions from `decisions.md` and `docs/learning/phase2.md`. `cbf43926` is the standard CRC-32 check value; W3 also matches zlib.

### Design decisions that shaped the workloads (`decisions.md`)
- **W1 inputs unsigned.** `__mulsi3` loops up to the highest 1-bit of one operand, so negative operands always cost 32 passes. Signed inputs gave 344,337 cycles (over budget); unsigned gives 147,409.
- **W3 implementation.** Measured: bitwise 483,740 cycles; 256-entry table 203,291 (table build alone 118,483); 16-entry nibble table 119,032. Nibble table chosen.
- **W4 budget.** Earlier correct versions took 242,986, 207,768 and 199,992 cycles; rejected for budget or too little margin. Final 192,392. Filter quality (Python trace): roll/pitch RMS error 0.005 / 0.008 rad; yaw drifts (no reference sensor).
- **W5 frames.** 4 real frames from "The 1090 MHz Riddle" (verified remainder 0). Reference uses big-integer long division, a different method from the C shift register.
- **Authorship change.** W3 and W5 were written by Claude and reviewed by Boniface (originally Boniface was to write them), to protect the Gate 1 date.

---

## 4. Verification method (Gate 1)

Two independent checks must both pass before any fault is injected ("golden first", `CLAUDE.md`).

### 4.1 Golden output check (`make golden`, alias `make check`)
`platform/tests/check_golden.py` builds each workload, runs it on the Verilator SoC, compares every `OUT` value with the Python reference, checks the cycle count against the 10k–200k budget, and writes `studies/seu/results/golden_runs.json`. It was tested once with a deliberately wrong reference value and correctly reported FAIL with exit code 1 (`phase2.md` §5).

### 4.2 Lockstep check (`make lockstep`)
`platform/tests/cocotb/test_lockstep.py` runs the ISS first, then the RTL under cocotb, sampling on the falling clock edge. Three streams must be identical:

| Stream | ISS | RTL |
|---|---|---|
| Executed PCs | `pc` at each `step()` | `cpu.next_pc` when `cpu.launch_next_insn` is high |
| Register writes | each write to x1..x31 | `latched_rd`, `cpuregs_wrdata` when `cpuregs_write` is high and `latched_rd != 0` |
| Stores | each SB/SH/SW | bus: `mem_valid & mem_ready & mem_wstrb != 0` |

It also checks outputs against the reference, DONE status, and cycle count against `golden_runs.json`. Internal signals are probed instead of RVFI so that the verified RTL is byte-identical to the RTL that will be injected.

### 4.3 Problems found on the way (`phase3.md` §3)
1. **Bus fetches are not executed instructions.** PicoRV32 prefetches and discards after taken branches (W2: 6,610 fetches for 5,913 executed instructions). Fixed by using `launch_next_insn`.
2. **Hidden first write.** After reset the RTL writes `x2 = 0x10000` through the normal write port. The ISS now logs it as write #0.
3. **Off-by-one cycle count.** `tb_soc.v` prints before its non-blocking increment; the test uses the same convention (`cycles - 1`).

None was fixed by loosening the test.

### 4.4 Does the test catch bugs?
A planted bug (SRAI made logical in the ISS) made lockstep FAIL on W4 at instruction 173 (`phase3.md` §4; `decisions.md`).

### 4.5 Instruction coverage
W1–W5 execute 27 of the 37 RV32I instructions. `platform/tests/sw/isa_test.c` covers the other 10 (AUIPC, BLTU, LB, LH, SLTI, ORI, SLL, SLT, SLTU, SRA) with 16 hand-computed values. Hand values = ISS = RTL, so all 37 instructions are verified.

---

## 5. Results so far

### 5.1 Baseline bring-up (Phase 1, `studies/seu/docs/log.md`)
Hello-world prints `OUT 00c0ffee`, `DONE cycles=191` on Verilator 5.052 and Icarus 13.0 (identical). It executes 44 instructions. The PicoRV32 README CPI table predicts 141 cycles; the extra comes from 48 memory transfers with one wait cycle each, plus about 2 start-up cycles (141 + 48 + ~2 ≈ 191). Hang path (`+max_cycles=100`) and trap path (EBREAK, `TRAP cycles=7`) were both checked.

### 5.2 Gate 1 results (`docs/learning/phase3.md` §6)

| Workload | Cycles | Instructions | Register writes | Stores | Golden check | Lockstep |
|---|---|---|---|---|---|---|
| W1 matmul | 147,409 | 28,903 | 19,417 | 397 | PASS | PASS |
| W2 qsort | 33,800 | 5,913 | 3,856 | 836 | PASS | PASS |
| W3 crc32 | 119,032 | 22,073 | 18,841 | 1,316 | PASS | PASS |
| W4 attitude | 192,392 | 36,077 | 29,656 | 2,820 | PASS | PASS |
| W5 adsb_crc24 | 150,997 | 29,760 | 19,958 | 549 | PASS | PASS |
| isa_test | — | 96 | — | — | — | PASS |

Register writes include the reset write of x2. Verilator and Icarus agree on W1–W5 cycles (`decisions.md`).

**Gate 1 status:** criterion met Mon 2 Nov 2026, 4 days before the Fri 6 Nov deadline. Signed off by Boniface the same day after reproducing `make clean && make gate1` on their own machine (all PASS). Scope frozen: W1–W5 and their cycle counts are the E1 baseline; changing them now needs a dated decision.

### 5.3 Platform migration (2 Nov 2026)
Repo restructured into `platform/` + `studies/{seu,hdc}` (commit `01238ed`; tag `pre-restructure` marks the old layout). Brought forward from Mon 9 Nov. All six migration tests passed: `golden_runs.json` byte-identical before and after, and a fresh clone passes (`docs/platform.md`, `decisions.md`).

---

## 6. Reproducibility

### 6.1 Tool versions (`docs/environment.md`, recorded 2026-10-08)

| Tool | Version |
|---|---|
| Verilator | 5.052 |
| Icarus Verilog | 13.0 |
| Yosys | 0.69+post |
| RISC-V GCC | riscv64-unknown-elf-gcc 16.1.0 |
| GNU binutils (objcopy) | 2.46 |
| cocotb | 2.1.0 |
| Python | 3.9.6 (venv `~/.venv`); packages pinned in `platform/requirements.lock` |
| Host | macOS 27.0.1, Apple M5, 10 cores |
| PicoRV32 | `ef203c2` |

Known environment issues: LibreLane is **not installed** (Homebrew Python refuses global pip install, PEP 668); it is needed by Gate 3. No waveform viewer installed. Always use `~/.venv/bin/python -m pip`, never `~/.venv/bin/pip` (points at a different Python).

### 6.2 Commands

```sh
make clean && make gate1        # full Gate 1 check from scratch (golden + lockstep)
make golden                     # W1-W5 vs Python references + cycle budget; writes golden_runs.json
make lockstep                   # RTL vs ISS, all workloads + platform tests
make lockstep W=w2_qsort        # one workload
make sim PROG=hello             # one program; expect OUT 00c0ffee, DONE cycles=191
make wave PROG=w2_qsort         # same, with a VCD dump
make golden STUDY=seu           # explicit study selection
```

`make smoke`, `make campaign`, `make figures`, `make synth` exist as stubs and currently exit with "not implemented yet".

### 6.3 Adding a workload
Add `studies/<study>/sw/x.c` and one function in `studies/<study>/sw/ref/workloads.py`. Any change to W1–W5 after Gate 1 needs a dated entry in `decisions.md`.

---

## 7. Planned work (not started; nothing below has results)

### 7.1 Fault injection platform (Gate 2, Fri 27 Nov) — PLANNED
- Injector in `platform/fi/` (Verilator + VPI), driven by a per-study **target descriptor**: top module, clock/reset, done/trap/output signals, timeout factor, and unit groups mapped to signal paths and bit ranges generated from the Yosys flip-flop list.
- Pluggable outcome classifier with base classes **masked, SDC, crash/trap, hang (> 2× golden cycles), detected**.
- One results schema: run_id, study, variant, workload, unit, signal, bit, cycle, outcome, sub_outcome, cycles_run, detected, seed, tool versions.
- Trace/diff export (per-cycle flip-flop dump, golden vs faulty, to JSON) after G2.
- Guide milestones: injector flips a chosen bit and a 50-run smoke campaign with time per run measured (week of 9–13 Nov); half of E1 and a first heat map (16–20 Nov); E1 complete and a Faultergeist cross-check on one workload (23–27 Nov).

### 7.2 Hardened variants (Gate 3, Fri 18 Dec) — PLANNED

| Variant | Protection |
|---|---|
| H0 | None (baseline) |
| H1 | Register-file parity |
| H2 | Register-file SEC-DED (39,32) |
| H3 | TMR on PC + control state |
| H4 | H2 + H3 |
| H5 | Full TMR |

Variants will use `(* keep *)` with a check that Yosys cell counts grow, and parity/ECC bits and voters will be injected too. Area, power and fmax from LibreLane on SKY130 (LibreLane not installed yet).

### 7.3 Experiments — PLANNED

| ID | Design | Runs |
|---|---|---|
| E1 | 5 workloads × 7 units × 1,068 (baseline vulnerability map, RQ1) | 37,380 |
| E2 | H1–H5 on W1 and W4 × 2,401 (RQ2) | — |
| E3 | PC unit on W2 × 20,000 (RQ3) | 20,000 |
| E4 (optional) | Faultergeist random vs physics-timed | — |

(E1 run total = 5 × 7 × 1,068, computed from `CLAUDE.md`.)

**Sample sizes** (Leveugle et al., p = 0.5, 95% confidence): n = z²·p(1−p)/e², so 1,068 → ±3%, 2,401 → ±2%, 9,604 → ±1%. Every reported rate will carry a 95% Wilson interval.

### 7.4 Deliverables (Gate 4, Fri 1 Jan 2027) — PLANNED
Figures generated from code, SwiftUI visualizer (heat map, trade-off and replay screens), 6–8 page IEEE-style paper, README, demo video. Side project (HDC bearing-fault classifier) runs 4–22 Jan 2027.

### 7.5 Fallback rule (`CLAUDE.md`)
If available time falls below about 12 h/week: drop E4 and H5 full synthesis first, then HDC RQ4.

---

## 8. Not recorded in the repo
These appear in the project guide but have no file in the repo yet, so this document makes no claim about them: literature review / paper summaries, Zotero library, hypotheses file (`hypotheses.md` is required before campaigns), LibreLane version.
