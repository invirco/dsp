# Retired LOGIC bitstreams

Nothing here is deleted and nothing here is flashed. These are artifacts
`loadlogic.sh` used to name, kept because the bench records point at them by
md5 and those records must stay resolvable.

They are here rather than in the repo's `attic/` because `attic/` is defined
by CLAUDE.md as the retired D24 ADAU1466/SigmaStudio material and is never
extended. This directory does the same job, next to the artifacts it retires.

**Do not build from these and do not flash them.** Each has a live
replacement named in `MW/D32/DSP/SHARC/loadlogic.sh`.

---

## `dsp4_logic_driveall.e13b5dec84e0` — retired S37, because it has no source

The DRIVEN-CAPACITY stimulus. Every driven capacity row since S28 was taken
on it, including the `100.82 %` D32 worst-use figure in
`MW/D32/DSP/window-candidate.md` §2.1.

**It matches no committed state of the logic tree at any point in its
history** (S36-3): it was built from a dirty working tree and that tree was
never committed. `build.sh`'s `SRC_HASH` is a pure function of committed text,
so this was settled exhaustively — 4,352 candidate labels across all 34
commits that have ever touched the tree, at all four `cfg:` line shapes and
all 32 macro combinations — not by failing to find it.

Its rebuildable equivalent is `dsp4_logic_driveall.907492a607bd`, the same
work committed at `a096c585` 36 minutes later; the two differ only in the
stamped `design_id` word. S37 rebuilt `907492a607bd` from `a096c585` in a
clean tree and got the same label and a **byte-identical pof**.

| | pof md5 | design_id |
|---|---|---|
| retired `e13b5dec84e0` | `ab6781b2edee4cfec312b56cd0dee9f4` | `32'h5dec84e0` |
| rebuildable `907492a607bd` | `8d52c5d3a3e09267da8a9ffa5913ce0a` | `32'h92a607bd` |

## `dsp4_logic_pisel.bd9c100db7c2` — retired S37, because it cannot say what it is

The CPLD-only loop reference, the far end of the S29 latency differential.
Built from `1dc67f39`, which **predates the design-ID stamp** (`3152e2b1`), so
its manifest carries no `design_id` line and `dsp4_logic_id.py` gets nothing
back from the part. Its identity rests on the flash records, not on the
silicon.

The stamped equivalent from the same work is
`dsp4_logic_pisel.2c1355bbc69b` (`3152e2b1`) — S37 rebuilt it from that
commit in a clean tree and got the same label and a byte-identical pof.

| | pof md5 | design_id |
|---|---|---|
| retired `bd9c100db7c2` | `9f0d2bcbf1fa2e31ef6529335fb461ae` | none — predates the stamp |
| stamped `2c1355bbc69b` | `621599e288c7cc6f9ba200a4bb0f506b` | `32'h55bbc69b` |

## `dsp4_logic.a1f6672af6c3` — retired S82, because it does not clock the converters and cannot say what it is

**THE ARTIFACT THE `shipping` LABEL NAMED FOR A MONTH.** Built 2026-08-21 at
commit `a4ee3d1f`, which `git merge-base --is-ancestor` puts BEFORE
`ded71079` — the S34 converter-clock fix of 2026-09-11, whose own RTL comment
reads *"THESE WERE INPUTS, AND THAT IS WHY NO CONVERTER CAN WORK"*. On this
bitstream U3 pins 142/141 (board nets C1 and L0) are INPUTS, so nothing drives
the converter bit clock or frame sync at all and no converter on the card can
work.

**TWO CORRECTIONS, BOTH FROM S84 AND BOTH MEASURED.**

*The bench did not live on it for a month.* The heading above used to say so
and the bench's own dated flash log says otherwise: `a1f6672af6c3` was on the
part for about 35 hours in all (2026-09-11 06:43Z to 2026-09-12 17:41Z), and
from 2026-09-13T13:11:14Z to 2026-09-19T21:47:06Z — six days containing
2026-09-16, the day S54–S58 measured live preamp noise — the part carried
`s41_mhrx_pullup_off.15f3ae07dae1` with nothing flashed in between. The LABEL
pointed here for a month; the PART did not. The whole table is in
`docs/d24-bench-logic-flash-log.md`, and it is the record, not this note.

*"Pre-S34" is NOT the discriminator and must not be used as one.*
`s41_mhrx_pullup_off` and its parent `s37_shipping_step0` are pre-`ded71079`
by ancestry (`git merge-base --is-ancestor ded71079 61e38ce3` is FALSE) and
they DRIVE the clock pair: at `61e38ce3` the top module already carries
`assign conv_bck = bck8; assign conv_fs = fs8;`, the same two lines HEAD has,
where `a4ee3d1f` has no such ports at all. Two independent lineages drive the
pair — the step-0 shipping branch and post-`ded71079` `main` — and exactly one
artifact does not. S41 measured it at the time (U3.142 = 12.288 MHz,
U3.141 = 48 kHz) and S84 confirmed it by reading all four codec lanes live on
`s41_mhrx_pullup_off`. What is wrong with `a1f6672af6c3` is what this file
says about `a1f6672af6c3`, and nothing may be inferred from a build date.

**Measured, not deduced (S81 §3.4).** Same DSP pair, same firmware, same
symbol map, same reads, half an hour apart, only the bitstream changed: on
`a1f6672af6c3` all four `_buf_C1_XIN_CODEC_0*` read exact digital zero; on the
post-fix artifact all four carry moving converter noise that grows with AN_EN
high. Ten sessions between S71 and S81 diagnosed a hardware fault that was
this file.

It also predates the design-ID stamp, so `dsp4_logic_id.py` answers *"no
reply: nothing in the capture carried the 0xD594 marker"* — the same defect as
`bd9c100db7c2` above, on the one artifact where it mattered most, because the
bench's whole account of what it had measured on rested on a flash log.

PW adopted the S34 fix on 2026-09-20 (S81-Q1). The replacement was
`dsp4_logic.7a6a4529f29c`, and `loadlogic.sh` refuses to stage ANY artifact
whose manifest carries no `design_id:` line (S81-Q2, ruled S82).

From S85, `loadlogic.sh shipping` names **`dsp4_logic.d02d83b3cc22`**
(`32'h83b3cc22`) — the same shipping lane path with the ad[0..2] witness built
in unconditionally (hub ruling S84-N1). `7a6a4529f29c` is NOT retired: it is
the artifact every S82-, S83- and S84-era reading was taken on, it is still in
`bitstream/`, and `./loadlogic.sh shipping-s82` stages it by name. Nothing in
this folder changes.

| | pof md5 | design_id | converter clock |
|---|---|---|---|
| retired `a1f6672af6c3` | `f08f3b525ff0fe2f7957a96d958842e6` | none — predates the stamp | **NOT DRIVEN** |
| `s37_shipping_step0.c62c024714f2` | `79284dad6e9c27995f91806056c9fba5` | none — does not fit at that size | driven (its own lineage, pre-`ded71079`) |
| `s41_mhrx_pullup_off.15f3ae07dae1` | `72a28864d54334215d192070d5742252` | none — does not fit at that size | driven (measured S41, confirmed S84) |
| shipping `7a6a4529f29c` | `7dc0976d7b13d98b4a37795d1eeaf49e` | `32'h4529f29c` | driven (S34) |

---

All three are the precise failure `shared/dsp4-logic/build.sh`'s own comment
block was written about, and each was still live in the tool the bench used
every day until the session that retired it.
