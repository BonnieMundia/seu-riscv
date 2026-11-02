// w3_crc32.c - W3: CRC-32 over 1 KB (memory + bit-operation workload).
//
// CRC-32/ISO-HDLC, the Ethernet / zip / Python zlib.crc32 CRC: reflected polynomial
// 0xEDB88320, start value 0xFFFFFFFF, final XOR 0xFFFFFFFF.
// Implementation: 16-entry ("nibble") table, 4 bits per step. Measured on this SoC
// (studies/seu/docs/decisions.md 2026-10-26): bit-by-bit 483,740 cycles and a 256-entry table
// 203,291 cycles are both over the 200k budget; this version is ~119k.
// Outputs: 1) CRC of "123456789" = the standard check value 0xCBF43926 (self-test),
//          2) CRC of a 1 KB pseudo-random buffer.
#include "common.h"

#define POLY 0xEDB88320u
#define LEN  1024

static uint8_t  buf[LEN];
static uint32_t T[16];

// One CRC step for one bit (reflected CRC: shift right, XOR the polynomial if the bit
// that falls out was 1). Branch-free: -(c & 1) is 0x00000000 or 0xFFFFFFFF.
static inline uint32_t bit_step(uint32_t c)
{
    return (c >> 1) ^ (POLY & -(c & 1u));
}

// T[i] = effect of the 4 low bits i on the CRC = 4 bit steps starting from i.
static void build_table(void)
{
    for (uint32_t i = 0; i < 16; i++) {
        uint32_t c = i;
        for (int k = 0; k < 4; k++)
            c = bit_step(c);
        T[i] = c;
    }
}

static uint32_t crc32(const uint8_t *p, int n)
{
    uint32_t c = 0xFFFFFFFFu;
    for (int i = 0; i < n; i++) {
        c ^= p[i];
        c = (c >> 4) ^ T[c & 15];    // low nibble of the byte
        c = (c >> 4) ^ T[c & 15];    // high nibble of the byte
    }
    return ~c;
}

int main(void)
{
    static const uint8_t check[9] = {'1', '2', '3', '4', '5', '6', '7', '8', '9'};

    build_table();
    report(crc32(check, 9));

    // 1 KB input: each xorshift32 word gives 4 bytes, lowest byte first.
    uint32_t seed = 0x0BADF00Du;
    for (int i = 0; i < LEN; i += 4) {
        uint32_t w = xorshift32(&seed);
        buf[i]     = (uint8_t)w;
        buf[i + 1] = (uint8_t)(w >> 8);
        buf[i + 2] = (uint8_t)(w >> 16);
        buf[i + 3] = (uint8_t)(w >> 24);
    }
    report(crc32(buf, LEN));
    return 0;
}
