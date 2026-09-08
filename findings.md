provenance: AI-drafted 2026-09-08 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# findings — dsp spoke

Numbered findings D1–D8x are recorded in `review-dsp-20260828.md` and in the
dispatch blocks of `tasks.md`. This file carries findings raised by dispatched
sessions after that review, newest first.

## hardware families through the landed contract (2026-09-08)

Session: the queued VIRTUAL AUDIO block, steps 2–4 — every D24 kernel family
exercised on the part with its parameters addressed out of the LANDED
`defs/products/d24/dsp.csv`. Write-up:
`MW/D32/DSP/dsp4-hw-families-20260908.md`. Image: the shipping FLOAT
configuration at defs-v2026.09.08.2, chip1 `906a70f7` / chip2 `3a2d930c`,
byte for byte the session's starting baseline.

### S2-1 — `ChanGateHold` reaches the kernel unconverted, and a gate that has opened never closes again

**Severity: major. Status: FIXED the same day — see S2-8 for the fix, which
is generic over `wire-units.csv` rather than a patch for this cell.**

`_gate_hold_<nid>` is an integer SAMPLE COUNT — the generator's own
initialiser is `2400`, which is 50 ms at 48 kHz — and the SPI dispatch
stores the host's IEEE-754 float32 word into it with no conversion. A host
writing the documented 1.0 ms therefore lands `0x3F800000` =
**1,065,353,216 samples, about 6.2 hours of hold**.

Measured on the part 2026-09-08. With hold written as `f32(1.0)` and the
gate threshold raised to 0 dBFS over a −6 dBFS step,
`_gate_gain_target_q_C1_GATE_01` stayed at unity (268,435,456) and
`_buf_C1_GATE_01` stayed at `0x07FFFF07` — the gate did not shut. Writing
the same cell as a RAW `48` (1 ms as the variable actually means it)
restores the behaviour completely:

| threshold | `_gate_gain_target_q` | capture peak |
|---|---|---|
| −80 dB | 268435456 (unity) | `0x07FFFF07` |
| 0 dB | 2684355 (the range floor) | `0x00147BDB` |

**The ladder is not the fault.** `dsp4_node_verify` scores GATE bit-exact
against `fixed_ref` on this same image, converted parameters and all, and
the threshold conversion is exact (`_gate_thrq` = −222,930,816 for −40 dB,
which is `fixed_ref.gate_thr_q(-40.0)` to the word). The missing conversion
is the whole defect.

`defs/common/wire/wire-units.csv` already carries the row — `ChanGateHold,
ms, hold samples — conversion to declare` — so the gap was known. This is
the first measurement of what it costs, and the cost is that the gate stops
gating after its first signal.

### S2-2 — a parameter that genuinely holds ZERO reads as unreadable, and it cost COMPRESSOR its verdict twice

**Severity: medium (instrument). Status: fixed in
`tools/pi/dsp4_family_verify.py`.**

`dsp4_node_verify.vpeek()` will only accept a value of 0 when a known
non-zero register still reads correctly — a dropped answer on this link
always reads as zero, so zero has to out-vote its own absence. That
corroborating register lives in `dsp4_node_verify.SENTINEL`, and `SENTINEL`
is populated in `dsp4_node_verify.main()`. **Any tool that calls
`run_node()` directly leaves it empty**, and every genuinely-zero parameter
word then returns `None`.

The compressor's hard-knee words `_comp_cgp_+2` and `_comp_cgp_+3` are zero
by default, so COMPRESSOR reported `parameters unreadable — no verdict` on
two consecutive bench runs while every other node passed. The other six
words read fine, which is exactly why it looked like a link fault:

```
_comp_attq   4294968        _comp_cgp_+0  4183501888
_comp_relq   4294968        _comp_cgp_+1  1610612736
_comp_mkq    367756576      _comp_cgp_+2  None      <- genuinely 0
_comp_parq   2147483647     _comp_cgp_+3  None      <- genuinely 0
```

`numeric_phase()` now arms the sentinel from `_scope_len` before the first
node and says so in the log when it cannot.

### S2-3 — BQCVT is the FIXED arm's converter and reports a false FAILURE on the shipping float image

**Severity: medium (instrument). Status: fixed.**

`run_bqcvt` compares the node's stored coefficients against
`fixed_ref.biquad_coeffs_q`, which is Q4.28. Under `DSP4_BQ_FLOAT` — the
shipping default — the node stores IEEE float32, so every set mismatches
and the run prints `MISMATCH b1 control fires` for all of them:

```
part  (1065353216, ...)   = 0x3F800000, float 1.0
model (268435456,  ...)   = Q4.28 1.0
```

That is the harness quoting the wrong model for the arm it was pointed at,
not a firmware defect. `shared/numeric-spec.md` is explicit: the SHARC float
cascade's bit-exact reference is `bq_float_ref` and its bar is
`bqeverify.sh float`. `dsp4_family_verify.py` now takes `--bq-arm` from the
build and skips BQCVT on a float image with the reason in the log.

### S2-4 — a DC step cannot see a filter whose gain at DC does not move

**Severity: medium (method). Status: fixed — the frequency-shaped families
are probed with an impulse.**

`dsp4_conform.bus_capture()` drives a STEP and reads a window at sample 900.
For a gain, a delay or a dynamics stage that is the right stimulus. For a
filter it is DC, and a peaking section has unity gain at DC — so a 28-band
GEQ's band 1 (near 25 Hz), an anti-feedback notch and a crossover all change
nothing that a step can show. The second run of this bar duly reported GEQ,
ANTI_FB and CROSSOVER as INERT, which would have been a wrong answer about
the firmware drawn from a property of the instrument.

An impulse response is frequency-complete. `dsp4_family_verify.capture()`
takes the stimulus mode per family, and the biquad-shaped families are armed
with an impulse read from sample 0.

### S2-5 — `ChanGain` and `TalkGain` are applied as LINEAR coefficients while the masters declare dB

**Severity: medium. Status: open — an mx26 unit call, corroborated on the
part.**

`docs/contract/wire-units-proposals.md` lists both families as unit
UNDECLARED with the Table domain proposed as the wire unit
(`ChanGain 0=0/127=60/[Lin]`, `TalkGain 0=0/127=40/[Lin]` — both dB).
Measured on the part, the kernel takes them as linear:

| cell | written | input peak | output peak | linear reading | dB reading |
|---|---|---|---|---|---|
| `Chan001Gain001` | 4.0 | `0x08000000` (0.5) | `0x20000000` (2.0) | ×4 ✓ | ×1.585 ✗ |
| `Talk001Gain001` | 4.0 | `0x08000000` (0.5) | `0x20000000` (2.0) | ×4 ✓ | ×1.585 ✗ |

The proposal as written ("declare the Table domain as the wire unit") cannot
be adopted without a dB→linear conversion appearing in the kernel; adopting
it as-is would silence the strip at the documented 0 dB, exactly as review
finding D57's `RtgDca` did.

### S2-6 — four families answer every landed address and reach no sample

**Severity: major. Status: reported — WIRE-vs-RESERVE is PW's call, and two
of the four were not on the list that was supposed to hold them.**

`ANTI_FB`, `GEQ`, `CROSSOVER` and `FX_ENGINE` — **646 of the 3,698 addressed
D24 cells** — take every write at their landed address, raise no SPI error,
and change nothing. Measured the strongest way available: walk the chain
with an IMPULSE (frequency-complete, unlike the step) and diff consecutive
node buffers word for word.

```
aux 1, GEQ bands driven +12/-12 dB, notch armed 1 kHz Q4 at -18 dB
  _buf_C2_AUX_FDR_01   0x08000000 0 0 0
  _buf_C2_AUX_EQ_01    0 of 32 samples differ from the previous node
  _buf_C2_AUX_GEQ_01   0 of 32
  _buf_C2_AUX_AFB_01   0 of 32
  _buf_C2_AUX_LIM_01   0 of 32

main, crossover frequency written 500 Hz
  _buf_C2_MAIN_DLY     0x08000000 0 0 0
  _buf_C2_MAIN_XOVER   0 of 32      <- the crossover does not split
  _buf_C2_MAIN_OEQ_01  0 of 32
  _buf_C2_MAIN_OEQ_02  0 of 32

FX 1, On=1, Mix=100, Decay=2.0
  _buf_C2_FX_ENG_01    0x08000000 0 0 0
  _buf_C2_FX_FDR_01    0 of 32
```

`ANTI_FB` and `FX_ENGINE` are **corroborated by the D38 static list** —
`docs/contract/inert-cells-d38.md` already names every notch cell and every
FX parameter as unreferenced by any emitted line — so this is the live
confirmation that list was waiting for, on families session 6's sampled
probe did not reach.

**`GEQ` and `CROSSOVER` are NOT on that list, and that is the new part.**
372 addressed cells that static analysis believed something reads, and the
part says nothing does. Either the generator emits a reference the kernel
never acts on, or `wire_contract.py`'s "reachable by offset" class is
hiding them; either way the D38 count of 896 is low by at least these.

### S2-7 — the CM4 duplex loop is up: one PCM device, S32_LE, 192 kHz

**Severity: medium. Status: CLOSED at the ALSA layer.** The recorded
blocker was that `dsp4-pcm-slave.dts` exposes TWO PCM devices sharing one
`bcm2835-i2s` CPU DAI (playback-only `spdif-dit`, capture-only
`spdif-dir`), so opening both re-programs the same block twice and the
counter comes back scrambled. Its stated fix direction — ONE dai-link with
a codec declaring both directions — is right, and the obstacle was that no
codec in the Pi tree fits this link. Four were measured on the bench
2026-09-08 before one was written:

| codec | result |
|---|---|
| `linux,spdif-dit` + `linux,spdif-dir`, two links | the overlay being replaced. Right rate, right format, one direction each. |
| the same two as multi-codec on ONE link | instantiates **capture only** (`00-01 bcm2835-i2s-dir-hifi … capture 1`) — the playback-only codec loses. |
| `asahi-kasei,ak4554` | ONE dai-link and a REAL duplex device (`00-00 … playback 1 : capture 1`) — this is what proved the shape is right — but its DAI declares **S16_LE only** (`arecord -f S32_LE` → "Available formats: - S16_LE"). |
| `google,voicehat` | both directions, **S32_LE** — and **48 kHz only**. With the hub's pin ruling it probes and the card comes up; then ALSA clamps 192 kHz to 48 kHz, the capture overruns by ~1.6 s, and a known word played as `0x00001000` / `0x00010000` / `0x00100000` comes back as the same unrelated constant. |

**THE HUB'S PIN RULING WAS APPLIED AND IT WORKED.** CM4 GPIO17 = CS6 as
`sdmode-gpios` (mx26 `src/hw/d24-hw-pins.csv`) cleared voicehat's
mandatory-GPIO probe failure exactly as ruled — `voicehat-codec
dsp4-duplex-codec: property 'voicehat_sdmode_delay' found delay= 5 mS` and
the card instantiated. It is voicehat's RATE, not its pin, that
disqualifies it. **The rate is not negotiable**:
`shared/dsp4-logic/slot-map.csv` lane A_I6 says LOGIC "regroups 4 Pi frames
per DSP frame", so the Pi frame is 2 slots × 32 bits at **192 kHz**.

**THE FIX IS FORTY LINES OF DAI DECLARATION**, `invirco,dsp4-pcm-dummy`
(`shared/dsp4-logic/pi/dsp4-pcm-dummy/`): playback and capture,
`SNDRV_PCM_RATE_8000_192000`, `SNDRV_PCM_FMTBIT_S32_LE`, no registers, no
control bus, no clocks, no GPIO — so CS6 stays free and the pin ruling is
recorded rather than consumed. Measured after it:

```
/proc/asound/pcm
00-00: bcm2835-i2s-dsp4-dummy-hifi dsp4-dummy-hifi-0 : ... : playback 1 : capture 1
arecord -D hw:dsp4pcm,0 -f S32_LE -c 2 -r 192000
    Recording raw data : Signed 32 bit Little Endian, Rate 192000 Hz, Stereo
```

One device, both directions, no rate clamp, and no over/underrun reported
by either `aplay` or `arecord` across a 96,000-word duplex run.

**FOR `cm4-setup-pi.sh`, UNDER A BENCH FLAG — the exact lines** (this repo
did not edit that script, per the dispatch):

```sh
# 1. the codec module (needs linux-headers; present on the bench image)
cd shared/dsp4-logic/pi/dsp4-pcm-dummy && make
sudo install -D -m 644 dsp4-pcm-dummy.ko \
     /lib/modules/$(uname -r)/kernel/sound/soc/codecs/dsp4-pcm-dummy.ko
sudo depmod -a

# 2. the overlay
dtc -@ -H epapr -O dtb -o dsp4-pcm-duplex.dtbo \
    -Wno-unit_address_vs_reg shared/dsp4-logic/pi/dsp4-pcm-duplex.dts
sudo cp dsp4-pcm-duplex.dtbo /boot/firmware/overlays/

# 3. /boot/firmware/config.txt — one line changes
-dtoverlay=dsp4-pcm-slave
+dtoverlay=dsp4-pcm-duplex
```

Nothing else in `config.txt` changes. The bench was left on the SHIPPING
`dsp4-pcm-slave` line with a backup at `config.txt.pre-duplex-20260908`;
both `.dtbo`s and the module are installed, so the flag is a one-line flip.

**WHAT IS STILL NOT A MEASUREMENT CHANNEL, and it is no longer the
overlay.** With the loop up, a known word played through it comes back
riding a large DC pedestal (~`0x11E7E000`, about 0.28 in Q4.28) and moving
only slightly with the input, so the path is not yet unity: the main chain
(`MIX_MAIN_L → MAIN_FDR → GEQ → COMP → LIM → DLY → ST_OUT`) sums seventeen
sources and none of its nodes was set to bypass. That is step 1 of the
queued block — "pass-through strip, all nodes unity/bypass" — and it is now
the only thing between here and a latency figure.

### S2-8 — `ChanGateHold` and `ChanDelay` FIXED: a wire-unit conversion at the SPI boundary

**Severity: major. Status: FIXED and verified on the part.**

S2-1 recorded the defect; this is the fix, and it is deliberately not a fix
for `Hold`. `defs/common/wire/wire-units.csv` is the LANDED declaration of
what each family carries on the wire and what its kernel word expects, and
`gen_dsp.py` now builds a conversion table from it: any family whose
declared unit differs from its kernel word gets a conversion id, and every
SPI address that family reaches carries it. `_spi_dispatch_cN_convert[]`
sits beside the dispatch and stride tables with the same indexing, and
`spi_handler.asm` applies it. Written as a one-off for Hold, `ChanDelay`
would have stayed broken in exactly the same way — which is how it was
found:

```
  wire-unit conversions applied at the SPI boundary:
    ChanDelay          ms -> samples    32 addresses
    ChanGateHold       ms -> samples    32 addresses
```

**AT THE WIRE, NOT IN THE NODE'S CONTROL-RATE PREP**, and the reason is the
ramp engine: it reads the CURRENT word and interpolates towards the new
one, so a current word in samples and an incoming one in milliseconds makes
every value the ramp passes through meaningless — and the handler's own
up/down test compares the two as floats before that. A unit change belongs
at the boundary where the unit changes.

**BOTH DIRECTIONS.** The read path converts back, so a host reads the unit
it wrote. Without that, save-and-restore — what every probe on this bench
does around a write — would read samples and write them back as
milliseconds. Measured on the part, 2026-09-08:

| cell | written | kernel word | read back |
|---|---|---|---|
| `Chan001GateHold001` | 1.0 ms | `_gate_hold` = **48** | 1.0000 ms |
| `Chan001GateHold001` | 50.0 ms | `_gate_hold` = **2400** | 50.0000 ms |
| `Chan001GateHold001` | 0.0 ms | `_gate_hold` = 0 | 0.0000 ms |
| `Chan001Delay001` | 20.0 ms | `_dly_read_offset` = **960** | 20.0000 ms |
| `Chan001Delay001` | 0.0 ms | `_dly_read_offset` = 0 | 0.0000 ms |

2400 is the generator's own initialiser for `_gate_hold_<nid>` (50 ms at
48 kHz), so the conversion reproduces the value the kernel was written
around. The samples-per-millisecond constant is GENERATED from
`dsp_codegen.SAMPLE_RATE_HZ` into `_spi_dispatch_cN_spms` rather than typed
into the assembler — a conversion that names the sample rate twice can
disagree with itself.

**WHAT IS DECLARED-BUT-NOT-CONVERTED IS REPORTED, NOT SKIPPED**, every
generation:

```
  wire-unit mismatches DECLARED but NOT converted
  (the contract states the mismatch, not the conversion):
    ChanCompAtt   wire 'ms (log table)' -> kernel 'alpha coefficient — needs conversion declared'
    ChanCompRel   ...    ChanGateAtt    ...    ChanGateRel   ...
    ChanMute      wire 'bool 0/1'  -> kernel 'coefficient fold to exact 0'
    ChanPol       wire 'bool 0/1'  -> kernel 'coefficient sign fold'
    Chan_Mtr      wire 'dBFS readback' -> kernel 'Q4.28 fixed via float mirror'
    ChanName      wire 'text' -> kernel 'n/a — host-side only'
    MainComp      wire 'mixed — see per-cell rows' -> kernel 'per-parameter'
```

The four ms→alpha rows say "needs conversion declared" in as many words:
the contract states the mismatch and not the conversion, and inventing one
here would be this spoke declaring cell semantics it does not own. **They
are the next thing the hub can land**, and the mechanism is now waiting for
them — a row plus a rule, no per-cell code. `ChanGateRng` (dB→linear, D39)
and `ChanCompPar` (percent→fraction, D40) are excluded deliberately: the
node's control-rate prep already converts them, and a second conversion at
the wire would apply it twice.

**AUX AND GROUP DELAYS ARE NOT COVERED, and that is the contract's gap
rather than the mechanism's.** `AuxDelay`, `GrpGateHold` and the rest reach
the same class of kernel word and have no row in `wire-units.csv`, so
nothing here converts them. Landing those rows is all it takes.

### S2-9 — the float cascade IS `bq_float_ref` on the part, 0 ULP

**Severity: none — this is the bar the numeric target names, run.**

`shared/numeric-spec.md` states the float arm's bit-exact bar as "SHARC
float cascade ≡ `bq_float_ref`, proved on the part by `bqeverify.sh
float`". It was run on this tree (block 8, image chip1 `adeb3f0c` / chip2
`3c48d892`):

```
ARM A  _bq_fx_cascade_simd  hash 0x7136AFED sum 0xD1246B11
       vs bq_float_ref offset wire 0x7136AFED/0xD1246B11   MATCH
ARM B  _bqfd_cascade_simd   hash 0x3E4B7636 sum 0xD11DDA0E
       vs bq_float_ref direct wire 0x3E4B7636/0xD11DDA0E   MATCH
A vs B: 14810 of 18432 words differ, first at 3, max |d| 22784
        model predicts 14810, first at 3, max |d| 22784     MATCH
        divergence bitmap: part 566 of 576 cells, model 566 MATCH

BQE_VERIFY PASS — 0 ULP over the whole vector set, and the offset
reconstruction is live
```

192 cascades x 4 stages x 3 drive levels x 4 blocks = 18,432 output words
per arm. The bar is two-sided by construction: a one-sided "assert zero
differences" would pass on a rig that never drove anything hard enough to
saturate, so the divergence bitmap is checked cell by cell and the two arms
have to disagree on exactly the 566 cells the model names.

So `EQ_BIQUAD`, `HPF_LPF`, `GEQ`, `CROSSOVER` and `ANTI_FB` have their
KERNEL verified against its normative reference — separately from whether
the graph node runs it, which for the last three it does not (S2-6).

### S2-10 — METER is bit-exact; the family walk's own verdict on it was wrong

**Severity: medium (instrument). Status: fixed, and the earlier verdict
retracted.**

`mtrverify.sh` reads **METER_BIT_EXACT**: the 64-bit meter state reproduces
`fixed_ref.meter_block` exactly, the float readback is peak 0.5 / rms 0.5
at 0.000e+00 relative error, the BLOCK=32 negative control is correctly
rejected and the wide-word control rejects the narrow model.

`dsp4_family_verify.py` had reported `DISAGREES` for METER: `_mtr_peak_
C1_MTR_01` read `0x40E1AFA1` (7.05 as float32) against a captured
post-trim peak of exactly 0.5. **A peak HOLD carries state**, and the
contract sweep that runs immediately before it writes `1.0f` into every rw
cell of the node under probe, which drives the strip close to full scale;
the hold had not decayed by the time the meter was read. 7.05 sitting just
below the Q8.24 ceiling of 8.0 was the tell, and it was not followed.

The lesson is the one this bench keeps relearning in new clothes: a
stateful readback is not a measurement unless the state is controlled.
`meter_phase()` now reports `NO_VERDICT` with the reason and names the
family's real bar rather than scoring a number it cannot interpret, and
`hw_coverage.py` scores a family by a dedicated bar's verdict — with the
bar and the image recorded — where one has been run.

## dsp.csv proposal (2026-09-08)

Session: propose `defs/products/{d24,d32}/dsp.csv` against `defs-v2026.09.08`.
Write-up: `MW/D32/DSP/dsp4-dspcsv-proposal-20260908.md`.

### S1-1 — CLOSED by ruling; four outputs, four strips

PW confirmed the 2026-08-25 main section model mid-session: `Main[1-1]` is the
stereo mix-bus strip and L / R / Ctr / Sub are each a post-crossover OUTPUT
strip. The four chains off `C2_MAIN_XOVER` map to `MainL` / `MainR` /
`MainCtr` / `MainSub` in DAC_13..16 order, `C2_SUB_*` is retired, and the
eight graph nodes that S1 could only report as unnamed now either reach a
strip or say what replaces them. `defs/tools/def_master.py` corroborates the
ruling independently: `MainCtr` is gated on `main.ctr` and the D24-only cell
`Main001Out3Mode001` — an OUT 3 MODE cell — is gated on the same key.

`MainCtr` is emitted for BOTH products at one address; D24 reaches it and D32
lists it out of product scope. That is decision D3's one shared address map
made structural rather than promised: 3,658 cells appear in both proposals
with **zero** address disagreements.

### S1-4 — the meter `taps=` declaration was wrong about what the DSP writes

**Severity: major. Status: fixed.**

A meter node meters ONE tap point and lays `peak` at +0, `rms` at +1, `gr` at
+2 and its own state array at +3. `taps=` therefore names meter WORDS, and
reading it as tap points produced two wrong cells:

- `taps=L;R` on the four mono main-output meters made the RMS word into an
  `R` channel, giving each output strip an `Mtr002` no master defines (two of
  the 23 orphans S1 found). The word keeps its dispatch entry — the host can
  still read it — and loses only the cell.
- `Chan*CompMtr001` (32 cells) was addressed at base+3, which is
  `_mtr_st[0]`, the meter's internal peak-hold state. A cell pointed at
  another variable's scratch is not reaching a DSP address; CompMtr is now
  listed as `unbacked-meter`. This is the read side of recorded defect 4:
  `gate_gr` is declared and never written, `comp_gr` has no word at all.

### S1-5 — `_parse_taps`: `parse_params()` splits on the tap separator

**Severity: major (would have been silent). Status: fixed in the same change.**

The first rewrite of `expand_meter` read the declaration with
`parse_params()`, which splits on `;` — the character that also separates the
taps. `taps=post_trim;post_fader;gate_gr;comp_gr` came back as
`{'taps': 'post_trim'}` and three of the four channel-meter words vanished
without a warning. Caught by the cell counts, not by a test. `_parse_taps()`
reads to the end of the params or the next `key=`.

### S1-6 — the post-crossover output strips have no fader, mute or delay

**Severity: major. Owner: PW / capacity. Status: open (Q1).**

All four output strips define `Level`, `Mute` and `Delay`; chain N in the
graph is EQ + COMP + LIM only. Twelve cells across the four strips reach no
word. Retiring `C2_SUB_*` makes this visible on `MainSub`, which had those
addresses through the sub bus strip; `MainL`, `MainR` and `MainCtr` never had
them. Closing it is four `FADER_PAN` and four `DELAY` nodes on chip 2, which
is the tighter part at 83.16% — a capacity decision, not a desk one.

### S1-7 — `CtrOn` and the retired sub bus cannot both be right

**Severity: major. Owner: PW. Status: open (Q3).**

Every channel defines `CtrOn[1-1]` — on D32 too, which has no `MainCtr` — and
its DSP word is `_rtg_sub_on_<nid>`, a per-channel assign to the `BUS_SUB`
mix bus that feeds the strip the ruling retires. If there is no centre/sub
mix bus, `CtrOn` has no destination; if `CtrOn` is real, that bus is real and
outputs 3 and 4 are not simply crossover taps. The cell keeps its address in
the proposal; one of the two has to give.

### S1-8 — D24's legacy SHARC graph is not a second address map

**Severity: minor (a trap avoided). Status: recorded.**

`MW/D24/DSP/SHARC/dsp.csv` is 201 nodes with no faders, routing, aux, groups,
meters or crossover. Deriving D24's addresses from it would have produced
exactly the second address map D3 forbids. D24's proposal is derived from the
superset DSP4 graph and filtered by D24's own cell set. The legacy file's
three `dsp_validate` parameter errors were fixed in place
(`source_gains` → `source_count`, `wet`/`dry`/`width` → `mix`); both product
files now validate clean.

## defs S1 (2026-09-08)

Session: adopt the `invirco/defs` submodule at `defs-v2026.09.08`, retire the
dsp-side expander and back-fill. Write-up:
`MW/D32/DSP/dsp4-defs-s1-20260908.md`.

### S1-1 — the graph has four main outputs and the product definition has three

**Severity: major. Owner: dsp.csv (the next dispatch). Status: open, now loud.**

This is review finding **D52** and S1 makes it visible instead of resolving it.
`defs-v2026.09.08` models the main section as one L/R bus strip (`Main001`:
fader, mute, DCA, 250 ms delay, 28-band GEQ, cue) plus **three** post-crossover
output strips — `MainL001`, `MainR001`, `MainSub001`, each with its own EQ,
compressor, limiter, delay, fader, mute and meter. `MW/D32/DSP/SHARC/dsp.csv`
builds **four** post-crossover chains off `C2_MAIN_XOVER` (DAC_13..16) plus a
separate sub-bus strip `C2_SUB_*` out to NET_OUT_01.

The consumer-side mapping now says exactly what it can defend and reports the
rest:

- `C2_SUB_*` → `MainSub001`. The master row notes came across verbatim
  ("Subwoofer compressor attack", "Subwoofer output level meter"), so the
  standalone `Sub` category was folded into the main section, not deleted.
- `C2_MAIN_O{EQ,COMP,LIM}_01/02`, `C2_MTR_MAIN_01/02` → `MainL001`, `MainR001`.
- `C2_MAIN_O{EQ,COMP,LIM}_{03,04}`, `C2_MTR_MAIN_{03,04}` → **nothing**. Eight
  graph nodes hold SPI addresses the DSP will answer on and no cell in the
  product definition names them. `gen_dsp.py` lists all eight by id and type.
- `C2_MAIN_COMP` and `C2_MAIN_LIM` (the main BUS dynamics) emit 21 cells the
  masters no longer carry: output dynamics moved onto the per-output strips.
  With `MainL001Mtr002`/`MainR001Mtr002` — the L;R meter taps on what is now a
  mono output strip — that is the 23 cells `validate()` reports as not in
  `_matrix.csv`.
- `MainL001Level001`, `MainL001Mute001`, `MainL001Delay001` and their `MainR`
  and `MainSub` twins are documented and unimplemented: the graph has one main
  delay and one main fader, not one per output strip.

**Why it was not fixed here:** the S1 dispatch bounds the session out of
dsp.csv authoring ("that is the next dispatch: dsp proposes `dsp.csv`, hub
lands it at the gate"). Choosing three chains over four, or giving each output
strip its own fader and delay, is a product decision with a cycle cost, not a
naming fix.

### S1-2 — two families the prune step called aliases are definitions again

**Severity: minor. Owner: hub (defs). Status: open, reported.**

`alias-retire-families.txt` deleted eight families from every expansion up to
`defs-v2026.08.20`, on the reading that they were compatibility aliases.
`defs-v2026.09.08` carries two of them:

| formerly pruned | D32 rows now | alongside |
|---|---:|---|
| `FxDuckThr` | 6 | `FxDuckSens` (6) |
| `PeqGain` | 12 on `MainL`, 12 on `MainR` | `Main001Geq[1-28]` |

Neither reaches a DSP address. They may be intentional (a per-side output PEQ
is a real feature; a duck threshold and a duck sensitivity are not obviously
the same control) or they may be the alias the July prune thought they were.
`defs` is the source of truth either way, so this repo carries them and says
so rather than deleting them again — deleting rows from the expansion and
renumbering `MxAdd` behind them is what made this repo a second source of
truth in the first place. Tracked in `alias-audit.md`.

### S1-3 — the H1S1 dispatch map was missing 2,064 cells and nothing said so

**Severity: major, and closed by this session. Owner: dsp. Status: fixed.**

`mx_dsp_map.h` keys matrix rows to `ghost_cells[]` indices **by cell name**.
Under the old pin the ghost table spelled the current master names
(`Chan001Mute001`) while `_matrix.csv` spelled the pinned ones
(`Chan001RtgMute001`), so those rows silently produced no map entry: the map
held 3,417 entries against 5,481 ghost cells, and `DspDispatch()` could not
reach a routing cell at all. `gen_dsp.py` reported the split as an INFO line
about legacy-spelling hits, which is a true statement that does not read as
"the MCU cannot dispatch to a third of the table".

One spelling closes it: the map now carries **5,393** entries. Nothing in the
DSP image changes (the dispatch tables key on `dsp.csv` node ids, not on cell
names, and all four W0 witnesses rebuild byte for byte), and **H1S1 was not
rebuilt in this session** — the fix is proven in the generated header, not on
an MCU.
