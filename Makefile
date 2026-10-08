# seu-riscv top-level Makefile
#   make sw     - compile sw/$(PROG).c to ELF + hex
#   make sim    - build the Verilator simulation and run $(PROG)
#   make wave   - same as sim, but also dump tb_soc.vcd
#   make clean  - remove build outputs
# Choose a program with PROG=<name> (default: hello).

PROG    ?= hello
PREFIX  := riscv64-unknown-elf-
CC      := $(PREFIX)gcc
OBJCOPY := $(PREFIX)objcopy
OBJDUMP := $(PREFIX)objdump
CFLAGS  := -march=rv32i -mabi=ilp32 -O2 -nostdlib -ffreestanding -Wall
LDFLAGS := -T sw/link.ld -Wl,--no-warn-rwx-segments -lgcc

SWB     := sw/build
ELF     := $(SWB)/$(PROG).elf
HEX     := $(SWB)/$(PROG).hex

RTL     := rtl/picorv32.v rtl/soc.v
TB      := tb/tb_soc.v
VFLAGS  := --binary -Wno-fatal --top-module tb_soc -j 0
SIMBIN  := obj_dir/Vtb_soc
MAXCYC  ?= 1000000

.PHONY: all sw sim wave clean
all: sim

sw: $(HEX)

$(ELF): sw/crt0.S sw/$(PROG).c sw/link.ld | $(SWB)
	$(CC) $(CFLAGS) sw/crt0.S sw/$(PROG).c $(LDFLAGS) -o $@
	$(OBJDUMP) -d $@ > $(SWB)/$(PROG).dis

# Word-addressed, one 32-bit little-endian word per entry: loads directly into
# soc.v's ram[] with $readmemh (checked with binutils 2.46, see docs/decisions.md).
$(HEX): $(ELF)
	$(OBJCOPY) -O verilog --verilog-data-width=4 $< $@

$(SWB):
	mkdir -p $@

$(SIMBIN): $(RTL) $(TB)
	verilator $(VFLAGS) $(RTL) $(TB)

sim: $(SIMBIN) $(HEX)
	./$(SIMBIN) +hex=$(HEX) +max_cycles=$(MAXCYC)

wave: $(HEX)
	verilator $(VFLAGS) --trace -Mdir obj_dir_trace $(RTL) $(TB)
	./obj_dir_trace/Vtb_soc +hex=$(HEX) +max_cycles=$(MAXCYC) +vcd

clean:
	rm -rf obj_dir obj_dir_trace $(SWB) tb_soc.vcd
