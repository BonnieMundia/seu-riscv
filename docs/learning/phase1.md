# Phase 1 walkthrough: hello-world on PicoRV32

Goal of this phase: a C program runs on a simulated RISC-V CPU and writes `0xC0FFEE` to
an output port. After reading this you should be able to explain every file, rebuild it
from scratch, and answer the self-check questions at the end without notes.

How to use this doc: read a section, do its "Do it yourself" tasks (predict first, then
run, then compare), and open the linked source to confirm what you read here. Do
experiments on a throwaway branch so `main` stays clean:

```bash
git switch -c play/phase1
```

When you are done: `git restore .` to undo edits, then `git switch main`.

---

## 1. The big picture

```
hello.c + crt0.S + link.ld
        │  riscv64-unknown-elf-gcc        (compile + link)
        ▼
   hello.elf   ── objdump ──► hello.dis   (human-readable assembly)
        │  riscv64-unknown-elf-objcopy -O verilog
        ▼
   hello.hex   (text file: one 32-bit word per entry)
        │  $readmemh in soc.v              (copied into the RAM array at time 0)
        ▼
 ┌──────────────── soc.v ────────────────┐
 │  picorv32 ◄── mem bus ──► RAM 64 KB   │
 │                     └──► out port / done port
 └───────────────────────────────────────┘
        ▲ clock + reset            │ out_valid / done / trap
        └──────── tb_soc.v ◄───────┘   prints OUT / DONE / TRAP / HANG
```

Three ideas to hold on to:
- **The CPU only sees memory.** It doesn't know about "printing". It just stores a word at
  an address. Our SoC decides that address `0x1000_0000` means "output port". This is
  called *memory-mapped I/O*: the network equivalent is a device that reacts to a
  particular destination address.
- **Hardware runs on clock edges.** Everything in `always @(posedge clk)` updates once per
  rising clock edge. A "cycle" is one clock period.
- **The simulator is the "chip".** Verilator turns the Verilog into a C++ program
  (`obj_dir/Vtb_soc`) that behaves cycle-by-cycle like the hardware would.

---

## 2. File by file

### 2.1 `sw/hello.c`
```c
#define OUT_PORT (*(volatile unsigned *)0x10000000)
OUT_PORT = 0xC0FFEE;
```
- `(unsigned *)0x10000000` treats the number as a pointer, so writing through it does a
  store instruction to that address.
- `volatile` tells the compiler "this write has a side effect, don't optimise it away".
  Without it, `-O2` may delete a write whose value is never read back.
- `return 0` hands control back to `crt0.S`.

### 2.2 `sw/crt0.S` (C runtime zero = startup code)
The CPU begins at address 0 after reset (`PROGADDR_RESET = 0`). C code can't run until
some setup is done, so these few assembly lines run first:
1. **Zero x1, x3–x31.** PicoRV32 doesn't clear its 32 registers on reset (it would cost
   chip area). In simulation they could hold anything. Zeroing them makes every run start
   identically, which the golden model (Phase 3) needs. x0 is always zero in RISC-V; x2 is
   the stack pointer.
2. **`li sp, 0x10000`**: the stack starts at the top of RAM and grows down. (PicoRV32 also
   sets sp from `STACKADDR`; doing it here too means the software doesn't depend on that.)
3. **Clear `.bss`**: C promises that uninitialised globals start at 0. The loop writes 0
   from `__bss_start` to `__bss_end` (labels made by the linker script).
4. **`call main`**, then **store to `0x10000004`** (the done port) to say "finished", then
   loop forever. The testbench stops the simulation as soon as it sees `done`.

`.section .text.start` puts this code in a specially-named section so the linker script
can force it to address 0.

### 2.3 `sw/link.ld` (linker script)
The linker decides *where in memory* each piece of the program goes.
- `MEMORY { RAM : ORIGIN = 0, LENGTH = 64K }` describes our only memory.
- `KEEP(*(.text.start))` first, so `_start` sits at address 0 where the CPU begins.
  This is the #1 cause of "nothing happens" bugs on bare-metal systems.
- Then `.text` (code), `.rodata` (constants), `.data` (initialised globals), `.bss`.
- `__bss_start` / `__bss_end` are symbols crt0 uses.

### 2.4 `Makefile`
- `make sw` compiles: `-march=rv32i -mabi=ilp32` = 32-bit base integer ISA only (no
  multiply), `-nostdlib` = no C library (we have no OS), `-ffreestanding` = don't assume
  standard library functions exist, `-lgcc` = link GCC's helper library, which supplies
  software multiply/divide (needed from Phase 2, since RV32I has no MUL instruction).
- `objdump -d` writes `sw/build/hello.dis`: the actual machine instructions. Read this
  file often; it's the truth about what the CPU runs.
- `objcopy -O verilog --verilog-data-width=4` makes the hex file (see 2.5).
- `make sim` builds the simulator with Verilator and runs it. `make wave` also records a
  waveform (`tb_soc.vcd`). `make clean` deletes all build outputs.
- Make only rebuilds what changed (it compares file timestamps).

### 2.5 The hex file and `$readmemh`
`sw/build/hello.hex` looks like:
```
@00000000
00000093 00000193 00000213 ...
```
- `@00000000` = "start loading at array index 0". With `--verilog-data-width=4` the
  index counts **32-bit words**, not bytes. We checked this: data at byte address 0x100
  came out as `@40` (0x100 / 4 = 0x40).
- Each entry is one 32-bit word. `00000093` is the instruction `li x1, 0` (= `addi x1, x0, 0`).
- `$readmemh(file, ram)` in soc.v reads it into `ram[]` before the simulation starts.

### 2.6 `rtl/soc.v` (the "system on chip")
- **`picorv32 #( ... ) cpu ( ... )`**: creates one CPU. The `#( )` list sets
  *parameters*: fixed choices made before the hardware is built (like compile-time
  constants). We set every one explicitly so the configuration is visible and recorded
  (docs/decisions.md). Unused inputs (`irq`, `pcpi_*`) are tied to 0 so the simulator
  and the synthesis tool see the same hardware.
- **`reg [31:0] ram [0:16383]`**: 16,384 words × 4 bytes = 64 KB.
- **The memory handshake (most important part).** The CPU sets `mem_valid=1` with
  an address (and data + `mem_wstrb` for a write) and holds it until we answer with
  `mem_ready=1` for one cycle. On a read we must put the data on `mem_rdata` in that same
  cycle. Our `always @(posedge clk)` block:
  - sees `mem_valid && !mem_ready` → sets `mem_ready <= 1` and registers the read data.
    The `!mem_ready` stops us serving the same request twice.
  - next cycle sets `mem_ready <= 0` again (the default at the top of the block).
- **`mem_wstrb`** (write strobe): 4 bits, one per byte. `1111` = write the whole word,
  `0001` = write only byte 0 (a `sb` store). That's why each byte lane has its own `if`.
- **`<=` (non-blocking assignment)**: all `<=` in a clocked block update together at the
  clock edge, like flip-flops. Use `<=` for clocked logic.
- **Reset**: when `resetn` is low (active-low reset) every output goes to a known 0.
  Without it, `done` could start as X/garbage and end the run instantly.
- **Address decode**: below 64 KB → RAM; `0x1000_0000` + write → `out_data`/`out_valid`;
  `0x1000_0004` + write → `done`; anything else → read 0 and set `bad_addr` (useful later,
  when injected faults make the CPU jump to strange addresses).

### 2.7 `tb/tb_soc.v` (testbench)
A testbench is Verilog that isn't hardware: it drives the clock/reset and watches outputs.
- `always #5 clk = ~clk;` toggles the clock every 5 time units (period 10).
- Hold `resetn = 0` for 5 cycles, then release.
- Each rising edge: count `cycles`; print `OUT xxxxxxxx` when `out_valid`; stop with
  `DONE`, `TRAP` (CPU hit an illegal/unsupported instruction or `ebreak`), or `HANG`
  (cycle limit reached). These exactly match the fault outcomes in the study.
- `$value$plusargs("hex=%s", ...)` reads command-line options like `+hex=file`. The fault
  injector will pass options the same way.

---

## 3. Worked check: why 191 cycles?

PicoRV32 README, section "Cycles per Instruction Performance", gives cycles per instruction:
ALU/`li`/`lui`/`jal` = 3, store = 5, taken branch = 5, `jalr` (`ret`) = 6.

hello-world executes 44 instructions (48 in the listing, but the `.bss` loop body and the
final `j` never run):

| part | instructions | cycles (README table) |
|---|---|---|
| zero 30 registers | 30 × `li` | 90 |
| set sp, `la` ×2 | 3 ALU | 9 |
| `bgeu` (taken, .bss is empty) | 1 | 5 |
| `jal main` | 1 | 3 |
| main: lui, addi, lui, sw, li, ret | 6 | 3+3+3+5+3+6 = 23 |
| done: lui, addi, sw | 3 | 3+3+5 = 11 |
| **total** | **44** | **141** |

Measured: 191. The waveform shows 48 memory transfers (46 fetches + 2 stores), each with
exactly **1 wait cycle**, because our RAM answers one cycle *after* `mem_valid`, while
the README's table assumes memory that answers in the same cycle. 141 + 48 = 189, plus about
2 cycles at start-up = 191. Lesson: always be able to explain your baseline numbers;
the "hang = more than 2x golden cycles" rule depends on them.

---

## 4. Do it yourself

1. **Read the machine code.** Open `sw/build/hello.dis`, find `<main>`. Explain why
   `lui a5,0xc10` then `addi a5,a5,-18` makes `0xC0FFEE`.
   *Check:* 0xc10 << 12 = 0xC10000; 0xC10000 − 18 = ?
2. **Two outputs.** In `hello.c` write `0x1234` then `0xC0FFEE`. Predict the output lines
   and whether the cycle count goes up or down, then `make sim`.
   *Expect:* two `OUT` lines, and more cycles (one extra `lui`/`addi`/`sw` group ≈ 3 instructions).
3. **Break the start address (two steps).**
   (a) In the `Makefile` swap the source order to `sw/$(PROG).c sw/crt0.S`, then
   `make clean sim`. *Expect:* still `DONE cycles=191`, and `hello.dis` still starts with
   `<_start>` at 0. Why? Because the `KEEP(*(.text.start))` line in `link.ld` forces it.
   (b) Now also delete that `KEEP(*(.text.start))` line and `make clean sim`.
   *Expect:* `<main>` is at address 0, you get about 66 `OUT 00c0ffee` lines and then
   `HANG`. Explain why: what is in `ra` when `main` executes `ret`, and where does the
   CPU go? (Hint: crt0 never ran.) This is exactly the kind of misbehaviour a fault in
   the PC can cause later.
4. **Bad address.** Write to `0x20000000` from `hello.c`. *Expect:* `WARN bad_addr`.
5. **Watch the handshake.** Install a viewer (`brew install surfer`), run `make wave`,
   open `tb_soc.vcd` in Surfer, and add `clk`, `dut.mem_valid`, `dut.mem_ready`,
   `dut.mem_addr`, `dut.mem_instr`. Find the store to `10000000` and count the cycles
   between `mem_valid` going high and `mem_ready` going high. *Expect:* 1.
6. **Second opinion.** Run the same program on Icarus:
   `iverilog -g2012 -o /tmp/tb rtl/picorv32.v rtl/soc.v tb/tb_soc.v && vvp -n /tmp/tb +hex=sw/build/hello.hex`
   *Expect:* the same `OUT` and `DONE cycles=191`.

Undo everything afterwards: `git restore . && make clean`.

---

## 5. Sources to verify (primary first)

- **PicoRV32 README**: sections "Verilog Module Parameters", "PicoRV32 Native Memory
  Interface", "Cycles per Instruction Performance". Local copy: `~/picorv32/README.md`;
  online: https://github.com/YosysHQ/picorv32
- **RISC-V Unprivileged ISA spec**: chapter "RV32I Base Integer Instruction Set"
  (instruction formats, `lui`/`addi`/`sw`/`jal`). https://github.com/riscv/riscv-isa-manual/releases
  (also listed at https://riscv.org/technical/specifications/)
- **RISC-V ELF psABI**: register names (`sp`, `a0`, `t0`), the `ilp32` ABI, calling
  convention. https://github.com/riscv-non-isa/riscv-elf-psabi-doc
- **RISC-V assembly manual**: pseudo-instructions like `li`, `la`, `call`, `ret`.
  https://github.com/riscv-non-isa/riscv-asm-manual
- **GNU ld, "Linker Scripts"**: https://sourceware.org/binutils/docs/ld/Scripts.html
- **GNU objcopy** (`-O verilog`, `--verilog-data-width`): https://sourceware.org/binutils/docs/binutils/objcopy.html
- **Verilator user guide** (`--binary`, `--trace`, warnings): https://verilator.org/guide/latest/
- **Icarus Verilog docs**: https://steveicarus.github.io/iverilog/
- **GNU make manual**: https://www.gnu.org/software/make/manual/make.html
- Beginner-friendly Verilog: **HDLBits** (interactive exercises, do "Getting Started",
  "Verilog Language" and "Sequential Logic → Latches and Flip-Flops") https://hdlbits.01xz.net/
  and **ChipVerify Verilog tutorial** https://www.chipverify.com/verilog/verilog-tutorial
- Book (recommended background): Harris & Harris, *Digital Design and Computer
  Architecture, RISC-V Edition*: chapters on sequential logic and single-cycle /
  multicycle processors.

---

## 6. Self-check questions (answer out loud, like a viva)

1. Why does `_start` have to be at address 0? Where is that number set in the hardware?
2. What does `volatile` prevent? What would the simulation print without it at `-O2`?
3. Walk through one store to the output port, cycle by cycle: which signals change, and when?
4. Why do we zero the registers in `crt0.S` instead of setting `REGS_INIT_ZERO=1`?
5. What is the difference between `DONE`, `TRAP` and `HANG`, and which fault outcome will
   each become in the study?
6. Why is the hello-world 191 cycles and not about 141?
7. Why is RAM never a fault-injection target in this study? (see docs/decisions.md)
