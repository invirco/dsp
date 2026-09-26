provenance: AI-drafted 2026-09-26 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# Contract proposal S122 — the panel haptic cell family

**Status: PROPOSED, not landed.** Nothing here writes a def, a master row or a
`_matrix.csv` row, and nothing in `defs/` was edited by the session that wrote
it. **Cell names are forever** (Bible ch 7), so the names below are a proposal
and PW rules them.

The DSP side is BUILT and is not waiting on this. `C2_HPT_01` is in the graph
at chip 2, page 1, addresses 2175–2182, its eight words are in the SPI dispatch
table, and the host can write every one of them **by address** today
(`s89_set.py <symdir> c2@2175=1`). What does not exist is a NAME, and until PW
gives one there is no `_matrix.csv` row, no ghost-cell entry and nothing the
console app can bind to. That is the whole of what this proposal asks for.

Evidence: `MW/D24/DSP/s122/haptic-path.md`; the graph row in
`MW/D32/DSP/SHARC/dsp.csv`; the generated node in
`MW/D32/DSP/SHARC/src/chip2/nodes/C2_HPT_01.asm`; the dispatch entries in
`MW/D32/DSP/SHARC/src/chip2/dsp_params.asm` at `0x087F..0x0886`.

---

## 1. Why there is a family at all

PW ruled on 2026-09-26: *"the spkr feed is for screen button haptics only, and
should be completely separate from all mixer signal paths."*

The D24 panel speaker is the AK4619's `AOUT1L` — codec TDM slot 0,
`CODEC_OUT_1`, the only codec DAC output fitted on a D24 — through the TS482 on
the digital board's always-on 5 V. Until S122 the MONITOR bus wrote that slot,
so `Mon001Level001/002` **were** the speaker's level, at unity by graph default,
and a self-test press could leave the speaker playing the main mix for as long
as the unit stayed powered (S115). S122 gave the slot its own source, a chip-2
`HAPTIC` node with no inputs, and made the generator refuse any graph in which
anything else reaches it.

A source that plays a stored click when the glass is touched needs the host to
be able to say *play, which one, how loud* — and the self-test needs *tone on,
tone level*. That is the family.

## 2. The proposed rows

Six cells, one instance, in `common/cells/mx_master.csv` spelling. The DSP
words already exist in this order and are contiguous, so a landing costs two
lines in `MW/D32/DSP/gen_dsp.py::expand_haptic` and **moves no address**.

| proposed `_Cell` | word | MxDatS | Table | Neutral | Notes |
|---|---|---|---|---|---|
| `Hpt[1-1]Trig[1-1]` | +0 | 2 | — | `0` | Write 1 to play one shot. The kernel consumes the write and clears it, so the host never has to. |
| `Hpt[1-1]Sample[1-1]` | +1 | 4 | — | `1` | Which stored click, 1–3. 0 and >3 are clamped into range by the kernel rather than refused. |
| `Hpt[1-1]Level[1-1]` | +2 | 255 | `dB:Off:-50@31:-30@63:-10@127:10` | `127` | Click level. **See the open question in §5** — a dB law may be the wrong shape for this cell. |
| `Hpt[1-1]TestOn[1-1]` | +3 | 2 | — | `0` | The steady 1 kHz test tone, for the acoustic self-test. Not a product control. |
| `Hpt[1-1]TestLevel[1-1]` | +4 | 255 | as `Level` | `0` | Test tone level. Neutral is **0**, not unity: the resting state of this cell must be silence. |
| `Hpt[1-1]Busy[1-1]` | +5 | 2 | — | `-` | Read-back, DSP writes: 1 while a click is playing. |

Words +6 and +7 are dispatched spares and get no cell.

`Seq` 1 and `Save2Mix` false on all six, as the `Test[1-1]` family has them:
none of these is desk state a show file should carry. `Hxf` true on `Trig`,
`Sample` and `Busy` (they are codes, not levels).

### 2.1 The product gate

The family wants a scope in `defs/products/<p>/<p>.csv` the way the monitor has
`mon,1` — proposed `hpt,1`, declared by **D24 only**. D32 has no codec speaker
and the graph node is already `scope=D24`, so a D32 boot never calls it.
`defs/tools/def_master.py` `PREFIX_RULES` gains `Hpt -> hpt`.

## 3. What the DSP does with each word, exactly

So that the names are ruled against behaviour and not against a guess.

- **Trig.** Read once per audio block. Non-zero → the kernel writes 0 back,
  latches the selected click's start address and length, sets `Busy` and begins
  playing on that block. A trigger during a click **restarts** it (it does not
  layer and it does not queue).
- **Sample.** Read only at the instant a trigger is consumed, so changing it
  mid-click does nothing until the next trigger.
- **Level.** A float in the DSP; the level word is converted to a Q4.28
  coefficient once per block and multiplied into every sample of that block.
  `1.0` plays the click exactly as stored (peak 0.94 of full scale, which is
  what PW auditioned).
- **TestOn / TestLevel.** While `TestOn` is non-zero and no click is playing,
  the node plays one stored 1 kHz period on a loop at `TestLevel`. A click
  **wins**: a trigger during the test tone plays the click and the tone resumes
  after it.
- **Busy.** 1 from the block the trigger is consumed to the block the last
  stored sample is written. Nothing but the DSP writes it.

**Everything is InstantCtl and MUST be written with ramp 0.** These six words
have no `_target_`/`_step_`/`_frames_` companions — a ramped SPI write walks
three words above the one addressed, and above `Level` sits `TestOn`. The
dispatch table gives them stride 1 and the host is expected not to ask for a
ramp. If PW wants a ramped haptic level, the node grows the companion words
first and that is a graph change, not a host one.

## 4. The stored clicks, and which is which

Three clicks are stored, generated from four numbers each and verified against
PW's own audition files (`MW/D24/DSP/s122/check_click_model.py`, max
|stored − file| = 0.00098 of full scale):

| `Sample` | frequency | decay τ | stored length | audition file |
|---|---|---|---|---|
| 1 | 2500 Hz | 2.5 ms | 829 samples, 17.3 ms | `2_click_2k5.wav` |
| 2 | 3000 Hz | 1.8 ms | 597 samples, 12.4 ms | `6_release_3k.wav` |
| 3 | 1500 Hz | 3.0 ms | 995 samples, 20.7 ms | `1_click_1k5.wav` |

**Which one is press and which is release is PW's ruling and is not made
here.** The mapping above follows the file names (`6_release_3k` is a release)
and this dispatch's own text (2.5 kHz for the press), and it is a default, not
a decision. Changing it is four numbers in `dsp.csv`, no address and no cell.

The two candidates NOT stored are `4_tick_noise` (noise, not a tone — it cannot
be generated from a frequency and a decay and would have to be stored as
literal samples) and `5_thump_plus_click` (a 217 Hz thump with modulation, 29 ms
and still audible at the end). If PW wants either, say so: the noise tick is
about 310 words of table and the thump about 1,400, against 90 kB of chip-2 DM
free.

## 5. Open questions for PW — none of them blocking

1. **THE NAMES.** `Hpt` or `Haptic` or `Click` or `Spkr`? Six cells or fewer
   (`Busy` could go; `TestOn`/`TestLevel` could be one cell with 0 = off)?
2. **The level law.** The table above is the monitor's dB law, borrowed. A
   haptic click is not a mix level and a plain linear 0–100 % may be the
   honest shape. A dB law also has no code for "silent but armed" other than
   its own `Off`.
3. **Press / release / spare** — §4.
4. **Is `TestLevel` a product cell at all?** It exists for AL1. It could be
   spared out of the product master and left as a dispatch-only word the
   factory reaches by address, which is what it is today.

## 6. What landing it costs

- `common/cells/mx_master.csv`: six rows.
- `defs/products/d24/d24.csv`: `hpt,1`.
- `defs/tools/def_master.py`: one `PREFIX_RULES` entry.
- this repo, `MW/D32/DSP/gen_dsp.py::expand_haptic`: six `add_cell()` calls
  beside the six `add_dispatch()` calls that are already there, and the
  `_UNREACHED_REASONS` entry for `C2_HPT_*` comes out.
- `MW/D24/DSP/s122/`, `tools/pi/d24_selftest.py` and
  `tools/pi/dsp4_s49_osc.py`: the `c2@2175`-style address writes become cell
  writes. They are marked in each file with the reason they are addresses.

No address moves in any of that, because the words are already allocated.
