// isa_test.c - not a workload: exercises the 10 RV32I instructions that W1-W5 never
// execute (found by counting the ISS trace on 2026-11-02): AUIPC, BLTU, LB, LH, SLTI,
// ORI, SLL, SLT, SLTU, SRA. Inline assembly forces the exact instruction.
// `make lockstep` runs it, so these instructions are checked three ways: hand-computed
// expected values (isa_test() in sw/ref/workloads.py), the golden ISS, and the RTL.
#include "common.h"

static volatile int8_t  b8[4]  = {-1, 0x7F, -128, 5};
static volatile int16_t h16[2] = {-2, 0x7FF0};

static uint32_t r2(uint32_t a, uint32_t b, int op)
{
    uint32_t r;
    switch (op) {
    case 0: __asm__ volatile("slt  %0, %1, %2" : "=r"(r) : "r"(a), "r"(b)); break;
    case 1: __asm__ volatile("sltu %0, %1, %2" : "=r"(r) : "r"(a), "r"(b)); break;
    case 2: __asm__ volatile("sll  %0, %1, %2" : "=r"(r) : "r"(a), "r"(b)); break;
    default: __asm__ volatile("sra %0, %1, %2" : "=r"(r) : "r"(a), "r"(b)); break;
    }
    return r;
}

static uint32_t bltu(uint32_t a, uint32_t b)       // 1 if the branch is taken
{
    uint32_t r;
    __asm__ volatile("li %0, 1\n\tbltu %1, %2, 1f\n\tli %0, 0\n1:"
                     : "=&r"(r) : "r"(a), "r"(b));
    return r;
}

int main(void)
{
    uint32_t m5 = (uint32_t)-5, r, here;

    report(r2(m5, 3, 0));                 // SLT  -5 < 3 (signed)          -> 1
    report(r2(m5, 3, 1));                 // SLTU 0xFFFFFFFB < 3 (unsigned) -> 0
    report(r2(1, 31, 2));                 // SLL  1 << 31                  -> 0x80000000
    report(r2(0x80000000u, 4, 3));        // SRA  arithmetic >> 4          -> 0xF8000000
    report(r2(0x12345678u, 36, 2));       // SLL  uses only 5 bits: << 4   -> 0x23456780

    __asm__ volatile("slti %0, %1, -4" : "=r"(r) : "r"(m5));
    report(r);                            // SLTI -5 < -4                  -> 1
    __asm__ volatile("ori  %0, %1, 0x34" : "=r"(r) : "r"(0x1200u));
    report(r);                            // ORI                           -> 0x1234
    __asm__ volatile("ori  %0, %1, -1" : "=r"(r) : "r"(0x0u));
    report(r);                            // ORI sign-extends the immediate -> 0xFFFFFFFF

    report(bltu(3, m5));                  // BLTU 3 < 0xFFFFFFFB: taken    -> 1
    report(bltu(m5, 3));                  // BLTU not taken                -> 0

    report((uint32_t)(int32_t)b8[0]);     // LB  -1                        -> 0xFFFFFFFF
    report((uint32_t)(int32_t)b8[2]);     // LB  -128                      -> 0xFFFFFF80
    report((uint32_t)(int32_t)h16[0]);    // LH  -2                        -> 0xFFFFFFFE
    report((uint32_t)(int32_t)h16[1]);    // LH  0x7FF0                    -> 0x00007FF0

    // AUIPC: rd = address of the auipc itself + (imm << 12). With imm 0, compare it with
    // the label's address computed by `la` (which the assembler expands to its own
    // auipc + addi pair, so 4 auipc in total): difference must be 0.
    __asm__ volatile("1: auipc %0, 0\n\tla %1, 1b" : "=&r"(r), "=&r"(here));
    report(r - here);                     // AUIPC                         -> 0
    __asm__ volatile("1: auipc %0, 1\n\tla %1, 1b" : "=&r"(r), "=&r"(here));
    report(r - here);                     // AUIPC imm 1 = +4096           -> 0x1000
    return 0;
}
