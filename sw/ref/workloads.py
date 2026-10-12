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


# Workload name (= sw/<name>.c) -> function returning the expected OUT values, in order.
WORKLOADS = {
    "w1_matmul": w1_matmul,
}

if __name__ == "__main__":
    for name, fn in WORKLOADS.items():
        print(name, " ".join(f"{v:08x}" for v in fn()))
