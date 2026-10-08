# Environment

Recorded 2026-10-08.

```
Verilator 5.052 2026-09-05 rev vUNKNOWN-built20260905
Icarus Verilog version 13.0 (stable) (v13_0)
Yosys 0.69+post (git sha1 143eb14f9cc55d6f8927e68523b0c9d2166ed02c, Release, AppleClang clang++ 21.0.0.21000334)
riscv64-unknown-elf-gcc (g6afcc4f6d) 16.1.0
GNU objcopy (GNU Binutils) 2.46
cocotb 2.1.0
Python 3.9.6 (venv at ~/.venv)
macOS 27.0.1 (26A434)
Chip: Apple M5, 10 cores
PicoRV32 upstream commit: ef203c2b0a3fb793280f5114941416c425c5b461
```

## Not found on 2026-10-08 (to fix)
- LibreLane: not on PATH, not in /nix/store, not under ~. Nix itself is installed at
  /nix/var/nix/profiles/default/bin but not on the default shell PATH. Version: TBD.
- Waveform viewer (GTKWave / Surfer): not found. Needed only for debugging.
- Python venv uses Python 3.9.6 (macOS system Python). Works today; consider 3.11+ later.
