provenance: AI-drafted 2026-09-26 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S115 — AL1 on bandpass THD, today's failures explained, and a silent handback

Hub dispatch `HUB DISPATCH 2026-09-26 11:39Z` plus addenda 1-4. Bench: MW-D24-2
(rev C+), pair `/home/app/loopthd/s109` (`DSP4_TEST_NODES=1`), chip1.ldr
`7f226919a5d181410c3804d92678da19`, chip2.ldr `6f11a1ddc6efd45ec30f536cef295292`.
All times UTC unless marked BST.

**Headline.** AL1's verdict is now bandpass THD (harmonics h2..h10, each
integrated in its own band, the noise between the bands excluded) off a coherent
capture of the MEMS lane taken inside the same session as the tone. On one press
the two instruments read, on the SAME window:

```
THD  h2..h10       -31.83 dB  = 2.562 %   ceiling -28.50 dB = 3.758 %   <-- THE VERDICT
THD+N (node)        -6.51 dB  = 47.244 %   ceiling -9.80 dB = 32.352 %   INFORMATIONAL
THD+N (capture)    -31.75 dB  = 2.584 %   INFORMATIONAL, the same window transformed
```

That −6.51 dB / 47.2 % IS the 45-46 % PW and S114 saw, reproduced here, on a
press that PASSES. The tone filled the capture (four quarters within 0.38 dB),
the fundamental is at 1000.0 Hz to the resolution of the transform, and the same
window transformed on the host contains essentially nothing but the tone and its
harmonics. The 45 % was the measurement, not the speaker — PW's ears were right.

The post-tone noise is fixed: every AL1 press now hands back with the speaker
path provably silent, and so does any press that boots the pair. The speaker was
live for **4.10-4.16 s** per press instead of indefinitely, and the analog rails
for **7.82-7.98 s** instead of the whole press.

---

## S0. What was measured with what

| instrument | what it is | used for |
|---|---|---|
| `C1_TEST_MEAS` MeasChan 54 | on-part accumulator over a 4,096-sample (85.3 ms) window: RMS, `ThdResult`, `NoiseResult` | tone level, both baselines, SNR, and `ThdResult` as an INFORMATIONAL THD+N line |
| `_scope_record` + `dsp4_bulk` + `dsp4_fft.analyse()` (NEW) | 1,024 contiguous samples (21.3 ms) of `_buf_C1_XIN_MEMS`, one streamed read, transformed on the unit | **the verdict**: bandpass THD, the harmonic table, the fundamental's frequency, the four-quarter window check |
| `s89_set.py` reads | SPI parameter reads through the image's own dispatch table | every cell state quoted below |
| product meter cell `MainL001Mtr001` | the mixer's own main meter | corroborating the MAIN bus level |

Cost of the capture, measured on the part: **0.085-0.090 s** to fill
`_scope_buf`, **0.100-0.105 s** for the `dsp4_bulk` streamed read — 0.19 s,
taken between the last measurement window and the fade-out, inside the tone's
own session.

**Only a node with its own block can be read this way.** Strip node buffers live
in the block pool (`gen_input_tdm`: "the pool is for strip inputs only"), so
`_buf_C1_FDR_nn` aliases whatever the pool last held. Caught on the bench during
this session: `_buf_C1_FDR_01`, `_buf_C1_FDR_12` and `_buf_C1_FDR_20` all read
+5.95 dBFS RMS with peak +11.97 dBFS, bit-identically, while `C1_IN_01/12/20`
read exactly zero. `C1_XIN_MEMS` is a non-strip converter lane and declares its
own `_buf_C1_XIN_MEMS[DSP4_BLOCK_SIZE]`, which is why it is readable and why it
is the tap AL1 uses. This is `[[dsp4-buf-symbols-are-not-buffers]]` again, one
step further: under block kernels a strip `_buf_` does not read as zero, it
reads as a *plausible waveform belonging to another node*.

---

## S1. The ruling implemented

`dsp4_s49_osc.py` gains `--cap-node SYM` / `--cap N`. After the measurement
windows and before the fade-out it arms `_scope_record` on `SYM`, waits for the
buffer, reads it back with `dsp4_bulk.read()` and hands it to
`dsp4_fft.analyse()`. The JSON it already wrote now also carries the samples, the
harmonic table and the derived figures.

`d24_selftest.py` AL1:

* `AL1_CAP_NODE = '_buf_C1_XIN_MEMS'`, `AL1_CAP_SAMPLES = 1024`.
* The capture is taken on the tone leg and on the FIRST baseline (the noise
  spectrum the tone is read against). Not on the second baseline — its job is to
  say the floor came back, which its RMS answers on its own.
* `al1_verdict`'s CLIP test is now `thd_db > thd_ceiling_db`.
* **No fallback.** A press whose capture does not come back is `NO DATA` with
  the reason, never a verdict off THD+N: "a THD-shaped ceiling applied to a
  THD+N number" is exactly how a clean loop came to read 45 %.
* The tone-present rule is UNCHANGED (`ThdResult <= -6 dB` OR `SNR >= snr_min`).
  A fit residual over half the window's energy is something a room cannot fake,
  and the dispatch asked for one limit to move, not two.
* Every AL1 figure is printed in dB and in percent (PW 2026-09-16). The glass
  line is `PASS base -55.0 tone -34.7 SNR 20.3 dB THD -31.8 dB 2.58%` — 62
  characters, inside the 70 the skin truncates at.

New evidence lines per press: the harmonic table in dBc and dBFS, the
fundamental's measured frequency, the capture's four-quarter RMS and spread, the
instrument's own THD floor, and both THD+N figures.

---

## S2. The new ceiling and its calibration run

`--al1-calibrate-thd` (new) runs the same calibration grid as `--al1-calibrate`
but writes **only** `thd_abs_db` and `thd_margin_db`; every other limit is left
exactly as it was. The dispatch asked for one limit to change, and this is how a
session proves it changed one: the diff the calibrator prints has two CHANGED
rows and nine unchanged ones.

```
  slope_db_per_db           1.029 ->        1.029
  intercept_dbfs          -29.650 ->      -29.650
  level_tol_db              4.000 ->        4.000
  level_hi_tol_db           7.000 ->        7.000
  snr_min_db               15.400 ->       15.400
  floor_max_dbfs          -48.300 ->      -48.300
  thdn_abs_db             -16.700 ->      -16.700
  thdn_margin_db           10.800 ->       10.800
  thd_abs_db                0.000 ->      -28.500   CHANGED
  thd_margin_db             0.000 ->        6.000   CHANGED
```

`thd_abs_db = -28.500 dB = 3.758 %`, stamp `2026-09-26T12:17:59Z`, 15 runs at
-12/-6/-3 dBFS x 5 reps, derived as (worst THD at the drive the test actually
runs at) + 3 dB. **PROVISIONAL** like every other AL1 limit, until the speaker
supplier's datasheet.

`thd_margin_db = 6.000` is a **constant**, not a fitted number, and that is a
deliberate correction made inside this session. The margin sits on top of the
capture's own THD floor — the noise inside the harmonic bands, which no reading
can beat — so its only job is to stop a reading that is already at the floor from
failing. The first calibration attempt fitted it as "how far past its floor a
healthy loop went" and produced `thd_margin_db 34.4`, which lifted the run-time
ceiling to −21.6 dB where the absolute one was −28.7 dB: it would never have
bitten. The reason is that this speaker genuinely distorts more at −3 dBFS than
at −12, so the widest gap between a reading and its floor is a measure of REAL
distortion. 6 dB clears the floor and leaves the absolute ceiling governing
whenever the room is not the limit — on this unit the floor sits 24 dB below it.
See `AL1_THD_FLOOR_GUARD_DB`.

### The calibration grid (`--al1-calibrate-thd`, 2026-09-26T12:17:59Z)

```
  drive    rep   baseline      tone        SNR       THD        THD     floor     THD+N        THD+N
  dBFS           dBFS       dBFS        dB        dB          %        dB        dB            %
   -12.0     1     -53.33     -41.70      11.62    -39.89      1.013    -49.87    -13.71       20.625
   -12.0     2     -56.55     -41.54      15.01    -39.98      1.002    -50.34    -11.06       28.006
   -12.0     3     -53.95     -41.72      12.24    -39.44      1.067    -49.79    -13.72       20.612
   -12.0     4     -53.45     -41.81      11.64    -39.65      1.041    -51.49    -17.49       13.343
   -12.0     5     -52.93     -41.80      11.13    -39.18      1.100    -50.15    -16.07       15.722
    -6.0     1     -55.76     -35.77      19.99    -31.50      2.659    -54.12    -27.24        4.346
    -6.0     2     -54.11     -35.76      18.35    -31.71      2.596    -56.73    -24.39        6.034
    -6.0     3     -55.94     -35.78      20.16    -31.56      2.642    -55.70    -29.44        3.371
    -6.0     4     -54.44     -35.79      18.65    -31.85      2.556    -55.85    -27.03        4.453
    -6.0     5     -53.61     -35.80      17.81    -31.50      2.662    -55.65    -28.27        3.857
    -3.0     1     -51.65     -32.67      18.99    -28.01      3.979    -58.68    -18.82       11.461
    -3.0     2     -53.12     -32.66      20.47    -28.03      3.969    -58.45    -17.91       12.728
    -3.0     3     -54.36     -32.61      21.75    -27.58      4.180    -55.83    -16.99       14.148
    -3.0     4     -55.40     -32.64      22.76    -28.12      3.926    -59.34    -16.87       14.342
    -3.0     5     -56.70     -32.64      24.05    -28.05      3.956    -59.06    -17.03       14.074
  mean at  -12.0: THD -39.63 dB = 1.044 % (spread 0.81 dB), THD+N -14.41 dB = 19.033 %
  mean at   -6.0: THD -31.62 dB = 2.623 % (spread 0.35 dB), THD+N -27.27 dB =  4.328 %
  mean at   -3.0: THD -27.96 dB = 4.001 % (spread 0.54 dB), THD+N -17.52 dB = 13.303 %
```

An earlier 15-run grid three minutes before this one (the full `--al1-calibrate`,
whose non-THD results were discarded) gave THD means of **1.035 / 2.576 /
4.001 %** against this one's **1.044 / 2.623 / 4.001 %** — the same numbers.
Its THD+N means were **19.0 / 4.3 / 13.3 %** here against **11.2 / 10.0 / 25.8 %**
there.

**That is the whole case for the ruling, measured twice.** THD rises
monotonically with drive (1.0 % → 2.6 % → 4.0 %), which is what a small speaker
does, and repeats between two independent 15-run grids to within 0.05 dB. THD+N
does not track drive at all, is non-monotonic, and moved by up to 6.5 dB at the
same drive level between two grids taken three minutes apart. In the first grid
the two quietest baselines of the whole session (−74.7 and −78.9 dBFS, the room
went silent) carried the two WORST THD+N readings of the whole session (34.5 %
and 35.1 %) — the opposite of what a noisy-room story predicts, and exactly what
a fit-residual story predicts.

---

## S3. Why every press failed today, named

### (a) The 45 % — a measurement fault, and the named cause is the node's fit

Reproduced under the new instrument on a PASSING press
(`logs/AL1-2026-09-26T123250Z-thdn-47pct-thd-2.6pct.txt`):

| quantity | reading |
|---|---|
| tone level | −34.64 dBFS (predicted −35.82, inside the 4 dB window) |
| baseline / SNR | −55.24 dBFS / 20.60 dB |
| **THD h2..h10 (the verdict)** | **−31.83 dB = 2.562 %**, ceiling −28.50 dB = 3.758 % |
| THD+N, the node's `ThdResult` | −6.51 dB = **47.244 %** — over its own ceiling; the OLD code scores this FAIL CLIP |
| THD+N, the same window transformed | −31.75 dB = 2.584 % |
| instrument THD floor | −55.30 dB (median-bin; see the caveat below) |
| fundamental | 1000.0 Hz at −35.75 dBFS |
| capture quarters | −34.29 / −34.67 / −34.43 / −34.29 dBFS, **spread 0.38 dB** |
| harmonics (dBc) | h2 −45.5 **h3 −32.2** h4 −62.1 h5 −46.0 h6 −57.9 h7 −59.2 h8 −68.5 h9 −68.7 h10 −66.6 |

Working through the four candidates the dispatch listed:

* **Window placement against the ~0.8 s tone: RULED OUT.** The capture's four
  quarters agree to 0.38 dB, so the tone is present across the whole of it; the
  oscillator was on for 0.79 s and `MeasChan` is written after the fade-in
  completes, so the node's windows sit inside the tone too. This is the direct
  answer to addendum 2(a): **the tone was present across the whole capture
  window.**
* **Noise inside the window: NOT ENOUGH ON ITS OWN.** The same 21.3 ms window
  transformed on the host has total-minus-fundamental at −31.75 dB, within
  0.08 dB of the pure harmonic sum. Over 21 ms there is almost nothing in that
  lane except the tone and its harmonics. The node's 85 ms window is reporting
  25 dB more non-fundamental energy than a transform of the same lane finds.
* **A level or scale change since 09-25: RULED OUT.** The tone reads −34.6 to
  −35.8 dBFS across every press today against S111's 09-25 PASS at −35.8 dBFS,
  and the fundamental sits at 1000.0 Hz. The level did not move.
* **Real distortion: PRESENT, AND IT IS 2.6 %, NOT 45 %.** It is dominated by
  the third harmonic at −32.2 dBc, which is stable to 0.1 dB over 30-odd presses
  and rises monotonically with drive. That is a speaker, not noise.

**So the named cause of the 45 % is `ThdResult` itself**: it is the window's
total RMS minus a single-frequency quadrature fit over 4,096 samples, and over
this loop what the fit leaves behind is dominated by everything that is not a
steady 1 kHz sinusoid — room noise integrated over four times the capture's
length and the whole band, plus whatever the returned tone's amplitude and phase
do over 85 ms of air, speaker and PDM microphone. It is not repeatable (a 20 dB
spread within one minute, measured) and it does not track the thing it is
supposed to measure. The bandpass THD is repeatable to 0.1 dB and does.

*Caveat on `THD floor (inst)`, stated rather than buried:* it is derived from the
MEDIAN unclaimed bin, which is robust against spurs but understates the noise in
the harmonic bands when that noise is not flat (this room's is mostly
low-frequency). The claim that the reading is harmonic rests on h3's stability
and its monotonic rise with drive, not on this figure. It is reported because it
is what the ceiling's second term is built on.

### (b) The cold press reading LOW (−10 dB) — NOT REPRODUCIBLE, and not the code

Both arms run today, on the same unit, minutes apart:

| runner | condition | tone | verdict |
|---|---|---|---|
| S115 (`421ceec0…`) | cold, 78 s after `systemctl reboot`, then ×2 | −35.8 / −35.8 / −35.8 dBFS | PASS / PASS / PASS, THD 2.56 / 2.62 / 2.66 % |
| **rollback** `d24_selftest.py.bak-s115-pre` = S114's exact code, md5 `c16264a7f96b6fee50f4c9944e6057eb` | cold, 75 s after `systemctl reboot` | **−35.7 dBFS** | **PASS**, THD+N −17.1 dB = 13.9 % |
| rollback, same md5 | warm | −35.8 dBFS | PASS, THD+N −20.8 dB = 9.1 % |

S114's cold LOW (−44.7 to −45.4 dBFS) does not reproduce, on either copy of the
runner. It was therefore a property of the unit's state in that window, not of
the code — which S114 had already established for the CLIP and which now holds
for the LOW as well. The only measured anomaly in the unit's state in that window
is S3(c) below. What the evidence RULES OUT: a settle problem in the code path
(the S115 copy raises AN_EN and then does 4 s of other work before the first
window, and passes cold), and a `codec_init` ordering problem (unchanged, and
unconditional in both copies).

Worth noting for whoever meets it again: the rollback's warm and cold passes read
THD+N −20.8 and −17.1 dB against a `thdn_abs_db` ceiling of −16.7 dB. **The old
verdict was 0.4 dB inside its own limit on a healthy loop.** It did not need a
fault to fail; it needed a quiet minute.

### (c) The unit state that made AL1 unmeasurable: a MAIN bus pinned at +17 dBFS

Read at 12:41-12:47 BST, before anything in this session had written a cell
(HUB addendum 1 records the hub's own read at 12:41 independently):

| node / cell | reading | instrument |
|---|---|---|
| `MainL001Mtr001` (chip 2, addr 1829) | 7.09-7.99 linear = **+17.0 to +18.1 dBFS**, sustained over 7 s of single reads | the product's own meter cell |
| `_buf_C2_MIX_MAIN_L` | **+14.4 to +16.6 dBFS** RMS, peak +17.7 dBFS | coherent capture |
| `_buf_C2_RECV_MAIN_L` | +13.2 to +15.3 dBFS RMS, peak **+18.06 dBFS** = ±8.0 in Q4.28 = saturation, words like `0x7FFFFEE0` | coherent capture |
| `_buf_C2_GRP_COMP_01` | −11.3 to −13.0 dBFS | coherent capture |
| `_buf_C1_BUS_MAIN_L` (chip 1's own MAIN block) | **−117.8 dBFS** | coherent capture |
| every strip's `MainOn` | 0 (AL1's CLOSE list had run) | `s89_set.py` read |
| the 595 chain | SAFE (`01`×24, gain 0, phantom off, muted) | disk marker, and the write verified later in the session |

Chip 1 was sending silence and chip 2 was receiving saturation. **`dsp4_config.py`
on both chips did not clear it. A full `dsp4_boot.py` + config, twice, did** —
the same cells then read −106 to −109 dBFS. Controls taken after that boot, with
`Mon001Level001/002` written to 0 first so nothing was audible:

| condition | `_buf_C2_MIX_MAIN_L` |
|---|---|
| boot defaults (every strip ON MAIN at unity), rails DOWN, chain SAFE | −107.6 dBFS |
| same, rails UP | −106.7 dBFS |
| rails UP, chain at **micGainFull** (`FC`×24 — gain 63, phantom off, UNMUTED, what an H1S1 reflash leaves) | −74.0 dBFS |
| rails UP, micGainFull, **every strip closed off MAIN** | **exactly 0** (−300 dBFS, 0/1024 non-zero) |

So the +17 dBFS was not the routing, not the rails and not the preamp gain: it
was a **stale graph state on chip 2 that only a re-boot cleared**, and it was
present with `MainOn` at 0 on every strip, which is why closing strip 20 did
nothing. It is also what made AL1 unmeasurable rather than merely noisy — the
press at 12:47:42 UTC, with the route asserted into that bus, read
`base -15.9 tone -18.7 SNR -2.8 dB THD+N -0.4 dB 95.8%` → NO SOUND, where the
same lane minutes earlier with the route down read −56.9 dBFS. **A 41 dB rise
caused by asserting the route.** The microphone was hearing a clipped roar out of
the speaker, not the room.

🔴 **Finding for the hub, outside this dispatch's fix:** the chip-1→chip-2 MAIN
receive can end up pinned at Q4.28 saturation while chip 1 sends silence, it
survives a `dsp4_config.py` commit, and nothing in the self-test detects it. It
was not reproducible on demand this session, so no root cause is claimed. Two
consequences worth a dispatch: (i) any AL1 press taken in that state is fiction,
and (ii) with the monitor bus at its default the unit is loud in that state. S117
removes the speaker from the mixer buses, which removes (ii) but not (i).

---

## S4. The noise after the tone: the step named, and the fix

### What was wrong, in one line each

1. **AL1 never tore its route down.** `_al1_prereq` wrote
   `Chan020MainOn001=1`, `Chan020Mute001=0`, `Main001Level001=1.0` and
   `Mon001Level001/002=1.0`, and nothing anywhere put them back. Every press left
   them set, for as long as the unit stayed powered.
2. **The speaker amplifier is not on AN_EN.** TS482 (digital U32) runs from the
   **5 V on the digital board**, always on while the unit is up (PW 2026-09-26,
   recorded here as a fact and not re-derived from the netlist). So dropping the
   rails at handback did not silence anything; it only unpowered the analog front
   end feeding the bus.
3. **There is no silent resting value in the graph.** Measured straight after a
   `dsp4_boot.py` + `dsp4_config.py` on both chips, with nothing else written:
   `Mon001Level001 = 1.0`, `Mon001Level002 = 1.0`, `Main001Level001 = 1.0`, and
   `Chan001/002/012/020/024MainOn001 = 1` with `Chan001Level001 = 1.0`. `defs`
   declares `C2_MON` as `level_l_db=0.0;level_r_db=0.0` — unity. **The panel
   speaker is live from the moment the pair boots, before any test writes a
   cell.** Pressing DR1 or DR2 is enough to do it.
4. Which is why "strip 20 off MAIN" did not silence it and `Mon001Level=0` did
   (hub addendum 3, PW: "gone"): the source was upstream of the monitor node and
   had nothing to do with strip 20.

### The fix

* `al1_silence(r, why)` writes `Mon001Level001=0`, `Mon001Level002=0`,
  `Chan020MainOn001=0`, `Chan020Mute001=1` and checks the read-back
  `s89_set.py` prints for every cell as it writes it. Idempotent, once per run.
* It is called **as soon as the last measurement window is read** — everything
  after that point in `t_al1` is arithmetic on numbers already in hand — and
  again from `handback` for the paths that never reach it: a prerequisite
  blocker, and **any run that booted the pair even if AL1 never ran** (item 3
  above). The handback call asks `link_alive()` first, because `DR1` deliberately
  holds `!RST_D` low and leaves the pair in reset: no graph, no audio, nothing to
  silence, and saying "NOT SILENT" there would be alarming and wrong.
* `al1_rails_down(r)` drops AN_EN at the same point instead of at handback.
  `--al1-keep-rails` still overrides it; handback reports whichever happened.
* **Why zero and not the product's resting value:** there is no resting value in
  the graph that is silent (item 3). Zero is the state PW confirmed silent at the
  bench on 2026-09-26, and it is what a self-test hands back until S117 gives the
  speaker its own haptic node off the mixer buses entirely (PW ruling, addendum
  4). Per that ruling nothing else was invested in this route.
* `tools/pi/dsp4_loop_thd.sh` gets the same four-cell write at the end. It
  asserts the same route and had the same defect.

### Every writer of the speaker path, listed (addendum 2)

| writer | what it leaves | state after S115 |
|---|---|---|
| `d24_selftest.py` AL1 route write | strip 20 on MAIN, main + monitor at unity | **FIXED** — torn down and read back every press |
| `d24_selftest.py` any run that boots (`DR1`,`DR2`,`DY1-*`,`DC1/2-*`, or a `--only` set that needs the pair) | the image's own initialisers: every strip on MAIN at unity, monitor at unity | **FIXED** — handback silences it when the link answers, and says so when it does not |
| `tools/pi/dsp4_loop_thd.sh` | strip 20 on MAIN, `Main001Level001=1.0`, monitor left at its unity default | **FIXED** — same four-cell write at the end |
| `tools/pi/dsp4_family_verify.py:375` | writes `Mon001Level001` as a ramp probe (1.0 then 0.25) and leaves it where the probe finished | **NOT changed** — a contract verifier, not a factory runner, and singling this cell out of its probe table would change what it verifies. Listed so it is not a surprise; S117 takes the monitor off the mixer path anyway. |
| `d24_selftest.py` AS-DAC | reads `_tx_out_slot_C2_MON_OUT`, writes nothing | no change needed |

### Rails-up and speaker-live seconds, before and after

| | BEFORE (S114, `c16264a7…`) | AFTER (S115, `421ceec0…`) |
|---|---|---|
| speaker path live per press | from the route write until **the unit is powered off** — unbounded | **4.10-4.16 s** (six presses), route write → silence write |
| AN_EN high per press | whole press + handback, ~14 s, and unbounded for a run that boots without AL1 | **7.82-7.98 s** (six presses) |
| proof it is silent | none — nothing read the cells back | the four read-backs `s89_set.py` prints, checked against target, in the evidence of every press |

Both numbers are printed in every press's evidence, so they are checkable
without a stopwatch.

---

## S5. Timing, honestly

| press | S114 measured | S115 measured |
|---|---|---|
| repeat (warm, standing route intact) | 7.1-7.2 s | **9.0-9.1 s** (9 presses) |
| first press after a boot (full route write) | — | 17.8-19.1 s |
| cold, ≥75 s after a CM4 reboot | 7.1 s | 9.1 s |
| whole `--section C` | 34.3 s | 36.3 s |

**The dispatch asked for ~7 s and the repeat press is 9.0 s.** Stated plainly
rather than rounded. Where the 1.9 s went, and what was done about it:

* +1.4 s the silence write (four cells, two chips, `s89_set.py` reads each one
  back). This is the handback fix; it is not optional and it is not free.
* +1.4 s the ENABLE route write, which is now needed on EVERY press because the
  previous press deliberately zeroed those four cells. Before S115 a repeat press
  wrote nothing and only probed.
* +0.4 s two coherent captures at 0.19 s each.
* −1.0 s the 1 s sleep after raising AN_EN, removed: `codec_init` alone is 2.0 s
  and the route write follows it, so the rails have 4 s or more of settle before
  the first window by construction. The sleep comes back if anything ever moves
  the measurement closer to the raise.
* −0.2 s the second baseline's capture, dropped.

What was done to keep it from being worse: the route write is split into a
marker-gated **STANDING** group (the 31-strip CLOSE list, level, pan, the four
processors off, the main level — only ever moved by a boot's config commit) and
the four **ENABLE** cells. A repeat press writes 4 cells instead of 43. Measured:
the full write is 10.0 s, the ENABLE write 1.4 s. Without that split a press with
a silent handback would have cost 19 s, not 9.

The marker (`<stage>/.al1_route_standing`) is written only when the full write's
read-back verified every cell, and is removed by `boot_pair()` and by a
`stage_setup()` re-copy — the same shape as S114's SAFE-chain marker and for the
same reason.

### Repeatability (the dispatch's 0.5 dB bar)

Three warm presses under the final code and the final table:

| press | tone | THD |
|---|---|---|
| 1 | −35.8 dBFS | −31.9 dB = 2.55 % |
| 2 | −35.8 dBFS | −31.8 dB = 2.58 % |
| 3 | −35.8 dBFS | −31.7 dB = 2.60 % |

**Spread 0.2 dB.** Across every warm press this session (nine, two runner
versions, spanning a re-boot): THD −31.4 to −31.9 dB, spread 0.5 dB, at the bar.
Within a single minute it is 0.1-0.2 dB.

---

## S6. A stage-directory defect found and fixed on the way

S114 made `stage_setup()`'s copy conditional on the PAIR's md5 (its rank 1), and
the copies of the tools that exist only in this repo sat inside that branch. So a
repeat press — the normal case — skipped them too, and a new version of
`dsp4_s49_osc.py` could be deployed to `/home/app/selftest`, be correct there,
and never reach the directory the run actually calls it from. It bit immediately:
the first S115 press answered
`s: error: unrecognized arguments: --cap-node _buf_C1_XIN_MEMS --cap 1024` on all
three legs and scored `NO DATA no settled window for: base, tone, back`.

`stage_tools()` now md5-gates those tools **on themselves**, on both paths: one
`md5sum` over the stage copies, then a copy of only the ones that differ. A
repeat press with nothing changed pays one `md5sum` and prints
`tools: 7 repo-only tools already current in /home/app/s90 (md5)`.
`dsp4_bulk.py` and `dsp4_fft.py` join the list.

---

## S7. Deployment, and no regression

| file | md5 |
|---|---|
| `d24_selftest.py` (deployed = repo) | `421ceec0461d50c8373c1bfbf3efdeaa` |
| `d24_selftest.py.bak-s115-pre` (rollback, = pre-dispatch `main`) | `c16264a7f96b6fee50f4c9944e6057eb` |
| `dsp4_s49_osc.py` | `098f95ba0a9bd5899f26a9e10810a5cf` |
| `dsp4_bulk.py` | `6b236080707608435b3106bf674ebb56` |
| `dsp4_fft.py` | `41a6fc694b45c19d8bcb7949a7e70c22` |
| `dsp4_loop_thd.sh` | `69281877e58d2cf2cffaf082bdbc3ae8` |

`--keys` cross-check clean before and after deploy: *34 distinct items, all
present in the export; 27 row numbers in the table match their position.*

`--section C` after deploy: **AL1 PASS, AS-ADC PASS, AS-DSPA PASS, AS-DSPB PASS,
AS-CPLD / AS-DAC / AS-PWR NO DATA** — 7 PASS / 0 FAIL / 4 NO DATA, the same
shape S114 recorded. `--only DR1,DR2`: both PASS, and the handback line reads
*"the speaker path, torn down (a boot in this run left the monitor bus at the
graph default, which is unity; exit 0, read-back SILENT)"*.

### Unit as handed back

`AN_EN` (GPIO26) `op dl`; `CS_M` (GPIO27) `op dh` DRIVEN; CS1/CS2 (GPIO6/24)
`op dh`; 595 chain SAFE (`01`×24 `00`, verified 200/200 by the DR2 press's
handback); speaker path silent (`Mon001Level001/002 = 0`, `Chan020MainOn001 = 0`,
`Chan020Mute001 = 1`, read back); pair booted and configured twice and answering
MAGIC/BOOT_STAGE 7 on both chips; `d24-testui` active, `matrix-app` inactive;
`.al1_route_standing` present in `/home/app/s90`. The codec was never `--reset`.

### 🔴 Gap, stated not hidden

No touch-injection ("on the glass") proof this session, for the same reason S114
gave: the wizard's own invocation string
(`~/mx26 src/sw/app/Core/TestSkinStore.cs:1069-1074`) is byte-identical before
and after and every number above comes from running that exact string, and this
dispatch touched neither the app nor the touch-to-runner wiring. Row 56's tap
coordinates are still not recorded anywhere this session could re-derive without
risking a misdirected tap on a live display with no visual feedback. If the hub
wants the touch path re-verified, it needs eyes on the glass.

Also, the earlier logs from this session (the first calibration grid and the
12:47 roaring press) lived in `/tmp/logs` and were lost to the two reboots the
cold-press arms needed. Their output is transcribed above verbatim from the
session transcript; the two logs that survive are in `logs/`.
