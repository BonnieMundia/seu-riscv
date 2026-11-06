# Top-level Makefile: shared platform + studies (see docs/platform.md).
#   make sw PROG=x        compile x.c (from studies/$(STUDY)/sw/ or platform/tests/sw/) to ELF + hex
#   make sim PROG=x       build the Verilator SoC simulation and run x
#   make wave PROG=x      same as sim, but also dump tb_soc.vcd
#   make golden           run every workload of $(STUDY), compare with its Python reference,
#                         check the cycle budget, write studies/$(STUDY)/results/golden_runs.json
#   make lockstep [W=x]   cocotb: RTL must match the golden ISS instruction by instruction
#                         (all workloads of $(STUDY) + platform tests); run `make golden` first
#   make gate1            golden + lockstep (the Gate 1 criterion)
#   make ffs              Yosys: list the SoC's flip-flops -> studies/$(STUDY)/targets/ff_list_$(VARIANT).json
#   make targets          check the target descriptor studies/$(STUDY)/targets/soc_$(VARIANT).yaml
#   make fi               build the Verilator fault-injection harness (obj_dir_fi/Vinject)
#   make fi-test          injector + classifier + campaign-planner tests (pytest)
#   make stats-test       tests of the statistics code (pytest)
#   make rates EXP=x      failure rates + Wilson intervals + chi-square for campaign x
#   make smoke            70-run smoke campaign (studies/$(STUDY)/experiments/smoke.yaml)
#   make campaign EXP=x   run studies/$(STUDY)/experiments/x.yaml (> 1,000 runs: add CONFIRM=1)
#   make clean            remove build outputs
#   (check = golden, kept as an alias)
# Choose the study with STUDY=seu|hdc (default seu), the program with PROG=<name> (default hello).

STUDY   ?= seu
PROG    ?= hello
PREFIX  := riscv64-unknown-elf-
CC      := $(PREFIX)gcc
OBJCOPY := $(PREFIX)objcopy
OBJDUMP := $(PREFIX)objdump
RUNTIME := platform/sw/runtime
CFLAGS  := -march=rv32i -mabi=ilp32 -O2 -nostdlib -ffreestanding -Wall -I$(RUNTIME)
LDFLAGS := -T $(RUNTIME)/link.ld -Wl,--no-warn-rwx-segments -lgcc

# Program source: the study's sw/ first, then the platform test programs.
SRC     := $(firstword $(wildcard studies/$(STUDY)/sw/$(PROG).c platform/tests/sw/$(PROG).c))
SWB     := build/$(STUDY)
ELF     := $(SWB)/$(PROG).elf
HEX     := $(SWB)/$(PROG).hex

RTL     := platform/rtl/picorv32/picorv32.v platform/rtl/soc/soc.v
TB      := platform/rtl/soc/tb_soc.v
VFLAGS  := --binary -Wno-fatal --top-module tb_soc -j 0
SIMBIN  := obj_dir/Vtb_soc
MAXCYC  ?= 1000000
PYTHON  ?= $(HOME)/.venv/bin/python
VARIANT ?= h0
TARGETS := studies/$(STUDY)/targets

.PHONY: all sw sim wave golden check lockstep gate1 ffs targets fi fi-test stats-test rates smoke campaign figures synth clean
all: sim

sw: $(HEX)

$(ELF): $(RUNTIME)/crt0.S $(SRC) $(RUNTIME)/common.h $(RUNTIME)/link.ld | $(SWB)
	@test -n "$(SRC)" || { echo "no source for PROG=$(PROG) in studies/$(STUDY)/sw or platform/tests/sw"; exit 1; }
	$(CC) $(CFLAGS) $(RUNTIME)/crt0.S $(SRC) $(LDFLAGS) -o $@
	$(OBJDUMP) -d $@ > $(SWB)/$(PROG).dis

# Word-addressed, one 32-bit little-endian word per entry: loads directly into
# soc.v's ram[] with $readmemh (checked with binutils 2.46, see studies/seu/docs/decisions.md).
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

golden:
	$(PYTHON) platform/tests/check_golden.py --study $(STUDY)

check: golden

# Lockstep list: the study's workloads + the platform test programs.
LOCKSTEP_LIST := $(shell $(PYTHON) platform/tests/list_programs.py --study $(STUDY))
W ?= $(LOCKSTEP_LIST)

lockstep:
	@for w in $(W); do \
	  $(MAKE) -s sw STUDY=$(STUDY) PROG=$$w >/dev/null && \
	  PATH="$(HOME)/.venv/bin:$$PATH" $(MAKE) -s -C platform/tests/cocotb WORKLOAD=$$w STUDY=$(STUDY) \
	    COCOTB_PLUSARGS=+hex=$(CURDIR)/$(SWB)/$$w.hex || exit 1; \
	done

gate1: golden lockstep

# Fault targets (see docs/learning/phase4.md): Yosys flip-flop list, then the descriptor
# check (every flip-flop bit in exactly one unit, or excluded with a reason).
ffs:
	$(PYTHON) platform/synth/list_ffs.py --top soc --out $(TARGETS)/ff_list_$(VARIANT).json $(RTL)

targets:
	$(PYTHON) platform/fi/descriptor.py $(TARGETS)/soc_$(VARIANT).yaml

# Fault-injection harness: the SoC (no testbench) + inject.cpp, every signal reachable
# through VPI by name (--vpi --public-flat-rw). See platform/fi/inject.cpp.
FIBIN := obj_dir_fi/Vinject
fi: $(FIBIN)

$(FIBIN): $(RTL) platform/fi/inject.cpp
	verilator --cc --exe --build -j 0 -Wno-fatal -O3 --vpi --public-flat-rw --top-module soc \
	  -Mdir obj_dir_fi -o Vinject $(RTL) platform/fi/inject.cpp

fi-test: $(FIBIN)
	@for w in $(shell $(PYTHON) platform/tests/list_programs.py --study $(STUDY)); do \
	  $(MAKE) -s sw STUDY=$(STUDY) PROG=$$w >/dev/null || exit 1; done
	$(PYTHON) -m pytest -q platform/fi

# Campaigns: results go to studies/$(STUDY)/results/raw/ (git-ignored); re-running resumes.
smoke: $(FIBIN)
	$(PYTHON) platform/fi/campaign.py studies/$(STUDY)/experiments/smoke.yaml

campaign: $(FIBIN)
	@test -n "$(EXP)" || { echo "usage: make campaign EXP=<name> [CONFIRM=1]"; exit 1; }
	$(PYTHON) platform/fi/campaign.py studies/$(STUDY)/experiments/$(EXP).yaml $(if $(CONFIRM),--confirm)

stats-test:
	$(PYTHON) -m pytest -q platform/stats

rates:
	@test -n "$(EXP)" || { echo "usage: make rates EXP=<name>"; exit 1; }
	$(PYTHON) platform/stats/rates.py studies/$(STUDY)/results/raw/$(EXP).csv

figures synth:
	@echo "make $@: not implemented yet (see docs/platform.md)"; exit 1

clean:
	rm -rf obj_dir obj_dir_trace obj_dir_fi build tb_soc.vcd \
	       platform/tests/cocotb/sim_build platform/tests/cocotb/results.xml
