provenance: AI-drafted 2026-09-09 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# The CM4 loop at 48 kHz: the latency figure, and the two things that stop it going through the DSP

Bench: rev C unit MW-D24-2, `app@192.168.1.219`. Rev A show model not
touched. Every bitstream named here was built tonight from the current
slot map with the fixed `shared/dsp4-logic/build.sh`, and every one of
them names its own configuration in its manifest.

## 1. The answer, in one table

Measured through `dsp4_logic_pisel.bd9c100db7c2` — Pi → CPLD re-frame →
CPLD de-frame → Pi, 48 kHz, duplex overlay, 20 reps per boot.

| | min | mean | median | max | spread |
|---|---|---|---|---|---|
| boot 1 | **14,431** | 14,445.0 | 14,438 | 14,585 | 154 |
| boot 2 | **14,431** | 14,436.4 | 14,437 | 14,440 | 9 |
| boot 1, ms | 300.646 | 300.936 | | 303.854 | |
| boot 2, ms | 300.646 | 300.757 | | 300.833 | |

**Counter agreement was 100.0000 % on every one of the 40 reps** —
48,000 of 48,000 ramp words at ONE offset, so nothing was reordered,
dropped or duplicated in any of them.

### The fixed part and the boot-to-boot part

**The boot-to-boot part is zero.** The minimum is identical to the
sample across the two boots (14,431 and 14,431) and the medians are one
sample apart (14,438, 14,437). The run-to-run part inside a boot is
**≤ 9 samples** (boot 2, 20 reps). Boot 1's spread of 154 is one outlier
rep against a median that agrees with boot 2's.

That is the answer gate 3 asked for about the alignment contract (net
N2a): **the CPLD loop's alignment does not move between boots.** There
is no boot-to-boot term to attribute.

### What the absolute number is, and what it is not

The harness deliberately starts `arecord` 0.3 s — 14,400 samples —
before `aplay`, so a zero-latency loop would land near 14,400 and the
residual is **31 samples, 0.65 ms**. Read that as an **upper bound**,
not as the path: the residual also contains the difference in ALSA
stream-start setup between the capture and playback halves, which is
additive, non-negative and cannot be separated without a second
bitstream to difference against. The min is the least contaminated
estimate available and it is the one that reproduces exactly.

Where the 300 ms goes is not a mystery and is not the CPLD: the ALSA
period is 1024 frames and the buffer 8192, and those two dominate every
other term by three orders of magnitude. Inside the CPLD the re-framer
is a frame each way by construction — its own comment, "capture runs a
frame behind playback onto the TDM line (one full stereo frame of
latency, constant)" — which is one sample each way at 48 kHz. The DSP
block is 8 (measured: `FRAME_COUNT` advances 5,999/s, and 48,000/8 =
6,000), and the SPORT DMA window is one block.

## 2. The through-DSP arm does not close, and no figure is quoted for it

> **CLOSED 2026-09-09, session 33 — see §7.** The arm is measured: the
> DSP's contribution is **72 samples / 1.500 ms**, boot-to-boot zero.
> This section's diagnosis was half right and half wrong, and both halves
> are worth keeping: the capture path DID have a real defect (it spliced
> every word out of two DSP frames, S7-1) and fixing it did NOT change
> the order result at all. The order defect is in the chip-2 transmit
> path — whole 8-sample blocks arrive from the wrong place — and it is
> still open (S7-5). Read §7 before quoting anything below.

> **2026-09-09, next session.** §3's defect is fixed and the main bus is
> now silent to 48,000 frames of 48,000 — and **this arm still does not
> close**, so the mask was not why. A constant returns through the DSP
> bit-exact; a staircase returns complete but with its sample order
> destroyed inside a window. It is the `_maincap` capture path, not the
> DSP. See `MW/D32/DSP/dsp4-chan-mask-20260909.md` §6 and finding S6-4.

`dsp4_logic_maincap.1216e35175cb` captures B_O3 slot 0 = `C2_MAIN_ST_OUT`,
which is where a Pi → DSPA → fabric → DSPB → Pi pass-through lands. It
returns a stream that is **mostly zeros with sparse, out-of-order counter
indices** — over 40 consecutive captured frames: 5, 5, 16, 18, 35.

The harness reported an offset of 14,550 for this arm. **That number is a
spurious mode and is not a latency.** Only 2,878 of 48,014 candidate
words agreed on it, spread across 44 distinct offsets, and the impulse
was never found at all. It is recorded here so that it is not picked up
later as a measurement; the honest statement is that the DSP's
contribution to loop latency was **not measured this session**.

Four things WERE established about that arm before it was stopped, and
they narrow it considerably:

1. **The capture path is right and it is reading `MAIN_ST_OUT`.** It
   tracks the contract: `Main001Mute001` = 1 → `0x00000000`, = 0 →
   `0x7FFFFFE0`; `Main001Level001` = 0.0 → `0x00000000`, = 1.0 →
   `0x7FFFFFE0`; a minimal image with no graph → `0x00000000`.
2. **The graph is running.** `_dly_write_ptr_C2_MAIN_DLY` advances
   between reads and `FRAME_COUNT` runs at 5,999/s against an expected
   6,000/s for block 8, with `BOOT_STAGE 7`, `SPORT0_ERR_A 0`. (The
   bench's copy of `dsp4_audio_verdict.py` is older than the repo's and
   prints "expect ~1500", i.e. block 32; the staged `dsp4_block.py`
   says `BLOCK = 8`, `BLOCK_RATE = 6000`, and that is the bar 5,999
   is scored against. Re-stage the tool before quoting it again.)
3. **The new slot map changed nothing DSP-facing** (§4).
4. **The main bus was not silent, and the reason is a firmware defect**
   (§3). That alone made every earlier attempt at this measurement
   unusable, including the 2026-09-08 note that "the loop still carries
   a DC pedestal until the main chain is set to unity". It is not a
   pedestal and it does not come from the main chain: it is positive
   full scale, and it comes from eight strips D24 does not have.

## 2a. Sample order at 48 kHz: 29,759,999 words, zero defects

Gate 4, on `dsp4_logic_pisel.bd9c100db7c2`, `tools/pi/dsp4_order_soak.py`:

```
order soak: 620 s at 48000 Hz on hw:dsp4pcm,0, counter step 256 wrap 65535
  elapsed 621.7 s, words checked 29,759,999 (620.0 s of audio)
  drops 0  reorders 0  stalls 0  dropouts 0  non-counter words 0
ORDER SOAK: PASS
```

**The 2026-09-08 "the link reorders samples" finding is now negatively
confirmed at 48 kHz on a bitstream that names its own configuration**, over
ten and a third minutes of continuous streaming with no ALSA under- or
over-run reported in either direction. It was already withdrawn as a
192 kHz artefact; this is the positive result that replaces it.

The first run of this soak reported `FAIL (0 defects)` — zero defects but
only 591 s of the 630 s asked for. That was the harness, not the link:
the stimulus generator paced itself at `RATE // CHUNK` chunks per nominal
second, and `48000 // 4096` truncates to 11, so it delivered 45,056
samples per second while every line of the report still said 630. Fixed
to count in samples, and the pass criterion now checks the word count
against the requested total instead of a loose margin — a soak that
quietly runs short is a soak that quietly misses its own gate.

## 2b. The TDM8 build proven on the part

`dsp4_logic_tdm8.83778a06f954` was flashed and its IDCODE re-read, but it
cannot be proven on the conformance image: in PI_TDM8 the capture source
moves to `o_dspb[0]`, which only the `DSP4_PATTERN` firmware drives on all
eight slots, so on the shipping graph it is inert and the capture is
empty. That is the build behaving as designed, not a fault, and it is why
the eight-channel claim needs the self-test variant.

`dsp4_logic_pisel_tdm8.c2f1457b5388` — the same PI_TDM8 re-framing with
the loop closed inside LOGIC — was built, flashed and run:

```
captured 1152000 words; first non-zero at 123422 = 1
counter range 1..192000 over 192000 words
consecutive +1 steps: 191999/191999 = 100.00%
DUPLEX 8-CHANNEL: PASS
```

So the TDM8 re-framing **built from the current slot map with the fixed
build.sh** carries eight channels each way, bit-exact, both directions at
once. That reproduces the 2026-08-23 result on a bitstream whose
configuration is recorded rather than inferred, which was the point.

## 3. `CFG_CHAN_MASK` is stored and never read, so D24 runs 32 strips

`tools/pi/dsp4_config.py` sends D24 `CFG_CHAN_MASK = 0x00FFFFFF`
("strips 25-32 NET-only"). `product_config.asm:121` stores it in
`_chan_mask`. **Nothing in the firmware ever reads `_chan_mask`** —
there are four references in the whole tree: the `.global`, the `.var`
initialiser, the `.extern` and that one write.

So on D24 all 32 strips run and all 32 sum into `C2_RECV_MAIN_L`,
whatever the product config says.

Measured on the part. With everything the D24 contract *can* silence
silenced — 32 strips attempted, the four groups, USB, BT, CodecAux —
and the Pi input turned OFF as well, `C2_MAIN_ST_OUT` sits at positive
full scale, `0x7FFFFFE0`, for 48,000 frames out of 48,000, with nothing
playing. Writing `MainOn = 0` and `Mute = 1` to exactly the eight strips
25–32 takes it to `0x00000000` for 48,000 frames out of 48,000. That is
the whole finding in two captures.

Those eight strips cannot be silenced from the D24 contract, and that is
CORRECT, not a second defect: D24 is a 24-channel product, its matrix
has 123 `Chan024` cells and **zero** `Chan025` cells, and
`defs-v2026.09.08.4`'s `d24/dsp.csv` accordingly carries 102 cells each
for `Chan001`–`Chan024` and none for `Chan025`–`Chan032`. The contract
is right. The firmware is running eight strips the product does not
have, because the one word that says so is inert.

To measure at all, the bench silenced them through **D32's rows for the
same cells** — legitimate because decision D3 makes the DSP address map
shared between the products, and `Chan024MainOn001` reads `0x0D44` in
both files. `tools/pi/dsp4_silence_2532.py` is that workaround, and it
says in its own docstring that it is one.

`_aux_mask` has the same shape — stored at `product_config.asm:124`,
read by nothing. `_out_mux` likewise, and that one is already
acknowledged in the host tool ("B_O2 = snake (stored; gather TBD)"). Of
the four product-config words only `_product_id` has a reader.

**This is a window item.** A D24 whose main output is saturated by eight
strips it does not have is not shippable, and the fix is in the
firmware, not in the contract and not in the app.

> **FIXED 2026-09-09**, the session after this one:
> `MW/D32/DSP/dsp4-chan-mask-20260909.md`. Both masks now have readers
> and a masked strip or aux is SKIPPED. `tools/pi/dsp4_silence_2532.py`,
> the workaround this section describes, is deleted.

## 4. The slot map moved; the DSP side did not

The current slot map is `sha256:4ecc4aa221a0787e…`, from the 2026-08-23
CM4 TDM8 allocation. No bitstream had ever been built from it: the
flashed `a1f6672af6c3` is on `efd8d555…` and the newest committed build
`dfe9b246f0fc` is on `4868ae9d…`.

Against the previous map it **adds ten slot assignments and moves none**:
`A_I6` slots 2–7 (`PI_PCM_3..8`) and `B_O3` slots 4–7 (`PI_RET_3..6`),
all of them previously unassigned. Every pre-existing (line, slot) →
signal pair is byte-identical.

And the generated lane tables confirm it reaches the DSP as nothing at
all: chip 1 RX lane 6 is still `CS 0x0003`, 2 words, and chip 2 TX lane 3
is still `CS 0x0003` — the masks come from where NODES exist, and only
`PI_PCM_L/R` and `PI_RET_L/R` have nodes. **The DSP side is untouched, so
the TDM8 build is not a contract change.** The panel MCU is an SPI
parameter host and does not see TDM slots at all.

## 5. Method

`tools/pi/dsp4_loop_latency.py` and `tools/pi/dsp4_order_soak.py`, both
committed. Two things about them matter.

**48 kHz is a constant, not an argument.** On a non-TDM8 bitstream LOGIC
masters `pcm_clk` and `pcm_fs` at 48 kHz and the CM4 is a clock slave, so
the wire rate is 48 kHz whatever ALSA is told. Asking ALSA for 192 kHz
does not change the wire — it mislabels the samples, and that
mislabelling is exactly how the 2026-09-08 "reorders samples" result was
produced and then withdrawn.

**The offset comes from the counter, not from the first non-zero sample.**
The stimulus is silence, one impulse, then a ramp carrying its own index
in the top 24 bits. Edge-finding cannot tell a late start from a dropped
block and breaks outright against a DC pedestal — which is what the loop
had, before §3. Instead every captured word votes for an offset and a
clean loop makes every vote agree, so the reorder/drop check and the
latency come out of one capture. The 100.0000 % in §1 and the 5.99 % in
§2 are the same statistic.

## 6. Bench state

| | at start | at end |
|---|---|---|
| CPLD | `dsp4_logic.a1f6672af6c3` | **`dsp4_logic.a1f6672af6c3`** (restored) |
| chip 1 | `~/dspboot/chip1.ldr` md5 `602a0feb…` | unchanged, `602a0feb…` |
| chip 2 | `~/dspboot/chip2.ldr` md5 `b1325022…` | unchanged, `b1325022…` |
| Pi overlay | `dtoverlay=dsp4-pcm-slave` | `dtoverlay=dsp4-pcm-slave` (restored) |
| matrix-app | active | active |

No staged image was replaced. The two conformance images are the ones
the window depends on and they were used exactly as found. `config.txt`
was switched to `dsp4-pcm-duplex` for the measurement and switched back;
it now diffs clean against the copy taken at the start
(`/home/app/config.txt.asfound-20260909`). The duplex overlay's `.dtbo`
and the `dsp4-pcm-dummy` module remain installed, so it is one line of
`config.txt` and a reboot away — and it is the only overlay any of this
can be measured on, because the slave overlay's two single-direction
devices re-program each other's framing.

The shipping bitstream was restored and verified three ways: IDCODE
`0x020a30dd`, both DSPs boot (so `DSP_CLK` survived), and `PCM_CLK` and
`PCM_FS` both read TOGGLING on `dsp4_netprobe.py` (so clkgen is intact).
It was also positively identified rather than merely assumed: on
`a1f6672af6c3` the CM4 capture stream does not return silence, it fails
outright — `arecord: pcm_read: read error: Input/output error`, zero
bytes — where every bitstream built tonight captures normally.

**Worth flagging for whoever schedules the next CPLD session:** the
bench's shipping bitstream is from 2026-08-21 and has no Pi capture path
at all, so the CM4 stereo return (`PI_RET_L/R`, the USB 2-track and
Bluetooth record source) does not exist on the bench today. A shipping
build from the current slot map would have it — the capture path is a
product feature in every configuration of the current re-framer — but no
such bitstream has been built, flashed or proven, and deliberately none
was committed tonight: a `SHIPPING: yes` artifact nothing has verified is
exactly the kind of thing §S5-8 was about.

### On proving which bitstream is running

Gate 2 asked for the running hash off the part. **The design has no ID
register** — there is nothing in `rtl/` to read back, and MAX V
configuration readback is not available over the SVF path. Identity was
therefore established by behavioural discriminant, and the three
bitstreams in play are mutually exclusive on it:

* `a1f6672af6c3` ties `pcm_din` to `1'b0`, so its capture is all zeros,
  always;
* `_pisel` returns the Pi's own playback bit-exact (48,000 of 48,000
  counter words at one offset);
* `_maincap` returns `o_dspb[3]` slot 0 and tracks `MAIN_ST_OUT` under
  mute and level.

Each of those was observed on the part after the corresponding flash.
It is sound, but it is indirect and it costs a measurement each time.
**A four-bit design ID readable over the parameter link, or on the TEST
pins, would replace all of it with one read** — recorded as a
recommendation, not done tonight, because adding it changes the RTL and
therefore every hash in this document.

### JTAG

There is **no USB-Blaster on the dsp machine** — `jtagconfig` reports
"No JTAG hardware available" and `lsusb` shows no Altera device. Every
flash tonight went through the documented hands-off path instead:
OpenOCD `linuxgpiod` bit-banging the bench CM4's own GPIOs (TCK 7,
TDI 23, TDO 22, TMS 25, `/home/app/cpld-jtag.cfg`), IDCODE `0x020a30dd`
read back before and after each one, and `pinctrl set
6,7,8,9,10,11,12,22,23,24,25 a0` after every one.

---

## 7. The through-DSP arm CLOSED (2026-09-09, session 33)

§2 said the DSP's contribution to loop latency "was not measured this
session" and that the `_maincap` capture was the thing scrambling the
order. The first half is now answered. The second half was the wrong
suspect, and both halves needed a different instrument to see.

Bitstreams, both built from the current slot map with the corrected RTL,
and both **identified by reading a register off the part** rather than by
inference (§7.4):

| arm | artifact | design id | cfg |
|---|---|---|---|
| LOGIC loop | `dsp4_logic_pisel.2c1355bbc69b` | `ae`→`55bbc69b` | pi_selftest |
| through DSP | `dsp4_logic_maincap.d903ae1ac4a9` | `ae1ac4a9` | pi_maincap |

DSP images: the WINDOW pair, chip1 `093c609f` / chip2 `2ba0e464`, run
from `~/s32` so `~/dspboot` was never touched.

### 7.1 The instrument had to change first

`dsp4_loop_latency.py` recovers latency by having every captured word
vote for an offset. That needs the loop to return the stimulus unchanged.
It does for the LOGIC-only arm and it does **not** for the through-DSP
arm — only about a third of the words come back where they belong (§7.3)
— so a per-word vote finds spurious modes. That is exactly how the
2026-09-08 figure of 14,550 was produced, and why §2 refused to quote it.

`tools/pi/dsp4_dsp_latency.py` scores every candidate offset by the
fraction of frames carrying the exact expected value and reports the
answer **only with its margin over the runner-up two plateaus away**. A
coherent third still puts a sharp peak at the true offset; a spurious
mode does not have one, and the margin says which happened.

### 7.2 The answer

20 reps per arm, `arecord` started 0.3 s (14,400 samples) before `aplay`
as in §1, so these are directly comparable with §1's numbers.

| arm | min | median | max | spread | coherent | worst margin |
|---|---|---|---|---|---|---|
| LOGIC loop (`_pisel`) | **14,432** | 14,438 | 14,451 | 19 | 100.0 % | ∞ |
| through DSP, boot 1 | **14,504** | 14,514 | 14,520 | 16 | 33.1–33.5 % | ×16.0 |
| through DSP, boot 2 | **14,504** | 14,511 | 14,519 | 15 | 33.1–33.5 % | ×16.2 |

The LOGIC-loop minimum reproduces §1's 14,431 to one sample, on a
different bitstream and a different instrument. That is the cross-check
that makes the rest of the table worth reading.

**The DSP's contribution is 72 samples, 1.500 ms.** Minimum to minimum,
14,504 − 14,432; median to median it is 76 and 73 on the two boots. Both
arms carry the identical ALSA start offset and the identical 0.3 s
pre-roll, so the difference is the only figure here that is free of them.
The absolute through-DSP residual over the pre-roll is 104 samples /
2.167 ms, and that remains an **upper bound**, not a path, for the reason
§1 gives: it still contains the capture-vs-playback ALSA start
difference.

**The boot-to-boot part is zero.** The minima are identical across the
two boots (14,504 and 14,504) and the medians are 3 samples apart, on 20
reps each. That is the same answer §1 gave for the CPLD loop, now with
the DSPs in the path — net N2a has no boot-to-boot term to attribute at
either level.

### 7.3 What the 72 samples is, and what cannot be separated

72 is exactly 9 × 8, and `BLOCK = 8` on these images. Six of those nine
block times are accounted for by buffering that has to be there — RX
DMA, processing, TX DMA on each of the two chips — leaving three for the
inter-chip fabric crossing, the TDM8 re-framing and the one frame the
frame-locked capture snapshot now costs (§7.4).

That decomposition is **arithmetic consistency, not four measurements**.
Separating the terms needs bitstreams that tap the path at intermediate
points, and none exist; the honest statement is that the total is 72
samples with a run-to-run spread of ≤ 16 and no boot-to-boot term.

### 7.4 Two LOGIC defects found and fixed on the way

Full evidence in findings S7-1 and S7-2. In short:

* **The capture read-out walked the live register file.** `cap_flat` is
  rewritten slot by slot while the Pi's read-out of one word spans nearly
  the whole frame, so every recorded word was **spliced from two
  consecutive DSP frames** at a fixed bit — bit 25 for the `_maincap`
  slots, **bit 9 for the SHIPPING CM4 return**. Proven by alternating two
  known words: the old bitstream returned `0x03F7CA48` / `0x1786C9A8`,
  the new one returns `0x17F7CA48` / `0x0386C9A8`, and the old pair is
  the bit-25 splice of the new pair in both phases, over 100,000 settled
  frames each. Fixed with a coherent snapshot of both presented slots.
* **The period decode was one BCK early**, and `CAP_EXTRA_DELAY = 1` had
  been added in August to cancel it. The two errors hid each other in
  every bit except the top one, which came from the other slot. Both are
  now right on their own terms.

Neither was ever simulated: `tb_pcm_reframe` leaves `tdm_in` dangling.
`sim/tb_pcm_capture.v` now covers the direction and fails on the old RTL.

### 7.5 The design now says what it is

S5-9 is closed. `build.sh` derives a 32-bit design ID from the artifact
hash and a 5-bit config field, stamps both into the bitstream as Verilog
macros, and records them in the manifest. They are read back over the one
path off the part that needs no hands — the CM4 PCM link — by knocking:

```
$ python3 dsp4_logic_id.py --expect ae1ac4a9
design_id: 32'hae1ac4a9   cfg_bits: 16'h0004   pi_maincap
  reply frames 2175 of 144000 captured, 1 distinct reply word
  MATCHES --expect ae1ac4a9
```

It discriminates: the `_pisel` build answers `55bbc69b` / `pi_selftest`
on the same command, and the restored shipping `a1f6672af6c3` answers
nothing at all — which is now itself a positive identification ("this
bitstream predates the ID register") rather than an absence of evidence.

### 7.6 The order defect is real, and it is NOT the capture path

The frame-lock fix does not move the staircase result by one percent —
32.87 % exact before, 32.87 % after. The arm's remaining defect is
elsewhere and it is now measured rather than described (finding S7-5):

| stimulus period | runs observed | runs if clean |
|---|---|---|
| 2, 4, 8 frames | 90,000 / 45,001 / 22,500 | 90,001 / 45,001 / 22,501 |
| 16, 32, 128 frames | 40,211 / 42,396 / 42,867 | 11,251 / 5,626 / 1,407 |

**Any pattern whose period divides 8 survives exactly; anything longer is
scrambled.** Every sample arrives at the right position inside its
8-sample block, from the wrong block — about a third of blocks in the
right place, the rest drawn from roughly the last 225 blocks (≈ 37 ms).
The chain is bit-transparent throughout (only ever the exact stimulus
values, never an intermediate), and the displacement is independent of
signal magnitude, so nothing is filtering and nothing is arithmetically
wrong.

It is not the CM4 (`_pisel` returns 96,000 of 96,000 on the identical
staircase through the identical ALSA path), not the CPLD capture (one
frame deep, and now proven coherent), and not the chip-2 node graph
(every `_buf_*` tap on the MAIN chain reads non-decreasing while the
staircase plays). That leaves the chip-2 transmit path. **It is the next
dispatch**, and it is not cosmetic.

### 7.7 Bench state

| | at start | at end |
|---|---|---|
| CPLD | `dsp4_logic.a1f6672af6c3` | **`dsp4_logic.a1f6672af6c3`** (restored) |
| chip 1 | `~/dspboot/chip1.ldr` `093c609f` | unchanged, `093c609f` |
| chip 2 | `~/dspboot/chip2.ldr` `2ba0e464` | unchanged, `2ba0e464` |
| Pi overlay | `dsp4-pcm-slave` | `dsp4-pcm-slave` (restored, diffs clean) |
| matrix-app | active | active |

Nothing in `~/dspboot` was replaced, reordered or booted from: the window
pair was copied to `~/s32` and every boot this session ran from there.
The shipping bitstream was restored and verified four ways — IDCODE
`0x020a30dd`, both DSPs boot (so `DSP_CLK` survived), `PCM_CLK` and
`PCM_FS` both TOGGLING on `dsp4_netprobe.py` (so clkgen is intact), and
the ID register silent (so it is not one of tonight's builds).

**No shipping bitstream was built or committed**, deliberately and for
the reason §6 gives: the S7-1/S7-2 fixes land in the shipping capture
path the moment one is built, and a `SHIPPING: yes` artifact that nothing
has verified is what S5-8 was about. The next shipping build gets both
fixes and must be proven against matrix-app before it is committed.
