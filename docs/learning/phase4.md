# Phase 4 walkthrough: fault targets and the injector (Gate 2)

Goal of this step: a complete, checked list of every bit we will flip in the fault
campaigns, each one labelled with its unit (PC, control, decoder, ALU, memory interface,
counters, register file). RQ1 compares failure rates **per unit**, so this list decides
what every later number means.

Commands: `make ffs` (Yosys → flip-flop list), `make targets` (check the descriptor),
`make fi` (build the injector), `make fi-test` (injector + classifier tests).

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

## 4b. The injector: `platform/fi/inject.cpp` (C++, Verilator + VPI)

**What it does.** One run = one program, at most one bit flip, one JSON line out:
`{"status":"done","cycles":32387,"outputs":["d5d609f1"],"injected":true,"before":"000000f0","after":"000000f4"}`

**Why C++ and not the Verilog testbench.** `tb_soc.v` cannot stop at cycle T and overwrite
an internal flip-flop chosen at run time. A small C++ `main()` can: Verilator turns the SoC
into a C++ class (`Vsoc`); our loop drives `clk` and `resetn` ourselves.

**VPI** (Verilog Procedural Interface, IEEE 1800 chapter 36-38) is the standard C API for
reading and writing signals of a running simulation by name. Verilator supports it when
built with `--vpi`; `--public-flat-rw` keeps every signal visible and writable. Steps
in the harness:
1. `vpi_handle_by_name("TOP.soc.cpu.reg_pc")` finds the signal (for the register file:
   handle of `cpu.cpuregs`, then `vpi_handle_by_index(h, 5)` for word x5).
2. At cycle T: `vpi_get_value` (as 32-bit chunks, `vpiVectorVal`, so 64-bit counters work
   too), XOR the chosen bit(s), `vpi_put_value`, then `eval()` so the logic sees it.
3. Keep clocking until `done`, `trap`, or the time limit.

**Same clock count as the testbench.** Before each rising edge it checks `out_valid`,
`done`, `trap`, the limit (the same order as `tb_soc.v`), then clocks. So fault-free runs
give *exactly* the cycles in `golden_runs.json`. The flip happens at "cycle T" = after T
clock edges since reset was released. Proof: flipping `count_cycle` at T = 1000 shows the
counter read 1000 just before the flip.

**Speed:** about 0.01 s for a whole workload, so a 1,068-run campaign is a few minutes.

**`platform/fi/injector.py`** is a short Python wrapper: builds the command line from a
descriptor `Site` (main bit + `also` bits), runs the harness, returns the JSON as a dict.

**Checked by `make fi-test`** (`test_injector.py`, 11 tests): fault-free = golden on
W1–W5 (outputs and cycles); the flip changes exactly the requested bits (single bit,
64-bit counter, 12-bit shared flip-flop, register-file word); a flip after the program ended
is reported `injected:false`; same flip twice = same result; a bit outside the signal is an
error. Before that, all 123 signal names of the descriptor were looked up through VPI
(`+resolve=`): none missing, all widths large enough.

**First hand-picked flips on W2** (single runs, *not* statistics):
| flip at cycle 10,000 | result |
|---|---|
| `count_cycle[63]` (cycle 1000) | right answer (no workload reads the counter) |
| `reg_next_pc[2]` | wrong answer `d5d609f1`: one instruction skipped (SDC) |
| `cpuregs[2]` (sp) bit 4 | trap (stack corrupted) |
| `cpuregs[31]` bit 0 | right answer (W2 never uses x31) |
| `cpu_state[7]` | hang (two states on at once, the state machine is stuck) |

## 4c. Your turn: the outcome classifier (`platform/fi/classify.py`)

The harness only reports facts (status, outputs). Turning them into masked / SDC / crash
/ hang / detected is a separate, small, pure-Python function, so another study (HDC) can
add its own sub-outcomes without touching the C++. The spec is in the file's docstring;
the 12 tests in `test_classify.py` describe it exactly. Write it, run `make fi-test` until
29 passed, and commit it yourself (`[platform] Outcome classifier`). I will review it.

## 4d. The campaign runner: `platform/fi/campaign.py`

An **experiment file** (`studies/seu/experiments/<name>.yaml`) says which workloads, which
units, how many runs per (workload, unit) "cell", and the random seed. `make smoke` runs
`smoke.yaml`: W2 × 7 units × 10 = 70 runs. That is a plumbing check, never a result.

What the runner does, and why:
- **Sampling.** For each run: a flip-flop chosen uniformly among the unit's sites, and a
  cycle chosen uniformly in [0, golden cycles). Uniform over "which bit × when" is the
  standard statistical fault injection of Leveugle et al. (2009), the paper that gives our
  sample sizes (1,068 runs = ±3 % at 95 %).
- **Seeds.** Each cell gets its own generator, seeded from sha256(seed/workload/unit).
  So the same experiment file always gives the same runs (reproducible), and adding W5
  later does not change the W1 samples. (Python's `hash()` is randomised per run, so
  it cannot be used.)
- **Parallel.** `multiprocessing.Pool` with 8 workers (SEU's share in
  `../seu-riscv-coord/cpu_budget.json`). Each worker starts the harness for one run.
- **Results.** One CSV row per run in `studies/seu/results/raw/<name>.csv` (git-ignored:
  raw data can be big) with run_id, workload, unit, signal, bit, cycle, outcome, status,
  cycles_run, bad_addr, detected, seed. Tool versions and the git commit go once into
  `<name>.meta.json` next to it.
- **Resume.** Rows are written as soon as each run finishes. Run the same command again
  after a crash or Ctrl-C and only the missing runs are done (useful: the MacBook Air is
  fanless and slows down on long runs).
- **Guards.** More than 1,000 runs stops with "ask Boniface, then add --confirm". A lock
  file in `../seu-riscv-coord/locks/` stops two campaigns at once (both checked).

Tests: `test_campaign.py` (6 tests: plan size, unique ids, same seed = same plan, other
seed = other plan, adding a workload leaves other cells unchanged, sites stay in their unit).
The full chain (plan → 70 injections → classify → CSV → resume) was checked once with a
private reference classifier; that output was deleted, so your first `make smoke` is the
real one.

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
5. **Your first injection.** `make fi sw PROG=w2_qsort`, then
   `./obj_dir_fi/Vinject +hex=build/seu/w2_qsort.hex +max_cycles=67600 +sig=cpu.reg_next_pc +bits=2 +cycle=10000`.
   *Expect:* `"outputs":["d5d609f1"]` (golden is `9c86f267`). Now try `+bits=3`: predict
   first whether the answer will be right or wrong, then run it.
6. **Write `classify()`** (§4c) and get `make fi-test` to `29 passed`.
7. **Your first campaign.** `make smoke`. *Expect:* `70/70 runs` in about a second, and a
   CSV in `studies/seu/results/raw/`. Count outcomes per unit with pandas
   (`pd.read_csv(...).groupby(["unit","outcome"]).size()`). Then run `make smoke` again:
   *expect* `70 already done, 0 to run`.
8. **Reproducibility.** Delete the CSV, run `make smoke` again, and compare the
   outcome counts with step 7. *Expect:* identical. Explain why (two reasons: seeds, and
   the simulator is deterministic).

## 6. Sources

- **Yosys built-in help** (primary, matches the installed 0.69): `yosys -h synth` lists the
  `begin / coarse / fine / check` stages and the `-flatten`, `-nofsm`, `-run` options;
  `yosys -h read_verilog` states that `SYNTHESIS` is defined automatically; `yosys -h write_json`
  describes the JSON netlist format (cells, connections, netnames).
- **Verilator manual** (primary): page "verilator Arguments" (exe_verilator.html) for `--vpi` and
  `--public-flat-rw`, and the "Connecting to Verilated Models" chapter (C++ main loop,
  `VerilatedContext`, `eval()`): https://verilator.org/guide/latest/
- **IEEE 1800 (SystemVerilog) standard**, the VPI chapters: `vpi_handle_by_name`,
  `vpi_get_value`, `vpi_put_value`, `s_vpi_vecval`. The installed header
  `$(verilator --getenv VERILATOR_ROOT)/include/vltstd/vpi_user.h` has the same definitions.
- **Leveugle, Calvez, Maistri, Vanhauwaert (2009)**, "Statistical fault injection:
  quantified error and confidence", DATE 2009: the sampling method and the sample-size
  formula behind 1,068 / 2,401 / 9,604.
- **Python docs**: `multiprocessing.Pool.imap_unordered`, `random.Random` (seeded
  generator), `hashlib.sha256`.
- **PicoRV32 source** `platform/rtl/picorv32/picorv32.v`: `cpuregs` declaration (~203),
  write port (~1337), read with x0 check (~1352), `mem_la_addr` (382), `cpu_state`
  encodings (~1172).
- **Beginner background:** the Yosys manual's "Getting started" chapter (on the
  YosysHQ documentation site) walks through `synth` on a small example.
