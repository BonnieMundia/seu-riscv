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
Phase 1 done: a C program runs on PicoRV32 (plain RV32I) in Verilator and writes
`0xC0FFEE` to the output port (191 cycles).

```sh
make sim            # build hello.c and run it on the simulated SoC
make sim PROG=name  # run sw/name.c instead
```

## Layout
`rtl/` hardware (upstream `picorv32.v`, untouched) · `sw/` workloads · `model/` Python
golden model · `tb/` testbenches · `fi/` fault injection · `synth/` synthesis ·
`analysis/` · `results/` · `viz/` · `docs/` · `paper/`

See `docs/environment.md` for tool versions and `docs/decisions.md` for design choices.
