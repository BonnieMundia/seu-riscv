# Decision log

One line per decision: `YYYY-MM-DD — decision — reason`.

- 2026-10-08 — Core = PicoRV32 upstream commit ef203c2 (docs/picorv32_commit.txt), copied unchanged to rtl/picorv32.v — reproducibility; all changes go in our own files.
- 2026-10-08 — RAM is assumed ECC-protected and is never a fault target; targets = core flip-flops + register file — keeps the study on the core.
- 2026-10-08 — Main study uses single bit flips only (no SET, no multi-bit upsets) — scope.
