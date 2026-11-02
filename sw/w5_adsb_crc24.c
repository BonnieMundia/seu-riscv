// w5_adsb_crc24.c - W5: Mode S / ADS-B CRC-24 check on sample frames (avionics comms).
//
// An ADS-B extended squitter (DF17) is 112 bits = 14 bytes: 88 data bits + 24 parity bits.
// Mode S parity: generator polynomial 0x1FFF409 (written 0xFFF409 without the x^24
// term), MSB first, start value 0, no final XOR. A receiver computes the CRC of the 88
// data bits and XORs it with the 24 received parity bits: this "syndrome" is 0 for a
// valid frame (and, in real decoders, also identifies a single flipped bit).
// Frames checked (32):
//   - 4 real frames published in "The 1090 MHz Riddle" (J. Sun, mode-s.org),
//   - 14 synthetic DF17 frames whose parity this program computes (transponder side),
//   - 14 copies of the above with one bit flipped (bad reception) -> must fail.
// Outputs: 1) number of valid frames (expected 18), 2) checksum of all 32 syndromes.
#include "common.h"

#define FRAME_BYTES 14
#define DATA_BYTES  11
#define N_REAL      4
#define N_SYNTH     14
#define N_BAD       14
#define N_FRAMES    (N_REAL + N_SYNTH + N_BAD)
#define GEN         0xFFF409u

static const uint8_t real_frames[N_REAL][FRAME_BYTES] = {
    {0x8D, 0x48, 0x40, 0xD6, 0x20, 0x2C, 0xC3, 0x71, 0xC3, 0x2C, 0xE0, 0x57, 0x60, 0x98},
    {0x8D, 0x40, 0x6B, 0x90, 0x20, 0x15, 0xA6, 0x78, 0xD4, 0xD2, 0x20, 0xAA, 0x4B, 0xDA},
    {0x8D, 0x48, 0x50, 0x20, 0x99, 0x44, 0x09, 0x94, 0x08, 0x38, 0x17, 0x5B, 0x28, 0x4F},
    {0x8D, 0x40, 0x62, 0x1D, 0x58, 0xC3, 0x82, 0xD6, 0x90, 0xC8, 0xAC, 0x28, 0x63, 0xA7},
};

static uint8_t frames[N_FRAMES][FRAME_BYTES];

// CRC-24 (Mode S) of n bytes, bit by bit, MSB first; the result is in the low 24 bits.
static uint32_t crc24(const uint8_t *p, int n)
{
    uint32_t c = 0;
    for (int i = 0; i < n; i++) {
        c ^= (uint32_t)p[i] << 16;
        for (int k = 0; k < 8; k++) {
            if (c & 0x800000u)
                c = (c << 1) ^ GEN;
            else
                c <<= 1;
        }
    }
    return c & 0xFFFFFFu;
}

static uint32_t syndrome(const uint8_t *f)
{
    uint32_t parity = ((uint32_t)f[11] << 16) | ((uint32_t)f[12] << 8) | f[13];
    return crc24(f, DATA_BYTES) ^ parity;
}

int main(void)
{
    uint32_t seed = 0x1090ADB5u;
    int n = 0;

    // Real frames.
    for (int i = 0; i < N_REAL; i++, n++)
        for (int b = 0; b < FRAME_BYTES; b++)
            frames[n][b] = real_frames[i][b];

    // Synthetic valid DF17 frames: header 0x8D, 10 random bytes (ICAO address + message),
    // then the parity computed over the 11 data bytes.
    for (int i = 0; i < N_SYNTH; i++, n++) {
        frames[n][0] = 0x8D;
        for (int b = 1; b < DATA_BYTES; b++)
            frames[n][b] = (uint8_t)xorshift32(&seed);
        uint32_t p = crc24(frames[n], DATA_BYTES);
        frames[n][11] = (uint8_t)(p >> 16);
        frames[n][12] = (uint8_t)(p >> 8);
        frames[n][13] = (uint8_t)p;
    }

    // Corrupted copies: frame i (of the 18 valid ones, cycling) with one bit flipped.
    for (int i = 0; i < N_BAD; i++, n++) {
        int src = i % (N_REAL + N_SYNTH);
        for (int b = 0; b < FRAME_BYTES; b++)
            frames[n][b] = frames[src][b];
        uint32_t pos = xorshift32(&seed) & 127;     // bit 0..127, folded into 0..111
        if (pos >= 112)
            pos -= 112;
        frames[n][pos >> 3] ^= (uint8_t)(0x80u >> (pos & 7));
    }

    // Receiver: check every frame.
    uint32_t valid = 0, cs = 0;
    for (int i = 0; i < N_FRAMES; i++) {
        uint32_t s = syndrome(frames[i]);
        valid += (s == 0);
        cs = mix(cs, s);
    }

    report(valid);
    report(cs);
    return 0;
}
