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
- LibreLane: NOT installed (re-checked 2026-10-08). Shell history shows
  `python3 -m pip install --upgrade librelane`, but no Python has the package: Homebrew
  Python 3.14 is EXTERNALLY-MANAGED (PEP 668), so a global pip install is refused. The Nix
  store (71 entries) has no LibreLane, OpenROAD, Magic or KLayout; only the nixpkgs recipe
  (pkgs/by-name/li/librelane). Nix is at /nix/var/nix/profiles/default/bin (not on PATH).
  Needed by Gate 3 (18 Dec). Version: TBD.
- Waveform viewer (GTKWave / Surfer): not found. Needed only for debugging.
- Python venv uses Python 3.9.6 (macOS system Python). Works today; consider 3.11+ later.
