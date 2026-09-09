provenance: AI-drafted 2026-09-09 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# CFG_CHAN_MASK and CFG_AUX_MASK get readers: a D24 runs 24 strips

Bench: rev C unit MW-D24-2, `app@192.168.1.219`. Rev A show model not
touched. Contract `defs-v2026.09.08.4`, unchanged — nothing here is a
contract change.

## 0. The answer, in one table

| | | |
|---|---|---|
| **the defect** | a D24 ran all 32 channel strips and all 12 aux buses | `_chan_mask` / `_aux_mask` were stored by `product_config.asm` and read by nothing |
| **the fix** | the process chain reads them and SKIPS what is masked | `DSP4_CHAN_MASK=1`, default on; `=0` rebuilds the pre-fix image byte for byte |
| **the audio** | `C2_MAIN_ST_OUT` **0x00000000 on 48,000 of 48,000 frames** | was `0x7FFFFF88` on 48,000 of 48,000 |
| **chip 1** | 262,033 → **202,786** cycles/block; margin 20.03 % → **38.11 %** | −59,247 = −18.08 % of budget |
| **chip 2** | 261,856 → **226,442** cycles/block; margin 20.09 % → **30.90 %** | −35,414 = −10.81 % of budget |
| **chip 2, six reverbs** | 310,185 → **275,035**; margin 5.34 % → **16.07 %** | the number the product ships against, and it clears the 10 % bar |
| **images** | chip1 `093c609f622cf805e7f675f1e2497a19`, chip2 `2ba0e464e9679bd2e1b1c3c2a6f08744` | staged as the window's `~/dspboot/chip1.ldr` / `chip2.ldr` |

## 1. What was wrong

`tools/pi/dsp4_config.py` has always sent a D24 `CFG_CHAN_MASK =
0x00FFFFFF` — "strips 25-32 NET-only". `product_config.asm` has always
stored it in `_chan_mask`. Nothing has ever read it. Same for
`_aux_mask`. The 2026-09-09 latency session found this and measured its
consequence; this session gives both words a reader.

The contract was never at fault. D24 is a 24-channel product, its matrix
carries zero `Chan025` cells, and `defs-v2026.09.08.4`'s `d24/dsp.csv`
correctly addresses `Chan001`–`Chan024` and `Aux001`–`Aux008` and nothing
beyond. The firmware was running eight strips and four aux chains the
product does not have, and it could not be told to stop, because the one
word that says so was inert.

**The host was wrong about the aux count too, and harmlessly so until
now.** `dsp4_config.py` sent D24 an `AUX_MASK` of `0x0FFF` — twelve.
D24 has eight. That was documentation while nothing read it and would
have been four live aux chains the moment something did. It is now
`0x000000FF`, taken from the product definitions.

## 2. SKIP, not run-and-silence

PW's first priority is capacity fit, so the design question was whether a
masked strip should be skipped (cycles come back, but anything reading a
stale buffer downstream has to be handled) or run and silenced (simpler,
cycles unchanged). **Skipped.** A D24 is a 24-channel product and its
cycle load has to be a 24-channel load; §4 is what that is worth, and it
is worth more than the whole 31-band GEQ costs.

The static schedule does not make it unsafe, but it does constrain it in
three ways, and each is answered rather than assumed.

**The mask gates RUNS, not nodes.** A per-node skip table was measured
in 2026-08-24 as a net loss for the product-scope gate — testing a word
before all 431 calls costs more than not calling the 34 scoped ones — and
the same arithmetic applies here. A strip's ten nodes and its meter are
contiguous in all three chain orders, so one compare and one branch
covers them.

**A PAIR runs if EITHER half is live.** The paired dynamics and paired
biquad kernels are one SIMD instruction stream over two strips; there is
no runtime way to half-issue them. The masked half of a live pair still
contributes nothing, because its ROUTING node has a gate of its own and
its crosspoint column is zeroed (§3). For every mask any product actually
sends — D24's `0x00FFFFFF`, D32's all-ones — the pairs are whole and
nothing extra runs.

**Only ROUTING and the aux nodes are gated exactly.** Two things make a
masked strip audible: its ROUTING node, which accumulates it into the
buses, and an aux node, which publishes a bus the gather reads. Those are
gated on their own index. Every other strip node is a private computation
read only by the next node of the same strip, so adjacent ones are merged
into a single gate keyed on the union of their strips. That is what makes
the fix FIT — see §5.

**Applied at CONFIG_COMMIT, and mid-life changes are supported with a
stated atomicity.** `_chan_mask` / `_aux_mask` stay the STAGED words the
host may write at any moment from the SPI RX ISR; `_chan_mask_live` /
`_aux_mask_live` are what the chain reads, and only `_mask_apply` — called
from `_product_config_commit` — moves one to the other. A mask change
therefore takes effect on the next CONFIG_COMMIT. That commit arrives on
the ISR and can land inside a block, so **one block (8 samples, 0.17 ms
at 48 kHz) can run with the strips of the old mask and the buffers of the
new one.** Nothing is torn beyond that: the masks are single words, the
chain re-reads them once per run, and every buffer `_mask_apply` zeroes
is re-derived next block by whichever nodes still run.

`_product_id`'s reader — the product-scope gate, one compare and one
branch per contiguous run, resolved at commit — is the pattern this
follows.

## 3. What the skip leaves behind, and what is zeroed

A skipped node does not write its output, so anything downstream that
reads a BUFFER rather than calling the node would carry the last value
the node ever produced. Three such buffers exist; `_mask_apply` zeroes
all three for every masked index.

| buffer | who reads it | why it matters |
|---|---|---|
| `_xpc[bus][strip]` (chip 1) | the bus-major fabric | it MACs `_xpc[bus][s] * _rtg_src[s]` for every s in a bus's live range whether or not strip s ran, so a strip that stops running with a live coefficient freezes a DC term into its buses |
| `_buf_C1_BUS_AUX_nn`, `_tx_slot_C1_BUS_AUX_nn_SEND` | the chip-1 gather points straight at them | a masked aux bus would keep transmitting its last block to chip 2 |
| `_tx_out_slot_C2_AUX_OUT_nn` | the chip-2 gather | a masked aux output would hold DC on the TDM wire |

Zeroing the crosspoint column also NARROWS `_xp_lo`/`_xp_hi` (hence the
`_xp_dirty` set after it), which is why masking strips 25-32 costs the
fabric less as well as summing less.

At a FIRST commit none of this has anything to undo: the columns are
still the zeros `rtg_fabric.asm` initialises them to and no node has run.
It exists for the SECOND commit, which the bench recipe does on every
boot and which a host may do again at any time.

## 4. Proven on the part

### 4a. The audio, three configurations, one bitstream, one night

`dsp4_logic_maincap.1216e35175cb` flashed (capture path on B_O3 slot 0 =
`C2_MAIN_ST_OUT`), duplex overlay, one second of capture with **nothing
playing at all**, `tools/pi/dsp4_mask_witness.py`.

| image | config | `C2_MAIN_ST_OUT` |
|---|---|---|
| `602a0feb` / `b1325022` — the pre-fix conformance pair, which is `DSP4_CHAN_MASK=0` byte for byte | D24 | **`0x7FFFFF88` on 48,000 of 48,000 frames** |
| `093c609f` / `2ba0e464` — the fix | D24 | **`0x00000000` on 48,000 of 48,000 frames** |
| `093c609f` / `2ba0e464` — the fix | D32 | **`0x7FFFFF80` on 48,000 of 48,000 frames** |

The third row is the positive control and it is the important one: on a
D32 config the fixed image does exactly what the pre-fix image did,
because all 32 strips are live and this D24 board has nothing driving
25-32. **D32 behaviour is unchanged.** The masking is the only
difference and the product config is the only thing that selects it.

The D24 row was taken twice, once with **nothing silenced at all** and
once with everything the D24 contract can silence silenced (48 cells:
`Chan001`–`Chan024` MainOn/Mute, the four group mutes, USB, Bluetooth and
codec aux). Both read zero on every frame. Before the fix, getting to
zero required writing D32's rows for cells D24 does not have —
`tools/pi/dsp4_silence_2532.py`, which said in its own docstring that it
was a workaround and to delete it once `_chan_mask` had a reader.
**Deleted this session.**

The masks read back off both parts:

```
chip 1  _chan_mask=0x00FFFFFF  _chan_mask_live=0x00FFFFFF  _aux_mask=0x000000FF  _aux_mask_live=0x000000FF
chip 2  _chan_mask=0x00FFFFFF  _chan_mask_live=0x00FFFFFF  _aux_mask=0x000000FF  _aux_mask_live=0x000000FF
```

and under a D32 config `0xFFFFFFFF` / `0x00000FFF` on both. Reading the
STAGED word alone would prove only that the SPI write landed — which was
the whole state of the firmware before today — so it is the LIVE word
that is quoted.

### 4b. Strips 1-24 still pass the family walk

`./famverify.sh` on the fixed image, pin `defs-v2026.09.08.4`, sha256
`4aa3c343cedf`:

**17 of 20 families PASSED, 3,619 of 3,737 addressed cells (97 %), 4
families on the strict bar (1,046 cells), 0 FAILED.** GEQ **31/31**,
CROSSOVER **8/8**. That is the `.4` conformance line to the cell, and it
has not moved down. The three families not exercised are the same three
as before, for the same reasons: AUX_INPUT (no stimulus path on this
bench), DCA (host-managed, nothing on the part to probe), METER
(`mtrverify.sh` is its bar).

### 4c. Capacity

Block 16, 983.04 MHz, budget **327,680 cycles/block**, `DEC=32`,
`DSP4_PROFILE_SIGNAL=1`, fused + paired + biquad-paired, **two boots a
point, minimum taken**, every point witnessed before its number was
accepted. Chip 1 through `captable.sh MODE=cyc`, chip 2 through
`sigprofile2.sh` — the same two instruments the `.4` record was taken
with, and both arms of each measured **in one session on one
instrument**, which is why the control column is measured here rather
than quoted from 2026-09-08.

| arm | cycles/block | % of budget | margin |
|---|---:|---:|---:|
| chip 1, unmasked control (`DSP4_CHAN_MASK=0`) | 262,033 | 79.97 % | 20.03 % |
| **chip 1, D24 masked** | **202,786** | **61.89 %** | **38.11 %** |
| chip 2, unmasked control | 261,856 | 79.91 % | 20.09 % |
| **chip 2, D24 masked** | **226,442** | **69.10 %** | **30.90 %** |
| chip 2, masked, six FX engines at Type 3 = Reverb | **275,035** | **83.93 %** | **16.07 %** |

**The controls reproduce the `.4` record.** Chip 2's control reads
261,856 against the record's 261,848 — eight cycles, 0.002 % of budget.
Chip 1's reads 262,033 against 261,879 — 154 cycles, 0.047 %. The
instrument agrees with itself across two sessions, so the differences
below are the fix and not the day.

**Chip 1 gains the most, and chip 1 was the tighter chip.** It carries
the channel strips: eight of thirty-two stop running, and the fabric's
live strip range narrows with them. −59,247 cycles/block is **18.08 % of
the part's budget** and takes chip 1's margin from 20.03 % to **38.11 %**.

**Chip 2 gains from the aux mask**: four of twelve aux chains — fader,
EQ, 31-band GEQ, anti-feedback, limiter, delay, output and meter each —
stop running. −35,414 cycles/block, **10.81 % of budget**.

**The six-reverb worst case is the number that matters and it is now
outside the bar.** With all six FX engines at Type 3, chip 2 runs at
83.93 % with **16.07 % margin**, measured by `fxcost.sh` at block 16 over
two boots with a restore-and-re-read control that came back within 68 and
82 cycles of the default. The 31-band `.4` figure was 94.66 % / **5.34 %
margin** — inside the 10 % bar, and recorded at the time as a product
decision rather than a defect. It was neither: it was 5.34 % because the
part was running four aux chains the product does not have. The reverb's
own cost is unchanged and the instrument says so — +49,187 cycles/block
here against +49,096 on 2026-09-08, ninety-one cycles apart.

## 5. The fix did not fit, and what that cost

The first cut gated every run exactly and unrolled `_mask_apply` per
strip and per aux. It **overflowed chip 1's `sec_swco` by 622 words** in
the block-16 paired build — the configuration every capacity number is
taken in. The shipping per-sample image linked, so nothing about the
window was blocked, but a fix that does not fit the operating point is
not a fix.

Three changes brought it to about 230 words:

* **`_mask_apply` is table-driven.** The per-strip crosspoint zeroing is
  one loop over 32 strips, the aux buffer zeroing one loop over a
  `(pointer, bit)` table, instead of 44 unrolled blocks. It runs once at
  commit, so it is written for size and not for speed. −360 words.
* **The chain's gate is three instructions, not four.** `_mask_apply`
  resolves one word per gate group into `_mask_on[]`, so the chain loads,
  tests and branches instead of loading a 32-bit immediate and ANDing at
  every one of sixty-odd gates.
* **Adjacent non-exact runs are merged** (§2), and a run of standalone
  METER entries — which emits nothing at all under block kernels — is not
  gated there. Chip 1 went from 124 gates to **61**.

Neither the merge nor the table changes what is skipped for any mask a
product sends.

## 6. The through-DSP loop arm: still open, and the reason is NOT the mask

The 2026-09-09 latency session closed the CPLD loop (14,431 samples /
300.646 ms, boot-to-boot part zero) and could not close the through-DSP
arm; it recorded the channel mask as the headline finding and the reason
every earlier attempt was unusable. **The mask was not why that arm does
not close.** With the main bus proven silent to 48,000 frames of 48,000
and the pass-through set to unity, the arm still does not close, and this
session names the mechanism instead of the symptom.

**The DSP pass-through is bit-exact and continuous.** Play a constant
`0x00123400` through Pi → CPLD → DSPA → fabric → DSPB → CPLD → Pi and it
comes back unchanged on 143,400 of the 144,000 frames played, with the
remainder at the onset transition.

**What is destroyed is sample ORDER, inside a window.** A staircase — 1,500
values, 64 frames a step, `tools/pi/dsp4_order_stair.py` — comes back with
every value present (index range 1..1500 complete) and the right count
(96,040 non-zero words for 96,000 played), but as **82,042 runs where a
clean loop gives 1,500**: 86 % of runs are a single frame, and only 8,141
of 81,351 run-to-run transitions are +1. The interleaved values sit within
a window of a few hundred to a few thousand steps of each other, and the
width of that window is not fixed.

That is the signature of a capture path that is **not frame-locked** to
the CM4 capture DMA — producer and consumer walking the same ring at
independent phase. It is a property of the `_maincap` instrument
(`o_dspb[3]` slot 0), not of the DSP: `_pisel`, which closes the same
loop inside LOGIC with the DSP out of the path, returns 48,000 of 48,000
counter words at ONE offset.

So, as the previous session did and for a better-understood reason:
**no through-DSP latency figure is quoted.** `dsp4_loop_latency.py`
reports an offset of 14,494–14,509 over 20 reps for this arm with
**counter agreement of 5.67 %** across ~2,780 distinct offsets and the
impulse never found; that is a spurious mode, it is recorded so it is not
picked up later as a measurement, and it is not one.

**What it would take.** A capture path frame-locked to the Pi stream —
a CPLD-side change to the `_maincap` re-framer, or a DSP-side capture
into a buffer the host reads over the parameter link, which sidesteps
ALSA entirely. Neither is a firmware defect and neither blocks the
window. Recorded as S6-4.

## 7. Method and controls

* **`DSP4_CHAN_MASK=0` rebuilds the pre-fix image byte for byte.** The
  whole of `mask_gates.asm`, the two live words and the commit-time call
  are inside that guard. Built twice from this tree, before and after the
  §5 rewrite, and both times it produced `chip1.ldr`
  `602a0febbd1947d288c2ac36c3d3f4c7` and `chip2.ldr`
  `b1325022df2013821c357a22d8a054f7` — the window's own conformance
  images. Every cycle figure recorded before 2026-09-09 is therefore
  reproducible on this tree, and the control column of §4c is that
  guarantee used rather than asserted.
* **The build flag is carried into the build DIRECTORY NAME** in
  `sigprofile2.sh` and `fxcost.sh`, and through `XFLAGS` in
  `captable.sh`, for the reason `CSVTAG` already exists there: two arms
  measured in one session must not share a directory, or the second boots
  the first one's image and reports the first one's number as a
  difference.
* **Host bars, before and after:** `golden_harness.py` 59/59,
  `dsp_validate.py` OK on 666 nodes with only the four known process-order
  notes, `test_geq_splice.py` 5/5, `test_dsp_validate.py` 13/13,
  `check-contract-drift.sh` clean at `defs-v2026.09.08.4`.

## 8. Bench state

| | at start | at end |
|---|---|---|
| CPLD | `dsp4_logic.a1f6672af6c3` | **`dsp4_logic.a1f6672af6c3`** (restored, IDCODE `0x020a30dd` re-read) |
| `~/dspboot/chip1.ldr` | `602a0feb…` | **`093c609f…`** — this session's fix, the window's new artifact |
| `~/dspboot/chip2.ldr` | `b1325022…` | **`2ba0e464…`** |
| the previous pair | — | kept alongside as `~/dspboot/conf_chip1.ldr` / `conf_chip2.ldr`, md5s unchanged |
| the rollback pair | `~/dspboot/ship_chip1.ldr` `3f0e479a…` / `ship_chip2.ldr` `ab43c75b…` | untouched |
| Pi overlay | `dtoverlay=dsp4-pcm-slave` | `dtoverlay=dsp4-pcm-slave` (restored; `config.txt` diffs clean against `/home/app/config.txt.asfound-20260909-mask`) |
| matrix-app | active | active |

`dsp4_logic_maincap.1216e35175cb` was flashed twice for the captures in
§4a and §6 and the shipping bitstream restored after each, through the
documented hands-off path: OpenOCD `linuxgpiod` on the bench CM4's own
GPIOs (TCK 7, TDI 23, TDO 22, TMS 25), IDCODE `0x020a30dd` read back
before and after, `pinctrl set 6,7,8,9,10,11,12,22,23,24,25 a0` after
every one. There is still no USB-Blaster on the dsp machine and the
design still has no ID register (S5-9).

**The bench's DSP images are the one thing not as found, and that is
deliberate**: they are the images the window should deploy instead of the
pair it was holding.
