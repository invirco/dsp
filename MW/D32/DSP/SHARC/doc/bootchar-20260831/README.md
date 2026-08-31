# Per-cycle boot+config data, 2026-08-31 (session 15)

Raw output of `tools/pi/dsp4_bootchar.py` — one boot attempt per cycle, no
retry ladder, every cycle recorded pass or fail. Score with
`tools/pi/dsp4_bootstats.py`; the analysis is
`MW/D32/DSP/dsp4-boot-handshake-20260830.md` (session 15 addendum).

Same two-strip, self-test-free image and timings as the 2026-08-30 arms,
product `d24`, chip 1 configured — but on the tree that SHIPS
`DSP4_SPI_PARTIAL_FIX2` (default-on) and reads the link through the
phase-calibrating `DiagLink` (D74). The probe's register list is wider
than the 2026-08-30 arms', which is why this lives in its own file: the
column sets are not compatible and `dsp4_bootchar.py` refuses to mix them.

| file | tag | n | result |
|---|---|---|---|
| `bootchar_s15fix2.csv` | `s15fix2` | 150 | **149/150 clean on one attempt (99.3%), failure rate 0.67% [0.12%, 3.68%] Wilson 95%.** 0 D71-class events — `SPI_RX_COUNT` read the full 112 on every one of the 149 cycles that answered. The single failure is cycle 105, `WEDGE_LINK`: chip 1 booted in 496.2 ms, answered `MAGIC`/`CHIP_ID`/`BOOT_STAGE 5`/`FRAME_COUNT` cleanly before config, took all 51 config writes — and then never answered again, while chip 2 ran on with `FRAME_COUNT` 30,130 → 48,565 → 138,932. That is D73's signature exactly, at D73's rate. |

**What makes this D73 event worth more than the earlier ones**: it was
taken through the phase-calibrating reader. `probe()` calls
`DiagLink.resync()`, which now tries BOTH answer arrangements over eight
realign rounds of twenty-four collects each, and `MAGIC` still never came
back. The reader can no longer manufacture this symptom out of a
word-offset (D74), so this instance is a chip that genuinely stopped
answering — one event, which is evidence and not proof, but it is the
first D73 sighting the instrument cannot be blamed for.
