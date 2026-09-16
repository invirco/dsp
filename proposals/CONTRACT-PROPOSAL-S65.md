provenance: AI-drafted 2026-09-16 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# Contract proposal S65 — the cue bus and the RTA on chip 1: 118 addresses, 82 new cell addresses (18 cue, 2 RTA controls, 62 band meters), `RtaSrc` retired

**Status: PROPOSED, not landed.** Nothing here writes a def, a master row or a
`_matrix.csv` row. The DSP side exists behind `DSP4_CUE` / `DSP4_RTA` (both 0 in
`shipping.config`; with them off both shipping images are byte for byte
`36daa238` / `3a9c950d`). On a switched-on image the addresses below already
answer on chip 1's parameter link. Evidence: `findings.md` S65-1..4.

This proposal **supersedes CONTRACT-PROPOSAL-S64 §2 (chip-2 addresses)**. PW
moved the RTA to chip 1 on 2026-09-16, so its cells move with it. S64's cell
names and laws are kept.

## 1. Existing master rows

| master row (`defs/common/cells/mx_master.csv`) | today | proposal |
|---|---|---|
| `Chan[1-64]CueSel[1-1]` (row 136, 2 states) | control-plane only (`dsp-unmapped.csv`, Q5) | **map it**, strips 1–32: rw 0/1, chip-1 `_cue_sel[n-1]` |
| `Main[1-1]CueSel[1-1]` (row 225, 2 states) | no reader | **map it**: rw 0/1, sums chip 1's main L/R bus into cue L/R |
| `Sys[1-1]CueMode[1-1]` (row 339, 3 states PFL/AFL/SIP) | control-plane | **map it**: rw. 0 PFL = the strip's pre-fader tap (post-delay, pre-mute), mono, unity to both sides. 1 AFL = post-fader times the strip's own pan legs. 2 SIP = AFL on the bus (muting everything else is console logic, not DSP). |
| `Sys[1-1]Cue[1-64]` (row 338) | skin map guesses indexes 25–40 for aux/FX | **no DSP mapping.** It is a console-state mirror. The DSP reads the per-source `CueSel` cells. The hub should decide whether it stays. |
| `Rta[1-1]On[1-1]` (row 250) | no reader | **keep**, rw 0/1, chip 1 |
| `Rta[1-1]Src[1-1]` (row 251) | no reader | **retire** (PW 2026-09-16: the only source is the cue bus) |
| `Mon[1-1]InputSel[1-1]` (row 235, **2 states**, chip-2 `0x06FC`) | the DSP word it reaches (`_mon_source_C2_MON`) had no reader | **widen to 14 states**: 0 Main, 1–12 Aux, 13 Cue. Under `DSP4_CUE`, C2_MON reads cue L at 13. Aux 1–12 still have no reader (§4). |
| `Phones[1-4]Src[1-1]` (row 243, 8 states "LR/Aux/Cue") | no DSP node | no change here. The D24 has ONE monitor node (C2_MON → CODEC_OUT_1). Phones 2–4 have no DSP path. |

## 2. New cells

| proposed cell | access | range / law | DSP symbol (chip 1) |
|---|---|---|---|
| `Aux[1-12]CueSel[1-1]` | rw | 0/1: the chip-1 aux n sum, mono to both sides | `_cue_bus_sel[n]` |
| `Grp[1-4]CueSel[1-1]` | rw | 0/1: the chip-1 group n sum, mono to both sides | `_cue_bus_sel[12+n]` |
| `Cue[1-1]Src[1-1]` | rw | what the bus carries when NOTHING is cued: 0 main L/R (default), 1–12 aux n, 13–16 group n; anything else reads as 0. PW: "the audio bus, not the cue logic". | `_cue_src` |
| `Cue[1-1]Active[1-1]` | ro | sources summed on the last block; 0 = the bus is carrying `Cue Src` | `_cue_active` |
| `Rta[1-1]Mode[1-1]` | rw | 0 fast (τ 35 ms), 1 slow (τ 125 ms), 2 peak-hold | `_rta_mode` |
| `Rta[1-1]PeakReset[1-1]` | w (reads 0) | non-zero restarts the peak hold; consumed within one block | `_rta_reset` |
| `Rta[1-1]MtrL[1-31]` | ro | band n of cue L, **dBFS = 10·log10(w)**, w = IEEE float32 mean square after ballistics (−20 dBFS pk centred sine → −23.01) | `_rta_out[n-1]` |
| `Rta[1-1]MtrR[1-31]` | ro | the same, cue R | `_rta_out[30+n]` |

Bus cues read the **chip-1** sums, which come before the chip-2 bus masters
(aux/group fader, EQ, dynamics). A post-master bus cue needs the cue sum on
chip 2 and is not in this build (S65-1).

## 3. Addresses (chip 1, after the dispatch table, no moves)

Chip 1's dispatch table is 4,984 entries and ends at `0x1377`. The block starts
at `CUE_SPI_BASE = 4984`. It is the S44 way: append, move nothing. The generator
(`dsp_codegen.py::cue_spi_layout`) is the single source of these offsets, and it
refuses to generate if the table ever grows into the block.

| cell | SPI addr | hex |
|---|---|---|
| `Chan001..032CueSel001` | 4984..5015 | `0x1378..0x1397` |
| `Main001CueSel001` | 5016 | `0x1398` |
| `Aux001..012CueSel001` | 5017..5028 | `0x1399..0x13A4` |
| `Grp001..004CueSel001` | 5029..5032 | `0x13A5..0x13A8` |
| `Sys001CueMode001` | 5033 | `0x13A9` |
| `Cue001Src001` | 5034 | `0x13AA` |
| `Cue001Active001` | 5035 | `0x13AB` |
| `Rta001On001` | 5036 | `0x13AC` |
| `Rta001Mode001` | 5037 | `0x13AD` |
| `Rta001PeakReset001` | 5038 | `0x13AE` |
| reserved | 5039 | `0x13AF` |
| `Rta001MtrL001..031` | 5040..5070 | `0x13B0..0x13CE` |
| `Rta001MtrR001..031` | 5071..5101 | `0x13CF..0x13ED` |

On a `DSP4_CUE=1 DSP4_RTA=0` image the RTA addresses read 0 and refuse writes.

**How it is wired today (behind the switch).** `spi_handler.asm` sends an address
at or above the table size to `_cue_spi_read` / `_cue_spi_write`, which index a
pointer table in `cue.asm`. Every entry is a plain word with no ramp, no
conversion and no dirty flag. When the hub lands the cells, the generator can
fold the block into `_spi_dispatch_c1` at the same addresses. The band meters
need a raw read-only float entry kind, the same one S64 asked for.

## 4. The inter-chip slots and the monitor path

- **Slots.** Cue L/R ride **MIX_2 slots 9/10 = global mix slots 41/42**. MIX_2
  carries snake 4–8 on slots 0–4 and the four matrix buses on 5–8 (global 37–40),
  and `shared/dsp4-logic/tdm-lines.csv` marks 9–15 reserved. **There is room: 7
  slots, 2 used.** The fabric lane is DSPA O2 → DSPB I2, and delivery on slots 9/10 is
  proven on the part (findings S65-3). Under the switch the lane grows from 9 to 11 packed
  words (`CS 0x07FF`, region 656 → 688 words on both chips). The slot map
  (`slot-map.csv`) should record `MIX_2,9,BUS_CUE_L` / `MIX_2,10,BUS_CUE_R`
  when this lands.
- **Monitor.** `C2_MON` now reads cue L when `Mon001InputSel001` = 13. What
  remains for a real monitor path:
  - `C2_MON`, `C2_MON_DLY` and `C2_MON_OUT` are **mono**. The node's R level is
    settable and unused, and `C2_MON_OUT` writes one TDM slot of its two. A
    stereo monitor is a graph change: two block arrays per node and the second
    CODEC_OUT_1 slot.
  - Sources 1–12 (Aux) still have no reader.
  - There is no dim/mono/solo-level or talkback-dim cell in the DSP. The master
    has only `Mon[1-1]Level[1-2]` and `Phones[1-4]Level`.
  - `Phones[1-4]` have no DSP nodes.

## 5. Meter path and rate

The 62 band words are read one raw word each through chip 1's parameter link.
This is the path the METER read-back block at `0x1200..` (`_mtr_peak`/`_mtr_rms`/…)
already uses, with the same one-word answer and no conversion. The DSP refreshes
them every block (3,000/s). On the bench (S65-3) the 62 reads took 0.155 s through
the tool link, about 6.5 fps, with one paced ask per word. A meter word moves every
block, so the settle-vote read cannot be used. The CM4 daemon's meter-ring rate is
still not in this repo (S64-3), and the hub owns that number.
