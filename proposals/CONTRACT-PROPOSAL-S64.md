provenance: AI-drafted 2026-09-16 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# Contract proposal S64 — the RTA: `RtaOn` armed, `RtaSrc` retired, 64 cells proposed (Mode, PeakReset, 62 band meters)

**Status: PROPOSED, not landed.** Nothing here writes a def, a master row or a
`_matrix.csv` row. The DSP side exists behind `DSP4_RTA` (default 0 in
`shipping.config`) and is reached through diag registers `0xE0C0..0xE0C7` until
the hub lands cells. Evidence: `findings.md` S64-1..4.

**Read S64-3 before landing anything.** As specified (31 bands × 3 biquads × 2
channels at the full rate) the filterbank costs chip 2 **+10.5 %** and **does not
fit the D24** on the current image (96.6 % → 107.2 %, 820 missed blocks in 4 s).
The cells below are the same whichever engine produces the numbers, so they can
land. The engine choice is PW's.

## 1. Existing master rows

| master row | today | proposal |
|---|---|---|
| `Rta[1-1]On[1-1]` (row 250, 2 states) | no reader | **keep**. rw, 0/1. Arms the filterbank. With 0 the kernel returns after one compare. |
| `Rta[1-1]Src[1-1]` (row 251, "main/aux/cue", 8 states) | no reader | **retire** (PW 2026-09-16: the only source is the cue bus). Nothing reads it and nothing should. |

## 2. New cells

| proposed cell | access | range / law | chip | DSP symbol |
|---|---|---|---|---|
| `Rta[1-1]Mode[1-1]` | rw | 0 fast (τ 35 ms), 1 slow (τ 125 ms), 2 peak-hold; anything else reads as 0 | 2 | `_rta_mode` |
| `Rta[1-1]PeakReset[1-1]` | w (reads 0) | any non-zero restarts the peak hold; the DSP consumes it within one block (333 µs) | 2 | `_rta_reset` |
| `Rta[1-1]MtrL[1-31]` | ro | band n of cue L: **dBFS = 10·log10(w)**, w = the IEEE float32 word, the band's mean square in full-scale units after ballistics (a −20 dBFS-peak sine centred in the band reads −23.01, the TEST_MEAS `RmsResult` law) | 2 | `_rta_out[n-1]` |
| `Rta[1-1]MtrR[1-31]` | ro | the same, cue R | 2 | `_rta_out[30+n]` |

Band n centres: 1000·10^((n−18)/10) Hz, n = 1..31, labelled 20, 25, 31.5 … 16k, 20k.
A word of 0.0 is −∞ (the source is exactly silent).

**Addresses (proposed, chip 2):** chip 2's dispatch table ends at `0x087E`
(`C2_MAIN_OUT_04` output mute) with `0x087F` spare, and is 2,176 entries long. The
RTA block would go directly after it and move no existing address:

| cell | SPI addr | hex |
|---|---|---|
| `Rta001On001` | 2176 | `0x0880` |
| `Rta001Mode001` | 2177 | `0x0881` |
| `Rta001PeakReset001` | 2178 | `0x0882` |
| reserved | 2179 | `0x0883` |
| `Rta001MtrL001..031` | 2180..2210 | `0x0884..0x08A2` |
| `Rta001MtrR001..031` | 2211..2241 | `0x08A3..0x08C1` |

That grows chip 2's table from 2,176 to 2,242 entries. The band meters are single
float32 words read raw, with no convert and no dirty flag. They are not the 4-word
Q8.56 METER block. The generator's dispatch emitter needs a read-only float entry
kind for them, and that change is the hub's to schedule with the landing.

## 3. What the host does with it

- The band words refresh every block (3,000/s). The 62-word read is the only rate
  limit. By single peeks on the diag link one word takes 1.25 ms, so the 62 take
  78 ms (about 13 fps). The daemon reading them with its meter path, or one bulk read
  per frame, is faster.
- **The CM4 daemon's shm meter-ring rate is not in this repo or readable on the
  unit** (the daemon is a stripped binary). The only meter cadence on record is the
  MCU meter poll, about 260 ms (`MW/D24/HW/hardware-map.md`). The hub owns this
  number. At 260 ms the RTA would feel sluggish against its own 35 ms ballistics,
  so the ring should poll these 62 at display rate or faster.

## 4. The source (no cell)

The graph has **no cue bus** (S64-1). The kernel reads two `_blk_` array pointers.
The generator defaults them to `C2_MIX_MAIN_L/R`, the only distinct stereo pair on
chip 2, and they can be repointed on a TEST_NODES image. When a cue bus exists in
`dsp.csv`, the generator's `RTA_SRC_DEFAULT` names its L/R nodes and no cell
changes.
