provenance: AI-drafted 2026-09-08 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# findings — dsp spoke

Numbered findings D1–D8x are recorded in `review-dsp-20260828.md` and in the
dispatch blocks of `tasks.md`. This file carries findings raised by dispatched
sessions after that review, newest first.

## The channel and aux masks get readers (2026-09-09, session 32)

Session: `CFG_CHAN_MASK` / `CFG_AUX_MASK` given readers, D24 capacity
restated on the masked image, the through-DSP arm attempted again.
Write-up: `MW/D32/DSP/dsp4-chan-mask-20260909.md`. Contract
`defs-v2026.09.08.4`, unchanged. New images: chip1
`093c609f622cf805e7f675f1e2497a19` / chip2
`2ba0e464e9679bd2e1b1c3c2a6f08744`; `DSP4_CHAN_MASK=0` rebuilds the
previous pair `602a0feb` / `b1325022` byte for byte.

### S6-1 — S5-7 fixed: the masks are read, and a masked strip is SKIPPED

**Severity: MAJOR (firmware, window item). Status: FIXED and measured.**

`_chan_mask` and `_aux_mask` are latched into `_chan_mask_live` /
`_aux_mask_live` at CONFIG_COMMIT and read by the process chain, which
skips a masked strip's or aux's nodes rather than running and silencing
them. Gating is per RUN (one compare, one branch) on the pattern
`_product_id`'s scope gate already set; a SIMD pair runs if either half
is live, and the masked half is made inaudible by its own ROUTING gate
and a zeroed crosspoint column instead.

Measured on the part, one bitstream (`_maincap`), one night, nothing
playing, `C2_MAIN_ST_OUT` over 48,000 frames:

| image | config | result |
|---|---|---|
| `602a0feb`/`b1325022` (= `DSP4_CHAN_MASK=0`) | D24 | `0x7FFFFF88` on 48,000 of 48,000 |
| `093c609f`/`2ba0e464` | D24 | **`0x00000000` on 48,000 of 48,000** |
| `093c609f`/`2ba0e464` | D32 | `0x7FFFFF80` on 48,000 of 48,000 |

The D24 row holds with NOTHING silenced and with all 48 silenceable D24
cells written. The D32 row is the positive control: D32 behaviour is
unchanged. `famverify` on the fixed image is the `.4` line unmoved —
17/20 families, 3,619 of 3,737 cells, GEQ 31/31, CROSSOVER 8/8, 0 FAILED.

`tools/pi/dsp4_silence_2532.py`, the workaround that silenced strips
25-32 through D32's rows, is deleted per its own docstring.

### S6-2 — the D24 aux mask the host sent was wrong, and inertly so

**Severity: minor (host). Status: FIXED.**

`dsp4_config.py` sent D24 `CFG_AUX_MASK = 0x0FFF` — twelve aux buses.
`defs/products/d24/dsp.csv` addresses `Aux001`–`Aux008`; D32's addresses
`Aux001`–`Aux012`. Harmless while nothing read the word; four live aux
chains the moment something did. Now `0x000000FF`. **A word no reader
consumes is not checked by anything**, which is the general form of both
this and S5-7.

### S6-3 — the D24 load was never a D24 load, and the reverb margin was never 5.34 %

**Severity: MAJOR (capacity). Status: measured.**

Block 16, 983.04 MHz, budget 327,680, two boots, minimum, both arms in
one session on one instrument:

| arm | cycles/block | margin |
|---|---:|---:|
| chip 1 control / **masked** | 262,033 / **202,786** | 20.03 % / **38.11 %** |
| chip 2 control / **masked** | 261,856 / **226,442** | 20.09 % / **30.90 %** |
| chip 2 masked, six reverbs | **275,035** | **16.07 %** |

The controls reproduce the `.4` record to 8 cycles (chip 2) and 154
(chip 1), so the differences are the fix and not the day. **Chip 1 — the
tighter chip — gains 18.08 % of its budget**, because it carries the
strips. Chip 2 gains 10.81 % from four aux chains.

The consequence for the product: the six-reverb worst case, which the
2026-09-08 record put at 94.66 % / **5.34 % margin** and which was
written up as a product decision inside the 10 % bar, is **83.93 % /
16.07 %**. It was 5.34 % because the part was running four aux chains and
eight strips the product does not have. The reverb's own cost did not
change (+49,187 here against +49,096 on 09-08).

### S6-4 — S5-10 narrowed: the DSP carries the audio, the CAPTURE PATH loses the order

**Severity: major (instrument, CPLD-side). Status: mechanism named, not fixed.**

The through-DSP arm still does not close and **no latency figure is
quoted**, but the mask was not the reason and the symptom is now named.

A CONSTANT through Pi → CPLD → DSPA → fabric → DSPB → CPLD → Pi returns
**bit-exact** (`0x00123400` on 143,400 of 144,000 frames played). A
STAIRCASE (1,500 values, 64 frames a step, `tools/pi/dsp4_order_stair.py`)
returns every value — index range 1..1500 complete, 96,040 non-zero words
for 96,000 played — as **82,042 runs where a clean loop gives 1,500**:
86 % of runs are one frame long and only 8,141 of 81,351 transitions are
+1. Interleaved values sit within a window of hundreds to thousands of
steps and the window width is not fixed.

That is a capture path not frame-locked to the CM4 capture DMA. It is a
property of the `_maincap` instrument (`o_dspb[3]` slot 0), not of the
DSP: `_pisel` closes the same loop inside LOGIC and returns 48,000 of
48,000 counter words at ONE offset. `dsp4_loop_latency.py`'s
14,494–14,509 for this arm has **5.67 % counter agreement** across ~2,780
distinct offsets with the impulse never found — a spurious mode, recorded
so it is not mistaken for a measurement.

Closing it needs a frame-locked capture: a CPLD-side change to the
`_maincap` re-framer, or a DSP-side capture buffer read over the
parameter link, which sidesteps ALSA. Neither blocks the window.

### S6-5 — the first cut of the fix did not fit chip 1

**Severity: major (program memory). Status: FIXED.**

Gating every run exactly, with `_mask_apply` unrolled per strip and per
aux, overflowed chip 1's `sec_swco` by **622 words** in the block-16
paired build — the configuration every capacity number is taken in. The
shipping per-sample image linked either way, so the window was never
blocked, but a fix that does not fit the operating point is not a fix.

Brought to about 230 words by three changes, none of which alters what is
skipped for any mask a product sends: `_mask_apply` made table-driven
(one loop over strips, one over a (pointer, bit) table for the aux
buffers); the chain's gate reduced from four instructions to three by
resolving one word per gate group into `_mask_on[]` at commit; and
adjacent runs merged where neither side has to be gated exactly, with
standalone METER runs — which emit nothing under block kernels — not
gated there at all. Chip 1: **124 gates to 61**.

**Chip 1's program memory is the binding constraint on this chip**, and
it is the third time it has bitten (S5-6's `bqeverify` arms, the
`dyn_selftest` in every paired build, this). Worth a dispatch of its own
before the next feature lands in the chain.

## The CM4 loop at 48 kHz, and the product-config word nothing reads (2026-09-09, session 31)

Session: PI_TDM8 bitstream from the current slot map, flashed via JTAG,
the CPLD duplex loop's latency at 48 kHz. Write-up:
`MW/D32/DSP/dsp4-loop-latency-20260909.md`. Contract
`defs-v2026.09.08.4`. Images unchanged: chip1 `602a0feb` / chip2
`b1325022`. Bitstreams built tonight from slot map
`sha256:4ecc4aa221a0787e…`.

### S5-7 — `CFG_CHAN_MASK` is stored and never read, so a D24 runs 32 strips

**Severity: MAJOR (firmware, window item). Status: FIXED 2026-09-09 — see S6-1.**

`tools/pi/dsp4_config.py` sends D24 `CFG_CHAN_MASK = 0x00FFFFFF`
("strips 25-32 NET-only"). `product_config.asm:121` stores it in
`_chan_mask`. Nothing reads `_chan_mask` — four references in the whole
tree: `.global`, the `.var` initialiser, `.extern`, and that one write.
All 32 strips therefore run on D24 and all 32 sum into `C2_RECV_MAIN_L`.

Measured on the part, block 8, conformance images. With everything the
D24 contract can silence silenced (32 strips attempted, the four groups,
USB, BT, CodecAux) AND the Pi input off, `C2_MAIN_ST_OUT` sits at
positive full scale `0x7FFFFFE0` for 48,000 frames of 48,000, with
nothing playing. Writing `MainOn=0`/`Mute=1` to exactly strips 25–32 —
through D32's rows for the same cells, the address map being shared per
decision D3 — takes it to `0x00000000` for 48,000 of 48,000.

The contract is NOT at fault: D24 is a 24-channel product, its matrix
has zero `Chan025` cells and `d24/dsp.csv` correctly carries none. The
firmware is running eight strips the product does not have.

This is what made every previous attempt at the loop measurement
unusable, including the 2026-09-08 note that "the loop still carries a
DC pedestal until the main chain is set to unity" — it is not a pedestal
and it is not the main chain.

`_aux_mask` has the identical shape (`product_config.asm:124`, no
reader). `_out_mux` likewise, and that one is already acknowledged in
the host tool. Of the four product-config words only `_product_id` has a
reader.

### S5-8 — the artifact hash covered every macro; the artifact NAME did not

**Severity: moderate (build hygiene). Status: FIXED this session.**

The 2026-09-08 fix put every macro into the bitstream hash and the
manifest's `config:` line, which stopped two different builds colliding
on one filename. It left the label wrong: a `PI_TDM8=1` build still came
out named `dsp4_logic.<hash>` — indistinguishable at a glance from a
shipping artifact — with `SHIPPING: yes` in its manifest, even though
`build.sh`'s own comments call PI_TDM8 non-shipping. The one line a
human reads at the bench said the opposite of the truth.

`build.sh` now folds every non-shipping switch into BOTH the artifact
name and the `SHIPPING:` line, each with its reason. Proof it changed
the label and not the bits: `build.sh` is not an input to `SRC_HASH`
(slot map + config line + RTL + qsf + sdc are), the rebuild produced the
same hash `83778a06f954`, and two consecutive builds gave the identical
pof md5 `1c556d38ed76c1cdd1190513c5447de4`.

### S5-9 — the LOGIC design has no ID register, so "which bitstream is running" costs a measurement

**Severity: minor (verifiability). Status: recommendation, not done.**

Gate 2 asked for the running hash off the part. There is nothing in
`rtl/` to read back and MAX V configuration readback is not available
over the SVF path, so identity had to be established behaviourally:
`a1f6672af6c3` captures all zeros (`pcm_din` tied to `1'b0`), `_pisel`
returns the Pi's own playback bit-exact, `_maincap` tracks
`MAIN_ST_OUT` under mute and level. That is sound but indirect and costs
a capture per flash. A few bits of design ID on the TEST pins or over
the parameter link would replace it with one read. Not done tonight:
adding it changes the RTL and therefore every bitstream hash.

### S5-10 — the Pi → DSP → Pi pass-through does not deliver a coherent stream

**Severity: major (open). Status: narrowed further 2026-09-09 — see S6-4. The
mask (S5-7) was NOT the reason; the capture path is.**

With S5-7 worked around and the main bus proven silent, the through-DSP
arm still returns mostly zeros with sparse out-of-order counter indices
(5, 5, 16, 18, 35 over 40 consecutive frames). **No latency figure is
quoted for it.** The harness's 14,550-sample offset for this arm is a
spurious mode — 2,878 of 48,014 candidate words agreeing, across 44
distinct offsets, impulse never found — and is recorded only so it is
not mistaken later for a measurement.

Excluded so far: the capture path (it tracks `MAIN_ST_OUT` under mute
and level); the graph being stopped (`_dly_write_ptr_C2_MAIN_DLY`
advances, `FRAME_COUNT` 5,999/s against 6,000/s expected for block 8,
`BOOT_STAGE 7`, `SPORT0_ERR_A 0`); the new slot map (chip 1 RX lane 6 is
still `CS 0x0003`/2 words, chip 2 TX lane 3 still `CS 0x0003`); and the
main bus not being silent. `dsp4_audio_verdict.py` cannot settle whether
the block loop keeps up because `_proc_passes` is absent from these
images — "no pass rate available" — which is the next thing to fix, since
it is the one instrument that would answer it directly.

### S5-12 — the order soak reported a pass criterion it had quietly missed

**Severity: minor (instrument). Status: FIXED this session.**

`dsp4_order_soak.py`'s stimulus generator paced itself at
`RATE // CHUNK` chunks per nominal second. `48000 // 4096` truncates to
11, so it delivered 45,056 samples per second: a 630 s request ran 591 s
while every line of the report still said 630. Zero defects either way,
but a ten-minute gate would have been missed by nine seconds and the
output would not have said so. Fixed to count in samples, and the pass
criterion now checks the word count against the requested total.

### S5-11 — the current slot map adds ten slots and moves none, and the DSP never sees them

**Severity: informational (contract question answered). Status: closed.**

Gate 1 asked whether a TDM8 build from the current slot map is a contract
change. It is not. Against the previous map the 2026-08-23 CM4
allocation adds `A_I6` slots 2–7 and `B_O3` slots 4–7, all previously
unassigned, and every pre-existing (line, slot) → signal pair is
byte-identical. The generated lane tables confirm the DSP side is
untouched: masks come from where nodes exist, and only `PI_PCM_L/R` and
`PI_RET_L/R` have them. The panel MCU is an SPI parameter host and does
not see TDM slots at all.

## The 31-band GEQ, the crossover slope, and the chip-2 re-layout (2026-09-09, session 30)

Session: confirming the DSP code against the latest known matrix. Write-ups:
`MW/D32/DSP/dsp4-geq31-relayout-20260909.md` and
`MW/D32/DSP/dsp4-window-readiness-20260909.md`. Contract
`defs-v2026.09.08.4`. Images: shipping float configuration, chip1
`602a0feb` / chip2 `b1325022`.

### S5-1 — the 31-band GEQ moves 1,192 D24 / 1,460 D32 addresses, and every host cache with it

**Severity: major (contract). Status: landed as `defs-v2026.09.08.4`.**

A GEQ node's SPI block is exactly its band count and chip 2's allocator
packs blocks end to end, so the three bands `.3` added to seventeen nodes
are +51 words and every chip-2 block above the first GEQ slides. Chip 1
does not move. This is the first time this contract has MOVED an address
rather than added one, and a host on the old map writes an aux limiter
threshold into an anti-feedback notch with every address answering. The
panel MCU headers and the app must be rebuilt against `.4` in the same
window as the firmware.

### S5-2 — `gen_dsp.py` kept the GEQ band count as a hand-maintained constant

**Severity: major (generator). Status: fixed — `resolve_geq_bands()`.**

`MW/D32/DSP/gen_dsp.py` carried `GEQ_BANDS = 28` beside a graph whose
nodes said `bands=28`, and the two agreed because someone remembered. The
band count is a market parameter (`gen_dsp_csv.py --geq-bands`), so the
moment the graph moved to 31 the constant would have addressed 28 words
of a 31-word block and the three bands past the end would have been
silently unmapped. It is now READ OFF THE GRAPH, and a graph whose GEQ
nodes disagree with each other stops the generator.

### S5-3 — `gen_dsp.py --propose` was unreachable in the one case it exists for

**Severity: major (process). Status: fixed.**

The fatal drift check sat ABOVE the `--propose` branch in `main()`, so
every run that had a new `dsp.csv` to propose — which is exactly a run
where the graph disagrees with the landed file — died before reaching the
flag. The propose path now authors first and takes the drift verdict as a
value, generating nothing while the graph is ahead.

### S5-4 — the LR2 crossover does not sum flat without inverting the highpass

**Severity: major (design). Status: fixed in `xover_ref.py` and
`xover_design_fx.asm`, verified on the part.**

The 09-08 proposal specified slope 12 as "the same five offset formulas
with 1/(2Q) at 1.0 and the second stage written as the identity". That
designs a correct pair of 2nd-order sections, each 6.02 dB down at the
corner — and their sum NULLS there, measured at −242 dB on the model,
because at 2nd order the two paths are 180 degrees apart. Every 2nd-order
Linkwitz-Riley is specified with one path reversed. The highpass is now
inverted at slope 12, which in the offset encoding is a sign flip on `b0`
alone (`n1` and `n2` are zero and stay zero). `xover_ref.check()` scores
the corner and sum properties at BOTH slopes now; scoring only 24 is what
let this through.

### S5-5 — `dsp4_geq_verify.py` hard-coded 28 bands and scored 28 of 31 as a pass

**Severity: minor (instrument). Status: fixed — the band count is
counted in the landed map, and a hole in the numbering stops the run.**

The first run against the 31-band contract reported `GEQ_DESIGN_OK` with
`bands: 28` in its report. Bands 29–31 were addressed, answering, and
never written.

### S5-6 — `bqeverify`'s fixed/shootout arms do not link, and it pre-dates this session

**Severity: minor (instrument). Status: filed, not fixed.**

Under `DSP4_BQ_SHOOTOUT=1 DSP4_BQE_VERIFY=1` chip 1's `sec_swco`
overflows by 604 words. Rebuilt at the previous commit (`e278667`) the
same arm overflows by 386, so it was already broken; this session's
crossover work accounts for the 218-word difference. The shipping image
is unaffected and links with 85,330 words of chip-1 code free. The FLOAT
arm — the shipping cascade — builds and passes at 0 ULP.

## FX engine and anti-feedback (2026-09-08, session 29)

Session: the queued FX/ANTI_FB block. Write-up:
`MW/D32/DSP/dsp4-fx-afb-20260908.md`. Images: shipping float
configuration, chip1 `85af9dce` / chip2 `bcdbe1f0`; the block-16
measurement tree is chip1 `160d8863` / chip2 `02e38fa8`.

### S4-1 — chip 2's margin with the FX reverb running is 5.98 %, measured

**Severity: major (capacity, PW's #1 priority). Status: measured, and it
replaces the projection.**

`fxcost.sh`, whole chip-2 graph, block 16, two boots, minimum, paired on
one boot with a restore-and-re-read control:

| arm | cycles/block | % of 327,680 |
|---|---:|---:|
| six engines at the landed default (Type 0, unimplemented, dry) | 249,231 | 76.06 % |
| six engines at Type 3 = Reverb | 308,076 | **94.02 %** |
| difference | **+58,845** | +17.96 % |

Control (restore − default): **+93** and **+10** cycles on the two
boots, against a delta of 58,845. The 09-08 projection was ≈ +56,300 and
≈ 93.6 %: **sound and 4.5 % optimistic.** On the FIXED tree, where the
default is a real Echo, the same measurement is **305,259 = 93.16 %,
margin 6.84 %** — see S4-6. **Either way it is under ten per cent, which
is the sentence the dispatch asked for.**

### S4-2 — the FX engine destroyed its own dry input, in every algorithm

**Severity: major. Status: FIXED and verified on the part.**

`f15` holds the dry sample; every algorithm advanced its delay-line
cursor with `r15 = 1; r1 = r1 + r15`, and `r15` IS `f15`. The saved dry
signal became the integer 1 — as float32, 1.4e-45 — so the mix
epilogue's `f1 = f15 * f8` multiplied the dry path by zero, and the
reverb's comb loop fed the input to the FIRST comb and denormal noise to
the other seven.

**It looked like a working pass-through** because Type 0, the landed
default, fell through to `.fx_passthru_` — the one path in the node that
touches no integer scratch, so the dry survived there and nowhere else.
Every increment is `r1 = r1 + 1` now: one instruction instead of two,
and it does not alias a float.

### S4-3 — and its write pointer, with the sample it had just read

**Severity: critical (it wedges the part). Status: FIXED and verified.**

`f1 = dm(_fx_feedback_)` in ECHO / PING-PONG / FLANGER, and
`f1 = dm(i0, 0)` in the reverb's comb and allpass loops, both overwrite
`r1` — the write pointer — with a float.

* In ECHO the pointer became the feedback coefficient's bits. At the
  landed feedback of 0.0 that is `0x00000000`, so **every sample was
  written to `buf[0]`, the cursor stuck at 1, and the tap read a part of
  the line nothing had ever written**. Measured: Type 0, Mix 1.0, delay
  240 — peak **0.000000** over 1024 samples.
* In the REVERB the clobbering value is AUDIO. A float32 sample's bits
  are about 1e9, and the loop stores that back into
  `_fx_rv_comb_wptrs` and uses it as an offset next block: **every comb
  wrote at `comb_buf + 1e9` and the SPI link stopped answering.**

**S4-2 HID IT.** While the dry input was being destroyed the comb lines
held only zeros, whose bits are `0x00000000` — a pointer of zero, in
range, every block. **The reverb could not crash because it could not
carry a sample.** Fixing S4-2 made it carry one and it wedged the bench
on the first capture. The delayed sample lives in `f9` now, and the bar
reads all eight write pointers off the part and checks they are inside
their own lines.

### S4-4 — three more FX defects, all in the generator

**Severity: major. Status: all FIXED.**

1. **No L register.** `_C2_FX_ENG_NN_process` used `modify(i0, m0)` on
   four buffers and post-modify on four table walks and set no length
   register — alone among every kernel in this tree. It survived only
   because `C_RUNTIME_INIT` zeroes `l0..l15` and nothing on chip 2
   writes one; the chip-1 DLY nodes DO, D70 measured the boot kernel
   leaving `l6 = l7 = 0x2FF`, and both ISRs run on the secondary DAG.
2. **Doubling read 720 samples out of an eight-word buffer** with a wrap
   of 8 — 711 words before the array. The line is 12,000 words (250 ms)
   now and the Echo delay is CLAMPED into it: the contract's 1000 ms is
   48,000 samples, six engines of that is 1.15 MB, and 364 kB were free.
   **It costs nothing net** — `_fx_comb_buf_R` and `_fx_allpass_buf_R`
   were allocated at full size (12,587 words an engine, 75,522 across
   the six) and **no emitted instruction read or wrote either**. The
   delay pool goes 1,708,216 → **1,694,112 bytes**.
3. **`_buf_L` carried float32 while `_buf_` carried Q4.28** — the store
   ran before the fixed-point conversion. Nothing reads either (checked
   across all 724 assembly files); both now carry the published word.

### S4-5 — the landed default was not an algorithm, and the fall-through was silent

**Severity: major. Status: FIXED and verified.**

`_fx_type` boots at 0 = Echo and the reverb class emitted no Echo case,
so the default fell through dry — **which is the state every capacity
number since 09-03 was measured in**. Echo is implemented; Types 1, 4, 5
and 6 now take an EXPLICIT bypass that parks the Type in
`_fx_bypassed_<nid>`, because a silent fall-through is
indistinguishable on a capture from an engine that ran and had nothing
to do, and that is how this went four sessions unnoticed.

The node header has always printed `/* Default type: Reverb */` — the
graph declares `type=Reverb` — while the `.var` was hardcoded to 0.
`DSP4_FX_TYPE_DECLARED=1` boots at the declared Type. **It is a flag and
not the default because of what it costs (S4-1), and which Type ships is
a capacity decision.**

### S4-6 — what each FX algorithm costs at block 16

**Severity: informational (capacity). Status: measured.**

Same instrument, on the fixed tree, against the explicit bypass:

| six engines at | cycles/block | % of 327,680 | over the bypass |
|---|---:|---:|---:|
| explicit bypass | 251,322 | 76.70 % | — |
| Echo (the landed default) | 256,359 | 78.23 % | +5,037 |
| Doubling | 254,833 | 77.77 % | +3,511 |
| Reverb | 305,259 | **93.16 %** | +53,937 |

**Making the engine honest costs the shipping image +7,128 cycles/block,
2.18 % of budget** — 76.06 % → 78.23 %, margin 23.94 % → 21.77 %. About
5,000 of that is Echo running and about 2,100 is the L-register
initialisation and the bypass book-keeping.

### S4-7 — a 32-sample window cannot see a reverb, and that is half of "peak zero"

**Severity: minor (instrument). Status: fixed in the bar.**

The Freeverb comb lengths are 1116–1617 samples and there is no direct
path from input to output — the wet signal IS the comb read — so the
first reverberant sample arrives 1116 samples after the impulse. The
2026-09-08 family walk scored `FX_ENGINE` over a **32-sample** window
and the scope buffer is 1024. **A window thirty-five times too short
cannot see a reverb even when the reverb is perfect.** `fxverify.sh`
drives a step and arms twice a handshake apart, fetching only the second
window: the fetch is the slow part, and half a second of rest is 24,000
samples, by which time a comb with 0.6 of feedback has been round its
line fifteen times.

### S4-8 — ANTI_FB: the parameters landed, the switch was unread, nothing designed

**Severity: major (it was the family walk's only FAIL). Status: FIXED
and verified on the part.**

The GEQ's disease on a third node. Eighteen parameter addresses always
dispatched to the right symbols — 1000.0 Hz, −18.0 dB and Q 4.0 read
back off the part — and nothing turned them into coefficients;
`_afb_on` took its write and was read by no emitted line.

The design is on the DSP (`src/lib/afb_design_fx.asm`, modelled by
`tools/dsp/afb_ref.py`), because eighteen addresses cannot also carry
thirty coefficient words and a swap trigger. **A notch here is RBJ
PEAKING at negative gain**: `AntiFbNotchGain`'s domain is
`0=-18/127=0`, so the depth IS the parameter, and a textbook notch has
no depth parameter. Nothing is a per-notch constant — frequency and Q
both move — so `sin w0` and `1 − cos w0` are computed on the part over
x ∈ [0.00524, π/2], the versine from its own degree-5 fit in x² because
at 40 Hz `1 − cos x` is 1.4e-5 against a cosine of 0.9999863.

`afbverify.sh`: worst **4 ulp** over five parameter vectors, response
worst **0.00009 dB** against a 0.05 bar, 1 kHz Q 8 at −18 dB measured
**−18.000 dB** against a model of −18.000, and both negative controls —
`AntiFbOn = 0` with six real notches written, and On with every gain at
0 dB — **64/64 samples equal to the input**. **`ANTI_FB` moves from the
family walk's only FAIL to PASS.**

**`AntiFbCtrlOn` is still read by nothing, deliberately.** It enables an
automatic feedback detector and no detector exists in this firmware;
wiring it to the design would make an empty switch look implemented. It
is not in the recompute run, and the kernel and the write-up both say
so.

### S4-12 — the family walk's own stimulus stops reaching its own captures

**Severity: major (it is the coverage instrument). Status: OPEN, with a
named next step.**

`famverify.sh` on this image reads `audio SILENT` for `GEQ`,
`CROSSOVER`, `ANTI_FB`, `FX_ENGINE`, `ROUTING`, `LIMITER` and
`TUBE_SAT`. Scored by `hw_coverage.py` with the four dedicated bars
given as external verdicts, the previous session's golden is **17 of 20
families / 3,580 of 3,698 cells** and this session is **7 of 20 / 753**.

**It is reproducible and it is not the graph.** Two independent runs,
each with its own boot and config ladder, produced family-for-family
identical verdicts. On the SAME image: `afbverify.sh` drives the SAME
injection symbol (`_rx_ic_slot_C2_RECV_AUX_01`) into the SAME aux chain
and reads 64/64 samples equal to the input plus a −18.000 dB notch;
`fxverify.sh` reads a 0.500000 impulse through the FX chain; `busgold.sh`
is **bit-exact over 256 bus words**. A capture that carries no stimulus
is not a verdict about a node, so **this session's family count is not
restated as progress and is not usable as a regression either.**

Next step: diff the walk's inject/arm/capture ordering and its setup
writes against `dsp4_afb_verify.py`, which reaches the same nodes
through the same symbol on the same image and does not go silent. The
strip-1 `CFG_COMMIT` repair (`gainfix.py`) is the first suspect — a
chain whose input gain is 0 is silent all the way down, and `busgold.sh`
logged strip 1 at `0x00000000` and repaired it in this same session.

### S4-9 — the CROSSOVER node's dispatch block overlaps the EQ that follows it

**Severity: minor, and it is what makes the slope proposal free. Status:
recorded, not changed.**

`expand_crossover` claims `base+0 .. base+23` — twenty-four words — but
`C2_MAIN_XOVER` sits at 1397 and `C2_MAIN_OEQ_01` at **1401**. Because
`expand_eq_biquad` runs later and `add_dispatch` is a dict assignment,
the EQ silently wins from `base+4` on. The crossover actually owns
**four** words, of which 0x0576–0x0578 dispatch to nothing.

Nothing is broken by it today — a write to an unmapped address raises an
SPI error, which is the correct answer — and it is what lets
`CrossoverSlope` take 0x0576 with no address anywhere moving. It is
recorded because a node whose expander claims six times the space it has
is a trap for the next person who adds a parameter to it.

### S4-10 — `defs-v2026.09.08.3` cannot be consumed: the cells landed without their unmapped rows

**Severity: major (it blocks the 31-band GEQ). Status: OPEN, and it is
the hub's.**

The tag lands `Geq[1-31]` in the cell master (D24 4,946 → 4,985,
fingerprint `3d41d5850df3`) and **touches `products/<p>/` not at all**.
The pin was advanced here and reverted, for two errors in sequence:

```
ERROR: cell 'Aux001Geq029' (Aux/Geq) reaches no DSP address and
       _UNMAPPED_REASONS in gen_dsp.py does not say why.
ERROR: d24/dsp-unmapped.csv cell set disagrees with the graph —
       39 the graph proposes and the landed file lacks
```

**The first is this repo's and is fixed here**: `GEQ_BANDS` is one
constant that both the expander and the reason read, and the reason
matches on the BAND NUMBER rather than the family, so a band inside
1–28 that ever stopped reaching an address would still stop the
generator — which a family-wide `('Aux', 'Geq')` entry would have
hidden.

**The second is not.** `products/<p>/dsp-unmapped.csv` is a landed file;
39 D24 cells (51 on D32) were added to the master without the rows that
account for them, and this repo cannot write them — `check_proposal()`
runs BEFORE `--propose`, so once the graph and the landed file disagree
the generator will not emit the proposal that would close the gap
either. **`defs-v2026.09.08.3` needs `products/{d24,d32}/
dsp-unmapped.csv` regenerated and landed with it.** Until then the pin
stays at `.2` and `Aux001Geq029..031` cannot be proved on the part
because they have no address to write.

### S4-11 — `CrossoverSlope` has an address to go to, and it is free

**Severity: major (a product control that does nothing). Status:
PROPOSED; prototyped and reverted at the contract boundary.**

Eight cells resolve to 0x0575. The proposal is **0x0576** — a word the
crossover node already owns and nothing dispatches to (S4-9) — so **no
address in either product moves and no row count changes**. **ONE shared
slope word, not one per strip**: there is a single `CROSSOVER` node
feeding all four main outputs from one LP/HP split, which is why the
four `CrossoverFreq` cells already share one word.

The DSP side is specified with it rather than after it: **12 (LR2) and
24 (LR4) are honoured** — the same five offset expressions with `1/(2Q)`
at 1.0 instead of 0.70711 and the second stage of each path written as
the compiled identity — and **6 and 18 are ignored, not clamped**,
because a 1st-order pair is 3 dB down at the corner rather than 6 and a
3rd-order pair does not sum flat, so neither is a Linkwitz-Riley
alignment this node can hold. `xover_ref.py` carries and checks both
(each path 6.0206 dB down at either slope).

It was implemented and then reverted **because `check_proposal()`
refused it**, which is the propose/land boundary working exactly as
designed: the address and the design land together, at a gate.

## the four inert families (2026-09-08, later)

Session: the queued INERT-families block. Write-up:
`MW/D32/DSP/dsp4-inert-families-20260908.md`. Images: shipping float
configuration, chip1 `a6db2a8b` / chip2 `8e42f2b0`.

### S3-1 — GEQ: the 28 band cells were dispatched to a coefficient array, and nothing designed them

**Severity: major (PW's market bar). Status: FIXED and verified on the
part.**

`defs/products/d24/dsp.csv` gives a GEQ node one address per band
carrying a gain in dB (`Aux001Geq001..028`, Table `0=-12/127=12/[Lin]`).
`gen_dsp.py:579` pointed those 28 addresses at `_geq_coeffs_next` — a
140-word staging array, one word per band, with no swap trigger. The
comment on the same loop has said `gains[28]` since it was written.
`_geq_gains_<nid>[]` was declared, written by nothing and read by
nothing.

Measured 2026-09-08: writing ±12 dB to all 28 cells moved
`_geq_coeffs_next[0..4]` to `41400000 C1400000 41400000 …` — 12.0f and
−12.0f as raw dB floats — while `_geq_coeffs_A/B` stayed at the compiled
identity `3F800000 40000000 BF800000 40000000 3F800000` and
`_geq_swap_pending` stayed 0. Every graphic EQ in the product passed its
input through: 32 of 32 captured words equal to the upstream node.

**28 addresses cannot carry 140 coefficients plus a trigger**, so the
design belongs on the DSP. `tools/dsp/geq_ref.py` is the normative model
(ISO R.40 third-octave centres, exact constant-Q 4.3185, RBJ peaking,
checked against `bq_float_ref.rbj_peak` to 2.2e-16);
`src/lib/geq_design_fx.asm` is the kernel; `src/geq_tables.asm` is
generated from the model; `_spi_dispatch_cN_dirty[]` is the trigger the
contract has no address for.

On the part: coefficients within **3 ulp** of the model over five gain
vectors, response within **0.00014 dB** of it, and band 17 at +12 dB
measures **+11.997 dB** at 1 kHz against a model of +12.000. A flat GEQ
designs the compiled identity and passes 64/64 samples unchanged.

### S3-2 — the offset coefficients cannot be designed the readable way

**Severity: major (would have shipped a wrong filter). Status: avoided by
construction; recorded because the wrong route is the obvious one.**

The natural implementation designs `b0..a2` and then converts:
`c1 = 2 + a1`. At 20 Hz `a1` is −1.99999 and `c1` is 6.8e-6, so forming
`a1` in float32 first carries about 1.2e-7 of absolute error into a
subtraction of two near-equal numbers — `c1` comes out about two percent
wrong. **That is exactly the error the offset encoding exists to remove,
thrown away in the step that computes it.**

Both new design kernels compute the offset words directly from
cancellation-free expressions, with the small quantity held as a
generation-time constant: `k2 = 2(1 − cos ω₀)` for the GEQ, and a series
for `1 − cos x` in the crossover (over 50–500 Hz `cos x` is
0.9979–0.99998). `geq_ref.check()` and `xover_ref.check()` both assert
the rearrangement is the same filter.

### S3-3 — a SHARC register alias produced a perfect coefficient set in the wrong bank

**Severity: major. Status: FIXED. Recorded because the symptom names none
of the cause.**

`_geq_design_N` held the band counter in `r12` and the reciprocal in
`f12`. On SHARC those are the same register, so after the first band the
count became the float bits of `1/(1+ia)` — about 1.07e9 — and the loop
walked past the end of `_geq_coeffs_next`, writing designed coefficients
into whatever followed until a band read out of the tables produced a
negative `inv` and `if gt` fell through.

**It did not look like corruption.** All 140 designed words were correct
to 1–3 ulp and the part stayed up, because everything the overrun touched
is rewritten every block — **except `_geq_active`**, which is not. That
word took `n1 = 2.0f`; `pass` reads any non-zero as bank B; the design
had been staged into A. The bench read `+0.000 dB` at every probe
frequency with every coefficient correct in memory.

The rule that follows: in a routine that mixes integer bookkeeping with
float arithmetic on SHARC, the bookkeeping goes in a register whose float
twin the routine never touches. Both new kernels state their clobber list
including that, and both keep `r13-r15` clear of floats.

### S3-4 — CROSSOVER: one address carries two parameters, in the landed contract

**Severity: major, and it is a `defs` defect this repo cannot fix.
Status: worked around; the ask is one row.**

`MainCtr001`, `MainL001`, `MainR001` and `MainSub001` each carry a
`CrossoverFreq001` AND a `CrossoverSlope001`, and **all eight resolve to
address 0x0575** — the contract's own Notes column says "shared crossover
word". Measured on the part: writing 500.0 then a slope left
`0x00000018` (the integer 24) in `_xover_coeffs_next[0]`.

The crossover design (S3-5) therefore **IGNORES a word outside the
frequency table's 50–500 Hz rather than clamping it**. Clamping a slope
into the frequency would move the crossover to 50 Hz every time the host
set a slope; ignoring it leaves the split where the last legal frequency
put it. The bar carries the negative control: writing slope 24 and then 3
leaves the staged set unmoved word for word.

**Until the row is split, the slope is not settable and the split is
LR4** — 24 dB/octave, the top of the slope cell's own table.

### S3-5 — CROSSOVER: a real LR4 split, made real

**Severity: major. Status: FIXED and verified on the part.**

Same defect shape as S3-1: a real pair of two-stage cascades, the landed
cell dispatched to `_xover_coeffs_next[0]`, no trigger, both banks at the
compiled identity, the node copying its input to all four main outputs.

`tools/dsp/xover_ref.py` (normative: Linkwitz-Riley 4, checked against
RBJ written out and against the two properties that make it a crossover
— each path 6.02 dB down at the corner, the two summing flat) and
`src/lib/xover_design_fx.asm`. On the part at 50/80/120/250/500 Hz:
staged coefficients within **3 ulp**, the live bank equal to the staged
one word for word, every corner reading **LP −6.021 dB / HP −6.021 dB**,
and LP+HP summing flat to **0.00013 dB** over ±4 octaves. Audio at
f0 = 120 Hz: LP −0.04 / −6.02 / −48.24 dB at 30 / 120 / 480 Hz against a
model of −0.03 / −6.02 / −48.21.

### S3-6 — ANTI_FB: the parameters land, the kernel is real, nothing joins them

**Severity: major. Status: DIAGNOSED, not implemented (the dispatch
scoped this family to diagnose and cost).**

`_afb_notch_freq/gain/q` take the write correctly — measured 1000.0,
−18.0 and 4.0 at their landed addresses — and are read by no emitted
line. `_afb_on` and `_afb_ctrl_on` are read by nothing either, so the On
switch does nothing. `_afb_coeffs_next` never moves and both banks hold
the compiled identity. The cascade underneath is real: six stages, its
own crossfade, the same `_fx_cascade_node` idiom the GEQ uses.

The work is a `_afb_design_N` beside `_geq_design_N` — RBJ from (freq,
gain, Q), the same dirty flag, the same swap — plus a product decision
about whether `AntiFbCtrlOn` implies an automatic detector.

### S3-7 — FX_ENGINE: the default algorithm is not implemented, and the reverb path takes the sample with it

**Severity: major. Status: DIAGNOSED, not implemented.**

Every FX parameter reaches the kernel; `_fx_type` selects the algorithm
and **defaults to 0 = Echo**, which the dispatch does not implement —
only 2 (Doubling) and 3 (Reverb) have cases and everything else falls
through to a dry pass-through. `_fx_on` is written 1 and read by nothing.

Three defects underneath:

1. The Doubling path reads a 15 ms (720-sample) delay out of
   `_fx_echo_buf[8]`, an **eight-word** buffer, with a wrap constant of
   8. It cannot work as written.
2. **`_C2_FX_ENG_01_process` sets no L register** and then uses
   `modify(i0, m0)` four times on its comb and delay buffers — every
   other kernel in this tree guards that with `l0 = 0`. Setting
   `Type = 3` in the family walk turned the FX chain from carrying the
   impulse to **peak zero on both arms**: the reverb path does not merely
   fail to reverberate, it takes the sample with it. This is the first
   thing to check, and it is why the family-walk spec was left at the
   default `Type`.
3. `Fx001Mix001`'s Table domain is `0=0/127=100` (percent) and the kernel
   uses the word directly as a 0..1 blend coefficient, so the documented
   100 gives `100·wet − 99·dry`. `wire-units.csv` carries no row for any
   FX cell.

Its cost is measured and it is large — see S3-9.

### S3-8 — the capacity numbers already carried the cascade families, and now that is tested rather than argued

**Severity: informational, and it answers the hub's question. Status:
measured.**

`_bq_fx_cascade_blk` issues the same instruction stream whatever its
coefficients hold. Until the GEQ design landed that could not be tested,
because no GEQ had ever held a coefficient other than the identity.
Paired on one boot, chip 2, block 8:

| arm | cycles/block |
|---|---:|
| every GEQ flat | 330,658 |
| every GEQ non-flat (364 band cells at ±12 dB) | 331,250 |
| difference | **+592, 0.18 %** |

Like-for-like at the operating point the fit numbers were taken at —
`sigprofile2.sh`, whole chip-2 graph, block 16, two boots, minimum:
**250,480 cycles/block (76.44 % of 327,680)** against the 09-03 record of
**249,737 (76.21 %)**. +743 cycles, 0.23 % of budget, against two boots
of this run that are 1,516 cycles apart. **The 09-03 fit numbers stand
and the designs cost nothing measurable.**

### S3-9 — the FX reverb has never been in a capacity number, and it is worth 17 % of chip 2

**Severity: major (capacity). Status: measured at block 8; projected to
block 16.**

`FX_ENGINE` is the one family whose instruction stream depends on its
parameters, and its `Type` has always defaulted to the unimplemented
Echo. Chip 2, block 8, paired on one boot:

| arm | cycles/block |
|---|---:|
| Type 0 on all six engines (the default) | 330,635 |
| Type 3 = Reverb on all six | 358,806 |
| difference | **+28,171** |

Reproduced over three boots: +27,861 / +27,867 / +28,171. That is 3,521
cycles per sample across six engines, **587 per sample per engine**.
Scaled to block 16 the same per-sample cost is **≈ +56,300 cycles/block,
17.2 % of chip 2's budget** — 76.4 % → ≈ 93.6 %, margin 23.6 % → ≈ 6.4 %.
**That is a projection from a measured per-sample cost, not a measurement
at block 16**, and it is the largest uncosted item in the capacity
picture. One arm of `sigprofile2` would settle it.

### S3-10 — the sample-order result was taken through unidentified logic, and is withdrawn

**Severity: major (it invalidates a recorded finding). Status: the cause
is fixed; the measurement must be re-taken.**

The recorded "the loop does not preserve sample order — 40.4 % of
transitions monotonic, dominant step −576 Pi frames" cannot be
interpreted, for three independently measured reasons.

**The Pi link runs at 48 kHz whatever ALSA is told.** Measured on the
bench, `arecord -d 5` on `hw:dsp4pcm,0`: 48,000 → 5.01 s wall; 96,000 →
10.01 s; 192,000 → **20.15 s**. Effective frame rate 47,917 / 47,955 /
47,645 Hz. LOGIC masters BCK and LRCLK, the Pi is a slave, and
`invirco,dsp4-pcm-dummy` declares `SNDRV_PCM_RATE_8000_192000` so it does
not refuse a rate the link cannot honour. The loop test ran at 192,000,
so **every frame count in that result is four times the truth**.

**The flashed bitstream predates the regrouping it was blamed on.** The
bench runs `dsp4_logic.a1f6672af6c3`, built 2026-08-21. `PI_TDM8` first
appears in `rtl/dsp4_pcm_reframe.v` on 2026-08-23 (`2bb0b49`).

**That bitstream has no Pi capture path at all**: in the RTL as of the
commit that shipped it, `assign pcm_din = 1'b0; // capture path to the
Pi: future work`. Confirmed on the bench today — with the DSP booted,
configured and in the documented pass-through state, a played counter
returned **0 carrying frames** at both 48 kHz and 192 kHz.

So the loop measurements were taken on a **different, unrecorded**
bitstream and the bench was then left on one that cannot loop. See S3-11
for why nothing recorded which.

### S3-11 — a bitstream could not name its own configuration

**Severity: major (it is the root cause of S3-10). Status: FIXED.**

`shared/dsp4-logic/build.sh` derived the artifact name from a hash over
the slot-map hash, `loopback=`, the RTL, the QSF and the SDC — and
**nothing else**. `PI_TDM8`, `PI_SELFTEST` and `PI_MAINCAP` are Verilog
macros passed to `quartus_map`; none of them entered the hash and none
was recorded in the manifest. A build that regroups four Pi frames per
DSP frame and one that does not therefore produced **the same filename
and an identical manifest**.

The flashed bitstream's recorded `slot_map` hash (`efd8d555…`) is also
two generations stale against the current `slot-map.csv` (`4ecc4aa2…`),
whose A_I6 rows declare the regrouping PW decided on 2026-08-23.

Fixed: every macro now enters the hash and the manifest records both the
config line and a plain-English `pi_link:` description of what the Pi
side does. Re-taking the order test needs a `PI_TDM8` bitstream built
from the current slot map with the fixed script, flashed at the bench.
**Not done here**: with the defect unfixed there was no way to be sure
which existing artifact is the TDM8 build, and flashing shared hardware
on a guess is not a measurement.

### S3-12 — the GEQ family probe was blind to a working graphic EQ

**Severity: medium (instrument). Status: FIXED.**

`dsp4_family_verify.py` probed `GEQ` with `Aux001Geq001` — band 1 of the
ISO third-octave set, **19.95 Hz**. Its impulse response takes 2,400
samples to ring once, so over the 32-sample capture window a +12 dB boost
moves `b0` by about 4e-4 and the family would read INERT for a graphic EQ
working perfectly. The probe is now band 18 (1 kHz), which the window
resolves. The numeric verdict lives in `geqverify.sh`, which scores the
whole band set against the model rather than one band against a window.

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

### S2-11 — the loop is a PASS-THROUGH with no pedestal, and it does not preserve sample order

**Severity: major (bring-up). Status: the pedestal is CLOSED, the ordering
is OPEN and characterised.**

Step 1 asks for a pass-through that is bit-exact end to end. Three of its
four parts are now measured; the fourth says the loop cannot carry a
latency figure yet.

**THE PASS-THROUGH, from the contract.** Seventeen sources sum into
`C2_MIX_MAIN_L` — `C2_RECV_MAIN_L` (chip 1's whole 24-strip bus), the four
`C2_GRP_COMP_*`, `C2_USB_IN`, `C2_BT_IN`, `C2_CODEC_AUX_IN`, `C2_PI_IN` and
the eight `C2_SNK_IN_*`. `passthru_setup.py` silences sixteen of them by
CELL NAME out of the landed map: 24 strips taken off the main bus AND muted
(48 cells, two independent ways, because one inert cell would otherwise
leave the bus live and look like a pedestal), `Usb001On001` /
`Bt001On001` / `CodecAux001On001` cleared, the four `Grp*Mute001` set, the
main fader at unity and `Main001Delay001` zero. **Every one of those 60
cells is in the contract** — the run reports which are not, and none were.
The eight snake returns have NO cell in the landed map at all and could not
be silenced from the contract; on this bench nothing is connected to them,
and the measurement below shows they contribute nothing.

**NO PEDESTAL.** With the setup applied and nothing played, the whole main
chain reads zero at the scope — `_buf_C2_MIX_MAIN_L`, `_buf_C2_MAIN_FDR`,
`_buf_C2_MAIN_DLY` and `_buf_C2_MAIN_ST_OUT` all `0x00000000` — and the
captured measurement channel idles at **8 LSB, about −168 dBFS**, which is
the residue on the TDM slot nothing drives. The `0x11E7E000` pedestal
(0.28 in Q4.28) that made the earlier capture unreadable is gone.

**THE ×2 WAS A LEVEL, NOT A SHIFT.** At `Pi001Level001 = 1.0` a known word
returned doubled, which reads like a one-bit scatter/gather asymmetry. It
is not: at **0.5** the loop returns unity, and `_auxin_q_C2_PI_IN` reads
`0x08000000` — Q4.28 0.5 exactly, target matched, frames 0, so the
coefficient is settled and exact. The node carries a factor of two the cell
value does not describe. Same class as S2-5 and a question for the unit
rows, not a defect in the path.

| played | returned | ratio |
|---|---|---|
| `0x00001000` | `0x00001000` | **1.0000**, `in << 0` |
| `0x00010000` | `0x0000FFF8` | 0.9999 |
| `0x00100000` | `0x000FFF88` | 0.9999 |

So the loop is amplitude-accurate to about 1.2e-4 (−78 dB) and **not
bit-exact**; the residual is not the Pi coefficient and is not yet
attributed.

**NO L+R SUMMING, AND THE RETURN IS MONO.** Played into L only the word
returns; into R only, nothing returns; into both, the same as L alone. That
settles a question the ×2 had made ambiguous. It also confirms on the part
the standing note that `C2_MAIN_ST_OUT` drives TDM slot 0 only.

**THE CAPTURED CHANNEL IS NOT FIXED.** The same stimulus came back on L in
one capture and on R in the next: the Pi is an I2S slave and LOGIC regroups
four Pi frames into one DSP frame, so the word a stream starts on is not
determined. `dsp4_loopcal.py` phases every capture before reading it and
reports which channel carried the return. Reading a fixed channel is what
made one run print `ratio 0.0000` for a loop that was working.

**AND THE LOOP DOES NOT PRESERVE SAMPLE ORDER — so no latency is quoted.**
A counter whose every value was held for **64 Pi frames (16 DSP frames)**
still comes back with only **40.4 % of transitions monotonic** (59,498
carrying frames), the dominant index step being about **−9 values ≈ 576 Pi
frames** backwards. Holding each value for 4 frames — the regrouping ratio —
is not enough either. DC returns perfectly and a ramp does not, which is
the signature of a reader sampling the wrong one of the four regrouped Pi
frames and periodically re-reading a stale region, rather than of a gain or
a clock error.

**A latency measured through a path that reorders is not a latency**, so
none is recorded. What the loop supports today is amplitude measurement on
slowly-varying or DC stimuli; a per-sample vector set needs the ordering
closed first. The next probe is the CPLD reframe (`rtl/dsp4_pcm_reframe.v`)
against the DSP's Pi-input DMA, not the ALSA layer — that part is now known
good.

### S2-12 — busgold: the graph is bit-exact across the wire-unit conversion

**Severity: none — a bar owed and paid.**

The audio image changed this session (S2-8), so the standing "the image is
byte-identical, therefore the capture cannot have moved" argument that had
covered `busgold` no longer applied. Run on the part:

```
strip 1 driven, 2 muted: 256/256 non-zero, sha256 ba3f52ecb83f9a60
postD59 vs cur: 0 of 256 words differ
GRAPH BIT-EXACT
```

`ba3f52ec` is the stored golden's own hash, so the capture reproduces
`goldens/busgraph-postD59-20260830.json` word for word. That is the
predicted result and it is now a measurement: `dsp4_pairgraph.py` writes
`DlyOff` as a raw `0`, which the new conversion maps to 0 ms → 0 samples,
and it never writes `GateHold` at all — so the conversion is audio-neutral
for this harness by construction, and the bar confirms it rather than
assuming it. The harness's two standing caveats still apply and are printed
by it: the biquads are in bypass and the gain is unity, so this comparison
says nothing about paired biquads or about GAIN's rounding.

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
