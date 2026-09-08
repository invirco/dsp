provenance: AI-drafted 2026-09-09 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# The 31-band GEQ, and the chip-2 re-layout that pays for it

`defs-v2026.09.08.3` (D24 fingerprint `3d41d5850df3`, 4,985 cells) lands
`Geq[1-31]` for Aux / Main / Grp in the cell master on PW's ruling that a
1/3-octave graphic EQ on every output is the market bar. It touches
`products/` not at all, and it could not have: `defs/products/<p>/dsp.csv`
is generated from the DSP4 node graph in this repo and proposed to the hub
gate. This is that proposal, and this document is the one thing the hub has
to read before landing it, because **it moves addresses rather than adding
them, and it is the first time this contract has done that.**

## What moved

A GEQ node's SPI block is exactly its band count, and the chip-2 allocator
packs blocks end to end with no slack anywhere:

```
   28  C2_AUX_GEQ_01   GEQ       28 words          ->  31 words
   56  C2_AUX_AFB_01   ANTI_FB   starts here       ->  starts at 59
   80  C2_AUX_LIM_01   LIMITER
```

Seventeen GEQ nodes × 3 bands = **+51 words on chip 2**, and every block
above the first GEQ node slides by however much of that precedes it.

| | D24 | D32 |
|---|---:|---:|
| `dsp.csv` rows, landed `.2` | 3,698 | 5,358 |
| `dsp.csv` rows, proposed | **3,737** | **5,409** |
| new rows (GEQ 29–31 + CrossoverSlope) | +39 | +51 |
| rows byte-identical to `.2` | 2,506 | 3,898 |
| **rows whose address moved** | **1,192** | **1,460** |
| of those, on chip 1 | 0 | 0 |
| chip-2 rows in the file | 1,278 | 1,558 |
| `dsp-unmapped.csv` rows | 1,248 → **1,248** | 1,590 → **1,590** |

Chip 1 does not move: not one of its 2,459 (D24) / 3,851 (D32) addressed
cells changes. On chip 2 the first casualty is `Aux001AntiFbOn001` at 56,
which becomes 59, and everything above it to 0x07CF follows. 195 of chip
2's 235 graph nodes take a new base.

`rows(dsp.csv) + rows(dsp-unmapped.csv) == cells(_matrix.csv)` holds on
both products at the new counts: 3,737 + 1,248 = 4,985 and
5,409 + 1,590 = 6,999.

**The unmapped count did not rise and did not fall.** The 39 D24 / 51 D32
cells `.3` added are all newly *addressed*, so they never appear in the
unmapped file; every one of the 1,248 / 1,590 remaining is a cell the DSP
does not own, unchanged class for class from `.2` (`mcu-only`,
`no-graph-node`, `control-plane`, `host-managed`, `surface-state`,
`hardware-control`, `label`, `unbacked-meter`, `s1-2-no-behaviour`). The
`geq-band-beyond-block` class that `.3` created is now **empty**, which is
the point of the proposal.

## What every host must do about it

Any cached chip-2 address is wrong. The panel MCU headers (H1S3/H1S4) and
the app must be rebuilt against whatever tag the hub lands this as; a host
running `.2`'s map against a `.4` image writes an aux limiter threshold
into an anti-feedback notch. There is no compatibility shim and there
should not be one — the two maps are told apart by the contract version,
not by inspection.

## `CrossoverSlope` came with it

Because the crossover node moves anyway, the slope's own word lands in the
same proposal rather than at the fixed `0x0576` the 09-08 analysis
proposed. `C2_MAIN_XOVER` was at 1397; it is now at 1436, so:

| cell | `.2` | proposed |
|---|---|---|
| `Main*001CrossoverFreq001` (×4) | 1397 / 0x0575 | 1436 / **0x059C** |
| `Main*001CrossoverSlope001` (×4) | 1397 / 0x0575 | 1437 / **0x059D** |

Still ONE word for all four sections, for the reason in
`dsp4-dspcsv-proposal-20260908.md` §A: one crossover node, one LP/HP
split, one order. The word it takes was `_xover_coeffs_next[1]`, which no
host writes and which the design overwrites in full on every redesign.

## The cost, which is the real gate

Three more biquad stages per GEQ node, on seventeen nodes, running
unconditionally every block — on a chip whose margin with the FX reverb
running was measured at 5.98 % on 2026-09-08. The measurement against the
28-band image is in this session's status line and in
`dsp4-fx-afb-20260908.md` §0's terms; **that number, not this table, is
what says whether the 31-band product ships as configured.**
