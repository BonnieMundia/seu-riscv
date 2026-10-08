# Weekly log

Format per entry: done · numbers · blockers · next.

## Week 0 (to 2026-10-11)
- Done: toolchain installed (steps 1–8); repo created with folder layout, CLAUDE.md, environment.md, decision log.
- Numbers: —
- Blockers: LibreLane install not found on this machine; no waveform viewer installed.
- Next: Phase 1 hello-world SoC on Verilator.

## Week 1 (2026-10-12 – 2026-10-16) — started early, 2026-10-08
- Done: Phase 1 hello-world SoC. rtl/soc.v (PicoRV32 RV32I + 64 KB RAM + out/done ports), tb/tb_soc.v, sw/ (crt0.S, link.ld, hello.c), Makefile (`make sw`, `make sim`, `make wave`, `make clean`).
- Numbers: hello-world prints OUT 00c0ffee, DONE cycles=191 (Verilator 5.052); Icarus 13.0 gives the identical result (191 cycles). Hang path (+max_cycles=100) and trap path (ebreak, TRAP cycles=7) both checked.
- Blockers: none for Phase 1. LibreLane install still not found; no waveform viewer installed.
- Next: push to GitHub; Phase 2 workloads W1–W5; papers 1–5.
