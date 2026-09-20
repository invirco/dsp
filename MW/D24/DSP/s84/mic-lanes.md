provenance: AI-drafted 2026-09-20 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S84 — the mic ADC lanes: the flash log settled, the sweep repeated on the bitstream they last worked on, and the ad[0..2] witness built and read

Unit MW-D24-2, 2026-09-20. Dispatch: HUB DISPATCH 2026-09-20 13:24Z.

**THE ANSWER IS THE OPPOSITE OF THE QUESTION.** The AK5558 mic-ADC lanes are
not dark. All three of them — `ad[0]`, `ad[1]`, `ad[2]` — are CARRYING DATA at
the CPLD's input pins, and they were carrying it in the same pass, on the same
bitstream, with the same rails and the same 595 image, in which the DSP's
thirty-two `_buf_C1_IN_*` buffers read exact digital zero. The converters are
clocked, out of reset, and converting. The fault is downstream of those pins.

No probe list for PW is owed, because nothing this session found points at the
analog board.

---

## GATE 1 — the flash log (S83-Q3)

The record exists and it is the bench's own: `/home/app/logic-flash.log`,
2,284,436 lines, **56 flash events, every one `rc=0`**, each a
`=== <UTC> <artifact> [attempt N] rc=N` header followed by the openocd output
that produced it. Dated table, residency intervals, per-session attribution and
findings: **`docs/d24-bench-logic-flash-log.md`**.

**The one fact that settles S83-Q3 is a gap.** Nothing at all was flashed
between `2026-09-13T13:11:14Z` and `2026-09-19T21:47:06Z` — six days and
8.6 hours. Whatever went on last before the gap sat on the part for all of it,
and what went on last was `s41_mhrx_pullup_off.15f3ae07dae1`.

That window contains **2026-09-16**, the day S54–S58 measured real preamp noise
on this unit. It also contains all of 09-19, so S69, S70, S71 and S72 are in it
too — S70's T1/T3 talkback numbers included.

| claim | verdict |
|---|---|
| "the bench spent a month on `dsp4_logic.a1f6672af6c3`" | **FALSE.** ~35 hours in all (09-11 06:43Z → 09-12 17:41Z), then nothing until 09-20 00:34Z. The LABEL pointed there for a month; the PART did not. |
| "`s41_mhrx_pullup_off` is what the bench lived on from 09-12" (its manifest) | **Essentially right, one day out.** Step 0 went on 09-12 17:58Z; s41 replaced it 09-13 13:11Z and stayed six days. |
| S54/S55/S58's live preamp noise was taken on — | **`s41_mhrx_pullup_off.15f3ae07dae1`.** |
| Was `a1f6672af6c3` ever resident when a session reported live converter data? | **No, on any date, and it could not have been.** |
| What did the hardcoded `shipping` label actually cost? | Less than S83-Q3 feared: the label was never invoked during the six-day gap, so nothing was silently overwritten there. Its real cost is four bounded 22–46 minute windows on the single night of 09-19/09-20 (S77–S80 handbacks), each self-correcting at the next flash. |

### S84-1 — "pre-S34" is not the discriminator, and using it as one was a second error on top of the first

`git merge-base --is-ancestor ded71079 61e38ce3` returns **FALSE**: the step-0
shipping base that `s41_mhrx_pullup_off` branches from does not contain the S34
converter-clock commit. It does not need to. At `61e38ce3` the top module
already reads

    output wire conv_bck,    // pin 142 (C1): 12.288 MHz, TDM8
    output wire conv_fs,     // pin 141 (L0): 48 kHz frame sync
    ...
    assign conv_bck = bck8;
    assign conv_fs  = fs8;

— the same two assignments HEAD carries, character for character. At
`a4ee3d1f` (`a1f6672af6c3`'s commit) those ports do not exist at all; the pins
are straps.

So **two independent lineages drive the converter clock pair** — the step-0
shipping branch and post-`ded71079` `main` — and exactly one artifact does not.
S41 measured it at the time (U3.142 = 12.288 MHz, U3.141 = 48 kHz, in its
manifest's `S41_PROOF`); S84 confirmed it by reading all four codec lanes live
on that bitstream in gate 2 below. `bitstream/retired/README.md` said the
discriminator was the build date relative to `ded71079`; it is corrected there,
and the two lineage rows are added to its table.

---

## GATE 2 — the S83 sweep, repeated on the bitstream the bench lived on

`s41_mhrx_pullup_off.15f3ae07dae1.svf` flashed through `tools/pi/logic_flash.sh`
under the AN_EN interlock (AN_EN read `lo`, IDCODE `0x020a30dd` before and
after), rollback staged as `dsp4_logic.7a6a4529f29c.svf` and verified present
before the first write, **FLASH-OK on attempt 1**. Bench md5
`fc6ce23ed14cda464f277a56cf21ab92` — identical to the manifest's `md5_svf`.

**Its identity rests on the log, and that was checked rather than assumed.**
This artifact carries no design ID by deliberate choice (the readback block
costs +124 LEs and would nearly double a one-pin change), so
`dsp4_logic_id.py` was run on it as a negative control and answered *"no reply:
nothing in the capture carried the 0xD594 marker"* — the expected answer, and
the exact discrimination `loadlogic.sh`'s no-design-ID-no-flash rule was built
on, taken in reverse on a part that had just answered `32'h4529f29c` an hour
earlier.

**The lane names mean what they meant in S83.** s41's slot map differs from
HEAD's only in the `A_I3` comment, the `A_I4`/`MIX_1` codec comments and the
six `A_I6` Pi TDM8 rows added at `1dc67f39`. The `A_I0`/`A_I1`/`A_I2` rows that
carry `IN_01..IN_24` are byte-identical, so `MIC 5 → _buf_C1_IN_16` holds on
this bitstream too.

Conditions: the S83 `DSP4_TEST_NODES` pair (`90daae5b`/`2483d61c`), **both
chips BOOT_STAGE 7**, rails UP (AN_EN `hi`, S70 recipe, authorised), 595 chain
at `0xFC` — every register unmuted, gain 63, phantom off — **VERIFIED 200/200**.

Both controls satisfied: `FRAME_COUNT +39332`, `_rx_slot_C1_IN_01` 1 distinct.

### S84-2 — 32 of 32 mic lanes exact digital zero on s41's bitstream too, with the codec live beside them

| lanes | reading |
|---|---|
| `IN_01`..`IN_32` (AK5558) | **0 of 32 moving.** All 32 STATIC ZERO, min = max = 0, tone off and tone on alike. |
| `XIN_CODEC_01`..`04` (AK4619) | **4 of 4 moving**, −69.1 / −69.7 / −96.4 / −81.5 dBFS, 15–16 distinct words of 16, in the same pass. |
| `XIN_PI_*`, `XIN_SNK_*` | static zero (nothing drives them in this configuration) |
| `XIN_MEMS` | static `0xFFFFFFFF` |

The tone arm ran too, for what the uncabled loop is worth: the AUX 1 bus
carried the tone digitally, no `_buf_C1_IN_*` lane rose with it, and the four
codec lanes read "moving, no rise". S83-Q2 is still with PW and nothing here
depends on it — the floor is the answer. A live ADC at gain 63 dithers; these
are exact zero.

**So there is no bisect to run.** Gate 2's branch condition was "if they
MOVE"; they do not. Three bitstreams — the two current ones (S83) and the one
the bench lived on for the six days containing S54–S58's measurements — give
one answer. There is no commit that silenced these lanes, because there is no
bitstream on which this instrument has ever seen them work.

That is worth stating as a fact about the instrument as well as the part: S54
and S58 measured real preamp noise on 09-16 on `s41_mhrx_pullup_off`, and S84
read exact zero on `s41_mhrx_pullup_off`. Both cannot be readings of the same
path. Gate 3 says which one to keep.

---

## GATE 3 — the ad[0..2] witness (S83-Q1, authorised)

### The instrument

A cdc-style ones/toggles/frames counter on `ad[0]`, `ad[1]`, `ad[2]`, riding a
**third knock** on the CM4 PCM link. RTL in `shared/dsp4-logic/rtl/` behind
`DSP4_AD_WITNESS`, default OFF; artifact
**`dsp4_logic_adwit.cbf1dbb1424a`**, `design_id 32'hdbb1424a`,
`cfg_bits 0x0040`, 695/1270 LEs (55 %), 513 registers, fmax 65.25 MHz, sim
gate PASS on all five testbenches.

    play  {L = 0xAD075E2<n>, R = ~L}   for lane n = 0, 1, 2
    record, 128 frames:
      L = {5'b0, lane[1:0], ad_ones_last[8:0], 7'b0, ad_ones_max[8:0]}
      R = {0xAD07, ad_toggles_last[8:0], frame_counter[15:9]}

One lane per knock: three lanes at the cdc witness's precision do not fit in a
64-bit reply, and a coarser reply would not separate "stuck high" from
"carrying data", which is the whole question. The lane is echoed back in the
left word and checked. `lane = 3` is not a knock (no converter on AD3) and the
testbench asserts that, so the guard cannot be deleted silently.

Sampled on `bck8_sample` — the same edge the DSP samples the lane on, and the
same edge the cdc_o witness uses, deliberately: the two are comparable only if
they count the same thing.

Reader: `tools/pi/dsp4_ad_witness.py`. It refuses `--reps 1`, and it takes the
**cdc_o control arm by default** — the same counter, same strobe, same
bitstream, pointed at the lane S83 and S84 both measured live.

### S84-3 — all three AK5558 lanes are CARRYING DATA at the CPLD

Flashed FLASH-OK on attempt 1; design ID read back and `MATCHES --expect
dbb1424a` before any reading was taken. Median of the reply frames, three
knocks per arm:

| arm | rails DOWN, 595 as found | rails UP, 595 `0xFC` unmuted gain 63 |
|---|---|---|
| `cdc_o` *(control)* | ones 48, toggles 24, max 91 — **CARRYING DATA** | ones 47–49, toggles 24, max 91 — **CARRYING DATA** |
| `ad[0]` | ones 94–98, toggles **26**, max 186 — **CARRYING DATA** | ones 93–96, toggles **26**, max 187 — **CARRYING DATA** |
| `ad[1]` | ones 94–96, toggles **26**, max 186 — **CARRYING DATA** | ones 96–97, toggles **50**, max 187 — **CARRYING DATA** |
| `ad[2]` | ones 95–96, toggles **26**, max 187 — **CARRYING DATA** | ones 95–97, toggles **48**, max 187 — **CARRYING DATA** |

Every arm's frame counter advanced between knocks, so no arm's numbers are
reported on a stalled witness.

Roughly 95 of 256 bit periods high with 26 transitions per 48 kHz frame is not
a dead pin, not a tied-off pin and not a stuck pin. It is eight channels of a
quiet, converting AK5558.

### S84-4 — ad[1] and ad[2] respond to the analog rails; ad[0] does not

Raising the rails and unmuting the 595 chain at gain 63 **roughly doubles the
toggle count on `ad[1]` (26 → 50) and `ad[2]` (26 → 48)** and leaves `ad[0]`
unchanged at 26, reproducibly, across both gate-3 runs. So those two lanes are
not merely alive, they are carrying more entropy when the front end in front of
them is switched on — which is a live analog signal path reaching a converting
ADC. `ad[0]`'s indifference is recorded as a fact, not yet as a fault: it may
be a different mic group, a different rail, or the AND-code gain behaviour
S57 found. It is a thing to look at, not a thing to conclude from.

### S84-5 — the two-sided reading, one bitstream, one pass

The cleanest form of the result, because it removes the last thing a careful
reader could object to — that gate 2 and gate 3 ran on different bitstreams.
`s84_gate3b.sh` takes both readings in one run on the witness build (which is
the shipping RTL plus counters, so its lane path IS the shipping lane path),
rails up, 595 at `0xFC`, both chips BOOT_STAGE 7:

| side | reading |
|---|---|
| the PINS (`ad[0..2]`, third knock) | **CARRYING DATA** — ones 96/98/97, toggles 26/50/48, all three frame counters advancing |
| the BUFFERS (`_buf_C1_IN_*`, SPI peek) | **0 of 32 moving**, exact digital zero |
| the codec buffers (`XIN_CODEC_*`) | **4 of 4 moving**, same pass |
| controls | `FRAME_COUNT +36936`, `_rx_slot_C1_IN_01` 1 distinct |

**VERDICT, one line: the AK5558 outputs are moving and the DSP reads zero, so
the break is between the CPLD's `ad[0..2]` input pins and the graph buffers —
downstream of the converters, and inside this repo's own domain.**

### S84-6 — where the break can and cannot be, and the one measurement that would decide it

This is analysis, marked as such, and it is handed over rather than acted on.

The CPLD's mux is not it. `net_sel` is `4'b1000` in **both** arms of its
ternary, so lanes 0–2 take `ad[]` whatever `strap_d32` does — S83 established
this from the source and it still holds.

The DSP side from `i_dspa` inward is not obviously it either. Under `driveall`
the CPLD substitutes the Pi stream for `i_dspa` and the same buffers carry it,
which proves pin → SPORT → RX DMA → slot map → buffer good for that stimulus.

What `driveall` does NOT prove is the part that is now suspect: **under
`driveall` the lane is launched by the CPLD's own `bck8_launch`, whereas
`ad[0..2]` are launched by the AK5558s off `conv_bck`, which the CPLD generates
and which reaches them down a net with five 33R taps and returns.** The
round-trip delay is not in the `driveall` path at all. A lane whose data
arrives at the wrong phase for the DSP's sampling edge is exactly the class
S78-3 located on the Pi stimulus, where seven of chip 1's eight RX halves read
one bit left because `c1_rx_lanes_mfd = {2,2,2,2,2,2,1,2}` and only lane 6
matched. Exact zero on every slot rather than shifted data is not the obvious
signature of a phase error, which is why this is a hypothesis and not a
finding.

The measurement that discriminates costs one more build of the same witness:
**count `ad[0..2]` on `bck8_launch` as well as on `bck8_sample` and compare.**
If the two disagree the phase is wrong and it is a lane-config fix; if they
agree the data is being sampled correctly at the CPLD and the loss is further
in. Nothing else needs to be flashed to find out.

---

## What was changed in the tree

| file | change |
|---|---|
| `shared/dsp4-logic/rtl/dsp4_logic_top.v` | the ad[0..2] counters, behind `DSP4_AD_WITNESS` |
| `shared/dsp4-logic/rtl/dsp4_pcm_reframe.v` | the third knock, its lane select and the reply mux |
| `shared/dsp4-logic/build.sh` | `AD_WITNESS` switch, `ad_witness=` in `CFG_LINE`, cfg_bits bit 6, and the manifest now records `logic_elements` / `registers` / `pins` from the fit (they were only ever in the fit report) |
| `shared/dsp4-logic/sim/tb_pcm_capture.v` | knock-3 arm: three lanes round-tripped through `ad_sel`, plus the lane-3-is-not-a-knock negative control |
| `tools/pi/dsp4_ad_witness.py` | new — the reader, with the cdc_o control arm and the frame-counter refusal |
| `tools/pi/logic_flash.sh` | **the default rollback was stale for the third time** and is set from the flash log: it named `s41_mhrx_pullup_off` a day after the part stopped carrying it, through every S77–S83 flash. Now `dsp4_logic.7a6a4529f29c.svf`. |
| `shared/dsp4-logic/bitstream/dsp4_logic.7a6a4529f29c.manifest` | `built_from: a1536bc6`, verified by recomputing the label from a clean `git archive` of that commit — and the one-line way to check it without Quartus |
| `shared/dsp4-logic/bitstream/retired/README.md` | the "lived on it for a month" heading and the "pre-S34" discriminator both corrected |
| `docs/d24-bench-logic-flash-log.md` | new — the dated table |

### S84-7 — the shipping label moves at HEAD, and the hub has to decide whether shipping follows

`SRC_HASH` covers `rtl/*.v` wholesale, so adding the witness — even behind an
`ifdef` that is off — renames the shipping build. Computed, not guessed:

| build | before S84 | at S84 HEAD |
|---|---|---|
| shipping (no switches) | `7a6a4529f29c`, `design_id 32'h4529f29c` | **`0cc6f94444b2`**, `design_id 32'hf94444b2` |

**The artifact on the part is untouched** — it is the same bytes, it answered
`32'h4529f29c` at handback, and it is still what `loadlogic.sh shipping`
names. What has changed is that it no longer rebuilds from HEAD, which is why
`built_from: a1536bc6` is now in its manifest and was verified this session.

There was no way to avoid this: the hash cannot tell a guarded addition from a
behavioural change, and a witness in a subdirectory the glob misses would be
worse — two functionally different bitstreams sharing one label, the exact
failure `build.sh`'s own comment exists to prevent. The cdc_o witness this one
copies IS built in every configuration including shipping, on the argument
that an instrument which only exists in a special build is an instrument
nobody has when they need it. Whether this one joins it — and whether shipping
adopts `0cc6f94444b2`, which would mean re-checking S82's 84.34 % D24 driven
capacity row on it — is the hub's call. **S84 did not make it, and left the
switch OFF by default and the diagnostic clearly named `_adwit`.**

---

## Unit as found

* **Shipping bitstream restored**, FLASH-OK on attempt 1, and **read back off
  the part**: `design_id: 32'h4529f29c   cfg_bits: 16'h0010   SHIPPING`.
* As-found pair `84c7951333e982204a38fe65e49d3fd6` / `bb2a7c6ea9e5d0caa419bc0b15a97f7c`
  booted and configured for D24; **both chips BOOT_STAGE 7, zero SPI errors**.
* 595 **SAFE image `0x01` VERIFIED 200/200**, written after the last DSP boot
  (S70-7).
* `AN_EN` (GPIO26) `lo` and `CS_M` (GPIO27) `ip pu`, both read back.
* `matrix-app` active, **3 of 3 MCUs verified on the FIRST restart**
  (H1S1, H1S3, H1S4).
* Nothing written to `~/dspboot`; the S82 deploy is still staged, not deployed;
  `~/dspboot/ldr/manifest.txt` untouched. No DSP image was built this session —
  every read ran on the staged S83 arm or the as-found pair.
* `defs.lock` did not move and no contract note is due.

## Findings

* **S84-1** "Pre-S34" is not the discriminator for the converter clock: the
  step-0 lineage does not contain `ded71079` and drives the pair anyway, with
  the same two assignments HEAD carries. Two lineages drive it, one artifact
  does not, and nothing may be inferred from a build date.
* **S84-2** 32 of 32 AK5558 mic lanes read exact digital zero on
  `s41_mhrx_pullup_off` — the bitstream the flash log puts under S54–S58 —
  with all four codec lanes live in the same pass. Three bitstreams, one
  answer: there is no bisect to run.
* **S84-3** All three `ad[0..2]` lanes are CARRYING DATA at the CPLD: ~95 of
  256 bit periods high, 26–50 transitions per frame, high-water 186–188, with
  the cdc_o control arm answering data and every frame counter advancing.
* **S84-4** `ad[1]` and `ad[2]` roughly double their toggle count when the
  rails come up and the chain is unmuted; `ad[0]` does not move. Recorded, not
  yet diagnosed.
* **S84-5** Pins moving and buffers at exact zero **in one pass on one
  bitstream**, both controls satisfied. The break is between the CPLD's
  `ad[0..2]` input pins and the graph buffers.
* **S84-6** The suspect the `driveall` proof never covered is the launch phase:
  `driveall` launches from the CPLD's own strobe, the AK5558s launch off
  `conv_bck` down a five-tap net and back. Counting `ad[]` on `bck8_launch`
  beside `bck8_sample` decides it and needs no new instrument.
* **S84-7** The shipping build's label moves to `0cc6f94444b2` at HEAD as an
  unavoidable side effect of touching `rtl/`. The artifact on the part is
  unaffected and now records `built_from: a1536bc6`, verified.
* **S84-8** `logic_flash.sh`'s default rollback was stale for the third time
  in its history — naming `s41_mhrx_pullup_off` a day after the part stopped
  carrying it. Fixed, and the flash log it says to set it from is now a table
  rather than 2.2 million lines.
* **S84-9** The witness's lane echo earned its bits on its first run: the
  reader extracted the lane from bits [25:24] instead of [26:25], which is
  `{lane[0], ones_last[8]}` and therefore reads correctly for lane 0 and
  wrongly for lanes 1 and 2. It reported a mismatch and refused to print
  numbers rather than reporting lane 0's data three times. The testbench
  stand-in had the same wrong layout, which is why sim passed — fixed to the
  real layout, so the class is caught in sim from here.

## Open for the hub

* 🟡 **S84-N1** Does shipping adopt `0cc6f94444b2` (and re-check S82's 84.34 %
  D24 driven row on it), and should `DSP4_AD_WITNESS` become unconditional
  like the cdc_o witness it copies? Left OFF and unsigned this session.
* 🟡 **S84-N2** S83-Q2 (the AUX 1 → J1 cable) is still with PW. Nothing in
  S84 depends on it: the floor, not the tone, carried every verdict here.
