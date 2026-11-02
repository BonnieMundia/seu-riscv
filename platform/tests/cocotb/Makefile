# cocotb lockstep test (RTL vs golden ISS). Normally run from the top level:
#   make lockstep STUDY=seu        make lockstep W=w1_matmul
# Direct use: make -C platform/tests/cocotb WORKLOAD=w1_matmul STUDY=seu COCOTB_PLUSARGS=+hex=<abs path>
SIM                 ?= verilator
TOPLEVEL_LANG       ?= verilog
ROOT                := $(abspath ../../..)
VERILOG_SOURCES     := $(ROOT)/platform/rtl/picorv32/picorv32.v $(ROOT)/platform/rtl/soc/soc.v
COCOTB_TOPLEVEL     := soc
COCOTB_TEST_MODULES := test_lockstep
COMPILE_ARGS        += -Wno-fatal

export WORKLOAD
export STUDY

include $(shell cocotb-config --makefiles)/Makefile.sim
