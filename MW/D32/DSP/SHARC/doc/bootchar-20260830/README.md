# Per-cycle boot+config data, 2026-08-30 (session 13)

Raw output of `tools/pi/dsp4_bootchar.py` — one boot attempt per cycle, no
retry ladder, every cycle recorded pass or fail. Score with
`tools/pi/dsp4_bootstats.py`; the analysis is
`MW/D32/DSP/dsp4-boot-handshake-20260830.md`.

All arms are the same two-strip, self-test-free image at 983.04 MHz, same
settle timings, product `d24`, chip 1 configured.

| file | tag | n | image | failures |
|---|---|---|---|---|
| `bootchar.csv` | base | 32 | no diagnostic flags | 1 × WEDGE_STAGE0 |
| `bootchar_watch48.csv` | watch | 48 | `DSP4_CFG_WATCH=1` | none |
| `bootchar_watch.csv` | watch250 | 22 | `DSP4_CFG_WATCH=1` | 1 × WEDGE_STAGE5 |
| `bootchar_pfix0.csv` | pfix0 | 24 | `DSP4_CFG_WATCH=1`, `SPI_PART_FIX` published | 1 × WEDGE_STAGE5 |
| `bootchar_nowatch.csv` | nowatch | 10 | no diagnostic flags | 1 × WEDGE_STAGE0 |
| `bootchar_fix2.csv` | fix2 | 150 | `DSP4_CFG_WATCH=1` **+ `DSP4_SPI_PARTIAL_FIX2=1`** | 1 × WEDGE_LINK |

Unfixed = the first five, 132/136 clean, 2.94 % [1.15, 7.32].
Fixed = the last, 149/150 clean, 0.67 % [0.12, 3.68], and its one failure
is the stopped-core mode (D73) that the fix does not address.

Two arms carry a scar worth knowing about. `nowatch` was run with
`--tag fix2` on an image that did not carry the flags being tested —
caught because its `CFG_PHASE` and `CGU_IT*` columns read 0 — and is
split out here under its own tag rather than discarded, because unflagged
one-attempt cycles are still perfectly good unfixed data. `watch` and
`watch250` were originally appended to `bootchar.csv` under a header six
columns too narrow; the rows are recovered here against the correct
header, and `dsp4_bootchar.py` now refuses such an append.
