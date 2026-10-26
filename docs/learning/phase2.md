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

## 8. W3: CRC-32 over 1 KB (**your task**: you write it, I review)

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
