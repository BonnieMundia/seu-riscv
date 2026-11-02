# Phase 3 walkthrough: the golden model and the lockstep test (Gate 1)

Goal of this phase: prove that the RTL does **exactly** what the RISC-V spec says, on
every instruction of every workload, before we start breaking it with fault injection.
If the fault-free hardware already had a bug, every "SDC" we measure later could be
that bug instead of the injected fault.

Commands: `make lockstep` (all workloads + ISA test), `make lockstep W=w2_qsort`,
`make gate1` (= `make check` + `make lockstep`).

---

## 1. The golden model: `model/rv32i_iss.py`

An **ISS (instruction-set simulator)** is a program that executes machine code one
instruction at a time, following the ISA rules, with no clocks or hardware detail. Ours
is about 240 lines of Python:

- **Loading:** pyelftools reads the ELF's `PT_LOAD` segments (code + data) into a 64 KB
  `bytearray`, the same bytes the RTL gets from the hex file.
- **State:** `pc` and `x[0..31]`. Reset copies PicoRV32: `pc = 0`, `x2 = 0x10000`.
- **One `step()`** = fetch the 32-bit word at `pc`, cut out the fields (opcode, rd, funct3,
  rs1, rs2, funct7, and the five immediate formats I/S/B/U/J), do the operation, write `rd`
  (never x0), compute the next PC.
- **Copies of our SoC rules:** RAM below 64 KB, reads elsewhere return 0, output port,
  done port, and traps for ECALL/EBREAK, illegal instructions and misaligned accesses or
  jump targets (PicoRV32 is built with `CATCH_ILLINSN=1`, `CATCH_MISALIGN=1`).
- **Not modelled on purpose:** FENCE and the counter CSRs. No program uses them, and the
  ISS raises `NotImplementedError` instead of guessing.
- **Python details worth knowing:** `sext(v, bits)` turns the top bit of a field into a sign
  (the immediates are signed); `signed()` reinterprets a 32-bit value for `slt`/`blt`/`sra`;
  every result is masked with `& 0xFFFFFFFF` because Python ints never overflow.

It also checks itself: the ISS's outputs equal the Python references for W1–W5, and
hello-world executes **44** instructions, the same number we counted by hand in Phase 1.

## 2. The lockstep test: `tb/cocotb/test_lockstep.py`

**cocotb** lets Python drive and watch a Verilog simulation: it starts the clock, applies
reset, and reads any signal (Verilator is built with `--public-flat-rw`, so internal CPU
signals can be read too; the fault injector will need the same thing to *write* them).

The ISS runs first and records three streams. Then the RTL runs and the test records the
same three streams from the hardware, once per cycle on the **falling** clock edge (the
middle of the cycle, when everything is settled for the next rising edge):

| stream | from the ISS | from the RTL |
|---|---|---|
| executed PCs | `pc` at each `step()` | `cpu.next_pc` whenever `cpu.launch_next_insn` is high |
| register writes | each write to x1..x31 | `cpu.latched_rd`, `cpu.cpuregs_wrdata` whenever `cpu.cpuregs_write` is high and `latched_rd != 0` (the exact write condition in picorv32.v) |
| stores | each SB/SH/SW | memory bus: `mem_valid & mem_ready & mem_wstrb != 0` |

All three must be identical. Then outputs must equal the Python reference, the run must
end with DONE, and the cycle count must equal `results/golden_runs.json`.

## 3. What went wrong on the way (and what it teaches)

1. **Fetches ≠ executed instructions.** The first version used bus fetches as the PC
   stream and failed on W2 at instruction 290. PicoRV32 **prefetches** the next
   sequential instruction while it executes the current one (`mem_do_prefetch`,
   picorv32.v ~line 1573) and throws it away when a branch is taken. W2: 6,610 fetches
   for 5,913 executed instructions. Fix: use `launch_next_insn`, the signal that marks
   the real start of an instruction.
2. **The hidden first write.** The RTL's first register write is `x2 = 0x10000`, before
   any instruction: PicoRV32 loads `STACKADDR` through its normal write port after reset.
   The ISS now logs it as write #0.
3. **Off by one in counting cycles.** `tb_soc.v` prints its counter *before* the
   non-blocking (`<=`) increment on the edge where it sees `done`. The test now uses the
   same convention (`cycles - 1`).

Each failure pointed to a real, explainable property of the hardware or the tools.
None of them was "fixed" by loosening the test.

## 4. Can the test catch bugs? (checked)

A deliberate bug was planted in the ISS (`srai` made logical instead of arithmetic). The
lockstep test failed on W4 at instruction 173 (a branch depending on the shifted value).
Then the ISS was restored.

## 5. Coverage: `sw/isa_test.c`

Counting the ISS trace showed that W1–W5 execute 27 of the 37 RV32I instructions. Never
executed: AUIPC, BLTU, LB, LH, SLTI, ORI, SLL, SLT, SLTU, SRA. `isa_test.c` runs each of
them (inline assembly forces the exact instruction) with edge cases (sign-extension,
only 5 shift bits used, signed vs unsigned compare) and 16 **hand-computed** expected
values. It passes three ways: hand values = ISS = RTL. All 37 instructions are now covered.

## 6. Results (Gate 1)

| workload | cycles | instructions | register writes | stores | lockstep |
|---|---|---|---|---|---|
| W1 matmul | 147,409 | 28,903 | 19,417 | 397 | PASS |
| W2 qsort | 33,800 | 5,913 | 3,856 | 836 | PASS |
| W3 crc32 | 119,032 | 22,073 | 18,841 | 1,316 | PASS |
| W4 attitude | 192,392 | 36,077 | 29,656 | 2,820 | PASS |
| W5 adsb_crc24 | 150,997 | 29,760 | 19,958 | 549 | PASS |
| isa_test | — | 96 | — | — | PASS |

(Register writes include the reset write of x2.)

---

## 7. Do it yourself

1. **Read one decode.** In `rv32i_iss.py`, find how `imm_b` is built. Take the `bgeu`
   at address `0x84` in `sw/build/w2_qsort.dis` (`0062f863`) and compute its offset by
   hand. *Check:* +16 (0x84 + 16 = 0x94, the target shown in the listing).
2. **Watch the prefetch.** `make wave PROG=w2_qsort` and open `tb_soc.vcd` in Surfer.
   Find the `bgeu` at `0x84` on its last pass, and see the bus fetch `0x88` and then `0x94`.
3. **Break it on purpose.** On a play branch, change `SLT` in the ISS to compare unsigned
   and run `make lockstep W=isa_test`. *Expect:* FAIL with "register write #… differs"
   at the `slt` result (the register-write stream is checked before the outputs; the
   first output would also have become 0).
4. **Explain to a reviewer** (viva practice): why is comparing register writes stronger
   than comparing only the final checksum? Give an example of a bug the checksum could miss.

## 8. Sources

- **RISC-V Unprivileged ISA spec**, chapter "RV32I Base Integer Instruction Set"
  (formats, immediates, every instruction): https://github.com/riscv/riscv-isa-manual/releases
- **PicoRV32 source** `rtl/picorv32.v`: `launch_next_insn` (~line 1400), register write
  port (~lines 1303–1344), `mem_do_prefetch` (~line 1573); README "Verilog Module Parameters".
- **cocotb docs** (triggers like `FallingEdge`, accessing signals): https://docs.cocotb.org/en/stable/
- **pyelftools** (reading ELF segments): https://github.com/eliben/pyelftools
- Background: the RISC-V Formal Interface (RVFI) is the "official" way to expose
  retired instructions for this kind of check; PicoRV32 supports it under
  `` `ifdef RISCV_FORMAL ``. We use existing internal signals instead, so the RTL under
  test is exactly the RTL we will inject faults into.
