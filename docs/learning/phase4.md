# Phase 4 walkthrough: which bits can a particle hit? (Gate 2, step 1)

Goal of this step: a complete, checked list of every bit we will flip in the fault
campaigns, each one labelled with its unit (PC, control, decoder, ALU, memory interface,
counters, register file). RQ1 compares failure rates **per unit**, so this list decides
what every later number means.

Commands: `make ffs` (Yosys → flip-flop list), `make targets` (check the descriptor).

---

## 1. Why we ask a synthesis tool

A single-event upset flips a bit stored in a **flip-flop** (or a memory cell). In Verilog,
storage is written as `reg`, but not every `reg` becomes a flip-flop:

- a `reg` can be pure combinational logic (assigned in `always @*`);
- a flip-flop whose output nobody uses is deleted by synthesis. Example: PicoRV32 has
  a `mem_instr` output, but our `soc.v` never reads it, so it is not in the hardware;
- two flip-flops that always hold the same value are merged into one.

**Synthesis** (Yosys) turns the Verilog into real hardware cells. Its list of flip-flops
is what a chip would contain. Injecting into a bit that does not exist in hardware would
add fake results.

## 2. `platform/synth/list_ffs.py`

1. Runs Yosys: `read_verilog` both files, then
   `synth -flatten -nofsm -top soc -run :fine`, then `write_json`.
   - `-flatten` removes the hierarchy, so names become `cpu.reg_pc` (`cpu` is the
     PicoRV32 instance inside `soc`).
   - `-run :fine` stops after the **coarse** stage: Yosys has optimised the design
     (removed unused and constant logic) but still works with whole words (a 32-bit
     register = one cell), so names are still readable.
   - `-nofsm`: Yosys's `fsm` pass would re-encode `cpu_state` into its own encoding.
     The simulator keeps PicoRV32's 8-bit one-hot encoding (picorv32.v ~line 1172), so
     the list must use the same.
2. Python reads the JSON. For each flip-flop cell it takes the output pin **Q**, bit by
   bit, and finds its name. One wire can have several names
   (`assign dbg_mem_addr = mem_addr;` gives two names to the same wire). We keep the
   name declared as `reg`, because that is the variable the simulator stores and the
   injector will overwrite.
3. **Shared flip-flops.** `decoded_imm_j[31:20]` are 12 copies of the instruction's sign
   bit. Yosys builds **one** flip-flop for them. The list keeps bit 20 and notes bits
   21–31 under `"also"`. One particle hits one flip-flop, so the injector must flip all
   12 RTL bits together.
4. Memories (`cpu.cpuregs` = the register file, `ram`) are listed separately: width × depth.

Output: `studies/seu/targets/ff_list_h0.json`. **647 flip-flop bits in 98 signals** plus
two memories (regfile 32 × 32, RAM 16384 × 32).

One change to our own `soc.v`: Yosys cannot run `$value$plusargs` (that is a simulator
feature), so the hex loader is wrapped in `` `ifndef SYNTHESIS `` (Yosys defines
`SYNTHESIS` by itself). `make gate1` was re-run: identical results.

## 3. The descriptor: `studies/seu/targets/soc_h0.yaml`

The descriptor is the study's decision on what counts as a target and in which unit. The
platform code (`platform/fi/descriptor.py`) knows nothing about PicoRV32; another core
or study just writes another YAML file.

| unit | what is in it | bits |
|---|---|---|
| regfile | `cpuregs` words x1..x31 | 992 |
| alu | `reg_op1`, `reg_op2`, `reg_out`, `alu_out_q`, `reg_sh` | 133 |
| counters | `count_cycle`, `count_instr` (64-bit each) | 128 |
| decoder | `instr_*`, `is_*` flags, `decoded_*`, decoder triggers | 125 |
| memif | `mem_valid`, `mem_addr`, `mem_wdata`, `mem_wstrb`, `mem_state`, `mem_do_*`, `mem_rdata_q`, `mem_wordsize` | 107 |
| pc | `reg_pc`, `reg_next_pc` | 62 |
| control | `cpu_state`, `trap`, `latched_*` | 20 |
| **total** | | **1,567** |

Left out on purpose, each with a reason in the YAML:
- **RAM**: assumed ECC-protected (a project assumption).
- **x0**: `cpuregs[0]` is never written (`if (... && latched_rd)`, ~line 1337) and never
  read (`decoded_rs1 ? cpuregs[...] : 0`, ~line 1352). A flip there cannot matter.
- **SoC glue**: `mem_ready`, `mem_rdata` (the SoC's memory controller), `out_data`,
  `out_valid`, `done` (our measuring points: flipping the thermometer is not a fault in
  the patient), `bad_addr` (debug flag).
- **Bits that are always 0 in hardware**: `reg_pc[0]`, `reg_next_pc[0]` (no compressed
  instructions, so addresses are even), `mem_addr[1:0]` (word-aligned bus,
  `{..., 2'b00}` at line 382).

**The check is strict.** Every flip-flop bit must be in exactly one unit or excluded.
A typo in a pattern would otherwise silently drop bits and change the per-unit rates. Four
deliberate mistakes were tried, and all were caught: a signal in two units, a signal in no
unit, a misspelt pattern, and a non-existent excluded bit.

## 4. An honest limitation (we will report it)

A full gate-level synthesis merges a little more than the coarse stage: 642 instead of
647 non-memory flip-flop bits. Examples: the rs1/rs2 fields are stored once and shared by
`decoded_rs1` and `decoded_imm_j`; `latched_is_lu` is merged with an equivalent flag. We
inject at the RTL level (in Verilator), and the SKY130 netlist at Gate 3 will be different
again. So we use the RTL-level list and state the difference as a threat to validity.

---

## 5. Do it yourself

1. **Predict, then count.** How many bits should the `pc` unit have? (Two 32-bit regs,
   minus what?) Run `make targets`. *Expect:* 62.
2. **Find a removed reg.** Run
   `grep -c '"cpu.mem_instr"' studies/seu/targets/ff_list_h0.json`. *Expect:* 0. Explain
   why, using `soc.v` (look at what the `.mem_instr` port is connected to).
3. **Break the checker.** On a play branch, move `cpu.reg_sh` from `alu` to `control` *and*
   leave it in `alu`. Run `make targets`. *Expect:* `descriptor check FAILED`,
   `cpu.reg_sh: in 2 units ['control', 'alu']`. Then `git restore` the file.
4. **Viva practice.** A reviewer asks: "Why not just inject into every `reg` in the Verilog?"
   Answer in three sentences using §1 and the `mem_instr` example.

## 6. Sources

- **Yosys built-in help** (primary, matches the installed 0.69): `yosys -h synth` lists the
  `begin / coarse / fine / check` stages and the `-flatten`, `-nofsm`, `-run` options;
  `yosys -h read_verilog` states that `SYNTHESIS` is defined automatically; `yosys -h write_json`
  describes the JSON netlist format (cells, connections, netnames).
- **PicoRV32 source** `platform/rtl/picorv32/picorv32.v`: `cpuregs` declaration (~203),
  write port (~1337), read with x0 check (~1352), `mem_la_addr` (382), `cpu_state`
  encodings (~1172).
- **Beginner background:** the Yosys manual's "Getting started" chapter (on the
  YosysHQ documentation site) walks through `synth` on a small example.
