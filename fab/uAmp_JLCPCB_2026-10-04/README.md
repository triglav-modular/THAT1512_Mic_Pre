# µAmp rev 3 — JLCPCB bare-board package

Generated 2026-10-04 from `uAmp.kicad_pcb` as saved 2026-10-04 09:58:05
(sha256 `7fce3061e375…`), KiCad 10.0.6, `kicad-cli`. Bare boards only: no BOM,
no placement file.

## Contents

| File | Purpose |
|---|---|
| `uAmp-gerbers.zip` | **upload this**: 9 gerbers, the job file and the drill file |
| `gerbers/` | the same files unzipped, plus the drill map PDF |

## Order parameters

| | |
|---|---|
| Dimensions | 45.00 × 24.03 mm, rounded corners |
| Layers | 2 |
| Thickness | 1.6 mm |
| Material | FR4 |
| Surface finish | HASL or ENIG, no constraint from this design |
| Min track / space | 0.50 / 0.25 mm |
| Vias | none |
| Copper to board edge | 0.20 mm or more |
| Holes | 47, all plated: 6 × 0.7, 3 × 0.714, 28 × 0.8, 7 × 1.0, 2 × 1.2, 1 × 3.2 mm (M3) |
| Order number | no marker on the board (the owner removed it 2026-10-04) |

## Verification performed

- DRC on the saved board: 0 errors, 0 unconnected, 11 warnings (10 library
  differences, 1 missing footprint library for RV1). One schematic-parity
  warning: U1's Value field.
- The saved zone fill equals a fresh fill (the owner refilled and saved;
  1210 mm² of GND pour over both layers).
- The project's copper-to-edge rule is 0.075 mm. DRC on a copy with the rule
  raised to 0.20 mm (JLCPCB's routed-edge minimum) and the zones refilled
  reports nothing.
- Read back from the files in this folder: the drill file's six tools and 47
  hits equal the board's pad holes; the outline is 45.000 × 24.030 mm; no
  coordinate on any layer lies outside it; the job file and the copper headers
  say 2 layers; the zip holds the same bytes as `gerbers/`.
- Silk gerbers are exported with the mask openings subtracted
  (`--subtract-soldermask`).
- Front and mirrored back plotted with the same options and looked at: the
  "µAmp Mic Pre" knockout plots with its µ; "TRIGLAV MODULAR" on the back reads
  the right way round.

## Not checked

- JLCPCB's own gerber preview. Look at it before paying.
- Silk text is 0.8 to 0.9 mm high; JLCPCB asks for 1.0 mm.
