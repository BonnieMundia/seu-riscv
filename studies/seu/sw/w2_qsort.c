// w2_qsort.c - W2: quicksort of 64 signed integers (branch-heavy workload).
//
// Recursive quicksort (Lomuto partition, last element as pivot). Lots of compares,
// data-dependent branches, function calls and stack use (return addresses, saved
// registers), so it exercises the PC, branch logic and control state more than W1.
// Note (checked in w2_qsort.dis at -O2): GCC keeps the first recursive call as a real
// call (ra saved on the stack, jal) and turns the second, final call into a loop
// (tail-call elimination); the function appears as quicksort.constprop.0.
// Output: one checksum of the sorted array, in order.
#include "common.h"

#define N 64

static int32_t a[N];

static void swap(int32_t *x, int32_t *y)
{
    int32_t t = *x;
    *x = *y;
    *y = t;
}

// Sorts a[lo..hi] (inclusive) in place.
static void quicksort(int32_t *v, int lo, int hi)
{
    if (lo >= hi)
        return;
    int32_t pivot = v[hi];
    int i = lo;
    for (int j = lo; j < hi; j++)
        if (v[j] < pivot)               // signed compare (blt)
            swap(&v[i++], &v[j]);
    swap(&v[i], &v[hi]);
    quicksort(v, lo, i - 1);
    quicksort(v, i + 1, hi);
}

int main(void)
{
    uint32_t seed = 0x51ED5EEDu;

    // Inputs: full 32-bit values, interpreted as signed, so negatives are included.
    for (int i = 0; i < N; i++)
        a[i] = (int32_t)xorshift32(&seed);

    quicksort(a, 0, N - 1);

    uint32_t cs = 0;
    for (int i = 0; i < N; i++)
        cs = mix(cs, (uint32_t)a[i]);

    report(cs);
    return 0;
}
