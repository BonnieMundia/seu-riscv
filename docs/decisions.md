# Decision log

One line per decision: `YYYY-MM-DD — decision — reason`.

- 2026-10-08 — Core = PicoRV32 upstream commit ef203c2 (docs/picorv32_commit.txt), copied unchanged to rtl/picorv32.v — reproducibility; all changes go in our own files.
- 2026-10-08 — RAM is assumed ECC-protected and is never a fault target; targets = core flip-flops + register file — keeps the study on the core.
- 2026-10-08 — Main study uses single bit flips only (no SET, no multi-bit upsets) — scope.
- 2026-10-08 — Memory map: 0x0000_0000–0x0000_FFFF 64 KB RAM (program + stack); 0x1000_0000 output port (each write logged); 0x1000_0004 done port (any write ends the run). Other addresses: reads return 0, soc.bad_addr goes high (sticky) — simple SoC, one RAM.
- 2026-10-08 — PicoRV32 config (all set explicitly in rtl/soc.v, names checked against picorv32.v @ ef203c2): ENABLE_MUL=0, ENABLE_FAST_MUL=0, ENABLE_DIV=0, COMPRESSED_ISA=0, ENABLE_IRQ=0, ENABLE_PCPI=0, ENABLE_TRACE=0, ENABLE_COUNTERS=1, ENABLE_COUNTERS64=1, ENABLE_REGS_16_31=1, ENABLE_REGS_DUALPORT=1, LATCHED_MEM_RDATA=0, TWO_STAGE_SHIFT=1, BARREL_SHIFTER=0, TWO_CYCLE_COMPARE=0, TWO_CYCLE_ALU=0, CATCH_MISALIGN=1, CATCH_ILLINSN=1, REGS_INIT_ZERO=0, PROGADDR_RESET=0x0, STACKADDR=0x0001_0000 — plain RV32I; counters kept on because "counters" is an RQ1 unit; misalign/illegal-instruction traps kept on so faults can show up as Crash/trap.
- 2026-10-08 — Unused core inputs (irq, pcpi_*) tied to 0 explicitly in soc.v — so Verilator, Icarus and Yosys all see the same hardware.
- 2026-10-08 — Memory interface: native PicoRV32 valid/ready; every request answered one cycle after mem_valid (registered mem_ready + mem_rdata) — same style as upstream testbench, no wait states.
- 2026-10-08 — crt0.S zeroes x1, x3–x31, sets sp=0x10000, clears .bss, calls main, then writes main's return value to the done port — PicoRV32 does not reset its register file (REGS_INIT_ZERO=0 keeps hardware realistic); golden model can assume all-zero registers.
- 2026-10-08 — Hex format: `objcopy -O verilog --verilog-data-width=4` used directly, no elf2hex.py. Verified on binutils 2.46: @addresses are WORD addresses (data at byte 0x100 -> @40) and each entry is one little-endian 32-bit word, matching soc.v ram[] — older binutils emitted byte addresses; re-check if binutils changes.
- 2026-10-08 — Link with -lgcc (rv32i/ilp32 multilib present) — RV32I has no MUL/DIV; workloads get software multiply/divide from libgcc.
- 2026-10-08 — Cycle count = clock edges counted by tb_soc.v from reset release until it sees done (or trap); timeout prints HANG (+max_cycles, default 1,000,000) — same definition will be used for golden cycle counts and the 2x-golden hang rule.
- 2026-10-12 — Single working copy at ~/Documents/GitHub/seu-riscv (old ~/seu-riscv copy retired); learning exercises live on play/* branches, never on main — two copies caused edits to be invisible to the other; main must stay the reference project.
- 2026-10-12 — Workload pattern: fixed-seed xorshift32 inputs (shifts/XORs only), work, one checksum via mix() = rotl5 ^ v, written once to OUT_PORT — deterministic, needs no MUL, order-sensitive checksum catches swapped elements.
- 2026-10-12 — Each workload has an independent Python reference (sw/ref/workloads.py); `make check` must PASS on all workloads before they are used for fault injection — proves C program + RTL are both right.
- 2026-10-12 — W1 inputs are 0..255 (not signed -128..127): libgcc __mulsi3 loops to the highest 1-bit of one operand, so negative operands cost 32 passes; signed version = 344,337 cycles (over the 10k-200k budget), unsigned = 147,409 cycles.
- 2026-10-12 — Golden fault-free results (outputs + cycles) are written to results/golden_runs.json by `make check` — source for the Hang rule (> 2x golden cycles).
- 2026-10-26 — `make check` also enforces the 10k-200k cycle budget (correct but out-of-budget = FAIL) — keeps every workload inside the project scope automatically.
- 2026-10-26 — W3 spec: CRC-32/ISO-HDLC (zlib, reflected 0xEDB88320, init/xorout 0xFFFFFFFF); outputs = CRC("123456789") (check value cbf43926) then CRC of 1 KB from seed 0x0BADF00D, one xorshift32 word -> 4 bytes little-endian — measured: bitwise 483,740 cycles, 256-entry table 203,291 (table build alone 118,483), 16-entry nibble table 119,032 -> nibble table is the intended implementation.
