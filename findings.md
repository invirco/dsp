provenance: AI-drafted 2026-09-08 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# findings — dsp spoke

Numbered findings D1–D8x are recorded in `review-dsp-20260828.md` and in the
dispatch blocks of `tasks.md`. This file carries findings raised by dispatched
sessions after that review, newest first.

## THE POOL ALIGNMENT WAS NEVER REQUIRED, AND THE ONE PAN TABLE (2026-09-10, session 25)

Session: S24-5 settled with one build and the existing bars, R5 built and
witnessed, the D24 rows S24 said it had not taken.

### S25-1 — the block pool's 8-byte alignment was never a requirement, and the net answer is 4 bytes

**Severity: HIGH — it retires the only actionable caveat the DSP spoke gave
the net spoke. Status: measured on the part 2026-09-10, both chips, D32.**

S24 answered the MW-Net alignment question with **8 bytes, set by the SHARC
core's SIMD dual-data access**, and filed the pools' even placement as
"luck, not a declaration" — a latent build fragility to be settled with one
pad and one run of the bars. It is neither luck nor a requirement.

`DSP4_POOL_PAD` emits N words of `.var` immediately in front of
`_blk_pool`, from the generator, in the same section and object. A slot is
`base + n x BLOCK` and BLOCK is 16, so an odd N moves the whole pool:

| | control | pad arm |
|---|---|---|
| chip 1 `_blk_pool` / `_blk_pool1` | `0x90330` / `0x903C0` EVEN | `0x90331` / `0x903C1` **ODD** |
| chip 2 `_blk_pool` / `_blk_pool1` | `0x91E74` / `0x91F04` EVEN | `0x91E75` / `0x91F05` **ODD** |

**Every bar reproduces bit for bit.** `busgold`'s 256-word main-bus capture
is sha256 `4126c00730a31f5f` on both arms. `goldnode` reads word for word
the same on all four nodes — including the COMP arm's pre-existing 0.00518
dB LUT-vs-`fixed_ref` deviation, which is a property of
`shipping.config.s21` and not of the pad. `famverify`'s two 26-family
reports differ, after stripping run metadata, in exactly ONE field: METER's
free-running live `meter_word`. Golden 59/59 and `dsp_validate` OK on 698
nodes on both.

**And the mechanism agrees.** `src/lib/dyn_simd_fx.asm` says in its own
header what the SIMD access does — *"a data access reads two consecutive
words -- PEx the addressed one, PEy the next"* — the addressed one,
whatever its parity. The access class that WOULD require an even address is
the long word, and **`LW(` appears zero times in every `.asm` in the source
tree**; there is not one `.align` directive either.

The control arm matters and passed: `DSP4_POOL_PAD=0` rebuilt
`2fdd9f95` / `9222c2ee`, byte for byte the staged `s24_*` pair.

**Consequence for the net spoke:** the requirement is **4 bytes, set by the
DMA** (`MSIZE04` / `XMOD 4`). `MWN_AUDIO_PAYLOAD_OFF` stays at 40 either
way — but the 802.1Q caveat is GONE. An 8-byte requirement was flipped by a
single VLAN tag shifting the header 4 bytes; a 4-byte requirement survives
it. No receiver-side placement rule, no tagged-frame copy.
`docs/net-contract-answers.md` is corrected, with the old §2.2/§2.3 left in
place and marked rather than deleted — the net spoke was told 8 bytes on
2026-09-10 and the withdrawal has to be visible.

### S25-2 — `fix` on this core ROUNDS to nearest, and this tree has said it truncates

**Severity: MEDIUM, and wide — it is a shared belief, not one bug. Status:
measured on the part 2026-09-10.**

The pan probe's first run failed and the failure is the finding. Pan
indices 31, 63 and 94 were written to a node computing
`fix(pan * 126 + 0.5)`, and the part came back with **32, 64 and 94**.

The three float32 products are EXACTLY 31.0, 63.0 and 94.0, so the sums are
exactly 31.5, 63.5 and 94.5. Truncation gives 31/63/94; round-half-away
gives 32/64/95; **only round-half-to-even gives 32/64/94, and it gives all
three.** MODE1's truncate bit is set nowhere in the tree.

The `+0.5` was written on the belief that `fix` truncates — a belief stated
in this tree's own comments, in `dsp4_s24_probe.py::q28()` ("which
truncates toward zero on this core") and in the first draft of
`tools/dsp/pan_table.py`. It made every exact index land on a tie and round
up to the next one.

**S24's probe could not have caught this and does not claim to**: its five
levels were 1.0, 0.5, 0.25, 0.0 and a mute, every one an exact power of two
at Q4.28, so no rounding was ever exercised and its five-of-five result
stands. But the comment is wrong, and **anything in this tree that converts
a non-dyadic constant with `fix` is up to one LSB from what its comment
says it does.** Worth a sweep in a later session; nothing measured so far
depends on it, because the places that have been witnessed on the part were
witnessed against the part.

The fix is one instruction deleted. `pan_table.py` models `fix` the
measured way and gained a `Pan -> index` round-trip bar over all 127
indices that would have caught this on the desk.

### S25-3 — LCR needs no new bus, because the sub bus IS the centre bus

**Severity: MEDIUM — it turns R5 from a fabric change into a coefficient
change. Status: read off the graph and the master, witnessed on the part.**

The obvious objection to R5 is that a centre leg needs a centre bus, and
chip 1's fabric has none: Main L, Main R, Sub, 4 groups, 12 aux, 6 FX and
the matrix rows. The four "main outputs" are the CROSSOVER's four outputs,
not four buses. An LCR centre would then have meant a 33rd fabric row, an
inter-chip lane, a TDM slot out of the single-sourced slot map and a chip-2
chain — on the chip S24 measured at 100.72 % at worst use, and against
R6-R11's hold on fabric growth. That would have been a refusal.

**`Chan*CtrOn` is already dispatched to `_rtg_sub_on`, and the master's own
name for the cell is "Center/sub output assign on/off".** The sub bus has a
complete chain behind it — `C1_BUS_SUB` -> send -> `C2_RECV_SUB` -> fader
-> EQ -> comp -> limiter -> delay -> its own TDM output. R5's "`Chan*CtrOn`
still GATES the centre leg" is a description of a crosspoint that has been
in the graph since the graph existed.

So R5 costs no fabric row, no inter-chip lane and no TDM slot. Witnessed at
pan index 31 (**not** at centre, where the hard-LCR centre leg is unity and
the bar could not tell LCR from a plain sub send): `_rtg_subq` reads
`0x07DF7DF8` with LcrOn=1/CtrOn=1, `0x10000000` with LcrOn=0/CtrOn=1, and
exactly zero with CtrOn=0.

### S25-4 — R5-amended as written silences a centre-panned stereo channel

**Severity: MEDIUM — a definition defect, for PW. Status: arithmetic, and
the build works around it in the one way that is provably free.**

R5-amended says a non-LCR channel "uses the same table's L/R columns
(centre column ignored)". Under hard LCR the centre position is *centre bus
only*, so its L and R legs are BOTH ZERO: read literally, a stereo channel
panned to the middle disappears. The same is true of the constant-power
law, so it is not a quirk of one law.

What the table stores instead satisfies R5 literally and fixes it: the L/R
columns ARE what a non-LCR channel reads, and an LCR channel's legs are
`(L - C/2, C, R - C/2)` — the centre bus takes what the two sides carried
between them.

**For hard LCR that is an identity.** Folding hard LCR's centre back at
half gives `(1-p, p)` at every position, which is the linear law this graph
has always run; and in the integer form the table stores, the centre column
is exactly twice the smaller side, so `C >> 1` returns it and the recovered
legs are exact with NO rounding — near side `L - R`, far side exactly zero,
at all 127 positions.

**And a second thing R5 cannot have: three columns cannot hold both a
two-bus constant-power law and a three-bus one.** Found by trying —
defining law 1's L/R as `cos(p*pi/2) / sin(p*pi/2)` makes the recovered LCR
legs miss constant power by up to 0.238 in sum-of-squares. So law 1's
primary definition is its LCR legs (which is all R5 specifies) and its
stereo projection is the -6 dB fold, peaking **+0.9687 dB** above unity at
index 107 — inside Q4.28's headroom, nothing saturates, reported by
`pan_table.fold_peak_db()` rather than remembered. Under law 0 the peak is
+0.0000 dB.

**What a non-LCR channel should read under the constant-power law is PW's,
and it is carried, not guessed.**

### S25-5 — the talkback mics and the noise generator reach no bus at all

**Severity: MEDIUM — it re-attributes two unmapped families. Status: read
off `dsp.csv`, 2026-09-10.**

`Talk*Dest[2-3]` and `Noise*Dest[1-10]` were recorded as unmapped because
the SPI blocks are too small — "the TALKBACK node has four SPI words (On,
Gain, Hpf, Dest1) and the graph gives it no more". True, and the wrong
deficiency.

`C1_TALK_01`, `C1_TALK_02` and `C1_NOISE` all have an **EMPTY outputs
column**. The talkback node already declares `_talk_route_<nid>[3]` — the
words are there — and **nothing in the tree reads it beyond the SPI
dispatch of Dest1**. The mics are gained, high-passed and delivered
nowhere.

So `Talk001Dest001`, which DOES reach an address, is a cell that reaches a
WORD and not the arithmetic — S24-7's shape one family along, and a
famverify "contract 4/4, audio LIVE" does not see it, because the family's
own node does run.

Two more addresses would add two more such cells. What the family needs is
crosspoints out of each node into named buses, and **which** buses is the
master's "aux/main" to resolve. The unmapped reasons now say that.

## THE NET CONTRACT ANSWERED, AND THE USE-PROPORTIONAL COST IS THE BYPASS (2026-09-10, session 24)

Session: the three MW-Net answers the wire declaration needed, the cost S23
could not price, and the first half of completeness leg 2.

### S24-1 — the cost proportional to USE is a BUS losing its bypass, not a crosspoint doing a MAC, and it is 450x

**Severity: HIGH — it decides whether D32 fits. Status: measured on the
part 2026-09-10, two boots, D32.**

S23 built the block-level bypass (S23-5) and measured it as worth 9.89
points of chip 2 when it was introduced. This session measures the same
thing from the other side — by switching it off one desk operation at a
time — and the shape is not what the record assumed.

Every rung driven, plugin load, one boot, S23's candidate image, the only
difference between two rungs being how many crosspoints are live. `f:m` =
FX returns opened into EVERY aux bus : strips opened into EVERY matrix bus.

Both boots, chip 1 / chip 2 average % of budget, chip 2 overruns:

| rung | boot 1 | boot 2 | chip 2 overruns |
|---|---|---|--:|
| 0:0 — every crosspoint closed (**the control**) | 77.07 / **90.93** | 77.06 / **90.78** | 0 |
| 1:0 — ONE FX return into each of the 12 aux buses | 77.07 / **100.70** | 77.40 / **100.80** | **600** |
| 6:0 — all six into each of the 12 | 77.06 / **100.81** | 77.23 / **100.78** | **600** |
| 0:1 — one strip into each of the 2 matrix buses | 77.39 / 91.05 | 77.64 / 90.78 | 0 |
| 0:32 — all 32 strips into each of the 2 | 78.20 / 90.77 | 78.30 / 91.26 | 0 |
| 6:32 — **worst use** | **78.46 / 100.72** | **78.36 / 100.71** | **601** |

**The control is what makes it readable**: rung 0:0 reads 90.93 / 90.78 %
against S23's driven row of 90.95 % on the same image and instrument, so
the ladder is measuring the crosspoints and nothing else.

- **0:0 -> 1:0 is +9.77 and +10.02 points of chip 2** — twelve aux buses
  leaving the bypass, with ONE live send each.
- **1:0 -> 6:0 is +0.11 and −0.02** — five more live crosspoints on each of
  those twelve buses.

**A bus that stops being empty costs 0.81–0.84 points of chip 2. Opening
the other five sends on it costs NOTHING THIS INSTRUMENT CAN RESOLVE** —
the two boots disagree in sign and both figures are inside the ±0.3-point
boot-to-boot spread S20 measured. The first boot alone would have supported
"about 0.002 points a crosspoint"; the second says that number is noise,
and the honest statement is an upper bound, not a slope.

That inverts the natural reading of "cost proportional to use": it is
proportional to how many BUSES are used and, to the limit of this
instrument, independent of how much each is used.

The matrix is chip 1's and it is cheap: 0:0 -> 0:32 is **+1.13 and +1.24
points of chip 1** for 64 live crosspoints on two buses. Chip 2 does not
move with the matrix — its four readings scatter from −0.16 to +0.48 about
zero — which is what the graph predicts, the matrix output strips being a
fader and an output that do not care whether the bus carries signal. The
two effects are additive: 90.93 + 9.77 = 100.70 against a measured worst
use of 100.72.

### S24-2 — D32 chip 2 does not fit at worst use, and it stops fitting at ONE send per aux bus

**Severity: HIGH, product-visible. Status: measured, two boots.**

**100.72 % and 100.71 % with 600–601 of 90,049 blocks missed (0.67 %)** on
the two boots. It is not the six returns that break it: **rung 1:0 already
overruns** — one FX return sent to each of the twelve aux buses.

At 0.82 points a bus, chip 2's ~9.1 points of margin at rung 0:0 buy about
eleven of the twelve aux buses.

This is a capacity fact and not a defect: nothing in the graph is wrong,
and the fix — if PW wants all twelve aux buses usable at once — is a
cheaper aux sum, not a smaller feature set. It is stated here because
S23's fit table said "90.95 % with 9.05 % free" and that figure describes
a desk with no FX return sent anywhere.

### S24-7 — the S24 gate-3 probe returned INCONCLUSIVE, and the control is what says so

**Severity: LOW (instrument/procedure). Status: the feature is unwitnessed
on the part; the probe is written and staged.**

`dsp4_s24_probe.py` reads the main output strips' folded coefficient back
and checks it against `round(level * 2^28)`, then demands an exactly-zero
output block for mute = 1 and for level = 0.0. Its first run reported
`_out_coeff_C2_MAIN_OUT_01 = 0x00000000` at every level, which reads like a
broken feature.

**It was not the feature, and the control is what established that.** On
the same boot `_fdr_level_C2_MAIN_FDR` and `_fdr_level_C2_AUX_FDR_01` —
`.var = 1.0` words S23 measured working — ALSO read `0x00000000`, and so
did every other word the probe touched. A bar that reports the same failure
for the thing under test and for a known-good control is not measuring the
thing under test.

**The cause was the read window, and it is S22-4's shape one level along.**
DM symbols are read with `Scope.peek(Scope.addr(name))`; `Scope.rd()` reads
the SPI diagnostic/cell window. A DM word address (731019) handed to `rd()`
lands outside the dispatch table and **answers zero**, which is exactly
what a feature that does not work would answer. Both probes in this tree
that read DM words use `peek`; this one used `rd`.

Fixed, and the probe now takes its control FIRST and refuses a verdict when
the control reads zero — the same guard `dsp4_dsp_latency.py` was given
after S11-6. On the re-run the control reads `0x3F800000` and **all five
fold cases are exact** (see S24-8).

The lesson is the one S23 recorded about its own negative control, one gate
along: **the sentence "the word read zero" is produced by a real defect and
by a wrong instrument alike, and only a control that can fail separates
them.**

### S24-8 — the main output fold is exact on the part

**Severity: n/a (the gate 3 witness). Status: measured 2026-09-10 on the
S24 tap arm (`17cc5a0e` / `e94dc5a3`), D32.**

`Main{L}001Level/Mute` written through the contract, `_out_coeff_
C2_MAIN_OUT_01` read back off the part, against `round(level * 2^28)`
computed on the desk:

| level | mute | `_out_coeff` | want | |
|--:|--:|---|---|---|
| 1.0 | 0 | `0x10000000` | `0x10000000` | **OK — exactly 2^28, so the node takes the copy path** |
| 0.5 | 0 | `0x08000000` | `0x08000000` | OK |
| 0.25 | 0 | `0x04000000` | `0x04000000` | OK |
| 1.0 | **1** | `0x00000000` | `0x00000000` | **OK — mute folds to exactly zero, not small** |
| **0.0** | 0 | `0x00000000` | `0x00000000` | **OK — the independent control: the level alone, with the mute bit at 0** |

Five of five exact, with the probe's own control (`_fdr_level_
C2_MAIN_FDR` = `0x3F800000`) proving the graph was running.

**What this does and does not establish.** It establishes that the cell
reaches the arithmetic, that the fold is the arithmetic claimed, that unity
lands on exactly the value the bypass compares against, and that mute and
level zero each reach exactly zero independently. It does NOT establish the
audio: the probe's capture bars (an exactly-zero output block under mute,
and a peak passthrough at unity) returned `capture stalled at 0 of 1024
samples` on every attempt and **no audio claim is made from them**. The
injection point this probe passes (`_rx_ic_slot_C2_RECV_MAIN_L`) is not one
the chain's scope gate injects into; the S23 probe uses
`_rx_ic_slot_C2_RECV_FX_01`. That is one line to change and one boot to
re-run.

### S24-3 — a ramped send written to 0.0 does not verify inside the instrument's window, and the state is right anyway

**Severity: LOW (instrument). Status: reproduced on both boots.**

`dsp4_driven_setup.py --mode use` writes the send families to a named count
and verifies each write by reading it back. The FIRST rung after the load
config — the one that takes 64 `Chan*MatrixSend` cells from 1.0 down to
0.0 — reports **64 of 64 FAILED**, identically on both boots; every later
rung, where the cells are already at 0.0, reports 0 failed. So it is the
1.0 -> 0.0 transition that the readback cannot confirm, not the write.

**The measurement is unaffected and the reason is the design**: the on/off
bit is folded INTO the Q4.28 crosspoint coefficient at block rate (S23), so
`MatrixOn = 0` zeroes the coefficient whatever the send level holds — and
`MatrixOn` writes and verifies cleanly, 64 of 64, on every rung. Rung 0:0
reproducing S23's driven row to 0.02 points is the evidence that the rung
state was what it claimed.

Not root-caused: the profile is 24 frames / 8 ms and the verify window is
12 x 30 ms, so ramp duration does not explain it. Reading the word back
after a settled ramp is one bench command and it was not spent this
session.

### S24-4 — three HPF bands per main output strip were listed as "no node in the graph" when the graph already had the node and the words

**Severity: MEDIUM (contract completeness). Status: fixed, 15 cells.**

`Main{L,R,Ctr}[1-1]EqHpf[1-4]` is what the masters declare and
`dsp-unmapped.csv` carried bands 2-4 as `no-graph-node`, "the generator
gives a non-Main strip one HPF (band 1) and the masters give the output
strips four". The EQ expander already handled it — `if cat == 'Main': for b
in range(1, bands+1)` with the comment "Main output zones allow any band as
HPF" — and the four post-crossover output EQs do not carry cat `Main`. They
carry `MainL` / `MainR` / `MainCtr` / `MainSub`, because that is what the
output strips ARE (`_MAIN_OUT_STRIP`). So the test named the main BUS strip
and missed the main OUTPUT strips, and a product feature that was fully
built reported as unbuilt for as long as the table has existed.

The fix is one condition. It costs **no arithmetic and no address**: every
`EqHpf` cell aliases its band's own coefficient base exactly as band 1
always did. D32 +6 cells, D24 +9.

The general shape is worth keeping beside S23-4 (the family walk keyed on
`NodeType` could not give the matrix a family at all): **a completeness
list is only as good as the category test behind it, and both of this
week's blind spots were a name that matched a sibling rather than the
thing.**

### S24-5 — the block pool's 8-byte alignment is luck, not a declaration

**Severity: MEDIUM (latent build fragility). Status: identified, not
settled on the part.**

The block kernels open a `PEYEN` region and read the pool with
`dm(i0, 2)` — one access feeding both processing elements from two
consecutive words, which needs an even (8-byte-aligned) address. Nothing
declares that alignment. **The linker does not supply it either: of 5,452
DM symbols in the chip-1 map of the S23 pair, 2,204 sit at ODD word
addresses**, so a `.var` gets word alignment and no more. Both pools happen
to be even (`_blk_pool` 590640, `_blk_pool1` 590784) and every slot with
them, because `BLOCK` is 16.

If the part force-aligns, nothing is wrong and the alignment answer for
MW-Net is 4 rather than 8. If it does not, this build works by luck and one
word of DM moving in front of `_blk_pool` would break every SIMD kernel on
chip 1 in a way no bar names. **Settling it costs one build with a one-word
pad and one run of the existing audio bars**, and it is worth doing for the
build-fragility reason whether or not MW-Net ever terminates on a SHARC.

### S24-6 — 96 kHz is stopped by the PART before it is stopped by the cycle budget

**Severity: INFORMATIONAL (it confirms D6). Status: argued from the data
sheet and the RTL.**

The obvious objection to DSP4 at 96 kHz is cycles, and that objection is
real — CCLK is already at the part's ceiling (983.04 MHz, the KSWZ10-only
row) so utilisation doubles whatever the block size, and S23's worst driven
row becomes about 182 %. But it is the third reason, not the first.

**First**: the data sheet caps `fSPTCLKEXT` at 31.25 MHz when transmitting
data or frame sync. A TDM16 lane needs 24.576 MHz at 48 kHz and 49.152 MHz
at 96 kHz, and TDM16 is every line of the INTER-CHIP MIX FABRIC — not an
edge lane that could be re-cut.

**Second**: the CPLD cannot generate those clocks. `dsp4_clkgen.v` derives
every clock role from one 49.152 MHz XO on a 1024-sysclk frame; at 96 kHz
TDM8's BCK is sysclk/2 (producible) and TDM16's is the sysclk itself, which
this design cannot emit as a registered divided clock.

So D6's 32 ch / 48 kHz line is not a preference with a cycle argument
behind it — it is where two independent pieces of hardware run out, and a
"deliberate DSP4-at-96k exception" would need a different XO and a
different SPORT topology before it needed a faster core.

## COMPLETENESS LEG 1 FINISHED (2026-09-10, session 23)

Session: the matrix's three remaining witnesses, the FX returns given a bus
at all, and the compressor gain-reduction meter published.

### S23-5 — twelve aux summing nodes cost chip 2 13.59 points with every FX send OFF, and the fix is a block-level bypass that is bit-exact by construction

**Severity: HIGH — it is the difference between gate 3 fitting D32 and not.
Status: measured on the part 2026-09-10 and fixed the same session.**

Gate 3's twelve `C2_MIX_AUX_nn` nodes take the generic chip-2 block wrapper,
which stages every source through its scalar `_buf_` word on EVERY sample —
six instructions per source per sample — whatever the coefficients are. With
seven sources that is about 63 instructions a sample a node before the MACs,
and it is paid identically whether an FX return is sent to that aux or not.

**Measured, driven, on the shipping configuration:** D24 chip 2 at
**87.67 %** against S21's 74.08 % on the same instrument, the same clock and
the same plugin load — **+13.59 points, with every `Fx*AuxOn` at its
shipping default of 0.** On D32, where S21's chip 2 was already at 87.08 %,
the same addition would not have fitted at all.

**Thirteen points for a crosspoint nobody has switched on is the wrong
trade**, and the fix does not need the kernel restructured. Every switched
coefficient is folded at block rate with its on/off bit multiplied in, so
one OR over the fold answers "is any crosspoint live this block?" for free.
When the answer is no, and the node has exactly ONE plain source at a
coefficient of exactly 2^28, the whole sum is that source unchanged:

```
  mrf = x * 2**28  (exact)  ->  _mrf_rns28  ->  (x * 2**28 + 2**27) >> 28  =  x
```

so the bypass is a block copy and it is **identical, not close**. It is
emitted only where that argument holds — `n_plain == 1`, checked at generate
time, and the plain gain read back as exactly `1.0f` at run time — so the
main mixes, which have seventeen plain sources and no switched ones, get
neither the bypass nor the prep and their emitted text is byte-identical to
the pre-S23 generator.

**And the exactness was measured before the bypass existed**, which is what
makes it a fix rather than a hope: with the sends off,
`_buf_C2_MIX_AUX_01` reproduced `_buf_C2_RECV_AUX_01` in 32 of 32 words.

The cost of the bypass is one compare per switched send plus a block copy —
about 38 instructions a block against 1,008 — so **an aux bus nobody sends
an FX return to is very nearly free, and one that is used pays the full
sum on that bus alone.**

### S23-6 — `Fx<n>On = 0` now costs chip 2 3.98 points LESS than the bypass Type it used to be measured against

**Status: measured 2026-09-10.**

The FX ladder's `off` rung was kept by S21 purely as the WITNESS for S21-4
(`Fx<n>On` had no reader, so the rung ran the same algorithm as the rung
before it and the two rows read the same). With the reader in place it is a
real rung, and it is the first measurement of what parking is worth:

| D24 chip 2, driven, same boot | avg % |
|---|--:|
| Type 3 — Reverb | 87.50 |
| Type 4 — parked in the explicit bypass (S21's baseline) | 71.55 |
| **`Fx*On` = 0 — the whole node parked (S23)** | **67.57** |

**Parking beats bypassing by 3.98 points**, which is the FX_ENGINE node's
per-sample overhead outside its algorithm — the wrapper's staging, the mix
ramp, the dispatch and the dry/wet epilogue — now not paid at all. Against
the reverb it is 19.93 points. `cap_table.py`'s label for the rung is
corrected from "(INERT: no reader)".

### S23-4 — the family walk could not give the matrix a family, because its keys were the landed contract's NodeTypes

**Severity: MEDIUM, and it is a bar defect and not an audio one.
Status: fixed 2026-09-10.**

`dsp4_family_verify.py` chose which families to walk from
`Landed.families()`, which is `{NodeType: cell count}` over the addressed
cells. The matrix's cells are `Chan*MatrixSend/On` — cells of a **ROUTING**
— and `Matrix*Level/Mute` — cells of a **FADER_PAN**. Both of those
families existed and were passing before the matrix did.

**So a NodeType-keyed walk had no way to give the matrix a family however
hard it looked, and would have gone on reporting the graph complete with a
whole product feature un-witnessed.** The same is true of anything else
built out of existing node classes, which is most of what the completeness
list has left.

Fixed by making the default family list the UNION of the landed NodeTypes
and the harness's own table: an entry in `FAMILIES` is a claim that
something is answerable for, and it runs whether or not its name is a
NodeType. `contract_phase()` gained a `cells=` override so an entry whose
cells sit on a node other families already sweep can name the four words
that are new instead of re-writing sixty routing words to reach them, and a
named cell the landed contract does not carry is reported
`NOT_IN_CONTRACT` rather than skipped — a harness naming a cell that no
longer exists is a stale harness.

### S23-3 — inserting a node into the aux chain silently un-pairs twelve limiters and thirty-six biquad cascades, and the generator is what says so

**Severity: HIGH for any future node inserted into a chip-2 chain.
Status: found by the generator 2026-09-10 and designed around the same day.**

Gate 3's `C2_MIX_AUX_nn` reads the FX returns' blocks, so every return has
to publish before the first aux sum. `repair_process_order()` does that on
its own — and that is the trap. It is a minimal, stable repair: it moves each
violating producer to *immediately before its earliest consumer*, which
drops `C2_MIX_AUX_02..12` into the middle of the aux chain, one per
instance.

The chip-2 pair families require each family's nodes to be a CONTIGUOUS RUN
of the chain, and `c2_pair_groups()` refused the graph in as many words:

```
  chip 2 pair family AUX: its 84 nodes are not a contiguous run of the
  chain (60..154), so the pair order cannot be built by reordering that run
```

Left to the repair, the twelve aux limiters and the paired EQ/GEQ/AFB
cascades would have had to run scalar. **That is the D81 shape one level
along** — a graph change dropping a pair family the shipping image pairs
today — and the reason it was caught rather than shipped is that D81's fix
made the family structure a CHECKED claim instead of a pattern match.

Fixed by splicing the FX chain and all twelve sums in front of the aux chain
in the ROW order, which reorders rows and moves no address (an address is
allocated at the `add()` call, not at the row's position). The AUX family's
84 nodes are then untouched and no repair move is needed at all.

**The general lesson: on chip 2, WHERE a new node's row sits is part of the
design, not a detail the repair can be left to settle.**

### S23-2 — `Chan*CompMtr` needed an address AND a declared source, and only the address had been written down

**Severity: LOW. Status: closed 2026-09-10.**

S22 wrote down the cheap route for the GR meter as "bind it to the meter's
already-allocated base+3, NOT to DM offset +3". That was right and it was
half the problem. The other half is that **nothing named the compressor**.
A meter node's `inputs` is its audio tap (`C1_GAIN_nn`), and deriving "the
compressor of the strip this meter belongs to" by string surgery on the
meter's own id is the second address map this repo keeps deleting.

So the link is a param on the dsp.csv row — `comp_gr_src=C1_COMP_nn`,
written by `gen_dsp_csv.py` — and a `comp_gr` tap without one is a hard
error in `dsp_codegen.py` rather than a guess.

**And the S22 note's wording was itself half wrong in a way that mattered**:
base+3 is not "the meter's own state array". `_mtr_st_[4]` is at DM offset
+3; SPI offset +3 of the four-word meter block had no dispatch entry at all.
Confusing the two would have pushed `_mtr_st_` up by one word and made every
meter on both chips fold into the wrong four words, which is why
`_mtr_comp_gr()` declares the new word AFTER `_mtr_acc_` and says so at the
declaration.

### S23-1 — the FIRST bus capture on a boot carries a dynamics-history term of up to 1,412 LSB, and a comparison that straddles it is not a bit-exactness claim

**Severity: MEDIUM for every bar built on `dsp4_pairgraph.py`.
Status: measured 2026-09-10; the affected bars are named below.**

The matrix bus vector compares two buses captured on one boot. The first
attempt read: aux 1 vs matrix 1, **235 of 256 words differ, first at word
21, maxdiff 1,412** — 1.06e-5 relative, −99.5 dB. That is far too small to
be a mis-wired bus and far too large to be nothing.

**It is the instrument.** A capture is 256 samples from the arm, and the
strip's gate and compressor are wherever their envelopes happen to be when
the arm lands — which depends on how long ago the previous capture's step
injection stopped. Taking aux 1 TWICE on the same boot, first and last,
settles it: `aux1` vs `aux1b` reports the **identical** 235-of-256 /
first=21 / maxdiff=1412, and `aux1b`, `mtx1` and `mtx2` all carry
sha256 `b67e59ca785515bd`. Three captures of three different buses are byte
for byte identical; the odd one out is the first capture of the boot.

**What this does and does not touch.** `busgold.sh`, `ctlgate.sh`,
`bqgraph.sh` and `gainsimd.sh` take ONE capture per boot and compare it
against a stored golden or against another boot's single capture, so both
sides of every one of those comparisons is a first capture and the term
cancels. It bites any bar that compares captures taken at different
positions within one boot — which is what `mtxgold.sh` does, and why
`mtxgold_run.sh` takes its control arm.

## COMPLETENESS, FIRST LEG — and S21-7 settled first (2026-09-10, session 22)

Session: gate 0 was inserted ahead of the matrix work by hub addendum, because
PW is being asked to sign `shipping.config.s21` and `DSP4_SIMD_DYN` is one of
its five switches.

### S22-4 — a cell outside the 144-word channel page reaches no strip node: the matrix crosspoint was built and stayed at zero

**Severity: HIGH for any future cell that lives outside a strip's page.
Status: found on the part 2026-09-10 and fixed the same session.**

The matrix send cells are deliberately NOT inside the channel's 144-word SPI
page — putting them there would have grown the routing block from 60 words
to 64 and moved every chip-1 address above channel 1's routing node. They
are allocated after every other chip-1 address instead, which is what keeps
the contract bump additive (5,409 D32 cells keep their address to the word).

**That is also what stopped them working.** `spi_handler.asm` bumps
`_ctl_epoch[addr / 144]` on every accepted write, and clamps *everything at
or above 4608* into slot 32 — "a catch-all no strip node watches". The
matrix block starts at 4806. So every matrix write landed in the catch-all,
the ROUTING node's control-rate gate never fired, its prep never ran, and
the matrix crosspoint coefficient stayed at the zero it initialises to.

**Measured, and only because the probe carried both controls:**

```
  chain witness: _buf_C1_FDR_01         peak 0x02BD1D96
  strip 1 post-fader peak = 0x0D39B767   <- the positive control
  send ON : [0, 0, 0, 0, 0, 0]
  send OFF: [0, 0, 0, 0, 0, 0]           <- the negative control
```

A silent bus with the send ON and a silent bus with the send OFF is not a
result; with the POSITIVE control showing the strip driven to 0x0D39B767 it
becomes one. Two earlier runs of the same probe were thrown away for exactly
this reason — the first wrote the send as `f32(0.0)` (the send word is a
LINEAR gain, not dB, so 0.0 is silence) and the second had not called
`drive_strip()`, so the channel fader sat at its `level_db=-inf` default.
Neither would have been distinguishable from this defect without the
control.

**Fixed by giving the handler a second per-strip range.** The block is
contiguous and strip-ordered, so the index is a subtract and a shift and
there is no second multiply in the ISR. Its extent is EMITTED INTO
`dsp_block.h` from the graph (`DSP4_CTL_MTX_BASE` / `_WORDS` / `_SHIFT` /
`_SPAN`) rather than typed — a hand-kept copy of an allocated address is the
drift this tree has been bitten by repeatedly — and the whole test is behind
`#ifdef DSP4_CTL_MTX_BASE`, so a graph without matrix sends builds the
handler it always did.

**The general lesson, which outlives the matrix:** the control-epoch gate
makes "this cell is inside a strip's 144-word page" a load-bearing property
of the address map. Any future family allocated outside those pages that a
GATED node must read needs its own range here, and the failure mode is
silent — the node simply never re-preps, and the cell reads back correctly
over SPI the whole time.

**Passes on the part with the fix** (chip 1 `20df0711`; chip 2 `e9c28846`
UNCHANGED, which is the check that the fix is chip-1 only):

```
  strip 1 post-fader peak = 0x0D39B767   <- the positive control
  send ON : [221885815, 221885815, 221885815, ...]
  send OFF: [0, 0, 0, ...]
  peak with the send ON  = 0x0D39B767
  peak with the send OFF = 0x00000000   <- the negative control
  PASS: the channel reaches matrix 1, and only when sent
```

The matrix bus carries the strip's post-fader block to the word at a unity
send, and exactly zero with the send off — the bus-assign bit folded into
the coefficient as the 08-25 crosspoint mandate requires.

### S22-3 — the scope could drive STRIP 1 and no other strip on any chip-1 block-kernel image

**Severity: MEDIUM, and it silently bounded every per-strip bar this tree
has. Status: fixed 2026-09-10, all of it inside `#if DSP4_SCOPE_BLK_TAP`;
W0 held.**

Found while giving `goldnode`'s GATE arm a verdict on both strips of a SIMD
pair (S22-1). With the tap site emitted, strip 1 read BIT-EXACT and strip 2
reported *"the injection is NOT reaching `_buf_C1_EQ_02` (captured peak 1)"*
on three amplitudes, with the chain witness showing every node of strip 2 at
`0x00000001` against strip 1's `0x08000000`.

**The generated chain contained exactly ONE `call _scope_inject_blk;`,
emitted after chain index 0 — `C1_IN_01` — with `r1 = BLK_CHAIN_A_P1`.** So
the block injector could only ever drive strip 1: an injection meant for
strip N was written before strip N's own input kernel ran, and that kernel
overwrote it.

**And strip 1 worked by luck.** `dsp4_node_verify.py::inject_addr()` handed
back a pool BASE on a block build — `_blk_pool1` for an odd strip, per S9-5's
note about the odd pool — and `_blk_pool1 + 0` happens to be strip 1's own
first chain slot, so the write landed where the chain would read it. The
redirect that `_scope_inject_blk` has carried since S9-5, which exists to map
a named RX slot onto wherever that node's block actually is, was never
exercised on chip 1 at all.

Fixed three ways:

1. the chain emits **one injector call site per strip** (135 on chip 1),
   each naming its own RX slot in `r0` and its own live chain slot in `r1`,
   guarded on `DSP4_SCOPE_BLK_TAP` so the shipping image keeps the single
   call it always had;
2. `_scope_inject_blk` **returns at a site whose slot the host did not arm
   on**. Without that the other 31 sites would each write a whole block at
   whatever raw address `_scope_inj` holds — the one-word-variable overrun
   S9-5 was about, thirty-one times over. `r0 == 0` still means "no
   redirect", which is chip 2, unchanged;
3. `inject_addr()` names the **RX slot symbol** on block builds as well as
   per-sample ones, and the pool arithmetic is deleted rather than extended.

**Strip 1's verdict is unchanged by the fix** (BIT-EXACT before and after),
which is what says the new resolution lands in the same place; strip 2 goes
from no verdict to **BIT-EXACT**. The default build still rebuilds to
`302d6142` / `3b3a6f8e` and `shipping.config.s21` to `81f799f9` / `11366344`.

### S22-2 — the six FX returns reach NO BUS AT ALL: the engines have been inaudible on every image this tree has built

**Severity: HIGH and product-visible. Status: found 2026-09-10 while scoping
gate 2; the fix is gate 2's ROUTING node, which now has to carry the MAIN leg
as well as the aux sends.**

`C2_FX_FDR_nn` DECLARES `outputs = C2_MIX_MAIN_L;C2_MIX_MAIN_R` in `dsp.csv`.
`C2_MIX_MAIN_L` and `C2_MIX_MAIN_R` do not list any FX return among their 17
`inputs`, and `gen_mix_bus_fixed` emits one MAC per entry of `inputs` and
reads nothing else. The declaration is therefore decorative: it is never
consulted by the thing that builds the sum.

Confirmed in the generated kernel rather than argued from the CSV — the only
`_buf_` symbols in `chip2/nodes/C2_MIX_MAIN_L.asm` are `C2_RECV_MAIN_L`, the
four `C2_GRP_COMP_*`, `C2_USB_IN`, `C2_BT_IN`, `C2_CODEC_AUX_IN`, `C2_PI_IN`
and the eight `C2_SNK_IN_*`. Across the whole of `src/chip2/`, the only files
that mention `_buf_C2_FX_FDR_*` are the six FX fader nodes themselves, the
call chain and the FX meters. **No mix node on either chip reads an FX
return.**

So the six engines consume their cycles — 16.28 points of chip 2 at D32 with
six reverbs (S21) — produce a return level, publish a meter, and are summed
into nothing. Taken with **S21-4** (`Fx<n>On` has no reader, so an engine
switched off still runs and still costs), the FX section as shipped costs its
full price whether it is on or off and is inaudible either way.

This is why gate 2's ROUTING node on the return strip has to carry the MAIN
leg as well as the twelve `Fx*AuxSend/AuxOn` crosspoints the definition
names: an aux send from a return that reaches nothing would be building the
second storey of a house with no ground floor.

### S22-1 — S21-7's "frozen gate state" is a step stimulus nobody stopped, and `DSP4_SIMD_DYN` was a proxy for which chain branch carries the witness

**Severity: the FINDING it replaces was blocking a sign-off; the defect
itself is in an instrument and in the generator's witness pass, not in any
audio kernel. Status: CLOSED, mechanism named, fix made and W0-checked.
Supersedes S21-7, whose audio question is closed by construction.**

S21-7 reported that under `DSP4_SIMD_DYN` one strip of every gate pair has
four FROZEN state words — envelope, gain, target, hold count — reproduced to
the digit across four builds and several boots, bisected to that one switch,
with the AUDIO question open. **The audio is not affected and the state was
never frozen.**

**The mechanism is in `dsp_codegen.py`'s scope-tap pass.** `goldnode`'s GATE
arm must be armed on `_gate_gain_<nid>` (the node's own output is `x * gain`,
zero wherever the stimulus is — S21-5 moved it there deliberately). That word
is a one-word-per-block publisher, so its witness is `_scope_tap1`, emitted
from a per-node list `blk_extra`. **The branch of the emitter that handles a
PAIR DRIVER call `continue`s before it ever reads `blk_extra`**, and
`blk_extra` is keyed by node id, not driver id. So the scalar branch carries

```asm
    r0 = _gate_gain_C1_GATE_01; r1 = _gate_gain_C1_GATE_01; call _scope_tap1;
```

and the paired branch carries nothing of the kind. On a paired image no call
site ever presents the armed address; `_scope_tap`/`_scope_tap1` both return
early on `r0 != _scope_src`; `_scope_idx` never advances; and **nothing ever
clears `_scope_arm`** — in a `DSP4_SCOPE_BLK_TAP` build the tap owns
disarming and `_scope_record` stands down by design. `_scope_inject_blk` is
gated on `_scope_arm` alone, and `mode 2` is a STEP, so it kept rewriting the
strip's whole block with the amplitude on every block indefinitely.

**Every "frozen" word is what an open, driven gate holds.** Envelope
221,910,951 is **14 counts** under the injected step 0x0D3A17B5 =
221,910,965 — the attack ladder's own quantisation stall point, which is
precisely why it reproduced to the digit across boots; target is EXACTLY
unity; gain is 9 counts under unity and converging up; and the hold count sat
at **10**, the reload value (`f32(0.2)` ms → 9.6 samples) rewritten every
sample by the open arm of the ladder. The partner strip, which the tool never
injects, is closed with a counter that runs — the contrast that read as an
asymmetry between the two halves of the SIMD pair.

**Settled in one image and one boot with the switch ON**
(`shipping.config.s21` witness arm `7f4417bd`/`e1673170`,
`DIAG_BUILD_CFG2 0xC2019E7F`, `tools/pi/dsp4_gate_latch2.py`):

```
  quiet     scope arm=1 idx=0 go=1 runs=15
              s1 [env gain tgt hold] = [221910951, 268435447, 268435456, 10]
              s2 [env gain tgt hold] = [0, 2684356, 2684355, -25552752]
  wait: capture stalled at 0 of 1024 samples
now clearing _scope_arm by hand (the stimulus stops here):
  t= 0.0s   s1 [env gain tgt hold] = [2, 2684356, 2684355, -6464]
  t= 8.0s   s1 [env gain tgt hold] = [2, 2684356, 2684355, -398448]
```

`idx=0 of 1024` is the instrument stating the mechanism itself: the capture
never took one sample. And with the stimulus stopped, strip 1 falls to
`[2, 2684356, 2684355]` — **the exact rest state S21 recorded for the
`DSP4_SIMD_DYN`-OFF arm** — on an image with the switch ON. The bisect was
measuring which chain branch carries the witness; the switch selects that
branch and the other three do not, which is why all three of them reproduced
the "freeze".

**Two further corrections to S21-7.** `_gate_pair_blk` DOES scatter all four
state words back to both members (`lcntr = 4` over `_gat_st`); S21's
corroboration read the `_DYNGATE` wrapper, not the kernel, and the gate's
write-back is in fact *more* complete than `_comp_pair_blk`'s. And on the
SHIPPED pairs the freeze cannot occur at all: on `s20_*` and `s21_*` both
strips sit at rest with both hold counters decrementing, because a non-tap
image has no chip-1 injection redirect and the stimulus reaches nothing.

**Fix (all outside every shipping image).** The generator emits `blk_extra`
on the pair branch too, for both members — chains gain 128 tap sites on chip 1
and 26 on chip 2, **zero lines removed**, all behind `#if DSP4_SCOPE_BLK_TAP`.
`dsp4_node_verify.py::capture()` disarms in a `finally`, so a stalled run can
never leave the graph driven. `dsp4_gate_latch.py` prints `_scope_arm` and
re-watches with the stimulus stopped. `goldnode.sh` gained `STRIPS="1 2"` and
now ships `dsp4_scope.py` with the run. **W0: the default build rebuilds to
`302d6142` / `3b3a6f8e`, byte for byte.**

**And the same blind spot covered chip 2's paired dynamics** —
`C2_GRP_GATE_01-04`, `C2_GRP_COMP_01-04`, `C2_MAIN_OCOMP_01-04`,
`C2_MAIN_COMP`, `C2_SUB_COMP` had no gain-word witness either, so any bar
armed on one of them would have stalled identically and driven the graph for
as long as it was left armed. That is the fourth time this shape has cost a
session (S9-5, S12-8, S13-4, and this): an instrument silent about the thing
it was built to watch.

## THE HEADROOM, MEASURED DRIVEN — and chip 1's 380 bytes made 40,572 (2026-09-10, session 21)

Session: the FX engines (the plugin load PW's headroom rule is about) driven
on `s20_*` at both products with a per-algorithm ladder taken on one boot;
`DSP4_SHARED_KERNELS` made to coexist with `DSP4_SIMD_DYN`; `goldnode` fixed;
and the worst-block column of every capacity table in the record corrected.
Write-up `MW/D32/DSP/dsp4-s21-20260910.md`. Contract `defs-v2026.09.08.4`,
unchanged. `shipping.config` and `shipping.config.s20` unchanged. **The only
file under `MW/D32/DSP/SHARC/src/` that changed is the GENERATED
`chip1/shared_kernels.asm`, which is behind `#if DSP4_SHARED_KERNELS` and is
in neither shipped image: the default build still reads `302d6142` /
`3b3a6f8e` and `shipping.config.s20` still reads `32dc1ea1` / `29d00a5e`,
byte for byte, rebuilt after every change below.**

### S21-1 — the plugin load, measured driven: six reverbs cost 16 points of chip 2, and BOTH products still fit

**Severity: none (measurement). Status: MEASURED, two boots per product,
zero missed blocks on every row.**

PW's requirement of 2026-08-28 is that 32 strips is the MINIMUM and the fit
must carry headroom for plugins. The FX engines ARE that plugin load and they
had never been driven: `--mode load` leaves every `Chan<nn>FxSend` at 0.0, so
`BUS_FX_01..06` carried silence however loud the inputs were and the six
engines ran their algorithm over zeros. The record's last figure for them was
a silence estimate of 6–7 % of chip 2 scaled from block 8.

`--mode loadfx` opens all six sends on all 32 strips and puts the engines on,
all wet, at a named Type, with the engine parameters written to the patch
`dsp.csv` declares; `FXTYPES="4 3 0 2"` takes a rung per algorithm **on one
boot**, so the FX cost is a within-boot difference and not a difference of
two boots. The regime is proved before every rung: six engines enabled, all
at the Type asked for, none parked in the unimplemented-Type bypass when the
Type is an implemented one, all six Freeverb comb delay lines carrying signal
at eleven probe offsets, all six engines publishing non-zero.

**Chip 2, driven, both boots, against a Type-4 rung where the dispatch parks
the engines in its explicit bypass:**

| rung | D32 | vs Type 4 | D24 | vs Type 4 |
|---|--:|--:|--:|--:|
| Type 4, parked | 71.00 / 70.62 | — | 57.62 / 57.63 | — |
| Type 2, Doubling | 71.69 / 71.66 | +0.86 | 58.70 / 58.78 | +1.12 |
| Type 0, Echo | 71.99 / 72.30 | +1.33 | 59.16 / 59.15 | +1.53 |
| **Type 3, Reverb** | **87.10 / 87.08** | **+16.28** | **73.89 / 74.23** | **+16.44** |

**Six reverbs driven on `s20_*` cost 16.28 points of chip 2 at D32 and 16.44
at D24, leaving 12.9 % of chip 2 free at D32 and 25.8 % at D24, with zero
missed blocks on every row of both boots of both products — and the worst FX
type is Reverb, by about nineteen times.** The six engines are fixed
instances and do not scale with the channel count, which is why the two
products pay the same for them. `s21_*` reproduces it: +16.56 at D32 and
+16.74 at D24.

Chip 1 does not move with the algorithm — the engines are chip 2's — but it
does pay for the SENDS: **+3.0 points at D32 and +2.5 at D24** of crosspoint
accumulate for six more sends on 32 strips (71.6 → 74.6 % and 53.8 →
56.3 %). Chip 2 pays nothing for the sends: its Type 0 rung reproduces S20's
sends-closed row to within the boot spread, because chip 2's FX receive,
return-fader and meter chain runs whether the bus carries signal or not.

**The reverb's cost does not depend on its settings, and that is measured.**
The D32 rungs ran at `damp = 0` and `feedback = 0` (every `_fx_*` word but
the Type and the mix is a `.var` with no initialiser and no host had written
one); the D24 rungs ran with the graph's declared patch written, and the
regime line proves it — 6 of 6 damping states non-zero against 0 of 6 at
D32. The deltas are 16.28 and 16.44. S21-4 says why that had to be so.

### S21-2 — `build.sh` refused SHARED_KERNELS with SIMD_DYN for two sessions, and the reason did not hold

**Severity: MEDIUM (a lever withheld on a wrong argument). Status: FIXED —
the refusal is replaced by a per-build CHECK.**

From S18 until 2026-09-10 `build.sh` exited 2 on `DSP4_SHARED_KERNELS`
together with `DSP4_SIMD_DYN`, saying: *"The SIMD pair drivers call
`_C1_COMP_nn_process_sample` directly; a shared body reached that way would
run on whatever record base the last strip left in the register."* S20-3
recorded that as the reason chip 1's 380 free bytes could not be improved,
and the window note carried it to PW.

**The premise is true and the conclusion does not follow.**
`_C1_COMP_nn_process_sample` is not the shared body — it is that NODE's own
stub. `dsp_codegen.py::gen_shared_kernels` emits `_process` and
`_process_sample` entry points **per node**, and each sets `i7` to that node's
record base and `i5` to that node's predecessor buffer before jumping to
`_shk_comp_smp`. A pair driver that calls that label gets the right strip for
exactly the reason `process_chain` does. The pair KERNELS never call a node
body at all: `_comp_pair_blk` and `_gate_pair_blk` take both channels' record
bases in r4–r7 and run their own loop, so the pairing and the sharing act on
different code.

The refusal is gone from `build.sh` and from `tools/dsp/cfg_words.py`, which
mirrored it. In its place, `shared_kernel_check.py --entries` runs on every
`SHARED_KERNELS` build and fails it if any `_shk_<cls>_*` entry point is named
by anything but one of that class's per-node stubs, if a stub jumps without
loading its own record base, or if a stub loads more than one base or more
than one predecessor buffer. On the s21 arm: **64 stubs per class, each
loading its own record base**, for COMP and for TUBE.

### S21-3 — what actually did not build was SHARED_KERNELS + DYN_LUT, and there were three faults, all latent since S18

**Severity: MEDIUM (three generator/checker defects in one place). Status:
FIXED, all three, and the arm builds and links.**

Removing S21-2's guard produced three failures in a row, none of them about
SIMD, all of them in the shared COMP body's LUT design step — the arm S18
never assembled because S18 built from `shipping.config`, where
`DSP4_DYN_LUT` is 0.

1. **`Rn = Rn + <const>` is not an instruction on this core.** The LUT design
   step passes four record ADDRESSES in r0–r3, and `_shk_rewrite` emitted
   `r0 = i7; r0 = r0 + SHK_COMP_OFF_comp_cgp;`. easm21k: *"Semantic Error in
   type 2 instruction / Operands don't fit instruction template 'REG EQUAL REG
   PLUS_OP REG'"*, four times. FIX: load the OFFSET as the immediate and add
   the base AS A REGISTER, which needs one scratch data register.
   `SHARED_KERNEL_CLASSES` now names it (`r11`) and the generator CHECKS the
   choice — a class whose body mentions its scratch register fails codegen
   rather than clobbering a live value. `r11` is already clobbered at those
   sites in the inline arm (`_dyn_lut_step` and `_compgain_fx` clobber
   r0–r12), so the shared arm's write to it changes nothing that was live.
2. **`shared_kernels.asm` did not inherit `#include "lib/dyn_lut.h"`.** The
   include is emitted in a node file's HEADER, not in the body the shared pass
   splits, so the generated file referenced `DYN_LUT_N` and defined it
   nowhere. A LINK error, and only with DYN_LUT on.
3. **`shared_kernel_check.py` could not evaluate `DYN_LUT_N`.**
   `defines_from()` matched only `#define NAME <integer>` and `DYN_LUT_N` is
   `(((DYN_LUT_OCTHI - DYN_LUT_OCTLO + 1) << DYN_LUT_K) + 1)`. An absent name
   resolved to 0, so `.var _comp_lut_<nid>[DYN_LUT_N]` scored as a ZERO-word
   field, every COMP field after the table looked 337 words out of place, and
   **the check reported the LINKER as wrong about a layout that was correct**.
   Expressions are evaluated now, in two passes, and an unresolvable length is
   a hard error rather than a zero.

The lesson is narrow and worth keeping: a switch pair was refused for two
sessions on a mechanism that was fine, while the pair that was actually broken
(`SHARED_KERNELS` + `DYN_LUT`) was never named because no arm had ever
assembled it.

### S21-4 — `Fx<n>On` has no reader, and eleven more FX_ENGINE host cells do not reach the audio

**Severity: MEDIUM (host cells with no effect; not a regression). Status:
MEASURED and attributed; no fix attempted this session.**

The FX ladder's first draft used `Fx<n>On = 0` as its baseline and the row
came back identical to the rung before it. `_fx_on_<nid>` is named by exactly
one thing in the tree — the SPI dispatch table in `chip2/dsp_params.asm`,
which is what lets the host WRITE it — and by no instruction in any kernel.
**The FX_ENGINE body has no on/off branch.** A host that switches an engine
off gets neither silence nor a saved cycle.

Auditing all 34 of the node's per-node words against every instruction in the
tree (excluding the dispatch table, which is the writer): **sixteen are named
by no kernel instruction, and eleven of those are host-writable SPI cells.**
Five cells reach the arithmetic — `Type`, `Mix`, `Damp`, `Feedback`,
`DelayTime`. `On`, `Decay`, `PreDelay`, `EqLo`, `EqMid`, `EqPresence`, the
five `FX HPF` coefficient words, `ModRate`, `ModLevel`, `LfoShape` and
`StereoWidth` land in words nothing reads; `Balance`, `DuckOn` and `DuckSens`
are dispatched to address 0 and go nowhere at all.

Two consequences, one of them useful:

* The reverb is, today, a Freeverb whose **room size and decay do nothing**,
  and whose EQ, modulation and width sections do not exist. That is a
  feature-completeness item for PW, not a defect in anything that was
  claimed.
* "The other FX types at their **worst settings**" has no worst setting to
  find: none of the five live cells is a branch, and the Freeverb body
  executes the same instructions for every value of every one of them. **The
  cycle figure for each Type is THE figure**, which is why the reverb rung
  reproduces to 0.05 points across boots.

### S21-5 — `goldnode` was reading words the block-kernel graph does not write, and the fix is the witness the tree already had

**Severity: MEDIUM (a bar that could not pass). Status: FIXED. Closes
S18-7 / S19-7.**

S19-7 attributed the failure and stopped there: three of the four arms read
`_buf_` scalars the block-kernel graph never writes. Stated completely: under
`DSP4_BLOCK_KERNELS` a strip node's `_buf_<nid>` is not the signal path — a
block kernel reads its predecessor's block from a shared pool slot through
`i3` and writes its own through `i4`. FADER_PAN leaves the block's last
sample in `_buf_<nid>` as a linkage scalar (which is why FDR's OUTPUT arm read
live); most classes never touch it. `_scope_record` then reads
`_scope_src + _sample_idx`, i.e. sixteen consecutive words from the named
address, so an arm pointed at a one-word scalar captures one possibly-stale
word and fifteen belonging to the next variable in the map. GATE's arm was
worse: its OUTPUT was `_gate_gain_<nid>`, a word the block kernel writes ONCE
per block, so the gain trajectory the model computed could not be captured
there under any stimulus.

FIX, and it introduces no instrument: `goldnode.sh` builds its arm with
`DSP4_SCOPE_BLK_TAP=1` — the block-aware witness S9-5 built for this and
famverify has used since S10 — under whatever `SHIPPING_CONFIG` names, and
prints the tap-OFF control's md5 first so the log carries the staged pair's
bytes beside the witness arm's. The GATE arm's output moves to
`_buf_C1_GATE_nn` and `_gate_model` returns the node's output
`sat32(rns(x * gain))` instead of the gain: the same state machine, the same
hold-less twin, one multiply further along.

### S21-6 — the worst-block column has been ONE DIAG TICK too big on about one row in six, and the true worst block is half a point above the mean

**Severity: MEDIUM (instrument; it inflated a column PW reads). Status:
ATTRIBUTED with the mechanism, corrected in the REPORTING, fix in `main.asm`
named and deliberately not made this session.**

About one capacity row in six carries a worst-block figure between 350 % and
390 % of budget **with zero missed blocks over 135,000** — which cannot both
be true. The caveat printed beside it since S13-2 was "the raw latch,
including the config ladder", and that is not the explanation: several
affected rows are row A, taken before any parameter is written, and the figure
is the POST-clear latch over the dwell.

**The mechanism is two instructions wide.** `main.asm` closes each block pass
with `r2 = tcount;` then `r0 = dm(_diag_ticks);`, and computes
`cycles = (ticks - t0) * DIAG_TPERIOD + (c0 - tcount)`. If the tick ISR fires
BETWEEN those two reads, the tick it just counted is included in `ticks` while
the matching timer wrap is not reflected in the `tcount` already in r2, and
the pass is credited with one whole `DIAG_TPERIOD` — 983,040 cycles, 300 % of
a block-16 budget, exactly the size of the anomaly.

**Measured across the record: every row in the S20 and S21 goldens whose
worst figure exceeds 150 % of budget lands within HALF A POINT of its own
average once one TPERIOD is subtracted** — eleven rows, both chips, both
products, three arms, 353.59 % → 53.59 % against an average of 53.78 %,
386.89 % → 86.90 % against 87.30 %, and so on. So the true worst block on this
configuration is about half a point above the average, and the graph is
steadier than the record has been able to say.

**AND THE "CONFIG LADDER TRANSIENT" DOES NOT EXIST.** S13-2 introduced the
caveat printed beside every capacity row since — that the PRE-clear latch is
"a one-off burst of parameter conversions and cascade sizings that no
per-block budget has to cover", which "read 376 % on chip 2 on an arm with
zero missed blocks". Of the **104** pre-clear latches in this tree's goldens
that exceed 150 % of budget, **92 sit exactly one TPERIOD above an ordinary
pass of their own row and the other twelve sit exactly one TPERIOD above an
ordinary pass of the PREVIOUS row of the ladder** — which is what a pre-clear
latch holds, and it lands within 0.45 points every time. All 104 are
accounted for; not one is a configuration transient. **There was never a
376 % block on this part.** The caveat text is corrected.

`dsp4_capacity.py` reports the raw latch unchanged and the de-ticked value
beside it, only where the raw figure exceeds 150 % of budget AND the arbiter
counted zero missed blocks AND `raw − TPERIOD` is still at or above the
last pass, and the reported figure is `max(raw − TPERIOD, _proc_cyc)` and a
FLOOR on the true worst block — a pass credited with a spurious TPERIOD
destroys the latch's information about every pass after it. `cap_table.py`
marks such a figure `*` and prints the reason.
Nothing is silently corrected. **The fix is four instructions in `main.asm` at
two call sites — read `_diag_ticks`, read `tcount`, read `_diag_ticks` again,
retry the pair if it moved — and it is not made in the session that found it,
so every figure in `dsp4-s21-20260910.md` comes from the images S20 staged.**

### S21-7 — SUPERSEDED BY S22-1: what looked like frozen gate state was a step stimulus nobody stopped, and the audio is NOT affected

**Severity: was MEDIUM and blocking a sign-off. Status: CLOSED 2026-09-10 by
S22-1 — the four words belong to a gate held OPEN by a `mode 2` step
injection that nothing disarmed, because the PAIRED branch of the generated
call chain omits the `_scope_tap1` site for `_gate_gain_<nid>` that the bar
arms on. `DSP4_SIMD_DYN` selects that branch; it does nothing to the gate.
The audio is NOT affected, and `_gate_pair_blk` does scatter all four state
words back to both members. Read S22-1 instead of what follows; the
measurements below are real, the attribution is not.**

`goldnode`'s GATE arm declines a verdict on `shipping.config.s20` — "the gate
is NOT closed at rest (target 268435456, range floor 2684355)" — with
`state at rest: [221910951, 268435447, 268435456]` reproduced **to the digit
across four builds and several boots**. 221,910,951 is the injected
amplitude: the envelope is holding the last driven level.

**A four-way bisect puts it on `DSP4_SIMD_DYN` and nothing else.** Each switch
turned off in turn, everything else in `shipping.config.s20` unchanged, GATE
arm only:

| arm | gate state at rest | verdict |
|---|---|---|
| `s20` minus `DSP4_SIMD_DYN` | `[2, 2684356, 2684355]` — closed | **64 of 64 bit-exact, control fired 2 of 64 (predicted 2)** |
| `s20` minus `DSP4_GATE_LINTHR` | `[221910951, 268435447, 268435456]` | no verdict |
| `s20` minus `DSP4_DYN_LUT` | `[221910951, 268435447, 268435456]` | no verdict |
| `s20` minus `DSP4_STRIP_FUSED` | `[221910951, 268435447, 268435456]` | no verdict |

**Then asked of the PAIR rather than of one strip** (`gatelatch.py`, new): the
same gate parameters written to strips 1 AND 2, the strip driven by the
scope's step injection, then twelve seconds of watching both strips' four
words with nothing driving:

| word | strip 1 (channel A) | strip 2 (channel B) |
|---|---|---|
| `_gate_envelope` | 221,910,951 — **unchanged for 12 s** | 0 |
| `_gate_gain` | 268,435,447 — unchanged | 2,684,356 |
| `_gate_gain_target_q` | 268,435,456 (unity) — unchanged | 2,684,355 (the range floor: CLOSED) |
| `_gate_hold_count` | 10 — unchanged | −6,732,352 → −7,554,848, **decrementing every sample** |

Strip 2's hold counter is decremented by the ladder on every sample below
threshold, so strip 2's gate is demonstrably running. **Strip 1's four words
never move.**

**At the source level the two pair drivers are not the same shape, and the
difference was already recognised once.** `_DYNCOMP_nn_mm_process` ends with
an explicit epilogue — *"the pair writes its gain display to the shared park;
give it back to each node so dsp4_dyn_witness.py still reads a live per-strip
compressor gain"* — copying `_cmp_gn[0]` and `_cmp_gn[1]` into
`_comp_gain_{ca}` and `_comp_gain_{cb}`. **`_DYNGATE_nn_mm_process` has no
write-back at all**: after `call _gate_pair_blk` it returns.

**WHAT IS NOT ESTABLISHED, and must not be read into this.** Whether the
AUDIO differs is open. No bar that looks at samples has found a difference:
famverify's GATE family reads LIVE on the SIMD arm, `famdiff` puts the s21
report 0 of 20 families from the s20 one and S20 put the s20 report 1 of 20
from the shipping pair (the compressor's table), `busgold` reproduces the
2026-08-30 golden BIT FOR BIT with the two declared deviations off, and
`golden_harness` is 59/59. Against that: **the per-sample gate body reads
`_gate_gain_<nid>` as its starting state**, and the pair driver calls that
body for sample 0 of every block, so a stale word there is not obviously
harmless. Nothing here decides it.

Two consequences worth carrying:

* **`dsp4_c2regime.py --require-driven` counts a FROZEN envelope as a live
  one.** "64 of 64 dynamics envelopes live on chip 1" is weaker evidence than
  it reads on a SIMD image. The CAPACITY figures are unaffected — the paired
  kernel runs both channels whatever it publishes, and `DIAG_BLK_OVERRUN`
  counted the blocks — but the regime instrument should test that an envelope
  MOVES, not that it is non-zero.
* **Half the strips' host-visible gate display is dead** on the configuration
  proposed for the window, whatever the audio turns out to be.

The next step is one session's work and it is named: put the four state words
under the same treatment `_comp_gain_` already gets, then re-run goldnode's
GATE arm on the SIMD image and require 64 of 64 — the bar is now able to
score it, which is what S21-5 bought.

## THE PAIR THAT FITS BOTH PRODUCTS UNDER LOAD — one named configuration, every bar on that image (2026-09-10, session 20)

Session: `shipping.config.s20` built as one named configuration
(`STRIP_FUSED` + `SIMD_DYN` + `C2_BQ_GRAPH` + `DYN_LUT` + `GATE_LINTHR` +
Option A), read back off the part to the bit, every audio bar taken on THAT
image, driven capacity on both chips and both products, and the decision table
rebuilt on driven numbers only. Write-up `MW/D32/DSP/dsp4-s20-20260910.md`.
Contract `defs-v2026.09.08.4`, unchanged. `shipping.config`'s VALUES unchanged
(one stale COMMENT corrected — S20-2). **No file under
`MW/D32/DSP/SHARC/src/` changed: the default build is `302d6142` /
`3b3a6f8e`, byte for byte the pair S17, S18 and S19 left.**

### S20-1 — S12-5 read OPEN for a day after S13-1 closed it, and that is what withheld the recommendation

**Severity: MEDIUM (record). Status: FIXED — S12-5's status line corrected.**

S19's §4 declined to recommend the only configuration it had measured that
fits D32 under load, on the grounds that *"what stands against it is
S12-5/S12-7, unchanged"*. Neither was unchanged:

* **S12-5** is titled *"SIMD_DYN is audio-correct; `DSP4_C2_BQ_GRAPH` is
  not"*. Its first clause is a RESULT — 17/20 LIVE, contract 20/20 with 0
  FAILED, three arms BIT_EXACT, verdict for verdict the shipping pair. Its
  second clause was closed the next day by **S13-1** (severity high, status
  CLOSED), which named the mechanism (the pair driver's steady test never read
  the pending-DESIGN flag, so for any class the host writes PARAMETERS to the
  design step at the top of the node body never ran and `swap_pending` never
  rose), fixed it in `gen_bq_pairs_c2`, and witnessed it three ways.
* **S12-7** — `DIAG_BUILD_CFG2` not carrying the switch — was closed by
  **S15-9** (bit 12) and the bench decoder learned it in **S18-4**.

S12-5's status line still read `OPEN — the chip-2 aux biquad pair`. A session
that trusts the status lines rather than reading the successor findings gets
the opposite answer to the one the record supports, and that is exactly what
happened. The line is corrected, pointing at S13-1.

**The lesson is mechanical, not editorial:** when a finding is closed by a
LATER finding rather than by its own session, the closing session must go back
and edit the earlier status line. Three of the four findings involved here
(S12-5, S12-7, S18-7) were closed or attributed by a different session than
raised them.

### S20-2 — `shipping.config`'s comment on `DSP4_C2_BQ_GRAPH` was two closed findings out of date

**Severity: MEDIUM (record). Status: FIXED — the comment rewritten; the value
is untouched.**

`shipping.config` exists because the build that shipped was not the build that
was measured, and its whole claim is that the shipping configuration is named
in ONE place. Its comment on `DSP4_C2_BQ_GRAPH` said, on 2026-09-10:

> NAMED HERE AT 0 BECAUSE IT IS NOT AUDIO-CORRECT, measured on the part
> 2026-09-09 (findings S12-5) … NOTE, and it is the same shape as the fault
> this file exists for: DIAG_BUILD_CFG2 does NOT carry this bit, so the two
> candidate images read back the same word and differ in audio. Recorded as
> S12-7.

Both sentences were true when written. Neither has been true since S13-1
(the defect is fixed) and S15-9 (the bit is in the word) respectively. So the
file that exists to prevent a stale fact about the shipping build was carrying
two, in prose rather than in values — which is the same failure one layer up
from the one it was built for.

The comment now states what the 0 is: **a PW ruling, not a defect**, with
`shipping.config.s20` named as the proposal to move it and the driven table
named as the case. The value stays 0; moving it is PW's.

### S20-3 — the configuration that fits both products leaves chip 1's code pool 380 bytes, and S18's byte lever CANNOT be combined with it

**Severity: MEDIUM (resource, no defect). Status: MEASURED and recorded.**

The cycle numbers are only half the cost of this configuration. From the
linker map, chip 1:

| arm | code, Blocks 3+2 | free | code in Block 1 | DM |
|---|--:|--:|--:|--:|
| default (`shipping.config`) | 235,064 / 262,144 (89.7 %) | **27,080** | none | 251,412 (67.0 %) |
| `s20_*` | 261,764 / 262,144 (99.9 %) | **380** | **1,692** | 298,922 (79.7 %) |
| `s20f_*` | 261,828 / 262,144 (99.9 %) | **316** | 1,692 | 298,922 (79.7 %) |
| `s20` + scope tap (the bar image) | 262,004 / 262,144 (99.9 %) | 140 | 7,708 | 304,942 (81.3 %) |

**The 1,692 bytes in Block 1 are `afb_design_fx` (666), `xover_design_fx`
(622) and `geq_design_fx` (404), and nothing else.** All three are on
`DSP4_COLD_OBJS` and all three run once per parameter move, never per block.
So S16-1's ordering did precisely the job it was built for: an image that does
not fit Blocks 3+2 gets to CHOOSE what pays the contended fetch, and what pays
is cold code. **No per-block kernel is fetched from Block 1 on either arm.**
The tap image spills 7,708 bytes and all eleven objects are on the same list.

**The margin, stated properly: 380 bytes of free pool plus 6,666 bytes of cold
code still in Blocks 3+2 — about 7,046 bytes of growth before a HOT kernel is
fetched from the DM/DMA block.**

And the obvious lever is closed: **`build.sh` REFUSES
`DSP4_SHARED_KERNELS` with `DSP4_SIMD_DYN`** (exit 2), because the SIMD pair
drivers call `_C1_COMP_nn_process_sample` directly and a shared body reached
that way would run on whatever record base the last strip left in the
register. S18's −38,634 bytes are therefore not available in this
configuration until the pair drivers learn the shared calling convention.
S15-8 named chip 1's code pool as the binding resource for the dynamics
integration; this is that constraint, measured on the configuration that
integrates them.

Not a defect and nothing here changes an instruction. It is the sentence that
belongs beside the cycle numbers when PW decides what else goes on chip 1.

### S20-4 — `busgold.sh` overrode the two switches the configuration is about, and defaulted them to 0

**Severity: MEDIUM (bar). Status: FIXED.**

`busgold.sh` pins `DSP4_SIMD_DYN=${SIMD:-0} DSP4_STRIP_FUSED=${FUSED:-0}` on
`build.sh`'s command line. `build.sh`'s rule is that the ENVIRONMENT WINS over
the configuration file — which is the right rule and is how every control arm
in this tree is built — so run with `SHIPPING_CONFIG=shipping.config.s20`, a
file that names both switches at 1, the bar quietly built and scored an arm
with both at 0. Its own capture said so and nobody was reading it:
`paired_build=False bq_paired_build=False`.

**A bar cannot witness a configuration whose defining switches it overrides,
and the override is invisible precisely because it is the bar's own default.**
That is findings S11-1 — the capacity record quoting an image with two
switches on that no file named — one layer inside the bars.

FIX: `SIMD` and `FUSED` still exist (they are how the pairing is A/B'd against
the stored golden) but they now DEFAULT to what the configuration file says,
read through `tools/dsp/build_config.py`, and the arm is printed in the log
line beside the md5.

Two related gaps closed with it:

* **`tools/dsp/build_config.py` read only `DSP4_SHIPPING_CONFIG`**, while
  `build.sh` reads `SHIPPING_CONFIG`. With two configuration files in the tree
  that means the shell half of a script builds one configuration and the Python
  half reads another. `SHIPPING_CONFIG` is authoritative now, with the old name
  kept as an alias.
* **`check_shipping_config.sh` is about `shipping.config` specifically** — it
  diffs that file against the bench mirror — so it now names the path instead
  of following `SHIPPING_CONFIG` to some other file and reporting that the
  mirror disagrees with it.

**`bqeverify.sh` pins the same two switches at 1 unconditionally**, which
happens to be what `shipping.config.s20` says, so its result stands. It is
worth recording that it has therefore always measured the PAIRED cascade
whatever `shipping.config` said — for that bar it is the right arm (the SIMD
cascade is what `bq_float_ref` is being checked against) but it is another
place where the image under test is not the configuration named.

### S20-5 — `s20_*` is audio-correct on every bar the tree has, and the one bar that is not bit-exact is 0.03934 dB

**Severity: N/A (a result). Status: MEASURED on the part.**

The whole configuration on one image (`065693ca` / `4cfa4763`, the `s20`
configuration plus the block-aware scope tap), one bench session, both chips:

| bar | verdict |
|---|---|
| `golden_harness` | **59/59** |
| `dsp_validate` | **OK** |
| `famverify`, 20 families, both chips | **1 of 20 verdicts differs from the shipping pair, and it is the one that has to: COMPRESSOR numeric.** 17/20 audio LIVE, contract 20/20 with every rw cell answering at its landed address, FADER_PAN and TUBE_SAT numeric BIT_EXACT, every `moved` count identical family for family (`tools/dsp/famdiff.py`) |
| `COMPRESSOR` numeric, in dB | **0.00518 dB** worst deviation against the table's 0.0950 dB design bound and PW's 0.1 dB ruling; all six converted parameters bit-exact. S16's figure to the digit, on an image that also carries fusion, SIMD and the chip-2 pairing |
| `bqeverify float` | **PASS, 0 ULP over 36,864 words** against `bq_float_ref` on the part; both arm hashes MATCH and the A-vs-B divergence bitmap is 567 of 576 cells exactly where the model names them |
| `geqverify` design + live | **GEQ_DESIGN_OK** — 1–3 ulp, ≤0.00014 dB modelled; live tone **+11.997 dB at 1 kHz against +12.000 modelled** |
| `afbverify` design + live | **AFB_DESIGN_OK** — 2–4 ulp, ≤0.00009 dB modelled; live tone **−18.000 dB against −18.000 modelled**; both negative controls read identity |
| `busgold` | **NOT bit-exact, and it cannot be** — see below |
| `goldnode` | FAILS, identically to the shipping default; S19-7's attribution stands (the bar reads `_buf_<nid>` scalars the block-kernel graph never writes) |

**The three families S12-5 found INERT under `DSP4_C2_BQ_GRAPH=1` are LIVE with
that switch ON, and they produce the SCALAR arm's words to the bit:** GEQ
`0x08000000 → 0x082DE520` moved 64/64, ANTI_FB `0x08000000 → 0x07B14CA0` moved
64/64, CROSSOVER `0x07E960D0 → 0x074AF178` moved 64/64. The live-tone arms are
the stronger witness: a paired AUX GEQ delivers its designed +12 dB to within
0.003 dB and a paired AUX AFB its −18 dB notch to within 0.000 dB. S12-5
measured `+0.000 dB at every point` for both.

**`busgold` and why NOT bit-exact is the right answer.** The harness leaves
`CompPar` at its power-on 100 %, so the strip's compressor is FULLY WET in the
capture — that is what review finding D59 changed and why the golden was
re-baselined on 2026-08-30. The compressor's gain computer is precisely what
`DSP4_DYN_LUT` replaces, so a bit-exact capture would prove the table was NOT
reaching the audio. Measured with `tools/dsp/busdev.py` (new — the bar reported
LSBs, and a maxdiff in LSBs reads the same for a 0.04 dB table and a dead node,
which is S16-4's criticism of counting):

```
postD59 vs s20:  235 of 256 words differ
                 0 of them zero in one capture and not the other
                 worst level difference 0.03934 dB at word 21
                 bound 0.0950 dB: PASS
```

**0.03934 dB worst word.** Not one word is zero in one capture and non-zero in
the other, which is the signature a dead node leaves. For scale, D59's real
audio change to this same capture was 151 times larger in LSBs.

### S20-6 — fusion, the SIMD pairing and chip 2's paired biquad graph change NOT ONE BUS WORD, and the whole busgold difference is the two declared deviations

**Severity: N/A (a result). Status: MEASURED on the part, three arms, one bench
session.**

`busgold.sh` captures 256 consecutive words of `_buf_C1_BUS_MAIN_L` out of a
running graph with both strips configured in opposite arms of every predicated
branch and the compressor left FULLY WET. Against
`goldens/busgraph-postD59-20260830.json`:

| arm | capture sha256 | vs the golden |
|---|---|---|
| `s20` with `SIMD=0 FUSED=0` (what the bar built before S20-4 was fixed) | `4126c00730a31f5f` | 235 of 256 differ, worst **0.03934 dB** |
| `s20`, the real configuration — `paired_build=True bq_paired_build=True` | **`4126c00730a31f5f`, the same capture byte for byte** | 235 of 256, worst 0.03934 dB |
| `s20` with `DSP4_DYN_LUT=0 DSP4_GATE_LINTHR=0`, everything else on | **`ba3f52ecb83f9a60` — the golden's own sha256** | **0 of 256. GRAPH BIT-EXACT** |

* **`DSP4_STRIP_FUSED`, `DSP4_SIMD_DYN`, `DSP4_C2_BQ_GRAPH` and
  `DSP4_TX_EARLY=2` together reproduce a golden taken on 2026-08-30 BIT FOR
  BIT.** Rows 1 and 2 are the same capture (`busdev.py`: 0 of 256 words, 0.0000
  dB), so the pairing is bus-word-identical to the scalar graph.
* **The entire difference is `DSP4_DYN_LUT` + `DSP4_GATE_LINTHR`** — precisely
  the two switches that are declared numeric-spec deviations — **at 0.03934 dB
  worst word against the table's 0.0950 dB bound**, with not one word zero in
  one capture and non-zero in the other.

A bar that goes from BIT-EXACT to 235 words differing when exactly the two
switches with dB bounds on them are turned on, by an amount inside those
bounds, is the bar working. `tools/dsp/busdev.py` is what turns its LSB count
into that sentence.

### S20-7 — `s20_*` fits BOTH products under load with 27 points of margin, and the switch S19 left off is most of it

**Severity: N/A (the result). Status: MEASURED, two boots, both products, both
chips, 16 of 16 regime snapshots proven.**

Instrument unchanged from S19: the `driveall` bitstream broadcasting the CM4's
400 Hz full-scale square onto every DSPA input lane, three rows on one boot,
`dsp4_c2regime.py --require-driven` proving every envelope live before row C,
`DIAG_BLK_OVERRUN` the arbiter. Row C is the product number.

| arm | D24 chip 1 | D24 chip 2 | D32 chip 1 | D32 chip 2 | overruns |
|---|--:|--:|--:|--:|---|
| `blk_*` (shipping default, S19) | 118.9 | 119.2 | 158.2 | 142.8 | **one block in six / one in three** |
| `s16_*` (S19) | 82.4 | 94.6 | 109.5 | 115.8 | zero at D24, 8.7 % / 13.3 % at D32 |
| `s18_*` (S19) | 119.6 | 119.3 | 159.3 | 144.3 | one in six |
| **`s20_*`** | **53.83 / 53.79** | **58.99 / 59.16** | **71.57 / 71.22** | **72.55 / 72.56** | **ZERO, every row, both boots, both products** |
| **`s20f_*`** | **52.43** | **54.93 / 55.09** | **69.75 / 69.61** | **66.73 / 66.72** | **ZERO** |

**Three things this table settles.**

1. **The signal is free on this configuration, on both chips and both
   products.** Driven minus silent-loaded is +0.05 / −0.29 points at D24 and
   +0.08 / +0.26 at D32. On the shipping default that column is +42.5 and
   +29.3. The LUT's claim — that the above-threshold path costs what the
   below-threshold one does — now holds on chip 2's output chains as well as
   chip 1's strips.
2. **`DSP4_C2_BQ_GRAPH` is worth ~21 points of chip 2 at D32 and ~17 at D24.**
   S19's `s16sd` arm is exactly `s20` minus that switch and it read 93.90 % /
   76.42 % where `s20` reads 72.55 % / 58.99 %. The switch S19 held at 0 on the
   strength of a finding closed a day earlier is most of the margin, and that
   is the practical cost of S20-1.
3. **`s20f_*` is worth 1.4–4.1 points for nothing measurable**, as S13-5
   predicted for the pipelined loop. Neither product needs it to fit, which is
   why the proposal names it at 0 and measures it beside.

Latency, MEASURED not carried: `s20_*` 14,513 / 14,516 median offset against a
**re-taken** LOGIC-only reference of **14,433** (100.0 % coherent, reproducing
S17's figure to the sample) — **80 / 83 samples through-DSP against the
contract's 82**, inside the instrument's ±2-sample spread.

**The worst-block column is still not a decision number** (S19-5): two entries
of 353 % and 366 % sit beside a full pass count and zero overruns, which a real
block cannot. Every other worst-block figure is within 0.7 points of its
average.

## EVERY CAPACITY FIGURE WAS A SILENCE FIGURE — the DRIVEN instrument, and what the staged pairs cost under load (2026-09-10, session 19)

Session: the driven capacity instrument made the standard — a stimulus the
part does not pay for, every dynamics node engaged, the regime proved before
the row is taken — and every staged pair re-priced under load on both chips
and both products. Write-up `MW/D32/DSP/dsp4-driven-20260910.md`. Contract
`defs-v2026.09.08.4`, unchanged; `shipping.config` unchanged. **No file under
`MW/D32/DSP/SHARC/src/` changed: the default build is `302d6142` /
`3b3a6f8e`, byte for byte the pair S17 and S18 left.** What changed is the
instrument.

### S19-1 — the driven instrument: the stimulus is in the CPLD, and it costs the part 0.28 / 0.53 points

**Severity: N/A (an instrument). Status: LANDED and measured.**

`shared/dsp4-logic` gains `DRIVE_ALL=1`, artifact
**`dsp4_logic_driveall.e13b5dec84e0`** (design_id `5dec84e0`, cfg_bits
`0x0020`, fmax 68.13 MHz, sim gate PASS with a new self-checking testbench
`tb_pcm_drive`): the Pi re-framer gains a second launch register that reads
the same de-framed stereo with the slot index forced to `slot[0]`, so all
eight TDM8 slots carry audio, and the top level assigns
`i_dspa = {8{pcm_drive}}`. One stereo stream played by the CM4 therefore
drives all 46 of chip 1's input kernels.

Three properties, and they are the reason it was worth a bitstream:

* **the DSP pays nothing** — the stimulus arrives on the wire, so there is
  no synthesis to net off on either chip;
* **it is runtime-switched** — the silent row and the driven row are the
  same image, the same boot, the same measured clock and the same parameter
  state, and the only difference between them is whether `aplay` is running;
* **every input lane at once**, including codec, MEMS and snake, so all 32
  strips carry full scale and the fabric can be opened up to reach chip 2.

Measured on the part with the stimulus playing: `_buf_C1_XIN_PI_L`,
`_buf_C1_XIN_MEMS` and `_buf_C1_GAIN_01` all `0x0FFFFFFF` (Q4.28 full
scale), `_gate_envelope_C1_GATE_01` `0x0FFFFFF6`.

**Its own cost, measured the way gate 1 asks — the driven-minus-silent delta
on a graph with every dynamics node switched off:**

| arm | chip 1 silent | chip 1 driven | Δ | chip 2 silent | chip 2 driven | Δ |
|---|--:|--:|--:|--:|--:|--:|
| dynamics bypassed | 33.55 % | 33.53 % | **−0.02** | 73.99 % | 74.70 % | **+0.71** |
| dynamics + FX bypassed | 33.27 % | 33.55 % | **+0.28** | 74.17 % | 74.70 % | **+0.53** |

The instrument executes no DSP instruction, so what this measures is the
residue: the graph's remaining signal dependence once every branchy audio
class is off. It is 0.28 points on chip 1 and 0.53 on chip 2 against the
~40 points the dynamics turn out to be worth. It is not the FX engines
(switching them off moves chip 2's driven figure by 0.00); the peak-update
branch in the meters is the open candidate and is not attributed here.

Files: `shared/dsp4-logic/rtl/dsp4_pcm_reframe.v`,
`rtl/dsp4_logic_top.v`, `build.sh`, `sim/tb_pcm_drive.v`;
`MW/D32/DSP/SHARC/drive_audio.sh`, `loadlogic.sh driveall`;
`tools/pi/dsp4_driven_setup.py`.

### S19-2 — chip 1's cost IS signal-dependent, S18-1's chip-1 sentence is withdrawn, and the 113 % was the product

**Severity: HIGH (it changes which chip the window has to fix).
Status: MEASURED. Corrects S18-1.**

S18 wrote that chip 1's cost is signal-independent and that its 113 % in the
driven arm was `DSP4_PROFILE_SIGNAL`'s own square synthesis. Driven from
outside the part, with a stimulus the DSP executes not one instruction for,
**chip 1 reads 113.23 % of budget at D24 on the shipping default with the
shipping routing, and misses 11.6 % of its blocks** — within 0.2 points of
the figure S18 wrote off as instrument.

The evidence S18 reasoned from was real and the inference from it was not.
On its hot boot the signal that reached chip 2's main bus came in over
`XIN_PI → XS_XFER_PI → C2_XR_PI → C2_PI_IN → C2_MIX_MAIN` — the CM4's
playback transfer, which crosses chip 1 as an INPUT_TDM node and an
INTERCHIP_SEND node and touches **no strip, no GATE and no COMPRESSOR**.
Chip 1 was silent on that boot in the only sense that costs it anything, and
`DSP4_PROFILE_SIGNAL`'s synthesis costs it about 0.2 points, not 41.

### S19-3 — the shipping default fits NEITHER chip at D24 under load

**Severity: HIGH. Status: MEASURED, two boots, regime proved on both chips.**

The three-row ladder on one boot (`capacity_run.sh DRIVEN=1`), D24, clock
measured on every row:

| product | chip | A silent, default cfg | B silent, loaded cfg | **C DRIVEN** | blocks missed |
|---|---|--:|--:|--:|--:|
| D24 | 1 | 70.51 / 70.61 % | 76.38 / 76.29 % | **118.89 / 118.92 %** | **15.85 %** |
| D24 | 2 | 89.76 / 89.94 % | 89.94 % | **119.24 / 119.25 %** | **16.05 %** |
| D32 | 1 | 91.68 % | 101.32 / 101.33 % | **158.18 / 158.13 %** | **36.79 %** |
| D32 | 2 | 109.94 / 110.05 % | 110.15 / 109.94 % | **142.80 / 144.16 %** | **30.00 %** |

The signal is worth **+42.5 points on chip 1 and +29.3 on chip 2** at D24
(+56.9 and +32.7 at D32); the configuration — opening every bus assign and
send — is worth +5.9 on chip 1 and +0.2 on chip 2. With the shipping
ROUTING as well as the shipping thresholds (MAIN only, one row, D24) chip 1
still reads **113.23 % with 11.6 % of blocks missed**, so this is not an
artefact of the −60 dB thresholds.

`DIAG_BLK_OVERRUN` is the arbiter and it agrees with the cycles.

### S19-4 — the arbiter could not be read while it was arbitrating

**Severity: MEDIUM (it lost rows, and it lost exactly the rows that matter).
Status: FIXED.**

`dsp4_capacity.py` read `DIAG_BLK_OVERRUN` with `Scope.rd`, the VOTED reader,
which returns only when one value has been seen twice. On an arm that is over
budget the register counts several hundred a second and never repeats, so the
first driven row on chip 1 came back
`register 0xE00A never settled: {0x7: 1, 0x8: 1, … 0x12: 1}` and the row was
lost — for the one reason the row exists to record. `moving()` is no help
either: it discards a zero as a dropped answer, and a healthy arm's overrun
count IS zero. `counter()` accepts three consecutive NON-DECREASING single
asks, which covers a register that is standing still and one that is running.

### S19-5 — `dsp4_capacity.py` could not tell whether it had reset the worst-block latch, because it confirmed a STROBE by reading it back

**Severity: MEDIUM (the worst-block column is the one the budget is quoted
against). Status: FIXED in the tool; the S19 matrix rows were taken before
the fix and their worst-block column is annotated accordingly.**

`Scope.wr` writes a register and then requires it to read back the value
written — correct for a parameter, impossible for `DIAG_CLEAR`, which is a
strobe and does not hold 1. So `wr` raised after eight attempts on every
row of this session and every row recorded `cleared: false`, while the
latch had in fact dropped on most of them (`_proc_cyc_max` came back
smaller than the raw latch read moments before). The flag was wrong in both
directions, which is worse than not having one: the rows where the clear
really WAS dropped — chip 2 holding a 419 %-of-budget pass left over from
the parameter burst, with zero overruns and a full pass count beside it —
looked exactly like the rows where it worked.

The clear is now confirmed by the thing it is for: write the strobe,
ignore the read-back, and require `_proc_cyc_max` to come back smaller than
the latch just read; retried, because a write on this link is dropped under
load exactly as a read is. `proc_cyc_max_after_clear` goes into the JSON.

**For the S19 table this means the decision numbers are `_proc_cyc` and
`DIAG_BLK_OVERRUN`, not the worst block.** They agree with each other to a
tenth of a point: at 118.92 % of budget the loop must miss
1 − 1/1.1892 = 15.9 % of its blocks, and the arbiter counted 15.847 %.

### S19-6 — the record's "silence" was the converters' noise floor

**Severity: LOW (it moves the silent baseline by 1–3 points).
Status: MEASURED.**

On the shipping bitstream the ADC lanes are connected and an open converter
input is not zero: the "silent" boots in the record read five of chip 2's
eighteen limiter envelopes live at `0x0000000C`. On the drive bitstream with
nothing playing, chip 2 reads **0 of 10 compressor, 0 of 4 gate and 0 of 18
limiter envelopes** — actually nothing.

| | chip 1 D24 | chip 2 D24 |
|---|--:|--:|
| the record's "silence" (S17/S18) | 71.65–71.84 % | 92.67–92.84 % |
| TRUE silence | **70.51 %** | **89.76 %** |

### S19-7 — the decision table on driven numbers: the silence table ranked the pairs the wrong way round, and it was not describing the staged pair either

**Severity: HIGH (it is the table PW is holding). Status: REBUILT on driven
numbers — five arms, two products, both chips, two boots, 36 regime
snapshots all PROVEN. Full table in the write-up §3.**

Ranked at silence, the shipping default is the cheapest arm on the board
and `s16_*` looks like a five-point regression. Driven, it is the other way
round and it is not close:

| D24, chip 1 | silent | driven |
|---|--:|--:|
| `blk` (shipping default) | **70.5 %** | 118.9 %, 15.8 % of blocks missed |
| `s16` (dynamics table) | 75.9 % | **82.4 %, zero** |

`s16_*` fits D24 driven on both chips (82.4 % / 94.6 %, zero overruns over
90,049 blocks per chip on each of two boots); `s16f_*` is within 0.7 points of it —
the spread between its own two boots — and buys the six-slot biquad for
nothing measurable; `s18_*` is a bytes lever
and costs 0.7 points driven exactly as silent. **At D32 nothing that was
staged before today fits** — `s16_*` is 109.5 % / 115.5 % driven and misses
blocks at silence too, so D32's problem is static cost, not dynamics. The
one configuration measured that fits D32 under load is `s16_*` plus
`DSP4_STRIP_FUSED=1 DSP4_SIMD_DYN=1` (**71.3 % / 93.9 %, zero overruns**),
and that is blocked on S12-5/S12-7, not on capacity.

**And the S16 table's numbers are not the staged pair's.** S16 records
`s16_*` at 46.8 % / 55.2 % (D24) and 60.3 % / 66.7 % (D32). Rebuilt from
`shipping.config` plus its two switches — which is what the staged pair
carries — it reads 75.9 % / 94.7 % and 99.0 % / 115.3 % at silence. Those
S16 figures belong to an arm that also carries `DSP4_STRIP_FUSED` and
`DSP4_SIMD_DYN` (measured here as `s16sd`: 48.1 % / 62.2 % on chip 1
against S16's 46.8 % / 60.3 %) plus `DSP4_C2_BQ_GRAPH=1` for chip 2's
remainder — the last of which S16's own footnote names.

### S19-8 — S18-7 attributed: three of `goldnode`'s four arms read words the block-kernel graph never writes

**Severity: MEDIUM (a bar that FAILS on the shipping image and cannot say
why is worse than no bar). Status: ATTRIBUTED with the mechanism; not
fixed. Closes the open half of S18-7.**

With a known full-scale signal on strip 1 and the image's own symbol map,
seven of fifteen capture points a strip bar might use read exactly zero:
`_buf_C1_IN_01`, `_buf_C1_FILT_01`, `_buf_C1_EQ_01`, `_buf_C1_TUBE_01`,
`_buf_C1_DLY_01`, `_tap_post_eq_C1_EQ_01`, `_tap_pre_fader_C1_DLY_01`.
The rest carry the signal. Against `dsp4_node_verify.py`'s four arms:
GATE's INPUT is `_buf_C1_EQ_01` (zero), TUBE's OUTPUT is `_buf_C1_TUBE_01`
(zero), FDR's INPUT is `_buf_C1_DLY_01` (zero) — and COMP's two are both
live, which is why COMP is the arm that got far enough to disagree on 70 of
96 samples while the other three could not obtain a usable capture at all.

**The bar is wrong, not the audio**: the signal is demonstrably present at
`_buf_C1_GAIN_01`, `_gate_gain`, `_comp_gain` and `_tap_post_fader`. The
classes whose block kernels keep intermediates in the block pool never
write their per-node one-word scalar — since `DSP4_BLOCK_KERNELS` landed,
which is S12-2's class of defect appearing in a bar for the third time. The
fix is to move the capture layer onto the taps and the pooled buffers.

### S19-9 — `capacity.sh BUILD=0` staged nothing, so it booted whatever the bench happened to have

**Severity: LOW. Status: FIXED.**

The staging block sat entirely inside `if [ "$BUILD" = "1" ]`, so `BUILD=0`
— the mode a re-measurement uses — booted whatever was already at `$STAGE`
under that arm name, with whatever symbol map was beside it. That is the
S10-9 trap with the image and the map free to disagree silently. A build
directory that exists is now staged, image and map together; only a missing
one falls through to what is there, and it says so.

## THE CODE POOL'S REAL LEVER, MEASURED — and chip 2's ten points were never boot-dependent (2026-09-10, session 18)

Session: S17-6 explained; one of the nine 32-copy per-strip kernels made
SHARED on the rig and in the graph, bit-exact and behind a switch; the
decision table for PW on the other eight. Write-up
`MW/D32/DSP/dsp4-s18-20260910.md`. Contract `defs-v2026.09.08.4`,
unchanged; `shipping.config` unchanged. **The default build is
`302d6142` / `3b3a6f8e`, byte for byte the pair S17 left**, from a tree
regenerated by the new generator pass — `DSP4_SHARED_KERNELS` defaults to
0 and at 0 it costs nothing.

### S18-1 — chip 2's D24 cost is SIGNAL-dependent by twenty points, the capacity record is a SILENCE record, and chip 2 does not fit at D24 under load

**Severity: HIGH (the window carries the wrong number for chip 2).
Status: EXPLAINED and MEASURED; the fix is a decision, see S18-6.
Closes S17-6.**

S17 filed, without explaining it, a chip-2 D24 cost that moved ten points
between boots of one image at one measured clock. It is not boot
dependence. `dsp4_c2regime.py` reads 347 chip-2 words on every boot at the
capacity dwell — every crossfade, engagement flag, envelope, mask and the
D71 word — and across six boots of the S17 default build **fifteen words
differ and every one of them is a dynamics ENVELOPE**, all on chip 2's
MAIN / SUB / OCOMP / OLIM chain:

| boot | chip 1 | chip 2 | chip 2 overruns | live envelopes LIM/COMP/GATE |
|---|---|---|---|---|
| b1, b2, b3, b5 | 71.65–71.84 % | 92.67–92.84 % | 0 | 5 / 0 / 0 |
| b6 | 71.65 % | **95.84 %** | 0 | 6 / 5 / 0 |
| b4 | 71.69 % | **103.14 %** | **2.999 %** | 7 / 7 / 1 |

Chip 2's dynamics have a cheap branch below threshold and an expensive one
above it; how many are above it is what the bench happened to be carrying.
Driven deliberately (`DSP4_PROFILE_SIGNAL=1`, three boots):

| | chip 1 | chip 2 | chip 2 overruns |
|---|---|---|---|
| every source driven | 112.99 / 113.04 / 113.03 % | **112.32 / 112.29 / 112.32 %** | **10.92 %** |

Reproducible to 0.03 points. **Chip 1's cost is signal-INDEPENDENT and that
is measured**: on b4 a near-full-scale signal reached chip 2's main bus and
can only have got there through chip 1's strips, and chip 1 still read
71.69 % — inside the silent boots' spread. Chip 1's COMP and GATE call
their gain computer every sample whatever the level. So **chip 1's 113 % in
the driven arm is the instrument** (the square synthesis in its 46 input
kernels) and not a product figure, while **chip 2's is a product figure**
less 0.18 points for the stimulus its own 37 RECV/XR nodes carry (one
instruction per sample per node — the production read is executed and
discarded) — **~112.1 % of budget with its dynamics engaged**, and the
in-graph b4 point (103.1 % at 7 of 18 limiters and 7 of 10 compressors,
with no stimulus at all) sits on the same line.

CONSEQUENCES. (a) **Every `capacity.sh` figure in this tree was taken on a
silent bench and is therefore chip 2's cheap branch.** (b) The D24 chip-2
figure to quote is the loaded one and **D24 does not fit on the shipping
default under load**. (c) S17's procedural conclusion — "`REPS=1` is not a
capacity measurement for chip 2" — is right but understates it: a capacity
arm has to state which branch its dynamics were on, and `capacity.sh` still
does not. (d) The lever is already on the table: S16-6 put the LIMITER on
`DSP4_DYN_LUT` at 253.3 → 92.1 c/sample-pair (−63.6 %) and chip 2 has 18
limiters and 10 compressors.

### S18-2 — one class shared returns 28,800 bytes of chip 1's code pool for 0.64 points of D24 budget, and TUBE with it 9,834 more

**Severity: HIGH (it is the pool's only remaining lever of this size).
Status: LANDED behind `DSP4_SHARED_KERNELS`, default 0.**

85 % of chip 1's code pool is 32 copies of 9 per-strip kernels, and for
eight of the nine the copies are not nearly identical — normalise the node
id and the SIMD pool suffix and all 32 emitted bodies are **the same text,
byte for byte**. `gen_shared_kernels()` re-proves that on every generation
and refuses to share a class whose copies are more than one body.

COMP (32,000 bytes, 13.6 % of the pool) and TUBE (12,480, 5.3 %) are each
emitted ONCE, as `_shk_comp_blk` and `_shk_tube_blk` in
`chip1/shared_kernels.asm`, and entered per strip through a stub that puts
that strip's record base in i7 and its predecessor's scalar buffer in i5. Every `dm(_comp_relq_C1_COMP_07)` becomes `dm(SHK_COMP_OFF_comp_relq,
i7)` — a pre-modify with an immediate, ONE instruction exactly as the
direct access was — because a node's `.var`s are laid out as a contiguous
record (COMP's 32 records are 44 words apart to the word).

Measured, `dsp_codepool.py --diff`, chip 1: each of the 32 COMP objects
**−928 bytes**, `shared_kernels` **+896**, **TOTAL −28,800**; each of the
32 TUBE objects −318, `shared_kernels` +342, **−9,834**; both together
**−38,634**, their sum to the byte. Boot stream 421,836 → 393,036 with COMP
alone and → 383,140 with both. Chip 1's code section goes from **235,064 of 262,144
bytes (89.7 %, 27,080 free) to 206,262 (78.7 %, 55,882 free)** — more than
the whole of the free space it started with. Read S16's "388 bytes of
margin" with its arm: that is the margin with the candidate switches on,
which is where the levers PW is weighing would ship; 28,800 bytes is 74
times it.

Cost, `capacity.sh` with the clock measured on every row, chip 1, zero
overruns on every row: at D24 `_proc_cyc` **71.71 % → 72.35 %** and worst
block 71.88 % → 72.58 %; at D32 **93.54 % → 94.43 %**. The chain skips a
masked strip entirely, so a D24 block runs 24 compressors and a D32 block
32 — **2,097 cycles over 24 nodes and 2,916 over 32, i.e. 87 and 91 cycles
per node per block, ~89.** Chip 2 is unchanged (it has no COMP class).

**The audio is proved by the bars, not by the md5.** `famverify` at 20
families on both chips is **verdict for verdict identical to S16's
shipping-pair run — 0 of 20 differ**, COMPRESSOR LIVE / BIT_EXACT and
TUBE_SAT LIVE / BIT_EXACT; `bqeverify` PASS on both arms; `busgold` GRAPH
BIT-EXACT, 0 of 256 words; `golden_harness` 59/59; `dsp_validate` OK;
`shared_kernel_check` OK on all 32 records of both classes. And by the bar this change needed and the tree did not have
(S18-7): **famverify structurally cannot witness it** — it drives
`C1_COMP_01`, and a shared kernel stuck on strip 1's record is exactly
right for strip 1 — so `shkstrip.sh` writes a DIFFERENT compressor
threshold to each of several strips and reads each strip's own converted
word out of its own record. On the shared arm, strips 1/2/7/16/24 read
`0xFD823098` / `0xFD02A0B4` / `0xFA84D150` / `0xF608C260` / `0xF20C4350` —
**five distinct words, each the model's to the bit and each identical to
the switch-off control's.**

### S18-3 — it is a JUMP, not a call: the graph has paid a call per node per block since block kernels landed

**Severity: MEDIUM (it changes the ROI of every remaining class).
Status: RECORDED.**

The dispatch priced this change as "one CALL per node per block added". No
call is added. `process_chain` has done `call _C1_COMP_07_process` since
`DSP4_BLOCK_KERNELS` landed, so the stub stands where the body used to and
the shared body's own `rts` returns to the chain — the stub ends in an
unconditional `jump`. On this part, measured (D66): a taken unconditional
jump is **+6.02 cycles** and a call/rts pair **+15.04**. The change pays
the cheaper one, and the 65.5 c/node/block it does cost is mostly the
stub's register set-up and the one base load that has to be rebuilt from
the record base inside the sample loop, not the branch.

### S18-4 — `dsp4_buildcfg.py` never learned four of the switches `DIAG_BUILD_CFG2` carries, and reported them as off

**Severity: MEDIUM (a readback that answers confidently about switches it
is not looking at). Status: FIXED.**

`DIAG_BUILD_CFG2` exists because an image has to say what it is in its own
words (S11-1, S12-7). S12 added `DSP4_C2_BQ_GRAPH` to it, S14
`DSP4_BQ_SIMD_PIPE`, S15 `DSP4_DYN_LUT` and `DSP4_GATE_LINTHR` — and
`dsp4_buildcfg.py`, the only thing that reads the word, was never taught
any of them. Its `off2:` line therefore listed the switches it knew about
and said nothing at all about four that change cost and audio, which is the
S12-7 hole reopened one layer down. All four are decoded now, with
`DSP4_BQ_SIMD_PIPE` as the two-bit field it is, and `DSP4_SHARED_KERNELS`
is in the word from this session (bits 5 and 15 — the two that were left).
**A third shared class needs a wider field, and `diag.h` says so at the
point where it would be forgotten.**

### S18-5 — RTG is the biggest class in the pool and it is not shareable as it stands

**Severity: LOW (it is the reason the biggest lever is not first).
Status: RECORDED, with the two things that have to change.**

RTG is 40,256 bytes, 17.2 % of chip 1's pool — bigger than COMP. It is not
the class this session shared, for two measured reasons rather than one
preference. (a) **Its 32 copies are 32 bodies**: they differ in the STRIP
INDEX as well as the node id (`i1 = _xpc + 0` against `_xpc + 16`,
`dm(_rtg_busy + 0)` against `+ 16`), so a shared RTG takes a second
argument that no other class needs. (b) **Its body touches all eight DAG
index registers**, so the register the record base would live in has to be
freed first. `shared_kernel_survey.py` reports both, per class, off the map
and the source.

### S18-6 — the decision table for the other eight classes, and the recommendation

**Severity: N/A (a decision for PW). Status: MEASURED, not estimated —
two classes landed, and the model interpolates between them.**

`tools/dsp/shared_kernel_survey.py` reads the linker map for the bytes, the
generated source for whether a class's copies are one body and how many
addressing sites a rewrite touches, and every library the class calls into
for which DAG registers are actually spare. It prints the table rather than
having one written by hand. See the write-up §4 for the numbers, the
recommendation and what the pool would then hold.

### S18-7 — the change needed a per-STRIP witness, the tree had none, and `goldnode` FAILS on the image that ships

**Severity: MEDIUM (a bar in the "confidently wrong" state, on the shipping
default). Status: the witness WRITTEN; `goldnode`'s own failure FILED, not
fixed.**

Every bar in the tree would have passed a shared kernel that was entered
with strip 1's record base every time: `famverify` drives `C1_COMP_01`,
`golden_harness` is off the part entirely, and the byte count does not
move. So `shkstrip.sh` / `dsp4_shk_perstrip.py` were written — a different
threshold per strip over SPI, each strip's own converted word read back out
of its own record, no signal and no capture needed.

**Its control arm is what made it a bar.** Its first run reported five of
seven strips WRONG on the SWITCH-OFF image `302d6142`, and both reasons
were the witness's own: the model computed the conversion in float64 where
the part does it in float32 (1–3 LSB on four strips), and it asked about
strips 31 and 32 at D24, which the channel mask never calls, so their words
are zero however right the kernel is. Both fixed.

**`goldnode.sh` FAILS on the shipping default and this session did not
cause it.** On the shared arm it reports `NODE VERIFY FAILED: 2 verdicts
against 2 measurable stimuli`; on the switch-off control it reports the
same, and the two logs are **identical except for two counts belonging to
the model's own negative-control prediction** — every word the PART
produced is the same on both arms, which is this change's strongest
witness and `goldnode`'s own indictment. Its COMP model disagrees with the
part on 70 of 96 samples (part −1,046,478,848 against model −319,593,315:
the part is passing through near unity where the model expects heavy gain
reduction), and its GATE, TUBE and FDR arms cannot obtain a usable capture
at all. The chain witnesses it prints are the one-word `_buf_<nid>` scalars
a block-kernel build never writes — S12-2's class, in a bar, again.

## WINDOW-READINESS CORRECTNESS: the sidechain bound closed, D79 root-caused to the recovery that was supposed to help, D80 put on the right axis (2026-09-10, session 17)

Session: the open numeric and verification items closed before PW's window.
Write-up `MW/D32/DSP/dsp4-s17-20260910.md`. Contract `defs-v2026.09.08.4`,
unchanged.

### S17-1 — the headroom guard's own bar had been building the guard OUT of the image since the float landing

**Severity: HIGH (instrument; a bar that cannot fail). Status: FIXED.**

`bqguard.sh` builds with `DSP4_BQ_GUARD=1` and did not name
`DSP4_BQ_FLOAT`. `build.sh` sources `shipping.config` wherever the
environment is silent, so it got `DSP4_BQ_FLOAT=1`, and `dsp_block.h`
answers that with `#undef DSP4_BQ_GUARD / #define DSP4_BQ_GUARD 0` --
correctly, because the float cascade needs none of the guard machinery.
That takes `lib/bq_headroom.asm` out of the build from under
`bq_guard_test.asm`, which references it unconditionally.

It does not silently pass -- it does not LINK, which is how long it has
been since anyone ran it. Rebuilt with the pre-fix flags to check:

```
[Error li1021]  The following symbols referenced in processor 'p0' could not be resolved:
        'bq_hr_poll [_bq_hr_poll]' referenced from '.../lib/bq_guard_test.doj'
        'bq_hr_request_n [_bq_hr_request_n]'
        'bq_hr_service [_bq_hr_service]'
=== Build FAILED (2 errors) ===
```

The float arm landed 2026-09-03, so the guard's bar has been unrunnable
since. `DSP4_BQ_FLOAT=0` is named in the script now: the guard is the FIXED
arm's and the arm has to be stated. `NSAMP` also defaults to 512 instead of
128 -- see S17-2, whose case needs about 270 samples to ring up and at 128
would have reported nothing and read like a pass.

### S17-2 — `dyn_state_bound` §3 is a REAL overflow, an ordinary tone reaches it, and it is fixed for zero bytes

**Severity: MEDIUM (correctness, fixed reference arm only). Status: FIXED,
and the finding is CLOSED.**

The GATE's sidechain HPF+LPF is the one cascade in the tree whose headroom
header nothing ever wrote. It cannot be sized at parameter load and the
reason is structural, not an oversight: the node converts its wire
coefficients on every block and there is no swap-trigger cell to say when
the host moved them, so there is no parameter-LOAD moment to hang a sizing
off. At H = 0 the round-once kernel jumps over both the entry scale and the
exit clamp, and the recursion can wrap -- a sign inversion fed back into the
poles of a level detector.

**It is reachable by an ordinary tone, which is the part that was not
known.** Swept inside the contract (`GateFilterHpf` 20-1000 Hz,
`GateFilterLpf` 500-20000 Hz, `GateFilterQ` 0.1-10) the worst cascade is
HPF 521 Hz over LPF 500 Hz at Q 10 -- an HPF above its LPF, which nobody
dials and a recalled preset can carry -- and there `|h|_1 = 125.01`
(H = 4) and **max|H| = 82.05, +38.3 dB at 510 Hz, against Q4.28's ceiling
of 8.0**. `|h|_1` needs a sign pattern matched to the impulse response;
max|H| needs a sine. The gate rectifies its key before the cascade and a
rectified sine puts 0.424 of full scale at TWICE its fundamental, so the
tone that lands on that resonance is 255 Hz. Through the kernel, 24,000
samples: **205 internal wraps at 0 dBFS, 28 at -12 dBFS, 0 with the
guard.**

MEASURED ON THE PART, not modelled. The corner is a named case in
`gen_bqg_vectors.py` now -- the only one driven by a plain tone rather than
the matched-sign pattern -- and `bqguard.sh` returns: the part's own sizer
picks **H = 4**, the unguarded arm inverts sign **127** times against the
model's predicted 127, the guarded arm **0**, and both whole output streams
hash-match the model bit for bit (`0x4D9CE0A5`/`0x6BE90AD8` guarded,
`0x43A42030`/`0xBDF8432F` unguarded).

FIX: `bq_h_load.GATE_SIDECHAIN_H = 4`, emitted by `dsp_codegen.py` into the
coefficient block's **initialiser** -- `.var _gate_filter_cq_<nid>[11] = 4,
0, ...`. A constant rather than a sized word because the parameters are
contract-bounded, so one number covers every setting the wire can carry; in
the initialiser because the converter already steps past the header and
never writes it, so the fix costs **+0 code bytes and +0 instructions** on a
chip 1 with 388 bytes of margin. The price is four bits of detector
precision: an absolute floor near -126 dBFS, 46 dB below the lowest
threshold the contract allows. §3 re-derives the sweep every run and FAILs
if the constant stops covering it.

**Two corrections to the finding as it stood.** The talkback HPF was counted
with the gate's and should not have been: `_talk_hpf_coeffs_<nid>` has no
entry in the SPI dispatch table -- the only talkback filter cell is
`Talk<nn>Hpf001`, the ON/OFF word -- so the wire cannot reach it, it stays
at its bypass initialiser, `|h|_1 = 1` and H = 0 is correct. And **no
shipping image is exposed at all**: `DSP4_BQ_FLOAT` forces `DSP4_BQ_GUARD`
off, so the sidechain runs the 40-bit software float kernel and has no fixed
recursion to wrap. §3 is the FIXED reference arm's bound -- the arm a future
FPGA fixed engine follows -- and that is where the fix lands.

### S17-3 — D80 root-caused: the meters were read on a steep part of their own convergence curve

**Severity: MEDIUM (instrument; it looked like an arithmetic defect for
thirteen days). Status: CLOSED as an INSTRUMENT ARTEFACT, and the
instrument is fixed.**

D80 recorded a 0.44-0.90 % difference between chip 2's per-sample and
block-kernel builds on the meters of the chains whose GATE and COMP are
engaged, peak low and RMS high, while every node OUTPUT was bit-identical.
Reproduced through every lever since 2026-08-28.

**The two builds were always bit-identical on the meters.** `d80.sh` boots
each arm ONCE and reads the meters at 12, 30, 60, 120, 240, 480 and 720 s
with `DIAG_FRAME_COUNT` and `DIAG_BLK_OVERRUN` bracketing every read. Across
26 probes and 7 captures there are exactly **two** non-zero cross-arm cells
-- `_mtr_rms_C2_MTR_FX_01` +0.1057 % at 12 s and `_mtr_rms_C2_MTR_FX_06`
-0.0135 % at 30 s -- both single-capture, both the size of the boot-to-boot
noise D80 itself recorded (worst 0.198 % on one build booted twice). Every
other cell is 0.0000 at every dwell.

**What moves is the meter, not the arithmetic.** A meter is a per-BLOCK IIR
with a 300 ms RMS window and a 1.333 s peak decay AT BLOCK RATE; under
`DSP4_BLOCK_DECIMATE=32` -- which `c2gold.sh` must use, because neither arm
fits a block period -- those are **9.6 s and 42.7 s of WALL CLOCK**. At the
12 s dwell `c2gold.sh` used:

    _mtr_peak_C2_MTR_MAIN_01   1.30406  0.855027  0.423672  0.116157 ...
    _mtr_rms_C2_MTR_MAIN_01   0.104717  0.114478  0.116084  0.116157 ...
                               12 s      30 s      60 s      120 s (settled)

The peak is a factor of **11.2** from its settled value at 12 s and still a
factor of 3.6 out at 60 s. **The peak comes DOWN while the RMS goes UP**,
which is D80's own "opposite directions so not a gain error" exactly. And
the chains without dynamics behave as reported: AUX and FX peak sits at 0.5
from the first capture -- a +/-0.5 square has no decay to do -- so only
their RMS converges, which is why those chains "agreed exactly". The two
arms boot and configure independently, so their capture instants sit
differently against their own CONFIG_COMMIT, and on that curve a fraction of
a second is worth a per cent.

The "two arms run at different speeds" half of the hypothesis is DISPROVED
and was not needed: both ran at 93.7 graph passes/s with zero new overruns,
so at equal wall clock they had equal pass counts.

FIX: `c2gold.sh`'s `DWELL` derives from `DEC` -- five peak time constants,
`(5 * 1333 * DEC + 999) / 1000`, **214 s** at the default against the 12 s it
used -- so a run at another decimation cannot silently keep a dwell that was
only long enough for this one. The `DEC` comment's claim that "decimation
changes how OFTEN a pass runs, never what one computes... the comparison is
unaffected" is corrected: what it changes is the wall-clock ballistics of
anything that integrates per pass, which is every meter.

**Chip 2's dynamics path can now carry a bit-exactness claim on its meters,
at a settled dwell.** D80's caveat -- "no chip-1-grade bit-exactness is
claimed for chip 2's dynamics path" -- is withdrawn.

### S17-4 — D79 and D71 are the SAME defect, the fix has been shipping since 2026-08-31, and chip 2's sighting was a READ

**Severity: HIGH as filed (a live audio parameter corrupted by a config).
Status: CLOSED. The chip-1 defect is fixed in firmware; the chip-2 half was
never a corrupt parameter.**

The parameter protocol is two words with no framing -- `word0[31:16] =
address`, `word1 = value`. Lose ONE word out of the DSP's receive stream and
the DSP reads the previous transaction's VALUE as the next one's ADDRESS.
Config values are small integers, so `value >> 16` is **zero** for nearly all
of them, and **SPI address 0x0000 is a live audio parameter on both chips**:

    chip 1   0x0000 = _gain_coeff_C1_GAIN_01     reads 0xF0040000 (CFG_COMMIT = 0xF004)
    chip 2   0x0000 = _fdr_level_C2_AUX_FDR_01   reads 0xE0FE0000 (DIAG_NOP  = 0xE0FE)

Both are exactly the words that were reported. **D79's "two faces" are one
defect seen through two dispatch tables**, and a `gainfix.py` for chip 2
would have been a second plaster on one wound.

WHERE THE WORD GOES: `_diag_timer_isr`'s stuck-partial-request recovery
(`diag.asm:721`) discards a word from `SPI2_RFIFO` after three consecutive
1 ms ticks that find the RX FIFO neither empty nor full. It is the **only**
single-word discard in the firmware -- `_spi2_rx_work` drains strictly two,
and only when `RFS` reads FULL, the RFE guard having been removed on
2026-08-22 for this very reason. The host's config burst is 51 back-to-back
transactions at 1 MHz, 32 us a word, so a tick that keeps landing inside the
second word sees "part full" three times running and throws a LIVE word
away. The recovery meant to protect the link is what corrupts the config,
which is why the negative control was always clean: no config write, no
burst, no part-full ticks, no discard.

**AND IT IS ALREADY FIXED.** `DSP4_SPI_PARTIAL_FIX2` arms the recovery only
while `_spi_rx_count` is standing still, and `build.sh` has defaulted it to 1
since **2026-08-31** (session 15, `388bcbd`, *"ship the D71 fix"*). **D71 --
the lost `CONFIG_COMMIT` transaction -- and D79 are the same defect from its
two ends**, and the connection was never made. `diag.h`'s own fallback said
`#define DSP4_SPI_PARTIAL_FIX2 0` while build.sh set 1, and two sessions read
the fallback and believed the feature was off. The fallback is 1 now (so a
source file assembled without build.sh gets shipping behaviour) and
`shipping.config` names the switch. **Neither change moves a byte: the md5 is
identical either way, because build.sh was already passing it.**

MEASURED (`d79.sh`, `tools/pi/dsp4_d79.py`): 12 boot+config cycles per arm,
both chips read after each with TWO AGREEING READS, `DSP4_CFG_WATCH=1` for
the counters. **48 chip-boots, 0 corrupt, 0 unreadable, in BOTH arms.**
`_spi_partial_seen` is 0-10 per boot -- the tick does land on part-full FIFOs
-- but `_spi_partial_fix` is **0 on every boot of both arms**: with the gate
off the dwell counter never reached three consecutive ticks, and with it on it
cannot. The gate is live and not merely compiled in, witnessed by
`_spi_partial_skip`, non-zero only in the gated arm and tracking `seen`.

**Chip 2's sighting was a read artefact.** `0xE0FE0000` is named in `diag.h`
as "the DIAG_NOP request word echoing back", `0xFFFFFFFF` is the link's
no-answer pattern, and the other arm's all-zero answer after a NOP collect is
D74's signature word for word. `c2gold_run.sh`'s `peek()` brackets a value
with two sane `DIAG_MAGIC` reads, which catches a dead link but not a single
mis-phased answer between them -- and on that evidence a whole aux chain, two
meters and six node-output probes, was excluded from the bar. Fixed: the
health read now requires two consecutive agreeing reads and treats
`0xFFFFFFFF` as no answer.

`gainfix.py` stays -- a pre-2026-08-31 image still has the defect, and
`gainsimd.sh` uses its gain-value argument -- but its header now says the
defect is fixed and that a repair reported on a current image is a
REGRESSION, not routine hygiene.

### S17-5 — the latency instrument played into a device with no playback stream, and swallowed the failure

**Severity: HIGH (instrument; it nulled every image including the shipping
control). Status: FIXED, and the 82-sample contract figure is now MEASURED
on the candidate.**

S12-10 recorded `latency.sh` returning the null signature -- offset 14779 on
all 20 reps of both boots, spread 0, coherent 0.0 % -- on the candidate AND
on the staged shipping pair, and attributed it to the bench sitting on the
`dsp4-pcm-slave` overlay where "the capture device exists and returns audio
that is not the DSP's output". The overlay is the right neighbourhood and
the wrong mechanism.

`dsp4_dsp_latency.py` used ONE device name for both `arecord` and `aplay`.
Under `dsp4-pcm-slave` the card exposes the directions SEPARATELY --
`device 0` is `bcm2835-i2s-dir-hifi`, capture only; `device 1` is
`bcm2835-i2s-dit-hifi`, playback only -- so `aplay -D hw:dsp4pcm,0` had no
playback stream to open. The failure was swallowed (`capture_output=True`,
no return-code check) and the run scored a capture with no stimulus in it.

**No reboot was needed and none was taken.** Measured on the bench:
`arecord` on device 0 and `aplay` on device 1 run CONCURRENTLY under the
standing slave overlay. `CAP_DEV` and `PLAY_DEV` are separate now, both
overridable (`DSP4_PCM_CAP` / `DSP4_PCM_PLAY`, or `DSP4_PCM_DEV` for a duplex
overlay), and the playback's return code is checked -- an `aplay` that
cannot open its device exits non-zero in milliseconds, and scoring the
resulting empty capture is a well-formed wrong answer.

The other half of S12-10 was real: the through-DSP arm needs the `_maincap`
CPLD bitstream, and the bench was on the shipping `a1f6672af6c3`
(`dsp4_logic_id.py`: "no reply: nothing in the capture carried the 0xD594
marker"). Loaded for the runs and restored afterwards, IDCODE `0x020a30dd`
re-read both ways.

MEASURED, 20 reps per boot, **coherent fraction 100.0 % on every rep of
every arm** against 0.0 % before:

| arm | median offset | through-DSP |
|---|---|---|
| LOGIC only (`_pisel` CPLD loop) | 14433 | reference |
| `cap_lat16`, `DSP4_TX_EARLY=0` | 14500 | **67 samples** (S11: 66) |
| `cap_lat16e2`, `DSP4_TX_EARLY=2` | 14515 | **82 samples** (S11: 82) |
| S17 tree, shipping defaults, 2 boots | 14516 / 14515 | **83 / 82** |
| `s16_*`, the recommended pair, 2 boots | 14517 / 14514 | **84 / 81** |

S11's control reproduces to within one sample. **The contract figure stands
at 82 samples / 1.708 ms and is no longer carried.** Boot-to-boot spread is
+/-2 samples on a 14,500-sample absolute offset that carries a deliberate
0.3 s pre-roll, which is why only differences are quoted.

BENCH NOTE: S16 staged `s16_*` but not its symbol map, so that arm ran with
the S17 tree's map -- visible in the log as `gainfix.py` reading
`0x0924256C` at what it thinks is `_gain_coeff_C1_GAIN_01`. Nothing in the
measurement uses the map (every cell write goes through the landed
contract's SPI addresses). **Stage `chipN.sym.json` beside every prefixed
pair from now on.**

### S17-6 — `_proc_cyc_max` was latching the config ladder, and chip 1's D24 margin is 28 % and not 15.2 %

**Severity: MEDIUM (a capacity number the window carries). Status: FIXED,
and it corrects S10-8.**

`_proc_cyc_max` is a high-water latch and nothing cleared it, so
`capacity.sh` printed the worst pass since RESET under the caption "the block
the budget has to cover". `DIAG_CLEAR` now zeroes it (it is a latch, which is
the class that register is for; `_diag_ticks` and `_frame_count` stay
untouched as the two free-running rate references), and `dsp4_capacity.py`
reads the latch BEFORE the reset, clears, dwells, and prints both figures --
saying so explicitly if the write did not take.

WITNESSED, D24, block 16, CCLK 983.04 MHz measured, three boots of the S17
default build:

| | `_proc_cyc` | `_proc_cyc_max` RESET | raw latch | overruns |
|---|---|---|---|---|
| chip 1 x3 | 234,276 / 235,119 / 234,768 | **235,478 / 235,825 / 234,984 (71.71-71.97 %)** | 277,735 / 278,087 / 277,743 (**84.76-84.87 %**) | 0 / 135,056 |
| chip 2 | 303,322 (92.57 %) | 304,353 (**92.88 %**) | 1,286,363 (**392.57 %**) | 0 / 135,056 |

**S13-2's "376 % on chip 2 with zero missed blocks" is that raw latch.** The
config ladder's worst pass is 1.29 M cycles -- a one-off burst of parameter
conversions and cascade sizings that no per-block budget has to cover -- and
the steady worst is 304 k.

**S10-8 IS CORRECTED.** It recorded "chip 1's worst block is consistently
18 % higher than `_proc_cyc` (234,267 -> 277,752 = 84.8 %)" and the window's
D24 chip-1 margin was cut to 15.2 % on that basis. **The 18 % was the
configuration transient**: the raw latch here reproduces 277,752 to the digit
(277,743), while over the dwell alone the worst block is **0.1-0.3 %** above
`_proc_cyc`, not 18 %. Chip 1's D24 worst block is **71.71-71.97 %** and the
margin is **28.0-28.3 %**.

SEPARATELY, AND FILED NOT EXPLAINED: chip 2's D24 cost is **boot-dependent by
ten points** on the same image, product and clock -- 92.88 % with zero
overruns on one boot, 102.83 % with 2.49 % of blocks missed on two others,
with `_proc_passes` tracking the shortfall exactly (403,346 against 393,273).
Chip 1 is flat to 0.3 % across the same boots. Nothing on record accounts for
it. What it settles is procedural: **`REPS=1` is not a capacity measurement
for chip 2.**

## THE LAST LINK AND THE NEW WALL: the code pool read by symbol, the audio-domain verdict on the table, and the LIMITER on it (2026-09-10, session S16)

Session: chip 1's code pool opened by measurement rather than by
deletion — the wall turned out to be a PLACEMENT that nothing had chosen
— which made the audio witness fit beside the table arm; the
audio-domain verdict on `DSP4_DYN_LUT` obtained on the part for both the
COMPRESSOR and the LIMITER; the LIMITER put on the same table machinery,
which is where chip 2's cost actually was; and a silent defect found in
S15's own lever. Write-up `MW/D32/DSP/dsp4-s16-20260910.md`. Contract
`defs-v2026.09.08.4`, unchanged; `shipping.config` unchanged. **Built at
the shipping defaults the tree produces `20588957` / `a1509a2a` — which
is NOT S15's `6ebd0807` / `a3582da1`, and the difference is entirely the
link ORDER that S16-1 changes. Every object contributes the same bytes;
see S16-1 for the proof and for why the md5 moved.**

### S16-1 — the code pool has a THIRD tier, hot kernels were landing in it by alphabetical accident, and nothing reported it

**Severity: HIGH (cost, and it invalidated an accounting). Status: FIXED.
Supersedes the "there is nothing behind it" half of S15-8.**

S15-8 recorded chip 1's code pool at 99.9 %, 244 bytes free, and said
"the LDF's overflow tier is the last one; there is nothing behind it".
The first half is right and the second is not. The LDF has carried a
THIRD code tier since 2026-09-09 — `sec_swco_ovf2`, into whatever Block 1
has left after the DM overflow and the DMA buffers — and on the
`DSP4_DYN_LUT` arm it was **already holding 1,598 bytes of code**.

Nothing said so. `dsp_memreport.py` pools code as Block 3 + Block 2 only,
so those bytes were counted against **"DM data + stack"**: an image
reading "code 99.9 %, free 228" was carrying 1,598 more bytes of code
that the report attributed to data.

**WHICH bytes was decided alphabetically.** The linker fills an output
section in command-line order and `build.sh` built that order with
`find | sort`, so the objects that spilled into Block 1 were the ones
whose names sort last. On the LUT arm that was `meter_fx` — the
per-block meter fold and `_gsimd_gain_blk`, the SIMD gain kernel — and
on the same arm plus the scope witness it was **`dyn_simd_fx`, the SIMD
dynamics kernel, the hottest routine in the graph**. Block 1 is the
block the DM overflow and the DMA ping-pong buffers live in, so that code
fetches against DDE traffic every block. The arithmetic was exact; the
fetch was not free; nobody chose it.

Fixed by naming the cold objects and appending them LAST
(`build.sh`'s `DSP4_COLD_OBJS`): the boot and configuration objects
(`sru_config`, `dma_config`, `sport_init`, `sport_config`, `cgu_init`,
`product_config`), the design steps (`afb_design_fx`, `xover_design_fx`,
`geq_design_fx`), and the instrument paths (`diag`, `spi_handler`,
`scope`, `scope_gates`). Everything on that list runs once per boot or
once per parameter move; nothing on it runs per block.

| chip-1 arm | Block 1 code, before | after |
|---|---|---|
| shipping default | 0 | **0** (inert) |
| `DYN_LUT` | `meter_fx`, `xover_design_fx` — 1,598 B | the three design steps — 1,692 B |
| `DYN_LUT` + scope witness | `dyn_simd_fx`, `biquad_fx`, `dyn_lut_fx`, `dyn_fx`, `geq_design_fx`, `meter_fx`, `xover_design_fx` — 7,634 B | boot + config + instrument + design steps — 7,702 B |

**Every per-block kernel is back in Blocks 3 and 2 on every arm.** The
audio is the same instructions at different addresses, and that is
checked rather than argued: `dsp_codepool.py --diff` reports every object
contributing **exactly the same number of code bytes** across the two
link orders, total delta **+0**. The image md5 moves because the
addresses move — default `6ebd0807`/`a3582da1` → `20588957`/`a1509a2a` —
and the bars (`golden_harness` 59/59, `dsp_validate`, `dyn_simd_inline_check`
5/5, `bq_simd_pipe_check` bit-identical, `famverify` 20 families) are
what say the audio did not.

`dsp_memreport.py` now reports the third tier as a tier, with the fetch
cost named, and `tools/dsp/dsp_codepool.py` is new: the pool by object,
by symbol and by node CLASS, across all three tiers.

### S16-2 — the audio witness FITS beside the table arm, and the constraint was never a size

**Severity: HIGH (it was the blocker on the audio verdict). Status: FIXED.
Closes the second half of S15's "what is NOT done".**

`famverify.sh`'s header said its `_scope_tap` witness "does NOT fit
alongside the paired kernels", and S15 recorded that the walk would have
to run with the tap off — which is what left `DSP4_DYN_LUT` with no
audio-domain verdict at all.

With S16-1's placement in force, the arm
`STRIP_FUSED + SIMD_DYN + GATE_LINTHR + DYN_LUT + SCOPE_BLK_TAP` **links
with 8 bytes to spare in Block 2**, puts 7,702 bytes of boot, config,
instrument and design-step code in Block 1, and runs the whole 20-family
walk. The header is corrected in place.

### S16-3 — `dsp4_comp_gr.py` was addressing a pool slot nothing writes, and its refusal had a mechanism

**Severity: HIGH (instrument). Status: FIXED.**

S15 ran `dsp4_comp_gr.py` against the LUT arm, got *"NOT COMPRESSING
(< 1 dB of reduction)"* with a settled value of **0**, and recorded the
cause as "a capacity arm has no signal source". It has one — the scope
IS the signal source — and the address was the defect. Three things were
wrong at once:

* the slot stride was hard-coded at **32 words** while the block has been
  **16** since the kernel rewrite, so `slot * 32` named slot 2;
* under `DSP4_SIMD_DYN` the ODD strip of each pair runs on a SECOND pool,
  `_blk_pool1`, so strip 1's chain is not in `_blk_pool` at all;
* and slot 1 is the chain's ping-pong B, which TUBE and DLY overwrite
  after the compressor has written it.

It now takes the capture point the way `famverify` does — the node's
IDENTITY (`_buf_C1_COMP_01`) through `_scope_tap`, which copies that
node's real block wherever the generator put it — and refuses, naming
`DSP4_SCOPE_BLK_TAP`, on an image with no block witness.

### S16-4 — the reference model did not know which GATE arm it was reading, and scored the part's correct word as a MISMATCH

**Severity: HIGH (a false failure on a shipping candidate). Status: FIXED.**

On the `DSP4_GATE_LINTHR` arm `dsp4_node_verify.py` reported

```
cvt gate threshold -> Q6.25 log2    2684355 / -222930816  <-- MISMATCH
1 converted parameter(s) do NOT match the model — the sample path below
would be measuring the wrong coefficients, so it is not run for this node
```

and threw the whole GATE verdict away. **The part was right.**
`DSP4_GATE_LINTHR` holds `2^thr` in Q4.28 where the log arm holds `thr`
in Q6.25, and 2,684,355 is exactly `exp2_q(gate_thr_q(-40))`. The model
knew one arm and the image was the other.

`fixed_ref` gained `gate_thr_lin_q`, `gate_step_lin` and
`gate_step_lin_nohold` — the last so the negative control differs from
the model in ONE thing (the hold) and not in two — and
`dsp4_node_verify.py` now ASKS THE IMAGE which arm it is, from
`DIAG_BUILD_CFG2` bit 11, once per run. On the part after the fix: all
three converted parameters match bit for bit, and the GATE's numeric
verdict class is the same `NO_STIMULUS` the shipping arm returns.

### S16-5 — THE LAST LINK: the table's gain reaches the audio, measured on the part

**Severity: HIGH (it is the session's headline). Status: PROVED.**

S15 named this as the thing it had not done. Four instruments, all on the
part, all able to fail:

1. **`famverify`, verdict for verdict against the shipping pair.** Twenty
   families, same bench, same walk, tap on: every verdict identical
   except `COMPRESSOR` numeric, `BIT_EXACT` → `FAILED`, which is what a
   working table looks like against a polynomial reference.
2. **How far that "FAILED" is.** `dsp4_node_verify.py` now reports the
   worst deviation in dB, not just a count: **0.00518 dB** over 96
   samples, against the table's own 0.0950 dB design bound and PW's
   0.1 dB bar. All six converted parameters match bit for bit.
3. **`dsp4_comp_gr.py` with a signal source.** **−20.98 dB of gain
   reduction** on a −6.02 dBFS step at threshold −30 dB, ratio 8:1 —
   against a static-law prediction of −20.982 dB, i.e. **0.0003 dB**.
   Sample for sample against the polynomial arm through the same
   injection: 43 of 64 bit-identical, worst **0.00175 dB** in the attack,
   and the settled value **bit-identical on both arms** (11,986,899).
4. **The LIMITER, the same way** (S16-6): worst **0.00214 dB** through
   the attack, bit-identical once settled.

**THE LUT'S GAIN REACHES THE AUDIO UNCHANGED — YES.**

### S16-6 — the LIMITER on the table, and it is the biggest single prize in the tree

**Severity: HIGH (cost). Status: LANDED behind `DSP4_DYN_LUT`.**

S14-4 measured 162 of `_lim_pair_blk`'s 251 instructions per sample-pair
as log2 + exp2 — 65 %, the highest share of any body, because the limiter
has no makeup and no parallel blend to dilute its gain computer. S15
left it on the polynomial and chip 2 therefore sat at 76.6 %.

It is now on the same `dyn_lut.h` machinery the compressor uses: the node
template's three declarations and design-step call, the LUT loop in
`_lim_pair_blk`, and the pair driver's table pointers. No new arithmetic
— `_lim_cgp_` is already a `_compgain_fx` parameter block (threshold,
slope `0x7FFFFFFF`, hard knee).

| measurement | result |
|---|--:|
| `dyn_lut_design.py --sweep`, LIMITER over its contract range −30..0 dB | **0.0604 dB** worst, bar 0.1 dB — PASS |
| `dsp4_dyn_lut_check.py` on `C2_AUX_LIM_01` | **337 of 337 words identical** to the host model |
| `dyn_shootout` rung 18 → 19, on the part | 253.3 → **92.1 c/sample-pair**, **−161.1, −63.6 %** |
| `dyn_state_bound.py` §5, LIMITER corners with the node's own slope word | every table word inside [0, 1] in Q4.28 |
| audio, `dsp4_dyn_lut_audio.py` | **0.00214 dB** worst against the polynomial |

The shootout's 161.1 c/sample-pair confirms S14-4's 162 instructions
almost exactly, and it is the **largest fractional saving on the whole
ladder** — against the compressor body's 56.7 % and the gate's 54.2 %.

### S16-7 — `_dlut_live` was never written on chip 2, so S15's lever was INERT there and read as "chip 2 barely moves"

**Severity: HIGH (a silent no-op that had already been recorded as a
measurement). Status: FIXED.**

`_comp_pair_blk` branches on `_dlut_live` once per block before its
sample loop. Chip 1's pair driver writes it. **Chip 2's did not** — the
generator emitted no such block for `_c2_dyn_driver` at all — so the flag
sat at its initialiser, every chip-2 pair took the polynomial loop, and
`DSP4_DYN_LUT` did nothing on chip 2 whatever.

It cost nothing and it looked measured. S15 recorded chip 2 moving
76.07 % → 76.55 % across the switch, which is noise, and wrote it up as
"chip 2 barely moves — its 18 LIMITERs are not on the table yet". The
limiters were half the reason; **the other half is that chip 2's ten
compressors were not on the table either, and nothing in the tree could
have said so** — the flag has no reader on the host side and the switch
reads back as ON in `DIAG_BUILD_CFG2` regardless.

`dsp_codegen.py::_emit_lut_pair` now emits the pair's two table bases and
its one live flag for both `comp` and `lim`, on the family pairs and on
the cross-chain pairs. With it, chip 2 at D32 goes **76.66 / 76.77 % →
66.72 / 66.55 %** — ten points — and the size of the move is itself the
proof the flag is now being written.

The predicted move is 9 limiter pairs + 5 compressor pairs × 15 samples ×
161 c/sample-pair = 33,839 cycles = **10.33 % of the block**, against a
measured **9.83 %**: 95 %, with the shortfall accounted for by the
sample-0 scalar path each pair runs.

### S16-8 — the sidechain's H = 5 was a bound over settings the WIRE CANNOT CARRY; within the contract it is H = 4, and the finding stands

**Severity: MEDIUM (a bound, over-stated by one bit). Status: sweep
FIXED, underlying finding FILED and still OPEN.**

`dyn_state_bound.py` §3 had returned FAIL at HEAD since before S15, with
its worst corner at an HPF of **8 kHz**. The defs do not allow an HPF of
8 kHz: `Chan001GateFilterHpf001` is `0=20/64=1000/[Log]` and
`Chan001GateFilterLpf001` is `0=500/127=20000/[Log]` — two DIFFERENT
ranges, overlapping only between 500 Hz and 1 kHz — and the section swept
both over one grid that ran to 18 kHz.

The sweep now takes its ranges FROM the landed CSV. Re-derived inside the
contract the worst cascade bound is **125.01 at HPF 521 Hz, LPF 500 Hz,
Q 10 → H = 4**, not 5.

**The finding is not dismissed by this.** H = 4 is still reachable, the
corner is still one the wire can carry (an HPF above the LPF is a
recallable preset, not a dialled setting), and the gate and talkback
sidechain blocks are still left at H = 0. The mechanism and the fix are
unchanged and are stated in the tool: those two classes call
`_bq_fx_convert_N` on every invocation rather than once per parameter
change, so there is no parameter-load moment to hang a control-rate
sizing off. §3 still returns FAIL, deliberately.

### S16-9 — `~/dspboot/chip{1,2}.ldr` is the shared SCRATCH SLOT, not a staged pair, and S15-10's alarm was pointed at the wrong thing

**Severity: LOW (bench hygiene). Status: the false claim FIXED; the
script sweep NOT done and scoped here.**

S15-10 recorded that ten measurement scripts scp over
`~/dspboot/chip{1,2}.ldr` while `famverify.sh`'s header calls those "the
window pair", and said both cannot be true. **Checked on the part:** those
two files were `08d0b9a4` / `6a349c13`, which is **no staged pair at
all** — it is whatever the last measurement run left there. The staged
pairs are the PREFIXED ones (`blk_*`, `cand_*`, `geq_*`, `dyn_*`,
`flr_*`, `conf_*`, `ship_*`, `tx_*`, and now `s16_*` / `s16f_*`), and
every one of them was intact.

So the header was wrong, not the scripts, and it is corrected. Two
corrections to S15-10 while it is being closed: the count is **about
thirty** scripts, not ten, and what protects the artifacts is the prefix
while what protects two concurrent runs from each other is
`bench_lock.sh`. Making all thirty STAGE-aware (the pattern
`capacity.sh` and `famverify.sh` already carry) is a mechanical sweep
that was NOT done this session — it cannot be verified on the bench in
one sitting and nothing is at risk while it is outstanding.

### S16-10 — a table-vs-polynomial capture cannot be trusted unless the design step is shown to have been STALE, and the cursor must be read at the right instant

**Severity: MEDIUM (instrument discipline). Status: FIXED, and it changed
a PASS into a refusal and then back into a real measurement.**

`famverify`'s audio arm moves a cell and asks whether the samples moved.
For a `DSP4_DYN_LUT` node that is the wrong gesture: the cell it moves is
the THRESHOLD, the threshold IS the curve, and a moved curve restarts the
design step — so the capture runs the exact polynomial. That is why the
LIMITER family's audio record is **bit-identical** on the shipping arm
and on the table arm, and why that identity is the design working rather
than the table being absent.

`tools/pi/dsp4_dyn_lut_audio.py` is the instrument that can see it: two
captures around the design step, the first with the table stale and the
second with it designed. Getting a verdict out of it took three
corrections, each of which is the point:

* it printed **`0.00000 dB PASS`** while BOTH captures ran on the table —
  a comparison that cannot fail — and now refuses;
* the refusal then fired on runs whose samples WERE the polynomial's,
  because the cursor was read after the SPI readback. The buffer fills at
  the audio rate (1,024 samples = 21 ms) and the readback takes hundreds
  of milliseconds; what decides the arithmetic in the window is where the
  cursor stood when the window FILLED, which is the instant `wait()`
  returns. It is read there now;
* and `DYN_LUT_CHUNK` is overridable so the stale window can be widened
  past the buffer (`-DDYN_LUT_CHUNK=1` → 337 blocks = 112 ms). 4 still
  ships.

With all three, on the part: cursor **230 of 337 when the window filled**
— the whole window provably polynomial — and the LIMITER reads
**0.00214 dB** worst through the attack, bit-identical once settled.

## THE DYNAMICS INTEGRATION: the clock settled by measurement, the table's home settled by measurement, and the level→gain table in the generator (2026-09-10, session S15)

Session: CCLK settled independently of the decode that quoted it (S14-7
closed), the level→gain table's home measured L2 against DM, the table
and its design step landed in the generator behind `DSP4_DYN_LUT`, the
paired `DSP4_GATE_LINTHR` port landed behind its own switch with the
`#error` lifted, and two of S14's design conclusions overturned by
measurement. Write-up `MW/D32/DSP/dsp4-dynlut-20260910.md`. Contract
`defs-v2026.09.08.4`, unchanged; `shipping.config` unchanged. **Built at
the shipping defaults the tree produces `6ebd0807` / `a3582da1`, byte for
byte what the pre-S15 tree produces — every switch in this session is
inert at its default and that is proved by a build, not argued.**

### S15-1 — the pair on the part was running at HALF CLOCK, because it had never been configured

**Severity: HIGH (bench state, and the instrument). Status: CLOSED. Closes S14-7.**

At the start of the session the shipping pair on the bench, with
`matrix-app` active and having been up seven hours, read **CGU0_CTL
0x00002800 — the CGU RESET row — and a diag tick of 499.995/s against a
`DIAG_TPERIOD` of 983,040, i.e. CCLK 491.52 MHz, exactly half** the clock
its own budget is quoted at. `DIAG_BLK_OVERRUN` was advancing one for one
with `DIAG_FRAME_COUNT`: it was missing essentially every block.

`DIAG_BUILD_CFG` read `0xCF45FF10`, whose bits 18:17 say the image was
*built* with `DSP4_CCLK_TARGET=983`. So the image asked and the part did
not do it.

**The cause is in the same register block that reported it: `BOOT_STAGE`
read 5 — `DIAG_STAGE_WAITCFG`, "interrupts on, waiting for host config".**
`_cgu_raise_cclk` is called from `_product_config_commit` and nowhere
else, deliberately (D10's objection was to relocking the PLL with the
boot kernel's SPI transfer still in flight). **A part that was never
configured runs on the CGU reset divisors**, at half the clock, with a
graph that cannot fit in half a budget.

Neither the firmware nor the app is at fault. The same staged `blk_*`
images (`ac65ad38` / `e5dce9e4`) booted through `dsp4_boot.py` +
`dsp4_config.py` came up at `0x00005000` and 983.04 MHz on both chips,
and so did `systemctl restart matrix-app` — after which chip 1 read
**0.00 % overruns over 60,014 blocks**. (Chip 2 read 2.49 % on the same
arm; that is a separate question, recorded and not chased here.)

**"Bench restored: shipping pair booted" does not distinguish a booted
part from a running one**, and this is the second time in this project's
record that a number was taken against a clock nobody had measured
(S9-1 was the first).

**The instrument is fixed, permanently.** `tools/pi/dsp4_capacity.py` now
measures CCLK on **every** capacity row: `DIAG_TICKS` across its own
dwell, with the TPERIOD the image was built with read out of
`DIAG_BUILD_CFG`'s bits 18:17, timed against the host clock with each
read bracketed and mid-pointed. It reports the measurement beside the
decode, **derives the budget from the measurement**, and prints an
explicit disagreement line when the two differ by more than 2 %.

### S15-2 — CCLK is 983 MHz, settled two ways, and every percentage in the record stands

**Severity: MEDIUM (the record). Status: CLOSED.**

Two measurements that share nothing, on a booted and configured pair.

**(a) The CGU registers decoded by hand** from the HRM's formula, with
SYS_CLKIN0 = 24.576 MHz: `CGU0_CTL 0x00005000` → MSEL = 80 (bits 14:8),
DF = 0; `CGU0_DIV 0x451442C1` → CSEL = 1;
fPLLCLK = CLKIN × MSEL / (2 × (DF+1)) = **983.040 MHz**, fCCLK = fPLLCLK
/ CSEL = **983.040 MHz**. The decode is checked rather than trusted: the
same three lines reproduce all three rows of `cgu_init.asm`'s own table
(`0x2800` → 491.520, `0x4000` → 786.432, `0x5000` → 983.040), which is
what fixes MSEL at bits 14:8 and puts the PLL's fixed /2 *inside*
fPLLCLK.

**(b) The core timer against two wall clocks that are not the DSP's.**
TCOUNT decrements once per CCLK by construction and reloads from TPERIOD,
so `DIAG_TICKS` advances at CCLK / TPERIOD Hz with nothing in the chain
reading the CGU. Against the Pi's crystal: **983.03 / 983.01 MHz**.
Against the CPLD's 48 kHz audio transport (ticks per block × 3000
blocks/s): **983.04 / 983.02 MHz**. On the capacity arms themselves the
instrument reads **983,037,269 Hz on chip 1 (3 ppm) and 983,025,072 on
chip 2 (15 ppm)** against a decode of 983,040,000.

**`capacity.sh`'s decode is right. The budget is 327,680 cycles per
block. No percentage in the record moves and the D32 fit survives.**

### S15-3 — the level→gain table's HOME is DM, and S14's premise that only L2 could hold it was wrong

**Severity: MEDIUM (design). Status: CLOSED.**

S14 recorded that 96 dynamics nodes × their own table "would have to go
to L2" and that an L2 gather was therefore the first thing to settle.
Both halves were tested and the first half is wrong.

**The linker map says DM.** At the shipping configuration
`dsp_memreport.py` reports **123,852 free bytes of DM on chip 1 and
145,788 on chip 2**, against 337 words × 32 nodes = 43,136 bytes on chip
1 and × 28 = 37,744 on chip 2. Measured on the built arm, DM lands at
**79.6 % with 76,438 free** on chip 1. The 1,024-word overflow
`dyn_tables_fx.asm` records was **`sec_stak`**, a different pool from
`sec_dmda` and its overflow tier; reading it as a DM-wide limit is what
put L2 in the design.

**And the rig measured what L2 would have cost anyway** (four new rungs
on `dyn_shootout.asm`, cycles per sample for a pair of channels):

| | c/s-pair | c/s/chan |
|---|--:|--:|
| the gain computer today, 6-term polynomials | 215.2 | 107.6 |
| **the level→gain LUT, table in DM** | **54.1** | **27.0** |
| the same, table in L2 | 76.1 | 38.1 |
| the whole COMPRESSOR body, today | 284.3 | 142.2 |
| **the same, LUT with a DM table** | **123.1** | **61.6** |
| the same, LUT with an L2 table | 146.2 | 73.1 |

**L2 costs +22.1 c/sample-pair on the gain computer (+40.9 %) and +23.0
on the whole compressor body (+18.7 %)** — not prohibitive, but not free.
**And PAGING a table from L2 into a DM slot is worse than gathering from
L2 directly for any table over 32 words**: the copy measures 11.5 cycles
a word, so a 337-word page is 3,876 cycles a block against the 354 the
direct L2 gather costs over the same block. The break-even is 32 words
and the smallest table that clears the accuracy bar is ten times that.

### S15-4 — the S14 rig's interpolation fraction was SIGN-EXTENDED, and a cycle rig is blind to that by construction

**Severity: HIGH (arithmetic). Status: FIXED.**

`LUT_INDEX_SIMD` took the interpolation fraction as `r4 = lshift r3 by K`
where r3 is the mantissa fraction in Q0.31. Shifting left by K to discard
the K bits already spent on the sub-index pushes what is left **into bit
31**, and the interpolation multiply is `mrf = r5 * r4 (ssi)` — signed.
**A fraction of 0.75 arrives as −0.25 and the interpolation runs
backwards out of its cell.**

Measured by `tools/dsp/dyn_lut_design.py`, which computes the index bit
for bit the way the kernel does, at K = 4 on the shipped compressor
defaults: **0.389 dB with the fault, 0.005 dB with the mask.**

The tell was the shape, not the size: **the error halved with each
doubling of the point count — first order — where linear interpolation of
a smooth function is second order. An error that improves at the wrong
rate is an arithmetic fault, not a mesh that is too coarse.**

**It could not have shown in S14, and the rig's own header says why:**
*the table's contents do not change the instruction stream*. A cycle
measurement is blind to what the table returns, so S14 measured the right
cycles for the wrong arithmetic and modelled the error separately against
what the comment said the kernel did. **The lesson is general: a rig that
measures cycles for a data-driven kernel must have its arithmetic checked
by a second instrument, or its cycles are for a kernel that was never
run.**

The fix is two instructions. With the high clamp a table that no longer
spans all 32 octaves also needs, the corrected paired gain computer is
**54.1 c/sample-pair against S14's 49.1** — four instructions, and that
is the whole of the difference.

### S15-5 — the point count is K = 4 / 337 words, and the GATE is confirmed untabelable independently

**Severity: MEDIUM (design). Status: CLOSED.**

`dyn_lut_design.py` builds the table on the kernel's own grid and sweeps
the result against `fixed_ref.comp_gain`. At the shipped defaults, worst
error over 0 to −100 dBFS: K = 2 (85 words) COMP 0.045 / LIM 0.247 dB;
K = 3 (169) 0.011 / 0.028; **K = 4 (337) 0.004 / 0.025**; K = 5 (673)
0.001 / 0.018.

**The defaults are not the bar.** Over the full documented parameter
sweep — 81 sets, thresholds to −60 dB, ratios to 100:1, knees 0/6/18 dB —
**K = 3 FAILS at 0.135 dB** (the limiter at a −3 dB threshold, whose
infinite ratio and hard knee is the sharpest corner in the family) and
**K = 4 PASSES at 0.0950 dB** against PW's 0.1 dB ruling. S14's model
predicted 0.030 dB at K = 3 with anchored knots; the measurement does
not support it. **K = 4 is the shipped value and the margin is 5 %**;
K = 5 halves the error again for 673 words and still fits DM.

**The GATE reproduces S14-3 from an independent instrument: 41–65 dB of
error at every mesh from 4 to 64 points per octave.** A step
interpolates to a ramp whatever the mesh. Its lever is the linear-domain
threshold and not a table.

### S15-6 — the two-table blend does not work, and the ramp path is the polynomial

**Severity: MEDIUM (design). Status: CLOSED, S14's proposal withdrawn.**

S14 proposed blending two designed tables while a parameter ramps,
because the design step is ~211 instructions per point and cannot run per
block. The rig priced the blend at **+49.1 c/sample-pair**, which looks
affordable. `dyn_lut_design.py --blend` priced its **error**, against a
0.1 dB bar: a −20 → −10 dB threshold ramp reads **1.13 dB**, −40 → −20
**3.12 dB**, −60 → −3 **20.20 dB**, where the same table designed at the
intermediate threshold reads 0.011 dB.

The reason is structural and is the same one that kills the gate: **two
gain curves whose KNEES sit at different levels do not interpolate into
the curve whose knee is between them.** The blend is exact at both ends
and wrong in the middle — which is what every plausible-looking
interpolation of a family of kinked curves does.

**What ships instead costs nothing and is exact.** A node whose converted
parameters have moved restarts its design and **runs the polynomial gain
computer — the path that ships today — until the table is finished**, 16
points a block (~3,400 cycles, 1.0 % of a block), 22 blocks / 7.3 ms for
a whole table. The table is the steady-state path; the ramp path is
unchanged and exactly correct; there is no second table. The changeover
is at a block boundary between two curves that agree to 0.004 dB.

### S15-7 — the paired GATE runs on the linear threshold: the `#error` lifted, 54 % of the gate body

**Severity: MEDIUM (capacity). Status: LANDED behind `DSP4_GATE_LINTHR`.**

`dsp_codegen.py` emitted an `#error` refusing `DSP4_GATE_LINTHR` beside
`DSP4_SIMD_DYN`, because the two are different arithmetic. The objection
was real; **the difference is a threshold shift of at most 0.0002 dB** —
both directions go through polynomials whose worst error over 0 to
−100 dBFS is 0.0001 dB — which was worth refusing against a 0.0001 dB
spec and is **1/500th of PW's 0.1 dB ruling of 2026-09-09**.

**What makes it safe is that one word means one thing.** Under the
switch, `_gate_thrq_<nid>` holds **2^thr in Q4.28 — linear — in every
path**: the per-sample body, the block kernel and the pair kernel all
convert it from the float parameter once per block and all compare the
envelope against it directly. There is no path in which one of them reads
a log value out of that word, which was the only way the two arithmetics
could have met.

The paired GATE then loses the whole of `LOG2Q_SIMD` and its log2(0)
guard — 73 instructions to produce a number used for one comparison:
**142.1 → 65.0 cycles per sample-pair, 71.1 → 32.5 per sample per
channel, 54.2 %.** It costs **480 bytes** of chip-1 code.

### S15-8 — chip 1's CODE POOL, not DM and not cycles, is the binding resource for the dynamics integration

**Severity: HIGH (feasibility). Status: OPEN, named for PW.**

Chip 1, `dsp_memreport.py`, the same arm plus one switch at a time:

| arm | code (VISA SW) | free | DM free |
|---|--:|--:|--:|
| S14's row (`STRIP_FUSED`+`SIMD_DYN`+`C2_BQ_GRAPH`+`PIPE=2`) | 257,322 | **4,822** | 122,156 |
| + `DSP4_GATE_LINTHR=1` | 257,802 | 4,342 | 122,156 |
| + `DSP4_DYN_LUT=1` | 261,900 | **244** | 76,438 |

**Chip 1's code pool was already at 98.2 % before this session touched
it** — the pairing and fusion arm is what fills it — and the LDF's
overflow tier is the last one; there is nothing behind it. The
level→gain table costs **4,098 bytes of code and 45,718 of DM** and
**links with 244 bytes to spare, which is not shippable margin.** Chip 2
is untroubled either way (54.6 % code, 73.0 % DM).

Factoring the design step into one shared routine was worth 178 bytes;
the first build, with it inlined per node, linked with **66 bytes** free.
The remainder is the per-node call sites, and the lever is the same
per-node inlining that S13 and S14 bought cycles with. **The LUT cannot
ship on chip 1 until the code pool has relief.**

### S15-9 — `DIAG_BUILD_CFG2` now carries the four switches it could not see

**Severity: MEDIUM (instrument). Status: FIXED. Closes S12-7.**

S12-7 recorded that `DSP4_C2_BQ_GRAPH` was not in `DIAG_BUILD_CFG2`, so
the two S12 candidate images **read back the same word and differed in
audio** — one of them silently inert on paired AUX GEQ and AFB. S14 added
`DSP4_BQ_SIMD_PIPE`, worth 5.6 points of chip 2, and it was not in the
word either.

All four are in it now — `DSP4_BQ_SIMD_PIPE` (bits 14:13),
`DSP4_C2_BQ_GRAPH` (12), `DSP4_GATE_LINTHR` (11), `DSP4_DYN_LUT` (10) —
and at the shipping defaults all four are zero, so the word is unchanged
and `check_shipping_config.sh` still reads `0xC2010244`.

### S15-10 — ten measurement scripts still write over `~/dspboot/chip{1,2}.ldr`, which one script's header calls a staged pair

**Severity: LOW (bench hygiene). Status: OPEN, recorded not fixed.**

S10-7 established that a measurement arm runs from its OWN staging path
and never `~/dspboot`, because that directory holds the pairs the window
rolls back to. `capacity.sh` obeys it (`/home/app/dspcap/$ARM`) and
`famverify.sh` was fixed to obey it, its header saying why: *"this script
used to scp its build straight over chip1.ldr and chip2.ldr, which are
two of them. A measurement bar must not be able to destroy the artifact
the product ships."*

**Ten scripts still do exactly that**, `dynshoot.sh` among them —
`bisect.sh`, `bootchar.sh`, `cfgstress.sh`, `strips.sh`, `dynst.sh`,
`profile.sh`, `readvote.sh`, `sigprofile.sh`, `sigstrips.sh`. Running
`dynshoot.sh` this session (as S14 did) left `~/dspboot/chip1.ldr` /
`chip2.ldr` holding the `dyn_shootout` rig image `08d0b9a4` / `6a349c13`.

The three NAMED pairs are untouched and byte-identical to the S14 record
(`blk_*` `ac65ad38`/`e5dce9e4`, `cand_*` `fcebc2e1`/`86662b92`, `geq_*`
`df6b847d`/`cb9bc58e`), so nothing that matters was lost. But
`famverify.sh`'s header still lists `chip*` as *"the window pair"* among
the staged artifacts, and ten scripts treat it as scratch. **Both cannot
be true**, and the record should say which — either `chip*.ldr` is
scratch and that header line is wrong, or it is a staged pair and ten
scripts need `capacity.sh`'s `STAGE` treatment.


### S15-11 — the table's top GUARD entry overflowed to unity, and the instrument built to look for it found it

**Severity: MEDIUM (arithmetic). Status: FIXED, in the kernel and in the model.**

`tools/pi/dsp4_dyn_lut_check.py` reads a node's designed table off the
part and diffs it word for word against `dyn_lut_design.py`'s model. On
`C1_COMP_01` at the shipped defaults it read **336 of 337 words
identical** — the design step, the grid and the curve agree exactly — and
**one mismatch, at index 336**, which is the table's last word.

That word is the GUARD the interpolation reads as `T[i+1]` for the last
real cell. Its grid point is octave `DYN_LUT_OCTHI + 1 = 31`, whose
envelope is `1 << 31` — **outside a signed 32-bit word**. On the part it
arrives NEGATIVE, `_compgain_fx` takes its `x_abs <= 0` path and returns
**unity**, so the top cell would interpolate from a heavily reduced gain
back UP to unity between +17.8 and +18.1 dBFS. The host model, in
Python's unbounded integers, computed the honest gain for 8.0 and so
disagreed.

Both are now clamped to Q4.28's largest positive value, which is the
right value in both places: four instructions once per table point in
`_dyn_lut_fill`, and a `min()` in `grid_env`.

**The point is not the size of the defect — it is above full scale and
would be reached only by an envelope 18 dB over 0 dBFS — it is that
nothing else in the tree could have found it.** The cycle rig is blind to
table contents (S15-4), the error sweep runs over 0 to −100 dBFS and
never looks above full scale, and `famverify` asks whether a family is
live and not what its curve does at +18 dBFS. **A word-for-word diff
between the part and the model is a different instrument from all three,
and this is what it is for.**


### S15-12 — the design step's PEAK is invisible to a capacity average, and at CHUNK=16 it went over budget

**Severity: MEDIUM (capacity). Status: FIXED (`DYN_LUT_CHUNK` 16 -> 4).**

Every node's design key starts unmatched, so **at the first
`CONFIG_COMMIT` all thirty-two of chip 1's compressors restart their
design in the same block.** One point is a whole `_compgain_fx`, about
211 instructions, so at `DYN_LUT_CHUNK = 16` the burst is
32 x 16 x 211 = ~108,000 cycles on top of the graph — **a third of a
block** — for the 22 blocks it takes to fill.

**`capacity.sh` cannot see it.** Its overrun figure is a DELTA across a
dwell that begins *after* the boot and config ladder, and the burst is
inside that ladder. `_proc_cyc_max` can, because nothing resets it:

| `DYN_LUT_CHUNK` | chip 1 avg | chip 1 `_proc_cyc_max` | blocks to fill |
|---|--:|--:|--:|
| 16 | 60.27 / 60.45 % | **124.06 %** — over budget | 22 (7.3 ms) |
| **4** | 60.26 / 60.49 % | **96.93 / 97.04 %** | 85 (28 ms) |

The average is unchanged and the worst block drops below budget. 28 ms
of the exact polynomial after a parameter move is inaudible and is the
arithmetic that ships today.

**This is the one place where `_proc_cyc_max` — which S13-2 correctly
distrusts, because it latches configuration transients and read 376 % on
arms with zero missed blocks — is measuring exactly the transient it is
being asked about.** A register is not trustworthy or untrustworthy in
the abstract; it depends what the question is.


## THE ORDER DEFECT: root-caused in the transmit path and fixed, and a capacity defect underneath it (2026-09-09, session 34)

Session: the chip-2 transmit path instrumented with a block counter on
the wire, the ORDER DEFECT root-caused to a ping/pong PHASE error and
fixed (100.0000 % ordered on the part), and a second, independent defect
uncovered by the same instrument — the block loop does not fit its
budget. Write-up `MW/D32/DSP/dsp4-order-defect-20260909.md`. Contract
`defs-v2026.09.08.4`, unchanged. New pair staged BESIDE the window pair
as `~/dspboot/tx_chip1.ldr` `21f9fdc1` / `tx_chip2.ldr` `de14981f`; the
window pair `093c609f` / `2ba0e464` is byte-identical to as-found and
`DSP4_BLK_LATCH=0` rebuilds it exactly. Bench restored to the shipping
bitstream `a1f6672af6c3` and the `dsp4-pcm-slave` overlay.

### S8-1 — the ORDER DEFECT is a ping/pong PHASE error, and it is FIXED

**Severity: MAJOR (firmware, every chip-2 output lane). Status: FIXED and
proven on the part.**

S7-5 localised the defect to the chip-2 transmit path and left three
candidates: the DMA ring indexing, the block hand-off, and the TX slot
tables. The hand-off is the one, and the mechanism is not an indexing
bug — it is the PHASE of the ping/pong itself.

`_set_tx_bufs` started the core on the PING half and `_sport_dma_work`
toggled it at each block interrupt. The DDE also starts each region on
its ping row and moves to pong at the first row boundary — the same edge
that raises that interrupt. So the core was always writing the half the
channel was clocking onto the wire. The slots the DDE had not reached
yet went out carrying the block the gather had just written; the slots
it had already passed went out carrying whatever that half held from two
blocks earlier. Every transmitted 8-sample window was assembled from up
to three consecutive blocks, split at a fixed sample.

**The instrument, not an inference.** `SHARC/src/tx_probe.asm`
(`DSP4_TXPROBE=1`) stamps chip 2's TX lane 3 slot 1 — driven onto the
wire, written by no node — with `(block counter << 8) | (half << 4) |
sample index`, immediately after the gather has written slot 0 of the
same frame. `_maincap` presents slot 0 as the Pi capture's LEFT channel
and slot 1 as its RIGHT, latched from ONE DSP frame (S7-1), so a recorded
stereo frame is a coherent (audio, stamp) pair. The stamp is in order by
construction, so what comes back off the wire settles it without any
appeal to the audio. Decoded, with the node graph out of the way
(`DSP4_BLOCK_MASK=5`) so that ZERO blocks were missed:

| build | blocks missed | stamp transitions +1 |
|---|---|---|
| pre-fix | 0.0 % | 143,999 of 191,999 = **75.0000 %** |
| pointer latched only | 0.0 % | 143,999 of 191,999 = 75.0000 % |
| phase corrected | 0.0 % | 191,999 of 191,999 = **100.0000 %** |

The pre-fix delta histogram has exactly three entries — `+1` ×143,999,
`-15` ×24,000, `+17` ×24,000 — one of each jump per 8-sample window over
24,000 windows, which is what "a fixed split point" means quantitatively.
The fixed histogram has ONE entry. The sample-index field is 24,000 of
each of 0–7 in every build, so the position inside the window was never
in doubt; only the block was.

The fix is `DSP4_BLK_LATCH=1` (default), in `src/sport_init.asm`:

* the block ISR advances a PENDING pair of half-pointers and
  `_blk_latch_bufs` moves them into the active pair once per block,
  before the sample loop — the generated `_scatter_chipN`/`_gather_chipN`
  reload the active pointer on EVERY sample, so the ISR used to retarget
  them mid-block. On the part this alone changed nothing (row 2 above);
  it is a real hazard closed, not the defect;
* the core starts on PONG, so it fills the row the DDE has just finished
  with and that row goes out on the next block. That is the defect, and
  row 3 is the fix.

`DSP4_BLK_LATCH=0` rebuilds `093c609f` / `2ba0e464` byte for byte, so the
control column is measured rather than quoted.

**It is not one lane.** The lane the instrument measured, `o_dspb[3]`, is
the CPLD's `dac_main` — a converter lane, not a measurement lane, and
slot 0 of it is `C2_MAIN_ST_OUT`. `_gather_chip2` writes all twenty
chip-2 outputs from the same half in the same loop through one pointer,
so the other four output lanes (AUX_OUT 01–12, MAIN_OUT 01–04, MON_OUT,
CODEC_AUX_OUT, SUB_OUT) carried the identical splice and are fixed by the
identical pointer. They cannot be witnessed directly on this bench —
LOGIC captures only `o_dspb[3]` and no analogue loopback is wired — and
what would settle them is a `_maincap`-style build capturing a slot of
`o_dspb[0..2]`. Chip 1's inter-chip TX and both chips' RX regions carry
the same off-by-one-half and get the same fix; the RX side is not
separately witnessed, because the only observable that could witness it
is the audio through the loop, and that is dominated by S8-2.

Cost: two DM words and one call per block. On-part `_proc_cyc` reads
286,757 before and 282,308 after on chip 2 — the instrument reports the
LAST pass and its pass-to-pass spread is wider than the change.

### S8-2 — underneath it: the block loop does not fit the block, and misses three blocks in four

**Severity: MAJOR (firmware/capacity, open). Status: measured, NOT fixed
— needs its own dispatch.**

The same instrument found a second defect that the first was hiding. With
the phase fixed, the staircase is still only 33 % exact through the full
D24 graph, because the core is not writing most of the blocks at all:

| what | chip 1 | chip 2 |
|---|---|---|
| blocks missed (`DIAG_BLK_OVERRUN` / `FRAME_COUNT`, 8 s) | **75.1 %** | **70.9 %** |
| `_proc_cyc`, shipping per-sample build | 330,389 | 286,757 |
| `_proc_cyc`, `DSP4_BLOCK_KERNELS=1` | 134,325 | 170,622 |
| `_proc_cyc`, plumbing only (`DSP4_BLOCK_MASK=5`) | — | 13,964 |
| budget, BLOCK=8 at 982.98 MHz | 163,830 | 163,830 |

The two instruments agree to a tenth of a percent: chip 2 misses 71.4 %
of blocks and the block counter on the wire advances at 28.7 % of the
frame rate. A half that is not rewritten is transmitted again, so the
wire carries stale whole blocks — which is the ±225-block tail S7-5
measured, and it is why the staircase does not come back exact even with
the transmit path proven in order.

**Every capacity number on record was taken in a configuration that does
not ship.** The `.4` record (chip 1 202,786 / chip 2 226,442 against
327,680) is a BLOCK=16 `DSP4_BLOCK_KERNELS=1` build. The shipping default
is BLOCK=8 per-sample, and that costs 2.0x (chip 1) and 1.75x (chip 2) of
the block-8 budget. Block kernels alone do not close it: chip 2 still
reads 170,622 against 163,830 and misses 51.9 % of blocks — and a loop
that takes 1.04 block periods misses every second block, not 4 % of them,
because `_block_ready` is a flag and not a queue.

The causal chain is closed by reducing the load until the loop nearly
fits. With `DSP4_BLOCK_KERNELS=1`, the phase fix, and the runtime masks
poked down to one strip and one aux, chip 1 misses 0.0 % and chip 2 misses
30.3 %, and the staircase through the whole chip-2 graph goes from
**32.87 % to 91.92 % exact** over 96,000 frames. The residual is the
residual overrun; nothing else moved.

CCLK is not the reason: 982.98 MHz measured against the 983.04 target, and
the block rate is 5,999.9/s against 6,000.

### S8-3 — the bench recipe was booting chip 2 with chip 1's firmware

**Severity: MAJOR (bench procedure, invalidates measurements). Status:
FIXED in the session's own scripts; the shared run scripts still carry
it.**

`sudo pinctrl set 6,7,8,9,10,11,12,22,23,24,25 a0` — the line every run
script executes after an OpenOCD flash, to hand the JTAG pins back — puts
GPIO24 into ALT0, which on this part is `SD0_DAT2`, not a deasserted chip
select. Chip 2's CS then sits asserted while chip 1's boot stream is
clocked out, chip 2 loads `chip1.ldr`, and the card comes up as two chip
1s. Six consecutive boots did this before the pins were read back;
holding GPIO 6 and 24 as outputs driven HIGH (`pinctrl set 6,24 op dh`)
and giving only 7, 9, 10, 11, 22, 23, 25 to `a0` booted chip 2 correctly
first time, every time after.

`dsp4_scope.check_chip` catches it — "link answers as CHIP 1, expected 2"
— and that is the only reason it was ever caught; `dsp4_diag.py` reports
it as a healthy part with a wrong CHIP_ID, and any measurement taken
through the diag link alone would have been fiction. `lat_run.sh`,
`famverify_run.sh` and `profile_run.sh` retry the boot until
`dsp4_diag.py --chip 2` answers 2, which recovers from it by accident;
they should hold the CS lines instead.

Two smaller traps found with it: `dsp4_diag.py --help` documents chip 2's
CS as GPIO 7 while the code (and `dsp4_scope.CS_GPIO`) uses 24; and
`dsp4_diag.py --chip 2` without `--rdy-gpio 12` uses chip 1's ready line
and cannot phase the link at all.

### S8-4 — the through-DSP latency did not move

**Severity: n/a (result). Status: measured.**

Re-measured on the fixed pair with the same instrument
(`dsp4_dsp_latency.py`, 10 reps x 2 boots): minimum 14,508 and 14,509,
medians 14,512 / 14,517, spread 13 and 15, worst margin over the runner-up
x16.8. The pre-fix session read a minimum of 14,504 on both boots. The
+4 samples is inside the instrument's own spread on either arm, so the
72-sample / 1.500 ms figure of S7-6 stands, and the boot-to-boot part is
again zero (14,508 against 14,509, one sample).

Coherent fraction 33.1–33.7 %, which is S8-2 and not the transmit path.

## The capture path made frame-locked, and the design given an ID (2026-09-09, session 33)

Session: a frame-locked CM4 capture and a readable design-ID register in
one bitstream, and the through-DSP arm re-diagnosed from measurement
rather than from the symptom. Write-up:
`MW/D32/DSP/dsp4-loop-latency-20260909.md` §7. Contract
`defs-v2026.09.08.4`, unchanged. Images unchanged: the window pair
chip1 `093c609f` / chip2 `2ba0e464`, run from a separate staging path
(`~/s32`) so `~/dspboot` was not touched. New bitstream
`dsp4_logic_maincap.d903ae1ac4a9`, design ID `32'hae1ac4a9`, 404/1270 LE,
Fmax 68.66 MHz.

### S7-1 — the CM4 capture spliced every word out of TWO DSP frames

**Severity: MAJOR (LOGIC, shipping path). Status: FIXED and proven on the part.**

`cap_flat` is rewritten slot by slot as the DSP frame arrives — slot `s`
completes at `frame_pos = (s+1)*128` — while the Pi's read-out of one
32-bit word spans nearly the whole frame (bit 31 launches around
`frame_pos` 32, bit 0 around 536). The read-out was walking the LIVE
register file, so for most `CAP_SLOT` choices the register was
overwritten part-way through and **the word the CM4 recorded was spliced
from two consecutive DSP frames at a fixed bit position**.

Measured, not inferred. With the DSP alternating two known words
A = `0x12345670` and B = `0x7BCDEF80` every frame, the old bitstream
(`dsp4_logic_maincap.1216e35175cb`) returned, over 100,000 settled
frames, exactly two values: `0x03F7CA48` and `0x1786C9A8` — **neither of
them A or B**. The new bitstream on the same stimulus returns
`0x17F7CA48` and `0x0386C9A8`, also two values, 50,000 each.

The two are related by the splice model exactly, in both phases:

```
old[n] = { true[n-1][31:25], true[n][24:0] }
  {0x1786C9A8[31:25], 0x03F7CA48[24:0]} = 0x17F7CA48   <- new, phase 1
  {0x03F7CA48[31:25], 0x1786C9A8[24:0]} = 0x0386C9A8   <- new, phase 2
```

Bit 25 is where the arithmetic says it should be: slot 0 completes at
`frame_pos` 128, which is `out_word_pos` 6, which is bit 25. The same
arithmetic puts the SHIPPING return (slot 2, complete at `frame_pos`
384) at **bit 9** — so the product's CM4 return had the defect too, three
bits into the audio, and would have shipped with it.

Fixed by reading a snapshot instead of the live file: both presented
slots are latched together one Pi word before the left read-out starts,
so a recorded stereo frame is a coherent pair from ONE DSP frame. Cost:
one extra frame of constant latency, 64 flip-flops. `PI_SELFTEST` is
bit-identical before and after — its source words are written outside the
read-out window — which is what makes the fix testable: `_pisel` must not
move, and it does not.

### S7-2 — and the period decode was one BCK early, hidden by a constant that cancelled it

**Severity: major (LOGIC). Status: FIXED.**

`in_period = frame_pos[9:2] - 8'd1` named the incoming bit by the period
BEFORE the one in which it is sampled. Period indices name the SAMPLING
period on the transmit side (`out_period` adds 1 because the launch is
one period earlier); MFD=1 puts slot 0 bit 31 on the rising edge after
the one that reads FS high, and FS is high through period 255, so slot 0
bit 31 is sampled at period 0. No offset belongs there.

The consequence was that `cap_flat[s]` held `{slot_s[30:0], slot_s+1[31]}`
— every word one bit left, with the NEXT slot's MSB in its LSB. That is
precisely the symptom recorded on 2026-08-23 ("the expected words shifted
LEFT exactly one bit, 100% stable over 96,000 frames"), and it was
answered by adding `CAP_EXTRA_DELAY = 1` to the read-out, which slid the
read back over the error. **The two errors cancelled in every bit except
the top one, which came from the other slot** — invisible on every word
the bench ever sent, because all of them had bit 31 clear.

Both are now correct on their own terms: `in_period = frame_pos[9:2]`,
`CAP_EXTRA_DELAY = 0`, plain Philips I2S on the link. Proven on the part
by the ID readback, which recovers a 32-bit constant exactly — 2,175
reply frames, ONE distinct reply word.

### S7-3 — nothing had ever simulated the capture direction

**Severity: moderate (process). Status: FIXED.**

`sim/tb_pcm_reframe.v` instantiates the re-framer with `tdm_in` and
`bck8_sample` **dangling** — it tests the Pi → DSP direction only. The
sim gate was therefore green through both defects above, and both are of
the kind a testbench catches on the first run.

Added `sim/tb_pcm_capture.v` with two new models
(`model_tdm_tx.v`, `model_pi_i2s_rx.v`). The DSP transmits a different
word in every slot on every frame, so a read-out that walks a live
register file cannot pass: the check is not "the value looks plausible"
but "L and R are both exactly the words of ONE frame, the same frame, at
a constant lag", over both slot configurations (0/1 and the shipping
2/3). It fails on the old RTL and passes on the new. The sim gate is now
4 testbenches.

Writing it also cost two model bugs worth recording, because both are
traps for the next person: an I2S receiver that resets its bit counter on
the WS edge loses the last bit of every word (the word runs ACROSS the
boundary), and a TDM transmitter that samples FS on the same falling edge
it launches data on races the clkgen's own NBA update and starts its
frame one BCK early. FS is sampled on the rising edge, data launched on
the falling one, in the model as on the part.

### S7-4 — S5-9 closed: the design carries an ID, and it is readable with no hands

**Severity: minor (verifiability). Status: DONE, proven on the part.**

`build.sh` derives `DSP4_DESIGN_ID` as the low 32 bits of the artifact
hash and `DSP4_CFG_BITS` as a five-bit configuration field (loopback,
pi_selftest, pi_maincap, pi_tdm8, shipping) and passes both in as Verilog
macros. They are GENERATED, never typed, and they do not feed the hash —
so "read the register, compare to the manifest" is a real check.

MAX V has no configuration readback over SVF, the DSPs have no link into
this CPLD, and the TEST pins land on a DNP header, so the one path off
the part that needs no hands is the CM4's PCM capture. The register is
therefore read by KNOCKING: the Pi plays `{L = 0xD5D51D1D,
R = 0x2A2AE2E2}` (R the exact bit-inverse of L) and LOGIC answers
`{L = design_id, R = 0xD594<cfg_bits>}` for 128 frames. Reader:
`tools/pi/dsp4_logic_id.py`.

On the part, after the flash:

```
design_id: 32'hae1ac4a9   cfg_bits: 16'h0004   pi_maincap
  reply frames 2175 of 144000 captured, 1 distinct reply word
  MATCHES --expect ae1ac4a9
```

It is built in EVERY configuration, which is the point: every future
flash answers "what are you?" in one `aplay` plus one `arecord`. It is
shipping-safe by scope — a false trigger needs a specific 64-bit pair and
costs 128 frames (2.7 ms) of the CM4's own return stream, and touches
nothing on the DSP-facing side, the DAC lanes, the NET lanes or the
panel.

### S7-5 — the through-DSP arm is NOT a capture problem: whole 8-sample BLOCKS arrive from the wrong place

**Severity: MAJOR (firmware, open). Status: mechanism measured and localised, NOT fixed.**

S6-4 named the `_maincap` capture path as the thing that "scrambles the
order". That was the wrong suspect, and the frame-lock fix (S7-1) — which
is a real defect and a real fix — does not change this result by one
percent: the staircase scores 32.87 % exact before the fix and 32.87 %
after it.

What the arm actually does, measured with a two-level stimulus at
different periods (`steptest.py`, 90,000 settled frames each):

| stimulus period | runs observed | runs if clean | verdict |
|---|---|---|---|
| 2 frames (HOLD 1) | 90,000 | 90,001 | **exact** |
| 4 frames (HOLD 2) | 45,001 | 45,001 | **exact** |
| 8 frames (HOLD 4) | 22,500 | 22,501 | **exact** |
| 16 frames (HOLD 8) | 40,211 | 11,251 | scrambled |
| 32 frames (HOLD 16) | 42,396 | 5,626 | scrambled |
| 128 frames (HOLD 64) | 42,867 | 1,407 | scrambled |

**Any pattern whose period divides 8 survives exactly; anything longer is
scrambled.** So the displacement is a non-zero multiple of 8: every
sample arrives at the RIGHT position inside its 8-sample block, from the
WRONG block. `BLOCK = 8` on these images.

Two more measurements pin it down. The chain is **bit-transparent** —
across every one of those runs the capture contained ONLY the two exact
stimulus values and zero, never an intermediate, so nothing is filtering
and nothing is arithmetically wrong. And the displacement histogram is
**independent of signal magnitude** (mean −10.1 steps in every one of six
250-step buckets from index 0 to 1500, min −28 max +1 in all of them),
so it is a time offset and not a gain or rounding error. About a third of
blocks are in the right place; the rest are drawn from roughly the last
225 blocks (≈1,800 frames, ≈37 ms).

Where it is NOT: the CM4 (`_pisel` returns 96,000 of 96,000 exact on the
identical staircase through the identical ALSA path, 100.00 %); the CPLD
capture (`cap_flat` is one frame deep and cannot deliver a sample from
1,800 frames ago, and is now proven coherent by S7-1); the chip-2 node
graph (`_buf_C2_PI_IN`, `_buf_C2_MIX_MAIN_L`, `_buf_C2_MAIN_FDR`,
`_buf_C2_MAIN_DLY`, `_buf_C2_MAIN_ST_OUT` read non-decreasing on 36 of 38
consecutive samples while the staircase plays, advancing at 48,000
frames/s — a ±1,800-frame scramble on the compute side could not do
that).

That leaves the chip-2 transmit path — the SPORT3 TX DMA and whatever
fills its buffer — as where a block-granular buffer is being read at an
index that is not locked to the frame. **That is the next dispatch**, and
it is not cosmetic: if the same machinery serves the converter lanes,
two-thirds of every output block is coming from a random point in the
last 37 ms.

Also retired by this: the 2026-09-09 note that a constant returns
"bit-exact" and a staircase does not, offered as evidence about the
capture. Both are explained by the block model — a constant is
period-1 — and neither says anything about the capture path.

### S7-6 — the through-DSP loop latency, measured, with the DSP block term visible

**Severity: n/a (result). Status: measured.**

A per-word offset vote cannot be used on this arm — with a third of the
words coherent it finds spurious modes, which is exactly how the
2026-09-08 figure of 14,550 was produced. `tools/pi/dsp4_dsp_latency.py`
scores every candidate offset by the fraction of frames carrying the
exact expected value and reports the answer only with its margin over the
runner-up two plateaus away. The coherent third puts a sharp peak at the
true offset; a spurious mode has no peak.

See `MW/D32/DSP/dsp4-loop-latency-20260909.md` §7 for the table. The
margin was never below x16 on any rep, so the figure is quotable in a way
the 2026-09-08 one was not.

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

### S9-1 — the build that shipped was not the build that was measured, in three parameters

**Severity: MAJOR (shipping configuration). Status: FIXED.**

Block size, block kernels and the core clock were all set one way in the
measurement scripts and another way in the build the images come from,
and no instrument could see it because every instrument was reading the
same wrong build.

* **BLOCK.** PW ruled 2026-09-03 that block 16 is the configuration that
  fits both chips. The ruling was applied only inside the measurement
  scripts, which generate a scratch tree with `DSP4_GEN_BLOCK` and build
  it through `DSP_SRC_DIR`. `dsp_codegen.py` carried `BLOCK = 8` as a
  literal from 2026-08-28 until 2026-09-09, so the committed tree — and
  therefore `./build.sh` — was never generated at anything but 8. Nothing
  drifted back; the ruling never reached the tree.
* **BLOCK KERNELS.** Every capacity figure since 2026-09-01, the `.4`
  record included, is a `DSP4_BLOCK_KERNELS=1` build. The default was 0.
* **CORE CLOCK, and this one had never been noticed at all.** Every cycle
  budget since 2026-08-24 is quoted at 983.040 MHz on the strength of
  PW's U5/U6 reading (`ADSP-21564KSWZ10`). `DSP4_CCLK_TARGET` defaulted
  to 0, which leaves the CGU on its reset divisors at 491.52 MHz. Read
  off the running window pair: `CGU0_CTL 0x00002800`, `CGU0_DIV
  0x05144281` on BOTH chips — exactly the "today" row of
  `src/cgu_init.asm`, not the 983.040 row (`0x00005000`). So the
  block-8 shipping image was over an 81,920-cycle budget, and its
  overrun was **4.03x on chip 1 and 3.50x on chip 2**, not the 2.02x and
  1.75x S8-2 scored against a clock the image did not have.

Fixed by naming the configuration in one file — `MW/D32/DSP/SHARC/
shipping.config`, sourced by `build.sh` and read by `dsp_codegen.py`
through `tools/dsp/build_config.py` — regenerating the tree at block 16
so `./build.sh` with no overrides IS the shipping configuration, and
making `build.sh` refuse a tree whose `dsp_block.h` disagrees with
`DSP4_GEN_BLOCK`. The image carries `DIAG_BUILD_CFG` (0xE0EA) so a
mismeasured configuration can never be silent again; the shipping word is
`0xCF45FF10`. On the fixed configuration, D24 mask: chip 1 234,594
cycles/block (71.6 % of 327,680), chip 2 303,894 (92.7 %),
`DIAG_BLK_OVERRUN` 0 on both over 600 s.

### S9-2 — the first frame of each DMA half has an earlier deadline than the block does

**Severity: MAJOR (product audio). Status: OPEN — mechanism named and
measured, margin improved, structural fix needs PW.**

With the block loop fitting the block and `DIAG_BLK_OVERRUN` at zero, the
chip-2 transmit path is still not exact at the D24 mask. The whole gather
runs at the END of the block period, after the node graph has spent
92.7 % of it, and the DDE clocks frame 0 of the half out FIRST. Those
frames lose the race and leave the part carrying what that half held TWO
BLOCKS earlier.

The count of late frames per block tracks the LOAD, not the block, which
is what makes it a race and not an indexing error. Transmit stamp,
192,000 frames, `_maincap` `d903ae1ac4a9`:

| arm | stamp order | late frames/block |
|---|---|---|
| node graph out of the way (`DSP4_BLOCK_MASK=5`) | 100.0000 % | 0 |
| load cut to one strip and one aux | 100.0000 % | 0 |
| full D24 graph | 87.4999 % | 1 |
| full D24 graph, `DSP4_GATHER_FIRST=1` | 100.0000 % | 0 |
| full D24 graph + the Pi playback input | 81.2499 % | 2 |

The two 100 % rows are also what confirms the 2026-09-09 ping/pong phase
fix (`DSP4_BLK_LATCH`) still holds at block 16.

`DSP4_GATHER_FIRST=1` moves the gather to the head of the loop body, in
front of `_scope_record` and the parameter-link poll, neither of which it
depends on. Worth about one frame of margin; at the heavier load both
orders measure 81.2499 % repeatably. **Margin, not a fix.**

The lever: give the gather a whole block period of slack — write block
N-1's outputs at the top of period N, or a third TX buffer. Both cost one
more block of output latency (16 samples, 0.333 ms) and both are
architecture decisions. Reducing chip 2's 92.7 % is the other half of the
same lever.

### S9-5 — famverify's audio arm moves 17/20 -> 8/20, and BLOCK KERNELS are the reason

**Severity: MAJOR (bar, and possibly product audio). Status: OPEN —
attributed, not explained.**

Three arms, one variable at a time, same bench, same contract
(`landed-d24.json`, 3,737 cells, sha256 `4aa3c343cedf`, pin
`defs-v2026.09.08.4`), same day:

| arm | BLOCK | kernels | CCLK | audio LIVE |
|---|---|---|---|---|
| the `.4` configuration, rebuilt | 8 | 0 | 491.52 | **17 of 20** |
| the discriminator | 8 | **1** | 491.52 | **8 of 20** |
| shipping | 16 | 1 | 983.04 | **8 of 20** |

The block-8 per-sample arm reproduces the `.4` line exactly, so the move
is not the bench or the day; block 8 WITH kernels gives the same 8 of 20
as block 16, family for family, so it is not the block size or the clock
either. **It is `DSP4_BLOCK_KERNELS`.**

The eight families that move are all chip-1 strip-chain nodes witnessed
at `_buf_C1_*` — COMPRESSOR, DELAY, EQ_BIQUAD, FADER_PAN, GATE and
HPF_LPF go INERT, ROUTING and TUBE_SAT go SILENT, COMPRESSOR's numeric
arm goes BIT_EXACT -> FAILED. The chip-2 families witnessed with an
impulse are unaffected, and **every family's contract arm is unmoved in
all three arms**: GEQ 31/31, CROSSOVER 8/8, ROUTING 42/42, COMPRESSOR
17/17, 0 failed.

Not settled: whether this is an audio defect or a witness that does not
hold in the block-kernel arm. The mechanism that would explain it with no
audio wrong is that `_scope_record` runs in the GATHER loop, after
`_chipN_process_all` has processed the whole block, so `_buf_<node>`
holds only the last sample of the block when the scope samples it and the
recorded window is one word repeated; a step settles, so a parameter
change that alters the waveform but not its settled value reads INERT.
Against a real regression: `c2gold.sh`'s D80 record has the block-kernel
arm bit-exact against per-sample except in the meters.

Settled by a block-aware witness — record `_blk_<node>` where the class
publishes one, or move `_scope_record` inside the kernel — and re-running
the three arms. **Block kernels have been in every capacity measurement
since 2026-09-01 and had never been through famverify once**; making them
the shipping configuration is what exposed that.

### S9-3 — D32's all-ones mask does not fit at block 16

**Severity: MAJOR (product scope). Status: OPEN.**

The same shipping configuration that fits D24 with 7.3 % of margin does
NOT fit D32: with all 32 strips and 12 aux buses active, chip 2 missed
**11.3 %** of blocks in a loaded run (1,552 overruns in 13,773 blocks).
D24 in the same script and the same session missed zero. D32 at block 16
is not a shipping configuration on this firmware, and the capacity work
that would make it one is chip 2's, not chip 1's — chip 1 sits at 71.6 %.

### S9-4 — the Pi playback input is off by default, and the loop is not bit-transparent

**Severity: MINOR (bench procedure). Status: RECORDED.**

Two things have to be done before the through-DSP staircase measures
anything, and neither is in any script:

1. `C2_PI_IN` is an `AUX_INPUT` with `on=0` and `level_db=-6.0` in
   `dsp.csv`. The stimulus crosses the fabric intact — `_blk_C2_XR_PI_L`
   reads `0x04000000` for a `0x20000000` stimulus, the documented 8x
   round-trip attenuation — and the node publishes zero, so the capture
   is a constant and every scorer reports 0 % exact on a loop that may be
   perfectly ordered. Write `0x0744 = 1` and `0x0743 = 1.0f` on chip 2.
2. The rest of the chip-2 graph sums a constant into MAIN, so the loop
   carries the staircase PLUS a DC offset. `dsp4_order_stair.py` and
   `dsp4_tx_order.py` both test for the exact stimulus value and score
   0 % on a capture that only differs by that constant. Score against the
   step index with the DC removed.

With both done, the audio and the transmit stamp agree to a tenth of a
percent on the same capture (82.3458 % against 81.2499 %), which is what
establishes that the staircase's disorder IS the transmit-path disorder.

### S10-1 — S9-5 SETTLED: block kernels are NOT an audio defect; the witness and the stimulus were

**Severity: MAJOR (closes S9-5). Status: CLOSED.**

S9-5's 17/20 → 8/20 was **entirely the bench instrument**, and it was two
independent defects on chip 1, not one. With both fixed, the shipping
configuration — block 16, block kernels, 983.04 MHz — reads **17 of 20
LIVE and agrees with the block-8 per-sample control on all twenty
families, verdict for verdict**; the contract arm is identical on every
family and the numeric arm is BIT_EXACT on COMPRESSOR, FADER_PAN and
TUBE_SAT.

**Defect one — the witness read a variable the kernel never writes.**
Under block kernels a chip-1 strip node writes a *shared pool slot*
(`blk_pool.h`), and `_buf_<node>` survives as a one-word `.var` that
nothing writes. `_scope_record`'s `#if DSP4_BLOCK_KERNELS` arm reads
`_scope_src + _sample_idx` — right for chip 2, whose kernels really do
publish `_blk_<node>[BLOCK]`, and on chip 1 a sixteen-word walk off a
one-word variable into the next node's parameters. Named in the link map:
`_buf_C1_GAIN_01 + 4 = _gain_coeff_C1_GAIN_02` (read back as 1.0f),
`_buf_C1_EQ_01 + 3 = _eq_coeffs_A_C1_EQ_02` (4.0f), `_buf_C1_DLY_01 + 6 =
_dly_max_C1_DLY_02` (12000). So GAIN and TALKBACK's arm-B "LIVE" was the
witness watching the parameter class the test was stepping. For the nodes
whose `_buf_` *is* written once per block, `moved` was exactly `N/BLOCK`.

**Defect two — the stimulus went into a slot with no reader.**
`_scope_inject_blk` fills `BLOCK` words at the RX-slot symbol the host
names. On chip 2, `_rx_ic_slot_<node>[BLOCK]` is a real array the chain
reads. On chip 1, `INPUT_TDM`'s kernel reads DMA straight into a pool slot
and `_rx_slot_<node>` is a one-word variable nothing reads — so the
stimulus went nowhere **and** fifteen words landed past the end of it.

The two are separable and were separated: fixing the witness alone
(arm C) leaves 9/20, with the peaks now honest (`0`, `1`, `4` — real
Q4.28 magnitudes) and the verdict SILENT. Both halves were needed.

**The witness proved itself first.** NOISE_GEN generates its own signal;
in arm C it read peak **268,365,104** against the per-sample control's
**267,776,416** while every stimulus-driven family correctly read silence.

**Consequence for the record: every block-kernel famverify run since
2026-09-01 was measuring its own instrument on chip 1**, and no chip-1
audio conclusion from those runs should be quoted.

Instrument: `DSP4_SCOPE_BLK_TAP` (default 0, never ships — a default
`./build.sh` reproduces `ac65ad38`/`e5dce9e4` byte for byte after every
change in this session). Write-up
`MW/D32/DSP/dsp4-block-witness-20260909.md`.

### S10-2 — a pooled buffer cannot be witnessed after the block, and the table that fixes it

**Severity: MINOR (method). Status: RECORDED.**

The pool is reused: strip N's `BLK_CHAIN_B` is strip N+1's the moment
strip N+1's GAIN runs, and by the end of a block every slot holds the last
strip that touched it. **There is no later point at which a given node's
block still exists**, so no witness that runs in the gather loop can ever
be correct for a pooled node — this is not a bug in `_scope_record`'s
timing, it is a property of the pool.

The tap therefore runs *at* the node, from the generated chain, and is
handed the address by the generator. Which slot each strip class publishes
into lives in `_STRIP_BLK_OUT` (`tools/dsp/dsp_codegen.py`), the same kind
of table as `_METER_SRC_BLOCK` and under the same rule: `_blk_out_of()`
**checks the table against the body it just generated** and fails the run
if a kernel has moved onto a different slot. A table of facts about
generated code that nothing checks is a table of facts about code that
used to exist.

### S10-3 — `_scope_inject_blk` overruns `_rx_slot_C1_IN_01` by fifteen words in the SHIPPING image

**Severity: MINOR (latent; bench-triggered only). Status: OPEN — needs PW.**

The overrun described in S10-1 is in the shipping image too, not only in
the instrument: `_scope_inject_blk` is compiled under `DSP4_BLOCK_KERNELS`,
not under the tap flag. It is inert in the field — `_scope_inj` is 0 until
a host arms the scope and nothing in the product does — but it is a real
out-of-bounds write and it should not stay. **Not fixed here**, because
fixing it changes `ac65ad38`/`e5dce9e4` and a new pair is a window
decision.

### S10-4 — GATE's NUMERIC arm reads NO_STIMULUS in a block build

**Severity: MINOR (bar coverage). Status: OPEN.**

With the block-aware witness, GATE's **audio** arm is LIVE and its
contract arm is 12/12, but its NUMERIC arm reads `NO_STIMULUS` where the
block-8 per-sample control reads `BIT_EXACT`: `dsp4_node_verify`'s own
stimulus search found no usable point in a block build. COMPRESSOR,
FADER_PAN and TUBE_SAT are BIT_EXACT in both arms, so this is specific to
GATE and to the second instrument, not to the family.

### S10-5 — `DIAG_BUILD_CFG` has no spare bit, so an instrument build can still be silent

**Severity: MINOR (method). Status: OPEN.**

Bits 8..23 of `DIAG_BUILD_CFG` are all allocated and 31..24 is the 0xCF
signature, so `DSP4_SCOPE_BLK_TAP` could not be added to the word that
exists to stop exactly this. The tap build is identified by its build
banner and by `_scope_tap` in its map — neither of which the *part* can be
asked. Widening the word means moving the signature and every check built
on `0xCF45FF10`, which is not a thing to do on the last day before a
window.

Partial mitigation landed: `dsp4_family_verify.py` now records
`build_cfg` per chip in its JSON. Five famverify reports were taken on
2026-09-09 in five different configurations and not one recorded which, so
telling the control from the arm meant trusting a filename.

### S10-6 — the capacity record's instrument and the shipping image disagree, and chip 2's gap is unexplained

**Severity: MAJOR (the capacity record). Status: PART OPEN.**

`sigprofile.sh` / `sigprofile2.sh` / `fxcost.sh` build an INSTRUMENT:
`DSP4_PROFILE_SIGNAL=1` (so the dynamics cannot be measured on their cheap
branch) and `DSP4_BLOCK_DECIMATE=32` (so a graph that does not fit still
completes). Right for attributing cost to a class; not the image that has
to fit. Measured both ways in one session, block 16, 983.04 MHz read back:

| | the record's instrument | the shipping pair | gap |
|---|--:|--:|--:|
| chip 1, D24 | 408,939 (124.8 %) | 234,267 (71.5 %) | +174,672 |
| chip 2, D24 | 225,646 (68.9 %) | 303,891 (92.7 %) | **−78,245** |
| chip 2, D32 | 261,093 (79.7 %) | 369,424 (112.7 %) | **−108,331** |

Chip 1's is EXPLAINED: `DSP4_PROFILE_SIGNAL` + `TUBEON=1` put all 32 strips
on their expensive branch, so 408,939 is the honest signal-present worst
case and 234,267 is the same graph on a silent bench.

Chip 2's is NOT. It is 24 % of budget at D24 and 33 % at D32, in the
direction the signal/silence split cannot produce. `DSP4_BLOCK_DECIMATE=32`
is the remaining candidate — it gives the graph thirty-two block periods,
so nothing in the block loop ever contends. **Until this is resolved a
chip-2 margin quoted from `sigprofile2`/`fxcost` is a margin for the
instrument.** The same disagreement shows up in the D24 mask's value:
35,447 cycles on the instrument, 65,533 on the shipping pair.

`tools/pi/dsp4_capacity.py` reads the shipping pair directly and is the
arbiter: `_proc_cyc`, `_proc_cyc_max`, `DIAG_BLK_OVERRUN`, and the CGU
words so the budget comes from the clock the part is running.

### S10-7 — a measurement bar could destroy the artifact the product ships

**Severity: MINOR (bench procedure). Status: PART FIXED.**

`famverify.sh`, `sigprofile.sh`, `sigprofile2.sh` and `fxcost.sh` all
`scp build/chip1.ldr build/chip2.ldr` into `/home/app/dspboot/` — which is
where `chip1.ldr` / `chip2.ldr`, two of the staged pairs the window rolls
back to, live. Running a bar overwrites them.

`famverify.sh` now takes `STAGE` (default `/home/app/dspboot`, so nothing
that calls it changes) and symlinks the shared bench helpers into it, so a
run can be staged anywhere. The three profile scripts still do not, and
this session protected the window pair by copying it to
`~/dspboot/.window/` and restoring it. Extending `STAGE` to the profile
scripts is the durable fix.

### S10-8 — the margin was being quoted off an average, and only on chip 1

**Severity: MAJOR (every chip-1 margin on record). Status: RECORDED.**

`_proc_cyc` is the last block pass; `_proc_cyc_max` is the worst since
reset. On the shipping pair, block 16, two boots per arm:

| | mean | worst | worst/mean |
|---|--:|--:|--:|
| chip 1, D24 | 234,267 | 277,752 | **1.186** |
| chip 1, D32 | 306,190 | 361,246 | **1.180** |
| chip 2, D24 | 303,891 | 304,874 | 1.003 |
| chip 2, D32 | 369,424 | 370,832 | 1.004 |

**Chip 2's block cost is flat to 0.4 %; chip 1's worst block is 18 % above
its mean at both masks on every boot** — stable enough to be structural,
not jitter. Chip 1 carries the 38 METER nodes and the ramp engine, and the
meter fold is an explicit per-block gate (`_mtr_block_tick`).

So **chip 1's D24 margin is 15.2 %, not 28.5 %**, and every chip-1 margin
ever quoted on this project is 18 % of its own value too generous.

Two riders. **OVERRUN 0 does not mean every block fitted** — chip 1 at D32
exceeds budget on its worst block (110.3 %) and still reports zero
overruns, because `_block_ready` is a flag and a long block is absorbed by
the next block's slack. And **`_proc_cyc_max` is never reset**, so it
catches the one-time work in the first pass after CONFIG_COMMIT: one boot
read 1,351,877 (412.6 %) against 370,832 on its twin. It needs a reset
before it can be a production margin figure.

### S10-9 — a stale `chipN.sym.json` gives well-formed wrong cycle counts

**Severity: MAJOR (bench procedure). Status: FIXED in dsp4_capacity.py.**

The symbol map moves on every build. A bench tool that reads
`/home/app/dspboot/chipN.sym.json` while booting an image staged elsewhere
peeks `_proc_cyc`'s address **in a different build**, and whatever lives
there answers. On 2026-09-09 that returned values increasing by three per
read (it was `_proc_passes`) and, on one run, a number that matched the
expected `_proc_cyc` closely enough to be believed.

Two "fixes" tried on the way made it worse and are recorded so they are not
tried again: reading the peek DATA half with the paced voted reader `rd()`
returned DIAG_FRAME_COUNT's value (it fires twelve pipelined asks of its
own into a two-transaction handshake), and wrapping the handshake in a
24-try agreement loop returned `_proc_passes`. **The peek window tolerates
exactly one handshake at a time under load.**

`dsp4_capacity.py` now prefers the map staged beside the `.ldr` that was
booted. Every bench tool that peeks by symbol has the same exposure.

### S11-1 — S10-6 SETTLED: the capacity record's instrument was a DIFFERENT, FASTER BUILD, and it was not decimation

**Severity: MAJOR (the capacity record). Status: CLOSED.**

`sigprofile2.sh` / `fxcost.sh` read chip 2 78,245 cycles/block low at D24
and 108,331 low at D32 against the shipping image — 24 % and 33 % of budget
— in the direction the signal/silence split cannot produce.
`DSP4_BLOCK_DECIMATE=32` was the standing candidate. **It is not the cause:
decimation is worth 554 cycles on chip 1 and −920 on chip 2, both inside
the pass-to-pass spread** (`capacity.sh`, one variable, D24 mask).

The cause is **two build switches that `shipping.config` does not name and
`build.sh` defaults to 0, and that both profile scripts have always forced
to 1**: `DSP4_STRIP_FUSED` and `DSP4_SIMD_DYN`. With them on, chip 2 reads
222,314 at D24 against the instrument's 225,646, and 268,790 at D32 against
261,093 — 1.0 % and 2.3 % of budget apart, i.e. the whole disagreement plus
what `DSP4_PROFILE_SIGNAL` accounts for.

**This is S8-2's shape a third time: a number quoted for a build that is
not the one running.** `DSP4_PROFILE_SIGNAL` was declared; these two were
declared nowhere. Every `.4` / 09-03 / 09-08 chip-2 capacity row is
re-annotated in `MW/D32/DSP/dsp4-capacity-s11-20260909.md` §5 as an
instrument figure. The profile scripts are **retired for capacity claims
about the shipping image** and remain valid for attributing cost to a class
inside their own arm.

### S11-2 — `DIAG_BUILD_CFG` could not tell three images 81,299 cycles apart from each other (S10-5 came true)

**Severity: MAJOR. Status: CLOSED by a second word.**

S10-5 recorded that `DIAG_BUILD_CFG` has no spare bit — 31..24 signature,
23..8 all allocated — so "an instrument build can still be silent to the
part". On 2026-09-09 three arms were measured in one session: shipping,
shipping + `DSP4_BLOCK_DECIMATE=32`, and shipping + `DSP4_STRIP_FUSED=1` +
`DSP4_SIMD_DYN=1`, which differ by **81,299 cycles/block on chip 2**. **All
three read `DIAG_BUILD_CFG 0xCF45FF10.**

`DIAG_BUILD_CFG2` (0xE0EB) is added: signature `0xC2`, `DSP4_BLOCK_DECIMATE`
in 23..16, `DSP4_TX_EARLY`'s per-chip mask in 9..8, and the cost switches in
the low byte. Shipping reads **`0xC2010044`**, the fused/SIMD arm
**`0xC201004F`**. `dsp4_buildcfg.py` decodes it and `--expect-shipping`
scores it; `dsp4_diag.py`, `dsp4_checkchip.py` and `dsp4_capacity.py` print
it on every dump, boot and capacity row; `check_shipping_config.sh` computes
both words and **reads `build.sh`'s own defaults** for the switches
`shipping.config` does not name, so the mirror is not a third copy.

**Consequence, stated rather than buried: the tree no longer builds
`ac65ad38…` / `e5dce9e4…`.** It builds `a95fd8eb…` / `fb1eee67…`. The staged
window pair is untouched; adopting the successor is PW's call, and it needs
the design bars re-run on it.

### S11-3 — Lever 1 (BLOCK 32) is answered and it is NO: D32 gets worse, and the latency price is 4× the estimate

**Severity: n/a (a ruling input). Status: CLOSED.**

It links (`chip1.ldr` 444,704 B, `chip2.ldr` 313,268 B) and it boots.

| D32 all-ones | chip 1 | chip 2 |
|---|--:|--:|
| block 16 | 93.4 %, worst 110.3 %, OVERRUN 0 | 112.7 %, worst 113.2 %, **11.26 %** |
| block 32 | **86.22 %**, worst 94.63 %, OVERRUN 0 | **117.51 %**, worst 121.7 %, **14.86 %** |

Per sample, chip 2 goes from 23,089 to 24,067 cycles (**+4.2 %**) while
chip 1 goes from 19,137 to 17,658 (**−7.7 %**). **The 2026-09-01 trend that
predicted 5–10 % was a chip-1 and per-class trend and does not transfer to
chip 2's graph** — chip 2 carries the six FX engines, and doubling the block
doubles every kernel's working set.

The price is also four times what was assumed: measured through-DSP latency
is **66 samples at block 16 and 131 at block 32**, i.e. **+65 samples /
1.354 ms**, not +16 / 0.333 ms. The signal crosses four block-buffered
stages, not one.

D24 *improves* at block 32 (chip 1 worst 84.8 % → 72.7 %, chip 2 93.0 % →
89.0 %), so the lever is not worthless — it is not a D32 lever.

### S11-4 — the lever that DOES close D32 is `DSP4_SIMD_DYN`, and it is the half that is not proven

**Severity: MAJOR (it is the D32 decision). Status: OPEN — needs a session.**

| D32 all-ones | chip 1 worst | chip 2 `_proc_cyc` | chip 2 worst | OVERRUN |
|---|--:|--:|--:|--:|
| shipping | 361,246 110.3 % | 369,424 112.7 % | 370,832 113.2 % | 11.26 % |
| `DSP4_STRIP_FUSED=1` | 354,816 108.28 % | 365,882 111.66 % | 366,699 111.91 % | 10.32 % |
| + `DSP4_SIMD_DYN=1` | **307,247 93.76 %** | **268,790 82.03 %** | **284,249 86.75 %** | **0** |

**D32 FITS with both on — zero missed blocks on both chips over 270,082
blocks.** The target was 41,744 cycles on chip 2; this delivers 100,634.
But `DSP4_STRIP_FUSED` alone is worth only 3,542 cycles (1.08 %) and does
NOT close it: **97,092 cycles/block, 29.6 % of budget, is `DSP4_SIMD_DYN`
alone.**

`famverify.sh` with the block-aware witness, one variable per arm:

* **shipping**: 17/20 LIVE, contract 20/20 with 0 FAILED, COMPRESSOR /
  FADER_PAN / TUBE_SAT numeric **BIT_EXACT**
* **`DSP4_STRIP_FUSED=1`**: **verdict for verdict identical** to shipping —
  proven, and worth 1.1 %
* **`DSP4_SIMD_DYN=1`**: contract still 20/20, **0 FAILED**, but ANTI_FB /
  CROSSOVER / GEQ / LIMITER read **NO_CAPTURE**, GATE reads INERT, and the
  three numeric arms lose their stimulus
* **both**: **DOES NOT LINK** — chip 1 overflows `sec_swco` with the witness
  in the image

**This is NOT recorded as an audio defect.** It is the shape of S9-5: the
paired graph adds a pool slot and reorders the chain into pairs, so where a
node's block lives moves and the witness reads a symbol chosen before it
moved (S10-2). What makes it a session rather than a re-run is the link
wall: **the witness and the paired kernels do not currently fit on chip 1 at
the same time**, so the arm that would certify the lever cannot presently be
built. Getting round that (tap chip 2 only, tap a subset of the chain, or
shrink the paired path) is the first gate.

### S11-5 — the family bar was scoring the SHIPPING image eight families below the record

**Severity: MAJOR (a bar that does not bar). Status: CLOSED.**

S10 settled S9-5 with `DSP4_SCOPE_BLK_TAP=1` and recorded the shipping
configuration at **17 of 20 families LIVE** with three numeric arms
BIT_EXACT. `famverify.sh` never set the switch. Measured both ways this
session on the same tree, one variable:

| `DSP4_SCOPE_BLK_TAP` | audio LIVE | COMPRESSOR numeric |
|---|--:|---|
| 0 (what the script did) | **9/20** | **FAILED** |
| 1 | **17/20** | **BIT_EXACT** |

A bar that reads the image it certifies at 9/20 and calls a BIT_EXACT
family FAILED is not a bar. `famverify.sh` now defaults the tap ON, with
`DSP4_SCOPE_BLK_TAP=0` as the control that reproduces the old reading, and
records why the paired-kernel arm cannot have it.

### S11-6 — a latency arm without the pass-through setup reports a confident wrong offset

**Severity: medium (instrument). Status: CLOSED.**

The first through-DSP latency arm of the session returned offset **14,779
on all 20 reps, spread 0** — and a **coherent fraction of 0.0 %** with a
peak width of 400. Seventeen sources sum into `C2_MIX_MAIN_L` and the main
chain comes up at its landed values, so the Pi's stimulus never comes back;
`dsp4_dsp_latency.py` reports the best of a flat field. **An offset with a
zero coherent fraction is not a latency**, and the summary line prints the
offset first. `latency_run.sh` now runs `dsp4_passthru_setup.py` before the
probe and says why. Every arm quoted in S11 reads 100.0 % coherent.

### S11-7 — the transmit-stamp arm needs a bitstream AND an overlay the bench does not live on

**Severity: low (procedure). Status: RECORDED.**

The bench lives on the shipping CPLD `a1f6672af6c3` with the
`dsp4-pcm-slave` overlay. `dsp4_tx_order.py` needs **both** the `_maincap`
bitstream and the `dsp4-pcm-duplex` overlay: on the shipping bitstream
`arecord` returns "Input/output error" and zero frames, and on the slave
overlay the duplex device does not exist. The tool reports both as "NO
STAMP: the right channel is all zero", which reads as a firmware result and
is not one.

`SHARC/loadlogic.sh` is added — `maincap` / `pisel` / `shipping` / `--id`,
with the canonical pin hand-back after every load, because openocd's
linuxgpiod leaves its GPIOs claimed and that looks exactly like a bricked
card. The overlay is still a `config.txt` line and a reboot; it was flipped
and restored byte-identically this session (`config.txt.s11bak`), and the
bench ends on `dsp4-pcm-slave`, the shipping bitstream and matrix-app
active.

**The bench's own `restore_bench.sh` still carries the WRONG pin sequence**
(`pinctrl set 6,7,8,9,10,11,12,22,23,24,25 a0`, the S8-3 line that boots the
card as two chip 1s). It is not in this tree, so `check_bench_pins.sh`
cannot see it. Left as found and recorded.

## Session 14 — 2026-09-09

Write-up `MW/D32/DSP/dsp4-floor-20260909.md`. Contract `defs-v2026.09.08.4`,
unchanged. `shipping.config` unchanged. All six staged `~/dspboot` pairs
byte-identical at the end; nothing new staged.

### S14-1 — the core's stall rule, measured, because no document states it

**Severity: informational (it decides every scheduling question on this
part). Status: CLOSED.**

The ADSP-2156x SHARC+ Hardware Reference (Rev 1.0, Dec 2020) has **no core
chapter at all**: zero occurrences of "pipeline stage" or "Instruction
Pipeline" in 101,300 lines, every "stall" in it peripheral flow control,
every "latency" near "compute" a memory or bus latency. It states neither
the pipeline depth nor how many cycles a compute result takes before a
dependent instruction may read it. `src/lib/bq_probe.asm` + `bqprobe.sh`
ask the part instead — 24 rungs of one loop nest whose inner body is the
only thing that differs. Minimum of five repeats:

- instructions issue at **exactly 1.000 cycles** each; a 15-trip hardware
  loop costs **0.402 c/iteration** on top of its body;
- **a COMPUTE result is not readable by the next instruction** — every
  producer→consumer edge between ADJACENT instructions costs exactly one
  extra cycle, identical for mul→mul (0.984), ALU→ALU (0.984) and
  mul↔ALU (0.984);
- **a memory LOAD's result IS readable next instruction, free**;
- the DM bus is not a constraint (two memory moves = 0.009 cycles) and
  neither is the SIMD pair (PEYEN on vs off = 0.000);
- **the PM bus costs +1.068 cycles** against the same access over DM — PM
  data is a pessimisation on this kernel, not a lever;
- a 15-trip loop against a 60-trip one carrying the same iterations:
  0.148 c/iteration.

So S13-5's "~1.47 cycles per instruction" was never a rate: the five-
instruction body is **5 issue + 4 stalls** and the old eight-instruction
one **8 issue + 2 stalls**, which is exactly why removing three
instructions bought 1.073 cycles instead of three.

### S14-2 — the dynamics gain computer: ONE level→gain table is 77 % of it

**Severity: high (cycles). Status: MEASURED, NOT INTEGRATED.**

`src/lib/dyn_shootout.asm` + `dynshoot.sh`, 14 rungs, same envelope and
same gain application throughout. Cycles per sample per channel, paired:

- the gain computer today (6-term polynomial log2 / knee / exp2) **107.6**;
- a 3-term polynomial **74.6**; **one level→gain table 24.5**;
- the whole COMPRESSOR body **142.2 → 59.1** with the table (58.5 % off);
- the whole GATE body **71.1 → 32.5** with a LINEAR-domain threshold.

The gather does not break the pairing: both channels' indices leave SIMD
in ONE store (a direct-address store inside a PEYEN region writes PEy's
word after PEx's) and the four words come back in two paired reads; PEy's
registers survive the excursion, so the interpolation fraction needs no
spill. Dropping the pairing costs **18.0 cycles more**; routing the second
channel over PM costs **6.0 more** rather than saving the two instructions
it removes (S14-1's PM penalty again).

Host-side modelling: index = `leftz` exponent + top *m* mantissa bits, so
the table is log-spaced without computing a logarithm. Uniform spacing
needs *m* = 5 for 0.1 dB; **anchoring a knot at the threshold and both
knee corners buys two levels of *m***, giving 0.030 dB at *m* = 3 with
19–101 words per node (49 for COMP and 20 for LIMITER at shipped
defaults). Quadratic interpolation does not help — the knee corner is a
kink, not a smooth function. The design step is ~211 instructions per
point, so a rebuild is 3–6 % of a whole block for one node: **blend two
tables while a parameter ramps, do not rebuild per block.**

**OPEN RISK:** 96 dynamics nodes × their own table is ~2,420 words at
shipped defaults and ~5,000 at worst case, where a 1,024-word pair already
overflowed `sec_stak` once. The tables would have to live in L2, and the
rig measured a **DM-resident** table — an L2-resident per-sample gather is
unmeasured and could move the 24.5.

### S14-3 — the GATE's static curve cannot be tabled, and does not need to be

**Severity: medium. Status: OPEN (the port is designed, not landed).**

Tabling the gate's curve measures **worse than today** (114.1 against
142.1 c/sample-pair) where the linear-domain threshold gives **65.0**.
The gate's curve is a STEP — unity above threshold, `range` below — and
linear interpolation smears a discontinuity across a whole cell whatever
the mesh: modelled worst error stays at **52–60 dB at every point count
from 2 to 64 per octave**. `log2(env) ≥ thr` is `env ≥ 2^thr`;
`DSP4_GATE_LINTHR` has done that conversion once per block in the SCALAR
kernel since S8. `dsp_codegen.py`'s paired-graph header `#error`s on it
because the two are different arithmetic — by **at most 0.0002 dB of
threshold shift**, a fixed offset, which was worth arguing about against a
0.0001 dB polynomial and is not against the 0.1 dB ruling.

### S14-4 — the paired LIMITER's 4,775 c/blk is conditional compute, not a mystery

**Severity: informational. Status: CLOSED.**

`_lim_pair_blk`'s per-sample body is ≈251 instructions for the pair, of
which **log2 (73) + exp2 (89) = 162, about 65 %**. The scalar kernel
branches around `exp2` on any sample below threshold; the SIMD kernel
cannot, because two channels may want different arms, so `COMPGAIN_SIMD`
computes both transcendentals unconditionally and selects afterwards. That
is why a class with no cascade in it costs more than the EQ and AFB pairs
together. The level→gain table removes the branch problem along with the
polynomials. The GATE's linear-domain trick does not transfer to COMP or
LIMITER — they need the log VALUE for the knee, not just a comparison.

ADI publishes nothing current with source on SHARC dynamics: the 1998
ADSP-21065L "Digital Audio Effects" EZ-KIT had assembly
compressor/expander/limiter; SigmaStudio(+) modules are binaries.

### S14-5 — the biquad primitive: six instructions that do not stall beat five that do

**Severity: high (cycles). Status: LANDED behind `DSP4_BQ_SIMD_PIPE=2`,
default 0.**

Under S14-1's rule the binding resource is the loop-carried dependence
chain y → q1 → w1′ → y: three dependent operations at two cycles an edge =
**six cycles per sample per stage**, against five instructions to issue.
Six slots is the exact floor for a bit-exact schedule and the new one
reaches it. Measured on the part: the old 8-instruction loop **10.415**,
the 5-instruction loop **9.343**, **the six-slot loop 6.409** (1.068
c/instruction — no stall anywhere), against a predicted 6.402.

Bit-exact twice over: `tools/dsp/bq_simd_pipe_check.py` runs all three
schedules register by register over 4,000 cascades × 4 blocks × 16 samples
with zero mismatches; `bqeverify float` on the part is **BQE_VERIFY PASS,
0 ULP over 36,864 words, hash `0xC607BA6B`** — the same hash the other two
schedules produce. At `DSP4_BQ_SIMD_PIPE=0` the pair is `df6b847d` /
`cb9bc58e`, byte for byte the staged `geq_*`.

Below six needs different arithmetic (fold B1 = b1 − a1·b0, B2 = b2 −
a2·b0 at design time for a two-operation recurrence and a four-cycle
floor). Not bit-exact; named, not built.

### S14-6 — RIG B: the IIR accelerator fails at 32 bits, passes at 40, and is too small

**Severity: informational. Status: CLOSED for now.**

The accelerator is a **transposed direct form II** biquad — the same form
this tree already uses — in 32-bit or 40-bit IEEE float, coefficients
stored pre-negated (Ak = b, Bk = −a), no saturation (MAC exceptions
instead). Modelled against the repo's own band design: band 1 (19.95 Hz,
Q 4.3185) at ±12 dB has worst error **0.19–0.21 dB in 32-bit mode** and
**0.0004–0.0014 dB in 40-bit mode**, so it **FAILS the 0.01 dB bar at 32
bits and PASSES at 40**. The cause is stated as an inequality: 1 − r is
1.5e−4 to 7.6e−4 against ε₃₂ = 1.19e−7, and the accelerator stores a1 ≈
−1.9997 **directly** (no offset encoding to dodge the cancellation), so a
2.4e−7 coefficient ulp compounds through 30k–140k samples of ring-down.
Round-to-nearest is required; truncation shows no limit cycle but is
biased with no accuracy benefit.

**Capacity is the harder limit:** coefficient memory is 1440 × 40 bits =
**288 biquads device-wide** (the per-channel 64 and the 32 channels are
not simultaneously achievable). Chip 2's twelve GEQ channels need
**372**, so at most **9 of 12** could run on it at full 31 bands.

### S14-7 — `_proc_cyc_max` still latches, and the instrument's CCLK decode wants checking

**Severity: low. Status: OPEN.**

S13-2 stands unchanged: `_proc_cyc_max` read 376 % on chip 2 on both boots
of an arm with **zero** missed blocks, because nothing resets it after the
config ladder. `DIAG_BLK_OVERRUN` is the arbiter. Separately, `capacity.sh`
decodes the running CGU as **CCLK 983.04 MHz** (budget 327,680
cycles/block) where the P2.2 record of 2026-08-21 measured 491.52 MHz off
the core timer. Every arm in the record is taken with the same decode, so
comparisons between arms are sound either way and the D32 fit verdict
rests on the overrun count — but the absolute percentages are only as good
as the decode, and that has not been re-derived since P2.2.

## Session 13 — 2026-09-09

Write-up `MW/D32/DSP/dsp4-geq-floor-20260909.md`. Contract
`defs-v2026.09.08.4`, unchanged. `blk_*` and `cand_*` byte-identical at the
end of the session; the audio-correct paired pair staged BESIDE them as
`~/dspboot/geq_chip1.ldr` `df6b847d` / `geq_chip2.ldr` `cb9bc58e`.

### S13-1 — the paired chip-2 biquad graph dropped the write UPSTREAM of the latch, not at it

**Severity: high (audio). Status: CLOSED.**

`DSP4_C2_BQ_GRAPH=1` lost every GEQ, ANTI_FB and crossover parameter
change because the pair driver's steady test never read the pending-DESIGN
flag. The generator's own note asserted that "every write to the
coefficients goes through `_<pfx>_coeffs_next_` and
`_<pfx>_swap_pending_`", which holds only for the classes the host writes
COEFFICIENTS to. A GEQ takes 31 band gains, an AFB six notches, a
crossover a corner frequency: the host writes those and sets
`_<pfx>_dirty_`, and the design that turns them into coefficients — and
only then raises `swap_pending` — runs at the top of the NODE BODY, which
is the body the latch exists to skip. Latched, the design never ran, so
`swap_pending` never rose, so the latch never came down, and the pair ran
the `.var` bypass initialisers for ever.

18 of the 24 chip-2 pairs were affected (12 GEQ, 6 AFB); the 6 EQ/OEQ
pairs and the whole of chip 1's `DSP4_BQ_GRAPH` were always correct,
because chip 1 has no design-driven class at all. That is why the S12
candidate read clean and only the arm that fits D32 did not.

FIX: the steady test reads `_<pfx>_dirty_` for any class that has one,
guarded on that class's `DSP4_<CLS>_DESIGN` macro (a DESIGN=0 build has
nothing that clears dirty). Two DM reads and an OR per pair per block, in
`tools/dsp/dsp_codegen.py::gen_bq_pairs_c2`.

WITNESS: geqverify and afbverify design AND live-bank arms at 1–4 ulp with
the switch ON, against IDENTITY and 50.9 M / 83.9 M ulp before; famverify
GEQ and ANTI_FB both LIVE paired, moved 64/64; bqeverify PASS, 0 ulp over
36,864 words. famverify 17/20 LIVE, contract 20/20, three BIT_EXACT.

### S13-2 — D32 fits on an audio-correct image, with 17.5 % of chip 2 spare

**Severity: n/a (measurement). Status: CLOSED.**

`capacity.sh`, two boots per arm, ~135,040 blocks each, `cfg2 0xC201024F`
read back on the part. D32 all-ones on the audio-correct paired pair: chip
2 **82.06 / 82.49 %**, chip 1 76.73 / 76.96 %, **zero overruns**. D24 mask:
chip 1 59.2 %, chip 2 67.6–67.9 %, zero overruns. Against S12's candidate
at D32 chip 2 102.5–102.7 % with 2.37 % of blocks missed.

`_proc_cyc_max` IS NOT TRUSTWORTHY ACROSS BOOTS and its definition says
why: "the worst block pass seen since reset", and nothing resets it after
the boot and config ladder, so it latches a one-off configuration-block
transient. The same image read 71.29 % on one boot and 367.58 % on the
next with zero overruns on both. `DIAG_BLK_OVERRUN` is the arbiter.
Resetting the counter after config would make the column mean what its
name says; not done.

### S13-3 — S12-9 was the instrument: `mode 1` was an impulse TRAIN on every block-kernel image

**Severity: high (instrument). Status: CLOSED.**

afbverify's −18 dB notch measured −4.799 dB and geqverify's +12 dB band
+8.451 dB on EVERY block-kernel image, scalar and paired alike, where the
same bars read −17.99989 dB on the per-sample block-8 image of 2026-09-08.

`_scope_inject_blk` runs once per BLOCK and drove the amplitude into
sample 0 every time it ran, so `mode 1` was not an impulse but an impulse
TRAIN at one per block — 3 kHz at block 16 — and the audio arms measured
that train's periodic steady state. The raw capture shows exactly 64
non-zero words in 1024, at indices 0, 16, 32, … Modelling the train
through the same designed cascade reproduces all three of geqverify's
points to three decimals: +0.219 / +8.451 / −0.305 measured, +0.219 /
+8.451 / −0.305 modelled. **The audio was never in question.**

The per-sample injector has always had the gate (`_scope_go == 0` is the
first sample of the run). The block injector cannot borrow it: under block
kernels BOTH injectors run in every block and the per-sample one raises
`_scope_go` first, so gating on it silences the block injector completely
(measured — an all-zero capture). It gets `_scope_fired`, cleared by the
same arm write.

AFTER: geqverify **+11.997 dB** against a +12.000 model and afbverify
**−18.000** against −18.000 — GEQ_DESIGN_OK and AFB_DESIGN_OK on the
shipping configuration AND on the paired arm. famverify unchanged.

OPEN, recorded not fixed: geqverify's flat negative control prints
"64/64 samples equal to the input" when both captures are all zeros. It
did not mislead (the verdict also requires `peak > 0`), but the line is
not evidence on its own.

### S13-4 — S12-8: the crossover's LP/HP legs were registered with no witness

**Severity: medium (instrument). Status: CLOSED for the stall; the audio arm is declared NOT SCORABLE.**

`_buf_lp_<nid>` and `_buf_hp_<nid>` are ONE-WORD variables — under block
kernels the crossover runs its per-sample body BLOCK times through them
and there is no `_blk_lp_` array — and nothing registered them with the
block-aware witness, so xoververify armed on an address no tap answered
for and waited for a buffer that never filled. They now get
`_scope_tap1`, the one-word-per-block witness TALKBACK and NOISE_GEN use.

The bar reaches a verdict and its design arms pass: 1–4 ulp staged, live
== staged, LP and HP both −6.021 dB at the corner, response error
≤ 0.00013 dB, LP+HP flat to 0.00013 dB, across BOTH LR alignments and all
five corners, with the non-LR slopes correctly leaving the coefficients
unmoved.

Its AUDIO arm is declared NOT SCORABLE rather than scored wrong: a
one-word-per-block witness samples at 3000 Hz and a single impulse falls
in the fifteen samples of sixteen it does not keep, so the reference reads
zero. Scoring it needs a `_blk_lp_`/`_blk_hp_` array in the crossover's
block kernel — a change to the SHIPPING image for a bench instrument, not
taken.

### S13-5 — GEQ is the wall on chip 2: 6.03 c/band-sample, 11.0 % of budget in the aux GEQs alone

**Severity: n/a (measurement). Status: CLOSED.**

`sigprofile2.sh`, D32 all-ones graph, paired arm, two boots per point,
minimum taken, one whole aux strip pair stepped node by node:

| node | cycles/block | % budget | c/band-sample |
|---|--:|--:|--:|
| AUX_FDR x2 | 323 + 317 | 0.20 % | — |
| PAIR_AUX_EQ (2 x 4-stage) | 1,111 | 0.34 % | 8.68 |
| **PAIR_AUX_GEQ (2 x 31-band)** | **5,983** | **1.83 %** | **6.03** |
| PAIR_AUX_AFB (2 x 6-notch) | 1,468 | 0.45 % | 7.65 |
| PAIR_AUX_LIM | 4,775 | 1.46 % | — |
| AUX_DLY | 2,251 | 0.69 % | — |
| AUX_OUT + MTR_AUX | 242 | 0.07 % | — |

The graph and the shootout rig agree on the primitive to 1.5 % (6.03 against
5.94), which is what makes the table believable. Six aux pairs are 113,778
cycles/block = 34.7 % of budget and 42.3 % of chip 2's 268,893; the six aux
GEQ pairs alone are 35,898 = 11.0 % of budget.

UNEXPECTED, not chased: PAIR_AUX_LIM at 4,775 cycles/block is bigger than
the EQ and AFB pairs together — 8.7 % of budget over six pairs, for a class
with no cascade in it. The obvious next question after the primitive.

CAVEAT from the instrument's own header: chip 2 is never configured under
`sigprofile2.sh`, so cascades run at bypass coefficients (cost is
coefficient-independent) and dynamics at compiled defaults, which makes the
LIMITER figure the branch this graph takes rather than a worst case.

### S13-6 — the biquad primitive is NOT instruction-count-bound, and that invalidates the 3.75 target

**Severity: high (it redirects the whole GEQ programme). Status: OPEN — the cause is unmeasured.**

The float SIMD inner loop was pipelined 8 instructions per sample per stage
to 5, behind `DSP4_BQ_SIMD_PIPE` (default 0; built at 0 the pair is
`df6b847d` / `cb9bc58e`, byte for byte the staged `geq_*` pair). The
schedule fits the dual-compute operand map — multiplier X from R0-R3 and Y
from R4-R7, ALU X from R8-R11 and Y from R12-R15, read off `easm21k`, which
rejects `f15 = f2 * f1, f8 = f11 - f14, dm(i3,2) = f1` with "Semantic Error
in type 4 instruction". Five products need x and y both in R0-R3 and would
need five coefficients in the four registers R4-R7, so one multiply can
never pair; that is why the old loop had two standalone multiplies.

**It is bit-exact and it does not buy what the instruction count says.**
`bqeverify` PASSES on the pipelined arm at 0 ULP over 36,864 words with
hash `0xC607BA6B` — the same hash the unpipelined kernel produces. But on
the same ladder point the GEQ pair goes 5,983 -> 5,655 cycles/block, 6.031
-> 5.701 c/band-sample: **5.5 %, where 8 -> 5 instructions predicts 25 %.**
A stall-free five-instruction loop would be 4,495 cycles. Capacity at D32
moves chip 2 from 82.06 / 82.49 % to 80.79 / 80.98 %, zero overruns.

**The loop is running at ~1.47 cycles per instruction, and the same
arithmetic gives ~1.4 for the unpipelined loop.** Instruction count is
therefore not the binding resource on this kernel, and the `max(5 multiplies,
4 ALU, 2 moves) = 5` floor that both the 2026-09-02 3.75 estimate and this
session's schedule were built on is wrong. Candidates not yet
distinguished: float result latency the old loop's slack was absorbing, a DM
bus conflict between the three index registers walking DM at once, or PM
fetch.

NEXT, and it is not more scheduling: a per-instruction cycle probe on the
shootout rig — one instruction added at a time to an empty loop — until the
1.4-1.5 shows up and names itself. The kernel stays in the tree at default
0: bit-exact, a real 5.5 %, not worth adopting ahead of knowing why it is
not 25 %.

### S13-7 — RIG B not reached

**Severity: n/a. Status: OPEN.**

The 2156x IIR accelerator was not brought up. The precision test that
decides it is unchanged: band 1 (19.95 Hz, Q 4.3185) and band 2 at ±12 dB
in the accelerator's float32 against `bq_float_ref`, inside the 0.01 dB
bar or not.

## Session 12 — 2026-09-09

### S12-1 — the certifying witness now links beside the paired kernels, in a second code overflow region

**Severity: medium (instrument). Status: CLOSED.**

`DSP4_SCOPE_BLK_TAP=1` with `DSP4_STRIP_FUSED=1 DSP4_SIMD_DYN=1` would not
link: chip 1's code fills Block 3 to within **2 bytes** and Block 2 to
within **0x134c**, and the witness costs **+2,976 words** in the generated
chain plus **+155** in `scope.asm`, leaving **0x63e words unmapped** — the
linker reports the same remainder once for `sec_swco` and once for
`sec_swco_ovf`, so the real shortfall is **799 words / 1,598 bytes**.

Read out of the link map rather than guessed: at the point of failure Block
1 had **0x193f8 bytes free** and nothing was allowed to reach it, because
the LDF gave code exactly two regions. `ADSP-21564.ldf` gains
`sec_swco_ovf2 > mem_block1_bw`, declared **after** `sec_dmda_ovf`,
`sec_dmda_c_bw_ovf` and `sec_dma`, so the DM overflow and the DMA
ping-pong buffers take what they need first and code gets only the
leftover. The chip-1 candidate places **0x31f words** there; chip 2 never
reaches it.

Inert when not needed, and checked rather than asserted: the default pair
rebuilt across the change is byte-identical — `a95fd8eb…` / `fb1eee67…`,
the same pair the tree built before it. The cost is stated where it lands:
instruction fetch from Block 1 runs against DDE traffic, which is a TIMING
price on an instrument build. **No capacity number in this session is taken
from a build that reaches `sec_swco_ovf2`.**

### S12-2 — the scope tap found pair drivers with a regex, and chip 2's pairs are not called what chip 1's are

**Severity: HIGH (instrument). Status: CLOSED.**

The tap pass matched
`_(DYNGATE|DYNCOMP|BQPFILT|BQPEQ)_nn_mm_process` — chip 1's four driver
names. Chip 2's drivers are `_C2PAIR_AUX_LIM_01_02_process`,
`_C2BQP_MOUT_OEQ_01_02_process`, `_C2PAIR_MSUB_LIM_process` and their
kind, so **the pass matched none of them** and every chip-2 node run by a
pair went untapped: in the `DSP4_C2_BQ_PAIRED_GRAPH` chain the tap count
was **124** against the scalar chain's **200**.

Measured on the part: the paired candidate read **ANTI_FB, CROSSOVER, GEQ
and LIMITER as NO_CAPTURE** — the scope was armed on a node with no tap in
that chain, so the capture never completed and the read timed out — while
every *unpaired* chip-2 family (FX_ENGINE, MONITOR) on the same image read
LIVE. That is S9-5's shape a third time: an instrument silent about
exactly the thing it was built to watch.

The fix is not a better regex. `pair_members` is now filled in by the four
call emitters themselves, so a driver that is called is a driver the
witness knows the members of, whatever it is named, and adding a fifth
kind of pair cannot silently drop off. With it, the same image reads 204
taps in the paired chain and the four families capture.

### S12-3 — a pair driver does not always publish where its class's scalar kernel does

**Severity: HIGH (instrument). Status: CLOSED.**

`_STRIP_BLK_OUT` is a fact about the SCALAR body, and the tap was using it
for paired call sites too. The chip-1 pair drivers are squared up to one
convention — channel A out in `BLK_CHAIN_B_P1`, channel B out in
`BLK_CHAIN_B`. For COMP, FILT and EQ that is the same slot the scalar
kernel uses, so the difference was invisible. **GATE is the exception:**
its scalar kernel publishes into `BLK_CHAIN_A` (`A_P1` on the odd strip)
and `_DYNGATE_nn_mm_process` publishes into `B_P1`/`B`.

On the part the GATE family therefore read **INERT on the paired
candidate — moved 0 of 64, peak exactly the injected `0x08000000` both
sides of the step**, because the tap was copying the block the gate had
READ, while COMPRESSOR, HPF_LPF and EQ_BIQUAD read LIVE on the same image.
A `_PAIR_BLK_OUT` table now answers for paired call sites, and the tap
raises rather than guesses if a paired node is witnessed at something that
is not a pool slot. GATE reads **LIVE** with it.

### S12-4 — the numeric arm injected into the pool the odd strip does not read

**Severity: HIGH (instrument). Status: CLOSED.**

`dsp4_node_verify.inject_addr()` returns `_blk_pool` for any block build.
A paired build gives the ODD strip of each pair a whole second pool
(`_blk_pool1`, blk_pool.h) because both strips of a pair must hold live
chain blocks at once — and the bar drives **strip 1**, which is odd. So
every stimulus the numeric arm injected on the paired candidate went into
a slot that strip never reads: `_buf_C1_IN_01` through `_buf_C1_FDR_01`
all captured **peak 0x00000001**, and COMPRESSOR, FADER_PAN and TUBE_SAT
reported **NO_STIMULUS** on an image whose audio arm read every one of
them LIVE. S9-5's second half, restated for the paired graph.

`inject_addr` resolves `_blk_pool1` for an odd strip when the symbol
exists; it only exists in a paired build, so an unpaired image resolves
exactly as it always did. With it the three families read **BIT_EXACT**.

### S12-5 — SIMD_DYN is audio-correct; `DSP4_C2_BQ_GRAPH` is not

**Severity: HIGH (audio). Status: CLOSED by S13-1 (2026-09-09) — the chip-2
aux biquad pair was fixed, with the mechanism named and three witnesses.
Status corrected 2026-09-10, S20-1: this line read OPEN for a day after the
defect it describes was closed, and S19 read it and withheld the
recommendation its own measurements supported.**

With the three instrument defects above fixed, `DSP4_STRIP_FUSED=1
DSP4_SIMD_DYN=1 DSP4_C2_BQ_GRAPH=0` reads **verdict-for-verdict identical
to the shipping configuration**: 17 of 20 families LIVE, contract 20/20
with 0 FAILED, COMPRESSOR / FADER_PAN / TUBE_SAT **BIT_EXACT**, GATE's
numeric arm NO_STIMULUS exactly as the shipping arm reports it. The
paired dynamics, the pair-ordered chain, the odd pool, chip 1's paired
biquads and chip 2's paired *dynamics* are all clean.

**`DSP4_C2_BQ_PAIRED_GRAPH` — chip 2's paired AUX biquads — is not.** With
it on, on the same image, in the same session, on the same bench:

| family | witness | C2 biquads PAIRED | C2 biquads SCALAR |
|---|---|---|---|
| GEQ | `_buf_C2_AUX_GEQ_01` | peak `0x08000000` -> `0x08000000`, **moved 0/64** — INERT | peak `0x08000000` -> `0x082DE520`, moved 64/64 — LIVE |
| ANTI_FB | `_buf_C2_AUX_AFB_01` | peak `0x08000000` -> `0x08000000`, **moved 0/64** — INERT | peak `0x08000000` -> `0x07FB92D0`, moved 64/64 — LIVE |
| CROSSOVER | `_buf_C2_MAIN_OEQ_01` | peak `0x07E960D0` -> `0x074AF178`, moved 64/64 — LIVE | LIVE, identical numbers |

It is not the witness: the address is the node's own `_blk_<nid>` array in
both arms, the unpaired arm proves that address is right, and
`_C2BQP_MOUT_OEQ_01_02` moves its block on the same image.

**THE MECHANISM IS NAMED, by two independent bars that read the
COEFFICIENT BANK rather than the audio.** On candA, `geqverify` and
`afbverify` both report the node's own live bank still at IDENTITY after
the host has written the parameters:

| bar | live bank | worst coefficient error | modelled response error | live tone |
|---|---|---|---|---|
| `geqverify` | `_geq_coeffs_A_C2_AUX_GEQ_01` | 50,965,640 ulp (word 89) | **-12.00000 dB** — the whole designed band gain | +0.000 dB at every point |
| `afbverify` | `_afb_coeffs_A_C2_AUX_AFB_01` | 83,887,018 ulp (word 1) | **+18.00000 dB** — the whole designed notch | +0.000 dB at every point |

The same two bars on the same image with `DSP4_C2_BQ_GRAPH=0` read those
banks correct to **1-3 ulp**. So on a paired chip-2 build **a GEQ band gain
and an AFB notch gain never become coefficients at all**; the node is
called, it runs, and it has nothing to apply. That rules out the
alternative this finding first left open — that the node is simply not in
the paired chain — and it locates the fault in the parameter-to-coefficient
path under `DSP4_C2_BQ_PAIRED_GRAPH`, not in the pair kernel's arithmetic.
Which side of the latch drops the write (the node's own design step never
running, or running into the interleaved copy) is the one thing still to
settle, and it is now a one-arm question.

### S12-6 — two chip-2 nodes are not called at all in the dynamics-only paired chain

**Severity: medium (audio, control arm). Status: OPEN.**

`_C2_CODEC_AUX_OUT_process` and `_C2_MAIN_ST_OUT_process` are called in the
scalar chip-2 chain and in the `DSP4_C2_BQ_PAIRED_GRAPH` chain, and **not
at all** in the `DSP4_PAIRED_GRAPH`-only chain (`c2grun`) — 198 tapped
nodes there against 200 in the other two. That arm is the one the
240,681-cycle chip-2 figure was measured on, so the figure is missing two
nodes of work as well as being an arm nothing ships. Found by counting
taps per chain variant, not by a bench run; not chased this session.

### S12-7 — `DIAG_BUILD_CFG2` does not carry the graph switches, and two images that differ in AUDIO read the same word

**Severity: medium (record). Status: OPEN.**

`DIAG_BUILD_CFG2` carries the decimation factor, `DSP4_STRIP_FUSED`,
`DSP4_SIMD_DYN`, `DSP4_SIMD_GRAPH`, `DSP4_SIMD_STRIPS`,
`DSP4_SCOPE_BLK_TAP`, `DSP4_TX_EARLY`, `DSP4_GATHER_FIRST` and
`DSP4_FX_TYPE_DECLARED`. It does **not** carry `DSP4_BQ_GRAPH` or
`DSP4_C2_BQ_GRAPH`.

So the two candidate images of this session — one of which loses parameter
changes on chip 2's aux biquads (S12-5) and one of which does not — both
read back **`0xC201004F`**, and a bench holding one of them cannot tell
which it has. That is S8-2's shape in the word that was added to end
S8-2's shape. Bits 5 and 10 of the second word are free.

Not fixed here: adding them changes the value a shipping image reads back
and therefore the default pair's bytes for the third time this week, and
the two switches are named in `shipping.config` in the meantime.

### S12-8 — four of the six design bars were reading a block-kernel image through the pre-block witness

**Severity: HIGH (instrument). Status: CLOSED for the bars run here, OPEN as a default.**

`fxverify.sh`, `afbverify.sh`, `geqverify.sh` and `xoververify.sh` arm the
scope on `_buf_<node>` and none of them sets `DSP4_SCOPE_BLK_TAP`. S11-5
found and fixed exactly this in `famverify.sh` and the fix was not carried
to the others.

Measured this session, same configuration, one variable: on the staged
shipping pair `ac65ad38…`/`e5dce9e4…` — no tap — `fxverify` reports

    input at _buf_C2_RECV_FX_01: peak 0.000000 at sample -1
    INPUT SILENT — no verdict is possible from this run

and exits 1. On the same configuration rebuilt with the tap
(`25f0a532…`/`9d713603…`) the same bar runs to **FX_VERIFY_OK**, every
sub-check PASS. The bar was not failing; it was reading a one-word `.var`
the chip-2 block kernels never write, and reporting that as silence.

All six bars in this session were run on tap-enabled images, and the four
scripts now **default the tap ON**, the way `famverify.sh` has since S11-5:
`export DSP4_SCOPE_BLK_TAP="${DSP4_SCOPE_BLK_TAP:-1}"`, with
`DSP4_SCOPE_BLK_TAP=0` left as the control that reproduces the old reading.
Leaving a default that is known to produce a confident wrong answer is the
thing this session spent most of its time undoing.

It does NOT rescue `xoververify`, which stalls for a different reason — it
arms on `_buf_lp_<nid>`, an address the tap does not cover at all (S12-2's
class, in a bar). That one is still open.

### S12-9 — `afbverify`'s live tone arm fails on the pair that ships, and it passed on 2026-09-08

**Severity: HIGH if it is the audio, medium if it is the capture. Status: OPEN, not attributed.**

Run on the staged shipping pair (`blk_*`, rebuilt with the tap), the
anti-feedback bar's DESIGN arms all pass — five parameter sets, worst
4 ulp on the coefficients, worst response error 0.00009 dB against a
0.050 dB bar. Its LIVE tone arm does not:

| point | 2026-09-08 | this session, `blk_*` | model |
|---|---|---|---|
| 250 Hz, two below | −0.0374 dB | −0.1927 dB | −0.0374 |
| **1 kHz, notch centre** | **−17.99989 dB** | **−4.7987 dB** | **−18.000** |
| 4 kHz, two above | −0.0358 dB | +0.2386 dB | −0.0358 |

`AFB_DESIGN_OK` then, `AFB_DESIGN_FAIL` now, same bar, same node, same
contract pin. The 09-08 image is a PER-SAMPLE, block-8, 491.52 MHz build;
`blk_*` is the block-kernel, block-16, 983.04 MHz pair. Nothing between
them was an AFB change.

Two readings fit and this session did not separate them:

* **The audio.** The notch is genuinely reaching about a quarter of its
  designed depth in the pair that ships.
* **The capture.** The 1024-sample window is assembled from 64 consecutive
  `_scope_tap` block copies. If those copies are not consecutive IN TIME,
  the tone's phase jumps between blocks, which spreads energy and raises
  the measured level at the notch — and would also account for the
  0.15–0.27 dB error at the two passband points, which no filter change
  explains.

The passband drift is the tell and it points at the capture, but "points
at" is not a measurement. **Separating them is one arm**: the same bar on
the same image with a stimulus that is coherent block-to-block, or a
capture that verifies its own block continuity. It is not
candidate-specific — it is the shipping pair.

### S12-10 — the latency tool's margin guard has a hole, and it swallowed a whole arm

**Severity: HIGH (instrument). Status: CLOSED.**

`dsp4_dsp_latency.py` warns when the winning offset's margin over the
runner-up is under 2x. When the runner-up is **0.0** the margin computes as
**infinite**, so `worst < 2.0` is false and a run in which NOTHING
correlated with the stimulus prints a clean-looking summary. S11-6 fixed
the CAUSE of that signature — the missing `dsp4_passthru_setup.py` — and
left the reporting hole open.

It returned on 2026-09-09. Both candidate arms, with and without
`DSP4_TX_EARLY=2`, read **offset 14779 on all 20 reps of both boots,
spread 0, coherent fraction 0.0 %** — S11-6's signature exactly, with the
pass-through setup demonstrably running (`chip2: 12 cells written, all
present in the contract`, main-bus sources at `0x0`).

**The control is what settles it: the same arm on the staged shipping pair
`blk_*` reads the identical 14779 / 0.0 %.** The instrument is at fault and
the candidate is uninvolved — so no latency figure was taken this session
and S11's 66 samples / 1.375 ms at block 16 is not overwritten with a null.

Cause, from the bench state: the through-DSP arm needs the `_maincap`
bitstream AND a duplex PCM overlay. The bench lives on `dsp4-pcm-slave`,
where the capture device exists and returns audio that is not the DSP's
output — a well-formed capture with nothing in it. S11 measured
successfully because it flipped to the duplex overlay and restored
afterwards (`config.txt.s11bak`); that flip is a `config.txt` line and a
REBOOT and was not taken here.

`dsp4_dsp_latency.py` now refuses the verdict when the coherent fraction is
0.0 % on every rep, exits 2, and names the capture-path requirement in the
message.
