provenance: AI-drafted 2026-08-30 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# The DSP4 boot+config intermittent, measured (2026-08-30, session 13)

The standing "intermittent boot+config failure" has been on the record
since session 5, every bench script in the tree carries a retry loop for
it, and it has been blamed for four sessions of debugging that turned out
to be about something else. It had never been measured. This is the
measurement, and the mechanism that came out of it.

**Summary.** The boot half does not fail. The failure is one lost
transaction in the CONFIG_COMMIT burst, the per-cycle rate is a couple of
percent rather than the ~25 % on the record, and the thing that eats the
transaction is a recovery routine this firmware added on 2026-08-22 to
clean stale fragments out of the SPI2 receive FIFO — it cannot tell a
stale fragment from a request that is merely in flight.

---

## 1. The instrument: one attempt per cycle, every cycle recorded

`tools/pi/dsp4_bootchar.py` (new) drives `dsp4_boot.py`'s own functions
rather than shelling out, so the reset pulse, the settle, the stream and
the per-chip elapsed time are all under its control. Per cycle it records
the !RST_D pulse, per-chip boot elapsed and whether the single attempt
raised, both chips' SPI_RDY levels before and after the stream, a
**pre-config** diag sweep of both chips, ONE config pass with no retry, a
**post-config** sweep, and — for any cycle that did not reach stage 6 — a
**recheck** sweep some seconds later, which is what answers "does a
wedged cycle ever recover unaided?". `MW/D32/DSP/SHARC/bootchar.sh` is
the host wrapper; `bootchar_run.sh` carries the same inline remote bench
lock as `sigprofile_run.sh`.

The image under test is a two-strip, self-test-free build at 983.04 MHz.
The shipping 32-strip image cannot be used for this: it is far over the
per-block budget and parks at BOOT_STAGE 5 by design, which is one of the
two failure codes under investigation.

## 2. The boot half never failed

**286 one-attempt cycles, 572 chip boots, zero boot failures.** Every
cycle across every arm of this session reached BOOT_STAGE 5 on BOTH chips
with MAGIC and CHIP_ID correct before any config was written. The cycles are near-identical:

| quantity | value across 32 baseline cycles |
|---|---|
| chip 1 stream elapsed | 495.6 ms ± 0.2 (min 492.1, max 495.8) |
| chip 2 stream elapsed | 254.1 ms ± 0.1 |
| SPI_RDY chip 1 / chip 2 before the stream | 0 / 0, all 32 |
| SPI_RDY chip 1 after the stream | 1, all 32 |
| chip 1 FRAME_COUNT at the pre-config probe | 31581 ± 1 |
| chip 1 TICKS at the pre-config probe | 2633, 31 of 32 |
| chip 1 SPI_RX_COUNT at the pre-config probe | 16, all 32 |

There is no precursor. Up to the moment the host starts writing config,
a cycle that is about to fail is indistinguishable from one that is not.

This also retires the collision model in `dsp4_boot.py`'s own docstring
as a description of *today's* bench: at 10 MHz the chip-1 stream occupies
495 ms, which that model scores as ~100 % collision risk against
H1S1's ~260 ms meter-poll period, and the stream nevertheless landed
572 times out of 572 with `--sync-poll` off. Whatever that model
described in August, it is not what limits this bench now.

## 3. The failure is at CONFIG_COMMIT, and there are TWO of them

Two distinct failures turned up, and the record has been treating them as
one because every bench script reads BOOT_STAGE and nothing else.

### 3a. BOOT_STAGE 5 — the commit transaction is lost

The part is **alive and answering**. Everything reads correctly:

```
cycle 8   pre1  magic D5B40001  id 1  stage 5  cfg 0  frames 31578  rx 16
          post1 magic D5B40001  id 1  stage 5  cfg 0  pid 1  rx 103  err 0
          rechk magic D5B40001  id 1  stage 5  cfg 0  pid 1  rx 140
          host: "51 writes", no error
```

`PRODUCT_ID` reads **1**, so the config burst reached the DSP's config
dispatcher and its first write landed. `BOOT_CFG` reads **0** and
`CFG_PHASE` reads **0**, so `_product_config_commit` never executed.
`SPI_ERR_COUNT` reads **0**, so nothing landed on an unmapped address —
this is not a mis-addressed write.

`SPI_RX_COUNT` is what names it. A clean cycle reads **104** at that
point in the probe (37 pre-probe transactions + 51 config writes + 16
into the post-probe). This cycle read **103**: the DSP assembled exactly
**one request fewer than the host sent**, and the state says which one.
The lost request is CONFIG_COMMIT.

### 3b. BOOT_STAGE 0 — the core has stopped

The other failure looks nothing like it. Every diag register on chip 1
reads 0, *including MAGIC*, which is a constant compiled into the image;
the recheck 15 s later is identical, so it does not recover unaided; and
chip 2 — same reset, same bus, same stream — stays healthy with
FRAME_COUNT advancing 30,136 → 48,295 → 138,381.

A part that answers nothing is a part whose **core has stopped**, not one
whose main loop is merely starved. That follows from the firmware: since
2026-08-23 the 1 kHz timer ISR services the parameter link as a backstop
(`diag.asm`, gated on boot stage ≥ DIAG_STAGE_DMA), so a main loop that
cannot finish a block still answers at 1 kHz. Silence means the tick is
dead too. The reading that `main.asm` attaches to "BOOT_STAGE read 0" —
"the signature of a main loop that can no longer finish a block" — does
not survive its own backstop.

## 4. What the wedged part is actually doing on the wire

What is MEASURED is that every register returned 0 with the echo check
passing, on a part that had answered correctly seconds earlier. What
follows is the inference that fits it, and it is an inference: a stopped
core leaves the SPI2 peripheral shifting with nothing ever loading its TX
FIFO, and the read protocol accepts the result. `DiagLink.read` asks with
`{addr|READ, 0}` and then collects with `{NOP, 0}`; a slave whose MISO
carries the host's PREVIOUS transaction hands the collect `(want0, 0)` —
the echo matches and the value is zero, for every register in turn. That
is the only arrangement of the two words that passes the check while
returning nothing, so it is what a starved slave must be doing, but it
has not been seen on a scope or a bus capture. `dsp4_cfgstress.py --raw`
exists to dump the literal MOSI/MISO of four distinct transactions from a
wedged part; it never fired, because the amplifier it lives in never
reproduced the wedge (section 6). Wiring the same dump into
`dsp4_bootchar.py`'s failure path would settle it.

That is not a new observation, it is one the firmware already made and
the tooling never acted on: `main.asm` says "a dropped answer comes back
as a well-formed (echo, 0) — a wrong value that cannot be told from a
real one", and `diag.h` records a bench capture where "a gain coefficient
[read] as 0xE0FE0000, which is the DIAG_NOP request word echoing back".

**Consequence for the record: BOOT_STAGE 0 read on its own is not
evidence of a wedge.** It is equally the signature of a lost answer.
Caught live on a healthy part during this session (watch arm cycle 22): a
part at BOOT_STAGE 7 with the commit demonstrably applied returned 0 for
a contiguous tail of seven registers within one probe, PRODUCT_ID
included, having answered MAGIC, CHIP_ID and BOOT_STAGE correctly moments
earlier in the same sweep. Roughly one probe in fifty. MAGIC read in the
same sweep separates the two cases; no bench script did that.

## 5. The mechanism: the stuck-partial-request recovery eats a live word

`_diag_timer_isr` has carried this since 2026-08-22 (`diag.asm`):

> A parameter request is TWO words and `_spi2_rx_work` only drains when
> SPI_RFIFO is FULL, so a single stale word left in the FIFO wedges the
> link permanently. […] A real request only sits half-arrived for
> microseconds, so three consecutive 1 ms ticks in that state means
> stale. Discard one word.

The premise — "a real request only sits half-arrived for microseconds" —
is true of one request and false of a burst. The host's config pass is
**51 back-to-back transactions**; at 1 MHz each word occupies 32 µs and
each transaction is followed by Python and gpiod overhead, so the burst
occupies tens of milliseconds and presents the RX FIFO part-full over and
over. `_spi_partial_ticks` is only reset when a tick finds the FIFO
*empty* or *full*, so three ticks that each land inside a second word —
which a 1 kHz tick beating against a ~1 ms host cadence will do — arm the
discard on a request that is perfectly healthy and still arriving.

`_spi_partial_fix` counts how often the discard fired. It was `.global`
but **not in the diag table**, i.e. unreadable off the part, for the
entire life of the defect. Published this session as 0xE01F under
`DSP4_CFG_WATCH`, it says the rest immediately:

| cycle | verdict | SPI_PART_FIX | SPI_RX_COUNT | CFG_PHASE | BOOT_CFG |
|---|---|---|---|---|---|
| typical clean | OK, stage 7 | 0 or 3 | **108** | 5 | 1 |
| pfix0 arm, cycle 11 | WEDGE_STAGE5 | **2** | **107** | **0** | **0** |

The arithmetic closes exactly, and the PARITY of the discard count is
what decides which symptom you get.

**An even number of discards inside the burst deletes whole requests and
leaves the framing intact.** 51 requests are 102 words; the two discards
this cycle counted leave 100, which assemble into 50 complete requests —
`SPI_RX_COUNT` one short, exactly as measured — with every surviving pair
still (address, value). That is why `SPI_ERR_COUNT` reads **0**: nothing
was mis-addressed, one request simply never existed. The request that
goes missing is the one at the end of the burst, CONFIG_COMMIT.

**An odd number shifts the framing, and that is the 2026-08-28 finding.**
The survivor of a discarded pair joins the next transaction's first word,
so the handler reads a *value* word as an address and an *address* word
as a value — which is precisely how `0xF0040000`, CONFIG_COMMIT's own
header word, ended up written into `_gain_coeff`/`_gain_target` of
`C1_GAIN_01` at "about one boot in three". One defect, two symptoms,
selected by parity.

A discard that lands on genuine residue outside the burst (the
`pfix = 3` clean cycles) costs nothing and is invisible either way.

## 6. What was excluded, by measurement

**The CGU relock is not it.** `_cgu_raise_cclk` is called from inside the
SPI RX interrupt by CONFIG_COMMIT and contains four **unbounded**
spin-waits on `CGU0_STAT` — the only unbounded loops anywhere in the
commit path, and exactly the shape that stops a core dead. `DSP4_CFG_WATCH`
(new, default 0) bounds all four at 4,194,304 iterations, stamps which one
expired, and publishes how many iterations each actually takes. Over 48
one-attempt cycles:

```
wait 1  (PLL bypass asserted)   1 iteration,  every cycle
wait 2  (bypass released)       51-56 iterations
wait 3  (clocks aligned)        0 iterations
wait 4  (DIV update taken)      0 iterations
CGU_FAIL                        0, every cycle
CFG_PHASE                       5 (commit complete), every cycle
```

A margin of roughly 75,000× against the watchdog limit, and the watchdog
never fired. Recorded honestly: those 48 cycles were all clean, so this
excludes the CGU for the normal case and does not yet convict or clear it
for a stage-0 wedge.

**The commit path itself is not it.** `dsp4_cfgstress.py` (new) boots
once and then repeats the commit against already-good patch registers,
and separately repeats the whole 51-write sequence. **0 wedges in 200
commits and 0 in 200 full sequences.** Re-running the commit code on a
part that is already at stage 7 does not reproduce the failure — the
failure needs the FIRST commit, out of `.wait_boot`, at the end of a
fresh burst.

**Per-read answer drops are not a steady-state artefact.**
`dsp4_readvote.py` (new) hammers registers whose correct value cannot be
0 on a part known healthy: **0 zeros in 3,600 reads**, and single, vote-2
and vote-3 host policies score identically. The (echo, 0) artefact is
per-burst and transient, not a background per-read rate.

## 7. The fix

`DSP4_SPI_PARTIAL_FIX2` (new, default 0) arms the recovery only while the
parameter link is standing still. The discriminator was already in the
original bug's own evidence: when the link was genuinely stuck on
2026-08-22, "SEC_COUNT and SPI_RX_COUNT frozen at 74". A live burst
always advances `_spi_rx_count` between ticks; residue never does. The
recovery now compares the request counter against its value at the
previous part-full tick and restarts the dwell whenever it has moved, so
a burst in flight can no longer be mistaken for a stale fragment. Genuine
residue is still cleared, one tick later than before.

Six instructions, behind a default-0 flag because it changes the shipping
image.

**Measured, 150 one-attempt cycles on the fixed path against 136 on the
unfixed one, same instrument, same settle, same image family:**

| | unfixed (136 cycles) | fixed (150 cycles) | Fisher exact |
|---|---|---|---|
| `SPI_PART_FIX` fired during the cycle | **4 of the 24 cycles where it was readable** (2 or 3 discards) | **0 of 150** | **p = 2.9 × 10⁻⁴** |
| D71, commit lost (WEDGE_STAGE5) | 2 | **0** | p = 0.23 |
| D73, core stopped (STAGE0 / LINK) | 2 | 1 | p = 0.46 |
| any failure | 4 (2.94 % [1.15, 7.32]) | 1 (0.67 % [0.12, 3.68]) | p = 0.16 |
| `SPI_RX_COUNT` at the post-config probe | 107 once, else 108 | **108 on all 149 that answered** | |

**Read this the right way round. The rate comparison on its own does not
prove anything** — at a per-cycle rate near 1.5 % for the D71 mode, 150
clean cycles is p = 0.23, and saying otherwise would be the same
arithmetic error that produced "~2 in 8" from eight cycles. **The
mechanism comparison is what carries it**: the discard is the only thing
that can remove a word from the burst, it fired on one cycle in six
before and on none of 150 after, and every fixed cycle that answered
assembled the full 108 requests. Zero D71 events in 150 cycles is
consistent with that and does not stand alone.

**D73 is untouched, exactly as expected** — the fix addresses the lost
transaction, not the stopped core — and the one failure on the fixed path
is a D73: chip 1 healthy at BOOT_STAGE 5 before config, the post-config
probe getting no answer at all, the recheck reading all zeros with
RESP_DROP 1, and chip 2 running normally throughout.

Checked against the case the recovery exists for: a fragment genuinely
stuck with no traffic behind it leaves `_spi_rx_count` static, so the
first part-full tick after the traffic stops restarts the dwell once and
the discard then fires on the fourth tick instead of the third. One
millisecond later, same outcome. The 2026-08-22 capture is exactly this
case — its own note records the counter frozen.

## 8. The rate, and what the record said

Pooled over every unfixed arm — 126 one-attempt cycles on the two-strip
983.04 MHz image, scored by `tools/pi/dsp4_bootstats.py`:

```
UNFIXED  132/136 clean on one attempt (97.1%); failure rate
         2.94% [1.15%, 7.32%] Wilson 95%
    WEDGE_STAGE5   2      (D71, the lost commit)
    WEDGE_STAGE0   2      (D73, the stopped core)

FIXED    149/150 clean on one attempt (99.3%); failure rate
         0.67% [0.12%, 3.68%] Wilson 95%
    WEDGE_LINK     1      (D73, the stopped core — untouched by the fix)
```

| source | rate | how it was obtained |
|---|---|---|
| session 5 → session 12 | "~2 in 8", ~25 % | BOOT_STAGE read alone, off retrying instruments, both failures counted as one |
| session 13, unfixed | **2.94 % [1.15, 7.32]** | one attempt per cycle, every cycle recorded, MAGIC anchored beside the stage, the two failure modes kept apart |
| session 13, `DSP4_SPI_PARTIAL_FIX2` | **0.67 % [0.12, 3.68]**, and the one failure is a D73 | same instrument, 150 cycles |

The old figure is an order of magnitude high, and the reason is in
section 4: a single BOOT_STAGE read that returns 0 was counted as a
wedge, and a dropped answer returns 0 too.

## 9. Standing instruments left behind

| tool | what it is for |
|---|---|
| `tools/pi/dsp4_bootchar.py` + `SHARC/bootchar.sh` | the per-cycle rate; one attempt, every cycle recorded, both chips probed before and after config |
| `tools/pi/dsp4_bootstats.py` | scores those CSVs into a count, a Wilson interval and the failure modes kept apart |
| `tools/pi/dsp4_bootlog.py` | one appended line per boot ATTEMPT (`dsp4_boot.py`) and per diag dump (`dsp4_diag.py`), so the rate accrues from every bench script without any of them being edited |
| `tools/pi/dsp4_cfgstress.py` + `SHARC/cfgstress.sh` | repeats the commit, or the whole write sequence, against a running part — the discriminator that separated "the commit code" from "the first commit at the end of a burst" |
| `tools/pi/dsp4_readvote.py` | the per-read answer-drop rate on a part known healthy, scored under three host read policies |
| `DSP4_CFG_WATCH` (default 0) | CFG_PHASE, CGU_FAIL, the four CGU wait iteration counts, SPI_PART_FIX and SPI_PART_TICKS as diag registers 0xE019..0xE020, plus the watchdog that keeps a stalled CGU wait from stopping the core |
| `DSP4_SPI_PARTIAL_FIX2` (default 0) | the fix in section 7 |

`bootchar.sh` names and echoes its own build switches rather than
inheriting them, because two arms of this session's bisect were run on an
image that did not carry the flag being tested and were only caught
because the diagnostic registers read 0 — the same trap as the 2026-08-23
`DSP4_STUB_*` defines that silently never reached the assembler. Those
two arms are not discarded: they are perfectly good UNFIXED cycles, and
they are pooled into the baseline under their own tag rather than into
the arm whose name they were written with.

`dsp4_bootchar.py` also refuses to append to a CSV whose header does not
describe the columns it is about to write. When the `DSP4_CFG_WATCH`
registers were added the probe grew by six fields, and the wider rows
went into the existing file under the narrower header: every column past
`pre1_build` shifted, the rows still parsed, and a 48-of-48 clean arm
scored as 0-of-48. Caught because MAGIC came out as 2510.

## Addendum, session 14 (2026-08-30): the flip to default-on, and D74

Session 14's mandate was to flip `DSP4_SPI_PARTIAL_FIX2` to default-on and
prove it at scale. The scale proof is clean and stands: pooling this
session's 200 fresh one-attempt cycles with session 13's 150,
**348 of 350 clean (99.4%), 0 D71-class events (`SPI_PART_FIX` never
fired, `SPI_RX_COUNT` read the full 108 every readable cycle), 2 D73
events (stopped core, untouched by this fix, as predicted)** —
`tools/pi/dsp4_bootstats.py` on the pooled CSVs, failure rate
0.57% [0.16%, 2.06%] Wilson 95%. D71 is proven at scale.

**The flip was reverted the same session.** The instrument that caught
it is the standing-bars sweep, not bootchar: with the flag on by default,
`busgold.sh` and `goldnode.sh` — both of which drive `dsp4_scope.py`'s
`Scope.check_chip()` over two chips — failed outright ("no usable
capture in 5 attempts", "chip 1 not ready after 8 attempts"), reading
`link answers as CHIP 0, expected 1` or timing out entirely on register
`0xE001` (`DIAG_CHIP_ID`). `bqst.sh`, `bqgraph.sh` and `mtrverify.sh` hit
the same symptom at least once each and recovered inside their own retry
ladders; `conform.sh`, `dynst.sh`, `numverify.sh` and `dcapar.sh` did not
hit it.

Isolated with a direct A/B on `busgold.sh`, same bench, interleaved in
time rather than early-vs-late in the session:

| `DSP4_SPI_PARTIAL_FIX2` | runs | result |
|---|---|---|
| 0 (off) | 2 of 2 | clean, first attempt, `GRAPH BIT-EXACT` (0 of 256 words differ) both times |
| 1 (on) | 0 of 4 | every run exhausted all 5 internal retries and failed |

One of the two clean `=0` runs was taken AFTER two failed `=1` runs, so
this is not simply "the bench was fresher earlier" — the flag tracks the
result better than session order does. This is filed as **D74** in the
review index and is NOT root-caused: the leading hypothesis is that
`dsp4_scope.py`'s own read traffic (resync polls, `check_chip` retries)
keeps `_spi_rx_count` moving just enough that the D71 fix — which only
discards a stale RX FIFO word while that counter is standing still —
never arms for a fragment that traffic itself left behind, so a word the
OLD unconditional 3-tick discard would have cleared now sits and
misaligns every read after it. This is a hypothesis, not a measurement;
it needs `DSP4_CFG_WATCH`-class live instrumentation of
`_spi_partial_ticks`/`_spi_partial_rxmark` during a reproduced Scope-path
wedge, which this session did not attempt — flipping a shipping default
back on with an unresolved regression is exactly the "push through
unknown-shape work on the wrong tier" this project's dispatch discipline
exists to prevent.

A separate, acute bench-link instability (chip 2 reading `CHIP_ID 1`,
later chip 1 reading `MAGIC 0`) also appeared during this session's
investigation, including once on the reverted, flag-off, byte-identical
baseline image — so it is recorded as a bench-health note, not folded
into the D74 finding. `restore_bench.sh` (CPLD reflash + GPIO release)
followed by a fresh boot+config cycle cleared it; the bench ended the
session healthy (both chips `BOOT_STAGE 7`, `SPI_ERR_COUNT 0`, matrix-app
verified all three MCUs on the first restart after).

**Net state at end of session 14**: `DSP4_SPI_PARTIAL_FIX2` default is
back to 0. The shipping image is byte-identical to the pre-session-13
baseline, `./build.sh` reproducing chip1.ldr `3f0e479a` / chip2.ldr
`ab43c75b`, 301,732 / 182,060 bytes. D71 remains fixed and proven at
scale behind the flag; it is not yet safe to ship as the default.

## Addendum, session 15 (2026-08-31): D74 root-caused — the link was never broken

Session 14 blocked on D74: with `DSP4_SPI_PARTIAL_FIX2` default-on, every
`dsp4_scope.py`-driven bar failed — "link answers as CHIP 0, expected 1",
"register 0xE001 never settled", "no usable capture in 5 attempts" — while
the same bars passed with the flag off. The leading hypothesis on record
was that the fix's counter gate never arms under Scope traffic, leaving a
stale RX-FIFO fragment that misaligns every later read.

**The gate really never arms. The fragment does not exist, and neither
does the misalignment.** Both halves were measured this session on an
instrumented image (three new registers under `DSP4_CFG_WATCH`:
`SPI_PART_SEEN` 0xE021, ticks that found the RX FIFO part-full;
`SPI_PART_SKIP` 0xE022, the subset the fix's gate turned away;
`SPI_REQ_WORD` 0xE023, the last request word the handler assembled).

**The gate is suppressed 100 % of the time under host traffic, exactly as
predicted** — across every run this session `SPI_PART_SKIP` tracked
`SPI_PART_SEEN` almost word for word (5/5, 6/6, 20/20, 44/44 on quiet
paths; 311/204 over a hammering `gainfix`/`pairgraph` ladder) and
`SPI_PART_FIX` stayed **0**. So with the flag on, the 2026-08-22 word
discard never fires while the host is polling. That much of session 14's
hypothesis is confirmed.

**Everything the hypothesis then blamed on it is wrong.** In a
"failed" state, caught live inside the retry ladder, the part reads
`BOOT_STAGE 7`, `SPI_ERR_COUNT 0`, `RESP_DROP 0`, `RFS 0` (RX FIFO
EMPTY — there is no stranded fragment), `SPI_REQ_WORD` holding a
correctly framed request, and `SPI_RX_COUNT` advancing 217 requests per
ladder round. The DSP is answering every transaction correctly. What is
wrong is **where the host looks for the answer**.

### The measurement

The firmware answers every accepted transaction with two words, echo then
value, and the master collects them on the transaction after the one that
asked (`spi_handler.asm`, `.spi_write_answer`). MISO is therefore a
continuous stream of two-word answers, and the host's 8-byte windows can
sit on either of two offsets in it. Both occur. Raw words, one ask of
`DIAG_CHIP_ID` (echo `0xE0012000`, value 1) followed by NOP collects:

| | word 0 | word 1 | |
|---|---|---|---|
| working | `0x00000001` | `0xE0012000` | value and echo in ONE window |
| failing, collect 0 | `0x00000000` | `0xE0012000` | echo here, value is NOT |
| failing, collect 1 | `0x00000001` | `0xE0FE0000` | the value, one window late |

**The echo lands in word 1 in both.** The echo check — the link's only
integrity mechanism, and the thing every tool trusts — passes either way.
In the second arrangement it passes while handing back word 0, which
belongs to the PREVIOUS request. In an ask/collect loop the previous
request is a `DIAG_NOP`, and a write answers with value 0.

So **"the link answers as CHIP 0" is a running part answering 1, read one
word away from where the 1 lay.** So is `MAGIC 0`. So is `BOOT_STAGE 0`.
So is the all-zero register dump: every register in the sweep returns the
preceding NOP's zero, which is why the dumps are zero *uniformly* rather
than plausibly. This is D72's "a dropped answer comes back as a
well-formed (echo, 0)" with the mechanism finally named — **nothing is
dropped**; the answer is present in the very next window.

It also explains why the fault is invisible on a repeated read of a
constant register: reading `CHIP_ID` twice in a row returns the previous
`CHIP_ID`, which is the same number. The wrong phase only shows itself
when the previous request was something else.

### Why the D71 fix looked responsible

Discarding a word from the RX FIFO shifts the DSP's request framing, and
therefore the answer stream, by one word. **The 2026-08-22 recovery is
the only thing in the whole system that moves this phase.** With the flag
off it fires every few seconds and shuffles the phase until it happens to
land right, which is why the bars pass, why `pairgraph_run.sh` carries the
note "a diag read walks it back into phase", and why a card that had been
sitting idle was always the one that worked. With the flag on the phase is
whatever boot left it as, for good. D71's fix did not break the read
path; it removed the accident that kept papering over it.

### The fix, and where it belongs

Host-side, because that is where the defect is. `DiagLink` now
**calibrates** the answer phase instead of assuming it: `DIAG_MAGIC` is a
compile-time constant, so one read of it says which of the two
arrangements is live (`pre` — value and echo in one window; `post` — the
value leads the next window), and every read after that is decoded with
it. A decode that stops matching, or a `realign()` — which moves the
window by exactly one word — invalidates the calibration and re-runs it.
`dsp4_scope.py`'s `_ask` uses the same decision, so the two tools can no
longer disagree about the same silicon. `resync()` calibrates rather than
merely draining, which it never could: draining clears the queue and says
nothing about the offset.

`DSP4_SPI_PARTIAL_FIX2` is now **default-on**, and D71 ships.

**And no bar script deployed either file.** Every one of them stages the
image, its own probe and its own `_run.sh`, then drives whatever copy of
`dsp4_diag.py`/`dsp4_scope.py` happens to be on the card — so a link fix
can be correct in the repo, green by hand, and absent from every bar that
matters. `bench_lock.sh` is the one file every bench script already
sources, so the link tools now travel with the lock.

### What this casts doubt on

A uniformly zero register dump — every register including `MAGIC` reading
0, off a part with no unaided recovery — is now known to be manufacturable
by the reader alone. **That is D73's entire evidence** (section 3b above),
and D73 is the finding this project has parked at a hardware boundary. It
is not settled either way here: D73 was seen while chip 2 kept running on
the same reset and bus, which a host-side phase error does not obviously
account for, and it was seen on the flag-off arm where the ISR discard was
still shuffling the phase every few seconds. But the next D73 event must be
read with the calibrating reader before it is counted as a stopped core —
`tools/pi/dsp4_spiphase.py --mode diagnose` asks the part the three
questions that separate the cases (is it answering at all; does silence
mend it; does one word of realign mend it). No further hardware-level
effort on D73 is justified until that has been done once.

The same caution applies backwards through the record: any conclusion drawn
from a register that read 0 — `BOOT_CFG 0`, `CFG_PHASE 0`, "CONFIG_COMMIT
DID NOT LAND" out of `dsp4_config.py --verify` — was taken through a reader
that could return the previous request's value. D71's evidence is NOT of
that kind and stands: its diagnosis rests on `SPI_RX_COUNT` reading 103 and
107, one short of 104 and 108, and on `SPI_PART_FIX` reading 2 — specific
non-zero numbers that a phase error cannot produce.

### Instruments left behind

- `tools/pi/dsp4_spiphase.py` — the link's phase, as an instrument.
  `--mode counters` (the D74 register block), `--mode raw` (every word the
  host clocks in, no interpretation), `--mode diagnose` (run this when a
  bench script says the link is dead), `--mode phase` (the calibrated
  phase plus registers read through it), `--mode inject`/`--mode pause`
  (a deliberate one-word residue, healed by traffic or by silence).
- Three diag registers under `DSP4_CFG_WATCH`: `SPI_PART_SEEN` 0xE021,
  `SPI_PART_SKIP` 0xE022, `SPI_REQ_WORD` 0xE023.
- `bench_lock.sh` now deploys the host link tools to the card, so this
  class of fix reaches every bar without editing every bar.

### The corroboration was already in section 3, unread

D72's own live capture (session 13) is the signature seen from the other
side: a healthy part at `BOOT_STAGE 7`, with the commit demonstrably
applied, returned 0 for a **contiguous tail of seven registers** — having
answered `MAGIC`, `CHIP_ID` and `BOOT_STAGE` correctly earlier in the same
sweep. A phase that flips partway through a sweep produces exactly that
shape: correct values up to the flip, the preceding NOP's zero after it. A
per-probe dropped answer would scatter its zeros through the sweep instead
of ending it. That capture was read at the time as evidence of a ~1-in-50
dropped-read rate; it is better read as one phase flip, mid-sweep.
