provenance: AI-drafted 2026-09-20 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S81 — the two instruments built, and the converters found not to be broken

**Session 81, 2026-09-20, rev C unit + desk.** Hub dispatch `tasks.md`
2026-09-20 09:23Z, answering S80's six questions.

**The headline is not one of the six.** Gates 2 and 3 built the instruments
the dispatch authorised — an SPI read arm in H1S1 and a CDC_O frame witness
in the LOGIC — and both worked first time. What they then measured is that
**the D24's converters are not dark. The bitstream flashed on the bench is.**
`dsp4_logic.a1f6672af6c3`, the artifact every session since S37 has called
"shipping" and "the state the bench lives in", was built at commit `a4ee3d1f`
on 2026-08-21, which is an ancestor of `ded71079` — the S34 converter-clock
fix, 2026-09-11, whose own commit message says the pre-fix design leaves
"the converters and all three option slots … no bit clock and no frame sync
at all". On that bitstream all four codec return lanes read exact digital
zero. On a bitstream built from the current tree, with the same DSP pair, the
same firmware, the same symbol map and the same reads half an hour apart, all
four carry converter noise and respond to AN_EN. S34's commit says "NOT
MERGED, NOT FLASHED. PW decides; this is the change, built and simulated so
the decision is one word." The dark converters have been a pending decision,
not a fault, since S71.

| gate | outcome |
|---|---|
| 1 — the 595 SAFE image (Q4) | **done**, and it confirms S80-10 on the part: `before:` read `FC`×24. The EIN sanity check could **not** be taken — see §1.2 |
| 2 — the H1S1 codec read arm (Q5a) | **done. The codec answers.** 21 of 21 registers read back the init image; a write-then-read control tracks; and the dispatch's own `0xC1` is disproved on the part |
| 3 — the CDC_O clock witness (Q5b) | **done**, with an A-B-A control on the codec's power register, and it produced the headline above |
| 4 — the instruments (Q6 + S80-12) | **done.** `dsp4_inscan.py` rewritten with two-sided controls proven on the part; four tools added to the bench-lock deploy; seven drivers that took no bench lock at all now take one |
| 5 — the controls owed | **Q1(a) re-anchoring done.** The D16/D12 instance-skip control arm and D12's regime were **NOT run** — see §5.3 |
| 6 — report, findings, tasks, handback | **done.** Unit as found: shipping bitstream, pair booted and configured twice, SAFE image on the chain, AN_EN lo, CS_M `ip pu`, `matrix-app` 3 of 3 |

Standing items honoured: 983.04 MHz only; **the shipping triple
`0xCF45FF10` / `0xE2018264` / `0xC47C0F26` was not moved and no DSP image was
built or deployed this session** — every DSP read ran on the as-found
`/home/app/s78restore` pair (`84c79513…` / `bb2a7c6e…`).

---

## 1. Gate 1 — the 595 SAFE image

### 1.1 Written, verified, and it confirms S80-10 by measurement

S80-Q4 was asked rather than done because writing the chain drives CS_M,
which S80's dispatch had fenced. S81 lifted the fence for that write.

```
before: FC FC FC FC FC FC FC FC FC FC FC FC FC FC FC FC FC FC FC FC FC FC FC FC 00
pass2 : 01 01 01 01 01 01 01 01 01 01 01 01 01 01 01 01 01 01 01 01 01 01 01 01 00
VERIFIED 200/200
```

`0xFC` is `{gain 63, phantom off, mute off}` in the chain's byte law. Twenty-
four of them, identical, with a clean `0x00` terminator: that is not latched
SPI traffic, it is exactly the image `TestMicPres()` sends, and it is S80-10
turned from an inference off the H1S1 source into a reading off the part.
**Every mic preamp on this unit has been unmuted at maximum gain since S79's
`--reset`**, and any noise figure taken on this bench in that window was
taken at full gain.

### 1.2 The EIN check could not be taken, and the reason is gate 3's finding

The dispatch asked for one number on MIC 5 against S54's −127.2 dBu. MIC 5 is
a mic preamp into an AK5558, and the AK5558 lanes read **exact digital zero
with the rails up** (`_buf_C1_IN_01/02/09/17`, AN_EN high, §3.4). There is no
noise floor to measure because there is no conversion. Quoting a figure from
a lane at exact digital zero would be a silence row wearing a driven label,
which is the S28 error the hub has already ruled against once.

The EIN check is therefore **owed, not refused**, and it becomes available
the moment the converter clock question in §3.5 is settled.

### 1.3 Written LAST, and the chain was re-latched during the session

At handback, after the final DSP boot, the chain's pass-1 MISO read

```
before: 00 E0 FE 00 00 00 00 00 00 E0 EB 20 00 00 00 00 00 E0 FE 00 00 00 00 00 00
```

— byte for byte the pattern S70 found, three `0xFE` bytes decoding as
**unmuted, phantom ON, gain 63**. So the S48-7 mechanism is still live: this
session's DSP boots shifted their own SPI traffic through the chain, and a
CS_M edge latched it. S70-7's rule ("the chain is asserted after the last DSP
boot of a session, not before it") is not a precaution, it is load-bearing,
and this session is the second measurement of it.

The SAFE image went in after that, `VERIFIED 200/200`, and CS_M went back to
`ip pu`. `matrix-app` was restarted afterwards and the chain was **not**
re-written: with GPIO 27 an input with a pull-up there is no CS_M rising
edge, so traffic shifts through the chain and nothing latches.

---

## 2. Gate 2 — the codec read arm, and the codec answers

### 2.1 What was built

`CodecPoll()` in `~/build-h1s1/Core/Inc/matrix.cs` gains three sentinels in
the ADDRESS cell beside S69's existing `0xFF`:

| `Sys001Test001` | effect |
|---|---|
| `0xFE` | READ the register named by the data cell |
| `0xFB` | hand back that read's GUARD byte |
| `0xFD` | set the read command code from the data cell |

plus `SpiTxRx()`, a full-duplex twin of `SpiTx()`. It is a separate function
on purpose: `SpiTx` has three other callers — `StartAK4619()` twice and
`TestMicPres()` once — and the 595 mic-pre chain shares this SPI, so the
write path had to stay provably untouched.

**Verified in the disassembly, not from the source edit** (the 2026-08-21
rule):

| | before | after |
|---|---|---|
| `bl <SpiTx>` call sites | 4 | **4** (write path byte-identical) |
| `bl <SpiTxRx>` | 0 | **1** |
| `bl <DspTx>` | 0 | **0** |
| `bl <HAL_SPI_Transmit>` | 1 | **1** |
| `bl <HAL_SPI_TransmitReceive>` | 0 | **1** |
| `bl` in `TimeSplice` | none | **none** |
| functions added | — | `SpiTxRx`, `HAL_SPI_TransmitReceive` |
| functions removed | — | none |
| function bodies changed | — | `CodecPoll` only (`SpiTx`, `StartAK4619`, `TestMicPres`, `MainLoop`, `MainInit`, `Poll`, `Eol` all mnemonic-identical) |
| text / data / bss | 33600 / 657 / 1940 | 35760 / 661 / 1944 |

The +2160 bytes of text are almost entirely `HAL_SPI_TransmitReceive` being
linked in for the first time. The operand decode confirms the addressing
rather than assuming it: matrix base offsets 19, 14, 18 are
`pSys001Test002[RXF]`, `pSys001Test001[RXD]`, `pSys001Test002[RXD]`, and the
reply stores land on offsets 12/13 = `pSys001Test001[TXD]`/`[TXF]`;
`r1 = 0x8000` is `CS_C_Pin`, `r0` is `GPIOA`.

The desk build reproduces the pre-change image byte for byte first
(`H1S1.elf` md5 `e1fe7fac…`, text 33600 — exactly S69's figure), so the tree
that was edited is provably the tree that is flashed.

### 2.2 The first build FREE-RAN on the part, and that is S81-4

The first S81 firmware answered on **both** cells — the value on
`Sys001Test002` and the guard on `Sys001Test001`. `Sys001Test002`'s RXF is
what triggers the arm, and the matrix bus is multi-drop: H1S1 hears its own
replies. So each reply re-armed the arm. Caught on the raw bus:

```
imjo37\nimjo\nimjo37\nimjo\nimjo37\n:\nimjo\nimjo37\n…
```

Register 00H answers `0x37`; the echo made the arm read register `0x37`,
which answers `0x00`; the echo of that made it read `0x00` again — a
self-sustaining ping-pong putting unasked SPI bursts on the copper the CM4
boots the SHARCs over, which is precisely the hazard the 2026-08-21 change
removed H1S1's periodic writes for. It terminated only by accident: the
echoed guard eventually poisoned the address cell into the write branch,
which transmits nothing. Bounded damage — the spurious writes went to
register `0x43`, which is not an AK4619 register — and the image was re-
inited and re-read afterwards.

The fix is structural rather than careful: **nothing this firmware transmits
may land on the trigger cell.** Every reply now goes on the ADDRESS cell,
where an echo changes a sentinel the host rewrites before every request and
triggers nothing, and the guard is FETCHED (`0xFB`) instead of pushed. The
second build does not free-run.

### 2.3 The dispatch's `0xC1` is wrong, and the part says so

S80-Q5 proposed command `0xC1`. S69's own source comment records the
datasheet pairing (9.12 Table 27 / 9.13): the command code's MSB is the R/W
flag and the low seven bits are the access area, so the write code `0xC3` has
read code `0x43` — same seven low bits, MSB cleared. `0xC1` fits that rule in
neither direction: its MSB is still the WRITE flag.

Rather than pick by reading, the command byte was made a firmware VARIABLE
settable from the bus (`--read-cmd`), and the part was asked:

| command | 01H | 05H | guard |
|---|---|---|---|
| `0x43` | `0xAC` | `0xBB` | `0x43` |
| `0xC1` | **`0x01`** | **`0x05`** | `0xC1` |

With `0xC1` the part hands back **the register number** — the master's own
address byte clocked straight through, because with the write flag set the
AK4619 is not reading anything. Had S81 implemented `0xC1` as dispatched, a
read of 00H would have returned `0x00` and the session would have concluded
"the codec does not answer on SPI", which is the exact opposite of the truth.

### 2.4 The answer: THE CODEC IS ALIVE

All 21 registers `StartAK4619()` writes, read back off the part:

```
37 AC 10 00 BB BB 30 30 30 30 00 00 00 00 18 18 18 18 04 05 0A
```

against the init image in `matrix.cs`:

```
37 AC 10 00 BB BB 30 30 30 30 00 00 00 00 18 18 18 18 04 05 0A
```

**21 of 21 exact.** Three controls behind it:

1. **Registers `StartAK4619()` does NOT write** — 15H, 16H, 1FH, 7FH — all
   read `0x00`. The part does not invent data.
2. **Write-then-read.** `05H := 0x35` reads back `0x35`; `05H := 0xBB` reads
   back `0xBB`. The readback tracks a write made seconds earlier, which
   disposes of any stale-buffer explanation.
3. **The echo signature is defined and absent.** If MISO were carrying the
   master's own MOSI (the U2-buffer fault) the data byte would be the
   register NUMBER. It is not, for the nine registers of the image whose
   contents differ from their address — 01H returning `0xAC` and 14H
   returning `0x0A` are echoes of nothing.

Decoded, 00H = `0x37` is `PMAD2=1 PMAD1=1 PMDA2=1 PMDA1=1 RSTN=1` — the codec
reports itself powered and out of reset — and 01H = `0xAC` is TDM=1, DCF=2,
TDM256 I2S, 32-bit slots. **Per the dispatch's own rule: the codec answers,
so it is alive and the fault is its clock/frame or the analog rails to it.**
Gate 3 then settled which.

---

## 3. Gate 3 — the CDC_O witness, and what it found

### 3.1 Why it rides the knock and not a TEST pin

The dispatch offered "a TEST pin or a word on a DSPA lane". The TEST pins
land on a DNP header (`J15`) and need a probe, which is the thing being
retired. But this CPLD already has a no-hands readback channel nobody had
reused: the design-ID knock on the CM4's PCM link (S5-9). The witness is a
**second knock word pair** on the same mechanism — `{L = 0xCD0432B4,
R = 0x32FBCD4B}`, R the exact inverse of L — answering for 128 frames with

```
L = {7'b0, cdc_ones_last[8:0], 7'b0, cdc_ones_max[8:0]}
R = {0xCD04, cdc_toggles_last[8:0], frame_counter[15:9]}
```

It moves no shipping lane, costs 2.7 ms of the CM4's own return stream on a
false trigger, and — like the ID knock, and for the same reason — is built in
**every** configuration, so whatever is flashed can answer the question.

### 3.2 Three numbers, because one bit fuses the cases

`ones` = bit periods in the frame with `cdc_o` high, out of 256; `toggles` =
transitions; `max` = high-water mark of `ones` since power-up.

| | | |
|---|---|---|
| ones 0, toggles 0 | exact digital zero | |
| ones 256, toggles 0 | stuck HIGH | a different fault, not silence |
| ones > 0, toggles > 0 | carrying data | |

`max` catches a burst between two knocks that a quiet frame would average
away. The free-running frame counter is **the instrument's own negative
control**: it advances every 10.7 ms, so two knocks a quarter-second apart
must differ, and `dsp4_cdc_witness.py` refuses to report its zeros as a
measurement if they do not. That guard is S80-19's lesson written into the
tool that could most easily repeat it.

### 3.3 The A-B-A on the codec's own power register

On `dsp4_logic.7a6a4529f29c`, rails down:

| step | ones (median [min..max]) | toggles | verdict |
|---|---|---|---|
| A — codec powered (00H = `0x37`) | 48 [9..86] | 24 [10..36] | carrying data |
| B — **codec powered DOWN** (00H := `0x00`) | **0 [0..0]** | **0 [0..0]** | exact digital zero |
| C — powered back up (00H := `0x37`) | 48 [12..86] | 24 [12..36] | carrying data |

Through B the witness's own frame counter kept moving (99 → 38), so the zero
is the lane and not the instrument. **`cdc_o` activity switches off and on
with the codec's own power register**, which rules out a floating input pin
and proves the data is the codec's. A codec can only emit a framed TDM stream
if BICK and LRCK are arriving, so **the codec is clocked** — and that is the
half of the question the CPLD genuinely cannot answer by looking at its own
outputs.

Rails up (AN_EN raised once under this dispatch's authority, `op dh`, read,
`op dl`, verified `lo` after): ones 47–48, toggles 24 — the activity is there
either way, and the DSP-side amplitude rises with the rails (§3.4), which is
S70's rails witness seen from the other end.

### 3.4 And then the DSP was asked, on both bitstreams

Same pair, same firmware, same symbol map, same `dsp4_scope.py` reads, the
two runs half an hour apart with only the LOGIC bitstream changed:

| buffer | `a1f6672af6c3` (bench "shipping", 2026-08-21) | `7a6a4529f29c` (current tree) |
|---|---|---|
| `_buf_C1_XIN_CODEC_01` | `00000000` ×8 | `ffffbec0 ffff6d60 fffecfc0 ffff9ba0 …` |
| `_buf_C1_XIN_CODEC_02` | `00000000` ×8 | `ffff75e0 00002740 00005660 00001220 …` |
| `_buf_C1_XIN_CODEC_03` | `00000000` ×8 | `00000dc0 fffff440 00001080 fffffaa0 …` |
| `_buf_C1_XIN_CODEC_04` | `00000000` ×8 | `00004d20 000041c0 ffffc1c0 fffff780 …` |
| `_buf_C1_IN_01` (AK5558) | `00000000` ×8 | `00000000` ×8, **rails up as well** |
| `_buf_C1_XIN_MEMS` | `ffffffff` ×8 | `ffffffff` ×8 |

The codec-lane values are small signed Q4.28 numbers moving sample to sample
around zero — converter noise, which is exactly what a clocked converter with
nothing plugged in produces. With AN_EN high the excursions grow
(`ffff2100 ffff3860 00011ea0 …`), the same rails sensitivity S70 measured as
a floor rising from −83 to −69 dBFS.

Confirmed a second time by the rewritten `dsp4_inscan.py`, an independent
instrument with its own controls (§4.1): `MOVING 0 / STATIC 47` on the
shipping bitstream, `MOVING 4 / STATIC 43` on the current one — the four
moving lanes being exactly the four codec returns.

### 3.5 The mechanism, confirmed in git

```
a4ee3d1f  2026-08-21  CPLD: dsp_clk = sysclk/2 …      <- added a1f6672af6c3
ded71079  2026-09-11  S34 OPTION BRANCH: drive the converter/option-slot clock pair (C1/L0)
git merge-base --is-ancestor a4ee3d1f ded71079  ->  YES
```

`ded71079`'s own message: U3 pins 142/141 were in the port list as
`ic_strap[1]` / `il_strap[0]`, read off the rev C sheet's IC/IL labels; the
netlist says they are board nets C1 and L0, each fanning out through five 33R
taps to the ADC/DAC FPC and to BCK_1-4 / FS_1-4, and **U3.142 and U3.141 are
the only active device pins on those nets**. As inputs, nothing drives the
converter bit clock or frame sync at all. The RTL comment says so in
capitals: *"THESE WERE INPUTS, AND THAT IS WHY NO CONVERTER CAN WORK."*

And: *"NOT MERGED, NOT FLASHED. PW decides; this is the change, built and
simulated so the decision is one word."* The fix has been built, simulated
and sitting unflashed since 2026-09-11, while the bench has gone on calling
the pre-fix artifact "shipping".

**One honest caveat.** The A/B has two variables, not one: the two bitstreams
also carry different slot-map generations (`efd8d555…` against `c4a3ca82…`).
The converter clock is the operative one and the witness is what separates
them — a slot-map change cannot make a codec start transmitting, and `cdc_o`
carries framed data on the post-fix bitstream that stops dead when the codec
is powered down. Whether `cdc_o` was also dead on the pre-fix bitstream is a
PREDICTION from the design, not a measurement: `a1f6672af6c3` predates the
witness and cannot answer.

### 3.6 What is NOT explained: the AK5558 lanes

`_buf_C1_IN_01/02/09/17` read exact digital zero **on the post-fix bitstream,
with the rails up**. The ADCs and the codec are fed by the same conv_bck /
conv_fs pair, so the clock fix alone does not account for them. Nothing in
this tree configures the AK5558s over SPI — H1S1's `StartAK4619()` writes the
AK4619 only, and CS_C is the converter chip select — so "the AD converters
have never been given their register image" is the first candidate and is a
different question from the one this session answered. `_buf_C1_XIN_MEMS`
stuck at `0xFFFFFFFF` (S79) is unchanged by any of this and remains its own
item.

---

## 4. Gate 4 — the instruments

### 4.1 `dsp4_inscan.py` rewritten, with both controls proven on the part

The old tool peeked `_rx_slot_C<chip>_IN_NN`. Those symbols still exist —
thirty-two of them on this image — but nothing writes them under
`DSP4_BLOCK_KERNELS`, so it printed `STATIC 1 distinct in 8 reads` twenty-
four times and a tidy summary, on every build that ships, whatever the lanes
were doing. The rewrite reads the block symbols (`_buf_C<chip>_IN_*`,
`_buf_C<chip>_XIN_*`), refuses to run at all if it cannot find them, and
gates every per-lane verdict behind two controls:

* **MUST-MOVE** — `FRAME_COUNT` (0xE004), incremented by the block ISR. If it
  is frozen the sample loop is not turning, every lane would read STATIC for
  a reason that has nothing to do with the lanes, and **no verdict is
  printed**.
* **MUST-NOT-MOVE** — `_rx_slot_C<chip>_IN_01`, through the same peek path:
  the very symbol that voided the old tool must read constant. If a symbol
  nothing writes comes back varying, the peek path is returning garbage and
  MOVING cannot be trusted either.

Both fired correctly on the part (`FRAME_COUNT 569171 -> 578396 advancing`;
`_rx_slot_C1_IN_01 constant at 0x00000000`), and the dispatch's required
two-sided control came out of the same A/B as §3.4 — **a lane known dead
reads STATIC and a lane known live reads MOVING, same tool, same image, same
symbols, opposite answers on the two bitstreams.**

Two smaller repairs went in with it. `0xFFFFFFFF` is both the link's "I don't
know" and a genuinely stuck lane; the old peek discarded it, which is why
`_buf_C1_XIN_MEMS` came back UNREADABLE from a link that was answering
perfectly — it is now resolved by the MAGIC brackets and reports STATIC at
`0xFFFFFFFF`, which is the truth. And the peek interval is 13.7 ms rather
than a round number, because S80's 20 ms pass was exactly 60 blocks and
aliased `CODEC_04` into a false STATIC.

### 4.2 The bench-lock manifest — S80-12's whole class

Four tools that live recipes invoke on the card, and that nothing in the repo
deployed, now travel with the lock. Card-side evidence, not suspicion:

| tool | on the card | why it matters |
|---|---|---|
| `dsp4_cclk.py` | **absent** | the MAGIC-bracketed clock read the recipe names as the safe replacement for `dsp4_diag.py --rate` (unguarded; measured −10509.64 MHz on a starved chip) |
| `dsp4_blk30.py` | **absent** | the block bar; its own contract assumes a deploy discipline that did not exist for itself |
| `dsp4_inscan.py` | **absent** | rewritten this session — a rewrite nothing deploys would never reach the card |
| `dsp4_logic_id.py` | **stale** `2b379c11…` 2026-09-09 vs repo `280f7ab4…` | the only tool that can say which bitstream is on the part. A live instance of exactly S80-12 |

**Seven drivers took no bench lock at all** — `bisect.sh`, `callcal.sh`,
`ctlgate.sh`, `dcapar.sh`, `mtrverify.sh`, `sigstrips.sh`, `strips.sh` — so
they got neither the exclusive card lock (the session-10 contention defect the
lock exists to prevent) nor the link-tool refresh, while their own `_run.sh`
called straight into `dsp4_config.py` / `dsp4_diag.py` / `dsp4_scope.py`. All
seven now `source ./bench_lock.sh; bench_lock_acquire "$0"` in the pattern
`numverify.sh` already used. `sigstrips.sh` additionally staged four tools
into its arm directory but not `dsp4_dyn_witness.py`, which
`sigstrips_run.sh:56` invokes and whose output is the verdict the arm is
scored on; it is staged now.

`check_bench_pins.sh` still exits 0 and `bash -n` passes on all eight files.

### 4.3 Two more of the same class, reported not fixed

* **`profile.sh` drives a file that does not exist here.** Lines 46/49 scp and
  ssh-invoke `profile_run.sh`, which has no history under that path in this
  repo at all; an orphan copy dated 2026-08-23 is still sitting on the card,
  so `profile.sh` has been running an un-diffable hand-copy. Either resurrect
  the script into the tree or retire `profile.sh`.
* **`chain_run.sh` would read a missing `chain.py` as a clean run.** Its guard
  block checks only `dsp4_checkchip.py`, and a missing `chain.py` prints
  `python3: can't open file …` to stderr, which matches none of the retry
  patterns at lines 51-53 — so the loop falls through, echoes the OS error as
  if it were the strip's report, and exits 0. **Latent, not live**: the card
  happens to hold a copy matching the repo (`a0815288…`) in the directory the
  script `cd`s to. It is one deleted file away from a false PASS.

---

## 5. Gate 5 — the controls owed

### 5.1 Q1(a): `product_fit.py` re-anchored

Executed as ruled. Rows A and B are re-anchored on S80's measured silent rows
across all four products; row C fits D16/D24/D32 only; D12's C is produced by
extrapolating that fit and is **labelled** `EXTRAPOLATED`, not invented from
D12's unproven driven reading. Row D is untouched and still carries its S27 /
2026-09-10 anchor, because S80 took no D row. Every construction and anchor
row in `fit-table.csv` now names its session and date in the `source` column.

| row | product | old (S27) built | S80 measured | new built | residual |
|---|---|---|---|---|---|
| A | D24 | 50.72 / 63.02 | 56.04 / 88.33 | 56.15 / 88.29 | −0.11 / +0.04 |
| A | D32 | 65.38 / 76.09 | 72.05 / 105.62 | 71.98 / 105.60 | +0.07 / +0.02 |
| B | D24 | 59.97 / 84.64 | 80.71 / 98.28 | 81.19 / 97.90 | −0.48 / +0.38 |
| B | D32 | 79.07 / 100.88 | 106.70 / 118.90 | 106.39 / 119.21 | +0.31 / −0.31 |
| C | D24 | 59.82 / 84.37 | 123.57 / 127.50 | 124.16 / 126.44 | −0.59 / +1.06 |
| C | D32 | 79.16 / 100.81 | 164.32 / 151.57 | 164.03 / 151.92 | +0.29 / −0.35 |
| C | D16 | (no anchor) | 84.59 / 113.00 | 84.30 / 113.70 | +0.30 / −0.70 |
| C | D12 | (no row) | *(unproven)* | 64.36 / 100.96 **EXTRAPOLATED** | — |

**Sanity check passed**: the pre-fix deltas reproduce S80's stated figures —
D24 C chip 2 **+43.13**, D32 C chip 1 **+85.16** — so the re-anchoring is
against the same arithmetic S80 reported, not a different one.

The FX-engine correction term is retired rather than carried: it required
mixing a new S80 C row with the stale S27 D row from a different session and
a different bitstream. It is also no longer needed — every re-anchored row now
spans real FX-engine counts (D12/D16 = 4, D24/D32 = 6) on measured data.

**The two rows marked *(ANCHOR — this is a control)* now pass by
construction**, and that is said in `score_measured`'s own output rather than
left for a reader to notice: a control that passes because the fit was built
on the same data is weaker evidence than one that passes independently.

### 5.2 Nothing was re-argued on Q2/Q3

Per the dispatch, the driven row stays the bar and the pairing configuration
is the route to it. No new case is made here.

### 5.3 🔴 NOT RUN: the D16/D12 instance-skip control and D12's regime

S79-Q3's product-driven instance skip with its control arm, and D12's regime
(22 of 24 chip-2 envelopes), were **not run**. They are bench capacity arms —
S80 spent most of a session on eight of them — and this session's bench time
went to gates 1-4, of which gate 3 turned into the converter finding and the
A/B that confirms it. Reporting a capacity row taken in the time that was
left would have been a worse outcome than reporting none.

They are unblocked and fully specified: the recipe is one line per arm
(`ARM=… PRODUCT=… ./capacity.sh --driven` on `loadlogic.sh driveall`), the
instrument is fixed, and the bench-lock now deploys the tools those arms cite
(§4.2), which it did not when S80 ran them.

---

## 6. The unit, as it was left

1. **LOGIC**: `dsp4_logic.a1f6672af6c3` — the shipping bitstream — restored,
   FLASH-OK on attempt 1, IDCODE `0x020a30dd` read both sides. Three flashes
   this session, all first-attempt: witness → shipping → witness → shipping.
2. **DSP pair**: the as-found `84c79513…` / `bb2a7c6e…` from
   `/home/app/s78restore`, booted and configured for D24 **twice**. Chip 1
   `MAGIC=0xD5B40001 CHIP_ID=1 BOOT_STAGE=7 ERR_COUNT=0 RESP_DROP=0`; chip 2
   `CHIP_ID 2 BOOT_STAGE 7 FRAME_COUNT 30370 SPORT0_ERR_A 0x00000000`.
   **No DSP image was built or deployed** and the shipping triple was not
   moved.
3. **H1S1**: reflashed, and this is a real change to the unit —
   `H1S1-s81b.shex`, 2279 records / 36,421 B, md5 `5dc7acde…`. The previous
   pack is kept as `/home/app/fwbuild/H1S1-pre-s81-2026-09-20.shex` (md5
   `2b377d15…`, which is S69's, confirming what was on the part) and as
   `/home/app/firmware/H1S1.shex.bak-2026-09-20-pre-s81`. No MH1 SWD reset
   was needed — both flashes took `OK: H1S1` first try.
4. **`GPIO 26` (AN_EN)**: raised once under this dispatch's authority for
   gate 3, and `op dl | lo` at handback, **read back, not assumed**.
5. **`GPIO 27` (CS_M)**: `ip pu | hi`. Driven only for the two authorised
   chain writes and restored immediately after each.
6. **595 chain**: SAFE image `0x01`×24 + `0x00`, **VERIFIED 200/200**,
   written after the final DSP boot per S70-7 (§1.3).
7. **Codec register image**: as `StartAK4619()` writes it — re-inited and
   then read back in full (§2.4) rather than assumed.
8. **`/home/app/dspboot`**: the link tools and the two new readers were
   refreshed there; `ldr/manifest.txt` untouched.
9. **`matrix-app`** active, **3 of 3 MCUs verified** on the second restart
   (the first verified 2 of 3 — the known race, recorded rather than
   smoothed).
10. **Dropbox mirror** `_mx/MW/D24/FW/H1S1/Core/Inc/matrix.cs` updated and
    now byte-identical to `~/build-h1s1` (md5 `f2fceaeb…`), with the prior
    copy kept beside it. **It had never received S69's hunks** — it was still
    the 2026-08-21 file, so the canonical copy has been four weeks behind the
    flashed firmware (S81-9).

**No contract note is due** and the absence is deliberate: `defs.lock` and the
submodule did not move, `check-contract-drift.sh` completes with no matrix or
address change, and nothing in the contract regeneration chain references
`product_fit.py` or `fit-table.csv`.

**A new bitstream exists but is not proposed here.**
`dsp4_logic.7a6a4529f29c` is committed with its manifest, is marked
`SHIPPING: yes` by build.sh's own rule (no non-shipping switch set), passes
the sim gate at 67.25 MHz Fmax, and is byte-identical across two rebuilds.
Whether it becomes the shipping bitstream is the S34 decision PW has had
since 2026-09-11, not a spoke call — see the question below.

---

## 7. 🔴 For the hub

**S81-Q1 — THE S34 CONVERTER-CLOCK FIX IS ONE WORD FROM PW AND THE BENCH HAS
BEEN CHASING ITS ABSENCE FOR TEN SESSIONS.** §3.4, §3.5. The converters are
not broken; the flashed bitstream does not clock them. `ded71079` says "NOT
MERGED, NOT FLASHED. PW decides", and it has been the pending decision since
2026-09-11 while S71 through S80 diagnosed a hardware fault. **The question is
PW's and it is the same one word.** What S81 adds is that the change is now
measured on the part rather than simulated: with it, all four codec return
lanes carry converter noise and `cdc_o` stops and starts with the codec's own
power register; without it, exact digital zero. If the answer is yes, the
follow-on work is a proper shipping bitstream (this tree's, whatever its hash
is by then), a re-take of every "dark converter" observation since S71, and
the EIN row §1.2 owes.

**S81-Q2 — "SHIPPING" HAS MEANT TWO DIFFERENT THINGS AND ONE OF THEM CANNOT
IDENTIFY ITSELF.** `loadlogic.sh` calls `a1f6672af6c3` "THE STATE THE BENCH
LIVES IN" while grouping `maincap`/`pisel`/`driveall` as "main +
s34-converter-clock + s36-xlogic-park". So every driven capacity row since S28
was taken on a bitstream **with** the converter clock, and every converter
observation was taken on one **without** it, and nothing in the naming says
so. Worse, `a1f6672af6c3` predates the design-ID stamp, so it is the one
bitstream on the shelf that answers nothing when asked what it is — its
identity rests on a flash log. Should `loadlogic.sh`'s `shipping` label move
to a post-S34 artifact, and should a bitstream that cannot identify itself be
allowed on the bench at all?

**S81-Q3 — THE AK5558s ARE STILL DARK AND MAY NEVER HAVE BEEN CONFIGURED.**
§3.6. With the converter clock present and the rails up, `_buf_C1_IN_*` still
reads exact digital zero. Nothing in this tree writes an AK5558 register
image: `StartAK4619()` writes the AK4619 alone, and the housekeeping SPI's
`CS_C` is the CONVERTER chip select. Is there an ADC init image anywhere — in
the app, in H1S1, in an MCU this repo does not build — or has nothing ever
configured them? This is one grep in mx26 and a hardware question this spoke
cannot answer.

**S81-Q4 — S69's HUNKS NEVER REACHED THE CANONICAL COPY, AND NOBODY NOTICED
FOR FOUR WEEKS.** §6.10. S69's dispatch said "the hub applies them to the
canonical Dropbox copy … and both copies must end identical"; the Dropbox file
was still the 2026-08-21 one today. S81 has now synced it, with S69's and
S81's changes together. The process question stands: the flashed firmware and
the canonical source diverged silently because nothing checks them. Should a
hash comparison of `~/build-h1s1` against the Dropbox copy join the bench
handback, the way `check-contract-drift.sh` guards the generated tree?

**S81-Q5 — `dsp4_cdc_witness.py` AND THE SECOND KNOCK ARE THIS BENCH'S FIRST
PERMANENT CPLD INSTRUMENT, AND THEY WANT A HOME IN THE CONTRACT.** The knock
is built into every configuration by design, so any future bitstream answers
"what is CDC_O doing" in one `aplay` + one `arecord`. That makes the knock
word pair and the reply layout a small interface, presently recorded only in
`build.sh`'s manifest emission and the tool's docstring. Does it belong in
`release-notes-contract-convention.md`'s scope, or is a CPLD diagnostic
register explicitly outside the matrix contract the way `DIAG_BUILD_CFG3` is?
