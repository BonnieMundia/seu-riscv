# crt0.S - startup code. The CPU starts executing here (address 0) after reset.
    .section .text.start
    .globl _start
_start:
    # Zero all registers except sp, so every run starts from the same known state
    # (PicoRV32 does not reset its register file; the golden model will assume zeros).
    li x1, 0
    li x3, 0
    li x4, 0
    li x5, 0
    li x6, 0
    li x7, 0
    li x8, 0
    li x9, 0
    li x10, 0
    li x11, 0
    li x12, 0
    li x13, 0
    li x14, 0
    li x15, 0
    li x16, 0
    li x17, 0
    li x18, 0
    li x19, 0
    li x20, 0
    li x21, 0
    li x22, 0
    li x23, 0
    li x24, 0
    li x25, 0
    li x26, 0
    li x27, 0
    li x28, 0
    li x29, 0
    li x30, 0
    li x31, 0

    li sp, 0x10000          # stack grows down from the top of the 64 KB RAM

    # Clear .bss (zero-initialised globals)
    la t0, __bss_start
    la t1, __bss_end
1:  bgeu t0, t1, 2f
    sw zero, 0(t0)
    addi t0, t0, 4
    j 1b
2:
    call main

    # Tell the testbench we are finished: any write to the done port ends the run.
    li t0, 0x10000004
    sw a0, 0(t0)
3:  j 3b                    # loop forever (simulation stops on the done write)
