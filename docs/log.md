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
- Done (later 2026-10-08): CLAUDE.md now asks for trainer/supervisor style; docs/learning/phase1.md written (file-by-file explanation, 6 exercises, sources, viva questions). Remote set to github.com/BonnieMundia/seu-riscv.
- Numbers: hello-world = 44 executed instructions; PicoRV32 README CPI table predicts 141 cycles; waveform shows 48 memory transfers with 1 wait cycle each -> 141 + 48 + ~2 start-up ≈ 191 measured.
- Blockers: push needs GitHub authentication on this Mac (no gh, no SSH key, no credential helper); LibreLane launch command unknown.
- Next: push; Boniface works through phase1.md exercises; Phase 2 workloads W1–W5; papers 1–5.
- Done (2026-10-12): single working copy at ~/Documents/GitHub/seu-riscv (old copy to Trash). Phase 1 exercises 1-2 done + answer key. Phase 2 started: sw/common.h, W1 matmul, Python reference sw/ref/workloads.py, `make check`, docs/learning/phase2.md.
- Numbers: W1 = OUT 36c7bde8, 147,409 cycles (Verilator = Icarus), matches Python reference. Signed-input W1 was 344,337 cycles (rejected).
- Next: W2 quicksort (Claude), W3 CRC-32 (Boniface writes, Claude reviews), W4 attitude filter (Claude), W5 ADS-B CRC-24 (Boniface).
