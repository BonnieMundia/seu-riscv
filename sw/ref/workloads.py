"""Independent Python references for the workloads (W1-W5).

Each function recomputes, in plain Python, the checksum its C workload should report.
No CPU, compiler or simulator is involved, so a match means the C program AND the
hardware produced the right answer. These values are what `make check` compares against.

Python ints never overflow, so every step that would wrap in 32-bit C is masked with
`& M32` to copy that behaviour exactly.
"""

M32 = 0xFFFF_FFFF


def xorshift32(state):
    """Same generator as common.h. Returns (value, new_state)."""
    x = state
    x ^= (x << 13) & M32
    x ^= x >> 17
    x ^= (x << 5) & M32
    return x, x


def mix(cs, v):
    """Same checksum step as common.h: rotate left 5, then XOR."""
    return (((cs << 5) | (cs >> 27)) & M32) ^ (v & M32)


def w1_matmul():
    n = 8
    seed = 0x1234567
    a = [[0] * n for _ in range(n)]
    b = [[0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            v, seed = xorshift32(seed)
            a[i][j] = v & 0xFF
    for i in range(n):
        for j in range(n):
            v, seed = xorshift32(seed)
            b[i][j] = v & 0xFF
    cs = 0
    for i in range(n):
        for j in range(n):
            c = sum(a[i][k] * b[k][j] for k in range(n))
            cs = mix(cs, c)
    return [cs]


def to_signed32(v):
    return v - (1 << 32) if v & 0x8000_0000 else v


def w2_qsort():
    # Any correct sort gives the same result, so Python's sorted() is an independent
    # reference for the C quicksort.
    seed = 0x51ED5EED
    a = []
    for _ in range(64):
        v, seed = xorshift32(seed)
        a.append(to_signed32(v))
    cs = 0
    for v in sorted(a):
        cs = mix(cs, v & M32)
    return [cs]


def w3_crc32():
    # zlib.crc32 is CRC-32/ISO-HDLC, the same CRC as the C code, implemented independently.
    import zlib
    seed = 0x0BADF00D
    buf = bytearray()
    for _ in range(1024 // 4):
        v, seed = xorshift32(seed)
        buf += v.to_bytes(4, "little")
    return [zlib.crc32(b"123456789"), zlib.crc32(bytes(buf))]


def w4_attitude(trace=None):
    # Line-by-line mirror of w4_attitude.c. Python's >> on negative ints is an arithmetic
    # shift (rounds toward minus infinity), the same as GCC's >> on int32_t (sra).
    # Values stay far below 2^31, so no 32-bit wrap-around ever happens (asserted).
    def field(w, lo, bits):
        return ((w >> lo) & ((1 << bits) - 1)) - (1 << (bits - 1))

    def sat(v, lim):
        return max(-lim, min(lim, v))

    bias = [655, -983, 1311]
    rate, truth, est, u = [0] * 3, [0] * 3, [0] * 3, [0] * 3
    seed, cs = 0xA77170DE, 0
    for _ in range(200):
        step_sum = 0
        for ax in range(3):
            w, seed = xorshift32(seed)
            rate[ax] = sat(rate[ax] + (u[ax] >> 4) + field(w, 0, 12), 1 << 16)
            truth[ax] += rate[ax] >> 6
            gyro = rate[ax] + bias[ax] + field(w, 12, 10)
            est[ax] += gyro >> 6
            if ax < 2:
                acc = truth[ax] + field(w, 22, 10)
                est[ax] += (acc - est[ax]) >> 5
            u[ax] = sat(-(est[ax] + (est[ax] >> 1)) - (gyro >> 2), 1 << 15)
            assert all(abs(x) < 2**31 for x in (rate[ax], truth[ax], est[ax], gyro))
            step_sum = (step_sum + ((est[ax] ^ u[ax]) & M32)) & M32
        cs = mix(cs, step_sum)
        if trace is not None:
            trace.append((list(truth), list(est)))
    return [cs]


MODE_S_GEN = 0x1FFF409  # Mode S generator polynomial, incl. the x^24 term


def mode_s_remainder(frame):
    """Remainder of the whole 112-bit frame divided by the Mode S generator, by big-integer
    long division (a different method from the C shift register). 0 = valid frame."""
    n = int.from_bytes(frame, "big")
    for i in range(len(frame) * 8 - 1, 23, -1):
        if n >> i & 1:
            n ^= MODE_S_GEN << (i - 24)
    return n


def w5_adsb_crc24():
    real = [bytes.fromhex(h) for h in (
        "8D4840D6202CC371C32CE0576098", "8D406B902015A678D4D220AA4BDA",
        "8D485020994409940838175B284F", "8D40621D58C382D690C8AC2863A7")]
    seed = 0x1090ADB5
    frames = list(real)
    for _ in range(14):
        data = bytearray([0x8D])
        for _ in range(10):
            v, seed = xorshift32(seed)
            data.append(v & 0xFF)
        parity = mode_s_remainder(bytes(data) + b"\0\0\0")   # = data * x^24 mod G
        frames.append(bytes(data) + parity.to_bytes(3, "big"))
    for i in range(14):
        f = bytearray(frames[i % 18])
        v, seed = xorshift32(seed)
        pos = v & 127
        if pos >= 112:
            pos -= 112
        f[pos >> 3] ^= 0x80 >> (pos & 7)
        frames.append(bytes(f))
    syndromes = [mode_s_remainder(f) for f in frames]
    cs = 0
    for s in syndromes:
        cs = mix(cs, s)
    return [sum(s == 0 for s in syndromes), cs]


# Workload name (= sw/<name>.c) -> function returning the expected OUT values, in order.
WORKLOADS = {
    "w1_matmul": w1_matmul,
    "w2_qsort": w2_qsort,
    "w3_crc32": w3_crc32,
    "w4_attitude": w4_attitude,
    "w5_adsb_crc24": w5_adsb_crc24,
}

def isa_test():
    # Hand-computed expected values for sw/isa_test.c (see the comments there).
    return [1, 0, 0x8000_0000, 0xF800_0000, 0x2345_6780,
            1, 0x1234, 0xFFFF_FFFF,
            1, 0,
            0xFFFF_FFFF, 0xFFFF_FF80, 0xFFFF_FFFE, 0x0000_7FF0,
            0, 0x1000]


# Test programs: checked by `make lockstep` (outputs + RTL-vs-ISS), but they are not
# workloads (no cycle budget, not in golden_runs.json, never fault-injected).
TESTS = {
    "isa_test": isa_test,
}

if __name__ == "__main__":
    for name, fn in WORKLOADS.items():
        print(name, " ".join(f"{v:08x}" for v in fn()))
