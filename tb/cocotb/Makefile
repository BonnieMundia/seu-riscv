# cocotb lockstep test (RTL vs golden ISS). Normally run from the top level:
#   make lockstep            (all workloads)     make lockstep W=w1_matmul
# Direct use: make -C tb/cocotb WORKLOAD=w1_matmul COCOTB_PLUSARGS=+hex=<abs path>
SIM                 ?= verilator
TOPLEVEL_LANG       ?= verilog
ROOT                := $(abspath ../..)
VERILOG_SOURCES     := $(ROOT)/rtl/picorv32.v $(ROOT)/rtl/soc.v
COCOTB_TOPLEVEL     := soc
COCOTB_TEST_MODULES := test_lockstep
COMPILE_ARGS        += -Wno-fatal

export WORKLOAD

include $(shell cocotb-config --makefiles)/Makefile.sim
