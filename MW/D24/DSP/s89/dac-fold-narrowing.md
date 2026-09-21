provenance: AI-drafted 2026-09-21 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S89c — narrowing the DAC fold to one stage and one trigger

Session 89c, 2026-09-21. Analysis and digital-only measurement; no physical
action on the unit (not flashed, not recabled, AN_EN left `lo`, parked exactly as
S89b left it). Companion to `MW/D24/DSP/s89/dac-fold.md`, which holds the S89
investigation this builds on. Separate file rather than a new section there,
because the S89 report is already long and this answers a different question.

## Answer in one paragraph

**The corruption is periodic at exactly the audio block rate, it is about two
samples wide out of every sixteen, and it carries stale data rather than
arithmetic damage.** Those three facts come from the measured spectrum, not from
inspection, and each is separately falsifiable. The digital chain is now proven
clean **to the last DM word before the DMA** — 1024 contiguous samples with every
component at or below −110 dBc — so the corruption enters in the gather → TX DMA
ring → SPORT → codec span. Within that span only one stage has block periodicity
at all, which is what makes this a one-probe question rather than a search.
**The load hypothesis is dead, and it died informatively: the folding arm is the
LIGHTEST of the three** (chip 2 worst-block 78.8 % of budget, against 93.1 % on
an arm that does not fold).

## 1. The period, from the spectrum alone

S89 recorded the fold's spectrum but read the pattern as "block-rate structure".
It is sharper than that, and the sharpness is the point.

The measured components are 2, 4, 5, 7, 8, 10 kHz at −11.2 to −12.6 dBc, with
**3, 6 and 9 kHz absent at −79 dBc**, and further components at 11, 13, 14 and
16 kHz at −18.4 to −20.5 dBc. Those are not harmonics. They are the set

    | f0 ± k · fb |   with f0 = 1 kHz and fb = 3 kHz

which is 1, 2, 4, 5, 7, 8, 10, 11, 13, 14, 16 kHz — and which contains no
multiple of 3 kHz. A 79 dB null sitting between two −11 dBc neighbours is not a
coincidence; it is the arithmetic of a disturbance whose repetition rate is
**exactly 3.000 kHz**.

    3.000 kHz = 48 000 / 16 = one audio block
              = 16 samples = 333.333 µs

Modelled directly (host-side, `dsp4_fft`'s own window), a once-per-block
disturbance reproduces the presence/absence pattern exactly: the 3/6/9 kHz bins
come out at −131 to −142 dB, i.e. nothing, while every other multiple is
populated at one level.

**So the fold is not a distortion of the waveform's shape.** A nonlinearity would
put energy at 3, 6 and 9 kHz like every other harmonic. This does not.

## 2. The width, from the comb's roll-off

A disturbance one sample wide gives a **flat** comb — every sideband at the same
level, because a single-sample impulse is white. The measured comb is not flat:
it falls about 9 dB from the 2 kHz component to the 16 kHz one. Fitting the
width against all ten measured components:

| error width | 2 kHz | 8 kHz | 16 kHz | rms error vs measured |
|---|--:|--:|--:|--:|
| 1 sample | −16.9 | −16.9 | −16.9 | 4.33 dB |
| **2 samples** | **−9.7** | **−11.1** | **−14.6** | **3.95 dB** |
| 3 samples | −4.9 | −9.0 | −26.6 | 5.32 dB |
| 4 samples | −0.9 | −9.9 | −13.4 | 53.20 dB |
| *measured* | *−11.4* | *−12.6* | *−20.5* | |

**About two samples, ≈41.7 µs**, out of every sixteen. One is too flat, three
rolls off far too steeply (its first null lands inside the band).

## 3. What the two samples contain: stale audio, not damaged audio

Re-fitting with the error being *substituted* rather than inverted — the two
samples carrying the value from an earlier block, which is what a buffer-handoff
race produces — improves the fit and, more importantly, gets the **absolute
level** right rather than only the shape:

| hypothesis | 2 kHz | 8 kHz | 16 kHz | rms error |
|---|--:|--:|--:|--:|
| 1 sample/block, stale | −18.5 | −18.5 | −18.5 | 5.23 dB |
| **2 samples/block, stale** | **−11.7** | **−13.2** | **−16.7** | **2.54 dB** |
| 3 samples/block, stale | −7.6 | −11.7 | −29.3 | 4.54 dB |
| *measured* | *−11.4* | *−12.6* | *−20.5* | |

2.54 dB rms across ten independent components, with the level predicted to
0.3 dB at 2 kHz. **One block of staleness on a 1 kHz tone is 120° of phase**, so
a stale sample differs from the right one by 2·sin(60°) = 1.73 × amplitude — and
an independent energy estimate from the measured 60 % THD+N gives 1.7 ×
amplitude. Two routes, same number.

The residual 2.5 dB is all in the top octave (predicted −16.7 at 14/16 kHz
against −20.5 measured), i.e. the real error is slightly smoother than a hard
rectangular substitution — which is what a reconstruction filter does to it, and
is expected for something measured through a DAC, a cable and an ADC.

**A lag of one block and a lag of two blocks are indistinguishable here** (120°
and 240° give the same magnitude of error on a 1 kHz tone), so the width is
stated with confidence and the depth is not.

## 4. Gate 1 — where the clean chain actually ends

S89's elimination list, restated precisely, because "everything digital is clean"
was doing more work than the measurements supported:

| S89 check | what it actually covers | what it does not |
|---|---|---|
| MeasChan 20 = 0.00019 % | chip 1, strip 20's chain, at its **post-fader pool block** | everything after the pan/bus send |
| compressor identical at four levels | the **COMP node's arithmetic** on chip 1, at the same tap | any stage downstream |
| BLK_OVERRUN zero delta | no **sustained** backlog on either chip | an occasional late block (see §5) |
| `_tx_out_slot_C2_MON_OUT` "a correct sine" | **16 non-atomic peeks**, each from a different block | anything with block periodicity — which is this defect |

The last row is the gap, and it was a real one: a peek is one SPI transaction per
word, so sixteen words span ~15 audio blocks and *cannot resolve a defect whose
period is the block*. **This session closed it properly.**

`_scope_record` runs inside chip 2's own gather loop and stores
`_scope_src[_sample_idx]` once per sample, so it yields genuinely contiguous
audio. Pointing it at the Monitor output slot on the **folding** arm
(`s89_b5_dynlut`, `SIMD_DYN=1 + DYN_LUT=1`, link verified clean, tone live at
−18.02 dBFS in the slot):

    fundamental                 -18.03 dBFS
    every multiple of 1 kHz     -110.0 dBc or lower  (2k -115.2, 3k -112.4,
                                4k -121.7, 5k -112.6, ... 16k -115.3)
    FOLD metric, contiguous     -0.02 dB
    mean by block position      a clean monotone ramp, no position stands out

**The last DM word before the DMA is clean to better than 110 dB on the arm that
folds.** That is 1024 contiguous samples, not sixteen scattered ones, and it is
the measurement S89 was missing.

So the clean chain now ends at `_tx_out_slot_C2_MON_OUT`, and the corruption
enters in exactly four remaining stages:

1. `_gather_chip2` — reads the slot, packs Q4.28 → Q1.31 with saturation, writes
   `_tx_active_buf + off + k·stride`;
2. the **TX DMA ring half** — ping/pong, chosen by `_blk_latch_bufs`, with
   `DSP4_TX_EARLY=2` deliberately writing one half ahead on chip 2;
3. SPORT 2 half B serialisation — MFD 2, 8 slots × 32 bits, 12.288 MHz BCK;
4. the codec DAC.

**Only stage 2 has block periodicity.** Stage 1 is per-sample arithmetic that
does not depend on either switch. Stage 3 repeats every frame (20.833 µs), not
every block. Stage 4 has no block structure at all. A defect whose period is
exactly 16 samples and which is two samples wide is a **buffer-half handoff**,
and nothing else in that list can produce one.

## 5. Gate 3 — the load hypothesis is dead, and its death has the wrong sign for "too slow"

`BLK_OVERRUN` cannot see an occasional over-budget block: it counts only blocks
where `_block_ready` was still set when the ISR fired, i.e. a sustained backlog.
The capacity doc's own case is a latch of 124.06 % on an arm averaging 60.27 %.
`_proc_cyc_max` is the instrument that sees it, and `DIAG_CLEAR` zeroes it so the
config ladder's transient is excluded (S13-2).

Measured, tone live, counters cleared after config, six seconds each:

| arm | chip 1 worst block | chip 2 worst block | fold |
|---|--:|--:|---|
| `SIMD_DYN=1 + DYN_LUT=1` | 47.15 % | **78.81 %** | **folded** |
| `SIMD_DYN=1` only | 54.29 % | 86.84 % | clean |
| `DYN_LUT=1` only | 59.87 % | **93.07 %** | clean |

**The arm that folds is the lightest of the three, by 14 points on chip 2 against
an arm that is clean.** No arm comes near the budget. This rules out over-budget
blocks, a late gather from graph pressure, and the LUT design burst — and it does
so in the direction that matters: the fold is associated with the graph being
*faster*, not slower, which is exactly what one expects of the two switches
together (the paired table lookup is 54.1 cycles per sample-pair against the
polynomial's 215.2, measured).

That is a real constraint on the mechanism and it should be stated as one: **any
proposed cause that works by the core running out of time is already refuted.**
What remains is a handoff whose correctness depends on *when* in the period the
core writes, with the fast case being the broken one.

### Ruling S89-1 in or out as a shared cause

Ruled **out**, and confirmed rather than assumed. S89-1 (the inter-chip sign-bit
loss) is build-independent — it appears on the `s51` diagnostic pair, which
carries neither switch — and it is per-boot, roughly one boot in seven, all three
lanes together. This fold is switch-dependent, deterministic on every boot
(measured five consecutive boots at 59.6–59.8 %, including boots where the link
gate had to retry), and reaches the DAC on a link that verified clean. Different
defect, different chip, different periodicity. Every arm in this session was
booted through `dsp4_boot_linked.sh` precisely so the two cannot be confused.

## 6. Gate 4 — the scope brief

**Hypothesis to test.** Two frames out of every sixteen leave the codec's serial
data line carrying the previous block's audio, because the core's gather and the
DDE's read of the TX DMA half are not correctly interlocked when the graph
finishes early.

**Probe.** The codec DAC serial input and its clocks, on the digital board:
`CDC_I` (DSPB O2 → codec DAC serial data — hardware map line 157), plus `BICK`
and `LRCK/FS` for that codec. Three channels; `CDC_I` is the one that carries the
answer, the other two are timebase. *The exact designators must come off the
schematic, not this document.* Note also a **naming discrepancy to settle before
the session**: `MW/D24/HW/hardware-map.md` calls this part **AK4916 ("CODEC4")**
while `s70lib`, S79 and `tools/pi/codec4619.py` call it **AK4619**. Have the right
datasheet open.

**Trigger.** Not on the audio. Trigger on the **block boundary**, which is every
16th frame sync — either divide FS by 16 externally, or trigger on FS and use the
scope's Nth-event/holdoff at 333.33 µs. Arm the tone at 1 kHz, −12 dBFS into a
strip routed to the Monitor, exactly as `tools/pi/dsp4_loop_thd.sh` sets it up.

**What a positive result looks like.** With the serial data decoded as 32-bit
words: the first one or two frames after each block boundary carry a word that is
*not* the correct next sample of the 1 kHz sine but a repeat of a word from
120° or 240° earlier in the cycle — i.e. a visible discontinuity of up to 1.7×
the amplitude, once every 333.33 µs, at a fixed position relative to the block
boundary. On the analog side of the same DAC the same event is a step, not a
clip and not a spike: **the waveform jumps to a wrong point on the sine and
continues correctly from there**, which is what PW's scope read as
"wrap-around/folding".

**What falsifies it.** If `CDC_I` carries a clean, monotonic 1 kHz sine with no
discontinuity at the block boundary while the analog output of the same codec is
folded, then the digital side is exonerated entirely and the defect is inside the
converter or its supply — at which point the probe moves to the codec's AVDD/VREF
with the same 333.33 µs trigger, looking for a supply artefact locked to the
block rate. If instead the discontinuity is present but its position is *not*
locked to the block boundary, the two-sample/one-block model above is wrong and
the width fit in §2 needs re-doing against the new period.

### A cheaper route that should be tried first

**The scope may not be needed.** `src/tx_probe.asm` already exists for exactly
this question — it stamps each transmitted frame with its block counter, buffer
half (ping/pong) and sample index, and S9-2 used it to measure the identical
failure mode ("87.4999 % of transmitted frames ordered", one bad sample per
16-sample window; this fold is the same thing two samples wide). Read back, it
gives the displacement **in blocks, directly**, instead of inferring it from
audio.

Its cost is that it writes into SPORT3's unused slot 1 and is read through the
Pi capture path, so it needs the `_maincap` LOGIC build flashed — a bitstream
change, which is why it was out of scope tonight. That is still far cheaper than
a scope session and needs no PW hands beyond the flash, and the S88 runbook step
(flash → design-ID readback → DSP double boot+config) already covers restoring
shipping afterwards. **Recommendation: run the TXPROBE arm first; keep the scope
brief for the case where the stamps come back in order.**

There is also a structural coincidence worth noting for whoever builds that arm:
S89-2 found that **codec slot 1 is driven but written by no gather entry** — the
same free-slot situation on the codec lane that `tx_probe.asm` exploits on
SPORT3. A stamp written there would ride the lane that actually feeds the folded
output, rather than a neighbouring one.

## 7. What this session did NOT establish

Stated plainly so the next session does not assume otherwise:

- **The mechanism is not named.** The stage is identified by elimination and by
  periodicity, not observed. No line of code is accused.
- **Why the switch pair changes a stage neither switch's code touches** is not
  explained. The honest form is: the pair changes the graph's *timing*, and the
  only downstream stage whose correctness is timing-dependent is the DMA-half
  handoff. The "runs early" direction is consistent with the measured cycle
  counts but is **not proven** — `_blk_latch_bufs` is gated by `_block_ready`
  once per ISR, so a fast core should not be able to run it twice, and that
  tension is unresolved.
- **The lag depth** (one block vs two) is not resolvable from a 1 kHz tone.
  A two-tone or a non-commensurate frequency would separate them, and is worth
  one capture if the TXPROBE route is not taken.
- No fix is proposed, nothing was applied, and the signed triple is untouched.

## Files

- `MW/D24/DSP/s89/dac-fold.md` — the S89 investigation this narrows.
- `tools/pi/s89_slotcap.py` — coherent capture of a per-sample node slot via
  `_scope_record` (the instrument the peek could not be).
- `tools/pi/s89_cyc.py` — the worst-block high-water mark, with `DIAG_CLEAR` so
  the config ladder is excluded.

---

# S89d — the code search came back empty, and `tx_probe` needs the bench after all

Appended to this file rather than opened as `dac-fold-mechanism.md`: no mechanism
was established, so a file named for one would be misleading. This is the same
narrowing, one step further in, plus a correction to S89c's own framing.

## 🔴 S89d-Q1 — `tx_probe.asm` cannot be run without a CPLD flash

**This contradicts S89c's framing and the dispatch built on it, so it is stated
first.** S89c recommended `tx_probe.asm` as "the cheaper route before a scope",
which is true — it is cheaper than a scope session — but S89c also said it "needs
the `_maincap` LOGIC build flashed", and the dispatch read the recommendation as
*bench-free*. It is not. Read end to end, `tx_probe.asm` is a **write-side**
instrument:

    _tx_probe_stamp:
        r1 = dm(_tx_active_buf);      /* the half the gather just wrote */
        ...                            /* off + sample*stride + 1 */
        dm(i4, 0) = r3;                /* block ctr | ping-pong bit | sample idx */

It writes the stamp **into the TX DMA ring**, in the slot next to the audio, and
the stamp then leaves the part on the wire. Nothing reads it back on-chip. The
readback path is the CPLD → Pi capture, which is why the file's own header
specifies the `_maincap` LOGIC build and `CAP_SLOT_L=0 / CAP_SLOT_R=1`.

**Exactly what it needs, in order:**

1. Build a `DSP4_TXPROBE=1` arm of the folding configuration — host-side, free.
2. **Flash a capture LOGIC bitstream** (`dsp4_logic_maincap.1216e35175cb` or the
   current equivalent), displacing shipping `83b3cc22` in flash. *This is the
   parked-unit violation and the reason this dispatch stops here.*
3. **Switch the Pi PCM overlay to duplex** — `config.txt` line 74 currently
   selects `dsp4-pcm-slave`; the capture path needs duplex. Edit plus a Pi
   reboot, ~30 s back.
4. DSP double boot+config after the LOGIC flash — the S88 runbook step, without
   which the SPORTs stay configured against the pre-flash clock relationship.
5. `arecord` on `hw:dsp4pcm,0`, decode the stamps.
6. Restore: reflash shipping, design-ID readback, double boot+config, overlay
   back, re-park.

Two flashes and an overlay round trip; call it 45–60 minutes with the
verification. No PW hands are needed beyond authorising it — the flash is
OpenOCD on the CM4's own GPIOs, not a JTAG pod.

**One correction to carry into that session.** `DSP4_TXPROBE_LANE` defaults to
18, which is `C2_MAIN_ST_OUT` on SPORT3 — the Pi return lane, not the codec lane
(SPORT2, entry 16) that carries the folded Monitor and AUX output. That default
is nevertheless **the right choice here**, and for a reason worth knowing: all
five of chip 2's TX lanes share **one** DMA region and **one** `_tx_active_buf`
pointer, toggled by **one** ISR (`LAST_CSID 37`, SPORT0_A_DMA). So a *write-side*
half-handoff fault is common to every lane and lane 18 is representative. The
caveat is the mirror image of that: each SPORT has its own DDE channel, so a
*read-side* per-channel skew would **not** show on lane 18. If the stamps come
back in order on lane 18, that does not yet exonerate the codec lane — it moves
the suspicion from the shared write side to the per-channel read side, which is a
useful bisection in itself.

## S89d-1 — there is no index or pointer difference to find. The handoff code is identical.

Gate 3 asked for a concrete code search: *find where the index/pointer
computation differs between the folding and clean configurations.* **It was done,
and it came back empty — decisively.** That is a result, not a failure to look,
and it removes a whole class of explanation.

**Source level.** The files that own the handoff do not mention either switch:

| file | contains | `DSP4_SIMD_DYN` | `DSP4_DYN_LUT` |
|---|---|--:|--:|
| `sport_init.asm` | `_blk_latch_bufs` — the ring-half selection | 0 | 0 |
| `chip2/block_io.asm` | `_gather_chip2`, `_scatter_chip2` | 0 | 0 |
| `dma_config.c` | the DDE rings, `SPEN` | 0 | 0 |
| `main.asm` | the chip-2 block loop | 2 | 0 |

and `main.asm`'s two are both `#if DSP4_SIMD_DYN && DSP4_DYN_SELFTEST`, which is
off in every configuration here, so they compile to nothing.

**Binary level**, which is the part that actually settles it. Comparing the
signed arm against `DSP4_SIMD_DYN=0` and against `DSP4_DYN_LUT=0`, all three
built from the environment S89b proved reproduces the signed pair byte for byte:

| routine | signed | SIMD_DYN=0 | DYN_LUT=0 |
|---|--:|--:|--:|
| `_scatter_chip2` | 55 B | 55 B | 55 B |
| `_gather_chip2` | 69 B | 69 B | 69 B |
| `_blk_latch_bufs` | 27 B | 27 B | 27 B |
| `_sport_dma_work` | 66 B | 66 B | 66 B |
| `_meter_scan_chip2` | 51 B | 51 B | 51 B |

Same length in every arm. The raw bytes differ only because the DM variables they
reference are relocated when the kernels' data footprint changes — and
disassembled, the difference vanishes:

    $ diff p_signed.gather.txt p_nosimddyn.gather.txt   -> no difference
    $ diff p_signed.gather.txt p_nolut.gather.txt       -> no difference
    $ diff p_signed.latch.txt  p_nosimddyn.latch.txt    -> no difference
    $ diff p_signed.latch.txt  p_nolut.latch.txt        -> no difference

`_blk_latch_bufs` in full, identical in all three arms:

    _blk_latch_bufs:
        r0 = dm(_rx_pend_buf);
        dm(_ic_rx_active_buf) = r0;
        r0 = dm(_tx_pend_buf);
        r1 = dm(_tx_ping_w);
        comp(r0, r1);
        if ne jump (pc, .txe_have);
        r1 = dm(_tx_pong_w);
    .txe_have:
        r0 = r1;
        dm(_tx_active_buf) = r0;
        rts;

**So whatever the displacement turns out to be, it is not computed differently.**
The ring-half selection, the gather, the scatter and the block ISR are the same
instructions in the arm that folds and in the two that do not. Gate 3's "find the
line" has no line to find, and any future explanation must account for identical
code behaving differently — i.e. timing, data placement, or bus behaviour, not
control flow.

## What this leaves, and what it costs

| hypothesis | status after S89d |
|---|---|
| different ring-half index/pointer computation | **refuted** — instruction-identical |
| over-budget blocks / late gather | refuted in S89c — the folding arm is the lightest |
| nonlinearity in the audio path | refuted in S89c — no energy at 3/6/9 kHz |
| corruption upstream of the DMA | refuted in S89c — slot clean to −110 dBc, 1024 contiguous samples |
| shared cause with S89-1 | refuted in S89c — build-independent vs switch-dependent |
| **write-side half handoff, timing-dependent** | **open** — needs `tx_probe` (a flash) |
| **read-side per-channel DDE skew** | **open** — `tx_probe` on lane 18 does not cover it |
| **data placement / bus contention** | **refuted** — tested below |

### Data placement: raised, tested, and refuted in the same session

The one thing that *does* differ between the images, outside the kernels, is
where the DM variables land — which is why the handoff routines' byte images
differ at all while their disassembly does not. Chip 2's DM total moves by
38,520 bytes between `DYN_LUT=1` and `DYN_LUT=0` (S89b), so it was worth asking
whether the TX ring or its pointers cross a memory-block boundary in one
configuration and not the other, which would be switch-dependent, timing-shaped,
block-periodic and invisible to everything checked so far.

It does not survive contact with the link maps:

| symbol | signed (folds) | `SIMD_DYN=0` (clean) | `DYN_LUT=0` (clean) |
|---|---|---|---|
| `c2_tx_buf_ping` (the TX DMA ring) | `0x2D3200` | `0x2D2AE0` | `0x2C9D80` |
| `_tx_active_buf` | `0x0B4711` | `0x0B4549` | `0x097F71` |
| `_tx_ping_w` / `_tx_pong_w` | `0x0B4716/17` | `0x0B454E/4F` | `0x097F76/77` |

**The folding arm and the `SIMD_DYN=0` clean arm sit in the same regions**, 0x720
words apart for the ring and 0x1C8 apart for the pointers. It is `DYN_LUT=0` —
also clean — that relocates wholesale. So membership of a memory block does not
track the fault: if the region mattered, `SIMD_DYN=0` would fold, and it does
not. Refuted, and recorded here so the next session does not raise it again.

## Is a scope still needed?

**Not yet, and possibly not at all.** The remaining open hypotheses are all
digital and all reachable without probing a pin:

- write-side handoff → `tx_probe` (one flash, as above);
- read-side DDE skew → `tx_probe` on a second lane, or the DDE's own
  current-address register sampled from firmware;
- read-side DDE skew → `tx_probe` on a second lane, or the DDE's own
  current-address register sampled from firmware.

The link-map comparison that would have been the cheap next step was run tonight
and came back negative (above), so **`tx_probe` on the folding arm is now the
cheapest remaining step**, and it costs the two flashes in S89d-Q1. The scope
brief in §6 stands as the fallback for the case where the stamps come back in
order on lane 18 — which would point at the per-channel read side rather than
exonerate the transmit path.
