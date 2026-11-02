"""Expected outputs of the platform test programs (platform/tests/sw/<name>.c).

Test programs are checked by `make lockstep` (outputs + RTL-vs-ISS) for every study,
but they are not workloads: no cycle budget, no golden_runs.json entry, never injected.
"""


def hello():
    return [0x00C0FFEE]


def isa_test():
    # Hand-computed expected values for isa_test.c (see the comments there).
    return [1, 0, 0x8000_0000, 0xF800_0000, 0x2345_6780,
            1, 0x1234, 0xFFFF_FFFF,
            1, 0,
            0xFFFF_FFFF, 0xFFFF_FF80, 0xFFFF_FFFE, 0x0000_7FF0,
            0, 0x1000]


TESTS = {
    "hello": hello,
    "isa_test": isa_test,
}
