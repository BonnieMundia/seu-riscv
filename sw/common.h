// common.h - helpers shared by all workloads (W1-W5).
//
// Every workload follows the same pattern:
//   1. build its input data deterministically (same data on every run),
//   2. do the work,
//   3. fold the results into one 32-bit checksum and write it to OUT_PORT once.
// sw/ref/workloads.py computes the same checksum in Python to check the result.
#ifndef COMMON_H
#define COMMON_H

#include <stdint.h>

// Memory-mapped I/O. Must be volatile: every write is a real event (see phase1.md Q4).
#define OUT_PORT (*(volatile uint32_t *)0x10000000)

static inline void report(uint32_t value)
{
    OUT_PORT = value;
}

// xorshift32 pseudo-random generator (Marsaglia, 2003). Uses only shifts and XORs,
// so it needs no multiply instruction. Same seed -> same sequence on every run.
static inline uint32_t xorshift32(uint32_t *state)
{
    uint32_t x = *state;
    x ^= x << 13;
    x ^= x >> 17;
    x ^= x << 5;
    *state = x;
    return x;
}

// Checksum step: rotate left by 5, then XOR in the next value. Order-sensitive, so
// swapped or wrong elements change the result. Uses only shifts and XORs.
static inline uint32_t mix(uint32_t cs, uint32_t v)
{
    return ((cs << 5) | (cs >> 27)) ^ v;
}

#endif
