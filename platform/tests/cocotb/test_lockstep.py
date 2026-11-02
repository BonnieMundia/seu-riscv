"""Lockstep test: the RTL must do exactly what the golden ISS does, instruction by instruction.

Run via `make lockstep STUDY=seu` (all workloads + platform tests) or `make lockstep W=w1_matmul`.

The ISS (platform/model/rv32i_iss.py) runs the ELF first and records three streams:
  - the PC of every executed instruction,
  - every register write (rd, value) to x1..x31,
  - every store (word address, byte strobes, data).
The RTL (soc + PicoRV32) then runs the same program while this test watches, once per
clock cycle on the FALLING edge (mid-cycle, when all signals are settled for the next
rising edge):
  - instruction starts: PicoRV32's launch_next_insn with address next_pc (picorv32.v
    line ~1400, the same condition that sets dbg_insn_addr). Bus fetches are NOT used:
    PicoRV32 prefetches the next sequential instruction during every non-JALR
    instruction (mem_do_prefetch, line ~1573) and discards it after a taken branch, so
    the fetch stream contains instructions that never execute (W2: 6,610 fetches for
    5,913 executed instructions),
  - PicoRV32's register-file write port (cpuregs_write, latched_rd, cpuregs_wrdata),
    exactly the condition picorv32.v uses to write cpuregs on the next rising edge,
  - data stores on the memory bus (mem_valid & mem_ready & mem_wstrb != 0).
The streams must match exactly; on the first difference the test reports where.
Also checked: outputs = Python reference, run ends with DONE, cycle count = golden.
"""

import json
import os
import pathlib
import sys

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, FallingEdge

HERE = pathlib.Path(__file__).resolve()
sys.path[:0] = [str(HERE.parents[2] / "model"), str(HERE.parents[1])]
from programs import build_dir, golden_path, load  # noqa: E402
from rv32i_iss import RV32I  # noqa: E402

MAX_CYCLES = 1_000_000


def byte_mask(wstrb):
    return sum(0xFF << (8 * i) for i in range(4) if wstrb >> i & 1)


def first_diff(a, b):
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            return i
    return min(len(a), len(b)) if len(a) != len(b) else None


@cocotb.test()
async def lockstep(dut):
    name = os.environ["WORKLOAD"]
    study = os.environ.get("STUDY", "seu")
    WORKLOADS, TESTS = load(study)
    elf = build_dir(study) / f"{name}.elf"

    iss = RV32I(str(elf)).run(trace=True)
    assert iss.status == "DONE", f"ISS did not finish: {iss.status} {iss.trap_reason}"

    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    dut.resetn.value = 0
    await ClockCycles(dut.clk, 5)
    dut.resetn.value = 1

    cpu = dut.cpu
    pcs, regwrites, stores, outputs = [], [], [], []
    cycles = 0
    while True:
        await FallingEdge(dut.clk)
        cycles += 1
        if int(cpu.launch_next_insn.value):
            pcs.append(int(cpu.next_pc.value))
        if int(cpu.cpuregs_write.value) and int(cpu.latched_rd.value):
            regwrites.append((int(cpu.latched_rd.value), int(cpu.cpuregs_wrdata.value)))
        if int(dut.mem_valid.value) and int(dut.mem_ready.value):
            addr = int(dut.mem_addr.value)
            wstrb = int(dut.mem_wstrb.value)
            if wstrb:
                stores.append((addr & ~3, wstrb, int(dut.mem_wdata.value) & byte_mask(wstrb)))
        if int(dut.out_valid.value):
            outputs.append(int(dut.out_data.value))
        if int(dut.done.value) or int(dut.trap.value) or cycles >= MAX_CYCLES:
            break

    status = "DONE" if int(dut.done.value) else ("TRAP" if int(dut.trap.value) else "HANG")
    dut._log.info(f"{name}: {status}, {cycles} cycles, {len(iss.pcs)} instructions, "
                  f"{len(regwrites)} register writes, {len(stores)} stores")

    if os.environ.get("LOCKSTEP_DEBUG"):
        for label, a, b in (("pcs", pcs, iss.pcs), ("regwrites", regwrites, iss.regwrites),
                            ("stores", stores, iss.stores)):
            j = first_diff(a, b)
            dut._log.info(f"{label}: RTL {len(a)}, ISS {len(b)}, first diff at {j}")
            if j is not None:
                dut._log.info(f"  RTL [{j-3}:{j+3}] {a[max(0, j-3):j+3]}")
                dut._log.info(f"  ISS [{j-3}:{j+3}] {b[max(0, j-3):j+3]}")

    # 1. PCs. done is a register, so the RTL may start up to 2 more instructions after
    #    the done-port store before the run stops: the ISS stream must be a prefix.
    extra = len(pcs) - len(iss.pcs)
    i = first_diff(pcs[:len(iss.pcs)], iss.pcs)
    assert i is None and 0 <= extra <= 2, (
        f"PC stream differs at instruction {i}: RTL started {pcs[i]:#x} "
        f"but ISS executed {iss.pcs[i]:#x}" if i is not None
        else f"RTL started {len(pcs)} instructions, ISS executed {len(iss.pcs)}")

    # 2. Register writes.
    i = first_diff(regwrites, iss.regwrites)
    assert i is None, (f"register write #{i} differs: RTL {regwrites[i:i+1]} "
                       f"ISS {iss.regwrites[i:i+1]}")

    # 3. Stores (includes the output-port and done-port stores).
    i = first_diff(stores, iss.stores)
    assert i is None, f"store #{i} differs: RTL {stores[i:i+1]} ISS {iss.stores[i:i+1]}"

    # 4. Outputs, status, cycles.
    reference = {**WORKLOADS, **TESTS}[name]()
    assert outputs == iss.outputs == reference, (
        f"outputs differ: RTL {[hex(v) for v in outputs]} ISS {[hex(v) for v in iss.outputs]} "
        f"reference {[hex(v) for v in reference]}")
    assert status == "DONE"
    # Same convention as tb_soc.v: it prints its counter before the non-blocking
    # increment on the edge where it sees done, i.e. one less than the number of
    # edges counted here (which includes that edge).
    tb_cycles = cycles - 1
    if name in WORKLOADS:                     # test programs have no golden cycle count
        golden = json.loads(golden_path(study).read_text())
        assert tb_cycles == golden[name]["cycles"], (
            f"cycles {tb_cycles} != golden {golden[name]['cycles']} (tb_soc.v convention)")
    dut._log.info(f"{name}: LOCKSTEP PASS ({extra} instruction(s) started after done)")
