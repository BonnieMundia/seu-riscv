# platform/ — shared, core-agnostic infrastructure

Used by every study (studies/seu, studies/hdc). Owned by Session SEU; other sessions
request changes via `../seu-riscv-coord/REQUESTS.md`. Design: `docs/platform.md`.

| folder | what | status |
|---|---|---|
| `rtl/picorv32/` | PicoRV32, pinned upstream (never edited), `COPYING` (ISC), `UPSTREAM_COMMIT` | done |
| `rtl/soc/` | `soc.v` (core + 64 KB RAM + output/done ports), `tb_soc.v` | done |
| `sw/runtime/` | `crt0.S`, `link.ld`, `common.h` (report, xorshift32, mix) for all C programs | done |
| `model/` | `rv32i_iss.py`: Python RV32I golden ISS of the SoC | done |
| `tests/` | `check_golden.py` (`make golden`), `cocotb/test_lockstep.py` (`make lockstep`), `sw/` test programs | done |
| `fi/` | injection harness (Verilator/VPI), campaign runner, outcome classifier, descriptors, trace/diff export | to do (G2) |
| `stats/` | Leveugle sample sizes, Wilson intervals, chi-square, two-proportion tests | to do |
| `synth/` | Yosys flip-flop listing → unit groups, LibreLane wrapper | to do |
| `viz/`, `web_export/` | SwiftUI package (one library per study), JSON schemas | to do |
| `requirements.lock` | pinned Python packages (`pip freeze` of `~/.venv`) | done |
