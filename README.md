# seu-riscv

**Workload-aware selective hardening of an open-source RISC-V core against single-event
upsets: a fully open-source simulation study.**

This project measures which parts of a small RISC-V CPU (PicoRV32, configured as plain
RV32I) fail most often when a single stored bit is flipped by radiation (a single-event
upset, SEU), across five small workloads (matrix multiply, quicksort, CRC-32, a
fixed-point attitude filter and an ADS-B CRC-24 check). It then compares selective
protections (register-file parity, SEC-DED ECC, partial TMR) with full TMR in terms of
reliability gained per unit of area, power and clock speed on SkyWater 130 nm. Everything
is simulation only, built with open-source tools (Verilator, Yosys, LibreLane, cocotb).

## Status
Gate 1 criterion met (2 Nov 2026): five workloads (W1–W5) run on PicoRV32 and match
independent Python references, and the RTL matches a Python RV32I golden model
instruction by instruction (cocotb lockstep), including a test covering all 37 RV32I
instructions.

```sh
make check          # run W1-W5, compare with Python references + cycle budget
make lockstep       # RTL vs golden ISS, instruction by instruction
make gate1          # both
make sim PROG=name  # run one program (studies/seu/sw/name.c or platform/tests/sw/name.c)
```

## Layout
A shared, core-agnostic platform plus two studies (details: `docs/platform.md`):

- `platform/`: pinned PicoRV32 (`rtl/picorv32/`, untouched, ISC licence), SoC +
  testbench (`rtl/soc/`), C runtime (`sw/runtime/`), Python RV32I golden model
  (`model/`), tests (`tests/`: golden checks, cocotb lockstep, test programs), and later
  the fault injector (`fi/`), statistics, synthesis, visualiser and web export.
- `studies/seu/`: this project's workloads, hardened variants, experiments, analysis,
  results and paper.
- `studies/hdc/`: a second study on hyperdimensional computing (separate branch).
- `docs/`: tool versions (`environment.md`), platform design, learning walkthroughs.
