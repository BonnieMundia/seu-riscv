"""Golden model: a Python RV32I instruction-set simulator (ISS) of our SoC.

It runs the same ELF as the RTL and records, per executed instruction, what the CPU must
do: the PC, register writes and memory stores. tb/test_lockstep.py (cocotb) compares the
RTL against this, instruction by instruction.

What it copies from the hardware (rtl/soc.v + PicoRV32 parameters in docs/decisions.md):
  - reset: pc = 0 (PROGADDR_RESET), x2 = 0x10000 (STACKADDR), other registers 0
    (the RTL leaves them undefined; crt0.S zeroes them before they are read);
  - memory: 64 KB RAM at 0; reads elsewhere return 0; stores elsewhere are ignored;
    0x1000_0000 = output port, 0x1000_0004 = done port (run ends after that store);
  - traps (CATCH_ILLINSN=1, CATCH_MISALIGN=1): ECALL, EBREAK, illegal instructions,
    misaligned loads/stores and jumps to a misaligned address stop the run with TRAP.
Not modelled (no workload uses them; raises NotImplementedError so it can't go unnoticed):
FENCE and the RDCYCLE/RDTIME/RDINSTRET counter instructions.

Usage:  python model/rv32i_iss.py sw/build/w1_matmul.elf
"""

import sys
from dataclasses import dataclass, field

from elftools.elf.elffile import ELFFile

M32 = 0xFFFF_FFFF
RAM_SIZE = 0x1_0000
OUT_ADDR = 0x1000_0000
DONE_ADDR = 0x1000_0004
RESET_PC = 0x0000_0000
STACKADDR = 0x0001_0000


def sext(value, bits):
    """Sign-extend the low `bits` bits of value to a Python int."""
    value &= (1 << bits) - 1
    return value - (1 << bits) if value >> (bits - 1) else value


def signed(v):
    return v - (1 << 32) if v & 0x8000_0000 else v


@dataclass
class Result:
    status: str                      # DONE | TRAP | HANG
    outputs: list                    # values written to the output port, in order
    instret: int                     # instructions executed (retired)
    trap_reason: str = ""
    pcs: list = field(default_factory=list)       # PC of every executed instruction
    regwrites: list = field(default_factory=list)  # (rd, value) for every write to x1..x31
    stores: list = field(default_factory=list)     # (word_addr, wstrb, data) every store


class RV32I:
    def __init__(self, elf_path):
        self.ram = bytearray(RAM_SIZE)
        with open(elf_path, "rb") as f:
            for seg in ELFFile(f).iter_segments():
                if seg["p_type"] != "PT_LOAD" or seg["p_filesz"] == 0:
                    continue
                addr, data = seg["p_paddr"], seg.data()
                if addr + len(data) > RAM_SIZE:
                    raise ValueError(f"segment at {addr:#x} does not fit in RAM")
                self.ram[addr:addr + len(data)] = data
        self.x = [0] * 32
        self.x[2] = STACKADDR
        self.pc = RESET_PC

    # ---- memory -------------------------------------------------------------------
    def load(self, addr, size):
        if addr % size:
            raise _Trap(f"misaligned load at {addr:#x}")
        if addr + size <= RAM_SIZE:
            return int.from_bytes(self.ram[addr:addr + size], "little")
        return 0                                   # unmapped (incl. ports): reads 0

    def store(self, addr, size, value, res):
        if addr % size:
            raise _Trap(f"misaligned store at {addr:#x}")
        value &= (1 << (8 * size)) - 1
        lane = addr & 3
        wstrb = ((1 << size) - 1) << lane
        res.stores.append((addr & ~3, wstrb, (value << (8 * lane)) & M32))
        if addr + size <= RAM_SIZE:
            self.ram[addr:addr + size] = value.to_bytes(size, "little")
        elif addr & ~3 == OUT_ADDR:
            res.outputs.append(value << (8 * lane) & M32)
        elif addr & ~3 == DONE_ADDR:
            return True                            # done port: end of run
        return False

    # ---- run ----------------------------------------------------------------------
    def run(self, max_instr=2_000_000, trace=False):
        res = Result(status="HANG", outputs=[], instret=0)
        if trace:
            # PicoRV32 loads STACKADDR into x2 through its normal register write port
            # right after reset, before the first instruction: log it as write #0.
            res.regwrites.append((2, STACKADDR))
        try:
            while res.instret < max_instr:
                if trace:
                    res.pcs.append(self.pc)
                done = self.step(res, trace)
                res.instret += 1
                if done:
                    res.status = "DONE"
                    break
        except _Trap as t:
            res.status, res.trap_reason = "TRAP", str(t)
        return res

    def write_rd(self, rd, value, res, trace):
        if rd:
            self.x[rd] = value & M32
            if trace:
                res.regwrites.append((rd, value & M32))

    def step(self, res, trace):
        pc, x = self.pc, self.x
        if pc % 4:
            raise _Trap(f"misaligned PC {pc:#x}")
        insn = self.load(pc, 4) if pc + 4 <= RAM_SIZE else 0
        op = insn & 0x7F
        rd = (insn >> 7) & 0x1F
        f3 = (insn >> 12) & 0x7
        rs1 = x[(insn >> 15) & 0x1F]
        rs2 = x[(insn >> 20) & 0x1F]
        f7 = insn >> 25
        imm_i = sext(insn >> 20, 12)
        imm_s = sext(((insn >> 25) << 5) | ((insn >> 7) & 0x1F), 12)
        imm_b = sext((((insn >> 31) & 1) << 12) | (((insn >> 7) & 1) << 11)
                     | (((insn >> 25) & 0x3F) << 5) | (((insn >> 8) & 0xF) << 1), 13)
        imm_u = insn & 0xFFFF_F000
        imm_j = sext((((insn >> 31) & 1) << 20) | (((insn >> 12) & 0xFF) << 12)
                     | (((insn >> 20) & 1) << 11) | (((insn >> 21) & 0x3FF) << 1), 21)
        next_pc = (pc + 4) & M32
        done = False

        if op == 0x37:                                         # LUI
            self.write_rd(rd, imm_u, res, trace)
        elif op == 0x17:                                       # AUIPC
            self.write_rd(rd, pc + imm_u, res, trace)
        elif op == 0x6F:                                       # JAL
            next_pc = (pc + imm_j) & M32
            self._check_target(next_pc)
            self.write_rd(rd, pc + 4, res, trace)
        elif op == 0x67 and f3 == 0:                           # JALR
            next_pc = (rs1 + imm_i) & M32 & ~1
            self._check_target(next_pc)
            self.write_rd(rd, pc + 4, res, trace)
        elif op == 0x63:                                       # branches
            taken = {0: rs1 == rs2, 1: rs1 != rs2,
                     4: signed(rs1) < signed(rs2), 5: signed(rs1) >= signed(rs2),
                     6: rs1 < rs2, 7: rs1 >= rs2}.get(f3)
            if taken is None:
                raise _Trap(f"illegal branch {insn:#010x} at {pc:#x}")
            if taken:
                next_pc = (pc + imm_b) & M32
                self._check_target(next_pc)
        elif op == 0x03:                                       # loads
            addr = (rs1 + imm_i) & M32
            if f3 == 0:
                v = sext(self.load(addr, 1), 8)
            elif f3 == 1:
                v = sext(self.load(addr, 2), 16)
            elif f3 == 2:
                v = self.load(addr, 4)
            elif f3 == 4:
                v = self.load(addr, 1)
            elif f3 == 5:
                v = self.load(addr, 2)
            else:
                raise _Trap(f"illegal load {insn:#010x} at {pc:#x}")
            self.write_rd(rd, v, res, trace)
        elif op == 0x23:                                       # stores
            size = {0: 1, 1: 2, 2: 4}.get(f3)
            if size is None:
                raise _Trap(f"illegal store {insn:#010x} at {pc:#x}")
            done = self.store((rs1 + imm_s) & M32, size, rs2, res)
        elif op == 0x13:                                       # ALU immediate
            shamt = (insn >> 20) & 0x1F
            if f3 == 0:
                v = rs1 + imm_i
            elif f3 == 2:
                v = int(signed(rs1) < imm_i)
            elif f3 == 3:
                v = int(rs1 < (imm_i & M32))
            elif f3 == 4:
                v = rs1 ^ (imm_i & M32)
            elif f3 == 6:
                v = rs1 | (imm_i & M32)
            elif f3 == 7:
                v = rs1 & (imm_i & M32)
            elif f3 == 1 and f7 == 0:
                v = rs1 << shamt
            elif f3 == 5 and f7 == 0:
                v = rs1 >> shamt
            elif f3 == 5 and f7 == 0x20:
                v = signed(rs1) >> shamt
            else:
                raise _Trap(f"illegal ALU-imm {insn:#010x} at {pc:#x}")
            self.write_rd(rd, v, res, trace)
        elif op == 0x33:                                       # ALU register
            sh = rs2 & 0x1F
            v = {(0, 0): lambda: rs1 + rs2, (0, 0x20): lambda: rs1 - rs2,
                 (1, 0): lambda: rs1 << sh,
                 (2, 0): lambda: int(signed(rs1) < signed(rs2)),
                 (3, 0): lambda: int(rs1 < rs2), (4, 0): lambda: rs1 ^ rs2,
                 (5, 0): lambda: rs1 >> sh, (5, 0x20): lambda: signed(rs1) >> sh,
                 (6, 0): lambda: rs1 | rs2, (7, 0): lambda: rs1 & rs2}.get((f3, f7))
            if v is None:                                      # incl. M extension (f7=1)
                raise _Trap(f"illegal ALU-reg {insn:#010x} at {pc:#x}")
            self.write_rd(rd, v(), res, trace)
        elif op == 0x73 and insn in (0x0000_0073, 0x0010_0073):
            raise _Trap(("ECALL" if insn == 0x73 else "EBREAK") + f" at {pc:#x}")
        elif op in (0x0F, 0x73):
            raise NotImplementedError(f"FENCE/CSR {insn:#010x} at {pc:#x} not modelled")
        else:
            raise _Trap(f"illegal instruction {insn:#010x} at {pc:#x}")

        self.pc = next_pc
        return done

    @staticmethod
    def _check_target(target):
        if target % 4:                                         # COMPRESSED_ISA=0
            raise _Trap(f"misaligned jump target {target:#x}")


class _Trap(Exception):
    pass


def main():
    res = RV32I(sys.argv[1]).run()
    for v in res.outputs:
        print(f"OUT {v:08x}")
    print(f"{res.status} instret={res.instret}" + (f" ({res.trap_reason})" if res.trap_reason else ""))


if __name__ == "__main__":
    main()
