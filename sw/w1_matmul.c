// w1_matmul.c - W1: 8x8 integer matrix multiply (compute-heavy workload).
//
// C = A x B with 32-bit signed integers. RV32I has no multiply instruction, so each
// a*b becomes a call to __mulsi3 in libgcc (a shift-and-add loop). That makes this
// workload exercise the ALU, shifter and register file hard.
// Output: one checksum of all 64 elements of C, row by row.
#include "common.h"

#define N 8

static int32_t A[N][N], B[N][N], C[N][N];

int main(void)
{
    uint32_t seed = 0x1234567u;

    // Inputs: values 0..255 (low 8 bits of the generator), like 8-bit pixel data.
    // Kept non-negative on purpose: __mulsi3 loops once per bit up to the highest 1-bit
    // of one operand, so a negative operand (top bits all 1) always costs 32 passes and
    // pushed W1 to 344k cycles; 0..255 keeps it inside the 10k-200k budget.
    for (int i = 0; i < N; i++)
        for (int j = 0; j < N; j++)
            A[i][j] = (int32_t)(xorshift32(&seed) & 0xFF);
    for (int i = 0; i < N; i++)
        for (int j = 0; j < N; j++)
            B[i][j] = (int32_t)(xorshift32(&seed) & 0xFF);

    for (int i = 0; i < N; i++)
        for (int j = 0; j < N; j++) {
            int32_t acc = 0;
            for (int k = 0; k < N; k++)
                acc += A[i][k] * B[k][j];
            C[i][j] = acc;
        }

    uint32_t cs = 0;
    for (int i = 0; i < N; i++)
        for (int j = 0; j < N; j++)
            cs = mix(cs, (uint32_t)C[i][j]);

    report(cs);
    return 0;
}
