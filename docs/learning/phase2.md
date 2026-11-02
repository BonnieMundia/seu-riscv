# Phase 2 walkthrough: the workloads (W1–W5)

Goal of this phase: five small C programs that each do real work and report one
checksum, plus an independent Python reference that proves each checksum is right.
These are the programs the fault-injection campaigns will run thousands of times.

Work on a play branch for experiments: `git switch -c play/phase2` … `git switch main`.

---

## 1. The pattern every workload follows

```
build inputs (fixed seed)  →  do the work  →  checksum  →  report() to OUT_PORT  →  return
```

and next to it, in Python:

```
sw/ref/workloads.py: same inputs → same work → same checksum   (no CPU involved)
```

`make check` runs both and compares. **Why both?** A CPU that prints *a* number proves
nothing. If an independent Python program gets the same number, both the C code and the
hardware are right. Later, the fault-injection runs are judged against these golden
outputs (Masked = same output, SDC = different output), so they must be correct.

---

## 2. `sw/common.h`: shared helpers

- **`OUT_PORT` / `report()`**: the `volatile` output port from Phase 1 (see phase1.md Q4:
  without `volatile` the compiler may delete writes).
- **`xorshift32()`**: a pseudo-random number generator. "Pseudo" = it looks random, but
  the same starting `seed` always produces the same sequence, so every run gets identical
  inputs. It uses only shifts and XORs, so it needs no multiply instruction (RV32I has
  none). Each workload starts with its own fixed seed.
- **`mix(cs, v)`**: the checksum step. It rotates the running checksum left by 5 bits
  and XORs in the next value. Rotation makes it **order-sensitive**: the same values in a
  different order give a different checksum. A plain sum would miss two swapped elements
  (important for W2, sorting).
- `static inline` = copy the function body into each caller (no call overhead, and no
  "unused function" warnings in workloads that don't use one).
- `uint32_t` / `int32_t` (from `<stdint.h>`) = exactly 32 bits, unsigned / signed. Always use
  exact-width types here so C and Python agree bit for bit.

## 3. W1: 8×8 matrix multiply (`sw/w1_matmul.c`)

`C[i][j] = Σk A[i][k] × B[k][j]`, i.e. 8 × 8 × 8 = **512 multiplies**, then a checksum of
all 64 results, row by row.

**Multiplication without a multiply instruction.** RV32I has no `mul`, so GCC calls
`__mulsi3` from libgcc (that's why the Makefile links `-lgcc`). Look at it in
`sw/build/w1_matmul.dis`:

```
__mulsi3:  a2 = a0; a0 = 0
loop:      if (a1 & 1) a0 += a2     # add when the current bit of b is 1
           a1 >>= 1 (logical)       # next bit of b
           a2 <<= 1                 # a doubles each step
           if (a1 != 0) goto loop
```

This is the long multiplication you learned at school, done in binary. **The number of
loop passes = position of the highest 1-bit of `b`.** `b = 200` (binary 11001000) → 8
passes. A **negative** `b` has its top bit set (two's complement), so it always costs
**32 passes**.

**The design decision this caused.** The first version used signed inputs −128…127. Half
the multiplies took 32 passes and W1 needed **344,337 cycles**, outside the 10k–200k
budget. With inputs 0…255 (like 8-bit pixel values) it takes **147,409 cycles**
(checksum `0x36c7bde8`, same on Verilator and Icarus). Logged in docs/decisions.md.

**Why this matters for the study:** W1's run time depends on the *data*. A bit flip in an
operand register can make a multiply longer or shorter. Keep that in mind when you see
the cycle counts of faulty runs. It's also why "Hang" is defined as > 2× golden cycles,
not "any change in cycles".

## 4. `sw/ref/workloads.py`: the Python reference

- Re-implements `xorshift32`, `mix` and the matrix multiply.
- **`& M32`** (`0xFFFFFFFF`): Python integers never overflow, but C's 32-bit ones wrap
  around. Masking after every shift/rotate makes Python behave exactly like the C code.
  (W1's sums stay small (max 8 × 255 × 255 = 520,200), so they never wrap.)
- `WORKLOADS` maps a workload name (= `sw/<name>.c`) to its function. Adding a workload
  = add a C file + one Python function + one line here.

## 5. `make check` (`tb/check_workloads.py`)

For each workload: build it (`make sw PROG=…`), run the simulator, read the `OUT` and
`DONE/TRAP/HANG` lines, compare with Python, print a PASS/FAIL table, and save the golden
outputs + cycle counts to `results/golden_runs.json`. It exits with an error code on any
FAIL. Tested on purpose with a wrong reference value: it reported FAIL and exit code 1.

---

## 6. Do it yourself

1. **Find the multiply.** In `sw/build/w1_matmul.dis`, search for `__mulsi3`. How many
   `jal … <__mulsi3>` instructions are there? Why only one, if there are 512 multiplies?
   *Check:* 1 call site, inside the innermost `k` loop.
2. **Count the passes by hand.** For `b = 200`, `b = 1`, `b = 255` and `b = -1`, how many
   times does the `__mulsi3` loop run? *Check in Python:* `(200).bit_length()`, and for
   −1 think of `0xFFFFFFFF`.
3. **Break the agreement.** On a play branch, change the seed in `w1_matmul.c` only and
   run `make check`. Predict PASS or FAIL. Then change the seed in `workloads.py` too.
   *Expect:* FAIL, then PASS. The reference must always mirror the C code exactly.
4. **Repeat the decision yourself.** Make the inputs signed again in **both** files
   (C: `(int8_t)(xorshift32(&seed) & 0xFF)`; Python: `v & 0xFF`, then subtract 256 if
   it is ≥ 128), and also mask the Python sum with `& M32`. Predict the cycle count.
   *Expect:* PASS, about 344k cycles.

## 7. Sources

- **libgcc** (what `__mulsi3` is): GCC internals manual, "The GCC low-level runtime
  library", integer arithmetic routines: https://gcc.gnu.org/onlinedocs/gccint/Integer-library-routines.html
- **Two's complement / why −1 is all ones:** RISC-V Unprivileged ISA spec, RV32I chapter
  (integer registers hold two's-complement values); Harris & Harris, *RISC-V Edition*, ch. 1
  "Signed Binary Numbers".
- **xorshift:** G. Marsaglia, "Xorshift RNGs", *Journal of Statistical Software* 8(14),
  2003. https://www.jstatsoft.org/article/view/v008i14
- **`<stdint.h>` exact-width types:** https://en.cppreference.com/w/c/types/integer

---

## 8. W3: CRC-32 over 1 KB (practice task; reference solution now in `sw/w3_crc32.c`)

> 2026-11-02: to protect Gate 1, Claude wrote W3 (decision of 2 Nov). Do this task on a
> play branch **without looking at `sw/w3_crc32.c` first**, then compare. Result to
> reproduce: outputs `cbf43926`, `0a6e4633`; 119,032 cycles.

You know CRCs from telecoms: Ethernet's frame check sequence is exactly this CRC-32.

### Spec (must match exactly, or the checksums won't agree)

| item | value |
|---|---|
| files | `sw/w3_crc32.c` (C) and a function `w3_crc32()` in `sw/ref/workloads.py` (+ add `"w3_crc32": w3_crc32` to `WORKLOADS`) |
| CRC | CRC-32 as used by Ethernet / zip / Python `zlib.crc32`: reflected polynomial `0xEDB88320`, start value `0xFFFFFFFF`, final XOR `0xFFFFFFFF` (catalogue name CRC-32/ISO-HDLC) |
| output 1 | CRC of the 9 ASCII bytes `"123456789"` → must be `cbf43926` (the standard "check value": a built-in self-test) |
| output 2 | CRC of a 1024-byte buffer: `seed = 0x0BADF00D`; each `xorshift32(&seed)` call gives **4 bytes, lowest byte first** (`w`, `w>>8`, `w>>16`, `w>>24`), 256 calls in total |
| budget | 10,000–200,000 cycles (`make check` now fails if outside) |
| done when | `make check` shows `w3_crc32 … PASS` and W1 still PASSes |

### How to work
```bash
git switch main && git pull
git switch -c w3-crc32          # a feature branch (real code, not a throwaway play/ branch)
# ... write the code, run `make check` until PASS ...
git add sw/w3_crc32.c sw/ref/workloads.py && git commit -m "W3: CRC-32 over 1 KB"
```
Then tell me. I review the diff, and after review we merge into `main`.

### Suggested path (correct first, then fast)
1. **Python first** (your strong side): `w3_crc32()` returns `[zlib.crc32(b"123456789"), zlib.crc32(buf)]`.
   Hint: `v.to_bytes(4, "little")`, and reuse `xorshift32` from the same file.
   Run `~/.venv/bin/python sw/ref/workloads.py` and check output 1 is `cbf43926`.
2. **C, bit-by-bit version** (the textbook algorithm): for each byte, XOR it into the low
   8 bits of `crc`; then 8 times: if the lowest bit is 1, `crc = (crc >> 1) ^ 0xEDB88320`,
   else `crc = crc >> 1`. At the end return `~crc`.
   *Expect:* `make check` gets the right answers but **FAILs the budget** (≈ 480k cycles).
   That's intended: now you have a correct version to compare against.
3. **C, faster version: 16-entry ("nibble") table.** Handle 4 bits per step instead of 1:
   - Build `T[16]` once at start: `T[i]` = run the bit step 4 times starting from `crc = i`.
   - Per byte: `crc ^= byte; crc = (crc >> 4) ^ T[crc & 15]; crc = (crc >> 4) ^ T[crc & 15];`
   *Expect:* same two outputs, and comfortably inside the budget.
   (A full 256-entry table is **not** faster here: building it costs ~118k cycles on its own.)

### Hints
- Use `uint8_t` for bytes and `uint32_t` for the CRC; `#include "common.h"`.
- Put the 1 KB buffer as a global: `static uint8_t buf[1024];`.
- Write one function `uint32_t crc32(const uint8_t *p, int n)` and call it twice.
- Branch-free bit step (optional): `crc = (crc >> 1) ^ (0xEDB88320u & -(crc & 1));`
  Work out why `-(crc & 1)` is either `0x00000000` or `0xFFFFFFFF`.

### Questions to answer in your PR/commit message or to me
1. Why does the bit-by-bit version cost so many cycles on PicoRV32? (Count instructions per bit.)
2. Why does the 16-entry table beat both the bit-by-bit version and a 256-entry table here?
3. Which CPU units does W3 stress most compared to W1? (Think: shifts, XOR, loads.)

### Sources
- CRC catalogue (Greg Cook), entry CRC-32/ISO-HDLC, gives poly/init/xorout/check value:
  https://reveng.sourceforge.io/crc-catalogue/17plus.htm
- Python `zlib.crc32`: https://docs.python.org/3/library/zlib.html#zlib.crc32
- Ross Williams, "A Painless Guide to CRC Error Detection Algorithms" (classic tutorial,
  explains table-driven CRCs): http://www.ross.net/crc/download/crc_v3.txt

---

## 9. W2: quicksort of 64 signed integers (`sw/w2_qsort.c`)

- **Algorithm:** recursive quicksort, Lomuto partition: take the last element as the
  pivot, move everything smaller to the left, put the pivot in between, then sort both
  sides. Inputs are full 32-bit values read as signed, so negatives are included.
- **Signed compare:** `v[j] < pivot` on `int32_t` compiles to `blt` (signed). With
  `uint32_t` it would be `bltu` and the order would differ: −1 would sort *after* 5.
- **Reference:** any correct sort gives the same final order, so Python's `sorted()` is a
  fully independent check of the C quicksort. Result: `0x9c86f267`, **33,800 cycles**
  (Verilator = Icarus).
- **What GCC did** (`sw/build/w2_qsort.dis`): the function is named
  `quicksort.constprop.0` ("constant propagation": `v` is always the same array, so GCC
  specialised it). The first recursive call is a real call (`sw ra,28(sp)` saves the
  return address on the stack, `jal` jumps back into the function). The second call is
  the last thing the function does, so GCC turned it into a jump back to the top
  (**tail-call elimination**).
- **Why it matters for faults:** return addresses on the stack sit in RAM (not injected),
  but on the way there they pass through `ra`, `sp` and the PC (injected). A flipped bit
  in `ra` just before `ret` sends the CPU somewhere random → expect more Crash/Hang
  outcomes for W2 than for W1, especially in the PC unit (that's experiment E3).

### Do it yourself
1. In `w2_qsort.dis`, find `blt` inside `quicksort.constprop.0`. Change `int32_t` to
   `uint32_t` for the array on a play branch: which instruction replaces it, and does
   `make check` still PASS? *Expect:* `bltu`; FAIL (unsigned order ≠ signed `sorted()`).
2. Count the `jal … <quicksort.constprop.0>` lines. Why only one, when the C code has two
   recursive calls? *Check:* 1 (tail-call elimination).
3. Predict: what happens to the cycle count if the input is already sorted? (Hint:
   Lomuto with last-element pivot.) Try it on a play branch by sorting `a` first in C.

Source: Cormen et al., *Introduction to Algorithms*, ch. 7 "Quicksort" (Lomuto partition);
RISC-V Unprivileged ISA spec, RV32I "Conditional Branches" (`BLT` vs `BLTU`).

---

## 10. W4: fixed-point attitude filter + attitude hold, 200 steps (`sw/w4_attitude.c`)

**What it simulates, per step and per axis (roll, pitch, yaw):** a plant (true rate and
angle, pushed by the actuator command plus a random disturbance), sensors (gyro = rate +
bias + noise; accelerometer angle for roll/pitch = angle + noise), a **complementary
filter** (integrate the gyro, then move 1/32 of the way toward the accelerometer angle),
and a **PD controller** `u = −(1.5·angle + 0.25·rate)`, saturated at ±0.5.

**Fixed point (Q16.16):** a real number x is stored as the integer x·65536. 1.0 = 65536,
0.01 = 655. Adding works as normal; multiplying by 1/64 is `>> 6`. Python's `>>` on
negative numbers and GCC's `>>` on `int32_t` (the `sra` instruction) both round toward
minus infinity, so the C code and the Python mirror agree bit for bit.

**No multiplies at all** (`grep __mulsi3 sw/build/w4_attitude.dis` finds nothing): dt =
1/64, filter gain = 1/32, controller gains 1.5 = 1 + 1/2 and 0.25 = 1/4, all done with shifts
and adds. That's standard practice on small flight-control CPUs, and here it's essential:
one signed software multiply can cost ~800 cycles.

**Getting inside the cycle budget (measured, all versions correct):**

| version | cycles |
|---|---|
| 3 `xorshift32` calls per axis, 2 `mix` calls per axis | 242,986 ❌ |
| 1 `xorshift32` per axis, noise cut from bit fields 0–11 / 12–21 / 22–31 | 207,768 ❌ |
| + one `mix` per axis of `est ^ u` | 199,992 (8-cycle margin, too fragile) |
| + one `mix` per **step** of Σ(`est ^ u`) | **192,392** ✅ checksum `0x8ec3e146` |

Lesson: on PicoRV32 **shifts by many bits are expensive** (no barrel shifter: README CPI
table, 4–14 cycles), and xorshift/mix are made of them. Count shifts when you need speed.

**Does the filter work?** (from the Python trace, `w4_attitude(trace)`): roll/pitch
estimate error RMS 0.005 / 0.008 rad after step 50; yaw drifts to +0.06 rad (no
accelerometer reference for yaw, so the gyro bias integrates: realistic). The controller
keeps all true angles below 0.1 rad.

**Unlike W2/W3, the reference is a line-by-line mirror** (there's no standard library
for "this filter"). It's still independent of the CPU and compiler, and it asserts that no
value ever reaches 2³¹, so 32-bit wrap-around can't hide a mismatch.

### Do it yourself
1. Convert by hand: what is 0.25 rad/s in Q16.16? What real value is `est = -3277`?
   *Check:* 16384; about −0.05 rad.
2. Why is `-7 >> 1` equal to −4 and not −3? Try it in Python, then find the `srai` in
   `w4_attitude.dis`.
3. On a play branch, set the yaw bias to 0 in **both** files. Predict the yaw drift, then
   measure with the trace snippet above. *Expect:* `make check` PASS (new checksum), and
   much smaller yaw error.

Sources: Mahony, Hamel & Pflimlin, "Nonlinear complementary filters on the special
orthogonal group", IEEE Trans. Automatic Control 53(5), 2008 (the complementary-filter
idea); PicoRV32 README, "Cycles per Instruction Performance" (shift cost).

---

## 11. W5: Mode S / ADS-B CRC-24 check (`sw/w5_adsb_crc24.c`)

**The frame:** an ADS-B extended squitter (downlink format 17) is 112 bits = 14 bytes:
5 bits DF (17) + 3 bits capability, 24-bit ICAO aircraft address, 56-bit message, then 24
parity bits. First byte `0x8D` = DF17, CA5.

**Mode S parity:** generator polynomial `0x1FFF409` (25 bits; usually written `0xFFF409`
without the leading x²⁴ term), processed MSB first, start value 0, no final XOR. It's a
different family from W3's Ethernet CRC: not reflected, and no start/end inversion.

**Receiver check = syndrome:** CRC of the 88 data bits XOR the 24 received parity bits.
0 = valid. Mathematically the syndrome equals the remainder of the *whole* 112-bit frame
divided by the generator, which is exactly what the Python reference computes, by a
different method (big-integer long division instead of a shift register). Real decoders
(e.g. dump1090) also use the syndrome to **locate and fix a single flipped bit**, because
every bit position gives a different syndrome.

**The 32 frames:** 4 real frames from "The 1090 MHz Riddle" (all checked: remainder 0),
14 synthetic DF17 frames with parity computed on the CPU (the transponder's job), and 14
corrupted copies with one bit flipped (bad reception). Result: `OUT 00000012` = 18 valid
frames, `OUT 32f0a6da` = checksum of all 32 syndromes; **150,997 cycles** (Verilator = Icarus).
The bit-by-bit CRC (88 bits × 46 CRC runs ≈ 4,000 bit steps) fits the budget, so no table
was needed.

**Why it's a good fault target:** the code is a tight bit loop where the *decision*
(`s == 0`) is what matters. A fault can make a corrupted frame look valid or a valid one
look corrupted: an SDC in the first output that would matter in a real receiver.

### Do it yourself
1. Decode the header of `8D4840D6…`: DF, CA and the ICAO address. *Check:* DF 17, CA 5,
   ICAO `4840D6`.
2. In Python: `from workloads import mode_s_remainder` and flip each of the 112 bits of
   a real frame in turn. Are all 112 syndromes non-zero and all different?
   *Expect:* yes, which is why single-bit correction is possible.
3. Why does `0x80 >> (pos & 7)` pick bit `pos` in MSB-first order? Work out `pos = 0`
   and `pos = 9` by hand.

Sources: J. Sun, *The 1090 Megahertz Riddle* (2nd ed.), chapter "Error control" (gives
the generator `1111111111111010000001001` and sample frames):
https://mode-s.org/1090mhz/content/ads-b/8-error-control.html ; ICAO Annex 10 Vol. IV
(Mode S parity, the formal standard).
