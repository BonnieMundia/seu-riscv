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
