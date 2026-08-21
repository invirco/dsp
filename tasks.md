## HUB DISPATCH 2026-08-21 14:37Z — P2.2 cont'd — characterise the >8KB boot-stream limit so the full 208KB image runs, then dma_cfg_init   [status: 🟢 done — **BOTH SHARCs now load and execute their full firmware, deterministically.** The ">8 KB block-size limit" never existed and is retired. Two real faults, both fixed: (1) elfloader's ZERO-FILL blocks desynchronise the boot kernel — fixed with `-NoFillBlock` plus a build-time guard; (2) U7/H1S1 was a second master on the boot bus — the two offending call sites were removed from its firmware and it was reflashed through MH1, after which the bus measures ZERO events in 15 s and chip 1's 258 KB image boots 6/6 unsynced at 10 MHz and 2/2 at 1 MHz on a 3.45 s stream. The stream-length budget is gone. **P2.2 itself is NOT closed**: with the image finally running, the firmware hangs in `_sru_init`'s DAI0 half — the very first SRU register writes — so `dma_cfg_init` and the `sport_dma_base()` fix are still untested. That is a new, separate item]   [model: opus]

model: opus

rev C is FREE again (the app/panel work is deferred — blocked on the matrix
drift, not the unit). Resume P2.2 from where the 09:xx session left it
(commit 0ce2b7e, "P2.2 reframed"). Read that commit + the 13:09Z block first.

STATE: the SPICMD fix boots ~1 KB images (blink/rdyprobe/bulkprobe) but the
full 208 KB firmware has NEVER executed an instruction — a park on the first
instruction of _start stayed silent. You bisected a boot-stream BLOCK-SIZE
limit: 180 B boots 10/10, 8364 B fails 0/10, and -MaxBlockSize 0x1000 (now in
build.sh LDRFLAGS) boots the 8 KB ladder 4/4. But a SECOND limit above ~8 KB
is still uncharacterised — the 208 KB image still does not run. dma_cfg_init
is downstream and untestable until the full image boots.

TASK — get the full firmware to execute, then close P2.2.
1. Characterise the second limit. Extend the bulkprobe size ladder (build.sh
   bulkprobe) above 8 KB — 16/32/64/128/208 KB — with -MaxBlockSize 0x1000
   already set; find where it stops booting. Use dsp4_stagewatch.py (no bench
   eyes). Hypotheses to test: total stream size vs a per-section/DMA-count
   limit; a boot-kernel scratch/heap ceiling; a second block-count or address
   window; whether multiple blocks vs one big section behaves differently.
   HRM ch.36/40 for any documented SPI-target-boot size/scratch limits.
2. Once the full image boots (park on _start's first instruction fires), move
   the park forward: does dma_cfg_init now run? Then the sport_dma_base() /
   l1_to_sys() fixes finally get a real hardware test. Use DSP4_BISECT to
   walk arm_region(A)/(B) → full run.
3. When the 208 KB production image runs on both chips: revert temp
   instrumentation, rebuild clean production .ldr (fix ldr/manifest.txt which
   currently records the two artifacts as NOT bootable), reflash, verify LD3/
   LD2 + a sane SPI readback. Update P2.2 → 🟢 with the size-limit root cause.
4. If the full image cannot be made to boot as one stream: characterise the
   hard limit and propose the workaround (multi-DXE boot, second-stage loader,
   or a smaller image), with evidence — do not leave it guessing.
Constraints: rev C is yours (app work deferred); ALWAYS restart matrix-app +
verify 3 MCUs before ending; ~/db Dropbox; single trunk; no AI attribution.

Rules: single trunk — pull main first, commit + push main on completion;
update this block's status (🟢 done / 🔴 blocked) with a short outcome;
no AI attribution in commits or any work product.

### Outcome 2026-08-21 17:2xZ — the boot-stream limit is characterised; it was never a size limit

**Headline: chip 2's full firmware executes.** A `DSP4_BISECT=5` build —
the park on the FIRST INSTRUCTION of `_start` — fired 5/6 at the bench.
Every previous session's premise ("the full image never runs") is now
resolved for chip 2, and the reason it never ran is understood.

**What the previous session's finding actually was.** `-MaxBlockSize
0x1000` does nothing. A/B of the identical DXE, capped vs uncapped, 8
boots each at 4 MHz: **7/8 vs 6/8**. The earlier "0/10 then 4/4" was a
~50% coin flip read as a signal. The flag is REMOVED from build.sh and
the claim retracted in `ldr/manifest.txt`.

**FAULT 1 — zero-fill blocks (this is what kept the firmware from ever
running).** elfloader compresses zero runs into ZERO-FILL blocks: a
header with a byte count and no payload. The SPI target boot kernel does
not survive one. A fill block followed by ANY further block loses the
kernel its place in the stream; a fill that happens to be last is
harmless, which is why nothing ever noticed.

| test (chip 2, gap-synced 11 MHz) | result |
|---|---|
| image that boots, one 640 B fill inserted at the FRONT | 3/3 → **0/3** |
| identical block APPENDED instead | 3/3 → **3/3** |
| chip2 firmware as elfloader emits it (324 blocks, 152 fills) | **0/6** |
| same firmware, `-NoFillBlock` (6 blocks, no fills) | **5/6** |

Found by grafting the firmware's first N blocks in front of a tiny probe
that toggles PB_05, so a boot proves the kernel consumed them: N=0 boots
3/3, N=1 (a single leading fill) **0/3**.

FIX IN TREE: `-NoFillBlock` in `build.sh` LDRFLAGS, and
`tools/dsp/ldr_stream.py check` runs on every image the build produces,
so the shape cannot come back silently. Because the zeros now travel for
real, `sec_delay`/`sec_delay_ovf` are marked `NO_INIT` in the LDF —
without that chip 2 would be a 1.9 MB stream. **Those delay buffers must
now be cleared by firmware at startup; that is a new NOW item below.**

**FAULT 2 — the boot bus's second master sets a TIME budget.** U7/H1S1's
legacy ADAU meter poll bursts ~0.5 ms on the shared SCK/MOSI every
~185–254 ms (63 bursts in 11.67 s, measured). Boot success tracks stream
ELAPSED TIME, not size and not block size — the cleanest proof is one
unchanged 3 KB image at three clocks: **5/6 at 1 MHz (25 ms), 5/6 at
4 MHz, 0/6 at 100 kHz (246 ms)**. Faster is safer; 10 and 11 MHz boot
cleanly, **12 MHz and above fail outright**. `dsp4_boot.py --sync-poll`
(new) starts the stream just after a burst. Budget with it: ~220 ms
≈ 240 KB at 11 MHz — a 107 KB probe boots 6/6, 176 KB 5/6, 197 KB 0/6.

**Chip 1 — FIXED the same day; see the addendum below.** 258 KB, ~320 ms
on the wire. It did not fit between two bursts at any clock, so no
host-side trick reached it. **CORRECTED 2026-08-21: it is not an "ADAU
meter poll" and it is NOT absent from the current sources** — `main.c`
line 24 `#include "matrix.cs"`, so that file is compiled. The two
interferers are `TimeSplice()`'s periodic `TestMicPres()` (25 bytes on
the mic-preamp CS, fired off a MainLoop ITERATION COUNTER, which is why
the period wanders 40–254 ms) and `MainLoop()`'s `DspTx(0xF520)` writes
to **CS1–CS8** on every blink transition — the latter asserting the very
chip selects the Pi boots through, for a legacy register the SHARC
firmware does not implement. Both are removable in a few lines;
`TestMicPres()` is also called once at init, so mic gain survives.
**NOT DONE, it needs PW's go-ahead** (and the 13:09Z
dispatch fenced the ADAU-poll item off).

**item 2 — the wedge is in `_sru_init`, NOT `dma_cfg_init`.** Redone on
clean `-NoFillBlock` chip-2 builds (the first pass used a fill-STRIPPED
diagnostic image with uninitialised BSS and reported `_diag_init`; that
reading is WITHDRAWN). Park rungs added to `main.asm` at each step of
`_start`'s init sequence, 6 boots each, read over ssh on PB_05:

| rung | park point | result |
|---|---|---|
| 6 | after the C stack prologue | **6/6 fires** |
| 7 | after `_diag_init` returns | **5/6 fires** |
| 8 | after `_sru_init` returns | **0/6 silent** |
| 9 | after `_sport_cfg_init` returns | 0/6 silent |
| 4 | entry to `dma_cfg_init` | 0/6 silent |

`_sru_init` never returns. Split further with rung 10 (an early `return`
in `sru_config.c` at the DAI0/DAI1 boundary): also **0/6**, so the hang
is in the **DAI0 half — the very first SRU register writes**, not the
DAI1/SPORT4-7 ones.

`sru_init()` is straight-line `SRU()` macro register writes with no loop
in it, so "never returns" is a FAULT, not a spin — the core vectors
somewhere and stays there. The obvious suspect is the DAI/SRU register
space not being reachable yet (clock/power gating, or a CGU that is not
where the code assumes). Note the independent evidence: **CCLK on this
card measures ~190 MHz, not the 400 MHz every delay constant assumes**
(diag.h), and the standalone blink images run ~2x slow — PW confirmed
both LEDs blinking at the slow rate 2026-08-21. Next session: read the
fault status registers at the park, and confirm DAI0 is clocked before
`sru_init` touches it. **`dma_cfg_init` and the `sport_dma_base()` fix
remain untested on hardware — they are three calls downstream of a
function that never returns.**

**Also worth knowing (cost me an hour).** Claiming GPIO9/10/11 with
gpiod/`gpiomon` takes them out of `a0` and **spidev does not put them
back** — every boot then fails and looks exactly like a dead part.
`pinctrl set 9,10,11 a0` restores it; `--sync-poll` does it automatically.
Separately, stopping `matrix-app` makes DSP boot fail outright (0/6 where
it was 5/6) — not chased, but do not debug boot with the app stopped.

**Bench state at hand-off:** `matrix-app` restarted and active, all three
MCUs verified 17:16–17:17 (H1S1, H1S3, H1S4 — "MCU verified" and "MCU
boot verified"), GPIO9/10/11 back to `a0`, spidev bufsiz back to its
4096 default. Chip 2 holds a production `chip2.ldr` from the last boot
attempt; chip 1 holds nothing running.

**NEXT, in order.** (1) H1S1 reflash — DONE, see the addendum.
(2) Zero `sec_delay`/`sec_delay_ovf` in firmware startup (new NOW item).
(3) Chase the `_sru_init` fault: read the fault status registers at the
park, and check DAI0 is clocked/ungated before `sru_init` writes to it —
CCLK measuring ~190 MHz against code assuming 400 MHz says the clock tree
is not where this firmware thinks it is.
(4) Production verification of chip 2 needs eyes on LD2, or a working
`dsp4_diag.py` — it crashes on start (`TypeError` in the gpiod line
request), unrelated to any of this.

### Addendum 2026-08-21 20:2xZ — H1S1 reflashed; the boot bus has one master again

PW authorised the change. Both interfering call sites removed from
`~/build-h1s1/Core/Inc/matrix.cs`:

* `TestMicPres()` dropped from `TimeSplice()`'s periodic path. It pushed
  25 bytes at CS_M every ~1e6 MainLoop iterations. It is STILL called
  once at init, so mic gain is still applied — only the pointless
  re-application every million loops is gone.
* the CS1–CS8 `DspTx(0xF520)` block deleted from `MainLoop()`. Those
  asserted the SHARCs' own boot chip selects, for a legacy ADAU-era
  register the SHARC firmware does not implement.

Built with `Debug/fw.sh` (text 34036 -> 33476 B). **Verified in the
disassembly, not from the source edit:** zero callers of `DspTx`,
exactly one caller of `TestMicPres` (the init one), and `TimeSplice`
contains no `bl` instruction at all. Packed with `hex2shex.py`
(2171 -> 2136 records, 34693 -> 34133 B) and flashed through MH1 with
`app cli loadfw H1S1` — the same path H1S3/H1S4 use, per PW. Previous
pack image kept at
`/home/app/fwbuild/pack-backup-H1S1-2026-08-21-preSPIfix.shex`.
All three MCUs verify after the reflash (20:24).

**Result, measured both ways:**

| | before | after |
|---|---|---|
| SCK/MOSI/MISO activity, gpiomon | 8530 events, 63 bursts / 11.67 s | **0 events / 15 s** |
| chip 1 full firmware, 258 KB @ 10 MHz, unsynced | 0/6 | **6/6** (350 ms) |
| chip 1 @ 1 MHz — a 3.45 SECOND stream | hopeless | **2/2** |
| chip 2 full firmware @ 10 MHz | needed --sync-poll | **3/3** |

There is no longer a stream-length budget on this unit, at any clock.
`--sync-poll` and the 11 MHz ceiling stay in `dsp4_boot.py` because the
two-master WIRING is still a rev-D item — any board whose H1S1 has not
been reflashed has the limit straight back.

**Incidental observation, not touched:** `/home/app/firmware/H1S3.shex`
carries the MCU-ID `H1S4` in its type-04 record (and fwbuild holds
`left-slot3-H1S4content.shex` / `right-slot4-H1S3content.shex`), so the
slot/content mapping looks deliberately crossed. All three MCUs verify,
so this is either intended or long-standing. Flagged for PW, not changed.

## HUB DISPATCH 2026-08-21 13:09Z — P2.2 — close the dma_cfg_init wedge with working boot + LD blink instrument   [status: 🔴 blocked — the wedge is NOT in dma_cfg_init: the full firmware has never executed a single instruction on this card. Root cause found and half-fixed — the SPI target boot kernel cannot take a loader block larger than ~8 KB, so every production image built without `-MaxBlockSize` is a stream the host clocks out in full and the part never runs. `-MaxBlockSize 0x1000` added to build.sh's LDRFLAGS and proved on the bench (0/10 → 4/4 on the same DXE at 8 KB), but the 208 KB firmware still does not run, so a SECOND limit above ~8 KB remains uncharacterised. Bench released to PW mid-bisect for an app/panel reflash]   [model: opus]

model: opus

SHARC boot is SOLVED (SPICMD, D14) and BOTH DSP blink LEDs are confirmed
running at the bench — you now have a working boot AND LD2/LD3 as live
instruments, which is exactly what the P2.2 bisect was blocked on. Resume
P2.2 per NOW item 1.

TASK — close the dma_cfg_init wedge.
1. The SPORT4-7 DMA-base fix (`sport_dma_base()` in dma_config.c) is in the
   tree, verified against sys/ADSP-21564.h, never confirmed on hardware
   because nothing booted before. Now it can be. Build `DSP4_BISECT=1`
   (parks after arm_region(A)); boot chip 1 with the SPICMD fix
   (dsp4_boot.py default 0x03); read LD3 (DSPA, chip 1): a steady ~1 Hz
   square = arm_region(A) survived. If it parks (slow single blink), the
   SPORT4 base was still not it — capture and reassess.
2. If A is clean: `DSP4_BISECT=2` (park after B), boot, LD3 again. Then
   `DSP4_BISECT=0` (production, no park/stamps) for a full run on BOTH
   chips; confirm LD3 (1 Hz) and LD2 (2 Hz) steady, and the SPI2 diag
   readback is non-zero / sane now that the core runs past dma_cfg_init.
3. When closed: REVERT the temp instrumentation (diag_stage_set / diag.asm
   stamps / the park loop behind DSP4_BISECT per item 3), rebuild the
   clean production images, reflash both chips, verify LEDs + readback,
   commit the production .ldr hash-named. Update P2.2 to 🟢 with the
   verdict; note the SPICMD dependency (production boot path must carry
   --spi-cmd 0x03).
4. If the wedge does NOT close on the SPORT4 fix: bisect further with the
   LED (now a real instrument) rather than the all-zero SPI readback, and
   write up where it dies.
Do NOT touch the CLKIN mods (blue, done) or the H1S1 ADAU-poll item (that
is a separate near-term firmware task needing the real H1S1 sources).
Constraints: matrix-app restarted + 3 MCUs verified before ending; ~/db
Dropbox; single trunk; no AI attribution.

Rules: single trunk — pull main first, commit + push main on completion;
update this block's status (🟢 done / 🔴 blocked) with a short outcome;
no AI attribution in commits or any work product.

### Outcome 2026-08-21 15:0xZ — 🔴 stopped mid-bisect (bench released to PW); P2.2's premise is refuted

**The dma_cfg_init wedge does not exist as described.** Every park placed
inside `dma_cfg_init` stayed silent, and so did a park on the FIRST
INSTRUCTION of `_start`. The full firmware has never run on this card —
not once, at any point in this investigation. Only the ~1 KB standalone
`blink` / `rdyprobe` images ever have, which is why "the DSPs boot" read
as settled after the SPICMD fix (D14): that conclusion was drawn entirely
from 1 KB images and does not generalise.

**ROOT CAUSE (partial): the boot kernel cannot take a large loader
block.** Bisected with a new instrument, `src/blink/bulkprobe.asm` —
rdyprobe plus a slab of never-executed code, so boot-stream size is the
only variable — chip 1, ten boots per rung, verdict read over ssh:

| image | stream | biggest block | boots |
|---|---|---|---|
| bulkprobe0 | 180 B | 68 B | **10/10** |
| bulkprobe2 | 8 364 B | 8 252 B | **0/10** |
| bulkprobe2, same DXE, `-MaxBlockSize 0x400` | 8 492 B | 1 KB | **4/4** |
| bulkprobe2, same DXE, `-MaxBlockSize 0x1000` | 8 396 B | 4 KB | **4/4** |

Nothing else moves the result. Not the SPI clock (100 kHz behaves exactly
as 1 MHz — so it is not a timing race). Not the host transfer size
(`--chunk 1024 / 2048 / 4096` all identical — so it is not a spidev or
CS-window artefact; `--chunk` was added to `dsp4_boot.py` for this). Not
the zero-fill blocks (deleting the 506 KB L2 fill via a temporary
`NO_INIT` on `sec_delay` changed nothing). It is the byte count in a
single block header.

`-MaxBlockSize 0x1000` is now in `build.sh`'s `LDRFLAGS`, with the
evidence written into the comment beside it.

**It is necessary and NOT sufficient.** The full 208 KB chip-1 image
built with the cap still does not execute (`DSP4_BISECT=5` park silent).
So there is a SECOND limit somewhere above ~8 KB — total image size,
block count, or the fill blocks. **That is exactly where this stopped.**

**NEXT STEP, and it is one command's worth of work:** the bulkprobe
ladder rebuilt with the cap in place, run up the sizes —

```
cd MW/D32/DSP/SHARC && BULK_LEVELS="2 3 4" ./build.sh bulkprobe
# bulkprobe2 8 KB (known good with the cap), 3 = 33 KB, 4 = 66 KB
scp build/bulkprobe{2,3,4}.ldr app@192.168.1.219:/home/app/dspboot/
# per image: dsp4_boot.py --ldr bulkprobeN.ldr --chip 1
#            dsp4_stagewatch.py --chip 1 --seconds 6
```

If 3 and 4 boot, the second limit is not raw size and the next variable
is the fill blocks (`-MaxFillBlockSize`) or the block count. If they do
not, bisect between 8 KB and 33 KB the same way. Either way the answer is
a loader flag, not firmware.

**What this retires.** The SPORT4-7 `sport_dma_base()` fix is still
correct against `sys/ADSP-21564.h` and stays, but it is UNTESTED on
hardware and was never the thing that hung: nothing in `dma_config.c` has
ever been reached. The "1-flash hang inside `arm_region`" reading from
2026-08-19 was an LED code from an image that had not loaded, not a hang.
`ldr/manifest.txt` now carries a WITHDRAWN note: the two production
`.ldr`s on record are not bootable images.

**New instruments, all committed and deployed to `/home/app/dspboot`
(md5-checked both ends):**

| tool | what it does |
|---|---|
| `tools/pi/dsp4_stagewatch.py` | samples GPIO8/GPIO12 at 1 kHz and decodes the DSP status-LED pattern into a verdict — steady square = running, N flashes = stuck after stage N, flat = not running. Removes the need for eyes on LD3/LD2 for every bisect round. |
| `src/blink/bulkprobe.asm` + `./build.sh bulkprobe` | the boot-size ladder above. `BULK_LEVELS="..."` selects rungs. |
| `dsp4_boot.py --chunk N` | host transfer size, to separate a kernel limit from a transfer-boundary artefact. |
| `DSP4_BISECT=4` / `=5` | park on entry to `dma_cfg_init` / on the first instruction of `_start`. Parks now pulse PB_05 (Pi GPIO8/12) with interrupts OFF instead of relying on the timer-ISR LED, so a park answers "was this point reached?" without also asking about the interrupt path. |

All of the above is still TEMPORARY scaffolding and still goes with NOW
item 3 — except `-MaxBlockSize`, `dsp4_stagewatch.py`, `bulkprobe.asm`
and `--chunk`, which stay.

**Bench state at hand-off (PW took rev C for an app/panel reflash):**
`matrix-app` restarted and active, all three MCUs verified at 14:58
(H1S1, H1S3, H1S4 — "MCU verified" and "MCU boot verified" both), GPIO
9/10/11 back to `a0`, GPIO8/12 inputs, GPIO16 output high. Chip 1 holds a
non-running `DSP4_BISECT=5` image and chip 2 was last reset without one;
neither runs code, which is the same state as before this session and
harmless. Nothing further was booted or flashed after the hand-off
request.


## HUB DISPATCH 2026-08-21 11:26Z — SHARC ③ — scope-driver + boot-bus toggle capture (rails good; CPLD cannot mirror SPI/RST)   [status: 🟢 done — **ROOT CAUSE FOUND AND FIXED. Both SHARCs boot and run application code.** The boot host never sent the SPICMD byte the SPI-target boot kernel reads as its FIRST byte (HRM Table 36-18: 0x03 = keep single-bit mode), so the ROM consumed the first byte of the .ldr as the command and every block header after it was shifted by one. Added `--spi-cmd` (default 0x03) to dsp4_boot.py: GPIO8 now toggles at ~1 Hz on chip 1 and GPIO12 at ~2 Hz on chip 2, and an A/B/A control with `--spi-cmd none` reproduces the old flat-low failure exactly. The parts were never damaged]   [model: opus]
model: opus

Rails are GOOD at the bench (PW): +0.9V, +1V8 VDD_REF, +3V3 all in spec —
suspect (1) power CLEARED. The liveness checklist now needs a live scope of
SPI2 CLK/MOSI and SYS_HWRST during a boot. Hub netlist check: neither the
Pi-mastered boot SPI to the DSPs nor RST_D routes to the CPLD, so a CPLD
patch cannot bring them out — do NOT build one for that. All three signals
are reachable natively:
  test 1 CLKIN  = R65.2/R33.2 pad (PW verified good).
  test 2 boot SPI = Pi header J6 pin 23 (SCK/GPIO11), pin 19 (MOSI/GPIO10),
    0.1"; DSP-side confirm R52.2/R51.2 (DSPA), R19.2/R18.2 (DSPB) 0402 pads.
  test 3 SYS_HWRST = J6 pin 36 (RST_D/GPIO16), 0.1"; expect a clean low pulse
    >= 11 x tCKIN (~450 ns at 24.576 MHz) at each boot.

**PW BENCH RESULT + NEW LEAD 2026-08-21 (highest priority now):** with the
square-wave driver running, PW scoped the Pi header: J6.23 (SCK) TOGGLING,
J6.19 (MOSI) TOGGLING, **J6.36 (RST_D/SYS_HWRST) STUCK HIGH — not toggling.**
The Pi drives the boot bus fine, but it CANNOT toggle RST_D. This matches the
netprobe ("!RST_D held high, U7 p47 also drives it") and the dual-master
errata: the S MCU H1S1 (U7 PA13, pin 47) drives RST_D push-pull and wins over
the Pi's GPIO16. CONSEQUENCE: the Pi has never been able to pulse SYS_HWRST low,
so the two SHARCs came out of reset once at power-on (ran the boot ROM with
nothing to receive) and every dsp4_boot since sent a stream to a part not in
its boot-listen window — exactly "boot reports OK, GPIO8 flat".

DO THIS:
1. CONFIRM contention (not a script miss): with the Pi driving GPIO16 LOW
   push-pull, read GPIO16 back — if it reads HIGH while driven low, U7 is
   overpowering it = confirmed. (If it reads low, the earlier script just
   didn't drive it — fix and re-scope.)
2. RELEASE RST_D to the Pi so a real reset is possible. Options, cheapest
   first: (a) does current H1S1 firmware drive PA13, or is this the rev-A
   image that should leave it as input? Check the H1S1 source (Core/... 
   the errata "H1S1 fw leaves PA13 as input" rule). (b) Hold H1S1 in reset
   (its NRST) during a DSP boot so PA13 goes hi-Z and the Pi owns RST_D —
   find how NRST is reachable (power-MCU? a GPIO? the SWD/prog path?).
   (c) If neither is quick, PW bench: physically lift U7 PA13 or the RST_D
   link — record as a red mod.
3. With RST_D released, run dsp4_boot (which pulses RST_D low then streams)
   and check GPIO8. THIS is the real boot test — the clock is good, the bus
   toggles, and now the part can actually be reset into boot mode.
4. Record the verdict. If GPIO8 finally toggles: the boot-handoff root cause
   = RST_D dual-master (H1S1 held the DSPs out of Pi-controlled reset), not
   damaged parts — a firmware/mod fix, no new card needed. Update the
   dual-master item on the mods PDF accordingly (still a rev-D hardware fix,
   but the immediate unblock is releasing PA13).

**PW REFINEMENT (do this FIRST, priority over the boot loop):** PW wants
INDEPENDENT steady repeating signals on each of the three pins to scope
directly — not boot-shaped bursts. Deploy a small script on the Pi
(app@192.168.1.219, /home/app/dspboot) that drives, as plain GPIO outputs,
a clean square wave PW can catch and level-check at the DSP-side pad:
  - SCK  = GPIO11  (scope at J6 pin 23 or R52/R19 DSP pad)
  - MOSI = GPIO10  (scope at J6 pin 19 or R51/R18 DSP pad)
  - SYS_HWRST = GPIO16 / RST_D (scope at J6 pin 36; note this RESETS both
    DSPs each cycle — fine)
Pick a scope-friendly rate (~1 kHz square, 50% duty) and drive all three
continuously; give PW a one-liner to start and to stop (and to restore the
pins after). CRITICAL: GPIO10/11 are normally spidev's — release/stop any
spidev claim first (the netprobe path already toggles these as GPIO), and
drive them push-pull so the scope shows whether the Pi can actually swing
the net or something clamps it (netprobe saw SCK/MOSI 'held high by
something stronger than the Pi pull' — this square wave at the DSP pad is
the direct test of that: if the Pi drives 0/1 at J6 but the DSP-side pad
stays stuck, there is a break/contention between them). Log the Pi-side
readback while driving. THEN the boot loop below for the realistic view.

TASK A — scope-driver so PW can probe live. Provide a repeating desk-driven
boot on demand: a small loop that boots rdyprobe1.ldr on chip 1 every ~3 s
(and a chip-2 variant), so the SPI2 CLK/MOSI and RST_D edges recur on the
scope. Deploy to /home/app/dspboot as a named script; give PW the exact
one-liner to start/stop it. While it runs, capture on the Pi side what the
boot bus is doing (dsp4_netprobe during the loop) and log it.

TASK B — the discriminating capture (no bench eyes): during the boot loop,
use the Pi to sample, at the DSP boot bus, whether SCK (GPIO11) and MOSI
(GPIO10) actually TOGGLE during the CS-asserted window, vs the netprobe's
earlier "held high" static read. If they are static during boot, the Pi is
not clocking the DSP (host/driver/contention problem) — a different class
than a dead DSP. If they toggle but RDY never deasserts and GPIO8 stays
flat, the DSP is receiving clock+data+reset and still not running = the
parts themselves. State which of these the evidence supports.

TASK C — bookkeeping. Write the scope-point map (the table above, with the
J6 header pin numbers and the resistor pads) into the liveness checklist
doc so PW has it at the bench, and record the CPLD-cannot-mirror-2/3
finding. If TASK B points at the parts, say so plainly and the fresh-card
build is next; if it points at the Pi-side boot drive, propose the fix.
Do NOT build a CPLD patch. Constraints: restart matrix-app + verify 3 MCUs
before ending; ~/db Dropbox; single trunk; no AI attribution.

Rules: single trunk — pull main first, commit + push main on completion;
update this block's status (🟢 done / 🔴 blocked) with a short outcome;
no AI attribution in commits or any work product.

### Outcome 2026-08-21 13:05Z — 🔴 BLOCKED on one DMM measurement at the bench

**TASK A — done, deployed, exercised.** Three new tools in `tools/pi/`,
copied to `/home/app/dspboot` (md5-checked both ends):

| tool | what it does |
|---|---|
| `dsp4_scopedrive.py` + `.sh` | PW's refinement, built first. Drives SCK/MOSI/!RST_D as **plain push-pull GPIO square waves**, one frequency per pin so the scope identifies the pin without moving the probe: SCK 1 kHz, MOSI 500 Hz, !RST_D 250 Hz. Also `hold RST_D=0` for a DC level a meter can read. Releases and **restores spidev's ALT0 pinmux** on stop. |
| `dsp4_bootloop.sh` | repeats a real `dsp4_boot.py` boot every ~3 s (chip 1 or 2) so the boot-shaped edges recur. |
| `dsp4_busmon.py` | **passive** GPLEV0 capture through `/dev/gpiomem` at ~1.3 MSa/s. Claims no line and changes no pull, so it runs *during* a boot — which `dsp4_netprobe.py` structurally cannot do, because its bias-and-read method takes SCK/MOSI away from SPI0 and would break the transfer it is meant to watch. That is why netprobe only ever reported the bus at rest. |

One-liners for the bench (all in the checklist doc):
`cd /home/app/dspboot && ./dsp4_scopedrive.sh start | stop | hold RST_D=0`,
`./dsp4_bootloop.sh start [chip] [period] | stop`. Both stop `matrix-app`
on start and restart it on stop.

**A live-fire hazard found and fixed while building this:** `pinctrl get
9,10,11` read **`ip` (plain inputs)**, not `a0`. Releasing a gpiod line
leaves the pin an input and nothing restores the SPI0 pinmux — not a
`matrix-app` restart. `dsp4_netprobe.py` had left them that way at the end
of the 08-20 session, so any boot run afterwards would have clocked
nothing while still reporting OK. Both new wrappers now set `a0`
explicitly, and `dsp4_scopedrive --restore` puts it back.

**TASK B — the discriminating capture: the Pi IS clocking the DSPs.**
`dsp4_busmon.py` around a real `rdyprobe1.ldr` boot, 3 267 584 samples in
2.5 s:

| net | whole capture | inside the CS1-low window |
|---|---|---|
| SCK (GPIO11) | ACTIVE, 16 170 transitions | **16 170 — all of them** |
| MOSI (GPIO10) | ACTIVE, 1066 transitions | 498 |
| !RST_D (GPIO16) | low for **51.7 ms** (the tool's 50 ms pulse) | — |
| MISO, RDY1, RDY2 | STATIC low throughout | STATIC low |

1024 bytes × 8 = 8192 SPI clocks = 16 384 edges; 16 170 observed, the
deficit being a 0.77 µs sampler aliasing a 1 MHz clock, not lost cycles.
PW's scope agrees at the header (J6.23 and J6.19 both toggling). **So the
netprobe's "MOSI/SCK held high" was a statement about an idle bus, not a
dead one, and TASK B's host-side-drive branch is closed.**

**The hub's PA13 mechanism is refuted — but the conclusion survives.**

- H1S1 firmware (`~/build-h1s1`): **PA13 is not configured at all.** It is
  absent from the `.ioc` pin list, `RST_D_Pin`/`RST_D_GPIO_Port` are not
  defined in `main.h`, and the only two references in `main.c` are
  commented out. PA13 sits in the STM32U5 reset default — SWDIO alternate
  function, ~40 kΩ internal pull-up. That is what beats the Pi's ~50 kΩ
  internal pull-down in netprobe; it cannot fight a push-pull output.
- Pi GPIO16 at the CM4 pad, 2000 samples per state: input+pull-down →
  **high** (the PA13 pull-up), input+pull-up → high, **driven low
  push-pull → low, 2000/2000**, driven high → high, square wave → follows
  0/1. The Pi owns the net at its own end.
- So there is nothing to release: holding H1S1 in reset or lifting PA13
  would change nothing, and dispatch options 2(a)/(b)/(c) are all moot.

**Net topology, settled from the schematic (ROOT sheet p1/10).** The DSPA
and DSPB hierarchy blocks each take `!RST_D` into a port named `RST`, and
on the DSPA sheet (p5) that sheet-local `RST` lands on **U6 p104,
SYS_HWRST** — same for DSPB/U5. One net: **CM4 GPIO16 · U7 PA13 · J6.36 ·
DIL100 P13 · U5 p104 · U6 p104**, no series resistor. Recorded in
`hardware-map.md` §3. (A wrong turn on the way, corrected by PW at the
desk: the DSP sheets are sub-sheets and their labels are sheet-local, so
the `RST` on the M MCU sheet is U8's own NRST — a different net. It was
briefly tested as a way to reset the DSPs: an AIRCR SYSRESETREQ on U8 does
pull its NRST low, proven by RCC_CSR going 0x00000000 → **0x14000000**
(SFTRSTF **and PINRSTF**) across a pure software reset, but that net does
not reach the parts, and booting after it left GPIO8 flat as expected.)

**Which leaves one physical reading of PW's bench result.** The Pi's end
of `!RST_D` is at 0 V while J6.36 on the card is at 3.3 V, on one net. That
is an **open between the CM4 and the DSP4 card** — a DIL100 P13 contact, a
broken track/via, or an unstuffed link — with PA13's pull-up holding the
isolated card-side segment high. If so, neither SHARC has ever been reset
by the host: both came out of reset once at power-on, ran the boot ROM with
nothing sending, and have never re-entered the boot window since. That is
"boot reports OK, GPIO8 flat", every time, since March.

**TASK C — bookkeeping done.**

- `~/db/TransferOnly/PCB mods/dsp4-revC-liveness-checklist.md`: new §1a
  probe-point map (J6 pin numbers + the DSP-side 0402 pads + the bench
  one-liners), the CPLD-cannot-mirror-2/3 finding recorded, step 1 marked
  PASS (rails), step 2 marked pass-at-the-header, and **step 3 rewritten as
  the open item** with all the evidence above and a four-step procedure.
- `MW/D24/HW/hardware-map.md` §3: the `!RST_D` net traced end to end, the
  sub-sheet naming trap, and the PA13-unconfigured finding.

**Blocked on — one measurement, no scope needed:**

```
ssh app@192.168.1.219 'cd /home/app/dspboot && ./dsp4_scopedrive.sh hold RST_D=0'
```

then meter **J6 pin 36** (and p104 on U5/U6 if reachable);
`./dsp4_scopedrive.sh stop` after.

- Both ~0 V → the net is sound, the earlier scope reading was a pin out,
  and the investigation goes to the parts (checklist step 4: fresh card /
  fresh SHARCs).
- J6.36 at 3.3 V → **open confirmed**; find the segment with a continuity
  check power-off, bodge it, re-run `./dsp4_bootloop.sh start` and watch
  GPIO8. Red mod on rev C, item on rev D.
- If the break is unreachable, the card-side fallback is real: U7 PA13 is
  on that net, doing nothing. Configure it as a push-pull output with a
  "pulse !RST_D" command in H1S1 and the supervisor can reset the DSPs —
  which the schematic annotation always claimed it could.

Unit left with `matrix-app` running, all three MCUs verified (H1S1, H1S3,
H1S4 at 12:46), GPIO5/13 back to inputs, GPIO9/10/11 back to `a0`, GPIO16
output high.


### Addendum 2026-08-21 14:00Z — 🟢 ROOT CAUSE: the missing SPICMD byte

**Both SHARCs boot and run application code. The parts are fine.**

PW put a scope on **DSP pin 10, SYS_CLKOUT**, and read **24.5 MHz at 3.3 V**
— the first positive liveness signal this card has ever produced, and the
thing that turned the investigation around. HRM §"CLKOUT Selections":
*"BMODE = (non zero) — When a hardware reset is deasserted, SYS_CLKIN is
selected by default"*, routed DIRECT per Figure 2-2. Our BMODE is 0b010, so
pin 10 is a straight mux from pin 5. That single reading proves VDD_EXT is
present at the die, the output driver works, SYS_CLKIN0 is reaching and
being received correctly *through the part* (better evidence than the pad
scope), and a hardware reset has been deasserted. It also proves BMODE is
non-zero, i.e. not the 000 No-Boot strap.

Then, with `!RST_D` held low from the desk, **PW read pin 10 LOW** — CLKOUT
stops. So the reset reaches the die too, closing the last unverified hop.
Every precondition was verified good on a part that was demonstrably alive,
which meant the fault had to be in the boot handshake itself.

**It was.** HRM ch.36, *SPI Target Boot Mode*:

> "The SPI target processor detects the correct boot mode from the host SPI
> device by reading **the first byte sent, defined as SPICMD**. … These
> additional bytes **must be sent prior to transmitting the data** to
> configure the SPI device."

Table 36-18, host starting in single-bit mode: **0x3 = keep single-bit
mode** (0x7 dual, 0xB quad). `dsp4_boot.py` sent the `.ldr` straight in with
no command byte, so the boot kernel ate the first byte of the first block
header as SPICMD and every header after it was misaligned by one byte:
HDRSIGN never 0xAD, no block ever passed its XOR check, the boot never
completed — while the host still saw a stream clocked out from end to end.
That is precisely the signature this card has had since March.

`--spi-cmd` added to `dsp4_boot.py`, default `0x03`, sent with SS asserted
and before the first stream byte per the host flow in HRM Figure 36-6.

**Result, and the A/B/A control that makes it causation:**

| run | GPIO8 / GPIO12 |
|---|---|
| chip 1, rdyprobe1, SPICMD `0x03` | `hi hi hi hi lo lo lo lo hi hi …` — **~1 Hz** |
| chip 2, rdyprobe2, SPICMD `0x03` | `hi hi lo lo hi hi lo lo …` — **~2 Hz** |
| chip 1, `--spi-cmd none` | `lo lo lo lo …` — the old failure, exactly |
| chip 1, SPICMD back on | toggling again |
| chip 1 rdyprobe + chip 2 blink2, **matrix-app running** | GPIO8 toggling; LD2 should blink |

**What this retires.** The "damaged parts / fresh card / fresh SHARCs"
verdict recorded earlier today is **withdrawn** — do not order parts on it.
Both SHARCs survived the SYS_CLKIN0 overdrive. Everything the earlier
rounds fixed was real and necessary (the ÷2 CPLD clock, the level-shift
bodge, the active-low RDY correction, the H1S1 CS1-6 reflash, the SPI0
pinmux restore), but none of it was sufficient, because the host had never
spoken the first byte of the protocol.

**What stands.** The two-master contention on the boot bus (H1S1's legacy
ADAU meter poll, ~600 µs every ~260 ms) is still real and still worth
removing — it is now the most likely cause of any *intermittent* boot
failure, at ~5.6 % per attempt. The RDY pull-downs (R34/R22) are still
backwards versus HRM Figure 36-4, which wants a 10 K pull-**up** to
VDD_EXT; back pressure works anyway because the part drives the pin, but
the in-reset hold-off does not, and the fixed 500 ms settle is standing in
for a handshake we cannot see. Both are rev-D items.

Unit left with matrix-app running, all three MCUs verified (13:57), chip 1
running rdyprobe1 and chip 2 running blink2.


### Addendum 2026-08-21 13:20Z — 🟢 the open item closed at the bench, verdict: the parts

**!RST_D is good.** PW watched the pin go LOW the moment
`./dsp4_scopedrive.sh hold RST_D=0` was started. The earlier "J6.36 stuck
high" was measured with GPIO16 at its idle level — the tool parks !RST_D as
an output HIGH whenever it is not deliberately driving, and so does every
`stop`, so a high reading in that state is correct and discriminates
nothing. There is no open and no contention. (The confirmed low was at the
header end; the last hop to p104 is netlist inference, no series R on the
net.)

**The closed loop, re-run on both parts with every precondition verified**
(`dsp4_busmon.py` capturing passively through the whole boot, GPIO9/10/11
confirmed at `a0` first):

| | chip 1 | chip 2 |
|---|---|---|
| `!RST_D` low pulse | 158.6 → 209.1 ms (50.5 ms) | 158.7 → 209.2 ms (50.5 ms) |
| CS low | 714.5 → 728.5 ms | 712.3 → 726.3 ms |
| SCK inside the CS window | **16 334 transitions, one burst, 50 % duty** | **16 332, 49 %** |
| MOSI inside the CS window | 236 transitions | 232 |
| MISO | static low throughout | static low |
| SPI_RDY (GPIO8 / GPIO12) | static low, and flat for 6 s after | static low |

16 384 edges are expected for 1024 B; the shortfall is a 0.75 µs sampler
aliasing a 1 MHz clock. Reset, settle, one clean burst inside the select
window — and neither part drives MISO or SPI_RDY, ever.

**Verdict.** SYS_CLKIN0 correct and scope-verified at the pin; +0.9 V,
+1V8 VDD_REF and +3V3 all in spec on a meter; !RST_D reaching the net; and
1 kB of correctly-framed data clocked into each part at the right moment.
Every precondition for a boot is verified good and neither SHARC has ever
driven a pin. **Nothing on the host side is left to fix — the next step is
a fresh card / fresh SHARCs** (checklist step 4), with the corrected clock
chain fitted before first power-up. Both parts were overdriven ~80 mA into
a 6 mA-max clamp on SYS_CLKIN0 from March until 2026-08-21, which remains
the only mechanism on the table that fits.

**Checklist step 0 is closed too, PASS:** PW confirms the decoupling caps
ARE fitted to both DSP chips — they are simply absent from the printed
schematic. The blank `CAPS` sub-sheets (PDF pages 9/10) are a documentation
defect, not a hardware one, so it is not a rev-C fault and not a suspect.
Rev-D mod 14 is downgraded from RED to a drawing item (draw the two CAPS
sub-sheets). Reading lesson recorded in the checklist: a blank sub-sheet in
this project does not mean an empty net.

With that, **every suspect on the list is closed except the parts.**

**A second, unarbitrated SPI master on the DSP boot bus — identified and
confirmed 2026-08-21.** PW named it from the history: H1S1 used to drive
these pins to **read ADAU meter levels, periodically**, and the flashed
image still does. The measurement confirms it and shows why it was
invisible.

With the Pi's `SPI_MOSI` idle, `!SPI1` carries a burst of ~80 transitions
every ~256 ms, and `SCK` showed **zero** transitions — which made no sense
for an SPI transfer. It made sense once GPIO9/10/11 were taken out of `a0`
and made plain inputs:

| | Pi SPI0 attached (`a0`) | Pi SPI0 released (inputs) |
|---|---|---|
| SCK transitions in 1.5 s | **0** | **1630, in 7 bursts** |
| SCK idle level | held LOW by the Pi's output | **99.9 % high** |
| burst period | — | **~260 ms** (260.7 / 260.0 / 263.1 / 261.2) |
| burst length | — | ~600 µs, ~240 edges each |
| MOSI | 472 transitions | 480 transitions, same bursts |
| MISO | static low | static low — nothing answers |

So **the Pi's SPI0, whenever it is enabled, actively clamps SCK and shorts
out H1S1's clock.** H1S1 has been polling into a dead bus, its clock
swallowed by the Pi's push-pull output, and nothing answers on MISO — the
ADAU those meter reads were written for is not there to reply. The idle-
high SCK also says H1S1 runs that bus in a CPOL=1 mode, against the Pi's
mode 0/1: two masters, two clock polarities, no arbitration.

(The tree at `~/build-h1s1` has its `DspTx()` — `buffer[0]=0`, address hi,
address lo, payload over `CS_C`/`CS_M`, the SigmaDSP/ADAU write format —
entirely commented out, and `MainInit`/`MainLoop` are not in it at all. So
that tree is not the flashed image; the running `firmware/H1S1.shex` still
carries the poll.)

**Could it corrupt a DSP boot? Yes, but only the data, and only ~5 % of
the time — and it did not corrupt the boots that failed.**

- **Not the clock.** The same clamping that hid the poll protects the boot:
  with GPIO11 in `a0` the Pi's SPI0 output holds SCK, and the measurement
  is direct — **zero** foreign SCK transitions with `a0` attached, 1630
  without. A boot necessarily runs with GPIO11 in `a0`, so the clock the
  DSP sees during a boot is always the Pi's. (Earlier phrasing "injects
  foreign clock and data" was wrong on the clock half.)
- **The data, yes.** MOSI shows H1S1's bursts even with `a0` attached (472
  transitions vs 480 released), so H1S1 wins, or at least contends
  successfully, on that line. The DSPs' `SPI2_MOSI` (PA_01) hangs off it
  through the 22 R network, and during a boot the Pi has CS asserted, so
  the part *is* listening. A burst landing inside the transfer would put
  foreign bits into the stream and the block would fail its HDRSIGN/HDRCHK.
- **Probability:** ~600 µs of burst every ~260 ms against a 14 ms transfer
  ≈ **5.6 % per boot attempt**, one in eighteen. That is an intermittent
  failure nothing in the host logs could explain — worth removing — but it
  cannot produce the 100 % failure seen since March across hundreds of
  boots.
- **And it is excluded for the boots that matter.** Both of today's boots
  were captured end to end: the bursts fell at 48.3, 301.2, 557.2 and
  808.2 ms while the chip-1 boot ran 714.6 → 728.4 ms, and SCK showed
  exactly one burst, entirely inside the CS window, 16 334 of 16 384 edges
  at 50 % duty. Those two streams were clean, and the parts still did not
  respond.

**Actions:**

1. **Near term: remove the ADAU meter poll from the H1S1 firmware.** The
   part it polls is gone — this card is the SHARC DSP4 — so the poll is
   dead legacy whose only effect is contention on the boot bus. The unit
   already flashes H1S1 from `/home/app/firmware`. Needs the real H1S1
   sources; the tree at `~/build-h1s1` is not the flashed image.
2. **Rev D: give the DSP boot bus an owner.** Either separate it from the
   S-MCU housekeeping bus, or arbitrate it properly. D1 already says the Pi
   masters DSP SPI directly; the schematic quietly puts a second master on
   the same three wires.
3. Note for anyone reading `dsp4_netprobe.py` output: "MOSI/SCK HELD HIGH"
   is this — an external master idling its bus high — not a fault.

Unit left with matrix-app running and all three MCUs verified (13:17).


## HUB DISPATCH 2026-08-21 10:46Z — SHARC testing ② — boot retest on corrected CLKIN (÷2 + level-shift fitted)   [status: 🔴 blocked — clock now verified good at the pad and BOTH chips are still flat (GPIO8/GPIO12 never move, no RDY high in a reset-pulse trace); new lead found at the desk: neither SHARC has any decoupling in the rev-C schematic — PW checklist written, ordered by cost]   [model: opus]

model: opus

PW fitted the CLKIN level-shift bodge (variant: 1k replacing R33/R65 +
330R from the DSP-side pad to GND, per DSP — same 0.245 ratio as the 1k2/390R
in your mod doc) and the card is back in the rev C unit, which rebooted
11:45 local (matrix-app active, H1S1/H1S3/H1S4 verified). CPLD is already on
the ÷2 bitstream a1f6672af6c3. The unit is yours.

**PW BENCH RESULT 2026-08-21 (feed into this task):** scope at the R33/R65
pad shows CLKIN LEVEL and FREQ both good now (0.7-0.82 V, 24.576 MHz) — the
clock suspect is CLEARED electrically, mod restated BLUE on the mods PDF. BUT
the DSP LEDs (LD2/LD3) show NO activity after boot. So: the clock fix alone
did not bring the parts up. Your GPIO8 rdyprobe loop is now the discriminator
— run it FIRST. If GPIO8 also stays flat with a verified-good clock, the
live suspects narrow to: (1) damaged SHARCs (both overdriven ~80 mA into the
0.9 V clamp since March — check the datasheet abs-max exposure, and whether
a fresh card / fresh parts is the only proof), (2) SYS_HWRST behaviour at
p104 (never met the 11xtCKIN-after-supplies-stable spec before), (3) a
boot-stream/entry issue that the earlier "stream consumed" evidence never
actually ruled in. Rank these by cost for PW; do not iterate blind.

TASK — SHARC testing ②: boot retest on the corrected clock.
1. Baseline first, no bench eyes: netprobe PCM_CLK/PCM_FS toggling (CPLD
   alive), RDY1/RDY2 resting state, +0.9 V sanity if readable. Note that
   PW has NOT scoped the clock level yet — if anything below behaves
   oddly, the first hands request is "scope R33/R65 pad: 0.70–0.82 V
   high, ≤0.10 V low, 24.576 MHz; if >0.82 V swap shunt to 300R".
2. Closed loop exactly as the 08-20 dispatch: rdyprobe1.ldr on chip 1,
   sample GPIO8 — success = ~1 Hz lo/hi. Then chip 2. Also repeat the
   "!RST_D pulse, no SPI traffic" RDY observation and compare with the
   dead-part baseline you recorded.
3. If the loop passes: blink1/blink2 (tell PW to eyeball LD3/LD2 at 1 Hz /
   2 Hz), then the production chip1/chip2 images and resume P2.2
   (dma_cfg_init) with working instruments. Record the verdict:
   "rev C CLKIN (freq + level) — root cause of the boot-handoff failure;
   fixed ÷2 in CPLD + level-shift bodge; rev D crystal per DSP".
4. If still flat: the fault is either the clock level at the pad (PW
   scope, see 1), damaged parts (both overdriven since March — a second
   card/fresh SHARCs is then the path), or something downstream; write
   the PW bench checklist ordered by cost and stop. Do not iterate blind.
5. Bookkeeping: mark the 07:23Z block 🟢/🔴 with the verdict; the mod
   goes BLUE on D24 DSP mods.pdf only after PW verifies on the scope —
   leave that to the hub, just record "fitted 2026-08-21 (1k+330R),
   scope verification pending" in the decisions doc.
Constraints: always restart matrix-app and confirm the three MCUs verify
before ending; Dropbox via ~/db; single trunk; no AI attribution.

Rules: single trunk — pull main first, commit + push main on completion;
update this block's status (🟢 done / 🔴 blocked) with a short outcome;
no AI attribution in commits or any work product.

### Outcome 2026-08-21 11:05Z — 🔴 BLOCKED. Clock cleared, parts still dead.

**Verdict: the corrected CLKIN is NOT the root cause of the boot-handoff
failure.** With the clock verified good at the pad by PW's scope
(0.70–0.82 V, 24.576 MHz) and the ÷2 bitstream on the CPLD, every liveness
test reads exactly as it did against the dead-part baseline of 08-20.

| test | result |
|---|---|
| `dsp4_netprobe.py` full sweep (matrix-app stopped) | identical to the 08-20 baseline: PCM_CLK/PCM_FS **toggling** (CPLD alive), RDY1/RDY2 held low on R34/R22, MOSI/SCK held high, !RST_D held high by U7, MISO/CS floating |
| `dsp4_boot.py --ldr rdyprobe1.ldr --chip 1`, then 20 × `pinctrl get 8` | boot reported OK (1024 B on CS1); GPIO8 **`lo` on every sample** |
| `dsp4_boot.py --ldr rdyprobe2.ldr --chip 2`, then 20 × `pinctrl get 12` | boot reported OK (1024 B on CS2); GPIO12 **`lo` on every sample** |
| `--rdy-trace 1 --window 1.0` (!RST_D pulse, no SPI traffic, ~14 µs sampling) | 69727 samples, **no HIGH** |
| `--rdy-trace 2 --window 1.0` | 70789 samples, **no HIGH** |
| LD2/LD3 after a boot (PW, bench) | no activity |

No blind iteration beyond that: two boots per chip, one trace per chip.
Images on the unit were hash-checked against `build/` first (rdyprobe1
`6f8da654…`, rdyprobe2 `049792ab…`) — identical, so nothing stale was booted.

### The new lead, found at the desk: neither SHARC has any decoupling

The DSPA (p5) and DSPB (p4) sheets of `D24 DSP.pdf` each instantiate a
sub-sheet block labelled **CAPS** carrying VDD_INT / VDD_EXT / VDD_REF —
and both of those sheets (PDF pages 9 and 10) are **blank**: title block,
zero ink, measured. There are no C-designators anywhere on either DSP
sheet, while every other device on the card is decoupled (CPLD C8–C21, the
1V8 regulator C3/C4/C6/C7, the XO C2/C5, the M MCU C202–C205). Each part
has ~25 VDD_INT pins plus VDD_EXT and VDD_REF (the PLL/OTP supply), all
arriving over the DIL100 stack.

Unverified against the layout/BOM (the Proteus project is on the Windows
machine), so it is a lead, not a finding — but it is a **one-minute check
with the board in hand**, it would explain everything seen since March, and
the bodge is a handful of 0402s. It is step 0 of the checklist below and
rev-D **mod 14**.

### Two suspects cleared from the desk (do not spend bench time on them)

- **Reset timing.** `dsp4_boot.py` holds `!RST_D` low 50 ms and waits
  500 ms before the first byte; the datasheet asks 11 × tCKIN ≈ 0.45 µs for
  both tWRST and tRST_IN_PWR (Tables 22/23), with supplies long stable. The
  timing half of the HWRST suspect is answered; only the *level* at pin 104
  is unproven, given the two unarbitrated masters on that net.
- **CGU arithmetic — and a correction to this dispatch's premise.** The HRM
  gives **PLLCLK = SYS_CLKIN × MSEL / 2** with reset defaults **MSEL = 40,
  CSEL = 1, SYSSEL = 2, S0SEL = 4** (Tables 2-10/2-11 + register diagrams).
  So at 24.576 MHz: PLLCLK 491.5 MHz, CCLK 491.5 MHz, SYSCLK 245.8 MHz,
  SCLK0 61.4 MHz — every one inside spec, ROM correctly clocked with no CGU
  programming (there is none anywhere in `SHARC/src`, correctly). At the old
  49.152 MHz it was 983 MHz PLLCLK/CCLK — inside the *family* maxima though
  about double the 21564 grade. The 07:23Z claim "MSEL = 60, DF = 0 →
  2.95 GHz, cannot lock, the ROM can never have run" was wrong twice (it
  dropped the /2 and used the wrong default). The ÷2 is still right — fCKIN
  20–30 MHz is an input-pin spec and 49.152 MHz violated it by 64 % — but
  the mechanism was not "the PLL could not lock", and nothing should rest on
  that story. Recorded in D10.

### Checklist written for PW, ordered by cost

`~/db/TransferOnly/PCB mods/dsp4-revC-liveness-checklist.md` (new):

0. **Eyes, no instruments** — are there ANY caps on the DSP power pins;
   does the layout/BOM have what the schematic lacks.
1. **DMM** — +0.9 V (0.855–0.945), **+1V8 VDD_REF** (1.71–1.89, U2 output;
   never measured, and without it the PLL cannot lock), +3V3.
2. **Scope during a desk-driven boot** — SPI2 CLK/MOSI at R52/R51 (DSPA),
   R19/R18 (DSPB): 1 MHz burst, mode 1. First proof a part receives data.
3. **Scope** — SYS_HWRST at p104 across the !RST_D pulse: does it actually
   reach VIL ≤ 0.7 V with U7 pin 47 also driving that net.
4. **The parts.** If 0–3 are clean and RDY still never moves: both were
   overdriven ~80 mA into a 6 mA-max clamp since March. Fresh card / fresh
   SHARCs is the only clean proof; a JTAG bodge is the alternative — and
   note the DSP TAP pins (99–103) are terminals that reach *nothing* on
   rev C, not even each other, so it is 5 wires per part on 0.5 mm pitch.
5. **Boot stream** last: it was verified byte-by-byte on 08-20 and cannot
   be ruled in until step 2 passes.

### Bookkeeping done

- Mod doc `dsp4-revC-clkin-bodge.md`: status → **fitted and scope-verified**,
  the as-fitted 1 k + 330 R recorded against the specified 1k2 + 390 R, a
  second trim ladder added for the 1 k series (300 R is the trim-down if a
  card reads > 0.82 V), the fault-1 mechanism corrected, and §6 records the
  retest result. Hub: the mod can go BLUE on the mods PDF — PW has scoped it.
- `dsp4-revD-modlist.md`: **mod 14 (DSP decoupling, RED)** added; mod 8
  annotated as fixed-and-verified-but-not-the-cause; mod 11 gains the "the
  TAP pins connect to nothing" detail.
- `dsp4-architecture-decisions.md` **D10**: bodge fitted + verified,
  the CGU correction, and what the fix did not fix.
- `MW/D24/HW/hardware-map.md` §3: verified clock chain, the decoupling
  observation, the three DSP supplies and where they come from (VDD_REF is
  on-card from U2), JTAG/RESOUT/FAULT connectivity.
- Unit left with matrix-app running and all three MCUs verifying.

**Blocked on:** PW at the board — checklist step 0 (eyes) and step 1 (DMM)
need nobody's permission and may end this investigation; steps 2–3 need a
scope on a powered card, and the boot side of them can be driven from the
desk.

## HUB DISPATCH 2026-08-21 07:23Z — SHARC testing ① — CPLD dsp_clk ÷2 (CLKIN out of range) + closed-loop retest   [status: 🔴 closed — VERDICT 2026-08-21: the clock chain was a real two-part fault (fCKIN out of range + a 3.3 V drive on a VDD_INT pin), both halves are now fixed and scope-verified on the card, and the boot handoff is STILL dead — so CLKIN was necessary but not sufficient, and this block's premise that it was the root cause is not confirmed]   [model: opus]

**Outcome 2026-08-21 09:55Z — 🔴 BLOCKED ON PW HANDS. Desk half done: ÷2 built, flashed and verified on the card; the level-shift bodge is specified and waiting to be fitted. No boot retest attempted — by the 08:45Z addendum it would not have produced a verdict.** See the outcome section at the end of this block.

model: opus

PW decision 2026-08-21: SHARC testing is the TOP priority for this machine;
reorder the NOW queue behind it (edit the NOW header to say so).

HUB HARDWARE REVIEW RESULT (mx26 docs/backlog-d24-schematic-errata.md
"DSP4 rev C", commit 5e1d419 — read it first): **SYS_CLKIN0 is driven at
49.152 MHz, outside the ADSP-2156x CLKIN range (20–30 MHz).** The CPLD
passes the XO straight through (`shared/dsp4-logic/rtl/dsp4_logic_top.v`
line ~100: `assign dsp_clk = sysclk;`). HRM CGU: reset-default MSEL = 60,
DF = 0 → PLLCLK ≈ 2.95 GHz at reset; the boot ROM can never have run.
This fits your 08-20 conclusion that there is no evidence either SHARC
ever received a byte. It is the prime suspect — test it first.

**TASK A — CPLD dsp_clk ÷2 (24.576 MHz).**
1. Replace the pass-through with a divide-by-2 flop on sysclk (50 % duty,
   glitch-free), keep pin 140; no other RTL changes. Add an SDC
   `create_generated_clock` for it. Update tb_logic_top to check dsp_clk
   = sysclk/2. Quartus build: fitter clean, STA met, LE delta noted.
   Commit the bitstream hash-named per the existing convention.
2. Flash it via the proven path (hub did it 08-19: SVF over the CM4 at
   app@192.168.1.219 — see mx26 tasks.md "dsp4_logic.fd6a5ec69198" and
   the IDCODE 0x020a30dd before/after check). Verify PCM_CLK/PCM_FS
   still toggle (netprobe) so the rest of the CPLD is unaffected.
3. Rerun the closed loop exactly as the 08-20 dispatch defines it
   (rdyprobe1.ldr on chip 1, sample GPIO8). Also repeat the
   "!RST_D pulse with no SPI traffic" RDY observation: with a live
   part the kernel should now show behaviour that differs from the
   dead-part baseline you recorded.
4. If GPIO8 toggles: boot blink1/blink2 (LD3/LD2 for PW at the bench),
   then the production chip1/chip2 images, and resume P2.2
   (dma_cfg_init) with working instruments. Record the verdict in
   findings/tasks as "CLKIN out of range — fixed in CPLD; rev D errata".
5. If still flat after a correct ÷2 (verified by build + a GPIO-side
   sanity where possible): STOP and write the scope checklist for PW's
   bench session — probe points are the 22R pads only: R65/R33 (CLKIN,
   expect 24.576 MHz, 3V3 swing), R51/R52 (SPI2 MOSI/CLK during a
   boot), p104 (HWRST), +0.9 V at J1 P1-6. Then the JTAG-bodge decision
   goes to PW (no DSP JTAG exists on the board).

**TASK B — bookkeeping.** Restate the clock finding in
dsp4-architecture-decisions.md (CPLD is the DSP clock source; 24.576 MHz
is the contract; programmable is a feature). Add the rev-D items from the
errata list to your "Blocked on PW" or rev-D section if not already there
(no JTAG, TRST floating, RDY pull-down, !RST_D dual master + PA13=SWDIO,
RESOUT/FAULT N/C, no test points). Datasheet gap: the 21560/61/64/68
datasheet is NOT in Dropbox or the repo (analog.com blocks fetch) — PW
asked to drop it into `_mx/_temp/adsp-2156x-docs/`; when it appears,
confirm the fCLKIN min/max line and close the [verify] tags.

**HUB ADDENDUM 2026-08-21 09:20Z — session restarted (permission mode
change only).** The previous session was killed by the hub mid-task to
relaunch under bypassPermissions; nothing of its work is lost: the working
tree holds the uncommitted ÷2 RTL/SDC/tb edits and the new bitstream
`dsp4_logic.a1f6672af6c3.*` (old fd6a5ec69198 files deleted), the board
was reported flashed with the ÷2 image and baseline netprobes taken, and a
mod document (CLKIN level-shift sizing against the datasheet) was being
written. Resume from `git status`: review those edits as your own, finish
the mod document, commit, and continue the 08:45Z addendum plan.

**HUB ADDENDUM 2026-08-21 08:45Z — datasheet now in hand (PW).** Files:
`~/db/_mx/_temp/adsp-2156x-docs/adsp-21560-21561-21564-21568.pdf` (Rev. A,
Feb 2026) + the 21564-specific HRM, EE-461 and the anomaly list, same
folder. mx26 errata DSP4 section updated (mx26 3371173). Two CONFIRMED
clock faults, which change TASK A:
1. fCKIN = 20–30 MHz (Table 23, crystal and external alike) — the ÷2 is
   right; finish step 1 (RTL/SDC/tb/build/commit).
2. **SYS_CLKIN0 is a VDD_INT-domain pin.** Abs max SYS_CLKIN0 input =
   –0.3 V to VDD_INT (Table 19); VIHCLKIN max = VDD_INT, VILCLKIN max
   +0.12 V; "must not exceed the internal (VDD_INT) voltage level". The
   CPLD drives it at 3.3 V through 22R → both SHARCs overdriven since
   first power-up; the pin clamp pumps the +0.9 V rail; parts may be
   damaged.
So: do NOT flash + retest expecting a verdict. Instead (a) commit the ÷2
build; (b) size a proto level-shift at R65/R33 to a ~0.8 V swing at pin 5
(e.g. ~560R series + ~180R shunt on the DSP side; check RC against the
24.576 MHz edges and the CPLD drive) and write it as a RED mod for PW to
fit, plus the scope checklist (first: +0.9 V sane with the card fitted,
clamping at pin 5); (c) downgrade TRST (internal pull-down per the signal
table), note BMODE2 internal PD and SYS_FAULT open-drain (external pull-up
if used). Record in this block + the decisions doc; when the desk work is
done mark the block 🔴 blocked on PW hands (bodge); push.

Constraints: chips may be freely booted/reset; ALWAYS restart matrix-app
and confirm the three MCUs verify before ending the session or between
long gaps; Dropbox via ~/db. The rev C unit is yours (no other machine
dispatched to it). Single trunk; update the dispatch block status; no AI
attribution.

Rules: single trunk — pull main first, commit + push main on completion;
update this block's status (🟢 done / 🔴 blocked) with a short outcome;
no AI attribution in commits or any work product.

### Outcome 2026-08-21 — what was done

**TASK A step 1 — done and committed (a4ee3d1).** `dsp_clk` is now a
dedicated toggle flop off sysclk: 24.576 MHz, exact 50 % duty (datasheet
asks 45-55 %), glitch-free by construction, `preserve`d so the
synthesiser cannot merge it into the heartbeat counter's carry chain and
put the DSPs' only clock on an LE mid-chain. SDC gains a
`create_generated_clock` (with a comment recording why Quartus warning
332088 is benign here — nothing inside the CPLD is clocked by dsp_clk).
`tb_logic_top` now checks period = 2 sysclk and high = 1 sysclk instead
of pass-through equality. Build: fitter clean, timing met, **157/1270 LE
(+1 for the flop)**, fmax 70.21 MHz, sim gate PASS, bitstream
`dsp4_logic.a1f6672af6c3` (source hash recomputed and matched before
committing).

**TASK A step 2 — done, verified on the card.** Programmed over the CM4
JTAG bit-bang path: IDCODE `0x020a30dd` before and after, **40779 SVF
commands, 0 errors, 58 s**. `dsp4_netprobe.py` after the flash: PCM_CLK
(GPIO18) and PCM_FS (GPIO19) still TOGGLING, every other net reads
exactly as it did on 08-20 — the rest of the CPLD is unaffected.
matrix-app restarted; **all three MCUs verify** (H1S1 "// H1S1 DSP",
H1S3 SW Right, H1S4 SW Left).

**TASK A steps 3-5 — deliberately NOT run.** Per the 08:45Z addendum a
retest cannot produce a verdict while the second fault stands, and each
boot attempt is more powered time on an overdriven pin. The scope
checklist replaces them.

**The second fault, sized and written up (the 08:45Z addendum's (b)).**
`SYS_CLKIN0` is the one signal pin in the **VDD_INT** domain: Table 7
(power domains), Table 13 (designer quick reference), Table 19 (abs max
= −0.3 V to VDD_INT), operating conditions (VIHCLKIN 0.68 V…VDD_INT,
VILCLKIN ≤ +0.12 V, VDD_INT 0.855/0.900/0.945 V), and the crystal
section's flat statement that the external clock "must not exceed the
internal (VDD_INT) voltage level". Rev C drives it at 3.3 V through 22 R
— R65 → DSPA U6 p5, R33 → DSPB U5 p5, both confirmed off the schematic
at 400 DPI, along with DSP_CLK on CPLD pin 140 in a **+3V3** bank
(VCCIO2_1/2_2 both on +3V3, so the swing really is 3.3 V). Through 22 R
the clamp demand is ~80 mA per part against a 6 mA per-pin absolute
maximum, injected into the +0.9 V core rail, continuously since March.

**Mod written: `TransferOnly/PCB mods/dsp4-revC-clkin-bodge.md`** (RED,
awaiting PW). Per DSP: R65/R33 22 R → **1k2**, plus a new **390 R** to
GND at the DSP-side pad. Ratio 0.245 → ~0.77 V high against a 0.68-0.855 V
window; ~2 mA per DSP (4 mA total on CPLD pin 140) instead of the ~160 mA
the two clamps are asking for now; Thevenin 294 R into ~7 pF → ~4.6 ns
edges on a 40.7 ns period, so tCKINH/L stay far above the 16.67 ns
minimum. Includes a trim ladder (360/390/430 R), the physical fitting
notes, and the **bench scope checklist** — ordered, with expected values:
+0.9 V rail first (a high reading means the clamps are pumping it), then
the clamped ~1.2-1.6 V clock at R65/R33 as direct confirmation of the
fault, then post-mod acceptance (0.70-0.82 V high, ≤0.10 V low,
24.576 MHz), then the boot retest with SPI2 CLK/MOSI at R52/R51 and
HWRST at p104. Failure branch spelled out: clean clock + good rail +
visible SPI traffic and still no RDY ⇒ the parts themselves, and the
JTAG-bodge / replace decision is PW's (there is no DSP JTAG on the card).

**TASK B — done.** New binding decision **D10** in
`dsp4-architecture-decisions.md`: the CPLD is the single DSP clock
source, 24.576 MHz is the contract, fCKIN must stay inside 20-30 MHz,
SYS_CLKIN0 must be level-translated to 0.68-0.855 V on any DSP4-derived
board, and the per-DSP-crystal alternative is explicitly rejected (it
would give up the programmable single source). `hardware-map.md` §3
records the R65/R33 topology and both faults. Rev-D list gains **mods
8-13**: the clock chain (mod 8, RED), RDY pulls → pull-ups, `!RST_D`
dual master (Pi GPIO16 + U7 p47 = PA13/SWDIO), a DSP JTAG header,
RESOUT/SYS_FAULT liveness (FAULT is open-drain, external pull-up
required), and test points. **Mod 7 (JTG_TRST) is downgraded to no
action**: Table 13 gives JTG_TRST an internal **pull-down** (TDI/TMS/TCK
have internal pull-ups), so floating TRST holds the TAP safely in reset.
SYS_BMODE2's internal pull-down is recorded with it. The datasheet gap is
closed — all `[verify]` tags on fCKIN and the CLKIN levels are now
answered from `adsp-21560-21561-21564-21568.pdf` Rev. A.

**Blocked on:** PW fitting the four resistors and running the scope
checklist. Everything after that is desk work over SSH.

**Note for PW:** the card is still being overdriven whenever it is
powered. The bodge doc says it plainly — keep powered time short until
the divider is fitted. matrix-app is running now because the dispatch
constraint requires the unit left verifying, not frozen.

## HUB DISPATCH 2026-08-20 18:43Z — Boot handoff investigation — apps never execute   [status: 🔴 blocked]

ROOT QUESTION: SHARC boot streams are fully consumed by the ROM (per-chunk
RDY back-pressure works end-to-end with the fixed active-low tool) but
APPLICATION CODE NEVER EXECUTES — proven tonight with a closed loop:
`src/blink/rdyprobe.asm` (blink.asm with PORTA→PORTB, bit 5 = PB_05 =
SPI2_RDY) booted on chip 1 and the Pi sampled GPIO8 flat low; the PA_12
blink images also never light LD2/LD3 (PW verified LED wiring anode→R→
PA_12, cathode→GND: pin-high = lit). All dma_cfg_init work is downstream
of this and moot until fixed.

Find why the ROM→application handoff fails. Investigate at the desk, then
verify with the closed loop (no bench eyes needed).

Suspects, in order:
1. Boot-stream format: elfloader flags are `-b SPI -bcode 1 -f BINARY
   -width 8`. Check HRM ch.40 (text already extracted to hrm.txt in your
   scratchpad from the previous session — regenerate if gone) for the
   BLOCK CODE / BCODE the 2156x ROM expects in SPI SLAVE boot (BMODE
   0b010), and whether -b SPI + bcode 1 encodes master vs slave. Parse
   the actual bytes of build/rdyprobe1.ldr (block headers: dBlockCode,
   dTargetAddress, dByteCount, dArgument; FIRST/FINAL/INIT flags) and
   check: final block flags, jump target address, and whether the ROM
   requires anything the stream lacks.
2. Entry/IVT: the .dxe has NO ELF entry (elfloader "Defaulting to
   0x90004"). Verify in the built blink/rdyprobe images that address
   0x90004 (RSTI slot) actually receives a jump to _start (dump the dxe:
   elfdump, or parse the .ldr payload for the 0x90000-block content).
   Check blink_ivt.asm places the IVT at 0x90000 and the LDF puts
   seg_pmco somewhere the ROM actually loads.
3. Post-boot core state: does the 2156x ROM hand off with the core in a
   state our code mishandles (e.g. executes from an address alias we
   didn't link for)? Compare with an ADI example loader stream if any
   ships in CCES (look under /opt/analog/cces/3.0.3/SHARC/ldr or
   examples) — diff their header/entry conventions against ours.
4. If a stream fix is identified: apply to build.sh loader() (and
   dsp4_boot.py only if the transport itself must change), rebuild
   rdyprobe1.ldr, and VERIFY with the loop below. Iterate until GPIO8
   toggles.

CLOSED-LOOP VERIFICATION (run as often as needed):
  ssh app@192.168.1.219 'cd /home/app/dspboot && python3 dsp4_boot.py \
    --ldr rdyprobe1.ldr --chip 1' \
  && ssh app@192.168.1.219 'for i in $(seq 1 12); do pinctrl get 8 | \
    grep -oE "lo|hi"; sleep 0.25; done'
Success = alternating lo/hi (~1 Hz). Copy fresh rdyprobe1.ldr to
/home/app/dspboot/ before each run. rdyprobe.asm is untracked — commit it
(it is now a permanent bring-up tool) with a header comment.

After GPIO8 toggles: boot blink1/blink2 and note in tasks.md that PW
should confirm LD3/LD2 blink at next bench visit (1 Hz / 2 Hz — also the
free CCLK measurement); then the production/park builds become meaningful
again and P2.2 resumes with working instruments.

Constraints: chips may be freely booted/reset (PW has released the
bench; the bisect state is void anyway). ALWAYS restart matrix-app
(sudo systemctl restart matrix-app) and confirm the three MCUs verify in
/home/app/logs/log before ending the session or between long gaps —
the unit must not be left on a frozen splash. Dropbox via ~/db. Single
trunk; update the dispatch block status; no AI attribution.

Rules: single trunk — pull main first, commit + push main on completion;
update this block's status (🟢 done / 🔴 blocked) with a short outcome;
no AI attribution in commits or any work product.

**Outcome 2026-08-20 20:20Z — 🔴 NOT FIXED. GPIO8 is still flat low after
every variant tried, so the handoff still fails. But the suspect list is
now much shorter: the boot stream and the toolchain flags are CLEARED with
evidence, two genuine defects in the boot host were found and fixed, and
the one assumption everything rested on — that the parts were receiving —
turns out to have no supporting evidence at all. Unit restored, all three
MCUs verify, app running.**

### The closed loop, run many times — always flat

`rdyprobe1.ldr` booted on chip 1 and GPIO8 sampled, across the full cross
product of SPI mode {0, 1} × post-reset settle {0.05 s, 0.5 s, 2.0 s}:
`lo` on every sample of every run. Nothing tried tonight moved it.

### Suspect 1 (boot-stream format) — CLEARED, with the bytes

Every block of `rdyprobe1.ldr`, `blink1.ldr` and the 207 KB production
`chip1.ldr` was parsed field by field against HRM ch.40 Fig. 40-15 /
Table 40-27. The streams are textbook:

- Headers are 16 B: BLOCK CODE / TARGET ADDRESS / BYTE COUNT / ARGUMENT.
  HDRSIGN = 0xAD (core 0) on every block; the HDRCHK XOR checksum was
  recomputed and matches on every block; `chip1.ldr` parses cleanly
  through 608 blocks and lands exactly on EOF (0x32814 = file length).
- First block = `BFLAG_FIRST|BFLAG_IGNORE`, count 0, TARGET_ADDRESS
  **0x00090004** (the RSTI slot — the entry point the kernel writes to
  RCU_SVECT0 at termination), ARGUMENT = offset of the final block.
  Final block = `BFLAG_FINAL`, count 0, same target. Both correct.
- The IVT **is** in the stream: a 48-byte payload block (8 NW slots × 6
  bytes) to 0x28240000. That address is right: NW 0x00090000 ↔ BW
  0x00240000, 6 bytes per 48-bit word, which is exactly why the stock
  CCES `ADSP-21564.ldf` starts `mem_block0_bw` at 0x002403F0 (0xA8 words
  × 6). Slot 1 (RSTI, word index 4) decodes as `jump 0x1C0000` — the SW
  address of `_start` at BW 0x380000. `BFLAG_AUX` is correctly absent:
  elfloader already emits byte-space addresses, so no PM translation is
  wanted.
- `-b SPI` vs `-b SPIHOST`: elfloader 6.4.2.1 emits **byte-identical**
  output for both (checked on blink1). `build.sh` now says `SPIHOST`
  anyway, because `-b SPI` documents the master/flash case and this is
  the host-push case. `-bcode 1` is right — HRM Table 40-19 gives
  SPIS_BCODE `00xx` = single-bit SPI bus, and 1 is in that range. (The
  BCODE nibble is also the first byte of the stream, which is what
  Table 40-18's SPICMD auto-detect reads.)

Nothing in the image explains the failure.

### Suspect 2/3 (entry, board straps, clock) — CLEARED off the schematic

Read at 1200 DPI from `D24 DSP.pdf` p5/10 (DSPA, U6):

- `SYS_BMODE0` = **pin 105 → GND**, `SYS_BMODE1` = **pin 106 → VDD_EXT**,
  `SYS_BMODE2` = **pin 82 → GND**. BMODE[2:0] = 0b010 = SPI Slave Boot
  (HRM Table 40-14). The strap is right. (`SYS_RESOUT` p107 is NC, so
  there is no reset-done signal to watch.)
- `SYS_CLKIN0` = pin 5, fed from **DSP_CLK through R65 (22R)**.
- `SPI2_RDY` → **PB_05** through R38 (22R), with R34 10K to GND —
  confirming what `rdyprobe.asm` drives is the right pin.
- SPI2 on DSPA: MISO→PA_00, MOSI→PA_01, CLK→PA_04, SS→PA_05.
- The S MCU (U7, p3/10) housekeeping SPI is on **ISPI0/1/2**, which are
  DIFFERENT nets from the Pi's SPI0/1/2 — so H1S1 is not a second master
  on the boot bus. It *is* a second driver on `!RST_D` (U7 pin 47).

**The LOGIC CPLD is alive and clocking.** LOGIC masters the Pi PCM port,
and `PCM_CLK` (GPIO18) / `PCM_FS` (GPIO19) read as TOGGLING at the Pi.
`dsp_clk` is a pass-through of the same `sysclk` that feeds the clkgen,
so the "unprogrammed CPLD = no DSP clock" theory is dead as stated.
`!RST_D` really does go low when the Pi drives it (verified by reading
the net back).

### TWO REAL DEFECTS FOUND AND FIXED in `dsp4_boot.py`

1. **SPI clock mode was 0; the boot kernel uses mode 1.** HRM ch.40:
   "In SPI slave boot mode, the boot kernel sets the SPI_CTL.CPHA bit and
   clears the SPI_CTL.CPOL bit", and ch.15 fixes the numbering —
   "mode-0 (CPHA=CPOL=0) and mode-3 (CPHA=CPOL=1)" — so CPHA=1/CPOL=0 is
   **mode 1**: MOSI is latched on the FALLING edge. A mode-0 host changes
   MOSI on exactly the edge the kernel samples. Now `SPI_MODE = 1`, with
   `--spi-mode` as an escape hatch. (The RUNTIME link is a separate
   question and correctly stays mode 0 — `spi2_init()` leaves CPOL and
   CPHA clear, matching `dsp4_diag.py`.)
2. **No settle time after reset release.** HRM Fig. 40-7 does not use a
   timer: the host waits for SPI_RDY DEASSERTED then ASSERTED, which is
   the kernel saying "SPI2 is up". That handshake does not exist on this
   card (pull-downs, see below), so the host was clocking bytes
   microseconds after `!RST_D` released, while the part was still in
   pre-boot. Now `POST_RESET_S = 0.500`, `--post-reset-delay` to override.

Both are real bugs by the manual. Neither, alone or together, made GPIO8
move — so there is at least one more cause.

### The finding that matters most: "the stream was consumed" was never evidence

New tool **`tools/pi/dsp4_netprobe.py`** asks the only question that
discriminates on a bus like this one: make the Pi pin an input, select the
internal pull-up, read; select the internal pull-down, read. Follows both
= nothing else drives it. Result:

| net | Pi | verdict |
|---|---|---|
| SCK | GPIO11 | HELD HIGH by something stronger than the Pi pull |
| MOSI | GPIO10 | HELD HIGH by something stronger than the Pi pull |
| MISO | GPIO9 | floats |
| CS1 / CS2 | GPIO6 / GPIO24 | floats (the H1S1 CS1-6 fix holds) |
| RDY1 / RDY2 | GPIO8 / GPIO12 | HELD LOW (R34 / R22, as designed) |
| !RST_D | GPIO16 | HELD HIGH (H1S1 U7 p47 also drives it) |
| PCM_CLK / PCM_FS | GPIO18 / GPIO19 | TOGGLING — the CPLD is running |

And a `!RST_D` pulse with **no SPI traffic at all**, sampling SPI_RDY every
~15 µs for 1 s: not one HIGH, on either chip, on any run. A 64 KB blast of
deliberate garbage at 20 MHz with no flow control: also not one sustained
HIGH — and a kernel that rejects a bad header should stop draining and let
the RX FIFO fill within ~32 bytes.

Because the card's pulls rest SPI_RDY ASSERTED, "every chunk was accepted"
is what a *dead* part looks like too. **There is currently no positive
evidence that either SHARC has ever received a single byte.** Every prior
"the stream was consumed" reading is compatible with the parts never
having listened. That is the honest state of the investigation.

### Committed alongside

- `src/blink/rdyprobe.asm` — now a permanent bring-up tool with a proper
  header, plus a `./build.sh rdyprobe` target. `blink()` and `rdyprobe()`
  are one parameterised `tiny_image()`; `blink1.ldr` is byte-identical
  after the refactor, checked.
- `LDRFLAGS` is now defined once and shared by `loader()` and
  `tiny_image()`.
- `tools/pi/dsp4_netprobe.py` (above), deployed to `/home/app/dspboot/`.

### Next — in this order

1. **Prove or disprove that a SHARC is receiving.** Everything else is
   guesswork until this is settled, and it needs a scope at the part:
   SYS_CLKIN0 (p5) for DSP_CLK actually arriving, then PA_04/PA_01
   (SPI2 CLK/MOSI) during a boot, then SYS_HWRST (p104). One session with
   a probe answers what a week of desk work cannot.
2. ~~The one board assumption still unverified~~ **VERIFIED 2026-08-20
   (hub): PA_00=SPI2_MISO, PA_01=SPI2_MOSI, PA_04=SPI2_CLK,
   PA_05=SPI2_SEL1/SS, PB_05=SPI2_RDY — from ADI's own pinmux data:**
   `ADSP-21564-pinmux.xml` inside CCES
   `Eclipse/plugins/com.analog.crosscore.addins.pinmux_*.jar`
   (extracted to /tmp/pinmuxjar on this machine; the jar is the local
   authoritative pin-function source — datasheet fetch no longer
   blocks anything). Schematic net names correct on every SPI2 pin;
   rdyprobe drives the right pin. Suspect list for the scope session
   accordingly narrows to the physical layer: VDD_INT (+0.9 V core
   rail) actually present at the card, SYS_CLKIN0 actually clocking,
   SYS_HWRST behavior, then PA_04/PA_01 during a boot. The HRM has no pin-function table
   (it is in the datasheet, which is not in `_mx/_temp/adsp-2156x-docs` —
   only `adsp-2156x_hwr.pdf`), and analog.com times out on fetch. If the
   two are the other way round the parts have never seen MOSI. **Get
   `adsp-21560-21561-21564-21568.pdf` into the Dropbox docs folder and
   check PORTA against p5/10.**
3. Rev-D hardware items, both from tonight: R34/R22 want to be pull-UPs
   (already logged 17:16Z; tonight shows exactly what it costs — no
   liveness signal at all); and `!RST_D` has two masters (Pi GPIO16 and
   H1S1 U7 p47) with no arbitration.
4. Left in the working tree, NOT committed, from an earlier session: a
   `DSP4_BISECT == 4` park in `src/dma_config.c` (its `#error` guard text
   still says 0-3). It is out of scope for this dispatch — finish or drop
   it deliberately.

## HUB DISPATCH 2026-08-20 17:16Z — P2.2 fix flash + readback verification   [status: 🔴 blocked]

**Outcome 2026-08-20 18:30Z — production images built and BOOTED into both
SHARCs (a first: with real flow control), but the readback verdict is FAIL
— both chips still echo all-zero, so P2.2 is NOT verified. Separate and
bigger find on the way there: `dsp4_boot.py` had the SPI_RDY polarity
INVERTED, and every boot before today only worked because H1S1 was
driving the shared CS3/CS4 nets high. Fixed and proven. Unit restored,
all three MCUs verify, app running.**

### What was done

1. **Build.** `DSP4_BISECT=0 ./build.sh all` — production, 0 errors.
   Confirmed the scaffolding really is compiled out: `elfdump -sym` on
   `build/chip{1,2}/dma_config.doj` shows no `_diag_stage_set` reference
   on either chip. Artifacts `chip1.b4090de01d5d.ldr` (207108 B) +
   `chip2.bb2b24db8617.ldr` (108172 B), hash-named, `ldr/manifest.txt`
   updated with the superseded pair recorded.
2. **Deploy.** scp'd to `app@192.168.1.219:/home/app/dspboot/`, sha256
   re-verified on the unit. matrix-app stopped, `S_RESET` (`*`) sent
   twice at 115200 8N1 on `/dev/serial0` with 2 s between, matching
   `Boot.FlashFirmwareViaSerial`.
3. **Boot — failed, then root-caused, then succeeded.** See below.
4. **Readback — FAIL.** See "The readback verdict".
5. **Restore.** matrix-app restarted; `MCU verified: // H1S4 SW Left`,
   `// H1S1 DSP`, `// H1S3 SW Right` and `Boot.Loop() - MCU boot
   verified: H1S1 / H1S3 / H1S4` at 18:30:31-37Z. Unit left whole with
   the production images loaded in both DSPs.

### THE BOOT-TOOL BUG — SPI_RDY polarity was inverted (fixed)

First boot attempt failed on BOTH of the tool's attempts, chip 1, before
a single byte: `SPI_RDY never asserted within 2.0s`. GPIO state read at
the time: `!RST_D` (GPIO16) = 1 (released), CS1 (GPIO6) = 1, **both RDY
lines low** — chip1 GPIO8 = 0, chip2 GPIO12 = 0.

- **The tool waited for HIGH.** Its docstring reasoned from the board's
  10K pulldowns (R34 DSPA / R22 DSPB) that asserted must be high.
- **The HRM says the opposite for boot.** Ch.40, SPI Slave Boot Mode:
  "In SPI slave boot mode, SPIx_RDY functionality is critical. The
  SPIx_RDY output is used for back pressure and requires a pulling
  resistor. **The boot code requires the SPIx_RDY signal function as
  active-low.**" The polarity during boot is the on-chip boot kernel's
  and is not configurable. Asserted = 0. Both parts were sitting there
  ready and the tool was waiting for the one level that never comes.
- **Why it only broke today.** CS3/CS4 are SHARED nets — Pi RDY inputs
  AND H1S1's "DSP 1/2 chip SPI_RDY" monitors (`MW/D24/HW/hardware-map.md`
  §3a). Until the 2026-08-20 17:17Z reflash, H1S1 drove CS1-6 push-pull
  HIGH, so the Pi always read 1 and **every RDY wait in every boot to
  date passed vacuously — all previous boots ran with no flow control at
  all.** Making CS1-6 inputs exposed the real line. The CS1-6-inputs
  change is correct and stays; it just uncovered this.
- **This also explains the "first attempt always fails, retry works"
  quirk** (reproduced ×3, 2026-08-19/20) — a timing race against a line
  nobody was reading correctly. With the polarity fixed, both chips
  booted on **attempt 1/2**, no retry.
- **Fix** (`tools/pi/dsp4_boot.py`): `wait_ready()` now takes
  `active_low`, defaulting to `RDY_ACTIVE_LOW = True` with the HRM
  citation; `--rdy-active-high` is an escape hatch, not a normal option.
  Threaded through `boot_chip`/`boot_chip_retrying`; module docstring
  corrected; the timeout message now names the expected level and points
  at the shared-net cause. Exercised off-target (asserted/stuck/timeout
  in both polarities) plus `--dry-run`; deployed to `/home/app/dspboot/`,
  md5 matches the repo copy.
- **Result:** `chip 1: attempt 1/2 OK — 207872 bytes sent on CS1`,
  `chip 2: attempt 1/2 OK — 108544 bytes sent on CS2`.

**HARDWARE ITEM for rev D — R34/R22 are the wrong way round.** The HRM
wants the pull to hold the line DEASSERTED while the part is in reset
("allows the processor to hold off the host while the processor is in
reset"). With boot fixed active-low, a pull-DOWN rests the line
ASSERTED, so the hold-off does not exist on this card and no host-side
wait can prove a part is alive or out of reset. Back pressure mid-stream
still works (the DSP drives the pin push-pull to deassert). Changing
R34/R22 to pull-UPS restores the hold-off — and would then also flip the
runtime `SPI_CTL.FCPL` to 0. Until that happens boot and runtime
legitimately disagree on polarity: `dsp4_boot.py` active-low,
`dsp4_diag.py`/`dsp4_config.py` active-high. Noted in `dma_config.c`
beside the `FCPL` write.

### The readback verdict — FAIL, and it cannot localise the fault

Against BOTH chips (`--cs-gpio 6 --rdy-gpio 8` / `--cs-gpio 24
--rdy-gpio 12`):

- With the runtime RDY gate honoured: `SPI_RDY never asserted` — SPI2 is
  never configured, so the pin is never driven and the pulldown holds it
  at 0.
- With the gate bypassed (`--rdy-active-low --resync`, which makes the
  resting-low line read as asserted so the transaction goes out):
  `response out of step reading 0xE000: echo 0x00000000, expected
  0xE0002000` — **all-zero echo, identical to the pre-fix symptom.**
- MAGIC / CHIP_ID / BOOT_STAGE / TICKS: none obtainable. No acceptance
  criterion from the dispatch was met.

**Why this is not evidence against the P2.2 fix.** `spi2_init()` runs at
DIAG_STAGE(5), *after* `arm_region(A)`, `arm_region(B)` and `sec_init()`
— i.e. the diagnostic link comes up downstream of the entire suspect
region. An all-zero readback therefore means "did not reach stage 5" and
says nothing about WHERE. It reads the same whether the part still dies
on lane index 4 of region A or now dies somewhere new. The SPI readback
was never able to bisect this; **LD2/LD3 is the only instrument that
can, and that needs bench eyes.**

**The addressing fix itself re-verified at desk level** against
`/opt/analog/cces/3.0.3/SHARC/include/sys/ADSP-21564.h`:
`REG_DMA10_DSCPTR_NXT = 0x31023000`, `REG_DMA17_DSCPTR_NXT = 0x31023380`,
`REG_DMA7_DSCPTR_NXT = 0x31022380`, and DMA8/DMA9 (MDMA0) sit off at
0x310A7000/0x310A7080. `sport_dma_base()` reproduces all of these
exactly. The fix is right; it was simply not sufficient on its own, or
the remaining fault is elsewhere.

### Next at the bench (PW, LD2 needed)

1. `DSP4_BISECT=1 ./build.sh` (park after `arm_region(A)`) and boot chip 1
   with the **fixed** boot tool. Steady 1 Hz square on LD2 = the SPORT4-7
   base fix closed the region-A wedge and the remaining fault is
   downstream; slow single blink = region A still dies and there is a
   second cause in `arm_region`.
2. Then `DSP4_BISECT=2` (park after `arm_region(B)`), then `=3`
   (EN-last) if A is implicated again.
3. Item 3 (clear the bisect scaffolding) stays BLOCKED — the scaffolding
   is now the only working instrument. Item 4 (`dsp4_config.py`, stage
   5→6) stays blocked behind a stage-5 readback.

### Deviation from the dispatch, declared

The dispatch's step 5 said one boot retry maximum and then mark 🔴. The
first boot failure was diagnosed to a tool bug with a documented HRM
citation rather than retried blind, the tool was fixed, and the boot was
run once more — which is what got both images loaded at all. The
readback that followed is the honest verdict and is reported as FAIL.
No CPLD or MCU was flashed; only the DSPs, `/home/app/dspboot`, and the
app stop/start were touched.


Flash the P2.2 wedge fix and verify by SPI readback — no bench eyes
available; the diag readback IS the verdict. PW has waived the
before-datapoint LD2 read; chip1's parked bisect state may be discarded.

Context: root cause fixed in fff7506 (sport_dma_base — SPORT4-7 at
0x31023000). Chip1 currently runs the round-1 park build, chip2 the
l1_to_sys-only build (both hung, harmless). Unit app is running with the
new H1S1 build; H1S1 proven not to drive !RST_D. dsp4_boot.py now has
the auto-retry. Dropbox via ~/db only.

Sequence:
1. Pull main. Build BOTH chips with **DSP4_BISECT=0** (production — no
   park, no stamps; note the current default is 1). `./build.sh all`,
   commit the .ldr pair hash-named per the artifact convention.
2. scp the .ldr pair to app@192.168.1.219:/home/app/dspboot/. Stop
   matrix-app, S_RESET '*' (hold slaves), run dsp4_boot.py for both
   chips (its auto-retry covers the hung-state first-attempt quirk).
3. Verify via dsp4_diag.py against EACH chip. Acceptance:
   - MAGIC correct, CHIP_ID = 1 and 2 on the right chips (proves CS
     routing), echo protocol passing (no all-zero echoes).
   - BOOT_STAGE = 5 (waiting for host product config) on both.
   - TICKS advancing between two reads (core alive), no unexpected
     ISSUES from the tool.
4. On PASS: restart matrix-app, confirm the three MCUs still verify,
   leave the unit whole. Update tasks.md: P2.2 marked VERIFIED ON
   HARDWARE with the readback evidence; note that item 3 (clear bisect
   scaffolding) is now unblocked and item 4 (dsp4_config.py, stage 5→6)
   is the next bench step. Commit + push.
5. On FAIL (readback still all-zero / stage < 5): do NOT thrash — one
   boot retry maximum beyond the tool's built-in retry; record exactly
   what the readback shows, restore matrix-app, mark the block 🔴 with
   findings; the staged LED bisect (DSP4_BISECT=1/2) resumes at PW's
   bench.

Constraints: touch ONLY the DSPs and /home/app/dspboot + app
stop/start — no CPLD flashing, no MCU flashing. Single trunk; update
this block's status; no AI attribution.

Rules: single trunk — pull main first, commit + push main on completion;
update this block's status (🟢 done / 🔴 blocked) with a short outcome;
no AI attribution in commits or any work product.

## HUB DISPATCH 2026-08-20 15:18Z — H1S1 aligned reflash + P2.2 prep (PW absent)   [status: 🟢 done]

**Outcome 2026-08-20 — both tasks done. TASK A: H1S1 reflashed with the
CS1-6-inputs build compiled against the RUNNING app generation
(`e80ccab5d6d8`); all three MCUs verify on reboot, DSPs untouched.
TASK B: boot-tool auto-retry + bisect variants B/C landed, and the HRM
desk-review FOUND THE P2.2 WEDGE — SPORT4-7 use DMA10-DMA17 at
0x31023000, not DMA8+ at 0x31022400; `2*sport+dir` off one base was
writing unpopulated MMR space. Fix applied (not flashed).**

### TASK A — H1S1 aligned reflash

- **Generation.** Built against `/home/app/fwbuild/matrix-aligned.h`
  (generated on-unit 2026-08-19 from `config/_matrix.mxc`, app build
  260714102659). `matrix_gen_id.py --compare` vs the unit's own
  decrypted matrix: **ALIGNED, full-id `e80ccab5d6d8`, 5412 cells,
  Sys001Skin001 = 5412**. Against mx26's baked
  `MatrixBus.Matrix.g.cs` it reports DRIFT of exactly one cell
  (`base-id 9b3c3d8f0286`): the g.cs predates `Sys001SwUpd001` (MxAdd
  6416, added on-device 2026-08-18) and still carries the dev-only
  `Aaa001Aaa001` placeholder, which shifts the `Zzz001Zzz001` sentinel
  6417 vs 6415. Hub confirmed the unit generation is the operative one.
  Immaterial either way for this image: **all four cells H1S1 actually
  compiles in are identical in both generations** — Sys001Enc001 5232,
  Sys001Skin001 5412, Sys001Test001 5414, Sys001Test002 5415 —
  confirmed in the linked ELF, `MATRIX[]` at `.rodata 0x080083b0` =
  {0, 5232, 5412, 5414, 5415}. The abandoned Dropbox-generation build
  had {0, 19479, 19727, 19730, 19731}.
- **Build.** `Debug/makefile.linux all` in the scratch copy
  `~/build-h1s1` (nothing written into Dropbox): exit 0, 0 errors,
  34036 text / 657 data / 1940 bss. 29 warnings, all pre-existing
  (`-Wpointer-sign` in DspTx/SpiTx/HAL_UART_Receive, three unused
  micGain* variables, CubeIDE `.cyclo` peer-target noise). Disassembly
  is byte-identical to the 2026-08-20 verified build except debug
  section sizes — the generation change lives in `.rodata`.
- **CS pins (acceptance 2).** All eight `GPIO_MODE_INPUT` in
  `H1S1.list`: CS5|CS2|CS7, CS8, and CS1|CS4|CS3|CS6(+BUSY,S3) groups
  each set `GPIO_InitStruct.Mode` to 0 in the disassembly.
- **Flash.** `hex2shex.py H1S1.hex H1S1` -> 2171 records / 34693 B
  image; previous pack image kept as
  `/home/app/fwbuild/pack-backup-H1S1.shex`. matrix-app stopped,
  S_RESET `*` on `/dev/serial0`, `app cli loadfw H1S1` -> MH1 loopback
  OK, S_SCAN found H1S1, all 2171 records ACKed, `// flash end of
  firmware record`, `OK: H1S1` (`logs/flash.log` 17:17-17:18Z).
- **Boot (acceptance 3).** matrix-app restarted and left running:
  `MCU verified: // H1S1 DSP`, `// H1S3 SW Right`, `// H1S4 SW Left`,
  then `Boot.Loop() - MCU boot verified: H1S1 / H1S3 / H1S4`. No new
  warnings — the only ones present are the 25 pre-existing SkinLoader
  "not in the matrix" notices (those cells are genuinely absent from
  the unit matrix, a skin<->matrix drift item, nothing to do with
  H1S1) and the pre-existing `mh1=?` build-stamp MISMATCH line.
- **DSPs untouched, as instructed.** No `dsp4_boot.py`, no `!RST_D`, no
  DSP reset. H1S1's own firmware never drives `!RST_D` — the only two
  writes to it in `main.c` are commented out and the pin is not in the
  `.ioc` — so the MCU reset during flashing did not reset either SHARC.
  Chip 1's bisect park should be intact for PW's LD2 read.
- **Flagged, not changed:** H1S1's blink handler still issues
  `DspTx(GPIOx, CSn_Pin, 0xF520, ...)` on SPI1 for all eight CS lines
  on every S_BLINK edge (ADAU-era LED writes, `matrix.cs` MainLoop).
  With CS1-6 now inputs it selects nothing, so this is strictly less
  intrusive than the build it replaced, but SPI1 SCK/MOSI still toggle
  on the housekeeping bus that carries the DSP CS provision. Deleting
  those dead calls belongs in the next H1S1 pass.

### TASK B — P2.2 prep

1. **`tools/pi/dsp4_boot.py` auto-retry.** `BOOT_ATTEMPTS = 2` with a
   `--attempts` override; every attempt is logged (`attempt n/m OK` /
   `attempt n/m FAILED`) so a part that needs the retry every time
   still says so. The retry restarts that chip's stream from byte 0 and
   deliberately does NOT re-pulse `!RST_D` (one reset line serves both
   DSPs). `Gpio` now releases and re-claims a line so the second
   attempt can re-request CS/RDY. Exercised off-target against a stub
   GPIO/SPI (fail-then-succeed and `--attempts 1` raise) plus
   `--dry-run`. Copied to `/home/app/dspboot/` so the next bench run
   picks it up (md5 matches the repo copy).
2. **Bisect round 2 ready to build, NOT flashed.** `DSP4_BISECT` in
   `dma_config.c`: 0 = production (no park, no stamps), 1 = round 1
   (default, park after `arm_region(A)`), 2 = **variant B** (park after
   `arm_region(B)`), 3 = **variant C** (write DSCPTR + CFG with
   `DMA_CFG.EN` clear, then set EN separately; parks after A so LD2
   answers the same question). `build.sh` passes it through:
   `DSP4_BISECT=2 ./build.sh`. All four values compile clean for both
   CHIP_IDs; an out-of-range value is a compile-time `#error`.
3. **HRM desk-review — root cause found (see the P2.2 note below).**
4. **`tools/pi/` sync.** `dsp4_config.py` pulled back from
   `/home/app/dspboot/` (the gpiod-v2 port) and committed verbatim;
   `dsp4_diag.py` and `dsp4_boot.py` were already byte-identical. Two
   rough edges in the ported `dsp4_config.py` left as-is so repo and
   unit stay identical, worth a tidy pass: the `if True:` block claims
   the RDY line unconditionally (crashes when `rdy_gpio is None` but
   `cs_gpio` is set), and the CS request is likewise unconditional.

Housekeeping: `~/mx26`'s `origin` was still HTTPS against a dead `gh`
token, so `git pull` there failed. Switched it to
`git@github.com:invirco/mx26.git` (same SSH key the dsp remote uses);
pulls work again and `tools/matrix_gen_id.py` is present.


Two tasks, PW absent — everything here is verifiable over SSH, no bench
eyes available. Unit access: app@192.168.1.219 (this machine's key works).
Dropbox via the space-free symlink ~/db ONLY. mx26 checkout at ~/mx26
(git pull it first; it has tools/matrix_gen_id.py and the app's baked
table src/sw/app/Core/MatrixBus.Matrix.g.cs).

**TASK A — reflash H1S1 with the CS1-6-inputs build (tasks.md NOW item 2).**
Correction to tasks.md first: it says H1S1 "has never been flashed" — STALE.
The hub flashed a matrix-aligned CS7/CS8-only build on 2026-08-19 night
(all three MCUs verify at boot since). What supersedes it is the CS1-6
build from the 2026-08-20 dispatch. Fix the tasks.md wording as part of
this task.

CRITICAL — matrix generation: the 2026-08-20 scratch build (~/build-h1s1)
compiled against the Dropbox MX/matrix.h generation (Sys001Skin001=19727),
which is NOT the running app's generation (5412). Do NOT flash that binary.
Rebuild against the running app's generation: the hub's 2026-08-19 flow
left an aligned header (matrix-aligned.h) on the unit or in its build area
— find it (check /home/app and the FW-home mechanics used that night), or
regenerate from the unit's own decrypted matrix as that flow did.
Verify alignment BEFORE flashing:
  python3 ~/mx26/tools/matrix_gen_id.py --compare <the matrix.h you built
  against> ~/mx26/src/sw/app/Core/MatrixBus.Matrix.g.cs
must print ALIGNED (base-id match).

Then: pack (H1S1.shex into the unit's firmware pack, same as 08-19) →
send S_RESET '*' on /dev/serial0 first (MH1 '?' responder is pre-loop
only) → `app cli loadfw H1S1` → confirm on reboot the app verifies
"// H1S1 DSP" AND both panels still verify.

Acceptance:
1. matrix_gen_id --compare says ALIGNED for the header actually compiled in.
2. H1S1.list of the flashed build: all eight CS pins GPIO_MODE_INPUT.
3. Boot log: H1S1 + SW Left + SW Right all verified, no new warnings.
4. tasks.md updated (item 2 done + the "never flashed" correction).

Constraints: do NOT touch the DSPs — no dsp4_boot.py, no !RST_D, no DSP
resets (chip1 carries the overnight bisect state; PW reads LD2 on return —
if the loadfw path unavoidably disturbs it, note that in the outcome, it
is re-establishable). Leave the unit with the app running.

**TASK B — P2.2 prep (desk work, no hardware contact with the DSPs).**
1. dsp4_boot.py: add auto-retry — a re-boot from a RUNNING/hung state
   fails its first attempt (SPI_RDY timeout) and works on the immediate
   retry (reproduced ×3). One automatic retry, log both attempts.
2. Prepare bisect round-2 as ready-to-build variants (guarded #ifdefs or
   committed patches — NOT flashed): variant B = park moved after
   arm_region(B); variant C = EN-write-order experiment (write DSCPTR +
   CFG with EN clear, then set EN separately).
3. HRM desk-review of the remaining dma_cfg_init suspects (DMA CFG EN
   write ordering, descriptor alignment, the lane-4/cs-mask special
   case) — findings appended to the P2.2 notes in tasks.md.
4. Sync the gpiod-v2-ported dsp4_config.py + dsp4_diag.py copies back
   from app@192.168.1.219:/home/app/dspboot/ into tools/pi/, commit.

Rules for both: work on main (pull first, push on completion); update this
dispatch block's status with a per-task outcome; no AI attribution.

Rules: single trunk — pull main first, commit + push main on completion;
update this block's status (🟢 done / 🔴 blocked) with a short outcome;
no AI attribution in commits or any work product.

# tasks — dsp spoke

Status: active · reprioritized 2026-08-20 (hub declutter — the full prior
text, day logs, and done-evidence live verbatim in
[archive/tasks-archive-2026-08-20.md](archive/tasks-archive-2026-08-20.md);
nothing was deleted).
Purpose: current work state for the mx26 → mx-dsp workflow and DSP4
firmware. This file is also the HUB DISPATCH queue (mx26 "machines"
model): the hub prepends dispatch blocks; sessions on this machine
execute them, commit, push `main`; the hub reviews on pull.

Trunk is `main` (`master` deleted + blocked). Mandates: `CLAUDE.md`.
Contract pin: **defs-v2026.08.20** (mx26 `345470a`; see `defs.lock` —
sync-from-mx26.sh now refuses an untagged mx26 HEAD).

## NOW — priority order (reordered 2026-08-21: SHARC BOOT SOLVED)

**MILESTONE 2026-08-21: both SHARCs boot and run application code.** Root
cause of the five-month boot-handoff failure was the boot host never
sending the **SPICMD byte** the SPI-target boot kernel reads as its first
byte (HRM ch.36 Table 36-18: 0x03 = keep single-bit); the ROM ate the
first `.ldr` byte as the command and every block header was misaligned by
one — which is why the 08-20 byte-by-byte stream audit found nothing (the
framing was right, the host was one byte early). `dsp4_boot.py --spi-cmd`
(default 0x03) fixes it; `--spi-cmd none` reproduces the flat-low failure
on demand. GPIO8 ~1 Hz on chip 1, GPIO12 ~2 Hz on chip 2, matrix-app up
(D14). **Parts were never damaged — no fresh card needed.** The clock
mods (÷2 + level-shift, D10) were real and are kept — an out-of-spec clock
had to be fixed regardless — but they were necessary, not the blocker.
Item 0 is DONE; the queue moves to P2.2 with working boot AND working LD2
blink as an instrument.

**MILESTONE 2026-08-21 (17:2xZ): chip 2's FULL FIRMWARE EXECUTES** — a
`DSP4_BISECT=5` park on `_start`'s first instruction fires 5/6. Two
independent faults were in the way and both are characterised in the
14:37Z dispatch outcome above: elfloader's ZERO-FILL blocks (fixed with
`-NoFillBlock` + a build-time guard) and U7/H1S1's ADAU poll on the
shared boot bus (mitigated with `dsp4_boot.py --sync-poll` at 10–11 MHz).
The ">8 KB block-size limit" is retired — it never existed.

**NEW NOW ITEM — zero the delay buffers in firmware startup.** With
`-NoFillBlock` every zero-initialised byte is clocked into the part for
real, so `sec_delay`/`sec_delay_ovf` (~1.7 MB) are now `NO_INIT` in the
LDF — otherwise chip 2 becomes a 1.9 MB, ~2.4 s stream that cannot
possibly boot. **Until firmware clears them at startup, the delay lines
come up holding whatever was in L2.** Owner: next SHARC dispatch.

**DONE 2026-08-21 — H1S1 reflashed, the boot bus has one master again.**
Its two SPI1 call sites (periodic `TestMicPres()`, and the CS1–CS8
`DspTx` LED writes) are removed and it was reflashed through MH1. The bus
measures 0 events in 15 s and **chip 1's full 258 KB firmware now boots
6/6 unsynced**. Full detail in the 14:37Z addendum above.

**NEW NOW ITEM — the `_sru_init` fault is the top SHARC item now.** With
both images loading reliably, the firmware hangs in `_sru_init`'s DAI0
half (the first SRU register writes). No loop in that function, so it is
a fault, not a spin. `dma_cfg_init` and the `sport_dma_base()` fix are
still untested — they are downstream of it.

**Context:** the rev-C card is LIVE on the fresh digital board — CPLD
`a1f6672af6c3` flashed 2026-08-21 (the ÷2 clock fix; supersedes
`fd6a5ec69198`), MH1/H1S3/H1S4 verify on every boot, H1S1 flashed
2026-08-19 (CS7/8 build) and reflashed 2026-08-20 with the CS1-6-inputs
build on the running app's matrix generation. This machine has direct SSH
to the unit (`app@192.168.1.219`) since 2026-08-20 — the hub-relay era is
over. **Correction to the previous context, which said "both SHARCs
slave-boot from the CM4": that was never evidenced** (2026-08-20
netprobe work) and the 2026-08-21 datasheet reading explains why — the
clock chain was wrong twice over (D10). Treat every pre-08-21 statement
about SHARC behaviour as unproven.

0. **SHARC testing — ✅ DONE 2026-08-21. Both parts boot and run.**
   Root cause = missing SPICMD byte (D14); fixed in `dsp4_boot.py
   --spi-cmd 0x03`. The clock two-part fault (D10) is also fixed and
   scope-verified on the card: ÷2 in the CPLD (`a1f6672af6c3`) + the
   level-shift bodge PW fitted (1k + 330R per DSP, mod BLUE on the mods
   PDF). Damaged-parts verdict WITHDRAWN. Two follow-ups fall out of it,
   now folded into the queue: (a) H1S1's legacy ADAU meter poll bursts on
   the shared !SPI1 net can corrupt boot DATA — near-term firmware fix
   (see item just below P2.2); (b) rev-D boot-bus owner. **PW confirmed 2026-08-21: both DSP blink LEDs visible at the
   expected rates — milestone closed visually (schematic map: LD3=DSPA/
   chip1 1 Hz, LD2=DSPB/chip2 2 Hz; LD1 is the CPLD LED, not a DSP).
   NOTE: on the rev C board these are SILKSCREENED D2/D1 = schematic
   LD2/LD3 respectively — refdes offset, don't re-confuse them.**

1. **P2.2 — REFRAMED 2026-08-21: there is no dma_cfg_init wedge. The
   full firmware has never executed an instruction on this card.**
   Parks inside `dma_cfg_init` AND a park on the first instruction of
   `_start` were all silent; only the ~1 KB blink/rdyprobe images have
   ever run. Root cause found and half-fixed: **the SPI target boot
   kernel cannot take a loader block larger than ~8 KB**, and every
   image so far was built with elfloader's default (one block per
   section). `-MaxBlockSize 0x1000` is now in `build.sh` LDRFLAGS —
   necessary, proven (0/10 → 4/4 on the same 8 KB DXE), NOT sufficient:
   the 208 KB image still does not run, so a second limit above ~8 KB
   is still uncharacterised. **Next step and full evidence: the
   2026-08-21 15:0xZ outcome at the top of this file.** Everything
   below this line is the 2026-08-20 desk review, kept because the
   `sport_dma_base()` fix in it is still correct — but it is UNTESTED
   on hardware and was never what hung, because nothing in
   `dma_config.c` has ever been reached.

   **(superseded framing, 2026-08-20 desk review)**
   - **The SPORT DMA channels are not one contiguous block, and the two
     blocks are not adjacent in the MMR map** (HRM Table 27-2 "ADSP-2156x
     DMA Channel List", Table 23-6, and `sys/ADSP-21564.h`):

     | half-SPORT | DMA channel | MMR base |
     |---|---|---|
     | SPORT0-3 A/B | DMA0-DMA7 | 0x31022000 + (2n+dir)·0x80 |
     | — | DMA8/DMA9 = MDMA0_SRC/DST | 0x310A7000 (different SCB node) |
     | SPORT4-7 A/B | DMA10-DMA17 | **0x31023000** + (2(n-4)+dir)·0x80 |

     `arm_region()` used `0x31022000 + (2*sport + dir)*0x80` for every
     lane, which is right only for SPORT0-3. From SPORT4 up it wrote
     0x31022400, 0x31022480, … — **unpopulated MMR space just past
     DMA7**. An SCB access there never completes, and the core stalls on
     its next MMR access: exactly the observed 1-flash hang. Chip 1's
     region A carries SPORT0-7, so it dies on lane index 4 (SPORT4)
     *inside* `arm_region(A)`, which is where the round-1 park says it
     dies. Chip 2 reaches SPORT4 in its region B (`c2_tx` lane index 4).
   - **Fix applied** (`dma_config.c`): `sport_dma_base(sport, dir)`
     picks the right base and half index; verified for all 16 half-SPORTs
     against the vendor header. Compiles clean for both CHIP_IDs.
     `dsp4-plumbing.md`'s DMA-channel-map bullet, which stated the wrong
     `2n`/`2n+1` rule, is corrected too. **Nothing has been flashed** —
     the DSPs were left untouched per the 2026-08-20 dispatch.
   - **FLASHED AND BOOTED 2026-08-20 18:2xZ** (hub dispatch 17:16Z, at the
     top of this file): production `DSP4_BISECT=0` images loaded into both
     SHARCs. **Readback still all-zero on both chips — P2.2 NOT verified.**
     The SPI diagnostic link comes up at DIAG_STAGE(5), downstream of the
     whole suspect region, so an all-zero echo cannot say where it dies;
     LD2 is the only instrument that can. The SPORT4-7 base fix itself was
     re-verified against `sys/ADSP-21564.h` and is correct.
   - **Next on the bench:** build (default `DSP4_BISECT=1` still parks
     after `arm_region(A)`) and boot chip 1. If LD2 now shows the steady
     1 Hz square, the wedge is closed — then `DSP4_BISECT=2` (park after
     B), then `DSP4_BISECT=0` for a full run. PW's LD2 read on the
     CURRENT image is still useful as a before/after datapoint but is no
     longer a gate.
   - Suspects cleared by the same review, for the record: **descriptor
     alignment** is fine — the HRM requires only 32-bit alignment for
     descriptor sets ("Descriptor Set Address Alignment"), `DMA_ADDRSTART`
     only needs MSIZE alignment (MSIZE04 = 4 bytes, and the buffers are
     `unsigned int` arrays), and the descriptor element order
     {DSCPTR_NXT, ADDRSTART, CFG, XCNT, XMOD} matches the MMR order at
     +0x00/04/08/0C/10 that NDSIZE=5 fetches. **DMA_CFG.EN write order**
     is already legal — `DMA_OFF_DSCPTR` (0x00) *is* `DMA_DSCPTR_NXT`,
     which is precisely what "Startup Minimum-Enable Requirements"
     requires be written before `DMA_CFG` for descriptor-LIST flow. The
     `DSP4_BISECT=3` variant keeps the EN-last experiment available
     anyway. **The lane-4/cs-mask special case** was the right instinct
     pointing at the wrong mechanism: lane index 4 is where it dies, but
     because that lane is SPORT4, not because `cs_mask = 0x000D` is
     non-contiguous.
   - Real fix already applied (KEEP): `arm_region` converts every
     DDE-visible address core-L1 → SYSTEM via inlined `l1_to_sys()`
     (+0x28000000 for 0x00240000..0x003FFFFF; ADI libcc math). The hang
     persists at sub-step ≤4 after it — SPI2 diag readback still all-zero
     echoes.
   - Temp instrumentation in the tree (REVERT when done): `diag_stage_set()`
     stamps 1..7 in `dma_cfg_init` + `_diag_stage_set` helper in
     `diag.asm` + the park loop — now all behind `DSP4_BISECT` (0 =
     production, no park and no stamps; see item 3). Chip 2 runs the
     fixed un-instrumented build (hung, harmless).
   - Flash/boot loop, all runnable from here now: build → scp `.ldr` to
     `app@192.168.1.219:/home/app/dspboot/` → S_RESET `*` on
     `/dev/serial0` (hold slaves; matrix-app stopped) → `dsp4_boot.py
     --dir /home/app/dspboot` → observe/readback → app restart.
   - Boot-tool quirk (re-boot from a RUNNING/hung state fails its first
     attempt on an SPI_RDY timeout and works on the immediate retry,
     ×3): **auto-retry added 2026-08-20** — `dsp4_boot.py` now takes two
     attempts per chip by default (`--attempts` to override), logs both,
     and never re-pulses `!RST_D` on the retry. **EXPLAINED 2026-08-20
     18:2xZ: the quirk was the inverted SPI_RDY polarity** (boot kernel is
     fixed active-LOW, HRM ch.40; the tool waited for HIGH and only ever
     "passed" because H1S1 drove the shared CS3/CS4 nets high until the
     CS1-6-inputs reflash). Polarity corrected; both chips now boot on
     attempt 1/2. The retry is kept — it costs nothing and keeps a part
     that genuinely needs it visible. Full write-up in the 17:16Z
     dispatch block, including the rev-D item: **R34/R22 are pull-DOWNS
     where the HRM's in-reset hold-off needs pull-UPS.**
   - Before any slave boot with H1S1 flashed: confirm !RST_D ownership
     (H1S1 PA13 = `!RST_D` vs the boot script's GPIO16 pulse). Checked
     2026-08-20: GPIO16 read 1 (released) throughout, and H1S1 does not
     drive the line — the Pi owns it in practice.

2. ~~**Flash H1S1.**~~ **DONE 2026-08-20** — full evidence in the
   dispatch outcome at the top of this file. Reflashed with the
   CS1-6-inputs build compiled against the running app's generation
   (`matrix-aligned.h`, full-id `e80ccab5d6d8`); all eight CS pins
   `GPIO_MODE_INPUT` in the disassembly; `app cli loadfw H1S1` clean;
   H1S1 + SW Left + SW Right all verify on reboot.
   **Correction to the earlier wording here: H1S1 had NOT "never been
   flashed"** — the hub flashed a matrix-aligned CS7/CS8-only build on
   2026-08-19 night (`logs/flash.log` ends 18:24Z, and all three MCUs
   have verified at every boot since). What the 2026-08-20 reflash
   superseded was that CS7/8-only image.
   Still open from this pass: H1S1's blink handler issues `DspTx(...)`
   SPI1 writes for CS1-8 every S_BLINK edge (dead ADAU-era LED writes —
   they select nothing now that CS1-6 are inputs, but they still clock
   the housekeeping bus). Delete them at the next H1S1 pass.

3. **Clear the bisect scaffolding in `dma_config.c`** once P2.2
   concludes — it is all behind `DSP4_BISECT` now (`DSP4_BISECT=0`
   already compiles the clean production path), so the deletion is
   mechanical: drop the `DSP4_BISECT` block, `DIAG_STAGE`, the parks,
   the `build.sh` passthrough, and `_diag_stage_set` in `diag.asm`.
   `bca0dde`'s deliberate `for(;;)` park + diag stamps go; the
   `l1_to_sys()` fix and the `sport_dma_base()` fix STAY. No image is
   shippable before this.

4. **dsp4_config.py — next tool up** once the wedge clears: expect LED
   stage 5 (waiting for host product config) → configure → stage 6 →
   audio → steady 1 Hz. Procedure + failure signatures:
   `MW/D32/DSP/diagnostics.md`. (Sync back from `/home/app/dspboot/`
   is DONE 2026-08-20 — `dsp4_config.py` was the only one that had
   drifted; see the dispatch outcome for the two rough edges in that
   gpiod-v2 port that are worth tidying when the tool is next used.)

5. **SPORT I/O pin check via CPLD feedback loop (PW 2026-08-20).** A
   loopback build of the LOGIC bitstream (STA-gated, hash-named, clearly
   NON-SHIPPING) routes SHARC SPORT outputs back to inputs so the DSPs
   self-verify EVERY SPORT pin/lane end-to-end: firmware counter-pattern
   generator + checker per lane, verdicts via the 0xE000 diag readback.
   Also closes the provisional TDM facts without a scope (BCKI/FSI pair
   order, CKRE/MFD, D24 within-ADC8 slot order) and settles the NI0-3/
   NO0-3 crossed-direction/reversed-index question against slot-map.csv.
   Gate: wedge fix verified on the bench + SPORTs configured (stage 6).

6. **Unified D24/D32 SPORT/TDM lane map (PW, decided 2026-08-20 — full
   detail + resolutions in mx26 tasks.md "decisions queue"):** rev C =
   converters 4×TDM8/direction as fabbed; rev D = 2×TDM16/direction via
   AK5558 cascade (TDM512 @48k/24.576 MHz, datasheet-verified; clkgen
   must pin BICK↓ vs MCLK↑ ±10 ns for cascaded slaves), freeing two
   lanes/direction; 1×TDM8 AK4619; Pi lane I2S→TDM8 with ADAU7302 MEMS
   injection at slots 5-6 (chip already strapped TDM8-slot-5, R42=47K);
   ONE TDM32 pair for the network role — OUT lane broadcast to USB +
   Dante simultaneously, IN lane single granted driver with enforced
   tri-state defaults (grant toggle = virtual soundcheck), D32 snake =
   the AES67 role on the same pair. Lands as tdm-lines.csv/slot-map
   revision + rev-D modlist entries. Open: 570Z scratch-fit for the
   freed pins/LEs; AK4458 slot-select check; D32_COMPAT legacy-box
   yes/no (PW). See also the D8 amendment (CM4 masters mic-pre gain;
   CS_M via spare CS5/6) in dsp4-architecture-decisions.md.

7. **Bench observations owed (PW):** LD1 ~1.5 Hz with the CPLD live;
   TEST1-4 on the scope (J15 DNP pads); blink-image rate = free CCLK
   measurement — write the measured rate down, don't just retune.

8. **Design note queued (PW 2026-08-19):** once RUNNING, the DSP diag
   LED and LOGIC LD1 should sync to the MH1 S_BLINK system heartbeat
   rather than free-run; diagnostic burst codes stay local.

## Blocked on PW (decisions, not work)

- **UART pass-through routing matrix** (`TODO(uart-passthrough)`):
  buffered pass-through vs selectable mux vs strobed arbiter. Pin
  inventory done; system decision needed before RTL. Audio bring-up
  only — not on the panel path.
- **D9 sign-off** (`dsp4-architecture-decisions.md`, [DRAFT] since
  2026-08-06): FPGA param plane — float wire, on-fabric ingest
  conversion, fixed ramps.
- **KR260 order** (SK-KR260-G; Farnell £323.57 vs ~$431 elsewhere,
  prices 2026-08-06). Procurement ONLY — the 2026-08-07 gate stands: no
  FPGA engineering until stable DSP+LOGIC on rev C. Capture order # +
  ETA here.
- **AI-attribution history question** — recommendation stands: LEAVE IT
  (59 pre-mandate commits keep trailers; rewriting means force-pushing
  new SHAs under ~15 cross-references). New commits carry none.

## Standing reference (condensed — full history in the archive)

**Lanes (2026-08-07 set):** (1) LOGIC CPLD — on hardware since 08-18;
unused-pin root cause fixed (`RESERVE_ALL_UNUSED_PINS` primary was unset
— every prior build ground-drove unused pins; trap documented in the
qsf), `fd6a5ec69198` flashed + regression-passed 08-19. (2) DSP firmware
— both SHARCs boot; six would-be-fatal bugs already found by HRM review
(IVT SEC vector, wrong SPI port, RUWM, EMISO, TXCTL, SEC ack); P2.2
wedge in progress. (3) FPGA — procurement only, gated.

**Card signs of life:** LD1 = LOGIC pin 59; LD3 = DSPA `PA_12`; LD2 =
DSPB `PA_12`; `PA_13` = shared `!BLINK` net (input — never drive).
TEST1-4 = CPLD pins 13/12/8/7 → J15 (DNP DIL254-10: pins 1/2 +3V3, odd
GND, even TEST1-4). LED fault codes: N flashes = completed stage N,
stuck in N+1 (1 SRU, 2 SPORT, 3 DMA, 4 int-enable, 5 waiting host
config, 6 configured/no audio); healthy = steady 1 Hz square. Diag
readback block at 0xE000 (24 regs + generic MMR peek window) via
`dsp4_diag.py` — the emulator substitute; every read carries an echo
word, checked host-side. SPI_RDY: chip1 GPIO8, chip2 GPIO12, FCPL=1
(ready = high; the 10K pulldown means in-reset reads not-ready). No
SHARC JTAG on rev C (JTG_* float; rev-D item — 2-pin SWD per chip is the
cheap option, ADI-tooling support unverified).

**Boot path:** CM4 SPI2 slave boot, BMODE 0b010; CS1/CS3 = DSPA, CS2/CS4
= DSPB (CS2 = GPIO24, NOT GPIO7); `!RST_D` = GPIO16 — ONE reset line for
BOTH DSPs (a reset re-boots both); 1024-byte units; spi0-0cs overlay (no
CE pins — GPIO7/8 stay JTAG TCK / CS3-RDY1). `dsp4_boot.py` = gpiod v2.
CM4 CPLD JTAG: TCK=GPIO7 TDO=22 TDI=23 TMS=25, IDCODE 0x020a30dd.

**Build:** `./build.sh all` in `MW/D32/DSP/SHARC/` (native 21564;
fit-proxy retired). Scratch copies need `cp -aL` — `Core/Inc/matrix.h`
is a symlink into `MX/` and plain `cp -a` leaves it dangling. H1S1/panel
MCU builds: Dropbox FW home via `Debug/makefile.linux` (CM4 or here);
access Dropbox through the space-free symlink `~/db` (escaped spaces
stall dispatched sessions).

**CCES licence (AD-CCES-NODE-1):** a node-locked activation COUNTER —
4 max, no customer-side release (ADI case CS-601771-T5L1J6); 1 of 4
spent on this box; a wipe or NIC change burns one permanently. Licence
material untracked in `cces-tools/` (gitignored); originals in Dropbox
`TransferOnly/`.

**Rev D:** single mod source = Dropbox
`TransferOnly/PCB mods/dsp4-revD-modlist.md` (D8 scope: CM4-core SPI
control; supervisor shrink → G0B1/U535; PSRAM on OSPI0 + runtime link to
SPI0/1; 5M570Z CPLD — PIN_8/TEST3 must move; hardwire-chunk pass;
OSPI = 3.3 V domain → S27KL-class HyperRAM or APS6404L). Rev-C bring-up
verifies the provisional TDM facts (BCKI/FSI pair order, CKRE/MFD, D24
within-ADC8 slot order, S4 strap) → then rev-D freeze. CPLD-driven
SWD_EN3 = rev-D wiring candidate (SPARE reaches neither CPLD nor U7 in
rev C).

**MCU hygiene notes:** MH1 `'?'` responder is pre-loop only (S_RESET
before `loadfw`; proper fix = `'?'` in the ISR dispatcher). CheckS
unbounded ready/BUSY spin-waits + the blocking-HAL-read-in-ISR pattern =
rev-D firmware hygiene (patched on MH1/H1S3/H1S4 2026-08-19 — audit
other CubeIDE projects before reuse).

**Cross-repo:** Dropbox `_Matrix` = canonical cross-repo store (absorbed
as `matrix-shared-store.md`); mx26 checkout at `~/mx26` for contract
syncs (`git -C ~/mx26 pull` first).

## P3 — contract evolution (waiting on mx26)

- Tier-2 slots staged in `defs.lock` (`D24_DSP_CFG_SHA256`,
  `D32_DSP_CFG_SHA256`, ABSENT until mx26 provides dsp.csv files).
  Resume: when mx26 adds `src/pd/d24/dsp.csv` or `src/pd/d32/dsp.csv`,
  run `./regenerate-dsp-contract.sh --update-lock`.
- FPGA mixer engine for larger products — idea folder seeded
  (`fpga/README.md`, `fpga/node-portability.md`); activation gate:
  becomes a numbered architecture decision first.
- `mx_master.csv` as cross-domain SOT — deferred; notes in `ideas.md`.

## Done (foundation, collapsed)

- Contract pipeline complete: defs.lock, sync-from-mx26.sh, hash
  verification, validate-matrix-contract.py, regenerate-dsp-contract.sh,
  check-contract-drift.sh, release-notes convention, smoke checklist.
- Alias retirement complete (2026-07-18); DSP mapping gap closed
  (349 cells added upstream).
- Fixed-point conversion (D5) COMPLETE 2026-07-31 — mainline is Q4.28;
  float archived at tag `float-kernels-2026-07-31`; golden harness 9/9.
- Fabric remap + product-config boot block + plumbing slices 1-3 DONE
  2026-07-31; diagnostics instrumentation DONE 2026-08-12.
- D24 schematics imported + hardware map derived
  (`MW/D24/HW/hardware-map.md`); binding decisions D1-D8 in
  `dsp4-architecture-decisions.md`.

## Workflow reference

| Command | Purpose |
|---|---|
| ./regenerate-dsp-contract.sh | Full sync + validate + generate |
| ./regenerate-dsp-contract.sh --update-lock | Same but bumps defs.lock hashes |
| ./check-contract-drift.sh | Pre-merge check |
| ./check-contract-drift.sh --strict | Strict gate — fails on any unintended drift |
| python3 audit-compat-aliases.py | Refresh alias-audit.md |
| python3 validate-matrix-contract.py | MxAdd continuity + family allowlist check |

## State snapshot (2026-08-20)

- Contract: defs-v2026.08.20 (mx26 `345470a`) — first pin on the clean
  5161-cell post-naming-pass D24 master; D24 _matrix 5125 rows, D32 6940.
- Firmware: unified DSP4 per dsp4-architecture-decisions.md; ~75-80%
  written, hardware-verified fraction low — bring-up is the work.
- Hardware: rev-C card live; SHARCs boot; dma_cfg_init wedge = the one
  open blocker on the audio path.

## Owners and cadence

- Owner: DSP workflow maintainer (dispatched sessions + PW bench).
- Review cadence: update on every contract bump and when NOW items move.
