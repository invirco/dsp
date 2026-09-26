provenance: AI-drafted 2026-09-08 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# findings — dsp spoke

Numbered findings D1–D8x are recorded in `review-dsp-20260828.md` and in the
dispatch blocks of `tasks.md`. This file carries findings raised by dispatched
sessions after that review, newest first.

## THE INTER-CHIP FABRIC IS A WIRE, AND NOW SOMETHING ASKS WHETHER IT STILL IS (2026-09-26, session 118)

Hub dispatch `tasks.md` 2026-09-26 14:22Z. Report: `MW/D24/DSP/s118/main-recv.md`.

**S118-1 🟢 THE INTER-CHIP FABRIC HAS NO GAIN AND NO CONVERSION IN IT, SO THE
TWO MECHANISMS MOST OFTEN PROPOSED FOR S115-2 ARE RULED OUT.** `_gather_chip1`
(`chip1/block_io.asm:980`) writes the Q4.28 word straight into the IC TX DMA
half and `_scatter_chip2` (`chip2/block_io.asm:482`) reads it straight out; the
`Q1.31 <-> Q4.28` shifts live only on the CONVERTER lanes
(`chip1/block_io.asm:943`, `chip2/block_io.asm:529`). A LOST CONVERSION cannot
be the fault, because there is no conversion on this path to lose. A SLOT
ROTATION cannot be the fault on its own either: all 41 fabric slots carry
chip-1 buses or forwarded inputs, and with chip 1's graph quiet a rotation
substitutes one silence for another. `shared/dsp4-logic/tdm-lines.csv`
additionally rules out a CPLD loopback: `MIX_0..2` are DSPA `O0..O2` -> DSPB
`I0..I2` and nothing routes chip 2's output back to chip 2. Measured healthy
behaviour under a −6 dBFS tone, both ends of MAIN L and R: **0.03 to 0.08 dB
apart**, decaying together to −115 dBFS when the tone stops.

**S118-2 🔴 THE FOUR DMA HALVES ARE CONTIGUOUS AND CHIP 2's Q1.31 TRANSMIT
HALVES SIT DIRECTLY ABOVE ITS INTER-CHIP RECEIVE HALVES.** Read off the part:
IC RX ping `0xB4770`, IC RX pong `0xB4A00` (+656 = `c2_ic_region_words`), TX
ping `0xB4C90`, TX pong `0xB4F10` (+640 = `c2_tx_region_words`). A receive-side
read that strays one region high lands in `_gather_chip2`'s output — Q1.31,
saturated at `0x7FFFFFFF` — and reports it as Q4.28: **x8, saturating,
sustained, with chip 1 silent, surviving a config commit and cleared by a
boot.** That is S115-2's signature including the factor of 8 hiding in
`+18.06 dBFS` and in the word `0x7FFFFEE0`, which is exactly `0x0FFFFFDC << 3`
— a 0 dBFS Q4.28 word sitting in Q1.31 position. The generated tables cannot
reach there (the largest address the scatter can form is 655 of 656), so this
needs `_ic_rx_active_buf` itself to be wrong, and the ISR toggle that maintains
it (`sport_init.asm:320`) is self-correcting. **No root cause is claimed** —
but this is the first hypothesis that accounts for the arithmetic rather than
only the symptom, and `s118_probe.py` prints all four pointer words on every
run, so the next occurrence decides it in one read.

**S118-3 🟡 S115-2's `_buf_C2_RECV_MAIN_L` READ SPANNED THREE DIFFERENT
VARIABLES.** Under `DSP4_BLOCK_KERNELS` that symbol is a SCALAR staging word —
the node file says so in as many words — and the block is
`_blk_C2_RECV_MAIN_L`. The 16 consecutive words S115 read covered the scalar,
three words of padding and 12 words of the NEXT node's `_rx_ic_slot`. The
finding stands (those words are still fabric-delivered MAIN data) but the
`+18.06 dBFS` peak may belong to MAIN_R rather than MAIN_L. Read `_blk_`.

**S118-4 🟡 A CM4 REBOOT LEAVES THREE PIN TRAPS BETWEEN THE HOST AND THE DSP
LINK, AND TWO OF THEM ARE NOT THE KNOWN ONE.** Measured after `systemctl
reboot` on MW-D24-2: GPIO27 (`CS_M`) back to `ip pd | lo`, the known U2/MISO
trap — the parameter link cannot phase; AND GPIO6/GPIO24 back in ALT, so both
chip selects sit asserted and the link answers as **"CHIP 3"**. Only
`7,9,10,11,22,23,25 a0` + `6,24 op dh` + `27 op dh` — what `pin_handback()`
does — makes a perfectly healthy pair readable. **The pair itself survived the
reboot**: `FRAME_COUNT` climbed straight through it and the fabric was still a
wire afterwards, so a host reboot is NOT a way to produce S115-2.

**S118-5 🟢 THE DETECTION IS A COMPARISON, NOT A THRESHOLD, AND IT LIVES IN
`ensure_pair()`.** `tools/pi/dsp4_icrecv.py` asks the one thing the fabric's
own construction guarantees — what chip 2 receives on MAIN equals what chip 1
sent — so it needs NO setup, writes nothing and has nothing to put back, and
is true at digital silence, under a tone and with the rails up. `IC1` in
`d24_selftest.py` reports it; `ensure_pair()` consults it and BOOTS THE PAIR on
a `no`, which is S117-3's structural fix: `link_alive()` was asking MAGIC and
BOOT_STAGE, both of which a pinned pair answers perfectly. A forced boot is
still reported as an `IC1` FAIL (`Rig.ic_forced_boot`), so repairing a unit
cannot turn it into a clean report. **Cost measured on the part: 0.706 s for
the gate, and an `--only AL1` press is 41 s against 39-41 s on the S118-pre
rollback.** Every arm is proven on the part — PASS, FAIL on each of the two
rules (limits moved onto a healthy part's own reading with `--ceiling` /
`--gain-tol` rather than a fault being faked), NO DATA with `!RST_D` held, and
the forced boot through the runner with `--ic1-ceiling -110`.

**S118-6 🔴 THE STATE DID NOT RECUR AND WAS NOT REPRODUCIBLE.** Five
deliberate perturbations, each ending in a full-fabric survey, all negative: a
−6 dBFS tone on and off (no latch); config commits on a running pair; the two
chips booted 10 s apart (`!RST_D` resets both together, so this is the only
staggered case that exists); a CM4 reboot with the pair left running; and six
self-test passes including one full `--section A,B,C` and five later
`--only AL1` presses that did not boot the pair — the exact S117-3 condition —
every one of them `AL1 PASS` with SNR 12.9 to 33.1 dB. The unit was also found
CLEAN at 15:25 BST with every stage of the chain at exact digital zero. **No
root cause is claimed.** The ranked hypotheses and the single experiment that
decides each are in the report §2; H1 (S118-2) is the only one that explains
the arithmetic.

**S118-Q1 🟡 FOR THE HUB, ONE LINE IN mx26's GENERATOR.** `IC1` has no
workbook row: `ITEMS['IC1'] = []` (the `USB-HUB` precedent), because rows
139/140 are the LINKS and already belong to `AS-DSPA`/`AS-DSPB`, and taking
them would let an `IC1` PASS overwrite an `AS-DSPB` FAIL on the same row.
Nothing was invented in this tree (S117-1's rule). Giving it a row of its own
is a new `Inter-board links` item — *Inter-chip mix fabric (dig-dsp-a ->
dig-dsp-b audio)* — APPENDED, so its number is above every existing one and
**nothing renumbers**, with `tests = IC1`, `automation = 1`, `group = A4`.
Until then the gate is fully effective inside `ensure_pair()` and its verdict
lives in the run log rather than in the results CSV.

## THE CATALOG'S PASS CRITERION IS ONE ROW OUT OF STEP FOR 75 CONSECUTIVE ROWS (2026-09-26, session 117)

Hub dispatch `tasks.md` 2026-09-26 13:17Z. Report: `MW/D24/DSP/s117/run-all.md`.

**S117-1 🔴 `pass_when` ON ROW N CARRIES THE CRITERION OF ROW N−1, FROM ROW 128
TO ROW 202.** Not a handful of rows and not new: S116 found the same shift on
rows 127/203, fixed those two by hand and left the rest flagged. Read across the
catalog the shift is unmistakable — row 128, the Ethernet socket, carries the
screen link's criterion (127's); row 133, the mains inlet, carries the second
HDMI socket's (132's); row 134, the power switch, carries the inlet's; row 140,
the DSP-B link, carries AS-DSPA's; row 198, the ADC, carries AS-DAC's; row 202,
the H1S1 MCU, carries ML-M's. The leading tag of each row's `pass_when` matches
the `tests` of the row ABOVE it for every row in that range.

Three consequences. The wizard's DETAIL page prints **PASS WHEN** straight out
of this column, so 75 rows tell a technician the wrong criterion today. A
generated INSTRUCT dialog built from it would tell an OPERATOR to do the wrong
thing, which is why S117 builds its manual dialog text from `board` / `item` /
`class` / `group` and publishes the generated wording in
`MW/D24/DSP/s117/manual-dialogs.csv` for review instead. And no manual row has a
usable numeric limit, so the meter station's question has to be "does it read
what the build sheet gives for it?" until the catalog carries limits belonging
to their own rows. The fix is in the hub's generator (mx26
`tools/d24/build-d24-test-skin.py`, `scrape_spec`/`build_catalog`); this repo
consumes the catalog and must not patch it here.

**S117-2 🟡 ROW 148 IS `automation 1` AND IN THE ANALOG-LOOPBACK STATION.** RUN
ALL orders by `group`, so it is stepped as an operator check and the disagreement
is printed on every run rather than resolved silently. One of the two columns is
wrong; the generator owns both.

**S117-3 🔴 THE ACOUSTIC LOOP'S `NO SOUND` ON MW-D24-2 IS S115-2's PINNED MAIN
BUS, AND A LATER PASS CANNOT CLEAR IT.** Both RUN ALL passes read `NO SOUND base
-18.0 tone -21.0 SNR -3.0 dB` and `base -15.9 tone -18.9 SNR -3.0 dB`; the same
check on the same unit at 13:33 the same afternoon read `base -55.4 tone -35.8
THD -31.8 dB 2.56 %` and PASSED. A base 37 dB high on the MEMS lane is exactly
the state S115 recorded (finding S115-2): the chip-2 MAIN bus pinned near full
scale, which makes the loop's SNR meaningless. S115 measured that a full boot +
configure twice clears it and that a configure alone does not. **S117 measured
the clearing directly**: straight after the second pass, `--section B --only
DR1,DR2` (reset + boot, BOOT_STAGE 7/7, 31 lanes carrying) followed by
`--section C --only AL1` read `PASS base -55.5 tone -34.8 SNR 20.6 dB THD -32.0
dB 2.53 %` — a base 37 dB lower and the distortion figure S115's ceiling was
calibrated against. **The RUN ALL
consequence is structural, not incidental:** a pass after the first does not
boot the pair when the link is alive (S114's saving, right for every other
check), so a unit in this state carries a fictional acoustic verdict through
every later pass. The one-line fix — the acoustic check asks for a boot when it
is owed on a later pass — is flagged for PW rather than taken, because it
changes the automatic set's cost and this dispatch's bar was to leave that set
alone.

## THE PANEL SPEAKER IS LIVE FROM THE MOMENT THE PAIR BOOTS (2026-09-26, session 115)

Hub dispatch `tasks.md` 2026-09-26 11:39Z and its addenda. Report:
`MW/D24/DSP/s115/al1-thd.md`.

**S115-1 🔴 THE MONITOR BUS AND EVERY STRIP'S `MainOn` ARE AT UNITY OUT OF THE
IMAGE'S OWN INITIALISERS, AND THE SPEAKER AMPLIFIER IS NOT ON AN_EN.** Measured
straight after `dsp4_boot.py` + `dsp4_config.py` on both chips with nothing else
written: `Mon001Level001 = 1.0`, `Mon001Level002 = 1.0`, `Main001Level001 = 1.0`,
`Chan001/002/012/020/024MainOn001 = 1`, `Chan001Level001 = 1.0`. `defs` declares
`C2_MON` as `level_l_db=0.0;level_r_db=0.0` — unity — so there is NO resting
value in the graph that is silent. The TS482 (digital U32) runs from the 5 V on
the digital board, always on while the unit is up and independent of AN_EN (PW
2026-09-26). So the panel speaker plays whatever the MAIN bus carries from the
moment the pair boots, before any test writes a cell, and pressing DR1 or DR2 is
enough to do it. PW heard exactly this at the bench as continuous noise with no
test running. AL1 additionally left its own route asserted at the end of every
press and never tore it down; S115 fixes the runner (`al1_silence`, four cells
read back, after AL1 and after any run that boots) and `dsp4_loop_thd.sh`, but
the GRAPH DEFAULT is the root and only S117 — the speaker on its own haptic node,
off every mixer bus (PW ruling 2026-09-26) — removes it.

**S115-2 🔴 THE CHIP-1 -> CHIP-2 MAIN RECEIVE CAN SIT PINNED AT Q4.28 SATURATION
WHILE CHIP 1 SENDS SILENCE, AND A CONFIG COMMIT DOES NOT CLEAR IT.** Measured on
the as-found unit at 12:41-12:47 BST: `MainL001Mtr001` (the product's own meter
cell) 7.09-7.99 linear = **+17.0 to +18.1 dBFS** sustained, `_buf_C2_MIX_MAIN_L`
+16.6 dBFS, `_buf_C2_RECV_MAIN_L` +15.3 dBFS with words at `0x7FFFFEE0` (±8.0 in
Q4.28 = saturation), while `_buf_C1_BUS_MAIN_L` — chip 1's own MAIN block — read
−117.8 dBFS, and with EVERY strip's `MainOn` at 0 and the 595 chain at SAFE.
`dsp4_config.py` on both chips did not clear it; a full `dsp4_boot.py` + config
twice did, and the same cells then read −106 dBFS. Controls after the boot rule
out routing, rails and preamp gain: every strip on MAIN at unity gives −107 dBFS
with the chain SAFE and −74 dBFS at micGainFull, and every strip closed gives
exactly zero. **Not reproducible on demand, so no root cause is claimed.** Two
consequences: any AL1 press taken in that state is fiction (the press at
12:47:42 UTC read `base -15.9 tone -18.7 SNR -2.8 dB THD+N -0.4 dB 95.8%`, a
41 dB rise on the MEMS lane caused purely by asserting the route into that bus,
against −56.9 dBFS with the route down), and nothing in the self-test detects it.

**S115-3 THE S49 NODE'S `ThdResult` IS NOT A USABLE DISTORTION FIGURE FOR THE
ACOUSTIC LOOP.** It is the window's total RMS minus a single-frequency quadrature
fit over 4,096 samples. Measured on this unit, same lane, same drive, on a
PASSING press: `ThdResult` −6.51 dB = **47.2 %** while the bandpass THD of the
same window is −31.83 dB = **2.56 %** and the same window's own FFT
total-minus-fundamental is −31.75 dB. Across two independent 15-run calibration
grids three minutes apart, bandpass THD repeated to 0.05 dB and rose
monotonically with drive (1.0 / 2.6 / 4.0 % at −12 / −6 / −3 dBFS); `ThdResult`
moved by up to 6.5 dB at the same drive and was non-monotonic, and its two worst
readings of the session (34.5 %, 35.1 %) came from the two QUIETEST baselines
(−74.7, −78.9 dBFS). PW ruled on 2026-09-26 that AL1 reports bandpass THD only;
`ThdResult` stays as an informational line. Note also that the old ceiling was
`thdn_abs_db = -16.7 dB` and a healthy loop today read −17.1 dB cold and −20.8 dB
warm on the untouched pre-S115 runner: **the old verdict sat 0.4 dB inside its own
limit on a good unit.**

**S115-4 A STRIP NODE'S `_buf_` READS AS ANOTHER NODE'S WAVEFORM, NOT AS ZERO.**
Under block kernels strip node buffers live in the block pool
(`gen_input_tdm`: "the pool is for strip inputs only"). On the bench
`_buf_C1_FDR_01`, `_buf_C1_FDR_12` and `_buf_C1_FDR_20` all captured +5.95 dBFS
RMS, peak +11.97 dBFS, bit-identically, while `C1_IN_01/12/20` read exactly zero.
So `[[dsp4-buf-symbols-are-not-buffers]]` is worse than "plausible zero": it is a
plausible WAVEFORM belonging to whatever last used that pool slot. The taps that
are real are the buses and the non-strip converter lanes, which declare their own
`_buf_<nid>[DSP4_BLOCK_SIZE]` — `C1_XIN_MEMS` among them, which is why AL1's
coherent capture uses it.

## THE CODEC'S DAC IS FED A CONSTANT ZERO BY THE CPLD (2026-09-24, session 108)

Hub dispatch `tasks.md` 2026-09-24 15:54Z. Dispatched to deep-dive the AK4619's
DAC/output path after PW measured nothing at `U3.22 (AOUT1L)` at the bench.
Report: `MW/D24/DSP/s108/dac-path-root-cause.md`.

**S108-1 🔴 `assign cdc_i = strap_d32 ? 1'b0 : o_dspb[2]` AND `strap_d32` IS
HIGH ON A D24, SO THE CODEC'S SDIN1 HAS ALWAYS BEEN TIED TO ZERO.**
`rtl/dsp4_logic_top.v:792`, unconditional, one commit in its history
(`e9b0f7da`, the original routing top) — so this is every bitstream this bench
has ever carried. The strap reading is measured, not inherited: `rtl:781` is
`i_dspa[5] = strap_d32 ? snake_in : 1'b0`, and on the shipping bitstream
(`design_id 32'h83b3cc22`, read off the part, no flash) lane 5 reads
`0xFFFFFFFF` = `snake_in`'s weak pull-up, where a low strap would give the hard
`0x00000000` that lane 6 shows. **The codec converts a constant, `AOUT1L` sits
at its DC bias, and that is the entire symptom.** The ADC side works because
`i_dspa[4] = cdc_o` is a plain wire with no strap — every test this codec has
ever passed was an ADC test, and the strap gates only the send path. **The
codec is not at fault:** all 21 registers read back live and equal the init
image byte for byte, with PMDA1/2 = 1, RSTN = 1, DAC volumes at `0x18` = 0.0 dB
(Table 19 — *not* the ADC's law, whose zero is `0x30`), `DA1MUTE`/`DA2MUTE` = 0,
TDM256 I2S with `SLOT` = 1, `FS` = 000 matching a board that ties BICK and MCLK
to one net, and `DAC1SEL` = SDIN1. Per datasheet Table 8 the part is in Normal
operation, so `U3.22` must idle at AVDD/2 ≈ 1.65 V — the measurement that
confirms it from the analog side.

**S108-2 🔴 `12H` IS THE RESET DEFAULT AND THE DEFAULT IS WRONG FOR THIS
BOARD — THE AUX OUTPUTS CANNOT WORK EITHER.** `DAC2SEL` = 01 selects **SDIN2**,
and datasheet 9.3 says input on SDIN2 is *ignored* in TDM mode, while the
netlist says `U3.2` is **N/C** (`G3619`) — the datasheet's own unused-pin rule
asks for it to be tied to VSS2. So `AOUT2L`/`AOUT2R` = `CODEC_OUT_3/4` = aux out
L/R are fed from nothing, independently of S108-1, and would still be silent
after it is fixed. One byte: `matrix.cs` `ak4619[]` index 21, `0x04` → `0x00`.
Not made here — H1S1 firmware, needs a flash.

**S108-3 🔴 THE D24/D32 PERSONALITY STRAP HAS NO DEFINED LEVEL.** `PIN_70` is
net `M MCU_S4` = `G2737`, and the netlist gives it exactly **two pins**: the
CPLD and `U8.11` (M MCU, STM32G031C8T6, DSP card). No pull resistor on the net,
no `WEAK_PULL_UP`/`DOWN` on the pin in the qsf, and MAX V I/O offers weak
pull-*up* only, so the CPLD cannot supply a pull-down. The level is whatever MH1
does with `U8.11` — and the M MCU's documented job is the S0–S31 matrix
signalling bus, so if `S4` is a live signalling line the strap may be **toggling
at runtime**, not merely stuck. Cheapest fix is MH1 driving it low (firmware
only, no CPLD flash, no new bitstream label); a pull-down on the net is the
belt-and-braces. Blocked on MH1's source, which is not on this machine.

**S108-4 ONE CAUSE, THREE SYMPTOMS, AND THE THIRD IS A LATENT HAZARD.** The same
strap leaves `snake_out` (PIN_110) and `dac_main` (PIN_111) **driven** on a D24
instead of high-Z (`rtl:823/824`) — precisely what S36-4's fix exists to
prevent so a card in option slot 2 owns its own lanes. Slot 2 is empty today;
fit a card and two drivers fight. S106-3 saw the strap and read only the
cosmetic lane-5 symptom from it.

**S108-5 THE AK4619 DATASHEET IS NOT MISSING, AND akm.com IS NOT BLOCKED.**
200900082-E-00 (2021/06, 73 pages) fetches with plain `curl` from
`https://www.akm.com/content/dam/documents/products/audio/audio-codec/ak4619vn/ak4619vn-en-datasheet.pdf`
(HTTP 200, md5 `57b8e7a0c41cdffe4b1336b4bf92e6d2`), byte-identical to the copy
already on this machine at `~/Stonepower Dropbox/Peter Watts/_mx/_0/tools/PCBA/
ConsoleApp1/bin/Debug/net6.0/PCBA/Datasheets/Codec AK4619.pdf`. S106's note that
analog.com blocks curl and WebFetch is true and does **not** generalise to other
vendors. **Trap:** `file` reports the local PDF as "3 page(s)" because it is
RC4-encrypted for copy-protection; `pdfinfo` says 73 and `pdftotext` extracts it
all. Do not discard the file on the `file` line.

**S108-6 THE DISPATCH'S PIN LIST OMITS THE TWO PINS THAT WOULD KILL EVERY ANALOG
OUTPUT AT ONCE.** `U3.5` is **AVDRV**, the internal 1.2 V LDO output, and `U3.17`
is **VCOM** (½ × AVDD, the output bias) — each needs a 2.2 µF cap to ground and
nothing else. Both are fitted and correct here (`G0202` = `U3.5` + `C18.1`;
`G0211` = `U3.17` + `C19.1`), so neither is a candidate, but they belong on the
list. Also: the dispatch's "no separate analog supply pin" is wrong — `U3.18` is
**AVDD** and `U3.3` is **TVDD**, two different supplies tied to the same `+3V3`,
which is what the datasheet asks for. The conclusion (not a rail problem, `AN_EN`
not in it) survives; the reasoning should not be inherited.

## THE MIC LANES WERE NEVER DARK: `_buf_C1_IN_nn` IS A SYMBOL NO BLOCK-KERNEL BUILD WRITES (2026-09-20, session 86)

Hub dispatch `tasks.md` 2026-09-20 15:05Z. Dispatched to bisect chip 1's
receive path between the S54–S58 firmware and HEAD. No bisect was run and none
was runnable: the receive path is not broken.
Report: `MW/D24/DSP/s86/rx-path.md`.

**S86-1 🔴 `_buf_C1_IN_01..32` IS NOT A BUFFER IN ANY BUILD THAT SHIPS, AND
NOTHING WRITES IT.** Under `DSP4_BLOCK_KERNELS` — every shipping and every
TEST_NODES pair — a node whose output feeds the next node of its own strip writes the shared
block pool: `_C1_IN_16_process` reads the RX DMA word and stores it to
`BLK_CHAIN_A`, and `_buf_C1_IN_16` is declared beside it as a single word that
survives only as linkage and as the identity token `_scope_tap` /
`_scope_inject_blk` compare `r0` against. Of chip 1's 442 nodes, 44 own a real
`_buf_<nid>[DSP4_BLOCK_SIZE]` — the 15 `XIN_*` lanes and the 29 buses — and
398 do not. **So "four codec buffers move and thirty-two mic buffers read
exact digital zero, in the same pass, on the same bitstream" is not a fact
about pins. It is the difference between a buffer and a linkage scalar.** The
warning was already in the tree three times (`dsp4_s39_chain.py`,
`dsp4_s48_audio.py`, `dsp4_node_verify.py`); the lane scanners never had it,
and S81's rewrite of `dsp4_inscan.py` moved the scan off one dead symbol
(`_rx_slot_C1_IN_nn`, correctly identified) onto another.

**S86-2 🟢 EVERY D24 MIC LANE CARRIES SAMPLES, READ OUT OF THE RX DMA REGION.**
`_rx_active_buf + off + k*stride`, geometry and node names taken off the part,
on the shipping bitstream `d02d83b3cc22` (design ID read back and MATCHED),
both chips BOOT_STAGE 7. Rails down: 24 of 24 mic entries carry the
converters' dither, 12–15 distinct words in 16 reads, RMS −112.6 to −119.9
dBFS — while `_buf_C1_IN_01` and `_buf_C1_IN_16` sat at exact zero in the same
pass as controls. Pin 3's eight entries (the D32's fourth AK5558), the eight
snake lanes and the MEMS lane read a constant `0xFFFFFFFF` and the two Pi
lanes a constant 0, which is correct for a card with nothing on those pins.

**S86-3 🟢 SIXTEEN LANES ANSWER THE ANALOG RAILS BY 30–50 dB.** Rails up, 595
unmuted at gain 63 (VERIFIED 200/200), same boot: `ad[1]`'s eight entries go
to −69.3…−83.3 dBFS and `ad[2]`'s to −64.6…−83.4, while `ad[0]`'s eight stay
at the dither floor. That is live preamp noise arriving through the AK5558s
and read from the DSP's own DMA region — the measurement ten sessions were
looking for.

**S86-4 🟢 ALL 47 RX ENTRIES DECODE THEIR OWN PIN AND SLOT, SPORT 0/1/2/3
INCLUDED.** On the `_laneid` bitstream (`12f4fd1cbfc1`, design ID
`32'hfd1cbfc1` read back) every entry carries `0xA5<pin><tick><slot>` naming
exactly the pin and TDM slot the generated lane table assigns it, at bit
offset 0 — with the two Pi lanes one bit out, reproducing
`c1_rx_lanes_mfd[6] = 1` against an MFD-2 build without being told. This
closes S85-7's hole in `driveall`'s proof: the hole was real and the binding
through it is correct.

**S86-5 🔴 S85-8 IS VOID, AND SO IS THE SAME CLAUSE IN S81-8, S82, S83 AND
S84.** "The fault is chip 1's RX path for sport 0/1/2" is disproved on the
same unit, the same firmware and the same bitstream. Those sessions'
measurements stand; the inference drawn from `_buf_C1_IN_*` does not. The RX
plumbing is also untouched since the S54–S58 reference: `sru_config.c`,
`sport_config.c` and `dma_config.c` have an EMPTY diff across
`aac62831..HEAD`, and `chip1/lane_config.c` does not touch lanes 0–3.

**S86-6 🟡 THE BENCH UNIT'S DEAD ANALOG SECTION IS EIGHT CHANNELS, NOT FOUR,
AND IT IS `ad[0]`.** All 24 channels surveyed at gain codes 63 and 0, register
under test alone open, TEST_MEAS on its own strip, rails up: U39's eight rise
32.5–36.9 dB and U60's eight rise 31.8–40.4 dB, while **U15's eight — panel
mics 1–4 and 13–16, XLRs J15–J22, preamps U17–U31 — rise −0.21 to +0.08 dB**
and sit at −116.0…−116.2 dBFS at both codes. That is S48's "MIC 1–4 section
the bench state records as DEAD" at "−114…−118 dBFS, what an unpopulated front
end reads", and S55's "J15–J22 … have no rails today: not tested" — a known
section whose EXTENT was not established, because S48 could only name four of
it while reading twelve lanes. It also closes S85-3: `ad[0]`'s indifference to
the rails is the dead section's converter converting with nothing in front of
it, and its `ones` high-water of 188 against 256 said so. 🔴 S86-N1 asks the
hub to correct the count wherever the bench state is written down — the
depopulated-section guard `dsp4_s42_align.py` has been owed since S48 has to
be sized to eight.
Separately, J15 (strip 1) reads exact digital zero through TEST_MEAS at both
codes while its RX lane carries dither — recorded, not diagnosed.

**S86-7 🔴 THE EIN ROW IS OWED ON A FIXTURE, AND THE NUMBER IS WHAT SAYS SO.**
The S54 loop check reads −142.81 dBFS where the loop cable gives −14.42, so
the cable is off. MIC 5 (J25, strip 5) then reads NoiseResult −77.31 dBFS at
code 63 → **EIN −109.89 dBu**, 17.3 dB above S55's −127.2 dBu at 150 Ω, with
an rms spread of 4.59 dB against 0.28–0.80 dB on every other row of the
session. Both are what an unterminated input does. The row needs 150 Ω across
J25 pins 2–3; what is recorded is the open-input noise row, labelled as such.
The talkback T1/T3 re-take is owed on the same cable. The dispatch's second
witness, MIC 14 (J18), is in the dead section (S86-6) and cannot be one: a
second EIN witness has to come from the sixteen channels that work.

**S86-8 🟢 THE INSTRUMENT IS FIXED AT THE POINT OF FAILURE.**
`tools/pi/dsp4_rxscan.py` is new and reads the DMA region, resolving geometry
and the patched node names off the part and carrying `_buf_C<chip>_IN_01` as a
must-not-move control so the trap is demonstrated on every run.
`dsp4_inscan.py` now scans `_buf_C<chip>_XIN_*` only — the buffers that exist
— and reads `_buf_C<chip>_IN_01` as a second dead-symbol control with the
pointer to the right tool. `dsp_codegen.py` makes every generated strip-input
node open its block-kernel arm with "`_buf_<nid>` IS NOT A BUFFER IN THIS
BUILD" and the one line that says what to read instead; comment only, so the
emitted code and data are unchanged and **the signed configuration's triple
does not move**.

**S86-10 🟢 THE GENERATOR CHANGE IS PROVABLY IMAGE-NEUTRAL, AND THE SIGNED
TRIPLE DOES NOT MOVE.** Built twice from the same tree with `./build.sh all`
on `shipping.config`, once before the change and the regeneration and once
after: `chip1.ldr e3e25a79…` / `chip2.ldr 41a6b913…` both times, and both
equal the image the S86 capacity arm built and ran. `regenerate-dsp-contract.sh`
clean at defs-v2026.09.19.3; `check-contract-drift.sh` leaves nothing but the
32 comment-only node files; `defs.lock` unmoved, so no contract note is due.
The audio bar is three for three against S82: golden harness 59/59,
`dsp_validate` OK with 701 nodes and the same 4 process-order notes, dry-run
187 of 187 (0 DIFF, 0 MISSING).

**S86-11 🟢 84.34 % HOLDS: THE S82 D24 DRIVEN ROW RE-TAKES AT 84.47 %.**
`ARM=s86d24 PRODUCT=d24 ./capacity.sh --driven`, both boots, 135,049–135,054
blocks a row, `build_cfg2 0xE2018E6F` read off the part during the
measurement, regime proved on both boots (48/48 chip 1, 28/28 chip 2). Rows
(two-boot means of `_proc_cyc`, the field S82 quotes): A 43.13/77.50, B
57.61/84.41, **C driven 57.55/84.47 (+0.02 / +0.12)**, zero missed blocks in
all twelve chip-rows. The boot spread is stated, not averaged away: chip 2's
row C read 84.20 and 84.73, a 0.53-point spread against the ~0.33 S82
documented — both boots bracket 84.34, and the three means on record now span
0.13 points (84.34, 84.35, 84.47). The dispatch's premise for the gate does
not apply: the mic lanes always carried data (rows A/B the converters'
dither, row C `driveall`'s broadcast), so nothing about the cycle count
changed tonight except what is known about it.

**S86-12 🔴 `logic_flash.sh` TOOK NO BENCH LOCK — THE ONE TOOL THAT
REPROGRAMS THE CPLD.** S80-12 gave seven bench drivers the lock and S82 gave
it to `loadlogic.sh`; the script that actually writes the bitstream and stops
`matrix-app` had none, so an arm landing on the card mid-flash was the S10
contention failure with a flash in the middle of it. Fixed the same way
`loadlogic.sh` does it, with `--self-test` exempt because it drives no bench;
nothing in the tree invokes the script so no caller can deadlock behind it;
proved with `--dry-run`. `dsp4_rxscan.py` joins the link-tool deploy in
`bench_lock.sh` for the same reason the other six are there.

**S86-9 🟡 MIC 5's NODE IS `C1_IN_05`, NOT `C1_IN_16`.** S82–S85 record
"MIC 5's own `_buf_C1_IN_16`". Under the landed S58 input patch J25 is strip 5,
node `C1_IN_05`, RX entry 15, DSPA pin 1 TDM slot 7 — what `d24_inputs.py`
says, what `_rx_patch_regs` says on the part, what S54's `MIC5_STRIP` has
always used, and what S86-6's gain response confirms physically. `C1_IN_16` is
the identity mapping of that DMA position, i.e. the pre-S58 answer.


## THE LAUNCH PHASE IS NOT THE FAULT, AND THE MIC LANES ARE NOT ON ANY PIN THIS CPLD DRIVES (2026-09-20, session 85)

Hub dispatch `tasks.md` 2026-09-20 13:57Z. S84 left one hypothesis standing —
the converter launch phase — and one proof unexamined. This session measured
the first and broke the second.
Report: `MW/D24/DSP/s85/launch-phase.md`. (S84's findings S84-1..9 are in
`MW/D24/DSP/s84/mic-lanes.md`; they were never copied here.)

**S85-1 🟢 THE TWO bck8 EDGES RETURN IDENTICAL COUNTS, SO THE LAUNCH PHASE IS
NOT THE FAULT.** The ad witness now runs six banks — three lanes on
`bck8_sample` and the same three on `bck8_launch`, counting the same 256 bit
periods of the same frames, 40.69 ns apart on an 81.38 ns bit period. Rails
down and rails up alike, the **toggle counts are identical, not close**
(26/26, 50/50, 48/48) and `ones` differs by at most 2 counts in 256. A lane
sampled on its own data transition cannot do that: half its bit periods would
resolve arbitrarily and both statistics would scatter. The data is stable
across the whole window between the two sampling points, and S84-6's
hypothesis is disproved by measurement rather than argued away. The knock's
bit 2 selects the edge and S84's three knock words have it clear, so the S84
readings are directly comparable without a correction factor.

**S85-3 🟢 S84-4's TOGGLE DOUBLING IS SIGNAL CONTENT, NOT A SAMPLING
ARTIFACT.** `ad[1]` 26 → 50 and `ad[2]` 26 → 48 when the rails come up,
`ad[0]` unmoved at 26 — reproduced exactly, and the second bank settles what
one bank could not: **the doubling appears identically on both edges.** A
sampling artifact would not. So it is the analog front end reaching converting
ADCs, measured from inside the CPLD. One new fact narrows `ad[0]`'s
indifference: its `ones` high-water is 188 in every run while `ad[1]`/`ad[2]`
both reach 256. The three lanes are three different AK5558s (`ad[0]` = U15,
mics 1-4/13-16; `ad[1]` = U39, 5-8/17-20; `ad[2]` = U60, 9-12/21-24), so U15
is converting and framing while its eight channels are not picking up what the
other two ADCs' are. Still a thing to look at, not a thing to conclude from.

**S85-5/S85-6 🟢 NEITHER A RETIMING REGISTER NOR THE CODEC'S OWN DATA REACHES
THE MIC BUFFERS.** Two builds, each flashed FLASH-OK on attempt 1 with its
design ID read back and MATCHED before any reading, each read two-sided in one
pass with both chips at BOOT_STAGE 7, rails up and the 595 at `0xFC` VERIFIED
200/200. `_adrt` makes `ad[0..2]` a register output launched on `bck8_launch`
— the arrangement `driveall` uses and that works — and the witness's launch
bank counts the very bits that register captures: **the register is loaded
with live converter data and the DSP reads exact zero out of it.** `_adcdc`
feeds all three mic lanes from `cdc_o`, the converter lane the DSP reads
correctly in the same pass: **mic 0 of 32 moving, codec 4 of 4 moving, the
same bits at the same instant.**

**S85-7 🔴 `driveall` NEVER PROVED WHICH PIN REACHES WHICH SPORT HALF, AND
FOUR SESSIONS READ IT AS IF IT HAD.** `i_dspa[5:0] = {6{pcm_drive}}` is six
pins carrying ONE signal, so a receiver reading any of them sees the same bits.
The test proves the pins reach the DSP; it cannot tell a correct lane mapping
from a permuted one, nor either from a receiver reading a pin this design
believes is elsewhere. Its successor `_laneid` gives every DSPA input lane a
different stream that names its own pin and slot
(`word[31:16] = {8'hA5, pin, tick, slot}`), and **it proves itself before it
accuses anything**: in the same pass `XIN_CODEC_01..04` decode to pin 4 slots
0-3, `XIN_MEMS` to **pin 7 slot 5** (the ADAU7302's 47K strap), and `XIN_PI_L`
to pin 6 — with its marker one bit later than the others, which is exactly the
MFD 1 half of `c1_rx_lanes_mfd = {2,2,2,2,2,2,1,2}` against this build's MFD 2
framing. The instrument reproduces the slot strap and the S78-3 framing
difference without being told either.

**S85-8 🔴 THE FAULT IS CHIP 1's MIC RX PATH, ON THE DSP SIDE, AND NO LOGIC
CHANGE CAN FIX IT.** With all eight DSPA input pins carrying distinct,
identified, non-zero streams, `IN_01` … `IN_32` read `00000000` — no marker,
nothing from any pin — while six other buffers on the same chip in the same
image in the same pass decoded their own pin and slot correctly, three
different pins across six slots. It is not the
converters, not the analog board, not the clock pair, not the launch phase and
not the CPLD's lane path in any of the three forms built today. It is SPORT/SRU
configuration, lane binding or RX DMA for chip 1's sport 0, 1 and 2.

**S85-14 🟢 THE EDGE COMPARISON HAS TO REST ON `toggles`, NOT ON `ones`.**
The two banks COUNT concurrently but are READ by separate knocks seconds
apart, so `ones` -- simply what the converter was emitting -- drifts with the
content between the two readings. The reader's first verdict rule took the
LAST knock and flagged either statistic moving by more than 4; on the shipping
re-take that called `ad[0]` a phase difference because `ones` wandered 96-101
on the sample bank against a flat 96 on the launch bank, while `toggles` was
26 on both edges in all six knocks. `toggles` is the statistic that MUST move
if a sampling point sits on a transition -- half those bit periods would
resolve arbitrarily and the count could not repeat -- so the rule now takes
the median across knocks, rests the verdict on `toggles`, and reports a large
`ones` difference as content drift rather than as evidence. No conclusion
changes; the reasoning behind S85-1 does.

**S85-13 🟢 THE S82 84.34 % D24 DRIVEN ROW HOLDS ON THE ADOPTED LABEL.**
Re-taken the way S82 took it -- `ARM=s85d24 PRODUCT=d24 ./capacity.sh
--driven`, no command-line override, on the matching new driveall build
(`943f27966c28`, design ID read back and MATCHED), both boots, 135,000 blocks
a row, `build_cfg2 0xE2018E6F` read off the part DURING the measurement, and
the driven regime proven twice at 48/48 and 28/28 envelopes. **Driven chip 2
84.35 % against 84.34 %, a delta of +0.01** -- an order of magnitude inside
the ~0.33-point boot spread S82 documented for that very row. Chip 1 57.62 vs
57.54; silent rows 43.13/77.54 and 57.50/84.36; **zero missed blocks in all
twelve chip-rows.** Adopting the label costs nothing measurable, which the
byte-identical lane path predicted and this now measures.

**S85-11 🟢 `build.sh` HAD THE `CFG_LINE` HOLE ONE LEVEL UP.** `SRC_HASH`
covers `rtl/*.v`, the qsf, the sdc, the slot-map hash and `CFG_LINE` — but not
`build.sh`, and `CFG_BITS` is computed BY `build.sh`. Adding a cfg bit for a
new switch changed what a part answers to the ID knock while leaving its label
identical: two functionally different bitstreams sharing one label, the exact
failure the `CFG_LINE` paragraph exists to prevent. Caught on the first
artifact it affected, before anything was measured on it, and closed by
putting the computed word into `CFG_LINE` so any future change to the
derivation renames every artifact it changes.

## THE MIC ADC LANES ARE NOT DARK — ad[0..2] CARRY DATA AT THE CPLD WHILE THE DSP READS ZERO (2026-09-20, session 84)

Hub dispatch `tasks.md` 2026-09-20 12:2xZ. Copied here at hub ruling S85-N3 —
these findings lived only in `MW/D24/DSP/s84/mic-lanes.md`, which is not where
a reader searching this file for S84-4 would look.
Report: `MW/D24/DSP/s84/mic-lanes.md`.

*Read with S86-1: every S84 statement about `_buf_C1_IN_*` reading zero is a
statement about a symbol nothing writes. S84-1, S84-3, S84-4 and S84-7..9 are
unaffected; S84-2's "there is no bisect to run" is right for a reason S84 did
not have, and S84-5/S84-6 are void.*

* **S84-1 🟢** "Pre-S34" is not the discriminator for the converter clock: the
  step-0 lineage does not contain `ded71079` and drives the pair anyway, with
  the same two assignments HEAD carries. Two lineages drive it, one artifact
  does not, and nothing may be inferred from a build date.
* **S84-2 🔴** 32 of 32 AK5558 mic lanes read exact digital zero on
  `s41_mhrx_pullup_off` — the bitstream the flash log puts under S54–S58 —
  with all four codec lanes live in the same pass. Three bitstreams, one
  answer: there is no bisect to run. *(S86-1: the reading is of the dead
  symbol; the conclusion that there is no bitstream bisect to run stands.)*
* **S84-3 🟢** All three `ad[0..2]` lanes are CARRYING DATA at the CPLD: ~95 of
  256 bit periods high, 26–50 transitions per frame, high-water 186–188, with
  the `cdc_o` control arm answering data and every frame counter advancing.
* **S84-4 🟢** `ad[1]` and `ad[2]` roughly double their toggle count when the
  rails come up and the chain is unmuted; `ad[0]` does not move. Recorded, not
  yet diagnosed. *(Diagnosed at S86-6: U15's eight channels pass no signal.)*
* **S84-5 🔴 VOID (S86-1)** Pins moving and buffers at exact zero in one pass
  on one bitstream, both controls satisfied; "the break is between the CPLD's
  `ad[0..2]` input pins and the graph buffers". The buffers read were linkage
  scalars and there is no break.
* **S84-6 🔴 VOID (S85-1, S86-4)** The launch-phase hypothesis. Disproved by
  measurement at S85-1, and the binding it doubted is proved correct at S86-4.
* **S84-7 🟢** The shipping build's label moves to `0cc6f94444b2` at HEAD as an
  unavoidable side effect of touching `rtl/`. The artifact on the part is
  unaffected and now records `built_from: a1536bc6`, verified.
* **S84-8 🟢** `logic_flash.sh`'s default rollback was stale for the third time
  in its history — naming `s41_mhrx_pullup_off` a day after the part stopped
  carrying it. Fixed, and the flash log it says to set it from is now a table
  rather than 2.2 million lines.
* **S84-9 🟢** The witness's lane echo earned its bits on its first run: the
  reader extracted the lane from bits [25:24] instead of [26:25], which is
  `{lane[0], ones_last[8]}` and therefore reads correctly for lane 0 and
  wrongly for lanes 1 and 2. It reported a mismatch and refused to print
  numbers rather than reporting lane 0's data three times. The testbench
  stand-in had the same wrong layout, which is why sim passed — fixed to the
  real layout, so the class is caught in sim from here.

## THE THREE ANSWERS LAND, THE LATENCY ROW IS TAKEN, AND THE MIC LANES ARE DARK (2026-09-20, session 83)

Hub dispatch `tasks.md` 2026-09-20 12:18Z. The hub answered S82's three
questions; this session landed them, re-took the two rows S82 owed, and
measured the mic ADC lanes on the fixed bitstream.
Report: `MW/D24/DSP/s83/contract-lanes.md`.

**S83-1 🟢 FOUR OF FIVE famverify RUNS COULD NOT READ A NODE'S STATE, AND IT
WAS THE VOTE.** `read_params` returns a word only after seeing the same value
twice in eight asks — right for a PARAMETER, which is static between block-rate
conversions (every one of COMPRESSOR's six converted words read first time,
including the two that are genuinely zero, so the zero sentinel was armed and
working), and wrong for STATE. `_comp_envelope_` and `_gate_envelope_` are
written on EVERY SAMPLE; an eight-ask vote over a word the part is still moving
can only agree by accident. It is the class `dsp4_scope.rd_counter` exists for.
The state read also happens immediately after a STEP capture, when the envelope
is furthest from rest: COMPRESSOR got ONE attempt by construction and GATE
broke out of its own three-attempt rest-watcher on `st is None` before reaching
it, so both died on the first try every time. Fixed by waiting for the state
and SAYING HOW LONG IT TOOK (`read_state`, the rule the gate's rest-watcher has
followed since S21-5). **The consequence is a verdict no session had obtained:
`GATE` numeric goes `NO_STIMULUS` → `BIT_EXACT`**, i.e. the signed
`DSP4_GATE_LINTHR` arm scoring bit-exact against the linear-threshold model on
the part. A second defect went with it: `run_node` returns `(0,0,0)` both when a
stimulus separated nothing and when it never ran one, and `numeric_phase` scored
both `NO_STIMULUS` — so "the bar could not read the node" was recorded as "no
stimulus moved it". There is now `NO_VERDICT` with a `reason`.

**S83-2 🟢 `latency.sh`'s BOOT: `dsp4_config.py` EXITED AT IMPORT AND THE ERROR
WENT TO `/dev/null`.** The config tool reads the input patch from a file beside
ITSELF and `sys.exit`s at import when it is absent (`dsp4_config.py:96-100`). A
staged arm links `~/dspboot/*.py` into its stage directory, so the tool is a
symlink but `__file__` is the LINK and the lookup lands in `$STAGE`, which had
no `input_patch.json`. Reproduced by hand in S82's own stage directory before
any edit. The chips therefore booted and were NEVER CONFIGURED — both at
BOOT_STAGE 5 on all four of S82's boots — and the 0.0 % coherent fraction the
bar reported was a correct reading of an unconfigured part. **It is a class:
46 occurrences of the staging block in 44 scripts had the same gap**, proved
within the hour when the first S83 famverify run, staged to a fresh directory,
failed identically and still wrote a 27-family table of dashes and exited 0.
All 46 fixed at the source; `latency.sh`'s link is deliberately OUTSIDE its
`BUILD=1` guard, because `BUILD=0 STAGE=…` is exactly the arm that skipped the
staging block. `latency_run.sh` now retries the whole boot, checks MAGIC before
believing BOOT_STAGE, prints the config error instead of discarding it, and
EXITS NON-ZERO rather than taking its reps; `dsp4_family_verify.main` returns 4
when a chip was not ready.

**S83-3 🟢 THE LATENCY ROW IS TAKEN AND THE 82-SAMPLE CONTRACT DOES NOT MOVE.**
Signed pair (`e3e25a79`/`41a6b913`) on `maincap`, both chips BOOT_STAGE 7:
offset median **14515** (14510…14529), **100.0 % coherent on 20 of 20 reps**,
where S82 got 0.0 % on forty. LOGIC-only reference RE-TAKEN the same session on
`pisel`: median **14435** (14427…14436), 100.0 % coherent — reproducing S20's
14,433 to two samples. **Through-DSP latency 80 samples at block 16.** 82 is
inside the through-DSP arm's own 19-sample spread, so the reading is consistent
with the contract number and does not replace it; moving it needs an arm whose
spread is smaller than the change claimed.

**S83-4 🟢 `FADER_PAN` CLOSES: THE PART WAS RIGHT AND THE MODEL WAS WRONG.**
`Pan` is an INDEX. Under `DSP4_PAN_TABLE` — the shipping default
(`src/dsp_block.h:148-151`) — the kernel computes `fix(pan × 126.0)` in float32
(`fix` rounds to nearest, ties to even, no `+0.5`), clamps to `0..126` and reads
the resident table (`src/chip1/pan_law.asm`), so the cell has 127 positions and
a host float between two of them lands on one. S82 drove `Pan = 0.317`, 0.058 of
a step off position 40; the part answered position 40's legs — `86/126` and
`40/126` EXACTLY — and `fixed_ref.fdr_coeffs`, which models the pre-R5
arithmetic, called it a mismatch. `fixed_ref.fdr_pan_legs` now quantises through
`tools/dsp/pan_table.py` (the law is not duplicated) and `_fdr_setup` drives a
value that IS a position. The new model reproduced the part to the word AT THE
DESK before any bench run, and the bench confirmed it: **`FADER_PAN` numeric
`FAILED` → `BIT_EXACT`**, both stimuli, negative control firing as predicted.
Nothing about the part changed. PW's Q3 ruling, executed.

**S83-5 🟡 THE COMPRESSOR WITNESS WAS NOT RE-MEASURED, AND THE REASON IS NOW A
READING.** With the state readable, COMPRESSOR reaches the next stage and stops:
the repeat capture — two runs of the same stimulus from the same rest, which the
bar correctly requires to be identical — never starts from the same place.
**The envelope does not arrive at the same word twice:** six arrivals at rest in
one run read 468, 511, 548, 508, 538, 485 (GATE's read 91, 220, 135, 90, 152,
153). For GATE the envelope LSB is a don't-care and it passes; for COMPRESSOR it
is the whole model. An intermediate fix DEMANDED equality with the rest state,
refused every capture and took GATE's verdict with it — measured and reverted
the same session, which is why the check reports the state pair instead of
vetoing on it. The witness stands at S82's **0.02509 dB**, recorded as a witness
under the hub's Q1 ruling and inside the 0.0950 dB design bound. Nothing is
outside a contract term.

**S83-6 🔴 THE AK5558 LANES ARE DARK AND IT IS NOT THE SLOT MAP.** The desk half
is conclusive: `git diff a4ee3d1f HEAD` on `shared/dsp4-logic/slot-map.csv` and
`tdm-lines.csv` returns NOTHING for any `A_I0`/`A_I1`/`A_I2` row — those rows
were added once at `8439b189` (2026-07-31) and never touched — so MIC 5 lands in
`_buf_C1_IN_16` on BOTH bitstreams, zero lanes of movement, and there is no live
lane for S58's patch to be missing. `net_sel` is `4'b1000` in both branches
(`dsp4_logic_top.v:312`), so `i_dspa[0..2]` take the converters. The bench half
assumed nothing: one tone, every lane, tone off then on, with FRAME_COUNT as the
must-move control and `_rx_slot_C1_IN_01` as the must-not-move control, both
satisfied on every pass; the route proved DIGITALLY first (AUX 1 bus −43.017
dBFS at oscillator −40.0). **With the rails UP and the 595 chain unmuted at gain
63 phantom off (VERIFIED 200/200), 32 of 32 `_buf_C1_IN_*` read EXACT DIGITAL
ZERO, tone on and tone off alike, while all four codec lanes carry their own
dithered noise floor in the same pass.** No EIN row is takeable: S54's
−127.2 dBu cannot be met or missed by a lane that produces no samples. The CPLD
cannot help — its `cdc_*` ones/toggles/frames witness counts `cdc_o` ONLY
(`dsp4_logic_top.v:185-230`) and there is no equivalent on `ad[0..2]`. Probe
list in the report §3.4; the cheapest decisive step is adding that counter.

**S83-7 🔴 THE TALKBACK LOOP IS NOT CARRYING THE TONE, SO T1/T3 STOP.** The AUX
1 bus reads −43.008 dBFS at oscillator −40.0, the rails were up, and the
talkback lane does not follow the oscillator: three drives 20 dB apart put the
lane at −105.773 / −105.609 / −105.676 dBFS, a spread of 0.16 dB. What DOES move
it is MGN2R — −106.7 dBFS at code 0 to −87.8 dBFS at code 11 — which is the
front end amplifying its own noise floor. S70 measured **+41.75 dB** of loop
gain at code 11 with the lane at −6.5 dBFS; today the same code is about
**81 dB** below that. Gate 1's 27 dB drop reads 25.558 dB FAIL and the T1 ladder
scatters by ±12 dB, which is what a noise floor does when the gain in front of
it changes. No number from this run is quoted as a talkback measurement.
Gates 2 and 4 fail the SAME way — the bus carries the tone digitally and nothing
analog comes back on any path — which is one observation, not two.

**S83-8 🟡 THE BENCH'S CPLD HISTORY BETWEEN S42 AND S81 IS NOT ON RECORD.**
`loadlogic.sh`'s `shipping` label was hardcoded to the pre-S34 `a1f6672af6c3`
from its creation at S37 until S82 changed it, so any session that handed the
bench back with `loadlogic.sh shipping` in that window silently reflashed a
bitstream that drives no converter clock — and that artifact predates the
design-ID stamp, so no readback could catch it. Meanwhile `s41_mhrx_pullup_off.
15f3ae07dae1`'s own manifest states in writing that IT, not `a1f6672af6c3`, is
what the bench lived on from 2026-09-12, with the converter clock pair driven
and measured at U3 pins 141/142. No dispatch block between S46 and S77 mentions
touching the CPLD at all. **So which bitstream S54 took its real preamp noise on
is not determinable from this repo**, and S54's data is unambiguously live
converter data. Two incompatible accounts are on record and only a dated flash
log can settle it.

**S83-9 🟢 A BOUND AND A WITNESS ARE DIFFERENT THINGS IN THE MANIFEST NOW.**
They were one dictionary, which is exactly how `comp_numeric_max_db` came to
hold S20's MEASUREMENT as though it were a limit. `gen_accept_fixtures.py` reads
any `*_witness_db` key into its own `numeric_witnesses_db` field, and
`limits.csv` carries `comp_numeric_witness_db` with its value, its date, the
configuration triple it was taken on and how reliably it was obtained.

## THE SIGNED CONFIGURATION SHIPS, ON THE FIXED BITSTREAM (2026-09-20, session 82)

Hub dispatch `tasks.md` 2026-09-20 10:19Z. PW adopted the S34 converter-clock
fix (S81-Q1) and signed the SIMD pairing configuration the same morning.
Report: `MW/D24/DSP/s82/signed.md`. Contract note:
`proposals/CONTRACT-PROPOSAL-S82.md`.

**S82-1 🟢 THE SHIPPING LOGIC IS `dsp4_logic.7a6a4529f29c` AND THE PART SAYS SO
— WHERE THE ARTIFACT IT REPLACES SAID NOTHING.** Flashed, FLASH OK on attempt
1, IDCODE `0x020a30dd` both sides. Twenty minutes before the flash, on
`a1f6672af6c3`, `loadlogic.sh --id` answered *"no reply: nothing in the
capture carried the 0xD594 marker"*; after it, `design_id: 32'h4529f29c
cfg_bits: 16'h0010 SHIPPING`. Two readings on one card through one capture
path, which is the negative control S81-Q2 could only argue for from build
dates. The artifact rebuilds byte-identically from HEAD (POF md5
`7dc0976d7b13d98b4a37795d1eeaf49e`; the SVF differs only in the `!Device #1:`
wall-clock comment line `build.sh`'s header names), Fmax 67.25 MHz, sim gate
PASS on five testbenches.

**S82-2 🟢 NO DESIGN ID, NO FLASH — AND THE RULE IS ON THE MANIFEST, NOT ON A
LIST OF NAMES.** `loadlogic.sh` extracts `design_id: 32'hXXXXXXXX` from the
manifest beside the artifact and refuses to stage anything without one. Proved
discriminating on three manifests: `7a6a4529f29c` → `4529f29c`;
`retired/a1f6672af6c3` → nothing; `s37_shipping_step0.c62c024714f2` → nothing
(its manifest says "NONE — AND THAT IS NOT FIXABLE AT THIS SIZE"). The step-0
image is the tree's one deliberate exception and goes on the part through
`tools/pi/logic_flash.sh`, so the exception is now a property of which tool is
used rather than of a convention. `a1f6672af6c3` is retired to
`bitstream/retired/` with its own README section; the name still resolves in
`loadlogic.sh`, to a refusal that says why.

**S82-3 🟢 `driveall` ALWAYS HAD THE CONVERTER CLOCK, FROM THE SOURCE.**
`ded71079` is an ancestor of HEAD and the two assignments it landed —
`assign conv_bck = bck8; assign conv_fs = fs8;` at
`rtl/dsp4_logic_top.v:446-447` — sit AFTER the single `ifdef DSP4_DRIVE_ALL`
block (lines 314-389) and are unconditional. `dsp4_logic_driveall.c49f4128a083`
was built 2026-09-20T01:08:20Z, nine days after the fix landed. So every driven
capacity row taken on it was taken WITH the converter clock, while every
converter observation was taken WITHOUT it — S81-Q2's two meanings of
"shipping", now stated from the RTL rather than inferred.

**S82-4 🟢 THE CODEC RETURN LANES ARE LIVE IN EVERY CONDITION, AND THE AK5558
LANES ARE EXACT ZERO IN EVERY CONDITION — SO THE SAFE IMAGE IS NOT THE ZERO.**
Signed pair, D24, ten peeks per lane. All four `_buf_C1_XIN_CODEC_0*` return
10 distinct words of 10, rails down and rails up. Every AK5558 lane read —
`_buf_C1_IN_01 / _02 / _05 / _09 / _17`, one on each of the three converters,
**and `_buf_C1_IN_16`, which is MIC 5's own** (J25 → U39/AD 1 → AIN 8 → slot 7
→ packed rx 15, resolved with `d24_inputs.py`; `C1_IN_05` is MIC 14, not
MIC 5) — returns `00000000` ten times out of ten in five conditions:
rails down with the 595 chain SAFE, rails up with it SAFE, and rails up with
the chain written to `0xFC` — gain 63, phantom off, **unmuted** — verified
200/200 on the part. A muted preamp still delivers converter noise; an exact
digital zero is no conversion. **The MIC 5 EIN row is therefore still owed and
still refused, and S81-Q3 is untouched by the converter-clock fix**, which is
what S81 §3.6 predicted: nothing in this tree has ever written an AK5558 a
register image. `_buf_C1_XIN_MEMS` remains stuck at `0xFFFFFFFF` (S79).

**S82-5 🔴 `dsp4_inscan.py` SCORED THE SIGNED PAIR THROUGH THE WRONG SYMBOL MAP
AND PRINTED A TIDY TABLE.** It reported `MOVING 0 / STATIC 47`, both controls
passed, on the same boot where a direct peek of the same lanes showed every
codec return moving. `load_syms()` searched `/home/app/dspboot` BEFORE the
working directory; the signed pair was staged at `/home/app/ship_s82` and
`~/dspboot` held the S78-restore pair's map. Three of the forty-seven lanes
read `0x3F800000`, which is `1.0f` and not a sample at all — the only visible
sign, and not one the summary mentions. This is the failure the tool's own
docstring warns about, committed by its own search order, ONE SESSION after
S81 rewrote it to stop being void. **Fixed**: the working directory first,
`~/dspboot` second, and the absolute path of the map it used is printed. Every
staged arm in this tree runs from its own directory, so the old order was
backwards for every case that matters.

**S82-6 🔴 `dsp4_node_verify.py` MASKED EIGHT BITS OF A SIX-BIT SIGNATURE, SO
SINCE S74 IT HAS REJECTED EVERY SHIPPING IMAGE AND GUESSED THE GATE ARM.**
`read_arm()` tested `(w & 0xFF000000) != 0xC2000000`. DIAG_BUILD_CFG2's bit 29
is `DSP4_TALK_INVERT` (S72) and bit 24 is `DSP4_TEST_NODES` (S49), both placed
outside the signature on purpose; `dsp4_buildcfg.py` has masked `0xDE000000`
for that reason since S72. `DSP4_TALK_INVERT` started shipping at S74, so from
that day the tool printed *"0x… is not a DIAG_BUILD_CFG2 word — assuming the
log-domain gate threshold"* on every shipping image.

**It was latent for exactly as long as it could be.** The fallback happened to
be right while `DSP4_GATE_LINTHR` and `DSP4_DYN_LUT` were both 0. PW signed
them to 1 on 2026-09-20, and the first famverify run on the signed pair scored
**GATE numeric FAILED** with the part holding `2,684,355` and the model
predicting `-222,930,816` — which is, to the digit, the S16-4 failure the
comment block above that code says it exists to prevent, reappearing through
the signature mask instead of through the missing read. With the mask
corrected the same image on the same boot reads `build arm: DIAG_BUILD_CFG2
0xE2018E7F — GATE_LINTHR=1 DYN_LUT=1, block 16` and all three of GATE's
converted parameters come out `ok`. **The mask is now IMPORTED from
`dsp4_buildcfg.py`** rather than repeated, because two copies of a signature is
how this happened, and the fallback literal names itself in the message when
it is used.

**S82-7 🟢 `shipping.config` NAMES EVERY SWITCH A CONFIG WORD CARRIES, AND
`check_shipping_config.sh` NOW ENFORCES THAT AS A RULE.** Fourteen switches
were reaching the shipping image through a `build.sh` default —
`DSP4_GAIN_FLOAT`, `DSP4_GAIN_SIMD`, `DSP4_GATHER_FIRST`,
`DSP4_BLOCK_DECIMATE`, `DSP4_BQ_SIMD_PIPE`, `DSP4_C2_XPAIR`, `DSP4_DLY_SPLIT`,
`DSP4_DYN_INLINE`, `DSP4_RTG_FABRIC`, `DSP4_FX_TYPE_DECLARED`,
`DSP4_SCOPE_BLK_TAP`, `DSP4_SIMD_GRAPH`, `DSP4_SIMD_STRIPS`,
`DSP4_DYN_TABLES`. **None of their values changed**: the triple moves by the
five signed bits and nothing else, which is the proof that this was a naming
change and not a configuration change.

This is one fault with five dates on it — S8-2/S9-1, S11-1, S76, S79 — and the
first time the fix generalises instead of naming the one switch that had just
been found. The existing completeness gates prove the FILE and the MIRRORS
agree, and they agree perfectly about a switch neither names, because both
fall through to the same default; what that cannot survive is the default
moving. The one exemption is `DSP4_BQ_GUARD`, which no configuration can set,
and the exemption list is checked in both directions. Proved not vacuous:
deleting `DSP4_RTG_FABRIC=1` produces `SHIPPING CONFIG DRIFT: … is carried by
a config word and is NOT NAMED in shipping.config`.

**S82-8 🟢 THE SIGNED TRIPLE IS `0xCF45FF10` / `0xE2018E6F` / `0xC47C0F26`, AND
ONLY THE SECOND WORD MOVES.** `0xE2018264 ^ 0xE2018E6F = 0x00000C0B` — bits 0
`DSP4_STRIP_FUSED`, 1 `DSP4_SIMD_DYN`, 3 `DSP4_SIMD_STRIPS`, 10
`DSP4_DYN_LUT`, 11 `DSP4_GATE_LINTHR`. Words 1 and 3 not moving is a check and
not a coincidence: none of the four signed switches lives in either. Read off
BOTH chips of the signed pair; the same tool given the OLD triple refuses the
same part in the same run and names all five bits. The signed pair is
`chip1.ldr e3e25a79c4619d1a44305258f99fac7d` / `chip2.ldr
41a6b913e5f77bac698e136abd9aac65`.

**S82-9 🔴 THE COMMITTED D24 ACCEPTANCE FIXTURES WERE STALE AGAINST
`defs.lock`, AND NOTHING CHECKED THEM.** All 38 fixtures and the manifest
carried `contract: defs-v2026.09.16.5` / `defs_commit 10d2f672…` /
`matrix_gen 39836144a9ba` while `defs.lock` has pinned `defs-v2026.09.19.3` /
`6fd91594…` / `54c7eafc8811`. Regeneration changes **provenance only** — no
fixture body, no limit, no measured number moves, and `dryrun_compare.py` still
reports `187 of 187 comparisons agree within tolerance` — so the staleness cost
nothing this time. It is recorded because the acceptance set is the artifact a
factory would run, it names the contract it was generated from, and for an
unknown number of days it named the wrong one with nothing in the tree to say
so. `check-contract-drift.sh` regenerates the matrices and the DSP artifacts;
it does not regenerate the acceptance fixtures.

**S82-10 🟢 THE ACCEPTANCE MANIFEST NOW CARRIES THE CONFIGURATION AND THE
BOUNDS.** `MW/D24/DSP/accept/manifest.json` gains a `dsp` block: the
`DIAG_BUILD_CFG` triple (computed by `cfg_words.py` from `build.sh` and
`shipping.config`, not typed), the four signed switches, and the three numeric
bounds read from `tools/accept/limits.csv`. A fixture set is generated from
the CONTRACT and scored against a FIRMWARE IMAGE, and until now the artifact
said nothing about which image. Both halves are read rather than written down,
and an unavailable half puts an error string in the manifest instead of a
stale guess.

**S82-11 🟡 `GATE_LINTHR`'s ACCEPTED BOUND IS EXCEEDED AT THE BOTTOM OF ITS
RANGE, AND THE CONTRACT TERM SHOULD SAY SO.** The full 801-point sweep finds
19 points over 0.0002 dB, **all** at thresholds at or below −77.1 dB, worst
+0.000320 dB at −79.9 dB, where the linear word is tens of Q4.28 LSBs and one
LSB of quantisation already exceeds the bar. Over any threshold at or above
−60 dB the worst shift is +0.000122 dB. Proposed as ≤ 0.0002 dB for
`GateThr ≥ −60 dB` and ≤ 0.00035 dB below it, and carried that way in
`limits.csv` and the contract note. A bound that is quietly exceeded at the
edge of its range is the shape this project calls a defect in the instrument.

**S82-12 🟡 `DSP4_DYN_LUT` PASSES ITS BOUND BY 0.005 dB AND THE HUB SHOULD KNOW
IT.** `dyn_lut_design.py --sweep`: worst over 81 parameter sets **0.0950 dB**
(comp `thr −60.0 ratio 100.0 knee 0.0` at −60.0 dBFS) against PW's 0.1 dB
ruling. It passes, with essentially no margin: a future change to the table's
K, its chunking or the documented parameter range has almost no room.

**S82-18 🟢 THE CONFORMANCE HARNESS PASSES ON THE SIGNED CONFIGURATION WITH
FOUR FEWER DECLARED-UNIT FAILURES THAN THE BASELINE.** `./conform.sh` walked
every address in both dispatch tables — chip 1 4984/4984, chip 2 2176/2176,
`healthy=True` at exit on both — for `ECHO 6420 / UNMAPPED 400 / CLEARED 121 /
HOST_MANAGED 60 / ERROR 24 / SKIPPED_METER 135`, **22 declared-unit checks
pass and 12 fail**, the wrong-unit negative control fired 4 of 4, `VERDICT:
PASS`. The standing baseline is *"18 declared-unit checks pass and the 16 that
fail are the named D41 known mismatches"*
(`goldens/conformance-20260830-s6.md`, repeated in
`dsp4-capacity-decision-20260902.md`). The twelve failures are the four
dynamics time-constant cells at three values each — `ChanGateAtt`,
`ChanGateRel`, `ChanCompAtt`, `ChanCompRel` — which is the D41 ms-versus-
samples class by name. **None is new and four are gone.**

**S82-19 🟡 AND THE INERT HALF OF THAT HARNESS SAMPLED NOTHING, INSIDE A
`VERDICT: PASS`.** In the same run:

```
driven window: _buf_C1_BUS_MAIN_L is silent; falling back to _buf_C1_FDR_01
positive control (GAIN):    0 of 32 bus words moved
positive control (CompThr): 0 of 32 bus words moved
inert: 0 classes sampled of 0 candidate addresses (bus window)
```

Its own two positive controls did not move and it sampled zero of zero
candidate addresses, and the run still reports PASS — the verdict is carried
entirely by the presence walk, the declared-unit checks and the two negative
controls that did fire. That is not wrong (nothing claims an inert result that
was not taken) but it is the S12-7 shape one level up: a phase that contributes
nothing is indistinguishable, in the verdict line, from a phase that passed.
**The inert phase should fail the run, or mark it INCOMPLETE, when its own
positive control does not move** — the same rule `dsp4_inscan.py` now applies
to `FRAME_COUNT` and `dsp4_cdc_witness.py` to its frame counter.

**S82-20 🟢 THE D24 FITS DRIVEN ON THE SIGNED CONFIGURATION, AND S80'S HEADLINE
IS REVERSED FOR THE PRODUCT PW RULED IS THE FOCUS.** `ARM=s82d24 PRODUCT=d24
./capacity.sh --driven`, no override on the command line, on `loadlogic.sh
driveall`. Mean of both boots, 135,000 blocks per row:

| row | chip 1 | chip 2 | missed | pre-S82 (S80) |
|---|--:|--:|---|---|
| A silent, default | 43.22 % | 77.41 % | 0 / 0 | 56.04 / 88.33 |
| B silent, loaded | 57.50 % | 84.27 % | 0 / 0 | 80.71 / 98.28 |
| **C DRIVEN, six FX live** | **57.54 %** | **84.34 %** | **0 / 0** | 123.57 / **127.50**, 21.5 % missed |

S80 measured this row 27.5 points over budget on chip 2, missing one block in
five, and concluded that *"on the fixed instrument, not one product in the
range fits driven"*. **43 points come off chip 2 and 66 off chip 1** on the
same instrument, the same bitstream generation and the same stimulus, and not
one block is missed in any of the twelve chip-rows.

**Three things make this a measurement rather than a claim.** The image is the
shipping pair rebuilt byte-identically inside the arm (`e3e25a79` /
`41a6b913`, the pair built at the top of the session from the same file).
Every row carries `cfg2 0xE2018E6F` read off the part DURING the measurement,
so the number and the configuration are one reading. And the regime is proven
on BOTH boots — `48 of 48 dynamics envelopes live on chip 1`, `28 of 28 on
chip 2`, twice — which is the check that separates a driven row from the
silence row wearing a driven label that voided every S28 row (S78-Q4).

**The signal is free**: driven minus silent-loaded is +0.03 points on chip 1
and +0.07 on chip 2. On the shipping default S19/S20 measured that column at
+42.5 and +29.3.

**The worst-block column is still not a margin.** Most rows latched a raw
worst block at 342–377 % of budget before the reset (the S21-6 tick artifact)
and one post-reset figure survived it at 357.32 %, so the honest statement is
the average plus zero missed blocks, not a worst-case headroom figure.

**S82-21 🟡 AT 32 CHANNELS THE D24 FIRMWARE FITS DRIVEN BY 0.64 POINTS, ON A
PARTIAL REGIME — WHICH IS NOT A HEADROOM CLAIM.**
`ARM=s82d24m32 PRODUCT=d24 DSP4_CHAN_MASK=0 ./capacity.sh --driven`, both
boots. The image is genuinely different (`a118cec8` / `cf8afa84`) and **says
so in its own word**: `build_cfg 0xCF45FB10`, bit 10 clear against the
shipping `0xCF45FF10`.

| row | chip 1 | chip 2 | missed | 24 ch |
|---|--:|--:|---|---|
| A silent, default | 54.76 % | 92.33 % | 0 / 0 | 43.22 / 77.41 |
| B silent, loaded | 68.96 % | 99.18 % | 0 / 0 | 57.50 / 84.27 |
| C driven | 69.21 % | **99.36 %** | **0 / 0** | 57.54 / 84.34 |

Eight more channels cost about 15 points of chip 2 and 11.7 of chip 1, and
not one block is missed in 270,000. **But the row is not a margin**, twice
over: the regime is PARTIAL on both boots (`56 of 64` envelopes live on
chip 1, `28 of 32` on chip 2, `REGIME NOT PROVEN … row C is taken`) because a
D24's input patch maps 24 channels and the strips above that have no lane for
`driveall` to drive — so the true fully-driven figure is at or above 99.36 %
and this arm cannot say by how much; and 0.64 points is about twice the
instrument's own boot-to-boot spread.

**The useful statement is the comparison**: the product's own 24 channels have
15.7 points of chip-2 margin on the signed configuration, and 32 channels have
none worth planning against. The signing is what makes 32 reachable at all —
the pre-S82 configuration was 27.5 points over at 24 — but headroom above the
product's channel count is not something this session demonstrated.

**S82-17 🟡 THE LATENCY BAR REFUSED, CORRECTLY, AND THE REFUSAL IS THE RESULT
WORTH RECORDING.** `latency.sh` on the signed pair with the SHIPPING bitstream
on the part returned `coherent fraction 0.0%` on all forty reps across two
boots and printed

```
NO VERDICT: the coherent fraction is 0.0% on every rep -- nothing in the
capture correlates with the stimulus, so the offset is the best of a flat
field and is NOT a latency. Check the capture path (the through-DSP arm needs
the _maincap bitstream AND a duplex PCM overlay) before re-running.
```

The offset it would have reported — 14779 samples, spread 0 over twenty reps —
is exactly the shape that reads like a confident measurement: perfectly
repeatable, zero spread, and meaningless. **The instrument says so itself**,
which is the behaviour S80-19 asked for and the opposite of what
`dsp4_inscan.py` did in S82-5. The through-DSP latency contract (82 samples at
block 16) is re-taken on `loadlogic.sh maincap`; the run above is recorded
because a session that saw `offset 14779, spread 0` and did not read the next
line would have moved the contract number.

**RE-RUN ON `maincap`, AND IT IS NOT THE BITSTREAM.** The contract row was
re-taken with `loadlogic.sh maincap` on the part (`design_id 32'heb00a4e8
cfg_bits 16'h0004 pi_maincap`, read back) and came out identically: `offset
14779, spread 0, coherent 0.0 %` on every rep, `NO VERDICT`. The duplex PCM
overlay the message also names IS present and correct — `dtoverlay=dsp4-pcm-
slave` in `/boot/firmware/config.txt`, playback `hw:dsp4pcm,1` and capture
`hw:dsp4pcm,0` both enumerated.

**The cause is the boot, and it is reproducible.** Both latency runs, four
boots in total, reported `chip 1 not ready after 8 attempts: BOOT_STAGE below
6` — and then took twenty reps anyway. A chip below BOOT_STAGE 6 is not
running the graph, so there is nothing in the path to correlate with the
stimulus, and 0.0 % coherence is the correct reading of an unbooted part. The
SAME pair (`e3e25a79` / `41a6b913`) reaches `BOOT_STAGE 7` under `s82.sh` and
under `capacity.sh` in this session, so the fault is in `latency.sh`'s own
arm — it stages to `/home/app/cap_s82lat` and boots from there — and not in
the image, the bitstream or the overlay.

**So the 82-sample contract row is OWED, not moved**, and the next session's
first step is `latency.sh`'s boot rather than the measurement.

**And the bar should not have taken the reps.** Proceeding past its own
readiness gate is what turned a boot failure into forty reps of a
confident-looking `spread 0` number; the refusal at the end is what saved it.
The gate should be fatal, the way `dsp4_inscan.py`'s FRAME_COUNT control now
is.

**S82-13 🔴 `wire_contract.py` CUT THE SPI DISPATCH TABLE IN HALF AT A SEMICOLON
INSIDE A COMMENT, AND THE WHOLE CONFORMANCE HARNESS EXITED 2.** `conform.sh`
failed before it reached the part with

```
src/chip1/dsp_params.asm: cannot parse dispatch line
'_meas_seq_C1_TEST_MEAS,    /* 0x136E: C1_TEST_MEAS window serial (no cell'
```

`entries()` found the end of a `.var name[N] = …;` initialiser with
`body.index(';')`. Line 6851 of the GENERATED `dsp_params.asm` reads
`/* 0x136E: C1_TEST_MEAS window serial (no cell; bench read-back) */` — the
semicolon is inside the comment, the initialiser was cut in the middle of it,
and the truncated fragment matched no dispatch form. The file is correct
assembler and the comment is the generator's; the parser was the thing that
was wrong. **Fixed**: the terminator is now the first `;` found outside a
`/* */`, and an initialiser that is never terminated outside a comment is an
error with its own message. Chip 1 parses 4,984 dispatch entries and chip 2
2,176; `0x136E` resolves to `_meas_seq_C1_TEST_MEAS` with its comment intact.

**S82-14 🟢 FADER_PAN's NUMERIC FAILURE IS NOT THE SIGNING, PROVED BY A CONTROL
ARM ON THE PART.** The same four families were re-run with
`DSP4_SIMD_DYN=0 DSP4_STRIP_FUSED=0 DSP4_DYN_LUT=0 DSP4_GATE_LINTHR=0` — a
different image, reading back `0xE201827C` (`GATE_LINTHR=0 DYN_LUT=0`) — and
the two pan legs mismatch by **exactly the same words**: part `183217856` /
`85217608` against model `183341408` / `85094040`. The part's right leg is
`20/63` to 1.1e-8 and the model used `0.317` verbatim, so the bar drives a cell
the wire quantises onto a 63-step grid and compares against an unquantised
model: −0.00586 dB on the left leg, +0.01260 dB on the right. Pre-existing,
independent of the pairing, and new since S20 (where this family was
`BIT_EXACT` and carried 118 cells against today's 122). Recorded with the
arithmetic that identifies it; not chased further.

The same control arm is the two-sided proof that S82-6's fix works: on the
signed image the tool reads `GATE_LINTHR=1` and compares the gate threshold in
the LINEAR domain (`2684355 / 2684355 ok`); on the control image it reads
`GATE_LINTHR=0` and compares it in the LOG domain (`-222930816 / -222930816
ok`). Same tool, same node, opposite arms, both `ok`.

**S82-15 🟡 NAMING A DERIVED SWITCH BREAKS ITS DERIVATION FOR OVERRIDE ARMS.**
`DSP4_SIMD_STRIPS` followed `DSP4_SIMD_DYN` through `build.sh`'s
`DSP4_SIMD_STRIPS_DEFAULT`. S82 names it in `shipping.config` — which is what
the dispatch required and what makes the shipping image self-describing — and
the file now wins over the derivation. The consequence showed up in this
session's own control arm: `DSP4_SIMD_DYN=0 ./famverify.sh` produced an image
with `SIMD_STRIPS` still 1 (`0xE201827C`, bit 3 set). It changed no conclusion
here, but **a control arm that means "the pairing off" must now set both
switches**, and any recipe in the tree that sets only `DSP4_SIMD_DYN=0` is
building something it does not name. Not reverted: the shipping image's
self-description is worth more than the shorthand, and the image's own config
word says which it is either way.

**S82-16 🔴 `_comp_envelope` WOULD NOT CORROBORATE AND THE COMPRESSOR VERDICT
WAS TAKEN ONCE IN FIVE RUNS.** Four of the five family runs this session ended
COMPRESSOR with `node state unreadable — no verdict for this node` — a
`BUILD=0` four-family arm, the full fixed-instrument run, the pre-S82 control
arm, and a `FAMILIES=COMPRESSOR CHIPS=1` arm built and staged for that one
node — while reading every one of that node's six converted parameters
successfully in the same pass. The dedicated arm also returned `contract 17 of
17` and `audio … moved 64/174099163 peak 0x0AF5C27E->0x009537A3 -> LIVE`, so
the node is running and compressing by about 21 dB while the numeric phase
declines to score it. `vpeek` returns None for a
corroborated ZERO unless the zero sentinel agrees, and a fully rested
compressor envelope is legitimately zero. So the one COMPRESSOR measurement
this session has (§3.3 of the report) has no A/B beside it, and the bar cannot
currently be relied on to produce that verdict on demand. This is the same
class as S82-5 and S82-6: an instrument that declines rather than lies, but
declines silently enough that three runs in a row can be read as "the bar was
run".

## THE CODEC ANSWERS, CDC_O IS CARRYING DATA, AND THE CONVERTERS ARE NOT DARK — THE BITSTREAM FLASHED ON THE BENCH IS (2026-09-20, session 81)

Hub dispatch `tasks.md` 2026-09-20 09:23Z, answering S80's six questions.
Report: `MW/D24/DSP/s81/witnesses.md`.

**S81-1 🔴 `dsp4_logic.a1f6672af6c3` — WHAT EVERY SESSION CALLS "SHIPPING" AND
"THE STATE THE BENCH LIVES IN" — PREDATES THE S34 CONVERTER-CLOCK FIX, AND
THAT IS WHY THE CONVERTERS ARE DARK.** Measured as an A/B on the part: same
DSP pair, same firmware, same symbol map, same `dsp4_scope.py` reads, half an
hour apart, only the LOGIC bitstream changed. On `a1f6672af6c3` all four
`_buf_C1_XIN_CODEC_0*` read exact digital zero. On a bitstream built from the
current tree (`7a6a4529f29c`) all four carry moving converter noise, and the
excursions grow with AN_EN high. Confirmed independently by the rewritten
`dsp4_inscan.py`: `MOVING 0 / STATIC 47` against `MOVING 4 / STATIC 43`, the
four moving lanes being exactly the codec returns. The mechanism is in git:
`a1f6672af6c3` was added at `a4ee3d1f` (2026-08-21), which
`git merge-base --is-ancestor` puts BEFORE `ded71079` (2026-09-11), the S34
fix — whose RTL comment reads *"THESE WERE INPUTS, AND THAT IS WHY NO
CONVERTER CAN WORK … as inputs the converters and all three option slots get
no bit clock and no frame sync at all"*, and whose commit message reads *"NOT
MERGED, NOT FLASHED. PW decides."* **Ten sessions have diagnosed a hardware
fault that is a pending decision.** Caveat stated rather than buried: the two
bitstreams also differ in slot-map generation, so the A/B has two variables;
S81-3 is what separates them, because a slot-map change cannot make a codec
start transmitting.

**S81-2 🟢 THE AK4619 ANSWERS ON SPI, AND THE READ ARM THAT ASKED IT IS
H1S1's.** `CodecPoll()` gains sentinels `0xFE` (read), `0xFB` (fetch the guard
byte) and `0xFD` (set the read command code) plus a full-duplex `SpiTxRx()`.
All 21 registers `StartAK4619()` writes read back the init image exactly
(`37 AC 10 00 BB BB 30 30 30 30 00 00 00 00 18 18 18 18 04 05 0A`); four
registers it does not write (15H, 16H, 1FH, 7FH) read `0x00`; and a
write-then-read control tracks (`05H := 0x35` reads `0x35`, `:= 0xBB` reads
`0xBB`). 00H = `0x37` is the codec reporting itself powered with RSTN set.
Verified in the DISASSEMBLY per the 2026-08-21 rule: `SpiTx` callers 4 → 4
(the write path byte-identical), `SpiTxRx` 0 → 1, `DspTx` still 0, no `bl` in
`TimeSplice`, only `CodecPoll` changed, only `SpiTxRx` and
`HAL_SPI_TransmitReceive` added. Flashed `OK: H1S1` first try, no MH1 SWD
reset needed; 3 of 3 MCUs verify.

**S81-3 🟢 A FRAME WITNESS ON `CDC_O` IN THE LOGIC, AND IT RIDES THE KNOCK
RATHER THAN A PROBE.** The TEST pins land on a DNP header, so the witness
reuses the one no-hands path off a MAX V that already exists — the design-ID
knock on the CM4 PCM link (S5-9) — as a SECOND word pair,
`{L = 0xCD0432B4, R = 0x32FBCD4B}`, answering with per-frame `cdc_o` ones,
toggles and a high-water mark, plus a free-running frame counter that is the
instrument's own liveness control. **A-B-A on the codec's own power register:**
codec up, ones 48 [9..86] / toggles 24; `00H := 0x00`, ones **0** / toggles
**0** with the frame counter still advancing; codec up again, ones 48 /
toggles 24. So the activity is the codec's, not a floating pin — and a codec
can only frame a TDM stream if BICK and LRCK are arriving, which is the half
of the question the CPLD cannot answer by looking at its own outputs.

**S81-4 🔴 THE FIRST BUILD OF THE READ ARM FREE-RAN ON THE PART, BECAUSE THE
MATRIX BUS IS MULTI-DROP AND H1S1 HEARS ITS OWN REPLIES.** It answered on
`Sys001Test002`, whose RXF is the arm's trigger, so each reply re-armed it:
00H answers `0x37`, the echo made it read register `0x37`, which answers
`0x00`, and it ping-ponged — unasked SPI bursts on the copper the CM4 boots
the SHARCs over, which is exactly the hazard the 2026-08-21 change removed
H1S1's periodic writes for. It terminated only by accident, when the echoed
guard poisoned the address cell into the write branch (which transmits
nothing); the spurious writes went to register `0x43`, not an AK4619 register,
and the image was re-inited and re-read afterwards. **The rule is structural:
nothing this firmware transmits may land on the trigger cell.** Every reply
now returns on the ADDRESS cell and the guard is fetched, not pushed.

**S81-5 🔴 S80-Q5's PROPOSED READ COMMAND `0xC1` IS WRONG, AND FOLLOWING IT
WOULD HAVE PRODUCED THE OPPOSITE ANSWER.** The datasheet pairing recorded in
S69's own source comment (9.12 Table 27 / 9.13) is that the command code's MSB
is the R/W flag, so the write code `0xC3` has read code `0x43` — same seven
low bits, MSB cleared. `0xC1` keeps the WRITE flag set. Settled on the part
rather than by argument, because the command byte was built as a firmware
VARIABLE: with `0xC1` the AK4619 hands back **the register number** (01H →
`0x01`, 05H → `0x05`), the master's own address byte clocked straight through.
A read of 00H under `0xC1` would have returned `0x00` and the session would
have reported "the codec does not answer on SPI".

**S81-6 🟢 S80-10 CONFIRMED ON THE PART: THE MIC PREAMPS WERE AT GAIN 63.**
The 595 chain's pass-1 MISO read `FC`×24 + `00` — twenty-four identical
`0xFC` = gain 63, phantom off, mute off, which is exactly `TestMicPres()`'s
only live image and not latched SPI traffic. Every noise figure taken on this
bench since S79's `--reset` was taken at full mic gain. SAFE image
(`0x01`×24 + `0x00`) written, `VERIFIED 200/200`, CS_M returned to `ip pu`.

**S81-7 🟢 S70-7's CHAIN RULE MEASURED A SECOND TIME.** At handback, after
this session's DSP boots, the chain read back `00 E0 FE 00 …` — byte for byte
S70's pattern, three `0xFE` bytes decoding as **unmuted, phantom ON, gain
63**. The S48-7 mechanism is still live and "assert the chain after the last
DSP boot, never before it" is load-bearing. With CS_M parked `ip pu` there is
no rising edge, so a later `matrix-app` restart shifts traffic through the
chain without latching it.

**S81-8 🔴 THE AK5558 LANES ARE STILL DARK WITH THE CLOCK PRESENT AND THE
RAILS UP, AND NOTHING IN THIS TREE EVER CONFIGURES THEM.** `_buf_C1_IN_01/02/
09/17` read exact digital zero on the post-S34 bitstream with AN_EN high, on
the same run where the codec lanes moved. The ADCs share conv_bck/conv_fs with
the codec, so the clock fix alone does not account for them. `StartAK4619()`
writes the AK4619 only; no AK5558 register image exists anywhere in this repo.
This is a different question from S81-1 and is not answered by it. It is also
why the gate-1 EIN check could not be taken: MIC 5 runs into an AK5558.

**S81-9 🔴 S69's H1S1 HUNKS NEVER REACHED THE CANONICAL DROPBOX COPY.** S69's
dispatch said the hub would apply them to `_mx/MW/D24/FW/H1S1/Core/Inc/
matrix.cs` and that "both copies must end identical"; today it was still the
2026-08-21 file, four weeks behind the firmware actually flashed. S81 synced
it with S69's and S81's changes together (md5 `f2fceaeb…` both sides, prior
copy kept beside it). Nothing checks these two against each other.

**S81-10 🟢 `dsp4_inscan.py` REWRITTEN ONTO THE BLOCK SYMBOLS, WITH BOTH
CONTROLS PROVEN ON THE PART.** It reads `_buf_C<chip>_IN_*` / `_XIN_*`,
refuses to run if they are absent instead of skipping silently, and gates
every verdict behind a MUST-MOVE control (`FRAME_COUNT` advancing — otherwise
the sample loop is not turning and every STATIC is meaningless) and a
MUST-NOT-MOVE control (`_rx_slot_C1_IN_01`, the symbol that voided the old
tool, through the same peek path). The two-sided control the dispatch asked
for came out of S81-1's A/B: same tool, same image, same symbols, STATIC on
one bitstream and MOVING on the other. Also fixed: `0xFFFFFFFF` is both the
link's "I don't know" and a stuck lane, and discarding it is why
`_buf_C1_XIN_MEMS` read UNREADABLE from a healthy link — it is now resolved by
the MAGIC brackets. Peek interval 13.7 ms, not a round number, because S80's
20 ms pass was exactly 60 blocks and aliased `CODEC_04` into a false STATIC.

**S81-11 🔴 S80-12's CLASS, AUDITED AND CLOSED — AND IT WAS BIGGER THAN ONE
TOOL. SEVEN BENCH DRIVERS TOOK NO BENCH LOCK AT ALL.** `bisect.sh`,
`callcal.sh`, `ctlgate.sh`, `dcapar.sh`, `mtrverify.sh`, `sigstrips.sh` and
`strips.sh` build, scp and ssh onto the card without sourcing `bench_lock.sh`,
so they got neither the exclusive card lock — the session-10 contention defect
the lock exists to prevent — nor the link-tool refresh, while their own
`_run.sh` called straight into `dsp4_config.py`/`dsp4_diag.py`/`dsp4_scope.py`.
All seven now acquire it. Four tools joined the deploy on card-side evidence:
`dsp4_cclk.py`, `dsp4_blk30.py` and `dsp4_inscan.py` were **absent** from
`/home/app/dspboot`, and `dsp4_logic_id.py` — the only tool that can say which
bitstream is on the part — was **stale** (`2b379c11…` 2026-09-09 against the
repo's `280f7ab4…`), a live instance of exactly S80-12. `sigstrips.sh` also
staged four tools into its arm directory but not `dsp4_dyn_witness.py`, the
witness its verdict is scored on.

**S81-12 🟡 TWO MORE OF THE SAME CLASS, REPORTED NOT FIXED.** `profile.sh`
scp's and invokes `profile_run.sh`, which has no history under that path in
this repo at all — an orphan copy dated 2026-08-23 sits on the card, so it has
been running an un-diffable hand-copy. And `chain_run.sh` would read a missing
`chain.py` as a clean run: its guard checks only `dsp4_checkchip.py`, and the
`python3: can't open file …` error matches none of its retry patterns, so the
loop falls through, echoes the OS error as the strip's report, and exits 0.
**Latent, not live** — the card happens to hold a matching copy in the
directory the script `cd`s to.

**S81-13 🟢 `product_fit.py` RE-ANCHORED ON S80's ROWS PER RULING Q1(a).**
Rows A and B re-anchored on the measured silent rows across all four products;
row C fitted from D16/D24/D32 only, with D12's C produced by extrapolation and
LABELLED as such rather than invented from its unproven driven reading; row D
untouched and still carrying its S27 anchor, because S80 took no D row. Every
construction and anchor row names its session and date. Sanity check passes:
the pre-fix deltas reproduce S80's stated figures (D24 C chip 2 **+43.13**,
D32 C chip 1 **+85.16**), and every anchor-row residual is now ≤ 1.06 points
against up to +85 before. The FX-engine correction term is retired rather than
carried — it required mixing a new S80 C row with the stale S27 D row from a
different session and bitstream. **The two rows marked *(ANCHOR — this is a
control)* now pass BY CONSTRUCTION**, and the tool says so itself: a control
that passes because the fit was built on the same data is weaker evidence than
one that passes independently.

**S81-14 🔴 NOT RUN: S79-Q3's D16/D12 INSTANCE-SKIP CONTROL ARM AND D12's
REGIME.** Both are bench capacity arms — S80 spent most of a session on eight
of them — and this session's bench time went to gates 1-4, of which gate 3
became S81-1 and the A/B that confirms it. They are unblocked and fully
specified (`ARM=… PRODUCT=… ./capacity.sh --driven` on `loadlogic.sh
driveall`), and the bench lock now deploys the tools those arms cite, which it
did not when S80 ran them.

## THE THIRD BUILD-CONFIG WORD IS FULL AND LANDED, SO THREE CONFIGURATIONS THAT READ BACK ONE WORD NOW READ BACK THREE — AND FOUR OF THE SIX THINGS A PROBE-FREE CONVERTER DIAGNOSIS WAS TOLD TO READ DO NOT EXIST TO BE READ (2026-09-20, session 80)

Hub dispatch `tasks.md` 2026-09-20 06:02Z, ruling S75-13. Report:
`MW/D24/DSP/s80/cfg3-rows-dark.md`.

**S80-1 🟢 `DIAG_BUILD_CFG3` CARRIES THE SWITCHES THE TWO FULL WORDS CANNOT,
AND THE PROOF IS ON FILES THAT ALREADY EXISTED.** S75's address (`0xE0EC`),
signature (`0xC4`) and bit 0 (`DSP4_EXTRAM`) stand — the hub's ruling, and a
landed signature is not renegotiable. Bits 23..1 were free and now carry the
instrument bit (23), `DSP4_RTG_FABRIC`/`GAIN_SIMD`/`DLY_SPLIT`/`C2_XPAIR`/
`DYN_INLINE`/`DYN_TABLES` (22..16), **the whole eight-class
`DSP4_SHARED_KERNELS` mask** (15..8), two free bits stated as free (7..6),
`DSP4_SPI_PARTIAL_FIX2`/`DSP4_RTA`/`DSP4_CUE` (5..3), the `MTX_GATE`
capability (2) and `DSP4_AUXIN_BYPASS` (1). The shipping triple is
**`0xCF45FF10` / `0xE2018264` / `0xC47C0F26`**. `DIAG_BUILD_CFG2` is NOT
re-laid out, so its value does not move for any image and every decoder of it
keeps working. The measurement that makes this a result rather than a design:
`shipping.config.s21`, `.s26` and `.s32` **all read `0xC2019E6F`** — three
different images, one word — and they now read `0xC47C0324`, `0xC47C0F24` and
`0xC47C0F26`. `.s21` against `.s26` is **S27-3 closed** (shared-kernel mask 3
against mask 15, open since S26); `.s26` against `.s32` is **S79's park-gate
hole closed**, one bit. Negative control on the artifact: a full
`DSP4_PATTERN=1` build — a switch no word carries a field for — puts
`0xC4FC0F26` in both boot streams and `0xC47C0F26` in neither.

**S80-2 🟡 `DIAG_BUILD_CFG2` HAS CARRIED `DSP4_TEST_NODES` SINCE S49 AND THE
REPO-SIDE COMPUTATION OF THAT WORD NEVER KNEW.** `src/diag.h` sets bit 24 from
`DIAG_CFG2_TEST_NODES` and `tools/pi/dsp4_buildcfg.py` has decoded it since
S49; `cfg_words.WORD2` did not list it and `check_shipping_config.sh`'s
`want2` did not either, so `cfg_words.words()` computed a CFG2 **`0x01000000`
short** for any `DSP4_TEST_NODES=1` arm. Nothing had failed, because the
switch is 0 in `shipping.config` and nobody had scored a self-test arm with
this tool — and that is the one arm a tool like this exists to score. Found by
pointing the S77 completeness gate at a third word. Fixed in both.

**S80-3 🟡 `build_defaults()` SILENTLY DROPPED EVERY SWITCH WHOSE `build.sh`
DEFAULT REFERENCES ANOTHER SWITCH.** `${KEY:-$OTHER}` and
`${KEY:-${OTHER:-N}}` matched no pattern it read, so `DSP4_NODE_LIMIT2` and
`DSP4_DYN_SELFTEST` were absent from its dict. Survivable while nothing asked
about them; fatal for an instrument bit that must know the shipping value of
every switch no word carries, because a switch whose default the function
cannot read is a switch the bit is **silently blind to** — S12-7's shape
inside the tool built to close it. Both resolve now, through the chain.

**S80-4 🟡 `build.sh` DEFINED FOUR SWITCHES FOR THE COMPILER AND NOT THE
ASSEMBLER.** `DSP4_DMA_AUTOBUF`, `DSP4_FCWM`, `DSP4_PATTERN`, `DSP4_RX0_L2` —
the only four of its ninety-six missing from `ASMFLAGS`. No assembly source
reads any of them, so nothing was wrong until the instrument bit needed to see
them: an undefined identifier evaluates to 0 in a preprocessor `#if`, so a
`DSP4_PATTERN=1` build would have stamped itself *"this is the product"*.

**S80-5 🟢 THE MIRROR THIS CHANGE ADDS IS PROVED, NOT TRUSTED.** The
instrument bit has to be computed at assembly time from literals, because the
cell that carries the word is assembled and not compiled — so `src/diag.h`
carries the list of fifty-six switches and their shipping values, which is a
default in two places and therefore S8-2 waiting to happen.
`check_shipping_config.sh` now derives the same list and the same values from
`build.sh` and `shipping.config` and fails in **both directions and on the
values**; derives `want3` from `cfg_words.WORD3` instead of listing it; runs
the completeness gate the other way round too (a field the bench decoder
reads that `cfg_words.py` does not declare is drift); and **cross-checks the
two independent computations of the triple**, which is the check that would
have caught S77's `0xE2010244` without a part on a bench.

**S80-6 🔴 NO HOST ON THIS BENCH CAN READ AN AK4619 REGISTER, AND THAT IS WHY
S79-Q1's FIRST QUESTION CANNOT BE ANSWERED WITHOUT AN H1S1 FIRMWARE CHANGE.**
H1S1's codec path is write-only in both halves: `CodecPoll()` only ever
assembles the AK4619's `0xC3` **write** command, with no read arm and no cell
to return a byte in, and `SpiTx()` never reads MISO at all. "Read a register
`StartAK4619` wrote and compare" is a firmware change (a read command plus one
matrix cell), not a bench technique.

**S80-7 🔴 THE LOGIC CPLD HAS NO HOST INTERFACE, SO THERE ARE NO CLOCK OR
FRAME COUNTERS TO READ AND NO PLACE TO PUT ONE.** `dsp4_logic_top.v`'s ports
are clocks, the eight DSPA input lines, the eight DSPB output lines, the
converter and NET lanes, the PCM link, one LED and four TEST pins — *"There is
NO reset input: MAX V registers power up cleared"*. A counter on `CDC_O` is an
HDL change plus a way out, and the only ways out are those four pins or a DSPA
lane.

**S80-8 🟡 NOTHING ON A D24 REPORTS A RAIL.** `S_TEST` returns three MCU
identity lines (`H1S1 DSP`, `H1S4 SW Left`, `H1S3 SW Right`) and MH1's idle
heartbeat, twice identically; and the only power-shaped cells among the D24
contract's 5,002 are the 24 `Chan[n]Phantom001` **writes**. There is no rail
telemetry to diff against S70's boot, so that item of S79-Q1 has no
instrument either.

**S80-9 🟢 THE 595 CHAIN IS READABLE AND IT IS RULED OUT: THERE IS NO
CONVERTER RESET OR POWER BIT IN IT.** `s55_chain.send()` shifts 25 bytes twice
and pass 2's MISO is the image that was in the chain, so it reads as well as
writes. The byte is `{gain[5:0] << 2 | phantom << 1 | mute}` and `!RST_C` is a
direct STM32 GPIO pulsed in `MainInit()`, not a chain bit. No 595 state can be
making the converters dark.

**S80-10 🔴 `codec4619.py --reset` LEAVES EVERY MIC PREAMP UNMUTED AT MAXIMUM
GAIN, AND THE DOCSTRING THAT SAID OTHERWISE PUT IT IN S79's HANDBACK RECORD.**
`MainInit()` ends with `TestMicPres()`, whose only live image is
`micGainFull` = `0xFC` x 24, which decodes as **gain 63, phantom off, mute
OFF**. The tool's docstring said `--reset` *"CLEARS THE 595 CHAIN"* and S79
recorded the chain left *"as MainInit leaves it ... benign (gain 0, phantom
off)"* on the strength of it. The SAFE image is `0x01` x 24 + `0x00` — gain 0,
phantom off, **MUTED** — and `0x00`, which "clears" implied, is unmuted at
gain 0. Phantom is off so nothing is at risk of damage, but the unit has been
at full mic gain since S79's handback and any EIN or noise figure taken on
this bench now is taken at full gain. Docstring corrected. **The state is
inferred from the H1S1 source and deliberately NOT verified on the part**,
because verifying it shifts the chain and shifting the chain drives CS_M,
which this dispatch's standing handback says to leave untouched.

**S80-13 🔴 ON THE FIXED INSTRUMENT NOT ONE PRODUCT IN THE RANGE FITS DRIVEN,
AND THE S28 ROWS THAT SAID OTHERWISE WERE SILENCE ROWS.** Driven/loaded, chip 2:
D16 **113.00 %** of budget (11.49 % of blocks missed), D24 **127.50 %**
(21.49 %), D32 151.57 % with chip 1 at **164.32 %** (39.03 %). Against S28 that
is **+39.98 / +42.86 / +50.75 points**, and it is what S78-Q4 predicted: every
S28 driven row was taken on the pre-fix `driveall` bitstream, where the MFD-2
lanes carried the stimulus one bit right-shifted and therefore at 2 LSB, so the
dynamics never left their cheap branch. S18 had already priced that difference
at ~20 points of chip 2 at D32, so a forty-point correction is the documented
size of the error rather than a surprise. **The new rows are corroborated by
S79 to a fifth of a point** — S79 read the D24 chip-2 driven row at
127.69 / 127.37 %, S80 reads 127.49 / 127.50 % on a different build of a
different tree. Every product fits **silent, loaded** (worst 98.28 % on a D24's
chip 2, zero missed) **except D32**, which is at 105.62 % on chip 2 at its own
boot configuration before anything is opened. Rows in
`MW/D32/DSP/fit-measured.json`; S28's kept, marked SILENCE, beside it.

**S80-14 🔴 THE D16/D12 SINGLE-CHIP QUESTION GETS A NO, AND NOT A MARGINAL
ONE.** PW 2026-09-11: *"D16 and D12 run on ONE 21564 each."* A D16's chip 2
**alone** is 113.00 % of budget driven and 87.73 % silent/loaded, on two chips;
there is no version of folding chip 1's 84.59 % onto the same part. Margin at 32
is **−64.3 points** on chip 1 of a two-chip D32. Nothing here contradicts the
2026-08-24 measured ceiling of ten channels a chip. S80-Q3 asks whether the
question moves to the FPGA engine or gets restated against a smaller defined
graph rather than the superset image every product boots.

**S80-15 🟢 THE PARK GATE IS WORTH 1.5–1.9 POINTS OF CHIP 2 ON A D16 OR D12,
WHICH IS LESS THAN A D24's AND THAT IS CORRECT.** `DSP4_AUXIN_BYPASS=1` against
`=0`, same tree, one build switch: D16 **−1.81 / −1.68 / −1.77** points on rows
A / B / C, D12 **−1.55 / −1.67 / −1.75**, with chip 1 — the noise witness, since
the two images differ on chip 2 only — spanning **−0.09…+0.14 on five of the six
comparisons and +1.09 on the sixth**, which is D12's driven row, where the `b0`
arm's two boots read chip 1 at 65.31 then 63.32. The lever gates **twelve** chip-2
`AUX_INPUT` nodes and twelve is twelve whatever the product is — the smaller
products have the same ones minus the eight snake returns already scope-gated
off below D32, which is why D32 gains most (4.9–5.7). **S79-Q3's "a D16 skips 18
instances and a D12 skips 20" is the OTHER lever** — the product-driven bypass,
`CFG_MTX_MASK` and `C2_MIX_AUX_nn` — which is not a build switch by design (D8)
and is therefore active in *both* arms of every pair here. Pricing it on D16/D12
needs a pre-S79 reference image as its control and is still owed.

**S80-16 🟡 D12's CHIP-2 DRIVEN REGIME REACHES 22 OF 24 ENVELOPES AND NO MORE**,
on both boots of both D12 arms, identically with and without the park gate. So
D12 has **no quotable driven number**, and its row is deliberately absent from
`fit-measured.json` (it falls back to the construction and says so). Two
envelopes that never engage under this stimulus is specific and reproducible and
is worth chasing on its own.

**S80-17 🟡 S28's "DEAR LAST SEGMENT" IS GONE AND THE RANGE'S COST IS NOW LINEAR
IN ITS SIZE.** Silent/default per-segment slopes over D12→D16→D24→D32: chip 1
**+1.97 / +1.96 / +2.00** points per strip, chip 2 **+4.20 / +4.43 / +4.32** per
aux bus — flat, against S28's chip-2 +2.32 / +2.39 / **+3.29**. S28 attributed
that step to D32's scope class, and the S29 re-take measures the scope class at
**−0.41 points of chip 1** on the driven row, i.e. almost nothing; its chip-2
figure (+0.71) is inside its own noise — `s29ns`'s two boots read 153.31 and
151.47, a 1.84-point spread within one arm — and is not quoted as a result. The mechanism is not isolated here and is not asserted; what is
measured is that the step is not there to explain.

**S80-18 🟢 THE DELIBERATE REPEAT REPRODUCES TO 0.65 POINTS ON CHIP 1 AND 0.14
ON CHIP 2, AND THE WORST-BLOCK COLUMN IS THE ONE NOT TO TRUST.**
`s80s28d32` and `s80s29ctl` are the same configuration run as two independent
arms — separate builds, staging and boots. Driven/loaded **average** % of budget
over the four boots: chip 1 163.99 / 164.64 / 164.11 / 164.15 (span 0.65), chip 2
151.56 / 151.58 / 151.70 / 151.65 (span **0.14**). Both are at or inside the
floor S79 (±0.27) and S28 (±0.30) used, so re-running an identical configuration
as a fresh arm reproduces it cleanly. **Eleven of this session's forty-two rows
latched a worst block at three to four hundred per cent of budget** — the S21-6
tick artifact, the timer ISR landing between the `tcount` and `_diag_ticks` reads
that close a pass — so the worst-block column is where the instrument is weak,
and no corrected figure is quoted as a measurement in the S80 report. Also
observed and not explained: D16's driven row misses 0 blocks on one boot and
15,510 (11.49 %) on the other at the same 113.00 % of budget — a row above
budget that misses nothing is internally inconsistent, so trust the avg % and
not the missed-block count there; and chip 1's load-config write reports 0–6
FAILED per boot on D24/D32 and 0 on D16/D12, non-deterministically.

**S80-19 🔴 `dsp4_inscan.py` ANSWERS "DO THE TDM LANES MOVE" WITH A NUMBER IT
CANNOT KNOW, ON EVERY BUILD THAT SHIPS.** It peeks the `_rx_slot_C1_IN_nn`
scalars, and under `DSP4_BLOCK_KERNELS` those are **dead symbols** — the node
source says so where they are declared: *"Under block kernels this kernel reads
the DMA buffer directly, so the slot var is unreferenced — kept as a scalar
purely so block_io.asm's tables still resolve."* So it reports STATIC zero
whether the lanes are alive or dead, and it read MOVING 0 / STATIC 32 in this
session on a stimulus the `_buf_` arrays show at full amplitude. **The standing
bench recipe (item 18) recommends it for exactly the question it cannot
answer**, and S79 quoted it as part of the case that the converters are dark —
that part of S79-2's case is void, though its conclusion stands on other
grounds. Wants a rewrite onto the block symbols or removal from the recipe.

**S80-20 🟢 THE FAULT BEHIND S79-Q1 IS UPSTREAM OF THE CPLD, BISECTED WITHOUT A
PROBE.** Under `driveall` the CPLD assigns `i_dspa[5:0] = {6{pcm_drive}}`, so
the codec return lane carries the CM4's playback where the shipping bitstream
has a bare `assign i_dspa[4] = cdc_o`. All four codec slots read MOVING between
`0x08000000` and `0xF8000000` — **±0.5 in Q4.28, i.e. −6.02 dBFS, exactly the
documented stimulus amplitude** (`0x40000000 >> 3`, the input kernel's shift),
so not merely alive but bit-correct. The SHARC's I4 pin, its SPORT, its RX DMA,
the slot mapping and the graph's input buffers are therefore all good, and the
probe list narrows to the `cdc_o` net, the J41/J42 flat-flex, the codec and its
clock. Separately, the AN_EN null **reproduces on the S80 image** (four codec
buffers, 40 reads each, exact zero with GPIO 26 `lo` and again `hi`), which
rules the build out as a factor and says the state is stable, not intermittent.

**S80-12 🟡 `dsp4_buildcfg.py` WAS NOT ONE OF THE TOOLS THE BENCH LOCK
DEPLOYS, WHICH IS D74's FAULT A THIRD TIME.** `bench_lock.sh`'s own comment
explains the shape: D74 fixed the link tools and not one bar script deployed
either file, so a fix could be in the repo, green on the bench by hand, and
absent from every bar that matters; S77 found the same for
`input_patch.json`. `dsp4_buildcfg.py` is the third, and it is the **only
thing on the bench that decodes what the image on the part was built with** —
`--expect-shipping` is what scores a part against `shipping.config`. It
becomes acute the moment `DIAG_BUILD_CFG3` has fields: a pre-S80 copy reading
`0xC47C0F26` **passes its own signature check**, decodes bit 0 alone, ignores
the instrument bit, the park gate, the matrix gate and the whole shared-kernel
mask, and prints *"== the shipping configuration"* having read almost none of
it. A stale decoder that says PASS is worse than one that raises. It travels
with the lock now.

**S80-11 🟡 THE MEMS-AGAINST-CODEC IDLE-LEVEL ARGUMENT CANNOT BE SHARPENED,
AND THE OBVIOUS SHARPENING IS UNAVAILABLE.** S79's inference — two different
stuck levels, so the SPORT is sampling real pins — is sound but cannot be
pushed to "the codec is driving": the lanes are different nets on different
boards (`tdm-lines.csv`: `A_I4`/`CDC_O` against `A_I7`/`MEMS`). The same-wire
version, the codec's four populated TDM slots against the four unpopulated
ones, is not available either: chip 1 receives that line as **stride 4, not
8** (`src/chip1/block_io.asm`, `_c1_rx_off` 512..515), so the unpopulated
slots are not in the RX buffer.

## THE DELAY POOL IS CODED FOR HYPERRAM AND RUNS WITHOUT IT: BOTH BACKENDS IN THE TREE, ZERO ADDED LATENCY, THE SHIPPING PAIR BYTE-IDENTICAL, AND TWO HARDWARE QUESTIONS THAT DECIDE WHETHER IT CAN EVER BE ARMED (2026-09-19, session 75 — desk only, no unit touched)

PW ruling 2026-09-19 evening: *"dsp ram is required, but needs to work without
it until dsp board modified -- code it in place."* Report:
`MW/D24/DSP/s75/extram-pool.md`. Contract proposal:
`proposals/CONTRACT-PROPOSAL-S75.md`.

**S75-1 🔴 OCTAL xSPI0 TAKES THE PARAMETER LINK *AND* THE BOOT PORT, AND D8'S
STATED RESOLUTION DOES NOT WORK — A QUESTION FOR THE HUB.** Datasheet Table 10:
`PA_00/01/04/05` are SPI2 at mux function 0 and xSPI0 at function 1;
`PA_06..PA_09` are **SPI0** at function 0 and xSPI0 at function 2. HyperBus
needs all eight data lanes, so xSPI0 consumes `PA_00..PA_09` (leads 14–27) plus
the dedicated `xSPI_RWDS` (lead 9) — which matches the mod sheet's "Port A
leads 14–27, RWDS lead 9, SEL1 = CS#" exactly, now cross-checked against the
120-lead assignment table. **Both SPI2 and SPI0 die.** Today the Pi's parameter
link *and* the slave-boot port are SPI2 (`dma_config.c`: PA_00 MISO, PA_01
MOSI, PA_04 CLK, PA_05 SEL1; `dsp4_busmon.py` agrees at the connector). D8 says
"the Pi RUNTIME param link moves to SPI0/SPI1" — but **SPI0 *is* xSPI0's
D4..D7**. The only SPI that survives an octal xSPI0 on this part is **SPI1
(`PA_10..PA_15`, function 1)**, and `PA_12` is currently the diagnostic LED.
QUESTION: does the board mod also move the Pi parameter link to SPI1 (giving up
or moving the LED), and does boot still happen on SPI2 before the firmware
re-muxes Port A? Without an answer the mod as drawn takes the control link away
the moment the RAM is enabled. Not decidable in this tree.

**S75-2 🔴 BOTH NAMED PARTS READ AS THE 1.8 V VARIANTS AND THE PROCESSOR HAS NO
1.8 V I/O — A QUESTION FOR THE HUB.** Datasheet Table 13: `VDD_EXT` is
3.13–3.47 V, nominal 3.30, with no lower option anywhere on the
ADSP-21560/61/64/68 — so the RAM must be a 3.0 V HyperRAM, exactly as D8
concluded in August. The dispatch names `S27KS0642GABHI020` and
`IS66WVH8M8DBLL-100B1LI`; on the vendors' own family naming `S27KS` is the
1.8 V Infineon part (`S27KL` is the 3.0 V one) and `IS66WVH` is ISSI's 1.8 V
part (`IS67WVH` the 3.0 V one). The processor half of this is datasheet-proven;
the part-family half is from naming convention, because vendor datasheets could
not be fetched from this machine. Either way the two statements cannot both be
right. QUESTION: confirm the orderable part numbers, or confirm a level
translator is in the mod. The design clock is unaffected — the 3.0 V grades are
the 100 MHz ones.

**S75-3 THE DATASHEET STATES THE xSPI CLOCK CEILING; D8'S "exact 21564 OSPI
clock ceiling" OPEN ITEM CAN CLOSE.** Table 14, "Clock Operating Conditions":
`fxSPICLKPROG` max **166.66 MHz with DQS**, 125 MHz without; footnote 5 —
with the offline PHY training methodology, 125 MHz with DQS and 80 MHz without.
HyperBus strobes reads with RWDS, which is the DQS case. The RAM, not the DSP,
is the binding limit at 100 MHz DDR octal = 200 MB/s raw.

**S75-4 THE ADSP-2156x DATASHEET IS PRESENT AND WAS RECORDED AS MISSING.**
`_mx/_temp/adsp-2156x-docs/adsp-21560-21561-21564-21568.pdf`, Rev. A, February
2026, 81 pages. It carries the clock table, both port multiplexing tables, the
120-lead assignment, the supply conditions and the I/O memory map — most of
what the HRM's missing core chapter could not answer. Every datasheet citation
in the S75 report comes from it.

**S75-5 🔴 CHIP 1'S CODE POOL HAS 946 BYTES FREE IN THE `DSP4_EXTRAM=1` ARM.**
The pool costs chip 1 **+7,960 bytes** of program memory: 253,238 → 261,198 of
262,144, 96.6 % → 99.6 %. It links, but nothing else will fit behind it —
`DSP4_CUE`, `DSP4_RTA` and `DSP4_TEST_NODES` are all still 0 and all want
chip-1 code. **Code reclamation is a blocking prerequisite for ever setting
`DSP4_EXTRAM=1` in `shipping.config`.** Cheap candidates: the dead float-era
`lib/delay.asm` bodies (gated out of block-kernel builds but still linked) and
the per-sample DLY body. This is not a defect in the pool; it is the existing
wall, reached.

**S75-6 THE BACKEND DECISION HAD TO MOVE AHEAD OF THE L2 CLAMP.** Found and
fixed inside this session. The DLY block kernel clamps the requested offset
into the *active L2 storage* (960 samples on a channel with no pool slot)
before anything else. The first cut of the EXTRAM arm decided head-versus-tail
*after* that clamp — against a number that can never exceed the head — so the
tail would never have been reached and a host asking for 200 ms would silently
have got 20, on an image that built, linked, ran and reported EXTRAM in force.
It now decides on the offset the host actually wrote and jumps the L2 clamp,
bounding against the full 12,000-sample spec instead. The simulated-part
harness reproduces the fault if the fix is reverted.

**S75-7 THE STAGING ARMS CHANNEL REGISTERS, NOT DESCRIPTOR LISTS, BECAUSE THIS
PART CANNOT DO DESCRIPTOR LISTS.** `dma_config.c` records `ERRC = 3` on every
descriptor-list arm ever tried on this silicon, including a self-referencing
descriptor built word by word in the probe, and the SPORT rings run in
autobuffer flow because of it. The obvious implementation of a per-block
staging queue — a pre-built descriptor chain with two patched fields — is
therefore unavailable. Recorded so the next person to look at the arming cost
does not "improve" it straight back into the known-broken path.

**S75-8 CHIP 2'S DELAY LINES ARE PER-SAMPLE NODES AND CANNOT BE STAGED UNTIL
THEY ARE NOT.** `gen_delay`'s non-pooled branch emits no block kernel, and the
aux/sub/main/monitor delays and the six FX echo lines all take it. Staging is a
per-block operation by construction, so `DSP4_POOL_LINES` is 32 on chip 1 and
**0** on chip 2. Chip 2's lines do not need the RAM for capacity — they already
carry the full 250 ms in L2 — they need it so their L2 can go to the reverb:
21 lines out of L2 is 984 KB, which pays for the stereo Freeverb halves
(+295 KB, deleted 2026-09-08) with ~1 MB still spare. Follow-on, with its own
byte-identical gate.

**S75-9 `DIAG_BUILD_CFG3` EXISTS AT `0xE0EC`, SIGNATURE `0xC4`, AND IS ITSELF
GATED.** `diag.h`'s own note (S72, reaffirmed S74) says the next flag of that
class needs a third word rather than a seventh narrowing of CFG2's six-bit
signature; `DSP4_EXTRAM` is that flag. CFG3 is behind `#if DSP4_EXTRAM` **only**
because a `.var` in `diag.asm` is a word of DM and a word of DM would have cost
the byte-identical proof below. It should become unconditional at the next
authorised shipping-image change. Until then `0xE0EC` reading 0 means "this
image has no CFG3, therefore no external-RAM pool" — less informative than it
will be, not ambiguous. Five runtime words join it: `DIAG_EXTRAM_STAT`
`0xE0ED`, `ID0/ID1` `0xE0EE/EF`, `XFERS` `0xE0F2`, `STALLS` `0xE0F3`.

**S75-10 THE 2D `YMOD` CONVENTION IS THE ONE PIECE NOTHING ON THIS BENCH CAN
CHECK.** The read-ahead fetch uses `YMOD = ROW_BYTES − (BLOCK−1)×4`, on the
reading that `YMOD` is applied after the last element of a row which has
already taken `XMOD`. An off-by-one fetches a window `BLOCK−1` words adrift —
audible as a delay right to within a third of a millisecond and wrong. It is
written at the call site with its reasoning so it is the first thing the bench
looks at, not the last.

**S75-13 TWO DIFFERENT `DIAG_BUILD_CFG3` DESIGNS NOW EXIST IN THIS REPO AND
ONLY ONE CAN SURVIVE — FOR THE HUB.** `tools/dsp/cfg_words.py` has carried an
unapplied design for a third build-config word since S28 gate 3: signature
`0xC3`, with every one of bits 23..0 allocated to a strip cut, the full
shared-kernel mask and six other switches. It was never implemented and
nothing in the firmware produces it. S75 has now implemented a word of that
name at `0xE0EC` with signature `0xC4` and one bit. **Neither layout has a
free bit for the other**, so they cannot be merged as they stand. They are at
least distinguishable — a decoder reading the wrong one rejects the signature
instead of decoding nonsense, which is exactly the property these words carry
signatures for — and that is the only thing that makes this survivable rather
than dangerous. Both files now say so at the point of definition. QUESTION:
which design lands? What must not happen is either going in on top of the
other without a decision: an image answering `0xE0EC` with S28's `0xC3` word
while a host built against S75's reads bit 0 would report "the external RAM
pool is compiled in" when what it read was `DSP4_DYN_TABLES`.

**S75-14 `check_shipping_config.sh` CHECKS THE NEW FLAG FROM THE START.** S74's
finding was that this script had never checked `DSP4_TALK_INVERT` — a flag in
`DIAG_BUILD_CFG2` that was absent from the script's `want2`, so
`shipping.config` could silently disagree with the bench mirror. `DSP4_EXTRAM`
is in `want3` and in `dsp4_buildcfg.SHIPPING3` on the day it was added, and the
script's printed line states plainly that with `DSP4_EXTRAM=0` the part reads
an unmapped `0x00000000` at `0xE0EC` and **not** `0xC4000000` — so a bench
operator is not told to expect a word the image does not carry.

**S75-11 THE PROOFS.** (a) Built at the shipping configuration the pair is
**byte for byte S74c's**: `chip1.ldr 10a413005e0647f5c66476f6a0b4ab60`
(452,388 B), `chip2.ldr e88a7a4302950d088a6c023c949c916e` (307,980 B) —
re-verified after `mem_pool.asm`/`extram.asm` moved from `src/lib/` to `src/`,
and again after `shipping.config` gained the key.
`./check-sharc-codegen-drift.sh` passes (734 generated, 0 differ).
(b) `DSP4_EXTRAM=1` assembles and links clean on both chips:
`52865949b546aa1757c26b6bb73f22ba` (461,052 B) /
`1198f18ec1759b0ff09ae7346a569f75` (309,132 B), neither deployed.
(c) Against a simulated HyperRAM that honours block timing
(`tools/dsp/extram_model.py`), the EXTRAM backend is **bit-exact**:
`tools/dsp/extram_bitexact.py` 9/9, **420,404 samples compared**, 0 LSB on
both the head range (where it must equal the L2 backend) and the tail range
(where it must equal an infinite-precision reference). Two arms exist only to
stop it passing vacuously — "the L2 backend must NOT match the reference"
(111,377 mismatches, i.e. the clamp is real) and a corrupted-RAM-word negative
control. Worst-block bus occupancy at 100 MHz with all 32 lines at 250 ms:
**0.2233**, harness limit 0.35.
(d) **Added audio latency: ZERO samples**, because the L2 head window covers
every offset short enough to matter and the tail is prefetched two blocks
ahead. L2 cost of the staging: +12,288 B on chip 1, which is the computed
figure to the byte.

**S75-12 WHAT THE RAM BUYS, READ OFF THE TREE.** Four things the L2 budget
cut: (1) 250 ms on all 32 channels became 20 ms on all 32 plus eight 250 ms
slots (−1,062 KB; only eight channels can exceed 20 ms at once); (2) the
reverb went mono, `_fx_comb_buf_R`/`_fx_allpass_buf_R` deleted 2026-09-08,
295 KB; (3) the FX echo is clamped to 250 ms where `Fx001DelayTime001`'s law
says up to 1,000 ms; (4) one main output delay where `dsp-def.md` budgets four.
**S75's arm restores (1)'s user-visible limit** — any of the 32 channels can
ask for up to 250 ms simultaneously, the eight-slot tier becoming redundant
rather than deleted (recovering its 375 KB is a separate authorised change).
(2), (3) and (4) all live on chip 2 and wait on S75-8.

## defs-v2026.09.19.3 CONSUMED: THE D24 RTA GATE LANDS CLEAN, ZERO EXISTING ADDRESSES MOVED (2026-09-19, session 74c — desk only, no unit touched)

Third pass at S74's gate 2. The hub landed S74b's proposal byte-for-byte as
`defs-v2026.09.19.3` (D24's `dsp-unmapped.csv` gains the two `Rta001On001`/
`Rta001Src001` no-graph-node rows, mirroring D32's). Consumed here in full.

**S74c-1. `defs.lock` advanced to `defs-v2026.09.19.3`
(`6fd91594315912e856b2e092d9b259f0d02da016`).** `./sync-defs.sh --update-lock`
expands all four products clean under the DictReader parse gate S74b added:
D12 2,336 / D16 3,318 / D24 5,002 / D32 7,014 rows, every `MxAdd` numeric.
D12/D16/D32 reproduce their prior matrix generation ids exactly
(`de54028f6fe2`/`7938e0d7ffc7`/`e473dd8c42d5` — untouched by the RTA change);
D24's generation moves to `54c7eafc8811` (the two new rows insert mid-file,
per S74b-2, and the `Test[1-1]SweepOn[1-1]` description quoting fix from
`.19.2` lands in D12/D16/D32's description text — content only, not
addresses).

**S74c-2. `gen_dsp.py --check-proposal`: zero errors on D32 and D24.** The
graph reproduces the landed `dsp.csv`/`dsp-unmapped.csv` exactly for both
products.

**S74c-3. The two RTA rows are unmapped by design — no DSP address
assigned, as expected.** `gen_dsp.py --force`: D32 unchanged at 5,780/5,780
mapped cells addressed (7,014 cells defined, matches HEAD exactly); D24
moves to 3,989/3,989 mapped cells addressed out of 5,002 defined (was
3,989/5,000 — the two new cells add to the *defined* count only, both land
in `dsp-unmapped.csv` as `no-graph-node`, neither in `dsp.csv`). Checked
directly, not assumed: a cell-by-cell diff of `MW/D24/MX/_matrix.csv`
against `git show HEAD:` over every DSP address column (`DspSpi`, `DspPage`,
`DspAdd`, `DspAddHex`, `RampProfile`) finds 0 diffs for any pre-existing
cell — the only two added rows are `Rta001On001`/`Rta001Src001`, both with
every address column blank. Same check on D32: 7,014/7,014 cells match
HEAD, 0 address-column diffs.

**S74c-4. All eight generated address artefacts byte-identical to HEAD.**
`ghost_cells.h` (both the DSP tree and `FW/H1S1/Core/{Inc,Src}` copies),
`mx_dsp_map.h`, `dsp_address_map.md`, and both chips'
`SHARC/src/chip{1,2}/dsp_params.asm` — `git diff --stat` empty on all seven
files (the eighth, `dsp.csv`/`dsp-unmapped.csv` itself, is the defs-side
proposal already confirmed identical to the landed rows in S74b). Only
`_matrix.csv` (four products, expected — the expansion) and
`MW/D24/DSP/input_patch.json` (one line, the `"contract"` version string)
changed in the tree.

**S74c-5. `./check-contract-drift.sh` passes clean, exit 0.** SHARC codegen
drift: 0 differ, 0 emitted-but-absent (732 files, tree == generator output).
Matrix contract: D12/D16/D24/D32 `MxAdd` contiguous, compatibility check
passed against the 376-family D32 allowlist. The 82-row Table/MxDatS
breakpoint mismatch report is pre-existing (reported for the hub, not fixed
here, unrelated to RTA — same rows as every prior session's run).

**S74c-6. Shipping pair rebuilt, byte-identical to S74's own recorded
hashes.** `MW/D32/DSP/SHARC/build.sh clean && ./build.sh` (talkback invert
still on, per S74): `chip1.ldr` `10a413005e0647f5c66476f6a0b4ab60`
(452,388 B), `chip2.ldr` `e88a7a4302950d088a6c023c949c916e` (307,980 B) —
matches S74-8 exactly, byte for byte, confirming the DSP address map and the
compiled image are unmoved by the RTA defs bump. Not deployed; the unit was
not touched.

**What is committed:** `defs` (submodule pointer → `.19.3`), `defs.lock`,
`MW/{D12,D16,D24,D32}/MX/_matrix.csv`, `MW/D24/DSP/input_patch.json`,
`tasks.md` (S74/S74b blocks closed), this entry. No hand edits to any
generated file; no DSP address moved for any pre-existing cell.

## TALKBACK POLARITY SIGNED IN CODE (D24 SHIPPING ON), AND THE RTA DEFS BUMP BLOCKED BY AN UPSTREAM EXPANDER DEFECT (2026-09-19, session 74 — desk only, no unit touched)

Report: `MW/D24/DSP/s74/talkback-invert-and-rta-block.md`. Two PW rulings
dispatched (2026-09-19 evening). Gate 1 (talkback) passed in full. Gate 2
(RTA defs bump) is BLOCKED — not a design question, a data-corruption defect
found in `defs/tools/expand_matrix.py`; `main`'s defs pin is unchanged,
still `defs-v2026.09.16.5`.

**S74-1. `DSP4_TALK_INVERT` is ON for the D24 shipping build.**
`shipping.config` (this tree's one copy, `DSP4_CHAN_MASK=1` — the D24's)
now carries `DSP4_TALK_INVERT=1`; `DIAG_BUILD_CFG2` moves **0xC2010244 →
0xE2010244** (bit 29, S72's design), confirmed to the bit by `cfg_words.py
--check`.

**S74-2. `check_shipping_config.sh` had a real, silent gap: it never
checked `DSP4_TALK_INVERT` at all**, since S72 added the flag to
`DIAG_BUILD_CFG2` but not to this script's `want2` dict, and the WORD1 loop
that checks every `shipping.config` key against the word-1 `SHIPPING` dict
skips any word-2-only key. Closed: added to `want2` (build.sh default, then
`shipping.config` override, same as every other word-2 switch) and to the
printed word-2 formula. Runs clean, printing `DIAG_BUILD_CFG2 0xE2010244`.

**S74-3. `tools/pi/dsp4_buildcfg.py`'s `SHIPPING2` mirror updated**
(`DSP4_TALK_INVERT` 0 → 1) so a bench `--expect-shipping` read scores
against the new default instead of flagging the correct image as wrong.

**S74-4/5/6. `diag.h`, `build.sh` and `dsp_codegen.py`'s stale "OFF UNTIL PW
RULES" language updated to the ruling** (diag.h's note appended, not
rewritten — the S72 bit-29-not-bit-25 narrative is unchanged and still
correct). `dsp_block.h` regenerated per the hard rule (never hand-edit a
generated file); `./check-sharc-codegen-drift.sh` found exactly the expected
one-file, comment-only drift beforehand and passes clean (732/732) after.

**S74-7. The T5 phase correction, computed from the S70 capture data, not
measured on the unit.** S70-6's T5 scan: phase extrapolated to DC =
**+181.56°**, residual attributed to the fit itself (max 0.19° over 21
points). A sign flip is an exact 180° shift at every frequency:
`181.56° − 180° = 1.56°` — the SAME 1.56° S70-6 already called the fit's own
error, i.e. the corrected sign lands the talkback at the fit's noise floor,
≈ 0°, exactly the design prediction. Arithmetic only; the unit was not
touched.

**S74-8. New shipping pair built here, NOT deployed, and it reproduces
S72's own recorded hashes exactly**: chip1 `10a413005e0647f5c66476f6a0b4ab60`
(452,388 B), chip2 `e88a7a4302950d088a6c023c949c916e` (307,980 B) — S72's
"`DSP4_TALK_INVERT=1`" row, byte for byte, because nothing about the node
code changed, only which arm `shipping.config` now names by default.
Against a control build (`DSP4_TALK_INVERT=0` override — the previous
shipping arm, `7d1ab146...`/`3a9c950d...`, also reproduced exactly): **chip 1
differs at 2 bytes** (the config word's top byte, and the Q4.28 sign S71/S72
already located), **chip 2 differs at exactly 1 byte — the config word, and
nothing else.**

**S74-9 🔴 `defs/tools/expand_matrix.py` parses its input with a bare
`line.split(',')` (no CSV quoting), and `common/cells/mx_master.csv` has
needed quoting since `defs-v2026.09.16.6` (S60): `Test[1-1]SweepOn[1-1]`'s
description is properly CSV-quoted in the source and contains a comma.** The
naive split corrupts field alignment from that row to EOF in every
product's expansion — `csv.DictReader` (what `gen_dsp.py` and every gate in
this repo actually use) parses only 6,931 of 7,014 D32 rows and 4,874 of
~5,000 D24 rows; `wc -l`/`grep`/`sha256sum` (what `sync-defs.sh` uses) see
nothing wrong, because the physical bytes are intact. Reproduced directly
from `defs/tools/expand_matrix.py` outside any of this repo's own tooling.
Present at every tag since `.16.6`, **including the target
`defs-v2026.09.19.1`**, unrelated to the RTA change, and uncaught until now
only because no dsp session advanced the defs pin past `.16.5` in between.

**Isolated, not assumed**: a clean worktree at `defs-v2026.09.16.5` (no
expansion re-run) passes `gen_dsp.py --check-proposal` with zero errors for
both products; the new D24 expansion's cell list, read as plain text
(immune to the quoting bug), is identical to the committed `HEAD` matrix
plus exactly the two expected appended rows, `Rta001On001` /
`Rta001Src001` — so gate 2's "0 existing addresses moved, 2 new unmapped
rows" would have been exactly true had the expander not been broken.

**Reverted, not landed.** `gen_dsp.py`'s own fatal check refused to proceed
on the corrupted comparison, so nothing was backfilled or installed from
it — but leaving even the submodule pointer + `defs.lock` bumped would break
`check-contract-drift.sh` for every session after this one, for a reason
unrelated to RTA. `git -C defs checkout defs-v2026.09.16.5`, expansion
stages removed, `defs.lock` and `MW/{D12,D16}/MX/_matrix.csv` restored
(D12/D16 install directly and were already corrupted the same way in the
working tree — caught before commit). Confirmed clean at HEAD after.

**🔴 S74-10, for the hub.** `defs/tools/expand_matrix.py` needs a real CSV
reader (`csv.reader`/`csv.writer`) or equivalent quote-awareness — options
not decided here: fix the expander in `invirco/defs`, or as a stopgap strip
the comma from the `Test[1-1]SweepOn[1-1]` description (content, not a
tooling fix — the next comma in a free-text field reintroduces this).
Blocks the D24 RTA landing and anything else advancing the defs pin past
`.16.5` until fixed.

## MEASCHAN 55 FOR THE NEW CODEC LANE, AND THE MINI-JACK BENCH NOTE CORRECTED (2026-09-19, session 73 — desk only, no unit touched)

Hub ruling on S72-8: the lane S72 declared (`C1_XIN_CODEC_02` = `CODEC_RET_2` = SPORT 4
slot 1, the aux-in right leg) had no `TEST_MEAS_LANE_CODES` entry, so slot 1 could not be
watched on the part. Fixed here.

**S73-1. `TEST_MEAS_LANE_CODES` gets MeasChan 55 = `C1_XIN_CODEC_02`.** Same mechanism
as S69's 51/52/53/54: codes only, no new cell, no new address, every emitted line inside
`#if DSP4_BLOCK_KERNELS && DSP4_TEST_NODES`. The regenerate touches exactly two files —
`tools/dsp/dsp_codegen.py` (the table entry) and `MW/D32/DSP/SHARC/src/chip1/
process_chain.asm` (one `.extern`, and one five-line hook block after each of the three
existing `C1_XIN_CODEC_02` call sites, each guarded by the same `#if`). No other file
changed.

**S73-2. Zero addresses moved, proved against `HEAD`.** All eight address artefacts are
byte-identical to `git show HEAD:` — `dsp_address_map.md`, `ghost_cells.h`, all four
`MW/*/MX/_matrix.csv`, both `dsp_params.asm`. `./check-contract-drift.sh` regenerated the
tree a second time and left it clean (only the two files above modified). Cell names
unchanged; `input_patch.json` untouched.

**S73-3. Shipping pair reproduces S72's recorded hash exactly.** Built here (not
deployed): chip1 `7d1ab146447a1f9d7c010ce9fa104e56` (452,388 B), chip2
`3a9c950d3551b6c5d7ff58925a47ec81` (307,980 B) — the identical pair S72's G5 recorded,
byte for byte, which is the strongest form of "shipping unchanged" available without the
unit: the shipping build reads nothing this session added, because the new lines are
behind `DSP4_TEST_NODES` and shipping.config holds that at 0.

**S73-4. Test pair, new hashes, NOT deployed.** With `DSP4_TEST_NODES=1`: chip1
`4ea95be16bf6944817ec57cec408504f` (459,424 B), chip2 `251ce3b2eb758aecae22b7550facf789`
(309,528 B) — chip 2 is the SAME hash S67/S69 recorded for a `DSP4_TEST_NODES=1` build,
confirming chip 2 carries none of this (or any prior) `TEST_MEAS` instrumentation. Chip 1
was also built from the pre-change tree for a direct control: `5d30fe99e42e985376bbb91
f22a5998f` (459,408 B) — the two chip-1 test images differ by exactly **+16 bytes**, one
`_test_meas_tap` call site's worth (r0 literal, r1 address, call), consistent with the
process_chain.asm diff in S73-1.

**S73-5. The CONTRACT-PROPOSAL note updated to reflect both S69 and S73**, which S69
never filed a proposal update for (`proposals/CONTRACT-PROPOSAL-S67.md` still said
"range 33 → 51" after S69 added lane codes 51–54). Title and table now read 33 → 56,
`## 3. Numbering` lists all five codec-return codes (51–55) by physical origin, and `##
2. Why` records the S69/S73 rationale alongside S67's. This is a documentation catch-up,
not a new landing — the firmware behavior it describes has been live in TEST_NODES
builds since S69/S73, unchanged by this edit.

**S73-6. The S71 §6d bench note corrected.** It told the next unit session to expect
"ring moves NOTHING" on the grounds that slot 1 had no lane — true when S71 wrote it,
false since S72 declared the lane and now false twice over since S73 gave it a tap. The
note (`MW/D24/DSP/s71/codec-lanes.md` §6d) is rewritten to watch MeasChan 51/52/53/55,
expect tip → 51 and ring → 55, nothing on 52 or 53, and states what each of five possible
deviations (tip→55, ring→51, either→52, either→53, neither moves) would mean. Copied
verbatim into `tasks.md` as a 🔴 bench item below.

## THE AUX-IN RIGHT LEG GETS ITS LANE, AND THE TALKBACK POLARITY GETS A BIT IN THE WORD THE PART READS BACK (2026-09-19, session 72 — desk only, no unit touched)

Report: `MW/D24/DSP/s72/aux-in-right-leg.md`. Pair built here, **not deployed**: chip1
`7d1ab146447a1f9d7c010ce9fa104e56` (452,388 B), chip2
`3a9c950d3551b6c5d7ff58925a47ec81` (307,980 B) — chip 2 byte-identical to S71's and to
the shipping chip 2 on record since S67, the whole change being chip 1's (+380 B).

**S72-1. The mini-jack's ring is received, and `XFER_CODEC_AUX_R` reads it.** The hub
ruled S71-3 option 1. One `superset_c1` row in `tools/dsp/gen_dsp_csv.py` declares
`C1_XIN_CODEC_02` = `CODEC_RET_2`, SPORT 4 slot 1, "Codec ADC 2 (Aux In R / mini-jack
ring)", and `XFER_CODEC_AUX_R` moves off the placeholder `C1_XIN_CODEC_03` onto it. The
aux input is stereo, which is what the netlist always said the hardware is.
`C1_XIN_CODEC_03` stays declared with its "(ADC2 L / not connected)" label and an empty
`outputs` column, so the lane map is complete and the not-connected converter input
reaches no audio path. `cs_mask` went 0x000D → 0x000F on its own: `lane_layout()`
derives it from the declared nodes, read off the regenerated `lane_config.c`, and no
SPORT register is set by hand anywhere in the change.

**S72-2. Zero addresses moved, proved against `HEAD` rather than asserted.** All eight
address artefacts are byte-identical to `git show HEAD:` — `dsp_address_map.md` (5,827
rows), `ghost_cells.h`, all four `MW/*/MX/_matrix.csv`, both `dsp_params.asm`. SPI
allocation still ends at chip 1 page 1 addr 4983 and chip 2 page 1 addr 2175; an
`INPUT_TDM` lane allocates nothing (`spi_page=-1`). Cell names unchanged.
`./check-contract-drift.sh` passed. Of the 22 files touched by the regenerate, twelve
are one-line diffs — the `r3 = N` packed-RX index of every node after the insertion
point — and `process_chain.asm`'s 660 changed lines are eighteen new lines plus
`DSP4_NODE_LIMIT` guards renumbered by one; `HEAD`'s copy was first confirmed
self-consistent with its own generator, so none of that churn is pre-existing drift.
`MW/D24/DSP/input_patch.json` grows 46 → 47 entries with a single `46` appended: the
permuted XLR entries are indices 0..31 and the new lane lands at 33, inside a stretch
that was already identity. No XLR moved.

**S72-3. The cost is one more copy kernel, not one load — and the codegen does not
count cycles, so this was counted off the emitted instructions.** The dispatch expected
"0 or one load". An `INPUT_TDM` lane is a full block kernel: ~20 setup instructions and
a 16-iteration loop of four, on the order of **85 chip-1 core cycles per block** at
block 16, one call per block. Memory is **+49 words of chip-1 DM** (RX region 736 → 752
for ping and pong, plus the 16-word node buffer and its slot word). Not a capacity
question against a chip-1 budget in the tens of thousands of cycles, but not zero, and
it should not go into the record as zero. The codegen's own report moves in exactly
three places: 441 → 442 chip-1 nodes, 731 → 732 files, scope tap 334 → 335 nodes.

**S72-4. `DSP4_TALK_INVERT` is now readable off the part: `DIAG_BUILD_CFG2` bit 29 —
and the bit position is the finding.** S71-4's gap is closed the way `diag.h` closed the
same gap for `DSP4_TEST_NODES` (S49): the flag takes a bit of the signature. **It has to
be a ZERO bit, and that is not a detail.** Narrowing the signature again at its bottom
(bits 31..26, flag at 25) would make the SHIPPING word `0xC0…`, which every existing
decoder rejects, and the INVERTED-TALKBACK word `0xC2…`, which every existing decoder
**accepts and reports as a shipping image** — the dangerous arm silent, which is the
exact failure the word exists to prevent. S49 avoided that only because the signature's
low bit is a 1. So bit 29 instead: signature `0b11 0001` in bits 31..30 and 28..25, six
bits, not contiguous. Measured off the two linked images at `_diag_build_cfg2`, not
computed: shipping reads `0xC2010244` — **the same value `HEAD`'s `cfg_words.py`
predicts**, so no existing record of a config word is invalidated — and the inverted arm
reads `0xE2010244`, which a decoder masking `0xFE000000` or `0xFF000000` rejects
outright. `DIAG_BUILD_CFG` is unmoved at `0xCF45FF10`. Landed in `src/diag.h`,
`tools/pi/dsp4_buildcfg.py` (`SIGMASK2 = 0xDE000000`), `tools/dsp/cfg_words.py` and the
`build.sh` note that used to say "known gap". Default still 0; PW's ruling is untouched.
**Written into `diag.h` for the next session: the signature is down to six bits and
23..0 are full, so the next flag of this class is the third word (`DIAG_BUILD_CFG3`,
designed in `dsp4-s28-20260911.md` §3), not a seventh narrowing.**

**S72-5. Three bytes separate the two polarity arms, and chip 2 is now one of them.**
`cmp -l`: chip 1 differs in **two** bytes — `0x4D`→`0xCD`, the sign of the Q4.28 scale
constant (S71-2's single byte, at a shifted offset), and `0xC2`→`0xE2`, the config word
— and chip 2 in **one**, the same config word. So the polarity flip still costs zero
cycles and zero words, and the new diag bit costs zero cycles and zero words too. But
**chip 2 now differs between the arms where it did not in S71**: the build-config word
is per-image and both chips carry it. That is correct — an image says what it was built
with — and the SHIPPING chip 2 does not move.

**S72-6. Proof without the unit: the gather table, not the XFER kernel.** Under
`DSP4_BLOCK_KERNELS` the XFER node's kernel is an `rts` and `_gather_chip1` walks a
pointer table, so S71's "disassemble the node" method does not reach this edge. Read off
the linked image instead: `_c1_ic_tx_ptrs` = `0x9030d`, entry 26 is `XFER_CODEC_AUX_R`,
and `elfdump -nxs sec_dmda` shows word `0x90327` = `0x95af9` = **`_buf_C1_XIN_CODEC_02`**
(entry 25 = `0x95ae5` = `_buf_C1_XIN_CODEC_01`, aux L). `_buf_C1_XIN_CODEC_03`'s address
`0x95b0d` appears **zero** times in that table. S71's fix was re-checked in the same
image and stands: `C1_TALK_01` loads `0x95b21` = `_buf_C1_XIN_CODEC_04` (slot 3, the
talkback XLR S70 measured), `C1_TALK_02` loads `_buf_C1_XIN_MEMS`, and the scale
constant two instructions earlier is `0x4d800000` — positive, i.e. the polarity-OFF
image. `TEST_MEAS_LANE_CODES` is a dict keyed by node id, so **MeasChan 51/52/53/54 did
not move**; the S70 capture set stays readable.

**S72-7. `shared/dsp4-logic/slot-map.csv` landed, and it behaved exactly as S71-5
measured.** Rows `A_I4,0..3` and `MIX_1,9..10` now carry the measured map, with the part
number corrected — the rows said **AK4916**; the board carries an **AK4619** — and
`CODEC_RET_2` marked received. Re-running `gen_slot_map.py` moves `source_hash`
`2c53de21…` → `c4a3ca82…` and the diff against the committed `dsp4_slot_map.vh` is
**that one comment line and nothing else**: the HDL is identical, no bitstream needed
rebuilding and none was. `dsp.csv` regenerates **byte-identically** from the new
`sport_map.json`, so the notes are confirmed not to be build inputs.

**S72-8. 🔴 The new lane cannot be measured on the part, and the S71 §6d bench note is
now wrong.** `C1_XIN_CODEC_02` has no `TEST_MEAS_LANE_CODES` entry (55 is free), so
nothing can watch slot 1 directly. Allocating one is a wire-contract allocation — S71
recorded those four codes as exactly that — and no gate of this dispatch covers it, so
it was not done: **hub's call**, and cheap when wanted (codes only, no cell, no address,
all inside `#if DSP4_TEST_NODES`). Meanwhile S71 §6d's owed measurement expects "ring
moves NOTHING, because slot 1 has no lane", which is no longer true. Replacement bench
note in the S72 report §6.

**S72-9. 🔴 The CPLD slot-map stamp move needs recording.** The shipping bitstream
manifest `dsp4_logic.ed70d3214c29.manifest` records `slot_map: sha256:2c53de21…`, which
no longer matches the committed slot map. The manifest was **deliberately not touched**:
it records what that bitstream was actually built from, and rewriting it would falsify
provenance to tidy a stamp. The bitstream is still correct — the HDL never changed.
Whether the move goes in the contract release note or waits for the next CPLD build to
re-stamp is the hub's call.

## THE CODEC-RETURN LANES NAMED FROM THE MEASURED MAP: THE TALKBACK XLR IS SLOT 3, THE GRAPH HAD IT ON SLOT 0, AND THE MINI-JACK'S RIGHT LEG HAS NO LANE AT ALL (2026-09-19, session 71 — desk only, no unit touched)

Report: `MW/D24/DSP/s71/codec-lanes.md`. Pair built here, **not deployed**: chip1
`abd2bea9fb0da81722861c52e3b06af8` (452,008 B), chip2
`3a9c950d3551b6c5d7ff58925a47ec81` (307,980 B) — chip 2 byte-identical to the shipping
image on record since S67, the whole change being chip 1's.

**The map, and which row is a measurement.** The AK4619's TDM256 slot order is fixed by
the part (datasheet Table 2 mode 10, Figure 19: ADC1 L, ADC1 R, ADC2 L, ADC2 R) and the
init image does not re-point anything (`0BH = 0x00`: all four channels differential on
their own pins). With the netlist (`mx26 docs/d24-analog-paths.csv`) that gives:
slot 0 = ADC1 Lch = IN1P = mini-jack **tip**, aux in L (NETLIST); slot 1 = ADC1 Rch =
IN2P = mini-jack **ring**, aux in R (NETLIST, **not received**); slot 2 = ADC2 Lch =
IN3, **both pins are one-pin nets — not connected on rev C** (NETLIST); slot 3 = ADC2
Rch = IN4N/IN4P = **talkback XLR J1** (**MEASURED**, S70-1: +41.75 dB loop gain constant
to 0.003 dB over 40 dB of drive while slots 0 and 2 did not move).

**S71-1. All three codec-return lane labels were wrong, and the error put the talkback
mic into the main mix.** `C1_XIN_CODEC_01` was labelled "Codec ADC 1 (TB XLR)" and is
the mini-jack tip; `C1_XIN_CODEC_04` was labelled "Codec ADC 4 (Aux In R)", is the
talkback XLR, and was wired to `XFER_CODEC_AUX_R` — so the talkback reached
`C2_CODEC_AUX_IN` and MAIN, while `C1_TALK_01` read a connector that is normally empty.
The labels came from the codec's ADC CHANNEL numbers read as TDM slot numbers.
Rewired in `tools/dsp/gen_dsp_csv.py` as a three-way rotation: `C1_TALK_01` ←
`C1_XIN_CODEC_04`, `XFER_CODEC_AUX_L` ← `C1_XIN_CODEC_01`, `XFER_CODEC_AUX_R` ←
`C1_XIN_CODEC_03`. `C1_TALK_02` stays on `C1_XIN_MEMS`. **Cell names unchanged** —
`Talk[1-4]Gain[1-1]` and the rest of the contract did not move.

**Proved on the linked image, not the source.** `elfdump -ns sec_swco_ovf chip1.dxe` at
`_C1_TALK_01_process`: `0018b2ac  1000 0009 5b05  r0=dm (_buf_C1_XIN_CODEC_04);` — and
`chip1.sym.json` gives `_buf_C1_XIN_CODEC_04 = 0x95b05` (it used to load `0x95add` =
`_buf_C1_XIN_CODEC_01`). That lane is `TEST_MEAS` **MeasChan 53**, the code every row of
the S70 capture set was taken on. The MeasChan codes 51..54 themselves did NOT move —
they are the wire contract that data was captured against; only their comments changed.

**S71-2. `DSP4_TALK_INVERT`: the polarity branch, in, OFF, and free.** The talkback is
inverted by wiring — J1 pin 2 (hot) on `IN4N`, pin 3 on `IN4P`; netlist, and S70-6 T5
measured +181.56° extrapolated to DC — and the AK4619 has no polarity bit. The flag
picks the other sign of the Q4.28 scale constant the node already multiplies its ramped
gain by: `r2 = 0x4D800000` becomes `r2 = 0xCD800000`. **`cmp -l` between the two chip-1
images reports exactly ONE differing byte** (offset 290336, `0x4D` → `0xCD`), same
452,008 bytes: zero cycles, zero words. Scoped by a node param `invert_opt` that
`gen_dsp_csv.py` puts on `C1_TALK_01` alone, so the MEMS instance emits no `#if` and
cannot move when PW rules between the sign here and swapping `C4`/`C11` at IN4 on rev D.
Wired through `build.sh` and named 0 in `shipping.config` — without that it is a flag
that silently does nothing, which is the S11-1 trap and did happen once here.

**S71-3. 🔴 The aux-in RIGHT leg has no lane, and this session did not invent one.** The
mini-jack ring is slot 1; slot 1 is not received. `XFER_CODEC_AUX_R` is therefore parked
on slot 2, which is IN3, which is not connected — the converter's own floor and nothing
else. A placeholder, chosen because it stops the talkback reaching MAIN without deciding
what aux R should be. **Slot 1 is not a SPORT setting**: `lane_layout()` in
`dsp_codegen.py` ORs each lane's `cs_mask` from the slots of the nodes declared on it
(`cs |= 1 << slot`), so `0x000D` is simply the three rows in `superset_c1`. Adding a
`C1_XIN_CODEC_02` row is one line and would make the mask `0x000F`. Question in the S71
dispatch block for the hub.

**S71-4. `DSP4_TALK_INVERT` cannot be read back off the part, and `diag.h`'s own rule
says it should be.** "A switch that changes cost or audio and cannot be read back is a
gap the next session pays for" — and this one changes audio. No bit exists:
`DIAG_BUILD_CFG` is 31..24 signature / 23..8 allocated / 7..0 `DSP4_BLOCK_SIZE`;
`DIAG_BUILD_CFG2` has 23..0 allocated (S18 spent the last two) and its signature already
narrowed from eight bits to seven so S49 could have bit 24. A bit means narrowing that
signature again — breaking every seven-bit decoder — or a third word. Hub's call; named
as a gap in `build.sh` beside the flag rather than taken unilaterally.

**S71-5. `shared/dsp4-logic/slot-map.csv` rows `A_I4,0..3` carry the same wrong names
and were deliberately NOT edited, for a measured reason.** `gen_slot_map.py` hashes the
two source CSVs into the generated Verilog header, so a COMMENT-ONLY edit moves
`source_hash` from `sha256:2c53de21…` to `sha256:d778a1ac…`. Tested in a scratch copy:
the diff against the committed `dsp4_slot_map.vh` is that one line and nothing else. The
HDL is identical and the bitstream would be, but the stamp reads as a CPLD source
change. Exact replacement text is in the report §6c for the hub to land with whatever
re-stamp it wants. The same rows also name the part **AK4916**; the board has an
**AK4619**.

**Contract: nothing moved, proved rather than asserted.** After
`./regenerate-dsp-contract.sh`, `git status` lists twelve files and not one is an
address artefact. `MW/D32/DSP/dsp_address_map.md` byte-identical (5,827 rows); all four
`MW/*/MX/_matrix.csv` byte-identical; `ghost_cells.h` and both `dsp_params.asm`
byte-identical. `dsp.csv`: 700 nodes before and after, chip 1 441 / chip 2 259, `c1_alloc`
still ending at page 1 addr 4983 and chip 2 at page 1 addr 2175 — **0 addresses moved**,
the only changed columns on the six changed rows being `label`, `inputs`, `outputs` and
`C1_TALK_01`'s added `invert_opt`. `./check-contract-drift.sh`: "SHARC codegen drift
check passed (tree == generator output)".

**Owed at the bench.** The mini-jack's tip/ring assignment is netlist and has never been
seen move. Cable in, drive tip and ring separately, watch MeasChan 51 and 52: expect tip
to move 51 and ring to move nothing. Mind the level — `04H` comes up `0xBB`, MGN1L/R
both **+27 dB**, and a line-level source into that will clip. Full note in the report §6d.

## THE 733-FIELD Table AUDIT WAS ALREADY FIXED BY S53 BEFORE THIS DISPATCH WAS WRITTEN; RE-VERIFIED CLEAN AT defs-v2026.09.16.5, THE SHIPPING IMAGE PROVEN UNMOVED (2026-09-18, session 68 — desk only, no unit touched)

**S68-1. Gates 1 and 4 were closed by S53 (`69c98fb3`, 09:39 09-16), forty-four minutes after the audit this dispatch quotes (09:13 09-16) — the dispatch was written from a stale read of `tasks.md`.** `git log` shows S53's message verbatim: it deleted the `table=` argument from all 86 `add_cell()` call sites and `backfill_matrix()`'s Table-writing branch (`gen_dsp.py:1742` now reads "Table is master-declared and arrives already on the row via the matrix expansion... the generator does not carry a second copy of it (S53)"), and added `check-table-mxdats.py`, wired non-fatal into `check-contract-drift.sh`. Read fresh this session: `grep -n "table="` in `gen_dsp.py` matches nothing but `add_cell`'s own dead default parameter; no call site passes one. No dsp-side line changed in this session — the work here is re-verification at the current pin, not a fix.

**S68-2. Gates 2/3 (regenerate, prove the revert): a full regen at the current pin (defs-v2026.09.16.5, three tags past S53's .2) leaves `git status` CLEAN.** `./sync-defs.sh` then `./check-contract-drift.sh` (which runs `dsp_codegen.py --force`, `validate-matrix-contract.py`, `gen_dsp.py --force`, `check-matrix-addresses.py`) touched zero committed files — the D24/D32 `_matrix.csv` already on disk are byte-identical to what the fixed generator produces from the pinned master today. Diffing the current tree against `e5182547` (S47, the `--force` landing the audit blames) by cell name: **D24 702 Table fields changed, D32 918, zero DSP-address columns (`DspSpi`/`DspPage`/`DspAdd`/`DspAddHex`) moved on any of them** — D24's 702 is exactly the audit's family B+C+D count. **Family A no longer exists as a blank hole**: the 31 cells the audit named (`Fx*Level`/`Damp`, `Talk*Gain`, `Main*/MainSub*/MainCtr* CompMake/CompPar/Crossover*`) are non-blank in both products' current matrices — defs filled them at `.2` (S53: "31 previously-blank family-A Table strings filled, provisional") and the fill has held through `.5`; a name-pattern scan against the current matrix found 0 blank cells in either product matching those families. The Table-blank cells that remain (2,567 of 5,000 D24 rows, 3,763 of 7,014 D32) are all `*Mtr*` read-only meter cells, which never carry a Table — not a mismatch.

**S68-3. Gate 4 (drift gate): `check-table-mxdats.py` ran clean against the current pin — 190 comparable master rows, 82 violators, same counts S53 recorded at `.2`.** Every violator has the identical shape: the master's Table breakpoint form tops out at code 127 (a 7-bit wire byte) while `MxDatS` documents a different top code (33, 65, 255, 21, 61, 3…) for the same cell — e.g. `Chan[1-64]CompMake[1-1]`: `MxDatS=33` (expect top 32), `Table='0=0/127=20/[Lin]'` (top 127). The script already reports every violator by name and exits 0 without blocking; this is a master (defs) question, restated for the hub, not a dsp edit — none applied here.

**S68-4. Gate 5 (shipping images unmoved): proven both structurally and empirically.** `tools/dsp/dsp_codegen.py` — the generator whose output `build.sh` compiles into the SHARC DXE/LDR — has zero references to `_matrix.csv` (`grep` returns nothing); the Table column has no code path to the shipping image at all. Confirmed on the part-facing artifact too: `MW/D32/DSP/SHARC/build.sh clean && ./build.sh` after the full regen produced `chip1.ldr` md5 `87126eb6d05c8acbda900b3b51338f3f` (452,008 B) / `chip2.ldr` md5 `3a9c950d3551b6c5d7ff58925a47ec81` (307,980 B) — the same pair on record since S67-6 (this file, line 14), byte for byte. `MW/D24/DSP/SHARC/build.sh` could not give an independent second data point: it drives `asm21k.exe`/`ld21k.exe` through wine, which fails outright on this box (`wine: failed to open ".../asm21k.exe": c0000135`, 207 errors) against a `src/` tree of 207 files where D32's is 770 — a pre-existing gap the CLAUDE.md already notes ("D24's SHARC tree lags D32; D32 tooling is the superset/reference") and `regenerate-dsp-contract.sh` already reflects (it only calls `dsp_codegen.py` against `MW/D32/DSP/SHARC`). Unrelated to Table, out of this dispatch's scope, not touched.

**Net: no dsp-side file changed this session.** The tree was clean at pull, stayed clean through two full contract-regen passes (`sync-defs.sh`, `check-contract-drift.sh` ×2) and a native D32 rebuild, and is clean now. The 82 Table/MxDatS violators (S68-3) are the one open item, and they are defs' to close.

## THE STRIP MATHS IS RIGHT ON THE PART TO 0.0001 dB, AND A BUS DEFECT PUTS −8.0 SPIKES ON EVERY CHIP-1 BUS, 444 PER 16k SAMPLES AT −40 dB FADER; FIXED IN THE GENERATOR (ONE INSTRUCTION) AND PROVEN (2026-09-17, session 67 — bench, MW-D24-2)

**Pairs** (all built from this tree).
- **`s67`** (`DSP4_TEST_NODES=1` + the new bus taps, before the fix): chip1 `4a784c6a`, chip2 `251ce3b2` [`~/s67u`]. The control, HEAD `TEST_NODES=1` before any S67 change, reproduced `s65base` byte for byte (`24353e71` / `251ce3b2`).
- **`s67fix`** (the same plus the S67-6 fix): chip1 **`e5fb7b4f`**, chip2 `251ce3b2` [`~/s67`, **left running**]. The S67 data comes from this pair; `MW/D24/DSP/s67/data_unfixed/` holds the same battery on `s67`.
- **Shipping.** With only the bus taps it was still `36daa238` / `3a9c950d`. **With the S67-6 fix, chip 1 is now `87126eb6` (452,008 B); chip 2 stays `3a9c950d`.** This is the first shipping-image change since S61. It is deliberate, and it is the fix.

**Bring-up.** matrix-app was stopped; AN_EN read `lo` before and after the stop. Pins set per the bench recipe, then CS_M `27 op pu dh`. The pair was booted and configured for D24 twice (`boot.sh`): CHIP_ID 1/2, `TEST_NODES = 1`, the S58 patch (`dsp4_config.py` = dspboot's). The SAFE chain image (24 registers muted, INSTR 0x00) was sent: **VERIFIED 200/200**. Then `pinctrl set 26 op dh`: AN_EN `hi`. **Rails:** there is no voltmeter on the link. The functional witness is that TEST_MEAS on strips 5/6/7/20 read −114.2…−114.8 dBFS RMS with the osc off. That is converter noise through the 80 Hz HPF; a non-converting lane is a DC word, and the HPF would null it. **Input:** the loop cable is on J25. The coherent loop gain donor strip 6 → AUX 1 → J45 → J25 → strip 5 at code 0 read +5.574 dB (+5.577 on the fixed pair; S54 +5.578), so tests 1, 2, 5 and MAIN-assign use the **real analog input**. AUX 1 is the loop's own source, so strip 5 cannot go on AUX 1 with the analog input: it would feed itself. AUX 1 fader, AUX 1 assign, the sum and a second EQ/dyn set use **TEST_OSC injected at strip 5's input node** (osc mode; it replaces the lane).

**Instrument.** All numbers are TEST_MEAS coherent fits against TEST_OSC's own reference (s54lib `H`), at 1 kHz unless stated. They are read at strip 5 post-fader (MeasChan 5) and at the buses themselves, which is new (S67-1). Tools: `MW/D24/DSP/s67/tools/` (`s67lib.py`, `s67_run.py <phase> <mode>`, `s67_report.py`, `s67_click.py`, `s67_eqglitch.py`, `s67_eqprobe.py`). Data: `MW/D24/DSP/s67/data/` (fixed pair) and `data_unfixed/`. Tables: `MW/D24/DSP/s67/report_fixed.md`. Chip-1 `_diag_blk_overrun` was +0 in every phase on both pairs.

**S67-1. TEST_MEAS now reads the chip-1 buses (TEST_NODES builds only, proposal S67).** `MeasChan`/`XtalkSrc`/`XtalkDst` 33/34 = MAIN L/R, 35–46 = AUX 1–12, 47–50 = GRP 1–4 (`dsp_codegen.py` `TEST_MEAS_BUS_CODES`). The chain calls `_test_meas_tap` with `r1 = _buf_C1_BUS_x` right after each bus node. Bus blocks are not pool slots, so there is no copy. The capture arm works on them too. Idle cost is about ten instructions per bus per block. The shipping image did not change (it was `36daa238` before S67-6). `proposals/CONTRACT-PROPOSAL-S67.md` widens the three cells' range from 33 to 51; no address and no new cell.

**S67-2. Fader, pan, assign and sum: measured = predicted, to the fit's resolution.** dB re the 0 dB fader or re strip 5 post-fader:

| test | predicted | analog input (MIC 5 via the loop) | osc input |
|---|---|---|---|
| fader 0 / −6 / −20 dB, strip 5 post-fdr + MAIN L + MAIN R (+ AUX 1 osc) | 20·log10(Level): 0 / −6.000 / −20.000 | 0.000 / −6.000 / −20.000 on all three, worst error **< 0.0001 dB** | same on all four |
| fader −∞ (Level 0) | exact zero | H = 0 exactly on every point | same |
| back to 0 dB | 0 | 0.000 | 0.000 |
| absolute MAIN L/R at 0 dB, pan centre | strip − 6.021 | strip +5.577, MAIN −0.444 (Δ −6.021) | 0.000 / −6.0206 |
| pan hard L / centre / hard R, law 0 and law 1 | L: 0 / −6.021 / −∞; R: −∞ / −6.021 / 0 | **identical to the prediction at all six points, error 0.0000** | — |
| MainOn 1→0→1 | present / exact zero / present | −0.444 / −∞ (MAIN L/R bus blocks 0 of 16 words non-zero) / −0.444; AUX 1 (donor) untouched | −6.021 / −∞ / −6.021 |
| AuxOn001 1→0→1 (PostFdr, send 1.0) | 0 / zero / 0 | (not run: feedback) | 0.000 / −∞ (0 of 16 words) / 0.000; MAIN unaffected |
| sum, OscChan 99, strip 5 alone / 6 alone / 5+6 / 5+(6 at −6 dB) | MAIN L,R −6.021 / −6.021 / 0.000 / −2.492; AUX 1 0 / 0 / +6.021 / +3.529 | — | **exactly as predicted on all 12 points (3 decimals)** |

- **Fader law.** The DSP's law is linear: `Level` is a linear float, and `_fdr_gq` = fix(Level·2^28) with mute folded in. The dB law lives in the cell master (`dB:Off:-50@31:-30@63:-10@127:10`, e.g. −20 dB = code 95) and belongs to the host. The fader is post-EQ/dyn, and the AUX 1 PostFdr send tracks it.
- **Pan law.** Stated from `tools/dsp/pan_table.py`, measured, with `Sys LcrLaw` at chip-1 0x1366 and `LcrOn` 0. **Under BOTH laws a non-LCR strip is at −6.021 dB at centre, not −3 or −4.5 dB.** Law 0 (hard-LCR) stores the linear (1−p, p) columns. Law 1 (constant power) stores the three-bus legs with the centre folded back at −6 dB. R5 left "what a non-LCR strip reads under law 1" open (pan_table.py: the fold peaks +0.97 dB at p ≈ 0.148). So no stereo −3 dB pan exists on the part today. **Product question for PW:** if stereo strips should pan at −3 dB (or −4.5 dB) centre, that is a third table or a change to law 1's stereo columns, not a bug.
- **Bus law.** A plain linear sum, 0 dB per input, no bus pad. Two equal coherent strips give +6.021 dB. On MAIN a centre-panned pair lands back at unity (2 × 0.5).
- **Assign depth.** "Off" is a crosspoint coefficient of exactly 0. The bus block holds 16 of 16 zero words and the fit reads H = 0, so the depth is total, with no residue at any level.

**S67-3. EQ spot check: exact.** Band 1 peaking 1 kHz, +6 dB, Q 1 (RBJ), bands 2–4 unity. Measured at strip 5 and MAIN L, analog and osc:

| f | predicted | measured (strip / MAIN L, both modes) |
|---|---|---|
| 1 kHz | +6.000 | +6.0000 / +6.0000 |
| 2 kHz | +1.866 | +1.8660 / +1.8660 |
| 250 Hz | +0.423 | +0.4229…+0.4230 |

**S67-4. Compressor spot check: the static curve is exact against the node's own ENVELOPE, and the envelope sits 1.1–1.2 dB under the sine peak.** Settings: thr −20 dBFS, knee 0, ratios 4 and 2; attack/release/makeup left as built (words 0.01 / 0.001 / 1.0). Input peaks −10.0 and −16.0 dBFS (osc), −10.46 and −15.42 dBFS (analog).
- Predicted from the sine's coherent PEAK: GR −7.500 / −5.000 / −3.000 / −2.000 dB.
- Measured coherent GR (osc): **−6.634 / −4.422 / −2.134 / −1.422**. Analog: −6.281 / −4.174 / −2.572 / −1.715 at strip 5, MAIN L within 0.03 dB of the strip.
- `_comp_gain_` (the node's own gain word) reads −6.608 / −4.419 / −2.128 / −1.405. The static curve applied to `_comp_envelope_` (−11.19 / −17.16 dBFS for −10 / −16 dBFS peaks) gives the same numbers.
- So the gain computer matches its model to ≤ 0.03 dB. The detector is |x| with ballistics that ripple under a 1 kHz sine, so it does not hold the peak. The measured fundamental's GR is within 0.03 dB of the mean gain word.
- The engaged compressor moves the level at MAIN L exactly as it does at the strip. Not chased: the attack/release words (0.01 / 0.001) are not in ms, although dsp.csv's row says attack 5 ms / release 100 ms. Their units belong to a dynamics session.

**S67-5. The EQ wire is the OFFSET form, and two bench tools still write direct form.** Under `DSP4_BQ_FLOAT=1` (shipping, and every pair since 09-03) the 20 `_eq_coeffs_next_` words are `(b0, b1+2b0, b2−b0, 2+a1, 1−a2)` per band (`geq_ref.offset_form`), not RBJ direct form. The first EQ run wrote direct form. It produced a different, unstable filter: strip 5 fell to −186 dB and MAIN L was pinned at +18.06 dBFS, the Q4.28 ceiling. Kept as `data_unfixed/eqdyn_analog_directform_wrong.json`. **`tools/pi/dsp4_eq_probe.py` and `dsp4_comp_probe.py` still write direct form (and direct "unity" [1,0,0,0,0]), so they are stale.** Direct "unity" happens to be benign as offset words: (1, −2, 1)/(1, −2, 1), a pole-zero cancellation at DC. `s67lib.eq_bands` converts. **Fixed after the session:** `tools/pi/dsp4_bqwire.py` reads DSP4_BQ_FLOAT from the part's DIAG_BUILD_CFG (bit 12) and encodes, and both probes now take and print direct form but write the running image's wire form (`--wire auto|offset|direct`); `dsp4_apply_strip.py` now writes Pan 0.5 (index 63, centre). `dsp4_pairgraph.py --bq` now encodes through `dsp4_bqwire` and stamps `bq_wire` in the capture; `--compare` warns when two `--bq` captures differ in wire form (unstamped = older captures that wrote direct RBJ whatever the image, so on a float-arm image their "peaking" biquads were other filters). The centre-pan writes that actually used 0.0 were `dsp4_s38_ch1_main.py`, `dsp4_s39_authority.py`, `dsp4_s39_outpath.py` and `dsp4_s39_loop.py`, now 0.5 (`chain.py`, `dsp4_conform.py`, `dsp4_send_proof.py`, `dsp4_xpoint_chain.py` already wrote 0.5; the xpoint sweep's 0.0/1.0 are deliberate ends). The unity resets in `chain.py`, `dsp4_conform.py` (`unity_wire(part)`, arm read once per Part), `dsp4_node_verify.py` (BQCVT's closing reset) and `dsp4_xpoint_chain.py` now write the image's wire form. **Full sweep (2026-09-17), closing S67-5:** every repo tool that writes to the part and names a biquad coefficient address or set was checked. Now through `dsp4_bqwire` as well: `dsp4_send_proof.py`, `dsp4_tubedly_probe.py`, `dsp4_comp_gr.py`, `dsp4_gate_probe.py` (unity resets), `dsp4_family_verify.py` (`write_coeffset`: unity, hpf4k, loshelf12), and three the earlier lists missed, **`dsp4_dly_diff.py`, `dsp4_dly_probe.py`, `dsp4_tap.py`**, whose "resonant HPF" (1, −2, 1, −1.8, 0.81) written raw into a float-arm image was a pole at ≈ 3.75, i.e. an exploding filter, not a resonance. `dsp4_node_verify.py` BQCVT now REFUSES on a float-arm image (its direct-form vectors score the fixed arm's converter, which does not run there). `s67lib.eq_bands` keeps its own offset conversion and now refuses a fixed-arm image. Result of the check: 18 writing tools reference coefficient addresses; 16 route through `dsp4_bqwire`, `s67lib` converts itself with an arm check, and `s67_eqprobe.py`/`s67_run.py` write coefficients only through `s67lib` — none write the old form. Not affected: GEQ/AFB/crossover tools (the part designs those coefficients from gain/freq/slope parameters), comp side-chain filter words (stored, read by no kernel), `eqsweep.sh`/`filtsweep.sh` (direct-form arguments into the converting `dsp4_eq_probe.py`), desk models/generators. Outside this repo and unchecked: whatever computes EQ/FILT coefficients for matrix-app must write the offset form too. `EqOn` has no DSP word (MCU-managed): "EQ off" is the offset unity (1, 2, −1, 2, 1).

**S67-6. THE BUS READOUT SATURATES A SUM IN [−2^27, 0) TO −8.0: a full-scale negative spike at negative-going zero crossings, on all 29 chip-1 buses. Root-caused, fixed in the generator, proven on the part.**
- **Symptom.** In osc mode at 250 Hz with strip 5's EQ at unity, MAIN L read RMS −4.8 dBFS with THD+N ≈ 0 dB, 24 dB above strip 5 × 0.5. It was deterministic and reproducible. A MAIN L capture: **one sample of 0x80000000 (−8.0) every 192 samples**, i.e. every 250 Hz period, at the negative-going zero crossing (…, 220,095, **−2^31**, −220,096, …); the positive crossing read +1. At 1 kHz and 2 kHz no sample happened to land in the window; the +6 dB EQ moved the phase off it at 250 Hz.
- **On real signal** (`s67_click.py`, analog, osc off, MIC 5 noise on MAIN): at fader −40 dB (Level 0.01), **444 of 16,384 MAIN L samples and 475 of MAIN R were −8.0** (2.7 %). At fader 0 dB: 0, because with the 0.5 pan leg only x = −1 can land in the window.
- **Consequence.** Any quiet or faded signal on any chip-1 bus carries full-scale negative spikes. The bus feeds chip 2, whose gather saturates Q4.28 → Q1.31, so they reach the outputs at digital full scale. It is in shipping `36daa238` and every image since the inline bus readout.
- **Cause.** `gen_mix_bus_fixed`'s block kernel (the inlined `_acc64_rns28`) adds the rounding half into MRF, then reads `lo`/`hi` back from MR0F/MR1F. For the saturation sign and test (b) it used `r3`: the `ex` word loaded BEFORE the add. For an accumulator in [−2^27, 0) the rounding carry takes hi −1 → 0 and ex −1 → 0. Test (b) then compared post-add hi (0) against pre-add ex (−1), fired, and saturated to the pre-add sign: −8.0. The shared `_acc64_rns28` reads `mr2f` after the add and never had it. `fixed_ref.mix_sum` gives 0 for these sums, and no harness vector sits in that half-LSB window.
- **Fix.** `r3 = mr2f;` after the add, one instruction per bus sample. It is in the generator, and all 29 `C1_BUS_*.asm` are regenerated.
- **Proof on `s67fix`.** Fader −40 dB: **0 of 16,384 on MAIN L and MAIN R** (was 444 / 475). Fader 0 dB: 0. The 250 Hz EQ toggle: MAIN L : strip 5 = −6.021 dB in every window, both EQ states. The whole S67-2..4 battery was re-run on the fixed pair (the tables above): every osc-mode row equals its pre-fix value to 0.001 dB except the one point the defect had corrupted (osc 250 Hz EQ at MAIN L, −10.389 → +0.4229 dB), and the analog rows agree within 0.03 dB (loop drift between runs). Chip 2 is unchanged, as it has no inline bus readout.

**Side notes.**
- (a) An `AuxSend001` 1.0 write by ramp 4 settles at 0x3F800002, not 0x3F800000 (+2e-6 dB); the send ramp does not snap to its target. Harmless, but a strict read-back verify fails on it (s67lib accepts 1e-5).
- (b) `dsp4_apply_strip.py` writes `Pan 0.0` "pan centre". Under R5 that is index 0, **hard left**. Every strip that tool set up since R5 is panned left.
- (c) The fixed pair was booted with AN_EN already high, which is not analog-last. The chain was all muted except MIC 5 at code 0 and no output was driven, but it is noted.
- (d) `dsp4_inscan.py` still loads `~/dspboot/chip1.sym.json` (the stale-map trap). The `~/s67` copy points at its own map, and under block kernels `_rx_slot_` reads 0 anyway: use TEST_MEAS RMS as the lane witness.

**Hand-back.** TEST_OSC off, MeasChan 5, Xtalk 0/0, LcrLaw 0, strip 5 comp off. Strip 5 and 6 at unity, strip 5 on MAIN, pan idx 63; others muted and unassigned. SAFE chain image VERIFIED 200/200, then **AN_EN `op dl` → `lo`, as found**. matrix-app restarted: active, **MCU boot verified H1S1/H1S3/H1S4 (3/3)**, and it logged "AN_EN STAYS LOW". GPIO 6/7/8/12/22–25/27 are back to the found input/pull states (27 `ip pd | lo`, as found). **Difference from found:** the DSPs were unbooted at power-on and are now running `s67fix` (e5fb7b4f / 251ce3b2). `~/s67u` keeps the pre-fix pair and data.

## THE ACCEPTANCE LAYER IS GENERATED: 38 FIXTURES FROM DEFS, ONE RUNNER, AND THE RECORDED D24 DATA REPRODUCES THE HAND TABLES 187 OF 187; A FACTORY UNIT IS ≈ 18 MIN ON THE HARNESS, OF WHICH 10 IS CROSSTALK (2026-09-16, session 66 — desk, no unit)

**Scope.** Desk only; the unit was not touched. New: `tools/accept/` (generator, battery, limits, units, step costs, the
topology→cell binding, replay-map builder, comparator, `dryrun_d24.sh`), `tools/pi/dsp4_accept.py` (runner: `run` / `report` /
`plan`), fixtures `MW/D24/DSP/accept/`, dry run `MW/D24/DSP/s66/` (`replay/`, `results/{factory,full}/`, `run.out`, `report.md`,
`compare.md`, `plan.out`). Description: `docs/acceptance-audio-layer.md`. No contract, generator or image change.

**S66-1. The fixtures come from defs, and defs is missing four joins the generator needs; each is reported, none is invented.**
- *Rule* (PW 09-14): the in-line path is the LONGEST topology route to the measurement point. Every cell bound to a path
  element goes to its `Neutral`. An assign on the path goes to `Neutral` (enabled), and the same assign on every other strip
  of that bus goes to 0. The measured strip has every assign off, so it cannot feed its own loop. The stimulus block is the
  loop's: donor strip 6 transparent (CompOn/MainOn 0, S54-2) → AUX 1 → J45, or strip 1 when strip 6 is under test. An empty
  `Neutral` is listed as undecidable, and a family the product lacks is listed as absent.
- *D24:* 38 fixtures: 24 inputs (61 path cells + a 98-cell stimulus block each), 11 outputs, 2 Monitor Out fixtures marked
  undecidable, and the cue/RTA node (status proposal). Deterministic; the manifest records the defs commit and a sha256 per table.
- *Trap fixed:* a shortest-path walk went `ch.phase → pick.preeq → ctl.compkey → ctl.compfilt → ch.comp` and skipped
  HPF/LPF/gate/EQ. The topology does not distinguish a sidechain edge from an audio edge, so the generator excludes nodes
  gated `ch.key` and passes pick taps only at the ends.
- *Gaps for defs:*
  - (a) **The topology binds no cells.** `tools/accept/path-cells.csv` is the join and is PROPOSED for
    `common/topology/`. Tube, AntiClip and the output PEQ have cells but no topology node.
  - (b) **Outputs have no table like `inputs.csv`.** Output XLR refs and DAC slots are undeclared (AUX 1 = J45 is known
    only from S42/S48).
  - (c) **The D24 topology has no `mon → io.out` edge**, so the Monitor Out L/R paths cannot be generated. `aux.comp` has
    no cells on D24. `Main001Level001` has an empty `Neutral` (undecidable on both main outputs, as defs already lists).
  - (d) **The factory T1 reference is not in defs.** `mic-gain-law.csv` carries only its target codes (no 8/16/32), so
    the per-code universal mean is averaged from `s55/law.csv` (15 channels, J29 out) and recorded in each fixture.
    The RTA is gated off in `d24.csv` while S65 builds it.

**S66-2. The dry run: 187 of 187 comparisons against the hand tables agree, and the generated table flags what the sessions found.**
- *Method:* `replay_d24_recorded.py` maps every runner key to the files the sessions committed. S61 chirps, reference and
  THD+N tones; S63 THD average and span captures; S57 150 Ω and AUX 1 noise captures; S60 T7; S55 law, loop json and 150 Ω
  captures; S65 proof rows. Captures are analysed as live captures would be. A recorded tone/meter result carries its
  file and method.
- *Exact* (≤ 0.0005 dB, or the hand table's printing precision):
  - MIC 5 against S61 `results.json`: eight chirp gains, T2 at five points × two codes, latency 91.398, inverted,
    THD+N −88.96 dB.
  - THD at code 63 −64.33 dB (S63, 32 averaged). EIN lane powers (S57).
  - A1: 70 silent transitions, 68 PASS / 2 pump, worst −74.0 dBFS (S63).
  - The 15 S55 channels: T2 20 Hz, T3 code 63, EIN 20–20k / A, T5, T8 and the T1 deviation (`channels.md`, `trim-table.md`).
  - AUX 1 −84.55 dBu / −86.96 dBu(A) (S57). The cue node's seven rows (S65-3).
- *Explained, not hidden:*
  - (i) MIC 5 EIN dBu is 0.024 dB below S57's. The powers are identical; the divisor is this run's chirp G(63) = 58.743,
    which carries the loop source's noise (+0.026, S61-3), where S57 used S54's tone 58.717.
  - (ii) The T1 deviations match to the 0.001 dB rounding of the 3-decimal `law.csv`.
  - (iii) The first node run flagged PFL and the mono aux source for a hot cold side. They are mono by design; the
    fixture now says so and the runner checks the sides are equal.
- *Factory verdicts* (`report.md`):
  - MIC 5 PASS.
  - **MIC 7 / J29 FLAG, T1 code 8 −0.849 dB** (the bit-3 stage, S55-2).
  - **MIC 8 / J31 and MIC 20 / J32 FLAG, EIN −123.2 / −125.2 dBu** against the provisional −126.0 (S55-5).
  - The other 12 S55 channels INCOMPLETE: THD-only at max gain and T7 were measured on MIC 5 only.
  - AUX 1 INCOMPLETE (only T4, PASS). Cue/RTA node PASS. MIC 1–4 and 13–16 not run (no rails, S55-1).
- *Full mode:* MIC 5 FLAG on A1, the 0→1 thump (pump 229 ms, and the repeat still open). **T6 is NO DATA on every path:**
  no DSP strip-mute measurement exists, because S54's T6 was the phantom shunt (PW 09-16).
- *Limits:* all in `tools/accept/limits.csv`, all provisional, each with the measurement it was set from.

**S66-3. Time, and what the runner has not done.**
- *Factory per input path:* 51.5 s with desk analysis, 63.6 s with CM4 analysis. That is S61's 26.5 s battery plus
  25 s of 10 kHz T7, 23 neighbours × 1.09 s by meter (S60-4). An output path is ≈ 20 s (step count modelled, not measured).
- *Unit, manual loop:* 24.2 min of instrument time; with 35 cable moves at 30 s, 41.7 min.
- *Unit, harness* (S61's model: per code one setup, per lane 1.55 s): chirps 5.1 + tone/noise 2.3 + analysis 0.4 =
  7.8 min, **plus T7 10.0 min = 17.8 min**.
  - T7 by meter is now the largest factory item. Same-converter neighbours only (7) would make it ≈ 3.0 min and the unit
    ≈ 10.9 min (arithmetic). A multi-lane capture arm is the other lever.
  - The spec's ≈ 2 min harness figure is not reachable with a per-strip arm/fill.
- *Full mode:* 5.1 h manual and 4.7 h on the harness. The A1 spans are 8.6 min a channel (S63), 3.4 h of it.
- *Not done:* **the live source is not exercised.** This repo has no verified host command that writes a cell by MxDat
  code (`app cli` has `chain-set`, not a cell set), so live mode refuses until `ACCEPT_SET_CMD` names one. The meter-method
  keys (T6, T7, the T4 floors) are wired for replay only. The first live run is a bench dispatch: MIC 5 factory against
  this dry run's numbers.

## THE CUE BUS AND THE RTA ON CHIP 1: BUILT, PROVEN THROUGH THE PARAMETER LINK, DELIVERED TO CHIP 2; +0.6 % FOR THE BUS, +10.6 % FOR THE RTA; THE D24 FITS AT 70.6 % DRIVEN ON THE s26 LEVERS AND DOES NOT FIT ON TODAY'S SHIPPING CONFIG (121.8 % BEFORE EITHER) (2026-09-16, session 65 — desk + digital loop, MW-D24-2)

**Pairs** (all built from this tree; bench dirs in brackets).
- **Shipping** (`DSP4_CUE=0 DSP4_RTA=0`): **`36daa238` / `3a9c950d`**, byte for byte S61–S64's, rebuilt twice after the generator change.
- **`s65`** (`TEST_NODES=1 CUE=1 RTA=1`, shipping.config): chip1 `2d69a32f`, chip2 `a4dd11f4` [`~/s65`]. **`s65base`** (`TEST_NODES=1` only, same tree): `24353e71` / `251ce3b2` [`~/s65base`].
- **`s65s26`** (the same switches on `shipping.config.s26`): `0ba6cba6` / `29f58878` [`~/s65s26`]; **base** `d90a379b` / `7ef50a94` [`~/s65s26base`].
- Chip 1 `TEST_NODES` images differ from S62's `57948d77` by the new TEST_OSC channel-99 arm (S65-2).

**Scope.** Digital only. The chain, MIC 5, the analog path, AN_EN and CS_M were not touched by the S65 work. The hub addendum's THD sweep (MIC 5, code 63) ran first on S63's pair and is in `MW/D24/DSP/s63/artefacts.md`. Generator: `dsp_codegen.py::gen_cue` / `gen_cue_rx` / `cue_spi_layout` (new), `gen_rta` moved to chip 1, the inter-chip tables and `lane_config.c` behind `#if DSP4_CUE`, the C2_MON source read, and the TEST_OSC every-strip arm. Hand-written: `chip1/spi_handler.asm` (the out-of-table branch), `diag.asm` (the RTA diag hooks now on chip 1), `diag.h`, `build.sh`, `shipping.config`. Tools `MW/D24/DSP/s65/tools/`, data `MW/D24/DSP/s65/data/`. Proposal `proposals/CONTRACT-PROPOSAL-S65.md`.

**S65-1. The cue bus exists on chip 1, from cells the master already carries plus four it does not.**
- **Cells found** (`defs/common/cells/mx_master.csv`; the Bible `09-cell-name-registry.md` has only the one-line descriptions):
  - `Chan[1-64]CueSel` (row 136) and `Main[1-1]CueSel` (225).
  - `Sys[1-1]CueMode` (339, PFL/AFL/SIP) and `Sys[1-1]Cue[1-64]` (338, a console-state mirror).
  - `Mon[1-1]InputSel` (235, 2 states, chip-2 `0x06FC`), `Mon[1-1]Level[1-2]`, `Phones[1-4]Src`/`Level`, `Rta[1-1]On`/`Src`.
- **Missing, PROPOSED not invented:** `Aux[1-12]CueSel`, `Grp[1-4]CueSel`, `Cue[1-1]Src` (the assigned source), `Cue[1-1]Active` (ro). There is no cue/monitor level cell other than `Mon Level` and `Phones Level`.
- **What it sums.**
  - PFL: the strip's pre-fader tap (`BLK_TAP_PREFDR`: post-delay, pre-fader, pre-mute), mono, unity to both sides.
  - AFL: the post-fader block times the strip's own pan legs (`_fdr_lq/_fdr_rq`, the legs the main crosspoints use).
  - SIP: AFL on the bus.
  - Bus cues: the chip-1 main L/R, aux and group sums, which come **before** the chip-2 bus masters.
  - Nothing cued: `Cue Src`, copied bit-exact (0 main L/R default, 1–12 aux, 13–16 group).
- **How.** A four-instruction test after every `C1_FDR_nn` calls `_cue_strip` only for a cued strip (the pool blocks die when the next strip runs). The float32 sums are FIXed back to Q4.28 in `_cue_finish` after the whole chain, and the RTA reads that output. `fix` overflow saturation is assumed from the core's documented behaviour; nothing here drove the sum past full scale to test it.
- **To chip 2.** MIX_2 slots **9/10 = global 41/42**. MIX_2 carries snake 4–8 on 0–4 and the matrix buses on 5–8, and marks 9–15 reserved: **room for 7, 2 used.** Under the switch the lane grows 9 → 11 packed words (CS `0x07FF`, region 656 → 688, both chips).
- **The monitor.** `C2_MON` reads the cue L receive when `Mon001InputSel001` = 13; its source word had no reader before. **What remains:**
  - The monitor path is mono end to end: MON, MON_DLY and MON_OUT carry one block, and MON_OUT fills one of its two CODEC_OUT_1 slots.
  - Aux 1–12 as a monitor source still has no reader.
  - The master's `Mon InputSel` is 2 states and must widen to 14.
  - `Phones[1-4]` have no DSP nodes.
- **Also found:** `Pan` on the wire is a float32 0.0–1.0 (`pan_law.asm` × 126), not an index; the first proof run wrote the integer 126 and read "no move" (`data/s65_prove_run1_intpan.jsonl`, a tool error, not firmware). And every strip's pan word boots at 0.0 = hard left.

**S65-2. The price, driven, on the part: the cue bus ≈ +0.4–0.6 %, the RTA +10.5–10.6 % (same as on chip 2), each cued strip ≈ +245 cycles. On the s26 lever configuration the D24 is 70.6 % with every strip cued and the RTA on. On today's shipping.config it is 121.8 % with neither.**
*Driven, without a CPLD flash.* TEST_OSC gained an S65 arm: channel **99 = every strip**. It replaces each strip's input block with a 1 kHz sine at −6 dBFS pk. `dsp4_driven_setup.py --chip 1 --mode load` opens every assign and send and puts every gate/compressor at −60 dB, On (648 written, 0 failed). The witness is a comp gain reduction of ≈ −39.6 dB on strips 1–3. The injector is in both images, so base vs S65 isolates the cue bus. `_proc_cyc` medians of 6 interleaved rounds × 0.5 s; overruns by delta (`s65_cost.py`, `s65_ladder*.sh`). Budget 327,680.

| configuration / product | base (no cue) | S65: nothing cued, RTA off | RTA on | + strip 6 PFL | + every strip AFL | overruns (worst arm) |
|---|---:|---:|---:|---:|---:|---:|
| **s26** D24 (24 strips) | 188,610 = **57.56 %** | 190,632 = 58.18 % (+2,022) | 225,383 = 68.78 % (+34,751) | 225,607 (+224) | 231,256 = **70.57 %** (max 71.01) | **0** |
| s26 D32 (32) | 228,366 = 69.69 % | 230,205 = 70.25 % (+1,839) | 264,575 = 80.74 % (+34,370) | 264,804 (+229) | 272,395 = **83.13 %** (max 83.73) | 0 |
| shipping.config D24 | 399,085 = **121.79 %** | 400,459 = 122.21 % (+1,374) | 434,878 = 132.71 % (+34,419) | 435,103 (+225) | 440,766 = 134.51 % | 2,320 / 3 s |
| shipping.config D32 | 484,788 = 147.95 % | 486,283 = 148.40 % (+1,495) | 520,720 = 158.91 % (+34,437) | 520,928 (+208) | 528,527 = 161.29 % | 3,439 / 3 s |

- **The RTA costs chip 1 what it cost chip 2**: +34.4–34.8 k cycles (S64-3: +34.4 k), product- and configuration-independent.
- **The cue bus idle** (hooks + finish + source copy + the two gather slots) is +1.4–2.0 k cycles. This is a base image against the S65 image on separate boots, so the boot-to-boot spread is inside the figure. A cued strip costs 224–229 (PFL) and 244–245 each (AFL).
- **The ≤ 90 % gate.** "Chip 1 near 59 % driven" is the **s26** configuration: the fit table's anchor, with SIMD_DYN, STRIP_FUSED, C2_BQ_GRAPH, GATE_LINTHR, DYN_LUT and SHARED_KERNELS. Measured here it is 57.6 %. **With the cue bus and the RTA the D24 reaches 68.8 % and, every strip cued AFL, 70.6 % (max 71.0 %), 0 overruns: IT FITS.** D32, reported: 83.1 %, 0 overruns.
- **On `shipping.config` as it stands, chip 1 is already 121.8 % driven with no cue and no RTA** (S39-3's 114.9 % was the same shape). The cue/RTA question does not change that; S42-6's lever decision does.
- **The cue hook is right on the PAIRED chain too** (s26 = SIMD_DYN): strip 5 (odd, pool1 slots) and strip 6, PFL → L and R −23.02/−23.01, AFL pan L → L −23.01 with R ≤ −163.9 (`data/s65_hookcheck.jsonl`).
- **Words and code pool** (linker maps):

| | chip 1 code (B) | chip 1 DM (B / words) | chip 2 code (B) | chip 2 DM (B) |
|---|---:|---:|---:|---:|
| cue bus | +1,792 | +2,096 / 524 | +18 | +416 |
| RTA | +972 | +3,008 / 752 | 0 | 0 |
| **shipping.config pool after both** | **6,390 free** (of 9,154) | 106,620 free | 128,126 free | — |
| **s26 pool after both** | **72,930 free** | 59,412 free | | |

**S65-3. Proof through the digital loop and the parameter link: every row within 0.1 dB, octave neighbours 40.7–50.9 dB down, the cold side at ≤ −162 dBFS, τ 35.0 / 125.0 ms, peak-hold held and reset, and the bus arrives on chip 2.**
*Pair `s65` (shipping.config, undriven: chip 1 read 225,168 cycles = 68.7 % with nothing cued and the RTA off; overruns were not tracked during the proof, and the RTA's input is the cue block the same pass produced).* Stimulus TEST_OSC −20 dBFS pk on strip 6 (S56 donor route); expected −23.010. Bands read as the proposed cells `Rta001MtrL/R` through chip 1's parameter link, median of 3 (`s65_prove.py`, `data/s65_prove.jsonl`).

| case | tone | band reads | error | octave down / up | cold side |
|---|---|---:|---:|---|---:|
| A strip 6 cued AFL, pan L | 63 Hz | −23.082 | −0.072 | 48.38 / 48.71 | R −359 (0) |
| A | 1 kHz | −23.001 | +0.009 | 48.72 / 48.58 | R −359 |
| A | 8 kHz | −23.009 | +0.001 | 50.86 / 40.74 | R −359 |
| A pan R (Pan 1.0f) | 1 kHz | R −23.011 | −0.001 | 48.69 / 48.57 | L −207 |
| B strip 6 cued PFL | 1 kHz | L −23.011, R −23.011 | −0.001 | 48.69 / 48.57 | (mono: both) |
| C nothing cued, Cue Src 0 = main L/R (strip 6 MainOn 1, pan L) | 1 kHz | L −23.011 | −0.001 | 48.69 / 48.57 | R −162.3 |
| C nothing cued, Cue Src 1 = AUX 1 | 1 kHz | L −23.011, R −23.011 | −0.001 | 48.69 / 48.57 | (mono bus) |

- `Cue001Active001` read 1 in A/B and 0 in C. TEST_MEAS on strip 6 read −23.071 / −23.012 / −23.010 at 63 / 1k / 8k.
- **Ballistics:** fast −124.1 dB/s = **τ 35.0 ms**, slow −34.7 dB/s = **τ 125.0 ms**. Peak-hold held −23.0 dBFS 1 s after the tone stopped; `Rta001PeakReset001` → −130.7 dBFS and read back 0.
- **Delivered to chip 2** (`Mon001InputSel001` = 13, 200 single peeks of word 0 per array):

| arm | cue L rx rms / max | cue R rx | `_blk_C2_MON` rms / max |
|---|---|---|---|
| strip 6 cued AFL pan L | 0.0805 / 0.0924 | 0 / 0 | 0.0793 / 0.0793 |
| nothing cued, Src main (silent) | 0 / 0 | 0 / 0 | 0 / 0 |
| cued again, monitor back on source 0 | — | — | 0 / 0 |

  - The tone's peak is 0.1. Word 0 of a 16-sample block of a 48-sample period takes only three phases, so the rms is not 0.0707; it is non-zero exactly where the cue says, R is exactly 0, and the monitor follows its source word.
  - **The chip-2 bulk read could not be used.** With S64's checksum bypass for live blocks, three different arrays on three reads returned the SAME 16 words, all broken at sample 10. That is not what any of those arrays holds, so no contiguity claim is made from it. Why the stream repeats is not chased. S64-4's chip-2 bulk-read snapshot used the same bypass and should be re-checked before it is cited.
- **The meter path and its rate.** The 62 band words are raw one-word reads on chip 1's parameter link, the path the METER read-back block at `0x1200..` uses. The DSP refreshes them 3,000 times a second (`_rta_seq` +1,502 in 0.5 s). Through the bench tool link all 62 took **0.155 s (≈ 6.5 fps)**, with one paced ask per word (a meter word moves every block, so the settle-vote read cannot be used). The CM4 daemon's ring rate is still the hub's number.

**S65-4. Contract proposal S65 (not landed), switches, gates.**
- `proposals/CONTRACT-PROPOSAL-S65.md` supersedes S64's chip-2 addresses:
  - `RtaOn` kept; `RtaSrc` retired; `RtaMode` / `RtaPeakReset` / 62 read-only band meters.
  - Chan/Main CueSel and `Sys CueMode` mapped; `Aux/Grp CueSel`, `Cue Src` and `Cue Active` new; `Mon InputSel` widened to 14 states.
  - All at chip-1 **`0x1378..0x13ED`**, directly after the 4,984-entry dispatch table, S44 way, no moves. The generator refuses to emit if the table ever grows into the block.
- **Switches.** `DSP4_CUE` and `DSP4_RTA`, both 0 in `shipping.config`. With them off both images are byte-identical (`36daa238` / `3a9c950d`). `DSP4_RTA=1` without `DSP4_CUE` is a build error.
- `check-sharc-codegen-drift.sh`: pass (`chip1/cue.asm`, `chip1/rta.asm`, `chip2/cue_rx.asm` generated; `chip2/rta.asm` removed).
- **Hand-back (19:23 BST).** The s60 pair twice (`fe522a7f` / `c56ed0ab`), `s56_setup.py`, `s60_handback.py`. `s60_found.py after_s65b` vs `found_s65`: every field identical but MIC 5 idle −106.08 → −105.72 dBFS. AN_EN `op pd | hi`, CS_M `op pu | hi`, never written; `matrix-app` inactive as found. `~/s65`, `~/s65base`, `~/s65s26`, `~/s65s26base` hold the pairs and tools; `~/s60`, `~/s62`, `~/s63`, `~/s64` and `~/dspboot` are untouched.

## THE RTA FROM THE CUE BUS: THE GRAPH HAS NO CUE BUS, TWO BIQUADS A BAND CANNOT MAKE 40 dB, AND THE FILTERBANK IS RIGHT ON THE PART BUT COSTS CHIP 2 10.5 % AND DOES NOT FIT THE D24 (2026-09-16, session 64 — desk + digital loop, MW-D24-2)

**Pairs.**
- **`s64`** (`DSP4_TEST_NODES=1 DSP4_RTA=1`): chip1 `57948d77` (S62's, byte for byte), chip2 `9ea76239` (313,516 B). Staged at `~/s64`. Booted and configured D24 twice, then D32 twice for the D32 row.
- **`s64lim`**: the same tree with `DSP4_NODE_LIMIT2=27`, chip2 `bef25110`, staged at `~/s64lim`. It is the proof instrument (S64-4).
- **Shipping:** `DSP4_RTA=0` from the final tree is still **`36daa238` / `3a9c950d`**, 451,892 / 307,980 B, byte for byte S61/S62's shipping pair.
- **Shipping with the switch on** (`DSP4_RTA=1`, TEST_NODES 0): chip2 `e213e98e`, 311,952 B. This one was built and **not booted**.

**Scope.** Digital only. The chain, MIC 5, the analog path, AN_EN and CS_M were not touched. Tools are in `MW/D24/DSP/s64/tools/`, data in `MW/D24/DSP/s64/data/`. Generator: `tools/dsp/rta_design.py` (new) and `dsp_codegen.py::gen_rta`, which emits `src/chip2/rta.asm` and hooks it at the end of chip 2's chain. Hand-written: diag registers `0xE0C0..0xE0C7` (`diag.h`/`diag.asm`), plus the `DSP4_RTA` flag in `build.sh` and `shipping.config` (0). Proposal: `proposals/CONTRACT-PROPOSAL-S64.md`.

**S64-1. There is no cue bus in the DSP. Chip 2 is the right chip, and the stereo it would need is not in the graph either.**
- **No cue node anywhere.** `dsp.csv` has no cue or PFL node on chip 1 or chip 2. The master's `Chan*CueSel`, `Sys001Cue*` and `Sys001CueMode` are all control-plane (`defs/products/d24/dsp-unmapped.csv`: "the DSP has one monitor source word … open question Q5").
- **The monitor is the nearest thing.** It is `C2_MON` on chip 2, feeding the phones codec (`C2_MON_OUT`, CODEC_OUT_1). It reads only `C2_MAIN_FDR`. Its `_mon_source_C2_MON` word (generator comment: 0 = Main, 1–12 = Aux, 13 = Cue) has **no reader**.
- **Chip 2's "2-channel" nodes are mono.** `C2_MAIN_FDR`, `C2_MON`, `C2_MAIN_DLY` and the others each carry ONE `_blk_` array. Main L and R stay separate only as far as `C2_MIX_MAIN_L/R`, then collapse at the fader.
- **What that means:** a stereo cue needs graph work (a cue bus pair, the monitor source switch, stereo monitor nodes) before any RTA can "follow the cue".
- **What was built.** The RTA reads a **pointer pair**. Its default is `C2_MIX_MAIN_L/R`, the only distinct stereo pair on chip 2, and it can be repointed through `DIAG_RTA_SRC_L/R` on a TEST_NODES image. The kernel's cost does not depend on its source (S64-3). When a cue bus exists, the generator's `RTA_SRC_DEFAULT` names it.

**S64-2. The dispatch's "class-2 shape = two biquads per band" cannot pass its own ≥ 40 dB-at-one-octave gate. Three can.**
- **Design.** Digital Butterworth bandpass, both −3 dB edges prewarped onto the IEC 61260 base-ten edges.
- **One octave from centre** (`rta_design.py`): prototype order 2 (two biquads) gives **32.2–32.5 dB** on every band below 5 kHz. Narrowing it until its edges read −5 dB still gives only 35.9 dB. Order 3 (three biquads) gives **48.3–48.8 dB**.
- **So the built bank is 31 × 3 × 2 = 186 biquads**, not 124.
- **Kernel shape.** Every section is (1 − z⁻²)/(1 + a1 z⁻¹ + a2 z⁻²). There is no numerator multiply, and the band gain goes into a block-rate normaliser.
- **Precision.** float32 DF1 was simulated first and holds the 20 Hz band (pole radius 0.9997). The kernel runs band-outer / sample-inner with all six coefficients and states of a band in registers: 25 instructions per band per sample.
- **Detector.** Mean square per block, then one pole at block rate: fast τ 35 ms, slow 125 ms, or peak-hold (fast, held until reset, branch-free as `max(hold·out, e)`).
- **Law.** dBFS = 10·log10(word), the TEST_MEAS `RmsResult` law.

**S64-3. The price, measured on the part: +34.4 k cycles a block (10.5 % of chip 2) whatever the product, the load or the signal. The D24 does not fit.**
*Method.* `_proc_cyc` (exact TCOUNT per pass) was read on chip 2 with `RTA_ON` toggled 0/1, interleaved on one boot, and `_diag_blk_overrun` was read by delta per arm (`s64_cost.py`). The budget is 327,680 cycles (block 16).

| image / configuration | chip 2 off | chip 2 on | Δ cycles | missed blocks (on arm) |
|---|---:|---:|---:|---:|
| `s64` D24, FX engines as booted (all 6 on, Type 0) | 316,642 = **96.63 %** | 351,197 = **107.18 %** | +34,555 | **820** in 4.0 s |
| `s64` D24, six engines parked (`FxnOn 0`) | 299,993 = 91.55 % | 334,169 = 101.98 % | +34,176 | **250** |
| `s64` **D32** configuration | 410,859 = **125.38 %** (2,450 missed with the RTA OFF) | 445,257 = 135.88 % | +34,398 | 3,192 |
| `s64lim` D24 (chain cut at position 27) | 33,086 = 10.10 % | 67,485 = 20.59 % | +34,399 | 0 |

- **What it costs.** **+34.2–34.6 k cycles in all four conditions**, a spread of 1.1 %. It is data- and product-independent, as the kernel is (no branch in it). That is 11.6 cycles per section per sample including overhead, or 10.5 % of chip 2.
- **Why the base is not "driven".** The base figures were NOT taken with S19's driveall CPLD method: that means a LOGIC flash on the rev C unit with the analog chain loaded, which this dispatch excludes. Only the base would move under drive, and only upward.
- **Memory.** 749 DM words (217 coefficient, 372 state, 124 detector/output, 36 other). Loader +3,972 B (shipping + switch vs shipping).
- **THE D24 DOES NOT FIT.** Chip 2 on today's D24 image is at 96.6 % before the RTA. The RTA takes it to 107 % and misses 5 % of blocks. Even with every plugin parked it reaches 102 % and still misses blocks.
- **D32, reported, not a gate.** Its chip 2 is already over budget at 125 % with the RTA off.
- **An overrunning RTA reads wrong, and it looks plausible.** On the full image, the 1 kHz tone read −24.67 (−1.65 dB) with the one-octave neighbours only 18–24 dB down (`s64_prove_full_overrunning.jsonl`). The spectrum smears in proportion to frequency, the signature of a stream with dropped blocks.
- **Levers, priced from the measured 11.6 cycles/section-sample:**
  - *(i) Multirate.* The 20 bands ≤ 1.6 kHz run on the stream decimated by 8, after a 4-section anti-alias filter at full rate. That is 712 section-evaluations a channel instead of 1,488, **≈ 16.5 k cycles = 5.0 %**. It still does not fit with the engines on (101.6 %). It fits only with them parked (96.6 %, no margin).
  - *(ii) Mono.* Half of either figure.
  - *(iii) Host FFT (B).*
  - **None of the DSP levers fits beside today's D24 plugin load.**
- **(B) HOST FFT**, priced from S56 and S61/S62 as asked, no build.
  - *DSP cost.* The capture arm costs +72 cycles per pass for one channel (S56-1), so ≈ 150 cycles for L+R, **0.05 % of chip 2**. It fits.
  - *Full-rate captures.* A 4,096-sample capture has 11.7 Hz bins. The 20/25/31.5 Hz bands are 4.6/5.8/7.3 Hz wide, so they need ≥ 16,384 samples (2.9 Hz bins, 341 ms). For two channels that is 32,768 words ≈ 0.44 s of bulk read (S62: 0.22 s per 16 k), so **≈ 1.3 fps** if every frame is a fresh 16 k pair. A 4,096 pair gives ≈ 7–8 fps (85 ms fill + ≈ 0.11 s read), but the bottom four bands are then unresolved.
  - *The multi-rate fix.* The DSP decimates the cue pair by 16 to one sample per block (a 4-biquad anti-alias filter: ≈ 16 × 4 × 11.6 ≈ 740 cycles a channel, ≈ 0.5 % stereo) into a ring the host reads, plus a short full-rate capture. 1,024 decimated samples give 341 ms with 2.9 Hz bins for bands ≤ 1.25 kHz. 1,024 full-rate samples give 47 Hz bins for bands ≥ 1.6 kHz. That is ≈ 4,100 words a frame ≈ 60 ms of read, so **≈ 10–15 fps** with a sliding low window, for ≈ 0.5 % of chip 2.
  - **This is the only priced option that fits beside the D24's plugin load today.** It moves 31-band maths per channel onto the CM4, where it is small.
- **(C) GOERTZEL.** It is the wrong tool for a band power. It is a single-bin detector: its response is a sinc of width fs/N centred on one frequency, not a flat 1/3-octave passband. A tone between bands is scalloped by up to ~4 dB (rectangular window), pink or broadband energy in the band is under-read, and its sidelobes decay 6 dB/octave, so the one-octave rejection of the biquad bank is not reachable. Making it a band detector means windowing it to the band's width: N ≈ fs/bandwidth, 10 k samples for the 20 Hz band (208 ms), with a window multiply every sample. *Price, trivial:* one multiply and two adds a sample a band ≈ 5 cycles, so 31 × 2 × 16 × 5 ≈ **10 k cycles ≈ 3 %** unwindowed, ≈ 5 % windowed. Cheaper than the biquads and still over the D24's 3.4 % headroom, for a worse answer.
- **The meter ring rate.** The CM4 daemon's shm meter-ring rate is **not in this repo or readable on the unit** (stripped binary). The only meter cadence on record is the MCU poll at ~260 ms. The DSP side refreshes the 62 words 3,000 times a second. By single peeks one word takes 1.25 ms (62 in 78 ms, ≈ 13 fps). The hub owns the ring figure.
- **The image does not say it carries the RTA.** `DIAG_BUILD_CFG`/`CFG2` read the same word as S62 (`0xCF45FF10` / `0xC3010244`), which is S12-7's shape. Until a CFG2 bit is assigned, detect it with `DIAG_RTA_BANDS` = 31.

**S64-4. Proof through the digital loop: the right band at the right dBFS to 0.12 dB, one-octave neighbours 40.7–50.9 dB down, the other channel at −214 dB, ballistics τ 35.0 / 125.0 ms, peak-hold held and reset.**
*The instrument.* A proof on an overrunning image measures the overruns (S64-3), so the proof image is `s64lim`. `DSP4_NODE_LIMIT2=27` stops chip 2's chain after position 26. The RTA is called after the chain and is byte-identical in `rta.asm`, and chip 2 runs at 10.1 %/20.6 % with 0 missed blocks.
*The source.* The stand-in pair is `C2_RECV_AUX_01` (L) / `C2_RECV_AUX_02` (R), chain positions 7/8. With no FX sends, S23 proved the aux sum bit-exact to the receive. The aux sums themselves are positions 59/60, beyond the cut.
*The stimulus.* TEST_OSC −20 dBFS pk on strip 6 → AUX 1 (the S56 donor route, unity). Nothing sends to AUX 2. Expected reading: 10·log10(0.1²/2) = −23.010.
*The bank as a whole on the full image.* A bulk-read snapshot of `_blk_C2_MIX_AUX_01` fitted a 1 kHz sine to a residual of 1.9 × 10⁻⁸, so the source block is contiguous.

| tone | band | reads, dBFS | error | TEST_MEAS strip 6 | one octave down / up | adjacent | cold channel |
|---|---|---:|---:|---:|---|---|---:|
| 63 Hz | 63 | −23.127 | −0.117 | −22.987 | 48.52 / 48.52 dB | 18.06 / 18.36 | −∞ (exact zero) |
| 1 kHz | 1k | −23.014 | −0.004 | −23.012 | 48.69 / 48.57 dB | 18.30 / 18.29 | −∞ |
| 8 kHz | 8k | −23.011 | −0.000 | −23.011 | 50.86 / 40.74 dB | 19.84 / 16.43 | −∞ |
| 1 kHz, **L/R swapped** | 1k on **R** | −23.014 | −0.004 | −23.012 | 48.69 / 48.57 dB | 18.30 / 18.28 | L max −214.06 |

- **Every row passes** (|error| ≤ 0.5 dB, both octave neighbours ≥ 40 dB, cold channel > 60 dB below).
- **Against the design.** The 8 kHz tone's upper neighbour (16 kHz band) reads 40.7 dB against a design value of 41.1 dB: the bilinear skirt of the top bands. The 63 Hz error (−0.12 dB) is inside the 0.5 dB gate; the float32 model of the same kernel predicts −23.05 for a 63.1 Hz tone over a 0.6 s read, so about half of it is the model's own, and the rest was not chased.
- **Stereo separation.** A tone on L only shows on L; swapping the source moves it to R and nothing else changes.
- **Ballistics.** Decay after the tone stops, slope fitted over 3–40 dB below the start: **fast −124.0 dB/s = τ 35.0 ms** (479 points), **slow −34.7 dB/s = τ 125.0 ms** (1,867 points), against designed 35 / 125 ms.
- **Peak-hold.** −23.0 dBFS still held 1 s after the tone stopped. `RTA_RESET` → −130.1 dBFS within 0.5 s, and the reset word read back 0 (consumed).
- **`RTA_SEQ`** advanced 1,508 in 0.5 s (3,016/s by host clock; 3,000 nominal).

**Hand-back (18:16 BST).**
- **Pair and cells.** The s60 pair was rebooted twice (`fe522a7f` / `c56ed0ab`), then `s56_setup.py`, then `s60_handback.py` **without its `R.chain(0)` line**.
- **Check.** `s60_found.py after_s64` against this session's `found_s64` snapshot: **every field identical** (`data/s64_found_after.jsonl`). MIC 5 idle −105.9 dBFS found and −106.1 after.
- **Unit pins and app.** AN_EN `op pd | hi` and CS_M `op pu | hi` were read before and after, never written. `matrix-app` inactive as found.
- **Staged.** `~/s64` and `~/s64lim` hold the pairs and tools. `~/s60`, `~/s62`, `~/s63` and `~/dspboot` are untouched.
- **Side note: the drift gate.** `check-sharc-codegen-drift.sh` was already failing on main. S61's hand-written `src/bulk_read.asm` had never been added to its HANDWRITTEN list. It is added now, and `check-contract-drift.sh` passes with `rta.asm` counted as generated.

## GAIN-CHANGE ARTEFACTS ON MIC 5: SILENCE HIDES ALL BUT A 0→1 THUMP; THE TONE FINDS A BREAK-BEFORE-MAKE DROPOUT TO THE AND CODE ON EVERY MULTI-BIT STEP; THE PREAMP ACTS ~10 ms AFTER THE LATCH; THD AT MAX GAIN −64.3 dB (2026-09-16, session 63 — bench, MW-D24-2)

**Pair and unit.**
- Pair: s62 handshake (`57948d77` / `251ce3b2`, TEST_NODES), staged at `~/s63`, booted and configured D24 twice.
- Found: s60 pair with S62's hand-back, `matrix-app` inactive, AN_EN `op pd | hi`, CS_M `op pu | hi`.
  Snapshot `found_s63` = S62's after.
- Loop: TEST_OSC strip 6 → AUX 1 → cable → J25 → MIC 5 (U41, p15) → strip 5, transparent.
- Chain: the S55 image by spidev, **CS_M driven by a GPSET0/GPCLR0 write on `/dev/gpiomem`** (one instruction; pin
  function and pull untouched). The hub's `app cli chain-set` route was not used because the app was inactive.
- Data: `MW/D24/DSP/s63/data/` (raw `.bin.xz` int32 Q4.28 + `.jsonl`; `tables.md`, `s63_results.json`, `latch.out`,
  `thd.out`). Tools: `MW/D24/DSP/s63/tools/`. Report and all tables: **`MW/D24/DSP/s63/artefacts.md`**.
- 216 captures, 0 overruns, 0 invalid. Read median 0.220 s.

**S63-1. The measurement format: one capture spans the change, and the change is placed to ± 16 samples.**
- *Capture.* `s63lib.Rig.span`: clear Ready, arm 16,384, poll `_meas_cap_idx_C1_TEST_MEAS` (~1 ms, 104 polls) to the
  4,800 mark, make the change, bulk-read.
- *Timing.* The polls map host time → capture sample; the within-capture spread is one block (median 10, max 16 samples).
  The latch edge is bracketed to ≤ 1.4 samples, a Gain001 write to ≤ 16.
- *Transitions.* Walked so each starts where the last ended, ≥ 3.0 s after any change: null ×2, the table's 48
  consecutive steps, 12 major-carry changes, trim ±1/3/6/12 dB at code 0, combined 30↔31 dB. That is 72 per stimulus:
  silent (osc off, loop-cable source) and 1 kHz (louder side −8 dBFS pk). 8.6 min per channel.
- *Analysis* (`s63_analyse.py`, desk numpy, 18 s a channel): one table per case, one row per transition. Silent
  detection thresholds are calibrated on the no-change captures: at every 480-sample offset, AC peak ≤ floor RMS
  + 14.6 dB and DC ≤ 0.90 × floor RMS. Set at > 3 dB over the old/new floor peak or DC > 1.5 × floor. **0 of 4 nulls detect.**
- *Tone.* Frequency fitted jointly; sinusoid+DC fitted before and ≥ 100 ms after; the ideal instantaneous step placed at
  the measured 50 % point. Level change matches the S55 law to ≤ 0.004 dB on all 70 transitions; phase step ≤ 0.14°.
- *Pass/flag.* PW's ruling (hub, this session): artefact peak ≤ −60 dBFS at the lane, no DC pump > 50 ms.
- *Runner.* Ready for the other 15 channels: `DONE=J25 python3 s63_run.py` (S55 WATCH, PROMPT to move the cable,
  ≈ 8.6 min a channel). PW was not asked and the WATCH path was **not exercised** this session; MIC 5 ran with `CHAN=J25`.

**S63-2. The preamp gain acts 9–10.5 ms after the latch, and the pass-1 edge is the one that applies it.**
- *Which edge* (`s63_latch.py`, code 0↔1 under the tone). With 0 and 50 ms between the two chain passes, the lane
  reaches 50 % at **+491…+503 samples (up) / +435…+439 (down) after pass 1's CS_M rising edge**. That is identical with
  the gap, and 2,081–2,149 samples before pass 2's edge.
- *Delay over the whole table* (clean steps): up median 10.5 ms (10.2–12.2), down 9.0 ms (8.4–9.4).
  Transition 10–90 % median 1.5 ms; settle to 0.1 dB median 10.9 ms after the latch.
- *Where the delay is.* The converter + DSP path is ~1 ms (S60 loop latency 91 samples), so ~8–9 ms is the preamp's
  control path (595 → gain-switch drive). Measured, not explained from the schematic.
- *Trim, for contrast.* A Gain001 write moves the lane at its own sample (host +0): the host map is good to a block.
  The GainFast ramp is linear, 144 samples up / 384 down (3/8 ms as the profile table says).
- *Consequence (not changed).* A product change that writes the code and the trim together lands the trim ~6 ms before
  the step reaches the lane. The combined 30↔31 dB case: trim 3.8 ms after the latch, step 9.2/10.3 ms after.

**S63-3. Every multi-bit step drops out to the gain of (from AND to): break-before-make in the gain switches. Silence hides it; only 0→1 is audible in silence.**
- *Silent: 68 PASS / 2 FLAG.* Only codes 0↔1 put anything above the floor:
  - **0→1 is a thump**, DC ↓ −78.2 dBFS (5 × floor RMS), τ 163 ms, pump 229 ms; the repeat (the bit case) reads −85 dBFS
    and is still open at the capture end. Both FLAG on pump.
  - 1→0 is a −81 dBFS click, 11 ms. It passes.
- *The silent limit is untestable at high gain.* From code 29 up the floor is ≥ −60 dBFS RMS (−51.9 at code 63, peak −39),
  so a −60 dBFS artefact cannot be seen there with this source.
- *Tone: 2 PASS / 68 FLAG* against an instantaneous step. The residual (−10…−43 dBFS) is dominated by the finite
  transition itself (1.5 ms 10–90 %, the 3/8 ms trim ramps). **The limit as written cannot be met by any real change**,
  so the tone flag means "not instantaneous". PW to rule a tone criterion; the dropout below is the candidate.
- *The dropout* (25 of 62 hardware/combined steps). The 1-cycle envelope dips below the quieter code, and the depth
  follows the gain of the AND code:

  | step | AND | predicted | measured |
  |---|---:|---:|---:|
  | 23↔25 | 17 | −1.8 | −1.8/−1.7 |
  | 47↔53 | 37 | −1.6 | −1.6 |
  | 11→13 | 9 | −1.2 | −1.2 |
  | 31↔37 | 5 | −18.0 | −17.4/−17.2 |
  | 15→17 | 1 | −25.7 | −23.2 |
  | 7→9 | 1 | −17.8 | −16.8 |
  | 31→32 | 0 | −46.2 | −36.0 |
  | 15→16 | 0 | −38.6 | −30.5 |
  | 7→8 | 0 | −30.6 | −26.8 |
  | 3→4 | 0 | −22.1 | −18.5 |
  | 1→2 | 0 | −12.8 | −6.5 |

  Deep dips read shallower because they last a few ms and the envelope is one cycle wide. Settle to 0.1 dB: 12–24 ms.
  Down steps mostly dip less than their up twins (4→3 −11.2 vs 3→4 −18.5; 8→7 −18.5 vs 7→8 −26.8; not 2→1 −8.9 vs 1→2 −6.5).
- *Clean steps* are those that only switch bits on or only off (0→1, 2→3, 4→5, 6→7, 9→10 …). 5→6 (AND 4) dips 0.8 dB
  (predicted 1.2), under the 1 dB note.
- *Mechanism.* Bits switching off act before bits switching on. Consistent with S63-2's down delay (9.0 ms) being
  shorter than up (10.5 ms).
- *PW, options, none applied:*
  - (a) sequence multi-bit changes make-before-break: from → (from OR to) → to, the transient goes UP, not to the AND gain;
  - (b) duck the digital trim across the ~25 ms window a multi-bit latch opens (it moves at its own sample, ~9 ms before the preamp);
  - (c) walk multi-bit changes one bit at a time.
  Silence at low gain says only the 0→1 thump is audible without signal; the dropout is audible with signal on any
  multi-bit step.

**S63-4. T3 addendum: THD only, h2..h10, at maximum gain on MIC 5 is −64.3 dB = 0.061 % (h2 −70.7, h3 −71.7 dBc); at code 0 −89.5 dB = 0.0034 %.**
- *Method* (`s63_thd.py`, `s63_thd_analyse.py`): 1 kHz, lane −3.00 dBFS pk (3 dB below clip) at each code; 32
  captures of 16,320 samples (340 cycles, bin-centred, rectangular); coherent average (bins rotated by k × φ1).
- *Floors.* Per-bin **−103.2 dBc at code 63** (single capture −88.0: the 15 dB the averaging bought) and **−154.7 dBc at
  code 0**. Every harmonic clears the floor by ≥ 7 dB (code 63, h9) and ≥ 27 dB (code 0).
- *Code 63:* h2 −70.7, h3 −71.7, h4 −71.8, h5 −77.0, h6 −76.0, h7 −91.3, h8 −77.4, h9 −96.1, h10 −70.7 dBc.
  - Coherent and incoherent averages agree ≤ 1 dB at h2–h6, h8, h10 (h10 phase stable ± 16°): these are the signal's harmonics.
  - 9 kHz carries a non-locked component (−77 dBc incoherent) that the coherent average rejects.
  - No 3 kHz block-rate line stands above the silent floor at code 63.
  - The DAC runs at −61.7 dBFS here, so this figure is preamp + ADC.
- *Code 0:* h2 −102.1, h3 −90.1, h5 −100.5 dBc, the rest ≤ −119. The DAC is at −8.6 dBFS, so this is the whole loop
  (S61 THD+N code 0: −88.96 dB).
- *Trap caught.* The first attempt asked 999.0234 Hz (341 cycles in 16,384). The word read back exact, but the tone fitted
  **1000.0000 Hz**: TEST_OSC does not honour a fractional frequency. The run was off-bin, its level trim chased the leakage
  (lane really −1.37 dBFS pk), and it was discarded (`thd_J25_offbin`, bench only).

**Hand-back (17:46 bench clock).**
- s60 pair (`fe522a7f` / `c56ed0ab`) rebooted twice, `s56_setup.py`, `s60_handback.py` **with** its `R.chain(0)`. That
  restores the S54 image (MIC 5 alone open at code 0), as S61 left it, which this session changed.
- `s60_found.py after_s63` against `found_s63`: **every cell identical**, MIC 5 idle −106.1 dBFS found and after.
- AN_EN `op pd | hi` and CS_M `op pu | hi` before and after, never written (CS_M was driven high/low only inside each
  chain send and left high). `matrix-app` inactive as found. Loop cable still on J25.
- `~/s63` holds the pair, tools and raw data; `~/s60`, `~/s62`, `~/dspboot` untouched.

## THE BULK READ'S STALL: A STRAY WORD IN THE RX FIFO THAT A BUSY HOST NEVER LETS THE FIRMWARE DISCARD; SPI_RDY IS NOW THE HANDSHAKE, 2,000/2,000 AT 0 ms (2026-09-16, session 62 — desk + bench, MW-D24-2)

**Pairs.** Reproduction on the S61 pair (`4a72bd2a` / `d6c763ea`, staged at `~/s62` first). The fix is on the **s62 pair** (`DSP4_TEST_NODES=1`,
chip1 `57948d77…` 458,564 B, chip2 `251ce3b2…` 309,528 B, maps from this build's `map.xml`, staged at `~/s62`), booted and configured
D24 twice (`boot.sh`, CHIP_ID 1/2, TEST_NODES). **Shipping:** `TEST_NODES=0` from the final tree is `36daa238` / `3a9c950d`, 451,892 /
307,980 B, byte for byte S61's shipping build. Every change is inside `#if DSP4_TEST_NODES`. Digital only: the chain, analog and
AN_EN/CS_M were not touched. Unit found: s60 pair with S60/S61's hand-back cells, `matrix-app` inactive, AN_EN `op pd | hi`, CS_M
`op pu | hi`. Tools: `MW/D24/DSP/s62/tools/` (`s62_hammer.py`, `s62lib_prep.py`). Data: `MW/D24/DSP/s62/data/`.

**S62-1. The mechanism: the hand-back's EN cycle inside a host transaction leaves the RX FIFO framed one word out, and only a link that stands still gets repaired.**
*Reproduce.* At stock timing with **0 ms** post-stream wait, 600/600 reads passed. The overlap needs the host's next transaction to be
on the wire during the 1–3 ms in which the tick restores the port, and the stock resync lands there only by chance (S61: 1 in 389).
So `s62_hammer.py HOT=8` clocks NOP transactions for 8 ms right after the stream, with no RDY wait, and the overlap happens every
few streams. **The S61 failure reappeared at stream 7:** the ordinary resync (8 × calibrate) failed with *"cannot phase the parameter
link: MAGIC never came back"* for **4.27 s**. The raw probe that followed, 50 ms of RDY sampling plus a paced MAGIC read, phased at
once (MAGIC at bit offset 0 mod 32, echo correct). **`_spi_partial_fix` had gone from 0 to 2**, so the stuck-partial discard in
`_diag_timer_isr` had fired in that pause. A second run (`STRAT=pause`) failed the same way at stream 55 (4.275 s). **Standing still
10 ms and re-phasing recovered it in 13 ms.** Over those 200 hot streams the discard fired 46 times, almost all of them silently
whenever the host happened to pause. RDY read 100 % high throughout: the part is never stalled.
*Name it.* The part frames requests by **RFIFO full** (two words), not by CS. The restore takes SPI2 EN low, which flushes both FIFOs.
If the host is half-way through a transaction, the words clocked after EN comes back land alone, and from then on every "request" the
part assembles is (the previous transaction's word 1, this transaction's word 0), one word out. The host's own repair,
`SpiLink.realign`, clocks a whole word, so it moves the RX framing and the answer window **together**. The only thing that removes an RX
word without shifting the answers is the firmware's discard. DSP4_SPI_PARTIAL_FIX2 arms that discard only after 3 ticks with
`_spi_rx_count` standing still (the D71 fix). **A retrying host never stands still for 3 ms.** S61's tool polled at 2 ms and retried for
two minutes, and it came back when the traffic stopped. The hub's guess was right about the trigger (the host's next transaction lands
while the tick hands the port back, with no GO-ack). The slip is an RX framing slip, and "until something resynchronises" means until
the host goes quiet for ≥ 3 ms. That calibrate's word realign never converges on its own is inferred from the 4.27 s failure, not
traced word by word. While the stream is framed one out, the part dispatches host words as writes, (0, request word) being a write to
address 0 = Chan001Gain001. That is also inferred and was not read back.
*Also seen, benign:* after the same overlaps the collect windows sit in the D74 POST arrangement, or in a third one that
`calibrate` rejects once and then fixes with its own realign. In the 19 `full` study records the stock reader (calibrate, then MAGIC and CHIP_ID read back) phased every one within 14 ms
(`stuck_study` records).

**S62-2. The fix at the protocol level: SPI_RDY carries the port's owner, and the tick will not cycle EN while anything clocks.**
*Firmware* (`src/bulk_read.asm`, `_spi_poll` in `src/main.asm`; TEST_NODES only):
- While ARMED, `_bulk_rdy_pre` takes PB_05 to **GPIO LOW before the drain**. Flow control's own low (RFIFO full) therefore runs
  straight into it, with no high glitch between GO landing and GO being decided.
- GO arms the stream and drives RDY **HIGH = "clock the stream now"** (the GO-ack). Any other request hands the pin back to flow control.
- On the first quiet tick (DMA stopped, TFIFO empty) the pin goes **LOW = "stream over, port busy"** and TUR is cleared.
- **The guard:** on each later tick a TUR (clocking an empty TFIFO) restarts the count (`_bulk_tur_holds`). The EN cycle happens only
  after 3 whole ticks of silence on the wire. Then RX comes back and the pin returns to SPI2_RDY flow control: **HIGH = released**.
  Every host transaction already waits for RDY high, so none starts during the hand-back. The guard covers the one that sampled RDY
  just before it fell, and a host that ignores RDY entirely.
- `_bulk_rdy_hs` in the map tells the host the handshake is there.
*Host* (`tools/pi/dsp4_bulk.py`):
- After GO, wait for RDY high (was: sleep 3 ms).
- After CS rises, look up to 50 ms for the release low, then wait for high, **before** parsing (parsing 16k words outlasts the low).
  Was: sleep 30 ms.
- `rephase()`: the ordinary resync proved by a MAGIC read. If that fails, stand still 10 ms, calibrate once and prove again, bounded at
  **1 s**. It never waits minutes.
- Images without `_bulk_rdy_hs` keep S61's 3 ms / 30 ms. `dsp4_meascap` picks all of this up unchanged.
*Adversarial proof on the s62 pair, 16k reads at 10 MHz:*

| run | host behaviour across the hand-back | reads | wrong | retries | re-phases | TUR holds | discards |
|---|---|---:|---:|---:|---:|---:|---:|
| smoke | stock | 30 | 0 | 0 | 0 | 0 | 0 |
| HOTRDY=8 | 18–28 NOPs, each honouring RDY | 300 | 0 | 0 | 0 | 0 | 0 |
| HOTRAW=8 | 41–52 raw NOPs, **no RDY wait** | 300 | 0 | 0 | 0 | 2,645 | 1 |

The one discard in HOTRAW is a raw NOP that ignored the handshake and still straddled a restore after a ≥ 3 ms gap in its own traffic.
The firmware repaired it silently and no read failed. A host that honours RDY cannot produce it.

**S62-3. Proof: 2,000 reads at 0 ms extra wait, 0 errors, 0 slips; a read is faster than S61's.**
Gate 3 (`s62_gate3.jsonl`): a real chirp capture (strip 6, −20 dBFS pk, TEST_MEAS buffer, 16,383 non-zero words) was made static, a
reference was read by PEEK (15.9 s, sum `48f355ac/2dfb1207`), then 2,000 bulk reads were each compared **word for word** with it:
**2,000 ok, 0 different, 0 failed, 0 retries, 0 re-phases, 0 release timeouts**. Over the run BULK_ABORT, BULK_ERR, SPI_ERR_COUNT and
RESP_DROP stayed 0, and the discard counter and TUR holds did not move. 452.7 s wall.

| | S61 (30 ms wait) | S62 handshake |
|---|---:|---:|
| GO → clock | 3 ms sleep | GO-ack median **0.03 ms**, max 0.18 |
| stream end → next transaction | 30 ms sleep | release median **1.76 ms**; 37/2,000 (1.9 %) missed the low and took the 50 ms look |
| 16k read, median / p99 | 0.278–0.281 s | **0.220 / 0.289 s** |
| digital capture step (arm + fill + read, `s62lib_prep.py`, 11×) | ~0.5 + 0.25 s | **0.70 s** median (read 0.22), 0 overruns |

Fast battery: S61-3's 26.5 s a channel carried 11 reads at ~0.25 s, and a read is now ~0.22 s, so **≈ 26.2 s a channel**. That is
unchanged or better, and the rest of the channel is stimulus and settle. Not re-run on MIC 5, because this dispatch kept the chain and
the analog path untouched.
*A test trap caught in-session:* the first gate-3 attempt used `_spi_dispatch_c1_spms`, the region the reproduction runs streamed, and
its peek reference is **1 non-zero word in 16,384**. A word slip over zeros passes both sums. Gate 3 was stopped and re-run on the
capture buffer. The reproduction runs are unaffected: they detected stalls, not data.

**Hand-back (17:02 BST):** s60 pair rebooted twice (`fe522a7f` / `c56ed0ab`, CHIP_ID 1/2), `s56_setup.py`, then `s60_handback.py`
**without its `R.chain(0)` line** (chain untouched), then `s60_found.py after_s62` against this session's `found_s62` snapshot:
**every cell identical** (`s62_found_after.json`). MIC 5 idle read −104.9 dBFS found and −106.3 after. AN_EN `op pd | hi` and CS_M
`op pu | hi` were read before and after and never written. `matrix-app` inactive as found. `~/s62` holds the handshake pair and tools;
`~/s61`, `~/s60`, `~/s56` and `~/dspboot` are untouched.

## THE CAPTURE READOUT: A DMA STREAM ON THE PARAMETER PORT, 16,384 WORDS IN 0.28 s, 0 ERRORS IN 700; THE FAST BATTERY IS 26.5 s A CHANNEL (2026-09-16, session 61 — desk + bench, MW-D24-2)

**Pair:** `s61` (`DSP4_TEST_NODES=1` + `src/bulk_read.asm`; chip1 `4a72bd2a…` 458,304 B, chip2 `d6c763ea…` 309,284 B), staged at
`~/s61`, booted and configured D24 twice (`boot.sh`, CHIP_ID 1/2, BUILD_CFG2 = TEST_NODES). **Controls, same session:** HEAD built
`TEST_NODES=1` reproduces s60 byte for byte (`fe522a7f` / `c56ed0ab`), and `TEST_NODES=0` builds of HEAD and of this tree are
identical (`36daa238` / `3a9c950d`, 451,892 / 307,980 B), so **the shipping image does not change.** Unit found: s60 pair running with
S60's hand-back cells, `matrix-app` INACTIVE (not restarted, as the dispatch expected), AN_EN `op pd | hi`, CS_M `op pu | hi`. The
chain was set by spidev at send position 15 (`s54lib.chain`), not `app cli chain-set`, because the app was not running.
Data: `MW/D24/DSP/s61/data/`. Tools: `MW/D24/DSP/s61/tools/`, `tools/pi/dsp4_bulk.py`.

**S61-1. Where the 12 s went: three transactions a word, ~100 us each, and the floor is not the SPI clock.**
`s61_gate1.py` (read-only; 2,000 NOP transactions, 300 ask/collect pairs, 1,000 peeks of the capture buffer at each clock):

| SCLK | RDY wait | CS lo + hi (gpiod) | spidev xfer2, 8 B | one transaction | answer on collect # | peek | words/s |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 MHz | 91 us | 19 us | 138 us | 250 us | 1 (300/300) | 750 us | 1,333 |
| 4 MHz | 87 us | 17 us | 38 us | 141 us | 1 | 429 us | 2,334 |
| 8 MHz | 59 us | 17 us | 23 us | 100 us | 1 | 300 us | 3,331 |
| 10 MHz | 62 us | 17 us | 20 us | 100 us | 1 | 300 us | 3,333 |

The bench link ran at 1 MHz, which is S60's 1,330 words/s exactly. The SHARC answers every ask on the very next collect, so the
dispatch handler is not the cost. A peek is three transactions (write PEEK_ADDR, ask PEEK_DATA, collect). Above 8 MHz one
transaction is ~100 us: the SPI_RDY poll plus the kernel's per-ioctl cost, whatever the clock. **Word-at-a-time tops out at
~3,300 words/s, 5 s for 16k. The ≥ 16k words/s target needs a stream,** and on this port that is possible without a second SPI, the
CPLD's PCM lane or the S49 Pi lane.

**S61-2. The bulk read: SPI2's transmit path handed to DMA26 for one region, 0 errors in 700 16k captures at 10 MHz.**
*Firmware* (`src/bulk_read.asm`, diag registers 0xE0D0..0xE0D9, `DSP4_TEST_NODES` builds only): BULK_ADDR / BULK_LEN, then
BULK_CTL = 1 arms it and the 1 kHz tick checksums the region, 1,024 words a tick. BULK_CTL reads 2 when that is done. BULK_SUM1/2
carry s1 = Σw and s2 = Σs1, both mod 2^32. BULK_CTL = 2 is GO and is **not answered**. GO takes SPI2 EN low and back (flushing both
FIFOs), turns RX off so the host's MOSI filler is never dispatched (a zero pair is a write of Chan001Gain001 = 0), pushes a header
(0xB0CA5E61, LEN) into the TFIFO and arms DMA26 from its registers with FLOW = STOP (the arming that works on this part,
dma_config.c) at TDR = not-full. `_spi_poll` stands aside while streaming. The tick gives the port back when the channel's RUN is 0
and the TFIFO is empty on two ticks running. There is also a 3 s abort. BULK_RUNS / ABORT / ERR / DSTAT / MS are readable after.
Idle cost: one load and compare in the tick and one in `_spi_poll`. No cell, no contract change.
*Host* (`tools/pi/dsp4_bulk.py`; `dsp4_meascap.capture` uses it whenever the map carries `_bulk_state`, and `DSP4_BULK=0` forces
peeks): write-verify ADDR/LEN, arm, wait for 2, read the sums, GO, sleep 3 ms, CS low, **one `xfer3` of (n + 10) words at 10 MHz**,
CS high, find the header at any byte offset (seen at bytes 0 and 4), check both sums, wait 30 ms, resync the link, confirm that
BULK_CTL = 0 and RUNS moved, and retry up to 3 times on any failure.
*The error check, and it can fail:* reference = the same 16,384-word chirp capture read by PEEK (12.3 s, 16,383 non-zero words).
Every bulk read is compared with it word for word as well as by the sums. **1 MHz** 5/5 (1.01 s). **8 MHz** 100/100 (0.306 s).
**10 MHz 100/100 + 500/500 (0.278–0.281 s median, 58–66 k words/s)**. 12 MHz 20/20 (0.211 s). 14 MHz 20/20 (0.201 s).
**16, 20, 25 MHz: 0/20 each, every one caught** (60 attempts per clock, all rejected at the header, bit-corrupted e.g. `f8ef7f71…`:
the MISO path's timing edge). Against the reference with synthetic faults the sums caught 2,000/2,000 each of single-bit flips,
adjacent swaps, a dropped word, a one-word shift and a stuck word (`s61_sumcheck.out`). **Clock: 10 MHz, 1.6× below the first
failing step.** A 16k read spends 0.067 s arming (voted writes + 16 ms of checksum), 0.10 s streaming (52 ms of clocking), 0.03 s
waiting and ~0.08 s resyncing and verifying.
*One real failure, and the fix.* With a 4 ms post-stream wait, stream 389 of 1,118 left the parameter link unphaseable. The next 67
reads failed at the ADDR write and `dsp4_diag` could not phase chip 1 either. It came back by itself within ~2 min. The part had
**not** reset (TICKS in step with chip 2, RUNS = 388, ABORT 0, ERR 0). The tick gives the port back 97–101 ms after GO at 10 MHz, i.e.
1–3 ms after the host's last clock, and later when a block delays the tick (that stream's BULK_MS was 121). So the host's resync
overlapped the EN cycle. **With 30 ms: 0 failures in the following 700.** How a mid-transaction EN cycle keeps the link out of phase
for minutes, when CS frames every transaction, is NOT explained. A GO-ack on SPI_RDY would replace the fixed wait. Not needed for the
gate; noted here.

**S61-3. The fast battery re-timed on MIC 5: 26.5 s a channel (was 170 s), and the captures reproduce S60.**
`s61_loop.py` = `s60_loop.py` with the bulk readout, same loop (strip 6 TEST_OSC → AUX 1 → J45 → cable → J25 → MIC 5), level first,
1 s settle, ref + 8 codes (0 and 63 twice) + 2 THD+N + EIN: **29 s wall for all 14 captures, 0 overruns, reads 0.25–0.28 s.**
S60's analysis run unchanged on these captures (`s61_analyse.py`, `data/analyse.out`): gain law within **0.026 dB** of T1 at all 8 codes
(worst code 63 +0.026, code 32 −0.013). Latency 1–2 kHz **91.398–91.469**, inverted at every code. Chirp − tone ≤ 0.004 dB at code 0
and ≤ 0.082 dB at code 63. THD+N code 0 **−88.96 dB**, code 63 **−47.05 dB**. EIN (loop source) −52.25 dBFS. S60 read 91.398–91.461,
−89.02 / −47.23 dB and −52.4 dBFS.

| step | count | each, s | total, s |
|---|---:|---:|---:|
| chirp: osc words 0.05 + chain 0.17 + settle 1.0 + 1.2 periods 0.41 + arm/fill ~0.5 + **read 0.25** | 8 | 2.46 (2.28–2.69) | 19.7 |
| THD+N tone capture | 2 | 1.89 | 3.8 |
| EIN capture | 1 | 1.87 | 1.9 |
| analysis, desk numpy (CM4 stdlib 1.2 s) | 11 | 0.1 (1.2) | 1.1 (13.2) |
| **per channel** | | | **26.5 s desk analysis; 38.6 s CM4 analysis** |

**Readout is now 2.8 s of the 25.4 s of acquisition (11 %)**. The rest is the stimulus and the analog path: the 1 s settle
(S60-3), the 1.2-period wait and arm/fill. On the CM4 the stdlib analysis (13 s) is now the largest item.
**24-channel projection.** *Manual cable:* 24 × 26.5 s = **10.6 min of instrument time** (15.4 min with CM4 analysis), plus the cable
moves. At ~30 s a move that is ~23 min. *Harness* (every lane driven, all registers at one code, S60-4's read-all-lanes): per code,
chain + settle 1.2 s once, then per lane strip up 0.20 + 1.2 periods 0.41 + arm/fill ~0.5 + read 0.25 + restore 0.19 ≈ 1.55 s, so
8 codes × (1.2 + 24 × 1.55) = **5.1 min**. Add 72 THD+N/EIN captures ≈ 1.9 min and desk analysis 264 × 0.1 s = 0.4 min:
**≈ 7.5 min a unit** (was ≈ 62 min). The dispatch's ≈ 2 min harness figure assumed the settle and fill could be shared across
lanes. Arm/fill cannot be shared as TEST_MEAS captures one strip at a time, so a multi-lane capture arm is the next lever there.

**Hand-back (16:23 BST):** s60 pair rebooted twice (`fe522a7f` / `c56ed0ab`, CHIP_ID 1/2), `s56_setup.py` + `s60_handback.py`, then
`s60_found.py` against this session's found snapshot. Every cell and the S58 patch are identical. The two differences are CaptureReady
(16,384 found, 0 now: a status word, zero after a boot) and `sym_osc_ch` (the found snapshot ran without SYMDIR, on s54lib's default
s51 map). Idle MIC 5 noise read −90.1 dBFS just after the hand-back and settled to −106.3 within a minute (S60 found −106.0, S61 found
−113.6: it wanders between sessions). AN_EN `op pd | hi` and CS_M `op pu | hi` before, during and after, never written. `matrix-app`
inactive as found. Loop cable still on J25. `~/s61` holds the bulk pair and tools. `~/dspboot`, `~/s56`, `~/s60` images untouched.

## CHIRPS INSTEAD OF TONES: ONE CAPTURE PER CONDITION, VALIDATED AGAINST THE TONE SET ON MIC 5; 10 kHz CROSSTALK; THE FAST BATTERY IS 2.6 MIN A CHANNEL, 85 % OF IT READOUT (2026-09-16, session 60 — desk + bench, MW-D24-2)

**Pair:** `s60` (`DSP4_TEST_NODES=1`, no tap; chip1 `fe522a7f…`, chip2 `c56ed0ab…` = the s56/s51 chip 2 byte for byte), staged at `~/s60`,
booted and configured D24 twice (`boot.sh`, BOOT OK, CHIP_ID 1/2). It is s56 plus the chirp. The build recipe reproduced s56's chip 1
(`314ce05f`) before the change. The shipping build (`TEST_NODES=0`) is still 451,892 B / 307,980 B. **Loop:** TEST_OSC on donor strip 6 →
AUX 1 → J45 → cable → J25 → MIC 5 → U39 → strip 5 (S58 patch, read on the part). MIC 5's register alone open (send p15, spidev,
every image verified). AN_EN `op pd | hi` before, during and after, never written. Data: `MW/D24/DSP/s60/data/` (captures + jsonl +
`analyse_final.out`, `results_s3.json`). Tools: `MW/D24/DSP/s60/tools/`.

**S60-1. TEST_OSC has a periodic log-sweep mode on the two existing Sweep cells, and every period is the same 16,384 samples.**
*Cells (no new cells, no address moves):* `Test[1-1]SweepOn[1-1]` (4979) = 1 runs the chirp on OscChan at OscLevel (peak, linear) with
OscOn 1. `Test[1-1]SweepStep[1-1]` (4980) = the period in units of 1,024 samples; 0 = 16 = 16,384 samples = 341 ms, one capture.
OscFreq is ignored while the chirp runs. The S49 stepped sweep that used these words is retired: S49 recorded that the link cannot
follow it, and no tool used it. The description text is proposed in `proposals/CONTRACT-PROPOSAL-S60.md` (descriptions only).
*Method (generator `tools/dsp/dsp_codegen.py::gen_test_osc`):* phase `p` in cycles, `sin(2πp)` by folding into the first quarter cycle
and the resonator design's own degree-13 Taylor. The increment starts at 20/48000 and is multiplied every sample by
`r = 1000^(1/L)`, taken from a 256-entry table the generator emits from the OscFreq law's endpoints. Phase and increment reset at each
period boundary. The capture arm (`gen_test_meas`) now starts a run only on the pass that injects a period's first block (three
instructions, only while the chirp is live), so capture sample 0 is sweep sample 0. TEST_MEAS's fit reference is zeroed during a chirp.
*Measured on the part (digital, strip 6 post-fader, −20 dBFS):* two captures 13 s apart are **identical in 16,384 of 16,384 words**,
0 overruns. **Cost +732 / +791 cycles per chip-1 pass** against the tone, interleaved exact TCOUNT (medians 214,488 vs 213,756, and
214,856 vs 214,065), **0.24 % of 327,680**, +0 overruns. **Two things that did not work, both recorded:** (a) the ratio table
first went into `seg_delay` (L2, beside the capture buffer) and read back 0.0 on the part, so the sweep froze after one sample:
**`seg_delay` is not loaded with `.var` initial values**. The table now lives in L1 DM, a net +128 words since the stepped sweep's
128-entry frequency table is gone. (b) A float64 host model of the kernel drifts from the part along the sweep (−67 dB error in the
first eighth, worse than the signal by the last eighth, about 4 samples late at 20 kHz). The part keeps 40-bit registers inside a block
and 32-bit state between blocks, and no simple float32/rounding emulation reproduced it. **So the "known sweep" is a capture of the
donor strip's post-fader block** (`ref_strip6_m20.json`), which is bit-exact because the sweep is periodic. It is taken once and scaled
by OscLevel. Against that reference the digital path deconvolves to latency 0, gain −0.003 dB, flat.

**S60-2. `dsp4_fft.py --chirp` (new `tools/pi/dsp4_chirp.py`), validated on MIC 5 against the tone set: every criterion met.**
*Analysis:* `R = Y·X*/(|X|²+ε)` over one period, which is Farina's inverse filter in the frequency domain and exact for a periodic
excitation. Impulse `h` = band-limited inverse. **Latency** is reported three ways: the phase-slope fit over 1–2 kHz (S54's T8
definition), over 1–10 kHz, and the interpolated impulse peak. **Polarity** is the sign at the peak. **Response** is |R| as a power
mean over a 1/48-octave band around each point (two-bin interpolation below ~140 Hz), re 1 kHz. **THD 2..5**: harmonic k's impulse
sits L·ln k/ln 1000 earlier; it is windowed from a 500 Hz high-passed `h` (without the high-pass, the 20 Hz band edge's ringing set a
−61 dB floor) and read at k·1 kHz. **SNR** comes from two captures ((y1−y2)/√2). Selftest (synthetic delay 91.4, inverted, gain,
x²/x³ terms): latency ±0.001 samples, response ±0.005 dB, h2/h3 ±0.03 dB, PASS. Runtime **1.2 s per capture on the CM4, stdlib**.
*Chirp level:* lane −10 dBFS peak at every code (osc = −10 − G_T1). Codes 0–32 come from the 3 s-settled run and code 63 from
the level-first run (S60-3):

| code | gain 1 kHz dB | − T1 | latency 1–2 k / 1–10 k / peak, samples | polarity | 20 Hz re 1 k | 20 kHz re 1 k | THD 2..5 @ lane −10 pk | SNR @ 20 Hz |
|---:|---:|---:|---|---|---:|---:|---:|---:|
| 0 | +5.578 | +0.000 | 91.398 / 91.618 / 92.084 | inverted | −0.418 | −0.117 | −97.8 dB = 0.0013 % | 97.4 dB |
| 1 | +18.423 | +0.000 | 91.409 / 91.629 / 92.094 | inverted | −0.420 | −0.119 | −93.9 dB = 0.0020 % | 83.6 dB |
| 2 | +25.041 | −0.000 | 91.411 / 91.630 / 92.096 | inverted | −0.422 | −0.118 | −83.6 dB = 0.0066 % | 78.9 dB |
| 4 | +32.474 | −0.001 | 91.413 / 91.631 / 92.097 | inverted | −0.433 | −0.117 | −74.0 dB = 0.020 % | 72.5 dB |
| 8 | +39.930 | +0.003 | 91.417 / 91.632 / 92.097 | inverted | −0.473 | −0.120 | −67.0 dB = 0.045 % | 64.4 dB |
| 16 | +47.168 | −0.001 | 91.424 / 91.634 / 92.097 | inverted | −0.606 | −0.124 | −58.8 dB = 0.115 % | 63.5 dB |
| 32 | +53.749 | +0.005 | 91.437 / 91.637 / 92.099 | inverted | −1.086 | −0.103 | −57.4 dB = 0.135 % | 50.3 dB |
| 63 | +58.718 | +0.001 | 91.461 / 91.641 / 92.099 | inverted | −2.123 | −0.108 | −48.3 dB = 0.385 % | 50.3 dB |

**Gain law at the eight factory codes: within 0.005 dB of T1** (criterion 0.05). **Response vs the S54 tone points** (chirp − tone,
dB, at 20 / 50 / 100 / 1 k / 10 k / 20 k Hz): **code 0** −0.004 / +0.001 / −0.000 / 0 / −0.001 / −0.000. **Code 63** −0.063 / −0.058 /
+0.015 / 0 / +0.016 / +0.005. Every point is within 0.1 dB (criterion). **Latency 91.398–91.461 samples on the 1–2 kHz fit**, within
91.4 ± 0.1 at every code, rising 0.06 samples from code 0 to 63 (the LF corner moves with gain, S54-4). The path's group delay is not
constant with frequency: 1–10 kHz reads 91.62–91.64, and S54's own 1–10 kHz tone fit read 91.596. The impulse peak is 92.08–92.10.
Quote the 1–2 kHz figure as T8. **Polarity inverted at every code.** **SNR at 20 Hz for this level: 97.4 dB at code 0, 50.3 dB at
code 63.** At code 63 the limit is the loop's source, not the method: AUX 1's output noise × 58.7 dB puts the lane at −52.4 dBFS
(20 Hz–20 kHz, tone off, `ein_s3_c63_loopsrc`). With a single-bin readout that scattered 10–20 kHz by up to 0.2 dB, and the
1/48-octave band readout fixes it. A 150 Ω or factory source would lift the code-63 SNR by about 35 dB. The THD column is the check
figure the dispatch asked for, at the chirp's instantaneous lane level. It rises with gain as the tone T3 does, and at codes ≥ 16 it is
noise-limited. THD+N tone captures (FFT method, 1 kHz, lane −3 dBFS pk): **code 0 −89.02 dB = 0.0035 %** (THD 2..10 −89.59 dB),
**code 63 −47.23 dB = 0.435 %** (THD −60.92 dB; S54 −47.05 dB = 0.444 %).

**S60-3. Change the stimulus level BEFORE the gain code, or the preamp's coupling caps pump a DC offset into the next capture.**
In the first two runs, code 63 was switched in while the code-0 stimulus (osc −15.58 dBFS chirp; −8.58 dBFS tone) still played, i.e.
the preamp was driven about 40 dB into clipping for the settle time. The next capture carried a decaying offset: +0.05 FS at sample 0,
τ ≈ 0.3 s (+0.3 FS on the THD+N tone capture), still there after a 3 s settle, because the recovery starts only when the level drops.
The damage is at 50 and 100 Hz (chirp − tone +0.14 / −0.13 dB) and in the capture-to-capture difference (−16 dB re signal). **Level
first, then code, then 1 s settle:** no offset, and capture 1 equals capture 2 to the noise (−37.5 dB re signal = the loop source
noise). Ascending codes 1 → 32 were never affected, since the previous level leaves the lane at −2.5…−3.4 dBFS peak at the next code.
`s60_loop.py` now orders it that way. Any battery or harness must too.

**S60-4. T7 at 10 kHz, and the fast battery's timing.**
*T7 (supersedes the 1 kHz figures of S54/S55):* S54's coherent method at 10 kHz, MIC 5 register alone at code 2 (as S54), loop gain
+25.101 dB, osc −31.10 dBFS, MIC 5 strip coherent peak −6.00 dBFS. Each of the other 22 strips was brought to unity in turn and put
back. **Worst neighbour: strip 17 = J26 (MIC 17, same converter U39) at −133.06 dB.** Next are strips 11 (J39) −136.40 and 22 (J38)
−136.44. The control on strip 17 (reference running, OscChan 0) reads **−144.18 dB**, so strip 17 sits 11 dB above the detector's floor
and the rest within 0–9 dB of it. 22 strips took 24 s. The 1 kHz worst in S54 was −131.37 dB.
*Fast battery, measured per channel* (link times on this bench; a 16,384-word read took 12.3 s in most runs and 15.2–16.4 s in some,
with no change on the part):

| step | count | each, s | total, s |
|---|---:|---|---:|
| chirp: osc words 0.05 + chain 0.17 + settle 1.0 + 1.2 periods 0.41 + arm/fill ≤ 0.7 + read 12.3 | 8 | 14.4 (18.5 slow read) | 115 (148) |
| THD+N tone capture: osc 0.05 + chain 0.17 + settle 1.0 + fill 0.4 + read 12.3 | 2 | 14.0 | 28 |
| EIN capture (tone off, code 63) | 1 | 14.3 | 14 |
| analysis (CM4 stdlib 1.2 s; desk numpy ≈ 0.1 s) | 11 | 1.2 | 13 |
| **per channel** | | | **≈ 170 s = 2.8 min (≈ 3.4 min with slow reads); on-desk analysis 2.6 min** |

**85 % of that is readout**: 11 × 12.3 s. The diag link answers one transaction per audio block, and a peek is two, about 1,330
words/s. A bulk read of the capture buffer would bring the channel to about 30 s.
*Read-all-lanes (harness: every register at the same code, all 24 lanes driven):* measured per lane, strip up 0.20 s + capture
13.6–17.5 s + restore 0.19 s ≈ 14 s, so **24 lanes × 8 codes = 45 min**, plus 72 THD+N/EIN captures ≈ 17 min, **≈ 62 min a unit**.
The meter instead (strip up + one TEST_MEAS window 0.23 s + restore) is 0.62 s a lane, 15 s a code, **2 min for 8 codes**. That gives
the 1 kHz coherent gain only, not the response. With a bulk capture read the chirp harness would be about 24 × 8 × 1.5 s ≈ 5 min.

**Hand-back (15:51 BST):** the `s60` pair is left running (a superset of s56: the same chip 2, and chip 1 = s56 + the chirp). Read back
through `s60_found.py handback` against `s60_found.jsonl` "found": TEST_OSC off (1 kHz, 0.1, OscChan 6), SweepOn 0, SweepStep 1,
MeasChan 5, CaptureArm 0. Strip 6 off AUX 1 (AuxSend 1.0 as found), CompOn/MainOn 0. Strips 5, 6 and 20 unmuted, the rest muted.
S58 input patch on the part. MIC 5 at code 0, phantom off. AN_EN `op pd | hi`, CS_M `op pu | hi`, neither written. matrix-app
inactive as found. Loop cable still on J25. `~/dspboot` and `~/s56` untouched.

## THE INPUT PATCH BECOMES GENERATED: defs .5 CONSUMED, `gen_input_patch.py` LANDS, THE HAND-TYPED TABLE RETIRED (2026-09-16, session 59 — desk, no unit)

**Consumed:** `defs-v2026.09.16.3/.4/.5` in one jump from the pinned `.2` (mic-gain-law table, `Test[1-1]CaptureArm/CaptureReady`,
`products/d24/inputs.csv`). `./regenerate-dsp-contract.sh --update-lock` then `./check-contract-drift.sh --strict`, clean after
committing the regenerated artefacts (the script dirties the tree by design; see `[[contract-drift-script-dirties-tree]]`).

**S59-1. D24/D32 gain exactly two cells, `Test001CaptureArm001`/`Test001CaptureReady001` at `4981`/`4982` (`0x1375`/`0x1376`), 0 other
columns changed, 0 addresses moved.** `validate-matrix-contract.py --update-allowlist` adopted the two new families
(`TestCaptureArm`/`TestCaptureReady`) intentionally, per the no-fallback policy — this is the CaptureArm/CaptureReady landing the
matrices were expected to gain, not an unreviewed family. `MW/D32/DSP/gen_dsp.py::expand_test_osc` now calls `add_cell` for both
(previously dispatch-only, "no cell" — S56's proposal text said the masters didn't name one; `defs-v2026.09.16.4` landed them, so
the generator now maps them at the same address the dispatch symbol already used). Verified against `defs/products/{d24,d32}/dsp.csv`
(landed contract copy): `check-proposal OK — the graph reproduces the landed dsp.csv / dsp-unmapped.csv exactly for d32, d24`. D12/D16
row counts moved by the same +2 (they carry no DSP address, unbackfilled). The rest of the matrix diff (Notes text on every
`Chan*Gain001` cell, `.3`'s mic-gain-law reference) is the S55 table proposal landing, not S59's own change — noted so the diff isn't
mistaken for drift.

**S59-2. The D24 input patch is generated, not typed — byte-identical to the S58 landed array.** New `tools/dsp/gen_input_patch.py`
(shared by all products): reads `defs/products/<p>/inputs.csv`, resolves each row's `rx_cell` to its PACKED RX INDEX the same way
`dsp_codegen.py::gen_block_io` assigns one — INPUT_TDM nodes off the shared `MW/D32/DSP/SHARC/dsp.csv`, sorted `(sport_id,
slot_start)`, enumerated — not by re-deriving "8 × AD + slot" (that only happens to hold because every INPUT_TDM node today has
`slot_count=1`). Validates every row (rx_cell exists and is INPUT_TDM; its graph `(sport_id, slot_start)` matches the row's
`(sport_id, tdm_slot)`; `tdm_slot == ain-1`; `send_pos == 24-chain_index`; `strip` in range and `strip`/`rx_cell`/`xlr`/`chain_index`
each unique) and fails loudly on any violation. Emits `MW/<P>/DSP/input_patch.json`. GATE:

```
$ python3 tools/dsp/gen_input_patch.py --product d24 --check \
    "3,15,2,14,13,1,12,0,7,19,6,18,17,5,16,4,11,23,10,22,21,9,20,8,24,25,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40,41,42,43,44,45"
d24: generated patch matches landed, 46 entries
```

`tools/pi/dsp4_config.py`'s hand-typed `D24_INPUT_PATCH` (the literal 46-entry array S58 landed) is deleted; the name now loads
`MW/D24/DSP/input_patch.json` (staged next to the tool on the Pi, like `landed-d24.json`; falls back to the repo-tree path for
dev/`--dry-run`) and is otherwise unchanged in shape (still a 46-entry tuple of ints at module scope). D32/D16/D12 have no
`inputs.csv` and get no file — identity, as before (`_load_input_patch` returns `None`, no key added to `PRODUCT_CONFIG`).
`tools/pi/d24_inputs.py`'s public API (`strip()`, `xlr_on()`, `MIC5_STRIP`, `PRE_S58_PATCH`, `check()`) is unchanged and its
`check()` still passes; confirmed by import (`MIC5_STRIP = 5`, `strip('J25') = 5`, `xlr_on(5).xlr = 'J25'`). Every file that
imports `D24_INPUT_PATCH` or `d24_inputs` (`s52lib.py`, `s54lib.py`, `s55_run.py`, `s55_ingest.py`, `s58_prove.py`, `dsp4_s48_scan.py`
and the rest of the S54/S57 tree) only slices, sorts or `list()`s the value — none mutate it or depend on it being a literal —
so the tuple-from-JSON is a drop-in. Every S48/S52/S54–S58 tool that touches either module `python3 -m py_compile`s clean; a live
IMPORT check on most of them stops at a Pi-only path (`/home/app/dspboot/landed-d24.json`, `/home/app/dspboot` itself) that this
desk cannot reach — a pre-existing constraint of the bench-deployment layout, not something S59 changed.

**Regenerate flow updated:** `regenerate-dsp-contract.sh` and `check-contract-drift.sh` both call
`tools/dsp/gen_input_patch.py --all` after `gen_dsp.py --force`; `MW/D24/DSP/input_patch.json` joins the strict-mode contract
file list. `CONTRACT-PROPOSAL-S56` and `CONTRACT-PROPOSAL-S58` marked LANDED with their tags (`defs-v2026.09.16.4` /
`.5`) in place.

## THE D24 INPUT PATCH IN NETLIST ORDER: MIC 5 ON STRIP 5, EVERY MEASURED XLR ON ITS PANEL STRIP (2026-09-16, session 58 — desk + bench, MW-D24-2)

**Pair:** `s56`, as S55 handed it back; nothing rebooted or flashed. AN_EN (`op pd | hi`) read at start and end, never written.
**Loop:** PW's cable J45 → J25 (MIC 5), TEST_OSC 1 kHz −20 dBFS pk on donor strip 6 → AUX 1 (MainOn/CompOn 0), MIC 5's register
as found (send p15 open, code 0). **No 595 write at all** (the tone was present, so the code-63 floor fallback did not run).
Data `MW/D24/DSP/s58/data/` (`s58_prove.out/.json`, `s58.jsonl`); tool `MW/D24/DSP/s58/tools/s58_prove.py`. (In `s58_prove.out` the XLR names printed beside the pre-S58 and identity scans
were looked up through the new patch — "20 (J32, rx 15)" is rx 15 = J25; the rx numbers are right, and the tool now labels by rx.)

**S58-1. Landed and proven: `D24_INPUT_PATCH` = `[3,15,2,14,13,1,12,0] + [7,19,6,18,17,5,16,4] + [11,23,10,22,21,9,20,8]` + identity.**
Written live to INPUT_PATCH[0..45] + CONFIG_COMMIT on the running pair. Raw RX peak of the tone, three scans per patch, strips 1–24:

| patch | tone on strip | peak dBFS | next strip |
|---|---:|---:|---|
| as found (pre-S58 half-frame; `_c1_rx_node_entry` = its inverse, verified) | 20 | −14.43 | 18 at −99.39 |
| **S58 netlist order** (`node_entry` = `[7,5,2,0,15,13,10,8,23,21,18,16,6,4,3,1,14,12,11,9,22,20,19,17]` = its inverse) | **5** | −14.45 | 6 at −103.99 |
| identity (comparison) | 16 | −14.43 | 24 at −101.45 |
| S58 re-applied | **5** | −14.45 | 7 at −102.63 |

TEST_MEAS on strip 5 (made transparent, off every bus): RmsResult −17.43 dBFS, ThdResult −87.9 dB, coherent peak −14.42 dBFS —
the S52 figures for MIC 5 at code 0 on strip 20 (−17.43 / −87.6). Strip 20 (now J32, no cable): −114.04 dBFS. Strip 16 (now J22,
U15 section unpowered): exact digital zero. The S58 patch is left applied on the part and staged for boot
(`~/dspboot` and `~/s56` `dsp4_config.py`, old copies `*.bak-2026-09-16-pre-s58`). `product-config.md`'s "verify the within-ADC8
slot order" note is discharged with these numbers.

**S58-2. Every channel S55 measured now resolves to its panel strip — read off the part, not assumed.** For each of the 16 XLRs S55
detected (U39 + U60), the RX entry the part resolved for its S55 lane under the old patch equals the entry the part now resolves for
its panel strip, and both equal the netlist slot (8 × AD + slot): J25 20→rx15→5, J26 19→14→17, J27 18→13→6, J28 17→12→18,
J29 7→10→7, J30 8→11→19, J31 5→8→8, J32 6→9→20, J35 24→23→9, J36 23→22→21, J37 22→21→10, J38 21→20→22, J39 11→18→11,
J40 12→19→23, J41 9→16→12, J42 10→17→24 — 16/16. This is the U60 proof the gate asked for (J41 → strip 12, J35 → strip 9): only
J25 is cabled, so the other 15 are proven through S55's tone detections plus the part's own tables. U15 (J15–J22) is unmeasured.

**S58-3. The dispatch's expectation "strip 16 = C1_IN_16" names the LANE, and the ruled patch delivers that lane to STRIP 5; and
`s54lib.chain` had gone stale.** (a) `C1_IN_16` (`sport_id=1;slot_start=7`) is J25's converter lane and stays right in dsp.csv.
The ruled array puts packed RX 15 on strip index 4 (`patch[15] = 4`): strip 5 = `Chan005` = panel MIC 5. Only the identity patch
puts J25 on strip 16, and that is a console where fader 16 plays MIC 5. Measured both ways (S58-1), landed the ruled array. "Lane N"
and "strip N" are different numbers from here on: tools say **strip** for the console channel (`d24_inputs.strip(xlr)`) and
**lane** for the `C1_IN_nn` INPUT_TDM cell (`Xlr.lane`). The declaration carries both (`proposals/CONTRACT-PROPOSAL-S58.md`).
(b) Every S54/S57 tool reached MIC 5 through `s54lib.Rig.chain` = `app cli chain-set ch8:… ch24:mute=0 instr1=1`, S52's workaround
for the reversed wire order. Since the app's wire-order fix (`AnalogControlChain.ToWire`), `ch8` is J31's register and that image
unmutes J42 and asserts INSTR1 again. It now sends the bytes by spidev (`s55_chain`, send position 15, every other register muted,
INSTR byte 0x00), independent of the app build.

**Tools changed (gate 3).** One map, `tools/pi/d24_inputs.py` (XLR, panel, 595 ref, chain index, send position, ADC, AIN, slot,
lane; strip computed from `D24_INPUT_PATCH`; `PRE_S58_PATCH` to read old records). Hard-coded MIC 5 = 20 replaced by
`d24_inputs.MIC5_STRIP` / `s54lib.LOOP` in: `tools/pi/dsp4_s48_scan.py` (also scans strips 1–24, not 1–12, labelled by XLR);
`s52/tools/s52lib.py` (patch from dsp4_config); `s54/tools/s54lib.py` (LOOP, chain), `s54_battery.py`, `s54_knee.py`,
`s54_t3c63.py`, `s54_txpeek.py`; `s55/tools/s55_run.py` (CHANNELS generated), `s55_handback.py`, `s55_repeat.py`, `s55_ingest.py`
(`channels.md` regenerated with "lane (S55)" and "strip (S58)" columns, no figure changed); `s56/tools/s56_setup.py`, `s56_fs.py`;
`s57/tools/s57_cap.py`, `s57_code0.py`, `s57_code63.py`, `s57_gain_set.py`, `s57_handback.py`, `s57_lfrec.py`, `s57_link.py`,
`s57_pw_setup.py`, `s57_readline.py`, `s57_readonly.py`. All deployed to the Pi (old copies `*.bak-2026-09-16-pre-s58`) and imported
there (`LOOP 5`). Left as records: the S52 shell scripts (`s52_law.sh`, `s52_meas51.sh`, `--meas 20` for the s49tap pair, which
is not the running pair). `s57_readonly.py`'s "strip 20" console text became "the MIC 5 strip".

**Unit handed back:** OscOn 0, OscChan 6, strip 6 and strip 5 as found (read back equal), MeasChan **5** (= MIC 5; was 20 = MIC 5
under the old patch), chain image as found (J25 open code 0, rest muted, INSTR off; not rewritten), S58 patch applied, AN_EN hi.
Loop cable still on J25.

## SIXTEEN MIC PREAMPS, ONE LAW: THE UNIVERSAL STEP/TRIM TABLE HOLDS TO 0.08 dB; J29 HAS A STAGE OFF-VALUE, J31/J32 A HIGH-FREQUENCY NOISE EXCESS (2026-09-16, session 55 — bench, MW-D24-2, hands-free)

**Pair:** `s56`, as S56/S57 left it; nothing rebooted or flashed. AN_EN (`op pd | hi`) read before every channel, never written.
**Loop:** TEST_OSC 1 kHz on donor strip 6 → AUX 1 → J45 → loop cable → XLR under test → preamp → lane (strip) → TEST_MEAS
(strip 1 was the donor for J32, whose lane is strip 6). **T4/T4b source:** a 150 Ω shunt across pins 2–3, loop cable off, tone off.
PW moved the cables; nobody typed. Conventions per spec-audio-test-set.md: dBFS on its own side, mean-square noise, EIN dBu =
P + 3.01 + 23.13 − G_loop(code) with the channel's own loop gain at that code. Data `MW/D24/DSP/s55/` (`law.csv`, `trim-table.md/.csv`,
`channels.md`, `data/<XLR>_loop.json`, `data/<XLR>_c63_*.json` / `_c00_*.json` captures, `data/s55_run.jsonl/.out`); tools `MW/D24/DSP/s55/tools/`.

**S55-1. Method and coverage.** `s55_run.py` ran 12:00–14:15 BST as one state machine: WATCH (the lane carrying the tone names the XLR,
three scans agreeing; 15 of 15 detections right, the tone lane −14.4 dBFS against ≤ −92.8 dBFS on the next lane), LOOP SET
(T1 64 codes, T2 codes 0/63, T3, T5/T8, ≈ 2 min per channel), SHUNT (code 63, floor < −70 dBFS held 12 s; the fitted floors read
−85.0 … −94.5 dBFS), NOISE (8 windows + six 16k captures at code 63, three at code 0), then back to WATCH. **Every 595 image was
sent by `s55_chain.py` (spidev, the `chain-set` wire protocol) and verified 200/200 — 1,113 of 1,113.** It exists because
`app cli chain-set` cannot put a gain on send position 0 (J42's register, which `chain-set` prints as `SHIFT`); validated by the app's
own pass-1 readback showing the bytes written (`A8 04 …`), and J42 then swept its full law. **0 capture overruns on 135 captures.**
All 15 powered registers not under test stayed open at code 0; INSTR byte (p24) 0x00 throughout. J25 (MIC 5) enters the table from S54's
sweep (same loop, same method). J15–J22 (U15, lanes 1–4/13–16) have no rails on this unit: **not tested.**

**S55-2. T1 on 16 channels: every law monotonic, code-0 loop gain +5.544…+5.580 dB (spread 0.036 dB), range 53.02–53.17 dB. One
flag: J29 (MIC 7).** Against J27, J29 matches to 0.01 dB at every code whose bit 3 (code 8, byte bit Q5) is clear, and is low at every
code where it is set: −0.84 dB at code 8, −0.50 at 15, −0.24 at 24, −0.10 at 40, −0.06 at 63 — the offset shrinks exactly as a smaller
parallel increment would once the other stages add. The code-8 stage gives **~9 % less linear gain** on J29: one part in that stage
(the bit-3 feedback resistor or its switch's on-resistance) is off-value. PW: probe J29's bit-3 stage. The other 15 channels agree within
0.171 dB at every code (worst at the code-32 stage, 0.17 dB; code 1–7 stages ≤ 0.010 dB).

**S55-3. The universal table (`trim-table.md`, proposed as `common/tables/mic-gain-law.csv`, `proposals/CONTRACT-PROPOSAL-S55.md`).**
Built from the 15 unflagged channels (J29 reported, not averaged). Target 0–60 dB → largest mean hardware gain ≤ target, trim ≥ 0.
It uses 25 codes (0, 1, 2, 3, 4, 5, 6, 7, 9, 10, 11, 13, 15, 17, 20, 23, 25, 29, 31, 37, 42, 47, 53, 61, 63). **A channel at the
spread's edge is off by ≤ 0.078 dB** at any of those codes. Largest trim inside the hardware range 12.0 dB (targets 1–12 ride on code 0;
the first hardware step is 12.84 dB); 54–60 dB take code 63 (+53.11 dB) + 0.89…6.89 dB. J29 at its worst table code (9) would be
−0.76 dB. No address change is proposed: `Chan[nnn]Gain001` (GAIN word 0, law 0–60 dB) receives the trim, the code goes to the chain.

**S55-4. T2/T3/T5/T8 are uniform across all 15 new channels.** T2 20 Hz re 1 kHz −0.41/−0.42 dB at code 0 and −2.07…−2.19 dB at code 63
(50 Hz −0.43…−0.47 at 63); 100 Hz–15 kHz −0.13…+0.08 dB (the −0.13 is 100 Hz at code 63), 20 kHz −0.11/−0.12 dB. T3 at code 0: −20 dBFS −81.6…−82.6 dB (≈ 0.008 %, noise-limited),
best −89.98 … −92.97 dB = 0.0032 … 0.0023 % at −10 or −6 dBFS, −3 dBFS −86.7 … −88.8 dB; code 63 at −3 dBFS −43.10 … −44.41 dB
(0.60–0.70 %, the code-63 noise floor, not distortion, as S54-3). No sample at FS (block peak −2.86…−2.92 dBFS at code 63).
**T5: every loop inverts** (intercept 180.2°). **T8: 91.40–91.41 samples** (1–2 kHz fit, residual 0.03°). Method note: T1's per-code
THD+N column is settling-limited (two windows 85 ms after a gain switch; codes 1–3 read −41…−70 dB on every channel against S54's −77 at
longer settle) — it is not a spec figure; T3 is.

**S55-5. T4/T4b at 150 Ω: 14 channels EIN −126.5 … −128.7 dBu 20 Hz–20 kHz and −130.2 … −130.9 dBu(A) at code 63; J31 and J32 are
worse, −123.2 / −128.7 and −125.2 / −129.8, from a high-frequency excess.** Band split against J26/J28/J30 (six captures each): J31
2–20 kHz +4.9 dB, 20–24 kHz +10.4 dB; J32 +3.3 / +7.4 dB; below 2 kHz identical to ≤ 0.5 dB. Smooth (no lines 12 dB above the local
floor except isolated −113 … −123 dBFS bins), Gaussian (kurtosis ≤ 3.13), mains ≤ 0.14 %. T2 at 10–20 kHz matches the other channels, so
it is not gain peaking. J31/J32 are lanes 5/6 and adjacent sends p9/p8 — a shared converter pair or neighbouring-stage cause is the suspect
(PW: what U-number serves lanes 5/6, any oscillation-prone compensation on those two preamps); a re-seat of the shunt and a re-capture
would exclude the fixture. Code 0 (converter floor at 150 Ω): −112.4 … −114.2 dBFS node, −115.0 … −115.8 dBFS 20–20k on every channel.
**Sub-20 Hz (S57's wander) comes and goes per channel:** −123.5 (J27) … −142.9 dBu (J36) input-referred, so the raw DC–24 kHz figure
ranges −119.2 … −126.0 dBu while the 20–20k figure does not move — the in-band number is the spec figure (S57-5).

**S55-6. Unit and bookkeeping.** Hand-back (`s55_handback.py`): TEST_OSC off, MeasChan 20, nothing on AUX 1, the S57 image (J25 open
code 0, every other register 0x01, INSTR byte 0x00) VERIFIED, lane 20 −108.7…−111.7 dBFS at code 0 with the 150 Ω. Two slips, both
repaired: (a) my first pre-flight crashed on a strip-1 AuxSend write after `strip_unity(1)` had run, so strip 1 was left unmuted with
the compressor off and a later save recorded that state; restored by hand to `Mute 1, CompOn 1, AuxOn 0, AuxSend 0.0` (the S55 start
snapshot). (b) `pkill -f s55_run.py` also killed its own ssh shell; the runner was stopped in WATCH (tone on, all registers open code 0)
and the hand-back then ran separately. AN_EN hi, GPIO 27 hi at the end.

**S55-7. Hub addendum: J31's T4/T4b repeated after PW refitted the 150 Ω — identical, so the high-frequency excess is the channel, not the fixture.**
Same conditions as the run (all powered registers open at code 0, J31 at code 63 via send position 9, TEST_OSC off, MeasChan 5).
Refit seen 14:31:29 (disturbance to −33.2 dBFS at 14:30:09, then −87.0 dBFS held 12 s). Code 63: **−123.3 dBu 20 Hz–20 kHz / −128.7 dBu(A)**
against the first run's −123.2 / −128.7; 2–20 kHz −91.0 vs −91.2 dBFS, 20–24 kHz −89.4 vs −89.3 dBFS; sub-20 Hz −127.0 vs −129.6 dBu
(the wander, which varies run to run); code 0 −95.0 vs −94.6 dBu (converter floor); 0 overruns on 9 captures. **The J31/J32 excess is not
the shunt or its fitting** — the suspect stays what serves lanes 5/6. Method slip, repaired: the first arming (14:24) took the
code-switch transient (−41 dBFS on the first 85 ms window) as the "disturbance" and measured J31's OPEN input 12 s later (a steady
−78.7 dBFS — between the loop cable's −51 and the shunt's −86, so the −70 dBFS rule cannot separate open from 150 Ω on this channel).
Those captures are void and not committed (`~/s55/data/void_open_J31/` on the bench). `s55_repeat.py` now takes a settled 20-window
baseline first and requires a rise ≥ 6 dB above it, then a floor ≤ baseline − 4 dB held 12 s. Unit handed back again as S55-6
(S57 image verified, TEST_OSC off, nothing on AUX 1, MeasChan 20, strip 5 restored, AN_EN hi, never written).

## THE BURST IS BELOW 20 Hz: THE AUDIO-BAND FLOOR AT FULL GAIN IS STEADY, AND THE EIN RECONCILES ABOVE THERMAL (2026-09-16, session 57 — bench, MW-D24-2; closed early, remaining gates carried into S55)

**Pair:** `s56`, running as S56 left it; nothing rebooted. AN_EN (`op pd | hi`) and CS_M (`op pu | hi`) never written. Data: `MW/D24/DSP/s57/data/`,
tools: `MW/D24/DSP/s57/tools/`. Every capture is a 16,384-sample capture-arm run of strip 20 post-fader (MeasChan 20, strip 20 transparent),
**0 overruns on every one**. Levels are mean-square dBFS (a full-scale sine reads −3.01). **dBu (S57-R):** input-referred = P + 3.01 + 17.55 −
(G(code) − G(0)), with T1 gains G(0) 5.578, G(48) 57.00, G(63) 58.717; output at J45 through the loop = P + 20.56 at code 0. Bands come from
`dsp4_fft.band_power` (mean removed, bin-domain brick wall, IEC 61672 A-weighting), added this session as `--band 20-20000 --aweight` (PW ruling).
Source: the 150 Ω metal-film shunt on J25 pins 2–3, loop cable off, TEST_OSC off, except where stated.

**S57-1. Gate 1, twenty captures at code 63 (`g1_*`, 10:46–10:51 BST): the excess is a sub-20 Hz wander, not mains, popcorn, broadband or pickup.**

| per capture (20) | min | max | energy avg | input-referred, dBu |
|---|---:|---:|---:|---:|
| DC-removed total, DC–24 kHz, dBFS | −92.19 | −89.94 | −91.63 | −124.21 |
| **20 Hz–20 kHz, dBFS** | −94.87 | −94.31 | **−94.63** | **−127.21** |
| **20 Hz–20 kHz A-weighted, dBFS** | −98.13 | −97.74 | **−97.93** | **−130.51 dBu(A)** |
| 0.1–5 Hz, dBFS | −123.90 | −94.75 | −102.00 | −134.58 |
| 5–20 Hz, dBFS | −122.12 | −100.82 | −107.50 | — |
| 20–24 kHz, dBFS | −96.37 | −95.44 | −95.90 | — |

(a) **Mains:** 0.12–0.43 % of the power per capture (floor-subtracted ±5 bins at 50…400 Hz, which is estimator scatter). In the averaged
20-capture PSD 50 Hz stands 4.3 dB above its local median at −122.5 dBFS (−155.1 dBu input-referred) and 100 Hz 3.2 dB, off-bin. No
harmonic series. (b) **Impulsive:** kurtosis 2.83–3.04 (Gaussian = 3); > 4σ excursions (robust σ) 0–4 per capture, mean 0.55 against 1.04
expected for Gaussian noise; widths 1 sample; RMS with them excised moves ≤ 0.03 dB; crest factor 11.2–13.1 dB. No popcorn. (c) **Broadband:**
the in-band power is steady to ±0.3 dB. Slope 100 Hz–10 kHz −1.0 dB/decade on average (−2.0 … +0.1), so white, not pink. Densities
20–200 Hz −138, 200 Hz–2 kHz −140.7, 2–20 kHz −140.1 dBFS/Hz. The 20–24 kHz band is about 5.5 dB denser than the audio band (converter
noise shaping near Nyquist, present at every code). (d) **RF / digital:** no line in the averaged PSD stands 6 dB above the floor anywhere.
Suspects checked by frequency: fs/n for n = 2…48, 1 kHz (USB SOF), 8 kHz (USB HS, and the alias of the 1 MHz PSU_12_CLK / PSU_48_CLK at
fs 48 k). Only fs/4 = 12 kHz shows, +4.9 dB at −126.5 dBFS (−159.1 dBu input-referred). **What moves between captures is the DC–24 kHz total
(2.3 dB), and all of that movement is below 20 Hz:** in a burst capture (g1_13, g1_10) the sub-20 Hz waveform is a smooth excursion of
±40 µFS (≈ −88 dBFS peak) across the 0.34 s record, not steps. In a quiet one (g1_03) it is ±2 µFS. S54-3b's 10 dB window-to-window
spread was this wander seen through TEST_MEAS's 4,096-sample DC–24 kHz RmsResult: an 85 ms window of a 0.5–1 Hz excursion reads it as
offset. The S54 bursts are therefore **not an audio-band noise problem**; the 20–20k figure is stationary.

**S57-2. The wander is 0.4–1 Hz and is not caused by the host's SPI traffic.**
*Slow record* (`s57_lfrec.py`, `lf_c63.json`, code 63, 40 s, one RX-lane word peeked per sample at 500/s, 9 × 8 s Hann segments): the
aliased audio-band noise gives a flat floor of −119.5 dBFS/Hz. Above that floor: **0.1–0.5 Hz +20.5 dB (excess −103.2 dBFS), 0.5–2 Hz
+20.6 dB (−97.2 dBFS)**, 2–5 Hz +4.9 dB, 5–20 Hz +2.6 dB, 20–60 Hz +2.6 dB. Largest bins 0.375–1.0 Hz (+22.5…+23.9 dB), with no
single dominant line at 0.125 Hz resolution, so it is band-limited random wander, not a periodic supply cycle. *Link A/B* (`lk_*`, code 63,
12 captures cycling quiet / flat-out chip-1 reads (200 I/Os per run) / flat-out chip-2 reads): 20–20k −94.34 … −94.77 dBFS in all three
states. Sub-5 Hz per state: quiet −106.6 … −129.7, chip 1 −103.2 … −128.8, chip 2 −111.1 … −123.8 dBFS. The spread is the wander's own,
and no state is systematically higher. The code-0 floor record at 150 Ω (`lf_c0`) was lost to a script bug (argv read after the s54lib
import, fixed); the code-16 record (`loopsrc/lf_c16.json`) was taken with the loop cable on and is set aside.

**S57-3. Gate 2 (per code) as far as it ran: the audio-band floor refers to the same input figure at codes 48 and 63.**

| set | code | n | 20–20k dBFS | A dBFS | DC–24k dBFS | 0.1–5 Hz dBFS | input 20–20k dBu | input A dBu(A) | input DC–24k dBu |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| g1 | 63 | 20 | −94.63 | −97.93 | −91.63 | −102.00 | −127.21 | −130.51 | −124.21 |
| g1v (after the refit) | 63 | 3 | −94.73 | −97.96 | −92.34 | −116.45 | −127.31 | −130.54 | −124.92 |
| g3 | 63 | 5 | −94.61 | −97.96 | −90.75 | −98.33 | −127.19 | −130.54 | −123.33 |
| g2c48 | 48 | 3 | −96.34 | −99.60 | −92.89 | −100.86 | −127.20 | −130.46 | −123.75 |
| f150c0 | 0 | 5 | −115.63 | −118.03 | −114.60 | −132.27 | (−95.07) | (−97.47) | (−94.04) |

The in-band input-referred figure is the same at 48 and 63 (−127.20 / −127.21 dBu), so the audio-band floor is set at the preamp input, as
S54 T4 found. The sub-5 Hz part scales with the gain too: −100.9 dBFS at code 48 against −102.0 at 63, both input-referring near −132…−135 dBu,
and at code 0 it is −132.3 dBFS. That points to the input stage (or the source and its leads), not the ADC or the post-preamp stages. With only
code 48 (3 captures) that inference is provisional. Code 0 is the converter floor, so its input column is not an EIN. **Not measured:** codes 32 and 16 with the 150 Ω. At 11:15:04–11:15:17 BST the lane at
code 48 moved from −93 to −53 dBFS between captures 2 and 3, and the next captures read S54's loop floors (−56.6 / −63.0 / −51.6 dBFS at
codes 32 / 16 / 63): the loop cable was back on J25 mid-run. Those captures (`data/loopsrc/`) are set aside and not used.

**S57-4. Gate 3 (time), partial: the wander comes and goes on a minute scale; the audio band does not.** Five captures a minute apart
(`g3_*`, 10:51:29–10:55:29 BST) plus three at 11:10 (`g1v`): 20–20k −94.45 … −94.84 dBFS throughout. Sub-5 Hz −95.8 / −118.6 / −106.8 /
−93.7 / −106.1 dBFS at the five minutes, and −112.7 / −120.8 / −122.5 at 11:10. DC–24k −88.9 … −92.4. Five of ten were taken (the
queue was stopped for the output-noise interrupt), so stationarity of the wander is not decided. It varies by > 20 dB between captures
a minute apart.

**S57-5. Gate 4. EIN (S57-R arithmetic), 150 Ω, code 63: −127.2 dBu 20 Hz–20 kHz unweighted and −130.5 dBu(A)**. Thermal 150 Ω at 290 K is −130.97
dBu and −133.02 dBu(A), so the noise figure is 3.8 dB unweighted and 2.5 dB A-weighted. The raw DC–24 kHz figure (the node's band) is −124.2 dBu, and
S54-3b's −123.6 dBu (+3.01 → −120.6) was the same figure in a DC–24 kHz window with the wander in it. **There are no bursts to excise in the
audio band:** the 4σ-excised RMS equals the plain RMS within 0.03 dB. Hum at the input: 50 Hz ≤ −155 dBu (+4.3 dB above the local floor, not
resolved as a line). **Physical suspects for the 0.4–1 Hz wander, for PW to probe** (no analog change here): (1) thermoelectric / air-current
EMFs at the 150 Ω shunt's leads and solder joints on J25 (a sub-Hz, draught-driven wander is their signature; a shielded, thermally lagged
shunt or a metal cap over J25 tells), (2) the input coupling network (C331/C348 33 µF electrolytics into 2k2 per leg: leakage or dielectric
absorption current through 2k2 at gain 58.7 dB), (3) the input pair's bias and tail current (Q220/Q221 with C343; the 1/f corner of the pair),
(4) the phantom node through R697/R749 6k8 even with phantom off (Q219 switch leakage and the +45 V converter), (5) the +5 V / AVDD rail
(4.6 V) and the ±15 V converters. The 1 MHz PSU clocks show no line in band. Their low-frequency supply ripple would reach the input stage
through (4)/(5). The quick discriminator is a shorted input (0 Ω across pins 2–3) against the 150 Ω. Wander that stays with 0 Ω is (2)–(5);
wander that goes is (1).

**S57-O. AUX 1 output noise (hub interrupt, PW reading -84 / -87 dBu on his meter).** Loop cable back on J45 → J25 (150 Ω off), MIC 5
at code 0 (`[15] ch8 0x00`, 200/200), TEST_OSC OFF (strip 6 → AUX 1 idle), twenty captures (`aux1n_*.json`), energy-averaged,
`s57_outnoise.py` (band figures from `dsp4_fft.band_power`, mean removed, bin-domain brick wall, IEC 61672 A-weighting):

| band | lane, dBFS | dBu at J45, lane + 17.55 | dBu, lane + 3.01 + 17.55 | floor-corrected (−113.8 dBFS), dBu (+20.56) |
|---|---:|---:|---:|---:|
| **20 Hz–20 kHz unweighted** | −105.11 | −87.56 | **−84.55** | −85.18 (lower bound) |
| **20 Hz–20 kHz A-weighted** | −107.53 | −89.98 | **−86.97** | −88.14 (lower bound) |
| DC–24 kHz raw (node figure) | −104.32 | −86.77 | −83.76 | −84.28 |

Per-capture spread ±0.4 dB (20–20k −104.68 … −105.50); the node's own windows read −103.94 … −104.47 dBFS, matching the raw column.
**The dBu reference: +17.55 dBu is a full-scale SINE's RMS voltage, and RmsResult / the FFT put that sine at −3.01 dBFS (mean square).
A noise power quoted in those dBFS is therefore lane + 3.01 + 17.55 dBu.** The plain "+17.55" rule reads 3.01 dB low. PW's meter
(−84 / −87 dBu) agrees with the +20.56 column to 0.6 dB and disagrees with the +17.55 column by 3 dB, which confirms the correction. The
same applies to the dispatch's EIN arithmetic (S54-3b's −123.6 dBu average is −120.6 dBu). **Floor correction:** power-subtracting the
150 Ω code-0 floor (−113.8 dBFS, the node's DC–24 kHz figure) moves the output figures by 0.5–1.2 dB. It is exact for the raw column only;
the in-band converter floor is lower than −113.8, so the corrected band figures are lower bounds, and the true AUX 1 output noise lies
between the corrected and uncorrected columns. **Band-matched floor, taken after the 150 Ω went back (`f150c0`, 5 captures, code 0):** 20–20k −115.63, A −118.03, DC–24 kHz −114.60 dBFS. Power-subtracted: **20–20k −105.51 dBFS = −84.95 dBu, A −107.94 dBFS = −87.38 dBu, DC–24 kHz −104.75 dBFS = −84.19 dBu** at J45 (+20.56). The code-0 floor already includes the preamp at code 0, but that part is −147.8 dBFS, so it is the converter floor.
**Lines** (averaged 20-capture PSD, band power minus local median, dBu at +20.56): 52.7 Hz −104.56 (5.2 dB above floor), 76.2 Hz
−105.87 (4.5), 102.5 Hz −106.06 (4.6), 16,136.7 Hz −117.57 (3.2). The next six are under 3 dB above the floor and are not resolved as
lines: 184.6 Hz −114.24, 284.2 −114.38, 155.3 −115.08, 553.7 −116.71, 3,893.6 −117.17, 17,361.3 −117.66. So there is no switching
line and no hum line stronger than −104.6 dBu. The three LF peaks sit within a bin or two of 50/75/100 Hz on a 2.93 Hz grid; the
7-term window's ±23 Hz lobe does not separate them from the LF skirt, so calling them mains is not claimed.
*Void:* a code-0 run meant as the 150 Ω floor (`f150c0`, 3 captures) turned out to have been taken after the cable swap (node −104 dBFS, not
−113.8). It is moved to `~/s57/void` on the bench and is not used.

**S57-R. Input-side reconciliation, desk part (hub 10:1xZ: "−132.8 dBu is below thermal").** Steps in `s57/data/s57_reconcile_desk.out`.
(1) Gate-1 lane power, code 63, 150 Ω, 20 captures energy-averaged: 20 Hz–20 kHz −94.63 dBFS (−94.87 … −94.31), A −97.93, DC–24 kHz −91.63
(mean-square dBFS, so a full-scale sine reads −3.01). (2) +3.01 dB to the FS-sine reference. (3) FS sine at the mic XLR at **code 0** = +23.13 dBu
(DAC FS at J45) − 5.578 dB (T1 code-0 loop gain) = +17.55 dBu. (4) Code 63 sits **53.139 dB above code 0** (58.717 − 5.578). **The error was in
the hub arithmetic: −94.6 + 20.56 − 58.72 subtracts the absolute code-63 loop gain, but code 0's 5.578 dB is already inside +17.55, so it was
counted twice (−5.58 dB).** EIN = −94.63 + 20.56 − 53.14 = **−127.21 dBu 20 Hz–20 kHz, −130.51 dBu(A)** (DC–24 kHz −124.21 dBu, which carries
the sub-20 Hz wander). (5) Thermal 150 Ω, 4kTRB, 19.98 kHz: −130.97 dBu at 290 K (−130.82 at 300 K); A-weighted white = flat − 2.05 dB →
−133.02 dBu(A). (6) **Margin over thermal: +3.76 dB unweighted (NF), +2.51 dB A-weighted: above thermal, physically possible.** The
convention checks: T1's loop gain is `H_db`, coherent PEAK over oscillator PEAK (`s54lib.windows`), and `gain_rms_db` uses RMS over
osc − 3.01 dB, so both are like-for-like; S54-1 had them equal to 0.001 dB, and S56-1 had FFT RMS equal to RmsResult to 0.002 dB. No
peak/RMS mix-up in the gain. **Preamp input R (netlist + analog BOM rev B), per leg:** J25.2 → C331 33 µF → node C1 → R696 2k2 to GND
(C345 220 pF to GND) → R695 10 Ω → the input pair's base (Q220/Q221, C343 across the pair). On the XLR side, R697 6k8 goes to the phantom
node PH (Q219 switch) and R701 33 k to the TRS ring (open). Cold leg mirrors (C348, R750 2k2, R741 10 Ω, R749 6k8, R702 33 k).
**Differential input R ≈ 4.4 kΩ (2 × 2k2) if PH floats with phantom off, or 3.32 kΩ (2 × 2k2‖6k8) if the switch grounds it**, with the bases'
own input impedance in parallel (not modelled). Loading: T1's ≈ 66 Ω loop source loses 0.13–0.17 dB into that R; a 150 Ω source loses
0.29–0.38 dB. Referred to the source EMF, the EIN moves **+0.16 to +0.21 dB** (−127.0 dBu / −130.3 dBu(A)); if PW's J45 DMM reading was
unloaded, that is −0.13 to −0.17 dB the other way. So ±0.2 dB, not the 5.6 dB. Thermal of 150 ‖ 3.32 k is −131.16 dBu. **Carried into S55:** the code-63 gain re-measured from an FFT of a capture (needs the loop cable) and the value of the resistor PW fitted (metal film, value not recorded here). Until both are in, the EIN below is quoted with that caveat.

**Hub/PW bench window (after gate 1, not S57 data).** For PW's external measurement: MIC 5 set to code 63 with only strip 20 on AUX 1 at unity
(`s57_pw_setup.py`, guarded: it refused once when the lane read −51.5 dBFS with the loop cable on, and routed only at −92.2 dBFS with the 150 Ω).
Read-only snapshots for the hub (`s57_readonly.py`, `s57_readline.py`): with PW's oscillator on J25 the lane stayed at the floor (−89.95
dBFS at code 63; −98.8 … −114 at code 0) until PW fixed his cable. Then the lane read −74.9 / −70.4 dBFS at code 0, and at code 63 −17.84 dBFS
RMS / −14.39 pk with AUX 1 TX −17.01 / −14.33 (expected ≈ −14 dBFS for −50 dBu). The chain image was re-sent once on the hub's word
(`[15]` 0x00, `[0]` 0x01, 200/200). AUX 1 end to end therefore passes the MIC 5 lane at unity (TX within 0.8 dB of the lane).

**Carried into S55 (per-channel noise phase):** gate 2 at codes 32 and 16 (and 0 again for the sub-20 Hz part) with the 150 Ω; gate 3's
remaining five minute-spaced captures, or a longer (10 min) slow record; the 0 Ω vs 150 Ω discriminator for the wander; the code-63 gain
re-measured by FFT on a capture with the loop cable on (S57-R); the fitted shunt's value recorded; the code-0 slow record. The
analysis tools carry across unchanged: `s57_analyse.py`, `s57_bands.py`, `s57_avgpsd.py`, `s57_lfan.py`, `s57_table.py`,
`s57_outnoise.py`.

**Hand-back (11:44 BST):** `s56` pair running. MIC 5 at **code 0**, unmuted, phantom off (`[15] ch8 0x00`, 200/200). **TEST_OSC off.**
MeasChan 20. **Strip 20 OFF AUX 1, and no strip on AUX 1** (read back; strip 6's S56 send was removed at 11:23 for the hub, so the 1 kHz
sine on AUX 1 is NOT running). Strip 20 unmuted, MainOn 0; 22 of 24 strips muted as found. AN_EN (GPIO26) `op pd | hi`, CS_M (GPIO27)
`op pu | hi`, neither written. matrix-app inactive. The lane reads −113.9 … −114.6 dBFS at code 0 (the 150 Ω floor). 150 Ω and cable as PW
has them.

## A CAPTURE ARM ON CHIP 1 FOR 72 CYCLES, AND THE 0.98 FS CEILING IS NOT IN THE DSP (2026-09-16, session 56 — desk + digital loop, MW-D24-2)

**Pair:** `s56` (`DSP4_TEST_NODES=1`, no tap; chip1 `314ce05f…`, chip2 `c56ed0ab…`, the same chip 2 as `s51_119ea9d9` byte for byte), staged at `~/s56`,
booted and configured D24 twice (`boot.sh`, `DIAG_BUILD_CFG2 raw2 0xC3010244`). The S54 hand-back image was re-applied on it
(`s56_setup.py`: strip 6 → AUX 1 unity, CompOn 0, MainOn 0; strip 20 transparent; 22 other strips muted; TEST_OSC 1 kHz −20 dBFS pk on
strip 6; MeasChan 20). Read on `s51` before the reboot and on `s56` after, the two matched in every word. The 595 chain was never written.
AN_EN (GPIO26) read `op pd | hi` before and after, never written. Every stimulus was digital (TEST_OSC). Data: `MW/D24/DSP/s56/data/`
(`s56_gate1.jsonl`, `s56_cost.jsonl`, `s56_fs.jsonl`, the six captures `cap_*.json`); tools: `MW/D24/DSP/s56/tools/`.

**S56-1. The capture arm: TEST_MEAS copies MeasChan's post-fader block into a 16,384-word chip-1 buffer, and the FFT agrees with the node to 0.002 dB.**
*Build.* The generator was changed, not the output: `tools/dsp/dsp_codegen.py::gen_test_meas` and `MW/D32/DSP/gen_dsp.py::expand_test_osc`.
After the MeasChan compare succeeds, `_test_meas_tap` checks `_meas_cap_arm_`. When the arm is set it copies the 16-word pool slot into
`_meas_cap_buf_C1_TEST_MEAS[DSP4_TEST_CAP_MAX]` (L2 `seg_delay`, next to the delay pool). This is the same slot the RMS/THD+N fit reads
on the same pass. At N samples, or at the end of the buffer, the tap publishes the count and clears the arm. `DSP4_TEST_CAP_MAX = 16384`
is generated into `dsp_block.h`, and the generator refuses a size that is not a whole number of blocks. The two host words are TEST_OSC's
two reserved dispatch entries, `0x1375` and `0x1376`, dispatched without cells like the window serial. No address moves and the table does
not grow. Contract proposal: `proposals/CONTRACT-PROPOSAL-S56.md`. Host: `tools/pi/dsp4_meascap.py` runs the handshake (Ready ← 0,
Arm ← N, poll Ready, peek N words, chip-1 `_diag_blk_overrun` delta across the run). `tools/pi/dsp4_fft.py --capture N` reads the buffer
straight off the part. Regenerate: `./regenerate-dsp-contract.sh` moved only `C1_TEST_MEAS.asm`, `chip1/dsp_params.asm` (two entries) and
`dsp_block.h`. No matrix changed. The shipping build (`DSP4_TEST_NODES=0`) still produces a 451,892 B chip 1 and 307,980 B chip 2.
*Cost, measured on the part* (D24 configuration, TEST_OSC driving strip 6, MeasChan 6). Code: **29 instructions** in the tap, TEST_NODES
builds only. Data: **3 L1 words** + **16,384 L2 words**. Idle: 3 instructions per block, only on the named strip (too small to resolve).
Copying: **+72 cycles median per block pass**, from interleaved exact TCOUNT passes (4,545 idle vs 1,398 taken while the run index was
moving): idle median 214,032, armed 214,104.5, mean +86. That is **0.02 % of the 327,680-cycle budget**, about 52 instructions, which
matches the code. Overruns: **+0 on chip 1 and +0 on chip 2** over a 30.3 s soak of 84 back-to-back 16k captures, and 84 of 84 completed.
`_proc_cyc_max` jumped on **both** chips during the soak. Chip 2 never executes the capture, so that maximum comes from link traffic and
not from the arm. Read time over the diag peek: 4,096 words in 3.1 s, 16,384 in about 13 s.
*Proof through the digital loop*, capture vs TEST_MEAS on the same running signal (node = 8 windows either side of the capture):

| signal on strip 6 (post-fader) | N | RMS node / FFT, dBFS | THD+N node / FFT, dB | THD+N % node / FFT | noise+dist node / FFT, dBFS | FFT THD(2..10) |
|---|---:|---|---|---|---|---|
| 1 kHz −20 dBFS, clean | 4096 | −23.010 / −23.010 | −115.42 / −151.61 | 0.00017 / 0.00000 | −138.43 / −174.62 | −156.46 dB |
| 1 kHz −10 dBFS, CompOn 1 | 4096 | −19.643 / −19.644 | **−55.750 / −55.750** | **0.16312 / 0.16313** | **−75.393 / −75.393** | −55.751 dB = 0.16310 % |
| 1 kHz −10 dBFS, CompOn 1 | 16384 | −19.646 / −19.644 | **−55.749 / −55.750** | **0.16314 / 0.16313** | **−75.394 / −75.393** | −55.751 dB = 0.16310 % |
| 1 kHz −18 dBFS, CompOn 1 | 16384 | −21.643 / −21.644 | **−55.752 / −55.752** | **0.16308 / 0.16309** | **−77.395 / −77.395** | −55.753 dB = 0.16306 % |

**Gate criterion (≤ 0.5 dB) met with ≤ 0.002 dB** wherever the signal is above both instruments' floors. The strip-6 compressor gives
a known digital distortion (h3 −55.93 dBc, h5 −70.39 dBc). The clean −20 dBFS row is the exception, and it is the instruments, not the
signal: ThdResult −115 dB is TEST_MEAS's own float32 fit floor (spread 1.1 dB), and the FFT sees the tone 36 dB cleaner. So TEST_MEAS
cannot certify a digital path below about −115 dB, and the capture can. Comparison basis: node NoiseResult is residual energy including
harmonics, compared with the FFT's `THD+N dBFS`. The FFT's harmonic-free `noise` (−109.74 dBFS) has no node counterpart. Fundamental:
1000.0000 Hz on every capture. **20 Hz, −20 dBFS, CompOn 0:** 16,384 samples hold **6.83 cycles** (6 rising zero crossings, sample peak
0.10000), so ≥ 3 cycles is met at 16k. 4,096 holds 1.71 cycles and does **not** meet it. At 20 Hz `dsp4_fft.py` flags the spectrum
"crowded": its ±8-bin tone band is ±23 Hz at 16k and swallows DC and h2. The capture is right and the FFT's band is the limit. A 20 Hz
THD+N from the FFT needs a longer buffer or a narrower-lobe window (NEXT). TEST_MEAS at 20 Hz reads RMS −22.96 ±0.37 dB over its
4,096-sample window, the known short-window error (S54-1).

**S56-2. THE 0.98 FS CEILING IS NOT THE DSP. It sits on the analog side at a fixed LANE-referred level, after the preamp's gain, and short
of the ADC's digital full scale.**
*The DSP, measured.* TEST_OSC was injected into strip 20's **input block** (after `C1_IN_20`, before `C1_GAIN_20`), strip 20 unity with
dynamics off, and swept through full scale. The meter is the one S54-5 read, `_mtr_peak_C1_MTR_20`, plus the capture's sample peak:

| injected pk | 0.500 | 0.900 | 0.950 | 0.979 | 1.000 | 1.020 | 1.100 | 1.259 | 1.585 | 2.000 | 4.000 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| meter pk | 0.5000 | 0.9000 | 0.9500 | 0.9788 | **1.0000** | 1.0200 | 1.1000 | 1.2590 | **1.5850** | 2.0000 | **4.0000** |
| capture sample pk | 0.5000 | 0.9000 | 0.9500 | 0.9790 | 1.0000 | 1.0200 | 1.1000 | 1.2590 | 1.5850 | 2.0000 | 4.0000 |
| ThdResult, dB | −115.1 | −122.4 | −141.3 | −110.5 | −115.1 | −129.6 | −113.1 | −117.4 | −108.8 | −115.1 | −115.1 |
| FFT THD+N, dB | −151.8 | −151.7 | −153.1 | −150.9 | −153.6 | −149.7 | −151.4 | −149.5 | −149.1 | −153.6 | −151.8 |

Every point is linear to +12 dBFS, with THD+N at the instruments' floors and +0 overruns. So `C1_GAIN_20`, its wide-word peak, the meter
fold, `C1_FDR_20` and the Q4.28 pool do not saturate anywhere near 0.98. The meter's own ballistics cost 0.0005 of a peak between attacks
(min/max over six reads 0.99955), which is 0.004 dB and not 0.18 dB. The one stage the injection cannot reach is `C1_IN_20`'s RX read,
and from source it cannot limit: `r2 = dm(i0, m0); r2 = ashift r2 by -3` (`chip1/nodes/C1_IN_20.asm`), a pure shift of the Q1.31 slot
word with no clamp, so a 24-bit full-scale code 0x7FFFFF00 arrives as 0.99999. A converter code at FS would read ≥ 0.9999 on this
meter. S54-5's maximum of 0.979 therefore means **the ADC's output never reached its FS code**.
*DAC side, excluded by S54's own data.* The ceiling sits at the same lane level at two gain codes whose DAC levels are 19.5 dB apart.
At code 0 (loop +5.58 dB) THD+N passes 1 % between lane −1 and −0.5 dBFS with the DAC at about −6 dBFS digital. At code 2 (loop
+25.04 dB, `knee.out`) lane 0 dBFS reads 1.91 % and meter 0.958 with the DAC at about −25 dBFS. A DAC or AUX 1 output-stage clip would
follow the DAC level and not the lane level. The TX words themselves are unsaturated there (S54 `txpeek.out`, decoded as Q1.31). By the
same argument, the preamp's **input** stage is excluded (its input differs by 19.5 dB between the two codes).
*What remains, an analog question for PW's scope.* The limiter is between the preamp's gain-setting stage output and the AK5558's
modulator: (a) the preamp or ADC-driver output swing running out about 0.2 dB before the ADC's FS input, or (b) the AK5558's own input
range or modulator overload sitting below its digital FS code. Both give a soft ceiling with THD rising from −1 dBFS rather than a hard
0x7FFFFF clip, so the two are told apart at the pins, not in code. Scope plan, loop cable back on, code 0, lane driven to +2…+4 dBFS
(osc ≈ −3.6…−1.6 dBFS on strip 6): (1) the ADC driver output (U39's stage feeding AK5558 ch5 AINx±), flat-topping and at what volts;
(2) the driver's supply rails at that moment; (3) the differential swing at the AK5558 pins against the datasheet FS input for the
fitted VREF. Flat tops at the driver output, a few hundred mV short of its rails = (a). A clean sine at the pins at or above the
datasheet FS = (b). **Netlist facts wanted from the hub:** the ADC driver part and its rail voltages, and AK5558 VREFH/VREFL (the FS
input follows them). The AK5558 datasheet FS figure is not in this repo and was not guessed.

**Hand-back.** The `s56` pair is **left running**, not rebooted back to `s51_119ea9d9`. PW was reading J45 against the sine, and a
reboot drops the tone for about 2 minutes. The pair is a superset (same chip 2 md5, chip 1 = S51 + the capture arm) with the same cells
applied. **1 kHz −20 dBFS pk on strip 6 → AUX 1** (TEST_OSC on, OscChan 6, level 0.100000), confirmed on chip 2's AUX 1 TX lane: peak
−20.00 dBFS (Q1.31). **MeasChan 20**, CaptureArm 0. Strip 6 CompOn 0 / MainOn 0, strip 20 transparent, strips 1–24 other than 6/20
muted, matching the as-found read. AN_EN `hi`, CS_M `op pu hi`, both unwritten. matrix-app inactive (as found). Chain not written. MIC 5
at code 0 with the 150 Ω shunt as PW left it. During the session AUX 1 carried the S56-1 stimuli (1 kHz at −10/−18 dBFS through strip 6's compressor, 20 Hz −20 dBFS), then no
tone while the S56-2 sweep had TEST_OSC on strip 20. PW then asked for the sine back, and it was restored and confirmed as above.

## THE STANDARD AUDIO TEST SET, FIRST RUN: MIC 5 → AUX 1 LOOP, T1–T8 + T4b (2026-09-16, session 54 — bench, MW-D24-2)

**Pair:** `s51_119ea9d9` (`DSP4_TEST_NODES=1`, no block tap; chip1 `119ea9d9…`, chip2 `c56ed0ab…`, md5 re-checked at
the end), already booted from S52. No reboot or flash, and nothing written to AN_EN. **Loop:** TEST_OSC on donor strip 6 → AUX 1 → DAC_08 →
J45 → cable → J25 → MIC 5 preamp → U39 → strip 20 post-fader → TEST_MEAS. MIC 5's register alone open, phantom off,
every image sent at p = 15 (`app cli chain-set 27 ch8:mute=M,gain=G ch24:mute=0 instr1=1`), **VERIFIED 200/200 on
all 141 logged loads**. Levels: osc = DSP digital peak on strip 6, which is also the DAC side (the gather's
Q4.28→Q1.31 shift makes 1.0 = DAC FS); lane = strip 20 Q4.28, 1.0 = ADC FS. **Loop gain = lane − osc, digital to
digital, not a preamp gain in volts.** +5 V/rails not taken (PW). Every number is TEST_MEAS: RmsResult / ThdResult /
NoiseResult / XtalkResult, plus the window's fit coefficients `_meas_a_`/`_meas_b_` (see S54-1). Data:
`MW/D24/DSP/s54/data/*.jsonl` (every window), `*.out` (as printed), `law64.md`; tools `MW/D24/DSP/s54/tools/`.

### Summary (the doc's rows, dB and % side by side)

| # | test | result | flags |
|---|---|---|---|
| T1 | gain law, 1 kHz, all 64 codes, lane pk −20…−6 dBFS | loop gain **+5.58 dB (code 0) → +58.72 dB (code 63)**, range 53.14 dB; **monotonic**; largest step **12.85 dB (code 0→1)**, smallest 0.061 dB (62→63); every code within **0.061 dB** of a six-stage linear-additive model (no stage mis-switching); three levels agree ≤ 0.019 dB (coherent). THD+N at lane −13 dBFS pk, code 0: −89.50 dB = 0.0034 % | RMS-based level spread 0.052 dB at code 63's lowest level (noise, > 0.05) |
| T2 | freq response re 1 kHz, osc −20 dBFS (code 0) / same lane level (code 16) | code 0: 20 Hz **−0.41**, 50 Hz −0.05, 100 Hz–15 kHz within ±0.07, 20 kHz −0.12 dB. code 16: 20 Hz **−0.60**, 50 Hz −0.10, 100 Hz–15 kHz within ±0.07, 20 kHz −0.12 dB | **20 Hz at code 16 beyond ±0.5 dB**; the LF corner moves with gain (20 Hz phase −172.8° → −163.5°) |
| T2 (max gain) | freq response re 1 kHz at **code 63**, osc −78.72 dBFS (lane −20.00 dBFS pk at 1 kHz) | 20 Hz **−2.06**, 50 Hz **−0.44**, 100 Hz −0.12, 200 Hz–15 kHz within ±0.07, 20 kHz −0.11 dB. THD+N −30.5 … −30.8 dB = 2.9–3.0 % at every point is the code-63 noise floor (−51.7 dBFS rms against a −23 dBFS rms tone), not distortion | **20 Hz −2.06 dB at max gain (FLAG)**; the LF roll-off grows with gain: 20 Hz −0.41 / −0.60 / −2.06 dB at codes 0 / 16 / 63 (phase −172.8° / −163.5° / −141.4°) |
| T3 | THD+N vs lane level, 1 kHz, code 0 | −60: −42.58 dB = 0.743 % · −40: −62.98 dB = 0.0709 % · −20: −82.48 dB = 0.00752 % · −10: −91.38 dB = 0.00270 % · −6: −92.59 dB = 0.00235 % · −3: −88.76 dB = 0.00365 % · **−1: −43.92 dB = 0.637 %** (noise-limited to −10) | **clip onset between lane −3 and −1 dBFS; no sample ever reaches FS** — the lane saturates at 0.979 FS (−0.18 dBFS) |
| T3 (min/max gain, 3 dB below clipping) | 1 kHz, lane −3.0 dBFS pk; code 0 osc −8.58, code 63 osc −61.72 (trimmed to −2.997 dBFS coherent peak) | **code 0: ThdResult −88.76 dB = 0.00365 %, NoiseResult −94.77 dBFS** (from T3) · **code 63: ThdResult −47.05 dB = 0.44437 %, NoiseResult −53.05 dBFS** (6 windows −46.69…−47.20). No sample at FS at code 63 (strip-20 block peak 0.716 = −2.90 dBFS) | code 63 is **noise-limited, not distortion**: NoiseResult −53.05 dBFS sits on the tone-off floor (−51.70 dBFS, T4), so THD+N = floor − signal. The distortion part at max gain can't be separated without a spectrum (S54-7) |
| T4 | noise floor, tone off | code 0 −104.29, 2 −84.91, 4 −77.72, 6 −75.00, 8 −70.22, 12 −67.49, 16 −63.03, 24 −60.12, 32 −56.58, 48 −53.45, 63 −51.70 dBFS; input-referred (floor − loop gain) −109.87 … −110.45 dBFS-eq at every code | — |
| T4b | EIN (reference, source = AUX 1 output stage ≈ 66 Ω: R1875 + R1876 = 33 Ω + 33 Ω, via C747/C748 and the cable) | code 63: NoiseResult −51.70 dBFS − loop gain +58.71 dB = **−110.42 dBFS-equivalent**, unweighted, DC–24 kHz (4,096-sample window, every sample), DAC idle noise included | reference only; not 150 Ω; no dBu (see S54-3) |
| T4 / T4b (REAL, source = 150 Ω across J25 pins 2–3, loop cable off) | tone off, 16–60 settling windows, 56 windows at code 63 and 32 at code 0, energy-averaged | **code 63: NoiseResult = RmsResult −87.97 dBFS** (median −90.34, quiet floor −91.99, bursts to −79.86) **→ input-referred −146.69 dBFS-eq** (median −149.06, quiet −150.71; divisor +58.717 dB). **code 0: −113.79 dBFS → −119.37 dBFS-eq** (divisor +5.578 dB; ADC/converter floor, not an EIN). **Side by side at code 63: reference (loop, ≈66 Ω) −110.42 vs real (150 Ω) −146.69 dBFS-eq**; lane −51.70 vs −87.97 dBFS. Unweighted, every sample of the 4,096-sample window, DC to 24 kHz (Nyquist; band edge set by the converters' own filters, not by a 20 Hz–20 kHz filter) | **intermittent bursts at code 63**: 11 of 56 windows sit more than 3 dB above the median, and they recur after settling, so it isn't a gain-switch transient; source not identified. The loop reference was **36 dB** worse than the real figure, so it measured the AUX 1 output stage and DAC idle noise, not the preamp. No dBu (needs J45 volts at DAC FS, S54-3) |
| T5 | polarity | phase intercept of the 1–2 kHz fit **180.2°** (1–10 kHz: 183.0°) → **INVERTED** round the loop | inverted |
| T6 | mute depth, register mute bit | **20.04 dB** at code 0 (coherent −20.00 → −40.04 dBFS pk), **20.03 dB** at code 2; five alternating arms repeat to 0.01 dB | **the mute bit only attenuates by 20 dB** |
| T7 | crosstalk, source lane −6 dBFS pk (code 2), 22 neighbour strips | none resolved: worst coherent reading strip 11 **−131.4 dB**, detector floor (no stimulus) **−135.2 dB** → **< −131 dB**; XtalkResult (energy, noise-limited) −102.2 … −107.2 dB | — |
| T8 | latency | **91.40 samples = 1.904 ms** (group delay, 1–2 kHz, residual 0.03°); 91.60 over 1–10 kHz, 91.95 over 2–15 kHz | — |

**S54-1. Method: the fit coefficients TEST_MEAS already computes give coherent level and phase, and they check
exactly.** `_meas_a_`/`_meas_b_` are the window's least-squares fit of strip 20 onto the oscillator's own s/c
reference. For the magic-circle recurrence (s' = s + k c, c' = c − k s') the reference phasors satisfy C/S = (z−1)/k,
z = e^{jω}, and the injected block is s·L·cos(ω/2) with |S| = 1/cos(ω/2). So H = (a + b·r)/(L·cos(ω/2)) is the complex
loop transfer. Its magnitude is below the noise (coherent over 4,096 samples), and its phase is −ωD plus the analog
phase. **Check: MeasChan = 6 (the digital reference) reads H = 0.000 dB, 0.000° at every one of eleven frequencies
from 20 Hz to 20 kHz**, while RmsResult on the same strip shows the known short-window error at 20 Hz (−22.933 vs
−23.010 dBFS). The coherent gain equals the RMS gain to 0.001 dB wherever the tone is 30 dB clear of the floor. This
is what T2's magnitudes, T5/T8's phase and T7's sub-floor crosstalk use. Peeks only, no cost on either chip. Window
count per point: settle 3–4 windows (8 at ≤ 50 Hz, 16 on the 20 Hz retake), then 3–6 untorn windows averaged.

**S54-2. THE DONOR STRIP WAS NOT TRANSPARENT, AND DRIVING IT HARD OVERRUNS CHIP 2 — the first T3 run is withdrawn.**
As found, strip 6 had **CompOn 1** and **MainOn 1** (S52 had made strip 20 transparent, not the donor). Two effects:
(a) above osc ≈ −19 dBFS strip 6's own compressor engages. Strip-6 digital THD+N goes −121.64 → −55.75 dB (0.163 %)
between osc −19.0 and −18.5, and the coherent level drops −0.26/−0.63/−1.38/−6.63 dB at −18.5/−18/−17/−10. This is
S49's C1_COMP_05 signature. (b) With the compressor off, the loop still broke at the same point: at code 0 the lane was
clean at osc −19.58 (THD+N −88.05 dB) and read **≈ 17 % (−15 dB) from osc −18.58 on**, with the fundamental still linear
and sample peaks 3.5 dB above it. It looked like a front-end overload. **It is not analog: chip 2 `_diag_blk_overrun`
+109 in 5 s at osc −15 and +0 at −20, chip 1 +0 in both.** Split by route at osc −15: **AUX only (MainOn 0) → 0
overruns, THD+N −91.70 dB = 0.0026 %; MAIN only (AuxOn 0) → +109.** So the chip-2 MAIN chain takes a more expensive
path once its input passes ≈ −18.5 dBFS, misses about 22 blocks/s, and the loop reads the block drops as distortion.
That is the S52-4 mechanism, triggered here by signal level rather than by the tap. Everything quoted above was taken
below that level or with MAIN off: T1 (64-code sweep), T3, the T1 code-0 row, T5/T8, T6 and T7 ran at osc ≤ −18.58 or
with MainOn 0. T2 ran at osc −20 with CompOn 1, below its threshold (digital reference 0.000 dB at every point).
**Hand-back leaves strip 6 CompOn 0 and MainOn 0 (was 1/1)**, so the donor is transparent and the MAIN chain
unstimulated. Stated here because it is a changed cell. Which chip-2 MAIN node goes expensive, and by how much, is not
chased (next list). Side notes: (i) a TX DMA word read back as Q4.28 is 8× (+18.06 dB) the node value, because
`_gather_chip2` shifts Q4.28→Q1.31 with saturation (`chip2/block_io.asm:343`). A peek decode that forgets this reads a
DAC-lane level 18 dB high; S48-4's "×8 / saturates at 1.006" figures are worth re-reading with that in mind. (ii)
`_mtr_peak_C2_MTR_AUX_01` reads a constant +18.06 dBFS (8.0, the Q8.24 ceiling) at every level, so it does not
measure the aux lane.

**S54-3. T1 over all 64 codes, T4 and T4b (hub addenda 09:41 and 09:58).** Per-code table (osc level, lane RMS,
coherent peak, loop gain, gain re code 0, model, THD+N dB/%) in `data/law64.md`. Loop gain, dB:

| code | +0 | +1 | +2 | +3 | +4 | +5 | +6 | +7 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 0–7 | 5.58 | 18.42 | 25.04 | 27.71 | 32.47 | 33.71 | 35.27 | 36.18 |
| 8–15 | 39.93 | 40.47 | 41.22 | 41.69 | 42.87 | 43.26 | 43.81 | 44.16 |
| 16–23 | 47.17 | 47.41 | 47.75 | 47.98 | 48.56 | 48.77 | 49.06 | 49.26 |
| 24–31 | 50.23 | 50.40 | 50.64 | 50.80 | 51.23 | 51.38 | 51.60 | 51.74 |
| 32–39 | 53.74 | 53.86 | 54.02 | 54.13 | 54.42 | 54.52 | 54.67 | 54.78 |
| 40–47 | 55.30 | 55.39 | 55.53 | 55.62 | 55.86 | 55.95 | 56.08 | 56.16 |
| 48–55 | 57.00 | 57.08 | 57.19 | 57.26 | 57.47 | 57.54 | 57.65 | 57.72 |
| 56–63 | 58.09 | 58.15 | 58.25 | 58.32 | 58.50 | 58.56 | 58.66 | 58.72 |

**The stages add in LINEAR gain, not in dB** (parallel-switched feedback resistors, G = 1 + Rf·Σ bit/R). A weighted
least-squares fit G = 1.901 + Σ bitᵢ·dᵢ with d = 6.441, 15.970, 40.128, 97.069, 225.388, 481.791 (bits Q2…Q7 alone
+12.85/+19.46/+26.89/+34.33/+41.55/+48.11 dB over code 0) **misses no code by more than 0.061 dB (mean 0.020)**, so no
stage is failing to switch and there are no flags. Consequence for the table: the steps are uniform in voltage, so in
dB they crowd at the top. Sorted, the 63 steps run from 0.061 dB (62→63) to **12.85 dB (0→1)**; the gaps above 2 dB
are 0→1 12.85, 1→2 6.62, 3→4 4.76, 7→8 3.75, 15→16 3.01, 2→3 2.67, 31→32 2.00. Repeatability: codes 30–50 were taken
twice, and the two runs agree within 0.005 dB. Run 1's codes 51–55 walked off and are excluded. That guard read a
noise-limited THD+N as clipping and stepped the oscillator down to nothing (`t1all_part1.out`); the fixed guard judges
on level only. **First-cut trim table** (gain re code 0, hw = largest ≤ target, trim ≥ 0; sample 1 of the averaged
table, channel = MIC 5 / J25 / U39, unit MW-D24-2 rev C): 0–12 dB → code 0 + 0…12; 13→c1+0.15, 14→c1+1.15,
15→c1+2.15, 16→c1+3.15, 17→c1+4.15, 18→c1+5.15, 19→c1+6.15, 20→c2+0.54, 21→c2+1.54, 22→c2+2.54, 23→c3+0.86,
24→c3+1.86, 25→c3+2.86, 26→c3+3.86, 27→c4+0.10, 28→c4+1.10, 29→c5+0.87, 30→c6+0.31, 31→c7+0.40, 32→c7+1.40,
33→c7+2.40, 34→c7+3.40, 35→c9+0.11, 36→c10+0.36, 37→c11+0.89, 38→c13+0.32, 39→c15+0.42, 40→c15+1.42, 41→c15+2.42,
42→c17+0.17, 43→c20+0.01, 44→c23+0.32, 45→c25+0.18, 46→c29+0.20, 47→c31+0.84, 48→c31+1.84, 49→c37+0.05,
50→c42+0.05, 51→c47+0.41, 52→c53+0.04, 53→c61+0.02, 54–60→c63+0.86…+6.86. **The largest trim inside the hardware
range is 12.0 dB, below 12.85 dB re code 0, where only code 0 exists.** The 0–60 dB product law needs +6.86 dB of trim
above code 63, because the hardware spans 53.14 dB. If the law's 0 dB is meant to be code 0's absolute gain, that
needs volts (below).
T4 floors are in the summary. **Input-referred, they are flat at −110.3 ± 0.2 dBFS-eq from code 2 up (code 0 −109.87).**
So the floor is set before the switched gain: DAC idle noise plus the preamp's input noise, which this loop cannot
separate. **T4b reference** at code 63: −51.70 dBFS (four windows −51.55/−51.82/−51.66/−51.78) − 58.71 dB
(58.717 in the 64-code sweep) = **−110.42 dBFS-equivalent**. With the tone off the reference is zeroed, so NoiseResult
equals RmsResult in every window: the energy of every sample of the 4,096-sample post-fader block. That is unweighted,
DC included, band-limited only by the converters' filters (0–24 kHz at 48 k), with strip 20's EQ/HPF off. Source:
AUX 1 output stage, U82 NJM4580 through C747/C748 and **R1875/R1876 = 33 Ω each (BOM, 1 %)**, so ≈ 66 Ω across pins
2–3 plus the cable. That is not 150 Ω, and the DAC's own idle noise is in the figure, so it is an upper bound. **No
dBu:** the loop gain is referred to the DAC's digital FS, so the noise lands in DAC-FS terms. A dBu figure needs the
**J45 output voltage at DAC FS**, not the AK5558's input FS. The only documented statement found (mx26
`backlog-d24-schematic-errata.md`) says the converter FS follows AVDD and gives no volts, so no conversion is claimed.

**S54-3b. T4/T4b WITH THE 150 Ω SOURCE (added after the swap, PW fitted 150 Ω across J25 pins 2–3, loop cable off).** Negative check first: 1 kHz −20 dBFS on AUX 1 at code 0 put the lane's coherent peak at **−145.12 dBFS** (−14.42 with the loop), so the loop is gone. Tone off, strip 20 post-fader, MeasChan 20, strip 20 EQ/HPF off; NoiseResult equals RmsResult in every window, because with the reference zeroed there is nothing to fit. **Code 63:** first pass 8 windows after 16 settling windows read −87.37 … −79.86 (10 dB spread). Retake 24 windows after 60 settling windows: −92.2 … −86.3. A third 24 with no re-switch: −92.2 … −81.3. Pooled 56 windows, energy average **−87.97 dBFS**, median −90.34, quietest quarter −91.99. **Input-referred with the T1 divisor +58.717 dB: −146.69 dBFS-eq (energy average; −149.06 median, −150.71 on the quiet floor).** The bursts (11 of 56 windows > 3 dB above the median, up to +10 dB) come back with no control change, so they are real pickup or interference, not settling after the gain switch; the quiet floor is the preamp. **Code 0:** 32 windows, energy average **−113.79 dBFS** (−115.08 … −111.52) → −119.37 dBFS-eq with +5.578 dB. At 5.6 dB of gain this is the converter's own floor, not an EIN. **Reference vs real at code 63: −110.42 (loop, ≈66 Ω, DAC and output-stage noise included) vs −146.69 dBFS-eq (150 Ω).** The loop reference overstated the input noise by 36 dB. Code 0 moved −104.29 → −113.79 dBFS. **Units:** dBFS-eq is referred to the DAC's digital full scale through the loop gain measured before the swap (the same divisor for reference and real, as the addendum specified). Unweighted, full band to 24 kHz (Nyquist), no 20 Hz–20 kHz band limit and no A-weighting. A dBu figure needs the J45 voltage at DAC FS (S54-3), not claimed. Data: `data/s54_t4_150r*.jsonl`, `data/t4_150r.out`.

**S54-4. T2 frequency response, T8 latency, T5 polarity.** Coherent magnitude re 1 kHz (loop +5.578 / +47.170 dB):

| f | 20 | 50 | 100 | 200 | 500 | 1 k | 2 k | 5 k | 10 k | 15 k | 20 k |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| code 0, osc −20 | **−0.414** | −0.050 | +0.012 | +0.029 | +0.027 | 0 | −0.002 | −0.006 | +0.061 | −0.019 | −0.117 |
| code 16, osc −61.59 | **−0.604** | −0.100 | −0.009 | +0.021 | +0.026 | 0 | −0.001 | −0.002 | +0.065 | −0.016 | −0.118 |
| code 63, osc −78.72 | **−2.060** | **−0.442** | −0.120 | −0.008 | +0.021 | 0 | −0.000 | +0.004 | +0.065 | −0.016 | −0.113 |

The 20 Hz retake at 16 settling windows plus 6 read windows: code 16 −0.604 dB (6 windows 46.563…46.569), code 0 −0.414
(identical over 6). The first pass's code-16 20 Hz point had a 0.207 dB spread and a −23.7 dB THD+N. That was
settling, and the retake reads −47.05 dB, the same as 1 kHz. RmsResult with the digital reference subtracted
agrees within 0.07 dB (20 Hz −0.487, the 1.7-cycle window). The +0.06 dB at 10 kHz is in both gains, so it is a
converter-filter ripple, not the preamp. **Code 63 (added after the first push, PW: response at MIN and MAX gain; loop still in place, 1 kHz lane −20.00 dBFS pk, 16 settling + 6 read windows at ≤ 50 Hz, 6 + 4 above; per-point spread ≤ 0.05 dB): 20 Hz −2.06 dB and 50 Hz −0.44 dB**. So the LF corner rises steadily with gain. That fits a gain-setting network with a coupling capacitor in its ground leg, whose corner scales with gain; inferred, not checked on the netlist. Above 200 Hz the three codes agree within 0.01 dB. At code 0/16, **only 20 Hz at code 16 exceeds ±0.5 dB**, and the corner moves with gain
(20 Hz phase −172.8° at code 0, −163.5° at 16). **T8:** unwrapped phase at 1.0…2.0 kHz in 100 Hz steps, then 2.5–15 kHz:
slope → **91.40 samples = 1.904 ms**, max residual 0.03° over 1–2 kHz. That is the whole loop: DSP blocks, inter-chip
fabric, DAC and ADC filters, analog. The HF fits (91.60 to 10 kHz, 91.95 to 15 kHz, residual 4°/16°) show the
converter filters' group delay rising. **T5: the intercept is 180.2° (183.0° to 10 kHz), so the loop INVERTS.** Strip 6
and strip 20 both have Pol 0. The inversion is somewhere in DAC → U82 → J45 → cable → J25 → preamp → ADC; one pin-2/3
swap anywhere does it. Not localised (next list).

**S54-5. T3 THD+N vs level and the clip point (code 0, strip 6 AUX-only).** Full table in `data/t3_auxonly.out`;
summary row above, plus −30 −73.17 dB, −18 −84.14, −16 −86.59, −14 −88.48, −12 −90.29, −8 **−92.80 dB = 0.00229 %**
(best). Up to −10 dBFS the residual is the −105 dBFS floor (NoiseResult −105.2 ± 0.4). From −6 the residual rises
(noise −101.6, −94.8 at −3). At −1 dBFS it is −43.92 dB = 0.637 %, then 2.57 % at −0.5 and 4.67 % at 0. **The peak
meter (`_mtr_peak_C1_MTR_20`, strip 20's gain-stage block peak) never reaches FS:** 0.885 at −1, 0.914 at 0, 0.970
at +2, a maximum of 0.979 (−0.18 dBFS) at +4. So the ADC's full scale is not reached in this range; something before
it saturates at ≈ 0.98 FS. Code 2 agrees (`knee.out`): lane −1 dBFS −80.28 dB = 0.00968 %, lane 0 −34.38 dB = 1.91 %
with the meter at 0.958. The code-2 points below −6 dBFS in that file follow a code change and had not settled.
**Clip point: THD+N passes 1 % between lane −1 and −0.5 dBFS pk; no sample at FS up to osc −0.58 dBFS.** **Max gain (added after the first push, PW: THD+N at min and max gain, 3 dB below clipping):** code 63, oscillator trimmed from the T1 level to −61.717 dBFS so the lane's coherent peak reads −2.997 dBFS; after 8 settling windows, six windows read ThdResult −46.69/−47.07/−47.10/−47.18/−47.04/−47.20 dB, mean **−47.05 dB = 0.44437 %**, NoiseResult **−53.05 dBFS**. The block peak meter reads 0.716 (−2.90 dBFS), so **no sample at FS**. The residual is the channel's own floor (−51.70 dBFS tone-off at code 63), so this is the noise-limited THD+N of a 58.7 dB gain, not a distortion figure. At code 0 the same −3 dBFS point (already in T3) is −88.76 dB = 0.00365 %, NoiseResult −94.77 dBFS. The loop was still in place at the time (`data/t3c63.out`).

**S54-6. T6 mute depth and T7 crosstalk.** T6: five arms open/muted/open/muted/open, the register mute bit alone
(byte 0x00↔0x01 at code 0, 0x08↔0x09 at code 2), 200/200 each. **Muted = −20.04 dB at code 0 and −20.03 dB at code 2**,
coherent and RMS agreeing, every arm repeating to 0.01 dB. As a mute that is shallow: either the bit is a −20 dB pad,
or a leak path around the mute switch sits at −20 dB. Tone-off floor muted −110.76 vs open −101.08 dBFS at code 0. The
open floor here is 3 dB above T4's; residuals after each mute toggle took several windows to settle (THD+N −82.5 →
−61.3 dB over the arms). T7: code 2, source lane −6.00 dBFS pk (osc −31.04), every other strip 1–24 except 6 (donor)
and 20 brought to unity for its own read and restored after (all 22 as found, Mute 1). Coherent readings −131.4
(strip 11) … −147.9 dB; the control is strip 11 with the reference running and OscChan 0: −135.2 dB. **No neighbour
resolves above the detector floor, so crosstalk is < −131 dB** at 1 kHz. XtalkResult (energy ratio) −102.2 … −107.2 dB
is the neighbours' own floors (−111 … −116 dBFS rms) against −9 dBFS.

**S54-7. There is no zero-cost capture on a no-tap pair, so no FFT this session; gate 0 is done.**
`_scope_record` survives in the no-tap build and runs per sample on chip 1 only. But it records `_buf_<node>[idx]`,
and under block kernels that is the node's STATE block, not audio. Captured on the part (`_buf_C1_FDR_20`, 1024
samples): +5.95 dBFS of parameter words (0.5, 3.96875, …), 63 distinct values. The audio lives in the shared
`_blk_pool` slot, which the next strip overwrites. **Proposal for a legitimate FFT source:** a `TEST_MEAS` capture
arm. `_test_meas_tap` already holds MeasChan's post-fader pool slot in r1; when a CapArm word is set, copy its 16
words into a 1024-word `_meas_cap` and clear CapArm when full. The host reads `_meas_cap` by peek, which
`dsp4_fft.py` takes unchanged. Cost: chip 1 only, one compare per block idle and a 16-store loop per block while armed;
chip 2 nothing. It needs one cell (or a diag word, per the S48 no-new-register rule) and the ADDRESS SPACE question
goes to the hub. The CPLD's Pi PCM lane is the second option; it needs a bitstream with a capture path and the duplex
overlay (bench recipe 5/5a/12). **Gate 0:** `tools/pi/dsp4_s49_osc.py` now prints `ThdResult … dB = x %` per window and
settled, and `tools/pi/dsp4_fft.py` prints THD+N, THD and every harmonic in dB **and** %. Both were run: on the part
(`ThdResult −78.86 dB = 0.01140 %`) and on S52's capture (`THD+N −85.40 dB = 0.00537 %`, h2 −91.54 dBc = 0.00265 %).
`--selftest` passes. Staged at `~/s54` on the bench, not over the pair directories.

**Hand-back (loop phase complete, then the 150 Ω phase run and done; holding):** `s51_119ea9d9` pair
running (not rebooted), `_diag_blk_overrun` +0/+0 in 5 s on both chips. **AN_EN (GPIO26) `op pd | hi`, never
written.** CS_M (GPIO27) `op pu | hi`, driven by `chain-set` as before. matrix-app inactive (as found). MIC 5 alone
open at **code 0**, phantom off (`[15] ch8 0x00`, 200/200). TEST_OSC **1 kHz −20 dBFS pk on strip 6 → AUX 1**,
MeasChan 20, Xtalk 0/0: RMS −17.43 dBFS, ThdResult −87.80 dB = 0.00407 %, NoiseResult −105.23 dBFS. **Strip 6 CompOn 0
and MainOn 0 (changed from 1/1, S54-2).** Strips 1–24 other than 6 and 20 muted as found. `~/s54` holds the tools
and logs; `~/s51_119ea9d9`, `~/s52`, `~/dspboot` untouched.

## THE LITERAL TABLE COPY IN gen_dsp.py IS RETIRED; THE MASTER IS THE ONLY SOURCE (2026-09-16, session 53)

**S53-1. `gen_dsp.py` no longer carries a hand-typed second copy of the
master's `Table` column.** Every `add_cell()` call site (86 call sites,
five of them via `params`/`more` tuple lists that also carried a `tbl`
element) passed a literal Table string; `backfill_matrix()` then wrote
`row['Table'] = cm['table']` over whatever the matrix expansion had
already put there from the master. Both are deleted: the `table=`
argument is gone from every call site (the tuple lists lost their table
element and the two loops that unpacked it), and `backfill_matrix()`'s
Table branch is gone. `add_cell()` keeps a `table=''` parameter for
signature stability but nothing sets it; `_matrix.csv`'s `Table` column
now carries only what `defs/tools/expand_matrix.py` put there from
`defs/common/cells/mx_master.csv`, unmodified by this repo. Where the
master is blank, the matrix stays blank (R1).

This also retired the SAME duplicate one layer up: `check_proposal()`
(the graph-vs-landed drift gate for `defs/products/<p>/dsp.csv`) compared
`Table` between the graph and the already-landed proposal file byte for
byte. With the graph no longer computing a Table opinion, that comparison
would fail permanently on every run (the landed file still carries the
historical, literal-derived strings). `check_proposal()` now excludes
`Table` from the per-cell equality check, with a comment stating why;
every other column (address, ramp, access, notes) is still compared
exactly as before. `write_ghost_cells_h()`, `write_address_map()` and
`_dsp_csv_row()` were NOT touched and did not need to be: `main()` swaps
`cell_map` for `load_landed_address_map()` (the merged, hub-approved
`defs/products/<p>/dsp.csv`) before any of them run, so the firmware
`ghost_cells.c`/`.h`, `dsp_address_map.md` and `mx_dsp_map.h` were already
reading Table off the landed contract, not off the graph's literals —
confirmed by regeneration below: none of those four files changed.

**Correcting the record**: commit `e5182547` ("S47 — consume
defs-v2026.09.14.1") states *"733 D24 Table-field corrections trace to
defs@5cc5d44, not to this repo's tooling."* That is wrong.
`defs@5cc5d44` (2026-09-14, the Neutral-column commit) changed no Table
strings — checked by diffing its parent against itself for the `Table`
column of every product master, zero changes. The 733-field mismatch was
this repo's own `gen_dsp.py`: S47's `--force` landing overwrote the
matrix's master-sourced Table with the generator's hand-typed literals on
every row where they differed, exactly the defect this session retires.

**S53-2. Regeneration proof.** Consumed `defs-v2026.09.16.2` first (per
dispatch: 31 previously-blank family-A Table strings filled, provisional)
via `./sync-defs.sh --update-lock`, then `./regenerate-dsp-contract.sh
--update-lock`. Before/after, keyed by `_Cell`, every column:

| product | rows | Table changed | any other column changed | DSP address changed |
|---|---:|---:|---:|---:|
| D12 | 2334 | 22 | 0 | n/a (not backfilled) |
| D16 | 3316 | 23 | 0 | n/a (not backfilled) |
| D24 | 4998 | **702** | 0 | 0 |
| D32 | 7012 | **918** | 0 | 0 |

Every changed field, on every product, is `Table` and nothing else; D24
and D32's changed rows now read the master's string (spot-checked against
`mx_master.csv` for the families the hub audit named —
`Chan[1-64]EqQ[1-4]` reads `0=0.1/120=10/[Log][2dp]`, matching). D12 and
D16 are not DSP-backfilled, so their 22/23 changed rows are purely the
`defs-v2026.09.16.2` master content landing through the ordinary
expansion, not this session's `gen_dsp.py` change.

**702 is not 733.** The hub audit's 733 was measured against
`defs-v2026.09.16` (family A's 31 strings still blank in the master); this
session was told to consume `.2` first, which fills exactly those 31
strings. A number of D24's previously-corrupted family-A rows therefore
now read a real master string where the audit's snapshot would have
compared literal-vs-blank, shifting which rows land in the "changed" set
and by how much. 702 is the true before/after count against the tag this
session actually built on; it is not a discrepancy in the fix, it is the
moving baseline the dispatch asked for.

`check-contract-drift.sh --strict` (run after committing) is clean:
`ghost_cells.h`, both `dsp_params.asm`, `dsp_address_map.md`,
`mx_dsp_map.h` and the FW copies are byte-identical to before this
session — only the four `_matrix.csv` files, `gen_dsp.py`, `defs.lock`
and the `defs` gitlink moved.

**S53-3. New drift-check gate: Table's top breakpoint code vs
`MxDatS`−1, on the master (R3).** `check-table-mxdats.py`, wired into
`check-contract-drift.sh` (non-fatal — see below). It reads
`defs/common/cells/mx_master.csv` directly (one row per family, so this
is naturally family-level, not per-instance), extracts the top `N=`
breakpoint code from `Table` for every row where both `Table` and
`MxDatS` are present and `Table` is in the breakpoint form (the
stepped/scale-only forms — `dB:Off:-50@31:...`, `Pan:dB:0:Off` — carry no
comparable top and are skipped), and compares it to `MxDatS`−1.

Result: **190 master rows are comparable; 82 disagree.** The families the
hub audit named as the fixed case — `Chan[1-64]EqGain[1-4]` (121→120),
`Chan[1-64]EqQ[1-4]` (121→120), `Chan[1-64]Gain[1-1]` (61→60),
`Chan[1-64]GateRel[1-1]`/`CompRel[1-1]` (255→254) — all PASS this gate;
they are not among the 82. The 82 are a different, wider set this gate
newly surfaces: `CompMake`, `CompPar`, `LimiterAtt/Rel/Rng/Thr`,
`PeqGain`, `Geq`, `Delay`, `CrossoverFreq`, `EqLpf`, `*FilterLpf`,
`AntiFbNotch*`, `TubeSat`, `AntiClip`, `Decay`, `DelayTime`, `Feedback`,
`ModRate`, `PreDelay`, `EqLo/Mid/Presence`, `EqHpf`, `Duck*`, `Level`
(several bus families), `TalkGain`, `Test*Osc*` — 82 rows total, printed
in full by `check-table-mxdats.py`'s own output (captured in this
session's `check-contract-drift.sh --strict` log). Every one of them has
`Table` top code 127 regardless of `MxDatS` (which ranges 2–255 across
the 82) — a single, consistent pattern, not scattered noise.

**This does not match the "25/60 family exceptions" the dispatch
anticipated**, and this session does not know why: the family-D examples
the audit gave (which the hub evidently used to derive 25/60) all pass
cleanly, so the 25 the hub expects are not visible in this gate's output
at all. Two readings: either the "25/60" figure was scoped to a narrower
family set this gate's whole-master sweep does not reproduce, or the 82
found here are a real, previously-uncatalogued class of Table/MxDatS
disagreement (the flat 127-regardless-of-span pattern reads like
`MxDatS` recording a *display step count* while `Table` records the *raw
wire byte range* for these particular families — a real question, not
this repo's to resolve). Reported in full for the hub to reconcile scope
against; **the master is not touched.**

The gate is wired into `check-contract-drift.sh` as informational only —
it prints and exits 0. R3 asked for every violator reported by name, not
a new build blocker over a master-content question this repo does not
own; making it fatal would turn an open question into a hard stop on
every future regeneration until the master resolves 82 rows it may never
resolve to this rule (some may be intentional, like the 25 the hub
already expects).

**S52-1. The half-frame lane order is neither the reframer nor the frame-sync
edge. It is `D24_INPUT_PATCH`, the chip-1 input patch the host writes at
boot, and the part moves MIC 5 from lane 20 to lane 16 when it is replaced
by identity.** From source:

- `shared/dsp4-logic/rtl/dsp4_pcm_reframe.v` serves ONLY the Pi PCM lane
  (`i_dspa[6] = pcm_tdm`, `dsp4_logic_top.v:282`). The converter lanes are
  wires through the CPLD: `i_dspa[0..2] = ad[0..2]` (`dsp4_logic_top.v:276-278`,
  `net_sel = 4'b1000`, line 223). Nothing in the CPLD reorders their slots.
- There is no 50 % LRCK. `fs8` is a one-BCK pulse, high only in period
  `8'hFF` (`dsp4_clkgen.v:63-65`), and it is the converter frame sync
  (`conv_fs = fs8`, `dsp4_logic_top.v:342`). PW's hypothesis needs a 50 %
  LRCK, which this design does not generate. A 4-slot framing error would
  also keep slot k on the SAME SPORT; the measured map sends AD1's slots to
  lanes 5–8 and 17–20, i.e. to two different SPORTs' default strips, which
  no framing error can do.
- The SPORT setup is per-lane and uniform (`sport_config.c:87-105`: SLEN 31,
  CKRE=1, MFD from `lane_config.c:26`, 2 on converter halves), one DMA ring
  per lane (`dma_config.c:302-365`).
- The reorder is `tools/pi/dsp4_config.py:66-75`,
  `D24_INPUT_PATCH = [0,1,2,3,12,13,14,15] + [4,5,6,7,16,17,18,19] + [8,9,10,11,20,21,22,23] + …`,
  written to `INPUT_PATCH[i]` (0xF010+, lines 153-155) and applied by
  `_rx_patch_apply` at CONFIG_COMMIT (`product_config.asm:198`,
  `chip1/block_io.asm:723`). It maps packed AD lane k, slot s to strip
  `4k+s` (s<4) or `12+4k+(s−4)` (s≥4). That is exactly the measured map.
  `MW/D32/DSP/product-config.md` flagged it: *"verify the within-ADC8 slot
  order … the table assumes block order"*.

On the part (`s49tap` pair, MIC 5 = J25 open at gain 0, 1 kHz −20 dBFS on
AUX 1), rewriting only the patch and re-committing:

| patch | `_c1_rx_node_entry[16]` | `[20]` | lane 16 rms / peak | lane 20 rms / peak |
|---|---:|---:|---|---|
| D24 (as booted) | 7 | 15 | −116.26 / −109.53 | −15.70 / −14.25 |
| identity | 15 | 19 | **−19.37 / −14.68** | −113.53 / −108.10 |
| D24 restored | 7 | 15 | −119.83 / −112.90 | **−18.56 / −13.70** |

Identity puts J25 (AD1 slot 7) on C1_IN_16 = `sport_id=1;slot_start=7`,
exactly the dsp.csv row. **The SPORT framing is correct and the INPUT_TDM
rows are correct**; the wrong fact is the patch's in-converter slot order.
Reverted in the same run; the unit is on the D24 patch. (The lane readers
in `dsp4_s48_scan.py`/`s52_lanes.py` go through `_c1_rx_node_entry`, so
every "lane N" in S48–S51 means strip N after the patch, not dsp.csv's
`C1_IN_nn` sport/slot.)

**S52-2. Two fix proposals, not landed: `proposals/PROPOSAL-S52-INPUT-ORDER.md`.**
(i) The 595 image is transmitted head-first but lands tail-first (byte p →
chain index 24−p). **The SAFE image is not safe:** byte 0 (`0x00`, meant for
U34) lands on J42's register (mute OFF), and byte 24 (`0x01`) lands on U34
(INSTR1 ON). Every image with ch24 muted and instr1=0 (the safe image, the bench
restore scripts, every S48–S51 image) left J42 unmuted and INSTR1 asserted, and a phantom request goes to another
XLR. Consumers that must change together: mx26 `AnalogControlChain.cs`,
`CommandLine.cs` listings, `ChainSetSpec.cs` doc, `AnalogBringUp.cs` safe
load test, `app.Tests/AnalogControlChainTests.cs`, the two mx26 docs, and
the seven bench-Pi hand scripts that hard-code `0x00 + 24×0x01`. No
dsp-repo tool builds a 595 image. (ii) The input patch preset rewritten from
the netlist order: `[3,15,2,14,13,1,12,0] + [7,19,6,18,17,5,16,4] +
[11,23,10,22,21,9,20,8]`, with the full XLR ↔ slot ↔ packed index ↔ today's
lane ↔ proposed C1_IN table. Recommended over rewriting INPUT_TDM rows
because the rows are shared with D32 and are right; the row alternative is
stated there for PW.

**S52-3. The first measurement of the analog loop: DAC → AUX 1 → cable → J25
→ MIC 5 preamp → U39 → C1_IN_20.** Oscillator on strip 6 → AUX 1 at unity;
MeasChan = strip 20 at unity, comp/gate/EQ/tube off, off both buses; J25's
register alone open, phantom off (`chain-set 27 ch8:…`, the S51 send
position; 200/200 every time).

Level law (TEST_MEAS RmsResult on strip 20; loop gain = lane RMS − the
injected sine's RMS; `s49tap` pair; RMS is unaffected by S52-4):

| gain code (byte) | osc −20 dBFS | osc −40 | osc −70 | loop gain |
|---|---:|---:|---:|---:|
| 0 (`0x00`) | −17.45 | −37.44 | −67.44 | **+5.57 dB** (all three levels within 0.02 dB) |
| 8 (`0x20`) | — | −3.23 (at clip) | −33.07 | **+39.94 dB** (+34.37 over code 0) |
| 16 (`0x40`) | — | −1.33 (clipped) | −25.85 | **+47.16 dB** (+41.59 over code 0) |

At code 0 with the −20 dBFS peak tone, on the `s51_119ea9d9` pair (no chip-2
overruns, S52-4), MIC 5 lane, twelve windows:

| | value |
|---|---:|
| RmsResult | **−17.43 dBFS** (settled, ±0.01) |
| ThdResult | **−87.62 dB** (windows 6–12: −87.29 … −87.78; windows 2–5 still settling from −79.8) |
| NoiseResult (tone on) | **−105.06 dBFS** |
| RmsResult, tone OFF, 16 windows | **−104.20 dBFS** (settles from −76 through −102 in two windows) |

THD+N is noise-limited: the tone-on residual (−105.06) equals the tone-off
floor (−104.2) within a dB. From the capture on the tap pair (the one
capture whose chip-2 discontinuity fell in the window's first 150 samples,
where the 7-term Blackman-Harris suppresses it): `dsp4_fft.py` fundamental
**1000.0002 Hz, −17.43 dBFS; THD+N −85.40 dB; THD(2..10) −89.67 dB; h2
−91.54 dBc, h3 −100.28 dBc; noise −104.87 dBFS**. That agrees with the node
within 2.2 dB on THD+N and 0.19 dB on noise. It is an upper bound because
some burst energy leaks through the window. Time-domain fits over the
burst-free 621–866 samples of four captures give THD(2..10) −78 to −93 dB,
h2 −81 to −107 dBc, and a residual whose low-frequency part varies with
the recovery after each discontinuity. Every level above is dBFS at its own
side: oscillator = DSP digital peak; lane = chip-1 strip post-fader
(q4.28, 1.0 = converter FS). **The +5 V rail is PW's DMM item and was NOT
measured.** No absolute volts are claimed: 0 dBFS at the DAC and at the ADC
are not calibrated to each other or to dBu, so "+5.57 dB" is the digital
loop gain, not a preamp gain in dB.

Files: `MW/D24/DSP/s52/` (captures, FFT text + PNG, TEST_MEAS JSON, the
bench scripts as run).

**S52-4. On the `s49tap` build (TEST_NODES + SCOPE_BLK_TAP) chip 2 misses a
block every ~22 ms, and in the analog loop that looks like −12 to −14 dB
THD+N.** Chip 2 `_diag_blk_overrun` +223 in 5 s (≈45/s); chip 1 +0. The
chip-2 AUX 1 output capture (`_buf_C2_AUX_OUT_01`) is a clean −20.00 dBFS
sine broken by whole-block discontinuities at samples 384 and 1008. Through
the DAC reconstruction filter, the analog path and the ADC they arrive as a
~70–90 sample ringing burst at a fixed block phase. The burst repeats
sample-identical, because it is phase-locked to a 48-sample tone. Every
1024-sample capture of lane 20 held exactly one. TEST_MEAS over its
4,096-sample window read ThdResult −12.2 … −14.3 dB with NoiseResult
tracking RmsResult −12.3 dB at −20/−40/−70 dBFS and at codes 0/8/16:
signal-proportional, i.e. not noise. The digital control (strip 6 captured
on chip 1) was clean, and host SPI silence around the capture window
changed nothing (three quiet captures, burst still present), so it is not
link traffic. **On `s51_119ea9d9` (TEST_NODES, no tap) chip 2 reads +0
overruns in 5 s with the tone running, and the same loop reads −87.6 dB.**
Consequence: an analog THD+N taken on a tap build is chip 2's capacity, not
the analog path. The FFT capture and the clean TEST_MEAS figure need two
different builds until chip 2 has headroom for the tap.

Side notes, recorded not chased: (a) a foreground `/home/app/app` (running ~58 min at session start,
launched by an `app cli … ; /home/app/app | head -20` command line of
unestablished origin, with a `gpiomon GPIO4` child) was still running at session start and was stopped
before any boot. AN_EN and CS_M were unchanged by stopping it. (b) The DSP
parameter link shares SCK/MOSI with the 595 chain, so boot and link traffic
shifts garbage through the chain's shift stage (pass-1 MISO is never "the
previous image"). Only CS_M's rising edge latches, so the latched outputs
are unaffected, but a readback of "what was latched" is impossible by
design.

**Hand-back:** `s51_119ea9d9` pair booted and configured D24 (patch as
shipped), AN_EN (GPIO26) high, CS_M (GPIO27) `op pu` high, matrix-app stopped.
MIC 5 ALONE open at gain 0, phantom off, and truly alone given S52-2:
`app cli chain-set 27 ch8:mute=0,gain=0 ch24:mute=0 instr1=1` (200/200).
`ch8` reaches J25; `instr1=1` is the byte that lands on J42 = mute;
`ch24:mute=0` is the byte that lands on U34 = INSTR1/INSTR2 off; every other
register muted, gain 0. TEST_OSC 1 kHz −20 dBFS peak on strip 6 → AUX 1
(and MAIN), MeasChan = 20 (repeat under this exact image: −17.44 dBFS /
−87.59 dB / −105.03 dBFS). Strip 20 unity, dynamics off.

## RAW STEP-4 DATA: ONE 595 REGISTER OPEN AT A TIME, ALL 24 CHIP-1 LANES READ (2026-09-16, session 51, hub addendum 08:09)

**S51-4. For every send position `p` = 0..24, the lanes whose floor rose above −100 dBFS and the lane carrying the injected square.** Method: `app cli chain-set` sent one full 25-byte image per row — the one register named for that `p` at `mute=0,phantom=0,gain=63` (= byte `0xFC`), every other one of the 24 channel registers at `mute=1,phantom=0,gain=0` (= byte `0x01`) — verified 200/200 each time; then all 24 `C1_IN_*` lanes read (RMS + peak, one 16-sample window) with the 500 Hz/−6 dBFS square already held continuously on donor strip 6 → AUX 1 (armed since the prior addendum, confirmed still `ARM=1` throughout this run). No interpretation below, numbers as read:

| p | register (chain-set label) | lane(s) with floor > −100 dBFS: lane(rms dBFS/peak dBFS) |
|---:|---|---|
| 0 | `SHIFT` (U34; not a `ch<N>`, held at `0x00` in every image below — never isolated, not testable through `chain-set`'s `ch<N>:` syntax) | not tested |
| 1 | ch1 | L9(−68.7/−62.1), L20(−38.0/−33.4) |
| 2 | ch13 | L12(−65.8/−64.4), L20(−39.7/−34.5) |
| 3 | ch2 | L11(−76.5/−69.9), L20(−37.3/−32.4) |
| 4 | ch14 | L11(−89.6/−88.3), L20(−38.4/−33.7), L21(−74.6/−69.6) |
| 5 | ch3 | L20(−36.8/−32.4), L22(−77.0/−69.7) |
| 6 | ch15 | L20(−36.7/−32.9), L23(−73.6/−70.7) |
| 7 | ch4 | L20(−41.3/−34.7), L24(−74.0/−66.1) |
| 8 | ch16 | L6(−46.8/−45.9), L20(−38.6/−32.6) |
| 9 | ch5 | L5(−69.7/−61.8), L6(−83.4/−82.4), L20(−40.1/−32.8) |
| 10 | ch17 | L5(−77.8/−77.0), L8(−60.9/−60.0), L20(−37.3/−32.3) |
| 11 | ch6 | L7(−68.4/−65.8), L20(−37.6/−32.3) |
| 12 | ch18 | L7(−91.7/−90.6), L17(−80.7/−72.9), L20(−37.1/−34.0) |
| 13 | ch7 | L17(−95.1/−93.5), L18(−74.5/−67.6), L20(−38.2/−34.4) |
| 14 | ch19 | L18(−97.8/−96.0), L19(−77.7/−73.2), L20(−40.8/−37.8) |
| **15** | **ch8** | **L20(−0.6/−0.0)** |
| 16 | ch20 | L20(−43.0/−38.8) |
| 17 | ch9 | L20(−40.0/−35.4) |
| 18 | ch21 | L20(−38.5/−33.9) |
| 19 | ch10 | L20(−37.6/−32.3) |
| 20 | ch22 | L20(−38.8/−34.0) |
| 21 | ch11 | L20(−40.2/−35.6) |
| 22 | ch23 | L20(−39.6/−32.0) |
| 23 | ch12 | L20(−36.2/−32.5) |
| 24 | ch24 | L20(−37.1/−32.2) |

Lane carrying the square at ≈0 dBFS peak: **lane 20, at p=15 (register `ch8`) only.** Every other row's lane-20 reading sits at −37 to −41 dBFS (present on every row regardless of which register is open) and every other lane's reading sits under −100 dBFS except the scattered −60 to −98 dBFS entries tabulated above (also present regardless of which specific register produces them varying by row). Chain restored to the standing baseline (twelve channels unmuted at gain 16, verified 200/200) after the sweep; the injector was never touched during this sequence (`ARM=1` before and after, read directly, not inferred).

**S51-5. How `chain-set`'s send-position numbering maps to a register, stated from what the tool itself prints (`app cli chain-safe`'s own "SENT (MOSI, transmit order — chain position 0 first)" listing) cross-checked against `mx26/docs/d24-analog-xlr-map.md`'s netlist-derived "chain index" table (both tables below are the same 25 rows, by the same numbers, from two independent sources):**

| p (chain-set's printed position) | chain-set's own label | `d24-analog-xlr-map.md` chain index → XLR |
|---:|---|---|
| 0 | `SHIFT` | 0 → U34 (head, SER from the MCU) |
| 1 | ch1 | 1 → J15 |
| 2 | ch13 | 2 → J16 |
| 3 | ch2 | 3 → J17 |
| 4 | ch14 | 4 → J18 |
| 5 | ch3 | 5 → J19 |
| 6 | ch15 | 6 → J20 |
| 7 | ch4 | 7 → J21 |
| 8 | ch16 | 8 → J22 |
| 9 | ch5 | 9 → J25 |
| 10 | ch17 | 10 → J26 |
| 11 | ch6 | 11 → J27 |
| 12 | ch18 | 12 → J28 |
| 13 | ch7 | 13 → J29 |
| 14 | ch19 | 14 → J30 |
| 15 | ch8 | 15 → J31 |
| 16 | ch20 | 16 → J32 |
| 17 | ch9 | 17 → J35 |
| 18 | ch21 | 18 → J36 |
| 19 | ch10 | 19 → J37 |
| 20 | ch22 | 20 → J38 |
| 21 | ch11 | 21 → J39 |
| 22 | ch23 | 22 → J40 |
| 23 | ch12 | 23 → J41 |
| 24 | ch24 | 24 → J42 |

**The first byte sent (`p=0`) lands in chain index 0, `SHIFT`/U34 — the head register, SER driven directly by the MCU** — per `chain-safe`'s own printed position `[0]`, which is the only position not carrying a `ch<N>` label in either table. Every subsequent send position `p` (1..24) is followed by `chain-set`'s own printed `ch<N>` label at that exact position, and that same `p` value indexes the identical XLR in `d24-analog-xlr-map.md`'s independently-netlist-derived chain-index column, row for row — stated as the observed correspondence between the two sources, nothing beyond that read here.

## THE GATE-RANGE INITIALISER FIXED FROM THE ROW; THE OPEN-CHAIN RE-SCAN STILL FINDS NO ANALOG RETURN (2026-09-16, session 51)

**S51-0. Priority insert (hub addendum 06:53, PW's go): all twelve channels
open at gain 16 still show no lane carrying the AUX 1 square — but four of
them (5, 7, 9, 11) sit 25-30 dB above the other eight's noise floor, a
pattern S48-25's ch5-only condition could not show.** Sequence run: chain
SAFE (verified 200/200) → AN_EN raised by hand (GPIO26 `op dh`; CS_M/GPIO27
untouched, stayed `op pu` hi throughout) → S48's square-generator tap pair
staged (`s48sq_81f4f954`, md5 `81f4f954…`/`530db1e3…`, chosen over the
addendum's named `s48tap_289421ed` because that pair's map has no
`_scope_sq_phase`: it is the step/DC injector build, not the square one —
`dsp4_s48_scan.py`'s own default symdir already points at `s48sq_81f4f954`)
→ donor strip 6 routed to AUX 1 (`dsp4_apply_strip.py 6 1`, 13 ok / 0
mismatch; the first scan pass was run before this and its chip-2 AUX tap
read flat -inf while MAIN rose, i.e. the stimulus was on the wrong bus —
re-run after routing, kept as the recorded pass).

All twelve unmuted at gain 16, phantom off (`app cli chain-set`, verified
200/200), 500 Hz / −6 dBFS square from donor 6 (`_scope_inj_blk = 0x90330`,
fired), OFF/ON/OFF, three windows each:

| lane | OFF | ON | OFF again | ON peak |
|---|---:|---:|---:|---:|
| 1 | −116.99 | −113.92 | −115.86 | −108.37 |
| 2 | −115.38 | −116.24 | −116.73 | −109.53 |
| 3 | −118.59 | −116.46 | −116.67 | −108.93 |
| 4 | −116.57 | −115.42 | −116.22 | −108.65 |
| **5** | **−84.25** | **−84.76** | **−84.54** | −74.46 |
| 6 | −114.55 | −114.69 | −114.07 | −106.88 |
| **7** | **−88.44** | **−87.99** | **−87.69** | −82.11 |
| 8 | −113.80 | −115.30 | −114.38 | −108.10 |
| **9** | **−79.27** | **−80.75** | **−78.85** | −74.88 |
| 10 | −114.71 | −116.66 | −113.54 | −110.87 |
| **11** | **−85.31** | **−87.93** | **−88.27** | −80.58 |
| 12 | −112.99 | −115.17 | −114.79 | −108.93 |
| C2 RECV_MAIN_L (fabric, expected) | −130.44 | −42.14 | −130.94 | — |
| C2 RECV_AUX_01 (fabric, expected) | −131.00 | −42.14 | −132.93 | — |

No chip-1 lane rises on ON and falls on OFF-again by the tool's own >6 dB
both-ways test — the verdict column was blank on every one of the twelve.
The chip-2 fabric taps ARE the positive control this time (both MAIN and
AUX 1 rise ~89 dB and fall back, confirming the square really is on the AUX
1 bus once strip 6 is routed there) — a difference from the earlier S48-26
run, whose AUX tap only rose after the same routing step was added here.
**Lanes 5, 7, 9, 11 sit 25-30 dB above the other eight's ≈−115 dBFS floor,
FLAT across all three passes (not correlated with the stimulus)** — a
static noise-floor pattern, not a loop hit, and not visible in S48-25
because every channel but ch5 was muted there. Left as a finding for PW,
not interpreted further here: it groups four of twelve channels and its
shape (elevated but stimulus-independent) is consistent with a preamp
bias/gain-strapping difference on that group rather than anything the
injected square would explain.

**Like-for-like repeat, ch5 alone at gain 63 (the S48-25 condition), same
image, same routing:** lane 5 floor −73.62 / −71.44 / −72.36 dBFS (S48-25
recorded −72.51 / −71.78 / −73.35 — same channel, same order of magnitude,
reproduces), no lane carries the stimulus, same as S48-25. **S48-25's
conclusion stands under the open-chain condition PW asked for: opening all
twelve did not surface a J25 ↔ preamp misassignment on any of the eleven
quiet lanes.**

**What could not be answered here: the expected voltage at MIC 5's op-amp
pin 1.** The repo has no absolute-level reference for the DAC output —
`dsp4-s48-20260915.md` §4 states the DAC's full scale only in the DIGITAL
domain (`1.0 Q4.28`, the code that saturates it); no dBu/Vrms figure for
that code, and no dB-per-gain-code LAW for the preamp (only the dBFS
NOISE-FLOOR readback S48-27 recorded at codes 0/16/32/63, which
characterises the preamp's own noise tracking the code, not a calibrated
gain against a known input) is written down anywhere in this repo or its
docs. Computing a number would mean guessing a datasheet figure this
session has not verified — left for PW to read directly off the analog
board/DAC datasheet rather than stated here as fact.

**Hand-back for the addendum, exactly as asked: AN_EN raised and left up
(GPIO26 `op dh`), CS_M/GPIO27 never touched (`op pu` hi throughout), all
twelve channels unmuted at gain 16 (verified 200/200), the 500 Hz / −6 dBFS
square held continuously on donor strip 6 → AUX 1 (`dsp4_s48_drive.py …
--sq`, PID alive, GPIO busy to a second SPI open confirms it is holding the
link), matrix-app left stopped (it was stopped for the DSP boots and the
addendum does not ask for it back). PW's probe points: MIC 5 op-amp pin 1,
the ADC driver output, the AK5558 ch5 input pins.**

## THE GATE-RANGE INITIALISER, FIXED FROM THE ROW AND PROVEN ON THE PART (2026-09-16, session 51)

**S51-1. The initialiser now comes from the graph row, in each word's own
wire unit, with no hardcoded constants left in the gate's `.var` block**
(`tools/dsp/dsp_codegen.py`, new `gate_init_words()`, consumed by
`gen_gate_fixed`). Three different treatments, by what the wire actually
carries:

- **`threshold`/`range` stay DECIBELS.** The block-rate body already
  converts them every block (D39's `_exp2q_fx` path for range, the same
  `_C_DB2L2Q25` scale for threshold) — a host write lands a dB number, so
  the initialiser only has to carry the row's dB literal directly. This
  is the actual S49-3 fix: the old literal was `0.001`, a stale LINEAR
  floor left over from before D39 was fixed for the conversion CODE but
  never for the INITIALISER — today's kernel reads that `.var` as dB, so
  an un-written gate closed to 0.999885 gain (0.001 dB) where the row
  says `range_db=60.0`. The new literal is the row's own `60.0`.
- **`attack`/`release` do NOT get a block-rate conversion** (finding D41:
  "ms vs one-pole alpha, no conversion in this repo") — the wire word IS
  the one-pole alpha `_envq_fx`/`env_step` multiplies straight in
  `env += a*(target-env)`. Pre-converted in Python at codegen time from
  the row's `attack_ms`/`release_ms` instead, using the standard
  per-sample coefficient for THIS update rule — `a = 1 - exp(-1/tau)`,
  `tau = ms * fs / 1000` — the reciprocal sense of the OTHER one-pole
  convention (`y = c*y_prev + (1-c)*x`) that `dsp_simulate.py`'s
  `_ms_to_tc` happens to compute; the two are not interchangeable and
  the wrong one would have made the row's `attack_ms=1.0` land as an
  alpha of 1.0 (never moves). Cross-checked against
  `tools/pi/dsp4_conform.py`'s own `alpha_ms()` predictor, already used
  on the bench to verify live GateAtt/GateRel writes and citing the same
  formula from `dynamics.asm` — the codegen's pre-converted default and
  the bench's independent conformance predictor now agree by construction,
  not by coincidence.
- **`hold` is SAMPLES**, also unconverted on the wire (`_gate_holdq_`
  under `DSP4_PAIRED_GRAPH` just copies `_gate_hold_`) — pre-converted the
  same way, `round(hold_ms * fs / 1000)`. The row's `hold_ms=50.0` gives
  2400, the exact value the old hand-written literal already carried —
  a check that the new formula reproduces what the previous author must
  have computed by hand.
- **`on` is NOT taken from the row** (no product's GATE row carries an
  `on` key today) but from the MASTER's documented power-on default
  (hub ruling R2): `defs/common/schema/mx_master.md`'s `Neutral` column
  derivation lists `GateOn` under "bypassed / off = 0". An un-written
  gate is therefore a true bypass (`.gate_bypass_`, the input passed
  through with no envelope, no smoothing, nothing) rather than the old
  `on=1` — which, combined with the range fix, would have put every
  un-written strip's gate ACTIVE with a 60 dB floor at boot. Flagged per
  R2 rather than shipped: see S51-3.

`gate_init_words()` is called once per GATE node from its own
`node['params']`; regenerating (`python3 tools/dsp/dsp_codegen.py
MW/D32/DSP/SHARC/dsp.csv MW/D32/DSP/SHARC/src --force`) touched exactly
the 36 GATE nodes (32 `C1_GATE_*` + 4 `C2_GRP_GATE_*`) and nothing else —
`./check-sharc-codegen-drift.sh` passes clean against the regenerated
tree. Every other generator (`COMPRESSOR`, `LIMITER`) still carries its
old hand-picked `.var` literals; this dispatch's scope was the gate only
(R1 names it explicitly), so they are untouched and not claimed fixed.

**S51-2. Proven on the part, strip 5, digital loop only (S49's TEST_OSC /
TEST_MEAS pair, `DSP4_TEST_NODES=1`, built fresh from the fixed generator —
md5 `119ea9d9…`/`c56ed0ab…`, staged at `/home/app/s51_119ea9d9`, identity
confirmed by `DIAG_BUILD_CFG2 raw2 = 0xC3010244` matching S49's arm A).
Before/after, strip 5, 1 kHz, reading `RmsResult` and peeking
`_gate_rngq_C1_GATE_05` through the FRESH symbol map (never the stale
default):**

| condition | RmsResult | delta vs baseline | `_gate_rngq_` |
|---|---:|---:|---:|
| baseline: `GateOn` left at its power-on default (0) | −63.02 dBFS | — | 0x00000000 (never converted — bypass never reaches the block-rate section) |
| `GateOn` ← 1 (everything else at row default) | — | — | 0x00041894 ≈ 0.0010000·2^28 = **−60.00 dB** |
| 1 kHz at −60 dBFS peak, below the −40 dB threshold, SETTLED (2 s, ≫ the row's 100 ms release τ + 50 ms hold) | **−122.92 dBFS** | **−59.90 dB** | (as above) |
| 1 kHz at −20 dBFS peak, above threshold, SETTLED | −23.01 dBFS | 0.00 dB (open, unity) | — |
| `GateRng` ← 20.0, back to −60 dBFS, SETTLED | **−83.01 dBFS** | **−19.99 dB** | 0x0199999A = 0.1·2^28 exactly = **−20.00 dB** |

The first pass at this table (not reported above) read only −37.92 dB and
0.00 dB closed for the 60 dB and 20 dB cases respectively — a REAL but
PARTIAL transient, caught by re-reading with the row's own attack/release
time constants in mind (release τ ≈ 100 ms; the gain smoother needs several
τ to converge, not the ~250 ms the first pass allowed) rather than reported
as the answer. Left in the record as the reason the script settles for 2 s
now, not because the number was wrong for what it measured.

**S51-3. The audio change, stated plainly (R4).** Two independent things
move, and only the second is audible on a booted-but-unconfigured strip:
(1) every gate's `.var _gate_range_` now reads the row's documented depth
in dB instead of a stale linear-floor literal misread as dB — this only
matters on a strip whose `GateOn` a host has written to 1, where it is the
difference between a working gate (closes ~60 dB, as measured above) and
one that was previously inert (closed to 0.001 dB, inaudible); (2) `on`'s
default flips from `1` (active, but accidentally inert because of (1)'s
bug) to `0` (true bypass, per the master's documented off default, R2). On
a D24, where "nothing writes per-strip node state" (S38-5) and every strip
today runs on its build-time initialiser, (1) and (2) together mean: every
un-written strip's gate goes from "quietly running with negligible ~0.001 dB
gain modulation" to "fully bypassed, zero gate processing" — inaudible
either way, since 0.001 dB is below any audible threshold, so NO strip's
steady-state gain changes as shipped. What changes is any strip a host
DOES turn on: before, `GateOn=1` alone produced an inert gate regardless of
`GateRng`; after, `GateOn=1` produces a REAL gate at whatever depth the row
(or a later host write) names. Chip 1 and chip 2 cycle/word budgets: **0
words, 0 cycles moved on either chip** — the fix changes only the literal
VALUE already stored in six existing 32-bit `.var` slots per gate node
(`on`, `threshold`, `attack`, `release`, `hold`, `range`); it adds no `.var`
declaration, no instruction, and the regenerated `.asm` diff for all 36
gate nodes is confirmed to touch nothing but those literals and one added
comment block (`git diff --stat`: 432 insertions / 144 deletions across 36
files, all inside the `.var` block). A freshly rebuilt SHIPPING image
(`DSP4_TEST_NODES=0`, this fix applied) reproduces S49's own recorded arm-0
sizes byte for byte — chip1.ldr 451,892 B, chip2.ldr 307,980 B — which is
what "0 words moved" predicts and is not a coincidence: a `.var` literal is
always one 32-bit DM word regardless of what the source text says.

Per hub ruling R2: **flagging for the hub, to carry to PW** — the master
documents `GateOn`'s neutral/power-on code as bypassed (0), and this
dispatch ships that rather than the row's implied active default,
specifically BECAUSE the row carries no `on` key of its own and the fixed
`GateRng` default would otherwise put every un-written strip's gate active
at 60 dB depth. If any product wants an un-written strip's gate ACTIVE by
default, that needs its own row key (`on=1` in the graph) or a master
ruling that overrides R2 — not a generator default.

## defs-v2026.09.16 CONSUMED, EVERY MATRIX COMMITTED (2026-09-16, session 50)

**S50-1. The pin advanced to `defs-v2026.09.16` (`invirco/defs@084dbc1`) and
all four `_matrix.csv` are committed with the thirteen new `Test[1-1]*`
cells, strictly additive.** Recipe run exactly per R1: `git -C defs fetch
--tags && git -C defs checkout defs-v2026.09.16`,
`./regenerate-dsp-contract.sh --update-lock`, `./check-contract-drift.sh
--strict`. Row counts before/after: D12 2,321→2,334, D16 3,303→3,316, D24
4,985→4,998, D32 6,999→7,012 — +13 on every product, 0 removed. The Test
rows sit mid-file in each product's cell master (MxAdd 2288–2300 / 3262–3274
/ 4863–4875 / 6922–6934 respectively), so every row at or above that point
shifts by a uniform **+13**: 34 rows on D12, 42 on D16, 123 on D24, 78 on
D32 — the per-build address contract working as designed. Checked by name,
not position: joining every product's before/after matrix by `_Cell`, **0 of
2,321/3,303/4,985/6,999 pre-existing rows differ in `DspSpi`/`DspPage`/
`DspAdd`/`DspAddHex`** — the SPI/DSP address columns, as opposed to the
per-build `MxAdd` host index, did not move on a single cell. The one class
that needed a deliberate step beyond the dispatch's predicted two-file diff:
`validate-matrix-contract.py`'s no-fallback family gate correctly refused
the unrecognised `Test*` families first (13 names, all four products) —
adopted intentionally with `--update-allowlist` (349/349/402/374 → same plus
the 13 Test families; D32's 361→374), per the hard rule. Diff is exactly:
`defs`, `defs.lock`, `matrix-families-allowlist.txt`, and the four
`_matrix.csv` — nothing else.

**S50-2. D32's generated SHARC artefacts gain exactly the sixteen S49
dispatch words and nothing else.** `dsp_params.asm` (both chips): **byte-
identical, 0 diff** — the graph nodes and their addresses were already
generated locally in session 49; only the addresses' presence in the
*landed* map (and therefore in the backfilled matrices/ghost tables) was
missing before this session. `ghost_cells.h`/`ghost_cells.c` (DSP copy +
FW copies): count `5810→5823` (+13, the named cells); the 13 new rows in
`ghost_cells.c` are exactly the S49 proposal's map, address for address
(4967–4980, minus the unnamed 4974 serial word). `mx_dsp_map.h`:
`5765→5778` (+13). `dsp_address_map.md`: the same 13 rows, chip-1 total
4043→4056. No other row in any of these five files changed.

**S50-3. `CONTRACT-PROPOSAL-S49.md` marked LANDED; `regen-s49-proposal.sh`
now refuses by design, confirming the def keys are live.** Re-run with
`--check`: `d32: def key 'util' is ALREADY DECLARED` — the script's own
stated obsolescence trigger (§5 of the proposal), reached because this
session landed the prerequisite. Contract note below. The unit was not
touched: no ssh, no boot, no flash — this was a desk-only defs consumption.

Contract note (per `release-notes-contract-convention.md`):
- version: defs-v2026.09.16
- source repo/ref: invirco/defs, tag defs-v2026.09.16 (the `defs/` submodule)
- source commit: 084dbc156cf3bd41b255239d755d0dd89b6ef6e2
- products affected: D12, D16, D24, D32
- change class: mapping (+ family allowlist adoption, additive)
- risk: low — 0 address moves, 0 removals, additive only on all four products
- validation run: `./regenerate-dsp-contract.sh --update-lock` then
  `./check-contract-drift.sh --strict`, both clean against the expected diff

## THE PART MEASURES ITSELF (2026-09-15, session 49)

**S49-1. The `Test[1-1]*` family has graph nodes, and they work on the part.**
`TEST_OSC` (a coupled-form sine oscillator) and `TEST_MEAS` (RMS / THD+N /
noise / crosstalk over any strip's post-fader block) are chip-1 nodes behind
`DSP4_TEST_NODES`, taking sixteen SPI words at 4967–4982. Driven through the
cells on arm A (`f0a94a2e1cf5814d4f59e496b16e736d`), strip 5, all sixteen
addresses proven by write and read-back first:

| f, at −20 dBFS peak commanded | RmsResult | ThdResult |
|---:|---:|---:|
| 100 Hz – 20 kHz (nine points) | **−23.01 ± 0.01 dBFS** | −103 to −142 dB |
| 20 Hz | −22.99 | −123.26 |
| 50 Hz | −23.16 | −120.30 |

−23.0103 dBFS is the exact RMS of a sine of −20 dBFS peak. The two low points
are the 4,096-sample window holding **1.71 cycles** at 20 Hz, where the mean
square of a sine is not A²/2 and depends on the opening phase; the float32
reference predicts the same deviation and the same sign.

**S49-2. The measurement engine read the compressor's own transfer curve off
the shipping strip.** Level sweep at 1 kHz, gain against the injected RMS:

| peak | −60 | −40 | −30 | −20 | −15 | −12 | −9 | −6 | −3 | 0 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| gain, dB | +0.00 | +0.00 | +0.00 | −0.01 | −2.88 | −5.13 | −7.39 | −9.63 | −11.89 | −14.65 |
| ThdResult | −109.9 | −110.9 | −121.6 | −114.6 | −55.75 | −55.75 | −55.75 | −55.75 | −55.75 | −55.75 |

Every 3 dB in gives 0.74–0.76 dB out above the knee — **4:1** — and
`C1_COMP_05` declares `threshold_db=-20.0;ratio=4.0;knee_db=6.0`. The knee is
where the graph says it is and the ratio is what the graph says it is,
measured by the desk on itself with nothing analog in the path.

**S49-3. THE GATE'S RANGE IS IN THE WRONG UNIT AND THE GATE IS INERT.
Severity: HIGH. Status: OPEN, deliberately not fixed here.** The `GATE`
kernel reads `_gate_range_` as **dB** (it clamps to 0..60 and computes
`10^(-dB/20)`); `dsp_codegen.py` initialises the `.var` to **0.001** and calls
it a "linear floor". So an un-written gate's CLOSED gain is
`10^(-0.001/20) = 0.999885` — **0.001 dB of attenuation where the graph row
says `range_db=60.0`.** Read off the part, strip 5, 1 kHz at −60 dBFS peak
against a −40 dBFS threshold: `_gate_on` 1, `_gate_threshold` −40 (correct),
`_gate_envelope` 0.000874 (below threshold, so the gate IS closing),
`_gate_range` 0.001, `_gate_rngq` **0x0FFF873C = 0.999885**, `_gate_gain` and
`_gate_gain_target_q` both 0.999885. `10^(-0.001/20)·2²⁸ = 0x0FFF8749`; the
part holds 0x0FFF873C, thirteen counts away, which is `_exp2q_fx`'s own
error. The level sweep above shows exactly 0.00 dB at −60 dBFS, where a gate
with `range_db=60` would show 60 dB.

The fix is one line — initialise from the row's `range_db` instead of a
hardcoded 0.001 — and it is not this session's: it changes audio on every
strip of every image, it would invalidate the byte-for-byte control arm S49
rests on, and a gate that suddenly closes 60 dB on a quiet channel needs a
bench arm of its own. **On a D24, where nothing on the host writes per-strip
node state (S38-5), every strip is running on that initialiser.**
`_gate_hold_count_` also reads negative while the gate is closed
(0xFFFEED10); noted, not investigated.

**S49-4. THE RESIDUAL MUST BE ACCUMULATED PER SAMPLE, NOT BY SUBTRACTION, and
that is the difference between a THD+N floor of −70 dB and one of −115.**
`Sxx − a·Sxs − b·Sxc` is algebraically the residual energy and is useless in
float32: both terms are of order `Sxx`, so the difference carries the
format's relative precision, 1.2e-7 = **−69 dB**, and every reading below
that would be the subtraction's rounding. `Σe²` accumulated sample by sample
cancels at the SAMPLE's magnitude instead. Measured floor: the float32
reference predicts −115.25 dB for a 4,096-sample window and the part reads
**−114.6 to −116.1 dB** at 1 kHz across five runs. The price is one window of
latency — e[n] needs (a,b) and (a,b) needs a finished window — so **the first
window after any change reads ThdResult 0.00 dB by construction** and a
caller waits for `_meas_seq_` to advance twice.

A longer window is not an improvement: 512 blocks measures −111 dB and 1024
measures −102 dB against 256 blocks' −115 dB, because float32 accumulator
precision is lost faster than cycles are bought.

**S49-5. THE MAGIC CIRCLE'S INVARIANT IS `x² + k·x·y + y²`, WITH A PLUS, and
the minus that looks symmetrical diverges.** `M^T Q M = Q` gives β = +k. The
first implementation used `x² + y² − k·x·y`, which is not conserved by the
recurrence at all: below a few kHz it is nearly right, at 10 kHz the
amplitude reached 1.26 within a second and at 20 kHz it overflowed.
**`tools/dsp/test_node_ref.py` caught it at the desk before an image was
built**, in its first run. It was caught a second time on the part, because a
bench arm ran against a tree generated before the fix landed — 15 kHz read
+2.1 dB and 20 kHz read −168.58 dBFS with a NaN beside it. **Both readings
are withdrawn.** A related consequence: on the ellipse E = 1 the state reaches
1/cos(πf/fs) — 3.86 at 20 kHz, i.e. 11.7 dB hot — so the published block is
scaled by cos(πf/fs), derived from the same z = x² the sine polynomial
already has.

**S49-6. The measurement tap's first-match dispatch published +220.03 dB of
"crosstalk".** The first `_test_meas_tap` jumped to the first accumulator
whose cell named the strip — MeasChan, then XtalkSrc, then XtalkDst — so a
strip named as both MeasChan and XtalkSrc fed only the measurement,
`Σx² on XtalkSrc` stayed at zero and XtalkResult published
`10·log10(Sdd/floor)`: **+220.03 dB on the part**, or −317.48 dB with the
roles reversed. Neither is a crosstalk figure and both look like one. The
cells are independent selectors; the routine now runs three independent tests
and naming one strip in two of them is the normal arrangement.

**S49-7. Crosstalk needs a LIVE neighbour, and `dsp4_apply_strip.py` mutes
one.** That tool's preamble mutes every strip but the one it sets up, so the
neighbour's post-fader block is EXACTLY zero and XtalkResult reads the
arithmetic floor (−317 dB) — true, and not a measurement of anything.
Bringing strip 6 to unity first:

| | ch 6 RMS | XtalkResult |
|---|---:|---:|
| tone on 5 at −6 dBFS, three consecutive windows | −116.1 dBFS | **−97.50 / −97.62 / −97.44 dB** |
| **negative arm, oscillator OFF** | −116.1 dBFS | **+0.01 / +0.36 / −0.45 dB** |

The negative arm is what makes −97.5 dB readable: with no tone both strips
sit on their own floors and the ratio is 0 dB. It is an **upper bound**, not
a crosstalk figure — whatever leaks is below strip 6's own content. A control
with XtalkSrc = XtalkDst = 5 reads **0.00 dB**.

**S49-8. The self-test nodes cost +1,520 cycles/block to USE and less than
the instrument can resolve to CARRY.** Same image, same boot, one cell write
between the two readings: chip 1 `_proc_cyc` 320,761 → 322,281 and
`_proc_cyc_max` 322,492 → 323,395 — **+0.46 % / +0.28 % of budget**, zero
missed blocks in 60,049 either way. The idle cost cannot be measured across
boots and **chip 2 is the control that proves it**: chip 2 carries not one
instruction of S49 and read 326,073 on one boot and 328,054 on the next,
**1,981 cycles apart on code that did not change**. Chip 1's arm-0-to-arm-A
idle difference is −683 average / +605 worst, well inside that. Bounded from
the code: 64 hook sites at ~10 cycles ≈ 640 cycles/block, 0.2 %. **The 33
missed blocks seen on chip 2 are not S49's** — same fact, chip 2 has none of
this code and sits at 99.5–100.4 % of budget either way.

**S49-9. The host-side FFT and the node agree to 0.00 dB, and where they
disagree the disagreement is the useful part.** Arm B, `C1_FDR_05`, 1024
samples, 1 kHz at −6 dBFS peak (the compressed regime):

| | cell | `dsp4_fft.py` | difference |
|---|---:|---:|---:|
| level | RmsResult −18.64 dBFS | −18.64 dBFS | **0.00 dB** |
| THD+N | ThdResult −55.75 dB | −55.75 dB | **0.00 dB** |
| noise+distortion | NoiseResult −74.39 dBFS | −74.40 dBFS | **0.01 dB** |

Stated tolerance was ±0.5 dB. The FFT also says what the node cannot: an odd
ladder, h3 −55.93 dBc, h5 −70.39, h7 −78.28, h9 −111.32 — symmetric
compression, not clipping — plus spurs at 12 kHz ± 1 kHz at about −98 dBc
(intermodulation with something at fs/4; recorded, not chased). At −20 dBFS
the two DISAGREE, ThdResult −115.70 dB against the FFT's −150.63 dB, and that
is the node reporting **its own arithmetic floor** with the FFT proving the
signal is 35 dB cleaner than the node can resolve. The published figure is
conservative, which is the right way round.

**S49-10. A 4-term Blackman-Harris would have made the FFT the limiting
instrument in the comparison it exists to make.** Its −92 dB sidelobes
integrate to an instrument THD+N floor of **−96.7 dB** with a 4-bin tone band
and −111 dB with a 16-bin one — ABOVE the node's −115 dB. The 7-term window
leaks below −180 dB and measures −140 dB to below float64 on a synthetic pure
tone. Separately, **the normalisation has to be Parseval's and not coherent
gain**: summing a band is a power sum, and the coherent-gain form was 0.01 dB
out on the 4-term window and **1.18 dB out on the 7-term one**, which is how
it was caught. With `|X|²/(n·Σw²)` the one-sided sum equals the mean square,
which is exactly what `RmsResult` publishes, so both instruments quote the
same dBFS and a full-scale sine reads −3.01 on each.

**S49-11. On a silent capture the FFT printed +11.33 dB of THD+N and it read
like a measurement.** With no tone the largest band is the largest noise bin,
and everything downstream of "fundamental" is then meaningless. `dsp4_fft.py`
now tests whether the fundamental clears the median bin by 20 dB and prints
**NO TONE IN THIS CAPTURE**, naming `total` as the one figure that stays
valid. Its `total` on that capture was −116.96 dBFS against the node's
−116.32 dBFS over a different window at a different time — 0.64 dB, which is
the agreement a noise measurement gets.

**S49-12. The `Test[1-1]*` cells are NOT in `dsp-unmapped.csv`, on any
product — they are in no product's cell set at all.** The S49 dispatch stated
they were listed `no-graph-node`. The thirteen rows exist only in the cell
library (`defs/common/cells/mx_master.csv`); `defs/tools/def_master.py` gates
the `Test` prefix on the def keys `util` and `util.osc`, and no product def
declares either, so no per-product master carries a `Test` row and
`gen_dsp.py` — whose proposal is the intersection of the graph's expansion
with the product's cell SET — drops them before either file is written. A
cell no product defines is in neither file; it is not "unmapped", it is **not
present**. Consequence for the gate: `gen_dsp.py --check-proposal` still
passes on this tree and **cannot see the question**, so S49's proposal needs
`./proposals/regen-s49-proposal.sh --check` instead, which stages the def
change in scratch, re-runs defs' own expander, regenerates and diffs. It
returns byte-identical. The def change — `util,1` and `util.osc,1` — adds
exactly 13 master rows and 13 expanded cells on each of D32/D24/D16/D12 and
opens no other family.

**S49-13. `DIAG_BUILD_CFG2` had no spare bit, so its signature narrowed from
eight bits to seven.** Bits 23..0 are fully allocated (S18 spent the last
two) and 31..24 was the signature. Rather than invent a third word for one
bit, 31..25 stay `0b1100001` and bit 24 carries `DSP4_TEST_NODES`. The
failure mode is the one to want and it was measured, not predicted: the first
S49 image read `0xC3010244` and a decoder still masking `0xFF000000` said
*"0xC3010244 is not a DIAG_BUILD_CFG2 word"* on both chips — a loud refusal
rather than a quiet misreading of the decimate field. `dsp4_buildcfg.py` now
masks `0xFE000000` and prints `DSP4_TEST_NODES = 1, shipping is 0`.

**S49-14. All 24 chip-1 RX lanes are STATIC, and it qualifies exactly two
numbers.** `dsp4_inscan.py`: `MOVING 0 / STATIC 24 / UNREADABLE 0`, lane 5
stuck at `0x00000040` across 8 reads at ~10 ms spacing. That is the state
with AN_EN low (S49-15). It matters to the strip's own floor (−115.93 dBFS —
which is therefore a clean measurement of the DSP's arithmetic noise with a
provably static input, not a converter floor) and to the crosstalk bound, and
**to nothing else in the session**: every other figure comes from a signal
injected digitally into the strip's input block AFTER the input kernel has
filled it, so whatever the converter sent is discarded.

**S49-15. STOPPING `matrix-app` NOW DROPS AN_EN, AND THE APP WILL NOT RAISE
IT AGAIN.** AN_EN (GPIO26) read `op -- pd | hi` two seconds after the first
`systemctl stop matrix-app` and `op -- pd | lo` at handback; **this session
never wrote GPIO26.** The app's log names it: `Boot.Init() - AN_EN gated
(PW 2026-09-10): analogAutoEnable=true` followed by *"AnalogBringUp: AN_EN
STAYS LOW — digital clocks not proven stable: CPLD running (Unknown); DSPs
booted and streaming (Unknown); Converters out of RST_C (Unknown). Analog
rails are not requested; bring AN_EN up by hand at the bench."* S48 recorded
the same app logging `analogAutoEnable=false` and AN_EN surviving four app
stops; with `true` the app runs the bring-up, finds all three gates Unknown
**by design** — it has no query path for any of them — and drives the pin
low. So the first app restart after the hub raises AN_EN by hand drops the
rails. Left low and flagged rather than silently restored, because the pin is
the hub's; one command puts it back: `sudo pinctrl set 26 op dh`.

**S49-16. The parameter link cannot follow an 85 ms measurement window.**
`SweepOn=1, SweepStep=16` walked the oscillator up the cell's own
128-position Log law and stopped itself at code 112 (8,845.03 Hz), the last
step below 127 — the DSP-paced stepping works, and it steps on the window
serial TEST_MEAS publishes so a step and the window that scored the previous
frequency cannot be off by one. **The host missed the first six steps.** The
link serves one register per audio block and `dsp4_scope.rd()` votes over up
to twelve asks, so reading the serial plus four results plus the frequency
takes about 350 ms against an 85 ms window. **A sweep should be driven one
frequency at a time over this link** — write `OscFreq`, wait two windows,
read — which is how the frequency table in S49-1 was taken. The DSP-paced
sweep is for a host that polls a subset, or for a longer window.

## THE MUTE BIT IS NOT INVERTED, AND IT PROVES THE ANALOG SWITCHING WORKS (2026-09-15, session 48 part 6)

**S48-29. The mute-polarity hypothesis is refuted: `mute=1` makes MIC 5
QUIETER, which is what muting does.** The proposal was that a normally-closed
mute short released by the bit would make `mute=0` the *muted* state — which
would explain a preamp amplifying its own noise with a correct gain law while
passing nothing. It is testable in one measurement and it fails. With the
500 Hz square driving, gain 63, phantom off, chain verified 200/200 in both
states (`0xFD` = Q0 set, `0xFC` = Q0 clear):

| ch5 mute bit | chain byte | lane 5 settled floor | stimulus on lane 5 |
|---|---|---:|---|
| `mute=1` | `0xFD` | **−87.5 dBFS** | none |
| `mute=0` | `0xFC` | **−73.7 dBFS** | none |

`mute=1` is **13.8 dB quieter**. If the polarity were inverted, `mute=1` would
be the connected, noisier, signal-passing state. It is the opposite, so **the
CLI's labelling is correct, the safe image is correct, and no software fix is
owed.** (The `mute=1` scan's first pass read −74.69 dBFS before settling to
−87.5 across the next two passes — the floor was still settling from the chain
write, not a third state.)

**S48-30. The same measurement is a positive control that the 595 chain
reaches the analog switching.** A 13.8 dB change in the preamp's own noise
floor, commanded over the chain and repeatable, proves the shift register's
output actually drives the channel-5 input switch — not merely that the
readback matches. Combined with the gain law (S48-28), **both** of the
channel's control functions are demonstrably live at the hardware.

**S48-31. So the fault is narrowed to the signal path itself, with every
control proven.** The square is present at J25 pins 2-3 (DMM); the mute switch
works; the gain switch works; the ADC converts; lane 5 is the right lane. What
remains is the part of the channel that carries the *signal* from the
connector into the amplifier — input coupling, protection, or the input
device. **Same class as the known-dead MIC 1-4 section, whose FET position is
already under investigation, and the MIC 5-8 section now wants the same
check.** Nothing further is reachable from the DSP: every DSP-side and
control-side hypothesis has now been tested and closed.

**S48-32. A background chain relaunched a driver after hand-back, and only a
process check caught it.** A `while pgrep …; do sleep; done; exec loop.sh`
waiter was left from the back-to-back window work. Two such waiters kept each
other alive by matching each other's command line under `pgrep -f`; when one
was killed the other proceeded to `exec` the loop script, **which begins with
`rm -f /tmp/s48stop`** — so the stop flag was cleared and a queued scan began
driving the output again *after* `chain-safe` had been issued. A first cleanup
attempt also killed its own ssh session (exit 255) because `pkill -f` matched
the pattern inside its own command line. Both are recorded because either
could leave a unit driving an output with the operator believing it handed
back. **Rules that follow: never let a cleanup script clear its own stop flag;
write `pkill -f` patterns so they cannot self-match (`dsp4_s48_[s]can.py`);
and verify hand-back by listing processes, not by having issued the stop.**

## THE SQUARE LEAVES THE UNIT AND REACHES THE MIC CONNECTOR; THE BREAK IS INSIDE THE MIC 5 CHANNEL (2026-09-15, session 48 part 5)

**S48-24. The DAC and its output stage are PROVEN, on a DMM.** With the
500 Hz square parked, PW read it at **J45 pins 2-3 on AC volts**, and then at
**J25 pins 2-3** — the MIC 5 input connector — so the signal leaves the unit
AND arrives at the input connector. Cable and connector are good. Every
candidate downstream of the DSP up to that connector is closed: the DAC, the
output stage (U82 NJM4580, C747/C748, R1875/R1876), and the cable.

**S48-25. No analog input lane carries the stimulus, on either chip.** All
twelve chip-1 converter lanes, OFF/ON/OFF, with the square verified live
(`_scope_inj_blk = 0x90330`):

| lane | OFF | ON | OFF again |
|---|---:|---:|---:|
| 1–4 (dead MIC 1–4 section) | −114…−120 | −115…−118 | −115…−116 |
| **5 (MIC 5, gain 63)** | **−72.51** | **−71.78** | **−73.35** |
| 6–12 | −110…−115 | −111…−114 | −110…−116 |

**Lane 5 does not move.** Nothing else does either. The run was done twice;
the first was perturbed by a concurrent `chain-set` (which drives CS_M) and
was re-run clean rather than reported.

**S48-26. The two chip-2 lanes that DO rise are the fabric, not the loop —
and the tool said otherwise.** `C2_RECV_MAIN_L` and `C2_RECV_AUX_01` rise
**+91.9 dB and +89.8 dB** and fall back cleanly. Those are the **inter-chip
lanes carrying chip 1's mix buses to chip 2**, i.e. DOWNSTREAM of the
injection and part of the DSP's own path: strip 6 → MAIN/AUX buses → fabric →
chip 2. Their rising is **expected**, and it is a good positive control that
the stimulus is real and reaches the buses — but it is **not** the analog
return. `dsp4_s48_scan.py` grouped them with the converter lanes and printed
*"The loop returns on the lane(s) above"*, which would have read as first
audio. **Corrected in the tool**: chip-2 fabric lanes are now classified and
reported separately, and only chip-1 lanes 1–12 can answer the loop question.
Recording it because the wrong version ran first and the output is in the log.

**S48-27. RX lane 5 IS physical channel 5 — the lane-map hypothesis is
closed.** Only `ch5`'s gain code was ever changed, and lane 5 is the only lane
that responded: its floor tracked **−133.0 → −107.1 → −101.4 → −96.2 dBFS**
across gain codes 0/16/32/63, and in the scan above it is the only lane
sitting 40 dB above the others while every other channel is muted at gain 0.
A wrong lane↔channel map cannot produce that. So this is **not** the ADC-side
twin of S42's reversed DAC block.

**S48-28. The break is inside the MIC 5 channel, between the XLR and the ADC,
and the preamp is alive but not passing its input.** Everything either side is
now proven: the square is present at J25 pins 2-3 (S48-24); the 595 image for
physical channel 5 is **verified 200/200 at chain position 9, `0xFC` — Q0
mute OFF, Q1 phantom OFF, Q2-Q7 gain 63** (readback matches the sent image bit
for bit, so the switching word is right); RX lane 5 is the right lane
(S48-27); and the AK5558 is converting, because lane 5 carries a dithered
floor that **tracks the gain code**. That last point is the sharp one: **the
preamp amplifies its own noise with a correct gain law while passing none of
the signal at its input.** So the amplifier and the gain switching work, and
what fails is the path from the connector into the preamp's input.
**This is the same class as the known-dead MIC 1-4 section, whose FET position
is already under investigation** — the MIC 5-8 section should be checked the
same way. It is a component-level question on the analog board and nothing on
the DSP side can take it further.

## THE IMAGE HAD NO STIMULUS IN THE AUDIO BAND AT ALL; ONE WAS BUILT, AND IT IS VERIFIED ON THE PART (2026-09-15, session 48 part 4)

**S48-19. The DC discriminator is void by construction, and the hub's netlist
trace says why.** The XLR OUT_01 path is U81 → RC → U82 (NJM4580) →
**C747/C748 electrolytic AC coupling** → R1875/R1876 → J45 pins 2/3 (spark
gaps SG51/52, J9.19/20 in parallel). A parked DC level therefore reads **zero
on a DMM by design**, however healthy the DAC is. This was flagged in advance
in S48-18 rather than discovered after the fact, so no null reading was
mis-scored — but the test itself cannot run on this hardware and is withdrawn.
`dsp4_s48_drive.py --dc` is kept only for a DC-coupled probe point upstream of
C747/C748.

**S48-20. Neither of the two stimuli this firmware already had can be read on
a DMM, and that is why a third was built.** Three candidates, all rejected on
measurement or on arithmetic: `scope.asm`'s **impulse and step** are DC or
single-shot; **`DSP4_PROFILE_SIGNAL`'s square alternates EVERY SAMPLE**, so it
is Fs/2 = **24 kHz**, which the AK4458's reconstruction filter removes and no
DMM AC range reaches; and the **host-toggled step** is limited to about
**1 Hz** because the parameter link is serviced once per block. The band a DMM
reads — roughly 40 Hz to 1 kHz — was empty.

**S48-21. A square generator was added to the block injector, and the shipping
image is provably untouched.** `scope.asm` gains a square mode gated entirely
behind `DSP4_SCOPE_BLK_TAP`. **No new diag register**: the half-period rides in
`_scope_mode` itself — **bit 16 selects square, bits 15:0 are the half-period
in BLOCKS** — which keeps the rule the file's own S9-5 note sets, that a bench
instrument's parameter does not go into the shipping register map. The
half-period is counted in **blocks, not samples**, deliberately: that puts at
most one sign change per block, so the decision sits outside the sample loop
and no condition flags are live across it — the SHARC flag hazard that a
per-sample version would have had. `_scope_sq_phase` is a **flip counter whose
bit 0 is the sign**, so zero is a valid starting state and nothing needs
initialising at arm time. f = Fs/(2·N·BLOCK) = **1500/N Hz** at 48 kHz and
BLOCK 16. **The control arm proves the confinement: `DSP4_SCOPE_BLK_TAP=0`
after the change still builds `825f9b7dac5978c973550c8e40819ba9` /
`7b1311e8e56f008fa98046cab59293c6` — the S42 pair, byte for byte.** The
witness pair is `81f4f954f91d08947775a230108edf3c` /
`530db1e3049bff1dc6446f5777b1acce` (chip 1: 6,160 symbols, +2 for the new
state vars), staged by hash at `/home/app/s48sq_81f4f954`, md5-verified both
sides, with `/home/app/s42` and `/home/app/s48tap_289421ed` intact.

**S48-22. The first self-test FAILED, and the failure was the test, not the
generator.** Capturing `_buf_C1_IN_06` while driving the square returned ADC
dither (`0x20`, `0x40`, `0x60`) and no square at any N. That reads as "the new
asm does not work". It does: `_scope_sq_phase` advances at **~990 flips/s
against a designed 3000/3 = 1000/s** for N=3, and `_scope_inj_blk` = 0x90330.
**The IN node's tap runs BEFORE the injector overwrites the pool slot**, so the
correct tap point is downstream. Re-run on `_buf_C1_GAIN_06`, on the part:

| N | expected half-period | measured | amplitude |
|---:|---:|---:|---|
| 1 | 16 samples (1500.0 Hz) | **16** | `0x01000000`, all 1024 samples |
| 3 | 48 samples (500.0 Hz) | **48** | `0x01000000` |
| 15 | 240 samples (100.0 Hz) | **240** | `0x01000000` |

Exact periods at three frequencies two decades apart and the exact injected
amplitude on every sample. **`C2_AUX_OUT_01` then carries it at ±0.50000 Q4.28
= −6.02 dBFS**, both polarities present, against a −92 dBFS floor with the
injector off. The generator is verified end to end from the injector to the
transmit lane.

**S48-23. A detached background launch silently produced a dead drive, and a
zero-byte log was the only sign.** `nohup`/`setsid` over ssh left the process
either unstarted or killed with an **empty** log, while an earlier variant left
it running but with Python's stdout buffered — also an empty log, but with the
drive alive. Both look identical from the desk, and either would have had PW
reading a DMM against a stimulus that was not there. The fix is to keep the
ssh session open and run `python3 -u`, so the log carries
`_scope_inj_blk = 0x90330 (FIRED)` and a live elapsed counter as the witness
that the drive is actually up. **Never ask for a hands-on reading without a
live witness that the stimulus is running.**

## THE DACs NEED NO REGISTER WRITE, AND "TDM128" WAS A DECODE ERROR IN THIS REPO'S OWN COMMENT (2026-09-15, session 48 part 3 — bench + netlist)

**S48-15. The serial-control candidate is refuted on the netlist, and it was
mine.** S48-13 named "the AK4458s are in serial control mode, unconfigured,
and nothing in the stack will ever configure them" as a live candidate for the
silent output, on the reasoning that `!CS_C` exists as a converter chip select
while no CS_C writer exists anywhere in the tree. **The hub read the netlist
against the AK4458 pin table and it is wrong: U81 is in PARALLEL control
mode** — pin 17 I2C = +3V3 and pin 16 PS = +3V3 (PS high with I2C high is
parallel), so there is no register interface to write and **no register write
is needed to unmute or to leave power-down**. The rest of the strap set is
consistent with parallel mode throughout: pin 11 SMUTE = GND (unmuted), pin 12
DCHAIN = GND, pin 44 LDOE = +3V3, pin 48 PDN = RST_C, SDTI1 (pin 4) the data
lane with SDTI2-4 grounded. **The candidate is closed.** What remains open on
the DAC is `!CS_C`'s purpose on a part with no serial interface — provision,
presumably — and that is a schematic question, not a fault.

**S48-16. "TDM128" in `sport_config.c` and `dsp_codegen.py` is wrong, the
strap bits quoted beside it are right, and the MFD fix is untouched.** Both
files record the converters as *"pin-strapped TDM128 in the I2S variant
(DIF0-1 = 10 = I2S 24-bit, TDM0-1 = 01)"*. The hub's netlist read gives U81
pin 14 TDM1 = +3V3 and pin 13 TDM0 = GND — **the same two bits**, decoded
from the AK4458 table as **TDM256**, with pin 15 DIF = +3V3 = 32-bit I2S.
**Three independent lines agree on 256 and none on 128:** the netlist; the
slot map, where `shared/dsp4-logic/tdm-lines.csv` gives `B_O0` (DAC8 OUT_1-8,
the lane carrying AUX 1) as **TDM8, 8 slots**; and the part itself, whose five
chip-2 transmit SPORTs read **SLEN 32, WSIZE 8** — 8 slots x 32 bits = **256
BCK per frame**. Also consistent: U81 pins 1 (MCLK) and 2 (BICK) share one net
at 256fs, which only works because BICK *is* 256fs in TDM256.
**CRUCIALLY THIS CHANGES NOTHING ABOUT MFD.** S42's derivation rests on the
*I2S variant* putting one BCK between the frame edge and the MSB, and on LOGIC
asserting FS one BCK before slot 0 — not on the mode's name. DIF = +3V3
confirms the I2S variant, so **MFD = 2 on the converter halves stands**, as do
S46's nineteen-lane register verification and S48's repeat of it. Corrected in
both files as comments only: `check-contract-drift.sh` passes with nothing but
those two files dirty, so no generated artefact moves.

**S48-17. The transmit side is enabled and correctly framed on the part.** All
five chip-2 half-B SPORTs read `CTL 0xC20031F1` — **SPEN = 1**, SLEN 32 — with
`MCTL` 0x721 on sports 0, 1, 2, 4 and **0x711 on sport 3**, i.e. MCE = 1,
WSIZE = 8, and **MFD = 2, 2, 2, 1, 2** exactly matching the generated
`c2_tx_lanes_mfd` table including the deliberate CPLD/fabric exception. That
match is also what identifies these as the transmit lanes. Together with
`FRAME_COUNT` advancing at **≈3,000 blocks/s — exactly 48 kHz / BLOCK 16** —
the DSP end has a valid frame clock and an enabled, correctly framed
transmitter. **So the break is not the DSP's transmit configuration, not the
DAC's control mode, and not the absence of a register write.** What is left,
and none of it is reachable from the DSP: `RST_C` at U81 pin 48 specifically
(inferred high, because the ADCs are converting and the S MCU drives one
common `IRST_C` — the hub is checking U92's PDN to close that), the clock and
data actually arriving at U81's pins across the FPC, the output stage, and the
loop cable.

**S48-18. Two discriminators ran; one is still waiting on hands.** The DC
drive was parked for its full 120 s with `_scope_inj_blk = 0x90330` and
`C2_AUX_OUT_01` held at 0.50000 Q4.28 (−6.02 dBFS), and cleared itself
afterwards; **PW's DMM reading on J45 pin 2–3 is outstanding.** Recorded in
advance so a null is not over-read: **a reading proves the DAC and its output
stage, but a zero disproves nothing** — an AC-coupled or servo'd XLR output
passes no steady DC however healthy it is; the DMM-compatible follow-up is a
slow ±A toggle watched on DC volts. The finger test ran two windows totalling
17.5 minutes with MIC 5 at gain 63 (chain VERIFIED 200/200): the lane sat at
**−73 to −75 dBFS against control lane 9 at −113 to −117 dBFS**, 40 dB apart,
so it is demonstrably live and sensitive — and **no rise above 6 dB was
flagged in either window**. That is recorded as *no touch observed*, not as a
verdict on the preamp: the windows elapsed while PW was away from chat.

## THE TAP BUILD REACHES THE DAC LANE AND THE ANALOG CHAIN WAS NOT WHERE IT WAS RECORDED (2026-09-15, session 48 part 2 — bench, MW-D24-2)

**S48-9. `DSP4_SCOPE_BLK_TAP=0` reproduces the S42 pair byte for byte, so the
tap is the only variable.** `DSP4_SCOPE_BLK_TAP=0 DSP_BUILD_DIR=/tmp/s48_ctl
./build.sh all` produced **`825f9b7dac5978c973550c8e40819ba9` (451,544 B) and
`7b1311e8e56f008fa98046cab59293c6` (307,980 B)** — the staged S42 pair
exactly. The witness arm is **`289421edacce2e8666369746c2b01796` (459,832 B)
and `01fa58b12df5a19d87398e6ab9eae43b` (312,608 B)**, staged by hash at
`/home/app/s48tap_289421ed` and md5-verified on both sides of the copy; the
S42 pair is untouched and remains the way back. Neither arm logged an error.
The `ea1092` "undefined symbol `_scope_inject`/`_scope_record`" warnings the
tap arm emits **also appear in the control arm**, which is the pair proven to
run on the part, so they are pre-existing per-file assembly warnings resolved
at link. Identity is positive at three levels: `_scope_inj_blk` is **absent**
from the shipping map and present in the tap map (6,158 vs 6,155 symbols on
chip 1), the build banner reads `*** INSTRUMENT BUILD: DSP4_SCOPE_BLK_TAP=1
taps every node's output block ***`, and **the part itself reports it** —
`dsp4_checkchip.py` prints `on: DSP4_SIMD_GRAPH, DSP4_SCOPE_BLK_TAP,
DSP4_GATHER_FIRST  <-- NOT the shipping kernel set`. Boot, map proof (**agree
5 / disagree 0 / not-in-map 2 on both chips**, against this image's own map)
and node state (**13 ok / 0 mismatch**) all pass on the tap pair.

**S48-10. The block injector reaches the DAC lane, and the strip's aux path
SATURATES above about 0.5 Q4.28.** With `_scope_inj` set to the **RX slot**
(`_rx_slot_C1_IN_NN`, not `_buf_C1_IN_NN` — naming the buffer arms a call site
that never fires) and the run armed against a `src` that matches no node so
`_scope_arm` is never cleared, `_scope_inj_blk` reads **0x90330** — the
per-strip call site fired — and `C2_AUX_OUT_01` goes from **−88 dBFS to
demand**. The transfer is not constant:

| `_scope_amp` | Q4.28 in | AUX 1 TX out | ratio |
|---|---:|---:|---:|
| `0x01000000` | 0.0625 | **0.50000** (−6.02 dBFS) | **×8.00** |
| `0x02000000` | 0.1250 | 0.84589 (−1.45 dBFS) | ×6.77 |
| `0x04000000` | 0.2500 | 1.00594 (+0.05 dBFS) | ×4.02 |

Linear at exactly ×8 in the first row and compressing above it — a limiter or
the tube stage, not a scaling error. **0x01000000 is the linear operating
point** and every level below is quoted there. Note the third row puts the
lane at **1.006 Q4.28, just over the ±1.0 criterion** S46 §5.3 applies, so an
injection that size is already past DAC full scale.

**S48-11. Mute and polarity are exact and reversible through the whole path.**
At the linear point, `Aux001Mute001` 0 → 1 → 0 gives **0.500000 → 0.000000
(−inf) → 0.500000**: the mute is absolute, not a finite attenuation, and it
returns to the same word. `Chan006Pol001` 0 → 1 → 0 gives mean **+0.50000 →
−0.50000 → +0.50000**: polarity inverts exactly, with |peak| unchanged.

**S48-12. THE ANALOG CHAIN WAS NOT IN THE SAFE STATE THE RECORD SAYS IT WAS,
and gate 2's RX spread was eight randomly-gained inputs, not eight converter
noise floors.** The dispatch's bench state records "safe image loaded (every
input muted, gain minimum, phantom off)". Running `app cli chain-safe` — the
first sanctioned chain write of the session — **moved every converter lane by
about 45 dB**, from −67…−82 dBFS to a uniform −111…−117 dBFS. A chain that is
already safe cannot do that. The mechanism is in the app's own banner for the
chain, `25x 74HC595, 200 bits, SPI0 shift, CS_M latch, MISO loopback via U2`:
**every DSP parameter transaction shifts through those 595s**, and CS_M is the
LATCH. CS_M sat low while the link was dead (S48-1) and went high when the hub
changed GPIO27's pull — and that rising edge latched whatever the preceding
DSP traffic had left in the shift register. **So the earlier reading of "eight
distinct noise floors inside the −65…−85 dBFS band" was eight unknown gain
codes**, and the band criterion in `dsp4_s42_align.py` — inherited from S39,
taken the same way — should be re-derived against a chain that is known.
Corrected baseline, chain verified 200/200 with only ch5 unmuted at gain 0:
**all twelve lanes −111…−117 dBFS**. The bit tests are unaffected: `lo7` never
set and bit 31 exercised are framing facts and hold in both states.
**Procedure that follows: assert the chain, THEN measure, and do not trust an
analog level taken after DSP traffic without a chain write in between.**

**S48-13. The ADC side is proved live; the DAC side is proved only to the
transmit lane; the loop returns nothing.** MIC 5's preamp responds to its gain
code exactly as a preamp should — captured noise floor **−133.0 dBFS at gain
0, −107.1 at 16, −101.4 at 32, −96.2 at 63** — so the 595 chain, the preamp,
the AK5558 and the RX lane are all alive and calibrated end to end. But the
loop does not come back. Driving a step into donor strip 6 → AUX 1 → OUT_01
and capturing strip 5's input block (the drive and the capture MUST be
different strips, or the injector overwrites the very slot the return arrives
on), **the drive-off and drive-on captures are identical to within 0.2 dB at
every gain**: −107.11/−107.14 at gain 16, −101.38/−101.47 at 32,
−96.22/−96.44 at 63. An earlier single capture reading −70.31 dBFS at gain 16
did not reproduce and **the negative arm is what killed it** — without the
control it would have been filed as first audio. The break is therefore **at
or after the DAC**: `C2_AUX_OUT_01` proves what the DSP handed the AK4458, and
nothing on the DSP side can prove what the AK4458 did with it. `!RST_C` is S
MCU PA11 and the app reports converter reset state as `Unknown`, so the DACs'
running state has never been established on this unit. The next instrument is
**PW's scope on OUT_01**, not another number off the DSP;
`tools/pi/dsp4_s48_drive.py` parks the drive up for as long as he needs.

**S48-14. A peek window cannot see a transient, and that invalidated the first
loop method.** `rx_rms()` re-reads the same 16-word active block repeatedly, so
however long it runs it observes about **0.33 ms** of audio. Against a
host-timed ~1 Hz toggle the odds of landing on the edge are under one in a
thousand, so an AC-coupled path — which passes only edges — reads as silence
however alive it is. That is why the levels in S48-6 moved by tenths of a dB.
The capture path is the right instrument: `_scope_tap` copies whole contiguous
blocks and `_scope_go` holds recording off until the stimulus is driven, so
sample 0 of the capture is the edge and 1024 samples is 21.3 ms of continuous
audio. Any future loop or latency measurement on this bench belongs in a
capture, not in paced peeks.

## CS_M WAS HOLDING U2 ON THE PARAMETER LINK; WITH IT RELEASED, THE D24 REACHES ITS FIRST LIVE AUX OUTPUT ON REV C (2026-09-15, session 48 — bench, MW-D24-2, PW and the hub at the bench)

**S48-1. The parameter link was dead because CS_M was idling LOW, and the
symptom was a plausible-looking lie.** The S42 pair booted exactly as in S46 —
md5s re-verified on the unit (`825f9b7d…` / `7b1311e8…`), 451,584 B on CS1 in
605.7 ms and 308,224 B on CS2 in 413.4 ms, S46's timings to a tenth of a
millisecond — and then `cannot phase the parameter link: MAGIC never came
back`, on both chips, on two independent attempts. Reading the raw words
rather than trusting the exception: 400 collect transactions returned **4
distinct word-pairs and 0 hits on MAGIC**, 390 of them the transmitted word
**right-shifted by exactly one byte**. Four checks characterised it — MAGIC
absent at *every* bit offset (not a sub-word phase slip); the delay exactly 8
bits at both 8 and 10 MHz (synchronous logic, not an MCU); GPIO9 forced
`a0 pd` then `a0 pu` changing nothing (MISO **driven**, not floating); and the
decisive A/B, **replies byte-identical with the chip select asserted and
deasserted**, so the SHARC was driving nothing. **The hub named the cause and
it was neither the DSPs nor the 595 chain's data: GPIO27 was idling as an
input with a pull-DOWN, holding CS_M LOW, which leaves the analog MISO buffer
U2 ENABLED and driving SPI2 MISO continuously** — H1S1 stopped holding CS_M
high when it was reflashed on 09-14. Changing GPIO27 to input pull-UP (CS_M
high, U2 tri-stated) fixed it outright: the next probe returned `w0
0xE0002000 / w1 0xD5B40001` — echo and MAGIC, word-aligned — and the same A/B
now reads the SHARC with CS asserted and silence with it deasserted. **Recorded
as a correction: the first write-up of this session attributed the echo to the
74HC595 chain's own shift output and hypothesised that the over-budget graph
was starving the link. Both were wrong.** The graph *is* over budget
(`BLK_OVERRUN` 2,245 / 2,230 at boot) and the link answers perfectly anyway.

**S48-2. Gate 1 passes in full, and for the first time on a D24 the strip
under test is not strip 1.** After the fix: boot `CHIP_ID verified: chip 1 = 1,
chip 2 = 2`; `dsp4_checkchip.py` **chip check OK**, both chips **BLOCK 16, CCLK
983.04 MHz, shipping configuration**, kernels `DSP4_SIMD_GRAPH` +
`DSP4_GATHER_FIRST`; 51 registers to chip 1 and 5 to chip 2. Both chips then
read **BOOT_STAGE 7 running, PRODUCT_ID 1, SPORT0_ERR_A 0, SPI_ERR_COUNT 0,
RESP_DROP 0, CGU_FAIL 0**, with `FRAME_COUNT` advancing 31,844 → 676,379 on
chip 1 (≈3,000 blocks/s, the BLOCK-16 rate at 48 kHz). `dsp4_config.py
--verify` fails its own read-back on both chips — that is the **known
CFG_COMMIT desync**, in-process only: a freshly started tool phases the link
immediately afterwards and reads every register. Map proof
(`dsp4_s39_symcheck.py`): **agree 5 / disagree 0 / not-in-map 2 on both
chips**, the sheet's required pass. Node state: **13 ok / 0 mismatch / 0
unreadable** for `Chan005…` → `Aux001…`, i.e. **MIC 5 → strip 5 → AUX 1 at
unity, every other strip muted and off both buses**, which is R1's routing
exactly.

**S48-3. `dsp4_apply_strip.py` could never write any strip but 1, and said it
did.** Line 33 is `sys.argv = ['s']` — emptying argv so `dsp4_scope`'s
import-time parser does not eat the arguments — and `STRIP`/`AUX` are read
**after** it, so both were pinned to 1 on every invocation. The tool then
printed `strip 5 -> MAIN and AUX 1` and listed `Chan001…` cells, which is
exactly the kind of output that reads as success. `dsp4_apply_strip.py 5 1`
wrote strip 1. **Fixed** by taking `sys.argv[1:]` before the clear, the same
way `dsp4_s42_align.py` already does it (`_argv = list(sys.argv)`), and
re-staged; the re-run writes `Chan005…` and reads back 13 ok / 0 mismatch.
Nothing in the prior record is invalidated — S46 §4 ran `1 1` and correctly
reported strip 1 — but any future "strip N" claim from before this fix is
strip 1 wearing another number.

**S48-4. The converters are alive and the RX lanes are right — eight of
twelve, and the other four are the section PW already knows is dead.**
`dsp4_s42_align.py` on the part: **MFD PASS on all nineteen lanes of both
chips** against the generated tables. RX, chip 1's twelve converter lanes:
**bits 6:0 never set on ANY lane** (the 24-in-32 pad is where it should be),
bit 31 exercised on every lane (13–20 words of 32), and lanes **5–12 all
inside the −65…−85 dBFS converter band with eight distinct noise floors** —
−69.9, −75.0, −72.3, −81.7, −67.6, −81.5, −76.8, −81.5 dBFS. **Lanes 1–4 read
−113.9, −117.6, −116.1, −118.4 dBFS**, far below the band, and that is the
**MIC 1–4 section the bench state records as DEAD** (FET position under
investigation) — not a DSP fault, and the tool scores it `**BAD**` only
because its band test has no notion of an unpopulated analog section. The
tool's overall RX verdict is therefore FAIL on a bank that is eight-twelfths
correct; it wants the same kind of guard S46 gave it for an undriven bus.
Chip 2's inter-chip receive resolves by name, with `C2_RECV_MAIN_L` and
`C2_RECV_AUX_01` carrying **16 distinct values** and the idle lanes 1 — the
two lanes strip 5 actually feeds.

**S48-5. AUX 1 is LIVE, and §5.3's criterion is met on the part for the first
time.** `C2_AUX_OUT_01` (off 7, stride 8) reads **|peak| 0.00423 Q4.28 =
−65.5 dBFS, 8 of 8 words non-zero** — comfortably **inside the ±1.0 Q4.28
criterion**, where S39-6 read 1.538 (+3.75 dBFS, above full scale) and S46
read exactly 0.00000 on an unpowered bank. S46's honest caveat was that 0 is
also what a dead path reads and the lane *"will only be proved live when the
converters are"*. **They now are, and it is.** `C2_MAIN_OUT_01`/`_02` and
`C2_MAIN_ST_OUT` are live too (−61.8 / −60.5 / −62.1 dBFS, 8/8 non-zero).
Note this proves what the DSP handed the AK4458, not what the AK4458 latched.

**S48-6. The analog loop is CORRELATED but not yet proved at level, and the
stimulus — not the loop — is what is missing.** With PW's cable patched rear
XLR OUT_01 → MIC 5, `Aux001Mute001` was toggled across five alternating arms
against a control lane that the loop does not feed. MIC 5's RX lane:
**open −68.19, −68.17, −68.32 dBFS; muted −68.55, −68.62 dBFS** — no overlap
between the arms, mean delta **+0.36 dB**. Control lane 9 over the same arms:
**+0.05 dB**. So the looped lane moves **seven times** the control's movement,
repeatably, in the right direction, and it tracks a control this session
owns. But **+0.36 dB is under S40 gate 3's 1 dB bar**, and the reason is that
the only thing on the bus is the strip's own converter noise: AUX 1 leaves at
−65.5 dBFS and comes back ~7 dB under MIC 5's own floor. **This is "the
stimulus is below the noise", not "the loop is open".**

**S48-7. The image's host-settable injector cannot drive the node chain, and
believing it would have produced a wrong finding.** `scope.asm` offers impulse
and step only (S39-9). Driving `_buf_C1_IN_05` with a 0.25 Q4.28 step
(mode 2) and capturing that same address returns **`04000000` for all 1,024
samples** — the injector works perfectly. But the AUX 1 and MAIN TX lanes
**never rose above their noise** during injection, and the naive reading of
that is "the step dies inside strip 5", which is the S38-5 / item-17 defect
signature and would have been filed as one. It is not. `scope.asm`'s own
comment settles it: under `DSP4_BLOCK_KERNELS` **both** injectors run, the
per-sample `_scope_inject` is what `_scope_record` captures, and
`_scope_inject_blk` *"rewrites the whole block and is the write the chain
actually reads"* — and that one is gated behind the build-time
`DSP4_SCOPE_BLK_TAP`, with **no memory POKE on the diag link, only PEEK**, so
the host cannot reach it on this image. **On the shipping D24 image there is
no host-settable stimulus that reaches the node chain.** A level-grade first
audio therefore needs either an external source into MIC 5 — which the loop
patch displaces — or a `DSP4_SCOPE_BLK_TAP` build, which is a hub call, not a
bench tweak.

**S48-8. `/home/app/dspboot/chip1.sym.json` is not this image's map, and
peeking through it returns plausible zeros rather than an error.** The staged
map (`f2e0c082…`) and the dspboot copy (`b694276e…`) differ. A first cut of
the loop instrument hardcoded the dspboot path, as `dsp4_apply_strip.py` does,
and every lane read `0.0000000 / -inf` across all five arms — a clean,
symmetrical, entirely fictional "the converters are silent". `_rx_active_buf`
peeked as **0**, which then addresses the RX window at absolute 128 and reads
zeros forever. `dsp4_apply_strip.py` survives the same hardcoding only because
it deliberately uses no `peek()` at all (its own docstring explains why).
Both new instruments now take the symbol directory as an argument, defaulting
to the staged pair, and `dsp4_s48_loop.py` **refuses to measure** if
`_rx_active_buf` peeks 0 twice.

## S44 LANDS AS defs-v2026.09.14.1, AND THE STRICT DIFF IS SIX FILES, NOT TWO (2026-09-14, session 47 — desk only, the unit was never touched)

**S47-1. The pin moved, the lock updated, and the diff the "how to land it"
steps predicted (`defs` + `defs.lock` only) is not the diff that landed —
six files changed, and both extra pairs are explained.** `git -C defs fetch
--tags && git -C defs checkout defs-v2026.09.14.1` (`5c827e9`), `git add defs`
to move the recorded gitlink, then `./regenerate-dsp-contract.sh
--update-lock`: SHARC codegen drift check passed first (726 files, 0 differ),
`sync-defs.sh` verified/updated the lock, `gen_dsp.py --force` backfilled —
**D32 5,765/5,765 mapped cells addressed (6,999 defined), D24 3,974/3,974
(4,985 defined)** — `check-matrix-addresses.py` passed, and a second,
independent `./check-contract-drift.sh` (no `--update-lock`) reproduced every
byte with nothing left to settle. `git status --porcelain` names six paths:
`defs`, `defs.lock`, and all four `MW/<P>/MX/_matrix.csv`. Row-by-row,
field-by-field diff against the pre-image (`git show HEAD:...`) explains all
four: **D12 and D16 — zero content diffs; the only column added is
`Neutral`, both empty (not backfilled products).** **D32 — 6,999/6,999 cells
identical on every existing column (cell set, `MxAdd`, `DspAdd`/`DspAddHex`,
everything); the only change is the same `Neutral` column landing empty-or-
coded per cell.** `MATRIX_GEN` (the console-comparable base-id) is unchanged
for all four products, and every DSP-generated artifact downstream of D32 —
`ghost_cells.h` (both copies), both `dsp_params.asm`, `dsp_address_map.md`,
`mx_dsp_map.h` — is **byte-identical before and after** (sha256 quoted).
**D24 — cell set unchanged; the `Dsp*` columns go from 0/4,985 addressed to
3,974/4,985 as R3 intends, and a further 733 `Table`/span fields differ on
cells the S44 proposal never touched.** That second class is not this
repo's doing: `git -C defs log 48745eae..5c827e9` shows the range crosses
`5cc5d44` ("Neutral column on the cell master … 16 table-span/MxDatS
disagreements noted in the schema … every product master and reference
regenerated"), landed the day before S44's tag and pulled in by the same
fetch. Advancing the pin at all — not just landing S44 — is what moves it.
**Verdict: the "only two files" expectation was written against a proposal
that predates the Neutral-column pin; the actual six-file diff is exactly
what R2 (Neutral passes through) and R3 (D24 backfilled, D32's *addresses*
untouched) each ask for, just not phrased as one diff. Nothing unexplained
moved — named here as the finding R1 asks for rather than absorbed.**

**S47-2. The cell master's `Neutral` column passes through every reader in
this repo untouched, because none of them reads a column by position.**
`common/cells/mx_master.csv` (the cell master itself) has exactly one reader
in this repo — `sync-defs.sh`'s `MX_CELL_MASTER_SHA256` check — and that
reads it as opaque bytes for a whole-file hash, not by name or index, so a
32nd column cannot touch it. The column's actual appearance is in the
per-product matrices, via `defs/tools/expand_matrix.py` (submodule code, not
this repo's). Every reader in this repo that opens `_matrix.csv` or a
product def uses `csv.DictReader` — `validate-matrix-contract.py:77`,
`check-matrix-addresses.py:64,70`, `gen_dsp.py:260,310,2869,2956,3031,3041`
— none positional. Live proof, not just grep: `validate-matrix-contract.py`
and `check-matrix-addresses.py` both ran clean above against matrices that
now carry the extra column.

**S47-3. The D24 matrix is committed with its DSP addresses — 3,974 rows
addressed, 1,011 unmapped, 3,974+1,011=4,985 — and D32 is untouched at every
level the firmware build depends on.** `MW/D24/MX/_matrix.csv` now carries
`DspSpi`/`DspPage`/`DspAdd`/`DspAddHex` on every cell `defs/products/d24/
dsp.csv` maps; this is the first commit of that file with any address in
it (previous commits: `54f29242`, `58ef0250` — both 0/4,985). D32's
`_matrix.csv` sha256 changed (`041b19a5…` → `e66c5e43…`) but the change is
the `Neutral` column alone (S47-1); its `DspAdd`/`DspAddHex` and every other
existing field are identical row for row, its `MATRIX_GEN` id is unchanged,
and `ghost_cells.h`/`dsp_params.asm`×2/`dsp_address_map.md`/`mx_dsp_map.h`/
the FW copies are sha256-identical before and after. Proposal
`proposals/CONTRACT-PROPOSAL-S44.md` marked LANDED.

## THE MFD FIX IS ON THE PART, AND THE GATE THAT WOULD HAVE DENIED IT WAS SCORING AN UNPOWERED CONVERTER BANK (2026-09-14, session 46 — on the unit)

**S46-1. The unit was off the network when the session opened and power-cycled
itself.** The dispatch's bench state records MW-D24-2 as ON and to stay on. Six
probes 20 s apart from 14:12:36Z found no ICMP reply and an ARP entry `FAILED`
on the wired segment; the whole /24 was swept for the unit's recorded SSH host
key in case it had moved address (ten hosts answered on 22, none of them it).
It booted at **14:14:20Z** (`uptime -s`, post-NTP) and answered SSH at 14:14:48
reporting *up 0 minutes*. **It was already unreachable at the first probe and
returned during the probe window**, so nothing here caused it: the only packets
sent were unanswered ICMP echoes and one TCP SYN. Corroboration points at the
supply — `vcgencmd get_throttled` = **`0x50000`** (under-voltage has occurred,
throttling has occurred) and `dmesg` **`Undervoltage detected!` at +7.7 s into
this boot, with AN_EN low and the analog rails not requested**. No prior-boot
evidence survives: one boot in the journal, no `wtmp`, no `syslog`, and the app
log is rewritten each start, so the outage can only be bounded between the
hub's last interaction (13:55Z) and the first probe. **The clock was restored
6 m 46 s behind by `fake-hwclock` and stepped by NTP at 15:14:56 BST, so every
"15:07:xx" stamp in that boot's app log is the same boot before the step** —
the app did not start seven minutes before the kernel. **The cost: AN_EN
dropped.** The hub raised GPIO26 by hand at 14:52 BST for the rail test; after
the cycle it reads low and the app leaves it there by design, so the rail-test
state is gone and the analog board is unpowered. This is S41's uncommanded-cycle
class recurring and is not attributed to any bitstream. A boot-id sentinel
(`f1078486-…`, boot 15:14:20) was re-read at every gate and never moved — **no
further cycle occurred while the work ran.**

**S46-2. §1–§4 pass.** The S42 pair staged into a new `/home/app/s42` with
`/home/app/s39` intact as rollback: `chip1.ldr` `825f9b7dac5978c973550c8e40819ba9`
and `chip2.ldr` `7b1311e8e56f008fa98046cab59293c6`, md5'd at the desk and again
on the unit after the copy, with this build's own maps (**6,155 / 3,894**
symbols). Cold start clean first try — 451,584 B and 308,224 B sent, CHIP_ID 1
and 2 verified, both chips **BLOCK 16, CCLK 983.04 MHz, shipping
configuration**, 51 + 5 registers configured. `DIAG_BUILD_CFG2` =
**`0xC2010244`** on both chips, the word the sheet requires.
`dsp4_apply_strip.py 1 1`: **13 ok / 0 mismatch**.

**S46-3. The §3 map gate failed on a correct map because `rd()` cannot read a
counter.** It reported *agree 2 / disagree 3 / not-in-map 2* against the sheet's
*agree 5 / disagree 0*. The three "disagreements" were `_diag_ticks`,
`_spi_rx_count`, `_frame_count`, and in each the **register** column read `--`
— the DIAG read raised and the peek did not; the sheet's real failure signature
is those three peeking *zero*, and they peeked 8,904 / 145 / 35,976. The
exception says it outright: `register 0xE005 never settled: {'0x100a2': 1,
'0x100a4': 1, '0x100a7': 1, …}` — **twelve asks, twelve clean answers, every
one larger than the last.** `dsp4_scope.rd()` resolves a register by voting,
needing the same non-zero value twice in twelve asks, and **a free-running
counter never repeats**. Four of the seven pairs this gate checks are counters
(TICKS, FRAME_COUNT, SEC_COUNT, SPI_RX_COUNT); it can read none of them, on a
healthy link and a correct map. Deterministic, 5 of 5 attempts each; the three
static registers answered every time. **The test that expresses the question is
a bracket — ask, peek, ask — and for a moving counter it is stronger than
equality, because a wrong address cannot track one:** chip 1 `_frame_count`
1,745,906 ≤ **1,745,915** ≤ 1,745,917, and so for all five pairs on both chips.
`Scope.rd_counter()` added, `dsp4_s39_symcheck.py` rewritten onto it, re-run on
the part: **agree 5 / disagree 0 / not-in-map 2 on both chips.** `rd()` itself
is unchanged so no other tool's behaviour moves.

**S46-4. THE ONE THAT MATTERS: the align gate was about to blame MFD for a
converter bank that was not switched on.** It reported *"bits 6:0 set on some
word — the 24-in-32 pad is not where it should be, so the window is off the
other way"*. The raw words say otherwise: over **48 words per lane across three
captures 0.4 s apart, on all twelve lanes, exactly two values appear —
`0x00000000` and `0xFFFFFFFF`** (plus rare one-bit variants `FFFFEFFB`,
`FFFFFFFB`, `FFFFDFFF`, `80280002`, a line sampled mid-transition). That is an
**idle, undriven TDM bus**. A powered, clocking AK5558 produces a *dithered*
noise floor — dozens of distinct small values in 32 words even with its input
open — never two. And **`0xFFFFFFFF` sets bit 31 AND bits 6:0**, so both of the
gate's bit tests score on it and both verdicts are artefacts of reading a rail.
The converters are unpowered for two independent reasons: the rev B analog
board's ±15 V isolation links are **all open** (the attach procedure: *"every
switching supply on the analog board is isolated from its destination
electronics by links that are NOT fitted yet"*), and AN_EN went low in the
power cycle. **`dsp4_s42_align.py` now refuses the RX verdict** when ≥ ¾ of
lanes read as an idle bus (≤ 4 distinct values, ≥ 90 % of words at a rail) and
**exits 2 — inconclusive, not failed** — naming the converters and pointing at
the register read that does not need them. Same class as S39-4, which cost a
whole measurement set.

**S46-5. S42's one-bit fix IS on the part — proved at the register, with no
converter required.** `SPORT_MCTL.MFD` is bits 7:4, written per lane by
`sport_cfg_init()` from the generated `<region>_mfd[]` tables; read back from
the SPORT MMRs at `0x31002000 + sport·0x100 (+0x80 half B) + 0x08`:

| chip | region | MFD read | generated table |
|---|---|---|---|
| 1 | rx, half A (converters), sports 0–7 | **2,2,2,2,2,2,1,2** | `c1_rx_lanes_mfd` identical |
| 1 | ic, half B (to chip 2) | **1,1,1** | `c1_ic_lanes_mfd` identical |
| 2 | ic, half A (from chip 1) | **1,1,1** | `c2_ic_lanes_mfd` identical |
| 2 | tx, half B (to the DACs) | **2,2,2,1,2** | `c2_tx_lanes_mfd` identical |

**Nineteen lanes, nineteen matches, both chips**, including the deliberate
exceptions — chip 1's lane 6 and chip 2's TX lane 3 are the CPLD/fabric lanes
and are correctly still MFD 1. This read is now part of the gate, and it is the
part of §5 that a bench with no analog board can always take.

**S46-6. The morning sheet's §0 is wrong on one point, and the dispatch
inherited it.** §0 says *"§1–§6 in full — the whole DSP side … none of it needs
the analog board"*. True for §1–§4 and §5.3. **False for §5.1 and §5.2**: their
pass criteria are the *converter* noise floor (−65…−85 dBFS) and *twelve
distinct converter* noise floors, both statements about powered AK5558s. Those
two sections belong in the "when the links are in" list. Separately,
`dsp4_s42_align.py` **had no chip-2 receive section at all** — it scored chip
1's RX and chip 2's TX and nothing between — so the gate could not have
satisfied the dispatch even on a healthy unit. Every symbol it needs is
exported by this image (`_c2_ic_rx_off/_stride/_ptrs`, `_ic_rx_active_buf`, a
`_rx_ic_slot_<NAME>` per node); the section was written, resolves **by name**
through the pointer table as the TX section does, and runs: `C2_RECV_MAIN_L`
idx 0, `MAIN_R` 1, `SUB` 2, `GRP_01` 3, `AUX_01` 7, `AUX_02` 8, `FX_01` 19.
`C2_RECV_MTX_01` does not resolve in `_c2_ic_rx_ptrs` — recorded, not chased.

**S46-7. TX passes by name, and a scoring gap was found in it.** All five nodes
resolve through `_c2_tx_ptrs`, so S42's slot move is on the part:
`C2_AUX_OUT_01` off 7 (`DAC_08` → rear XLR **Aux Out A1**), `C2_AUX_OUT_02`
off 6, `C2_MAIN_OUT_01` off 131 (`DAC_12` → J56 MAIN L), `C2_MAIN_OUT_02`
off 130 (`DAC_11` → J57 MAIN R), `C2_MAIN_ST_OUT` off 384. **AUX 1 is no longer
above full scale** — S39-6 read 1.538 Q4.28 (+3.75 dBFS), it now reads 0.00000
— but with no converter input that is **not positive proof of level**: 0 is
also what a dead path reads. The gap: the tool failed a TX lane only at
`pk > 8.0`, the Q4.28 accumulator ceiling, while **the sheet's §5.3 criterion is
inside ±1.0 — and S39-6's 1.538 sits between the two**, so the ceiling test
alone would have *passed* the exact reading the gate exists to catch. The ±1.0
criterion is now applied.

**S46-8. Hand-back, and one open question in it.** `matrix-app` active, pins as
found, **AN_EN read at every gate and never written**, GPIO27 / SWD selects /
analog board / rocker / `logic_flash.sh` untouched, MCU boot verification
all-pass on the restart. **The DSPs were left booted with the S42 pair and
streaming.** R3 asks for them stopped unless the sheet names streaming as the
app's expected state, and it does not; they were left up because stopping them
means driving !RST_D (GPIO16) low and holding it — a larger departure from "as
found" than leaving them running — and because the app cannot query DSP state
either way (`[??] DSPs booted and streaming — no boot-state query`). **The hub
should rule on which it wants.** No contract artefact moved: `defs.lock`,
`dsp.csv`, the SPI addresses, both `_matrix.csv` and every generated file are
untouched, so no version bump.

## THE MATRIX IS THE APP'S ONLY SOURCE OF DSP ADDRESSES, AND D24'S WAS EMPTY (2026-09-13, session 45 — desk only, the unit was never touched)

**S45-1. The backfill runs for every product now, from that product's own
landed map.** `MW/D32/DSP/gen_dsp.py` filled the `DspSpi`/`DspPage`/`DspAdd`/
`DspAddHex` columns of `SCRIPT_DIR/../MX/_matrix.csv` — D32's, and only D32's —
so `MW/D24/MX/_matrix.csv` carried an address on **0 of its 4,985 rows** while
`defs/products/d24/dsp.csv` mapped 3,737 of those cells (S44-5, the gap S38-5
named on 2026-09-12). The two globals are now per-product
(`matrix_csv_path()` / `matrix_stage_path()`), `backfill_matrix()` takes the
map to fill FROM rather than reading a module global, and each product is
filled from `defs/products/<p>/dsp.csv` — **its own**, not the merged map: one
shared address map (decision D3) does not mean one shared cell set, and a
D32-only cell has no business carrying an address in D24's matrix. Measured
here: per-product and merged select exactly the same cells today (3,737 for
D24, 5,409 for D32), so the stricter rule costs nothing and closes the case
where it would not.

**Both counts, run.** `gen_dsp.py --backfill-report` (new; reads, generates
nothing, names the provenance it counted):

| map | D24 cells with an address | D32 |
|---|---:|---:|
| landed, `defs-v2026.09.08.4` | **3,737** of 4,985 | 5,409 of 6,999 |
| the S44 candidate (`DSP_LANDED_DIR=proposals/defs/products`) | **3,974** | 5,765 |

`rows-with-address + named-unmapped == cells defined` is asserted per product
before anything is written — 3,974 + 1,011 = 4,985 and 5,765 + 1,234 = 6,999
under the candidate — and the assertion is not decorative: renaming one D24
matrix cell to a name in neither file stops the run naming that cell.

**The D32 matrix is byte-identical to before, to the hash.** A full candidate
generation in a scratch tree and a full `DSP_LANDED_DIR=proposals/defs/products
./regenerate-dsp-contract.sh` in the real tree both leave
`MW/D32/MX/_matrix.csv` at
`041b19a585a93f6f24f53609da1e0502a893db20ad3dbea99d0e5cd5e3da8b8f` — the hash
it has carried since `cea457e0` — with D12, D16, `ghost_cells.h`,
`dsp_address_map.md`, both `dsp_params.asm` and all 765 SHARC sources
unchanged. The change adds D24; it perturbs nothing. Idempotent: a second and
third run (with and without `--force`) reproduce D24's matrix to the byte.
D24's matrix gains the five `Ramp*` columns D32 already had, 32 columns to 37.

**And `sync-defs.sh` no longer keeps its own copy of the list.** It carried
`STAGED_PRODUCTS=(d32)` under a comment asking the next person to keep it in
step with `gen_dsp.py` by hand — the arrangement that produced this gap. Both
halves now read `gen_dsp.py --backfill-products`. D24's expansion is staged
exactly as D32's is, so an abort between the two processes leaves D24's
committed matrix whole too: verified by running the landed-pin
`./check-contract-drift.sh`, which still exits 1 on the S22 drift and leaves
all nine contract artefacts byte-identical.

**S45-2. The app reads the matrix, and only the matrix — so the empty column
was the whole gap, and nothing in the app has to change.** In mx26,
`Core/AppContext.ResolveMatrixPath()` resolves ONE artefact
(`{HomePath}/config/_matrix.mxc` packed, else `_matrix.csv`, else the
published `{store}/Products/<P>/pd/generated/_matrix.csv`);
`Core/Boot.LoadMatrixData()` loads it and `Core/ProjectBuilder.Matrix.cs
::GetMatrixCsvHeaders()` resolves the columns **by header name** —
`DspI2c`, `DspSpi`, `DspPage`, `DspAdd`, `DspAddHex` — into
`dspI2cHdr … dspAddHexHdr`. Nothing computes an address, nothing carries a
fallback table, and a column that is absent or empty reads as `(undefined)`
(`Views/DspViewer.axaml.cs::SafeCsvRead`). **Format: decimal in `DspAdd`, the
same value as `0xNNNN` in `DspAddHex`, chip in `DspSpi` (1 = DSPA, 2 = DSPB)
and page in `DspPage` — four columns, all strings, exactly what the backfill
writes.** So the D24 matrix as produced satisfies the loader unchanged: **no
mx26 change is required for the app to have the addresses.**

What the app does NOT yet have is a writer. `DspViewer` is the only consumer
of those columns and it DISPLAYS them; the only SPI code in the app is
`Services/AnalogChainHardware.cs::SpiDevChain`, the 74HC595 analog chain on
`/dev/spidev0.0`, which is not the DSP link. That is an mx26 hub item and is
named as one below — not a dsp change and not made here.

**The equivalence, cell by cell.** For the 13 cells
`tools/pi/dsp4_apply_strip.py` writes by name for strip 1 → MAIN + AUX 1, the
address the matrix now carries equals what the tool computes, **13 of 13**,
chip/page/decimal/hex all four: `Chan001Gain001` 1/1/0/`0x0000`,
`Chan001Pol001` 1/1/1/`0x0001`, `Chan001Level001` 1/1/80/`0x0050`,
`Chan001Pan001` 1/1/81/`0x0051`, `Chan001Mute001` 1/1/82/`0x0052`,
`Chan001MainOn001` 1/1/84/`0x0054`, `Chan001AuxOn001` 1/1/90/`0x005A`,
`Chan001AuxSend001` 1/1/102/`0x0066`, `Chan001AuxPick001` 1/1/114/`0x0072`,
`Aux001Level001` 2/1/0/`0x0000`, `Aux001Mute001` 2/1/2/`0x0002`,
`Main001Level001` 2/1/1379/`0x0563`, `Main001Mute001` 2/1/1381/`0x0565`. It
could hardly be otherwise and that is the point: the tool reads
`landed-d24.json`, which `tools/dsp/landed_map.py` cuts from
`defs/products/d24/dsp.csv`, and the backfill fills from the same file. None
of the 13 moves between the landed map and the S44 candidate.

**S45-3. The intake gate catches an empty address column.**
`check-matrix-addresses.py` (new), run by `check-contract-drift.sh` after the
regeneration and by `regenerate-dsp-contract.sh` after its own. **This class
could not have been caught by anything already in the path, and that is why it
survived:** `sync-defs.sh` verifies the EXPANSION against `defs.lock` and the
expansion has no DSP columns by design; `validate-matrix-contract.py` checks
MxAdd continuity and the family allowlist; `--strict` asks git whether the
file CHANGED, and a file that was never right does not change; `gen_dsp.py`
validated the product it backfilled and was silent about the one it did not.
Four gates, each individually correct, and between them a matrix that
published none of the addresses it exists to publish.

It checks, per product `gen_dsp.py --backfill-products` names (so the gate and
the tool cannot hold different lists): zero addresses against a non-empty
landed map; every mapped cell carrying the map's address; no address the map
does not give; and the four columns filled together with `DspAddHex` agreeing
with `DspAdd`. **Negative controls, eight, each against a scratch copy of a
tree the gate passes clean:** whole address column blanked → caught (the S44-5
class, by name); 12 mapped rows blanked → caught; one address off by one →
caught, cell named, both values printed; `DspAddHex` set to `0xDEAD` → caught;
one row left with `DspAdd` and no `DspSpi`/`DspPage`/`DspAddHex` → caught as
ragged; an address written onto an unmapped cell → caught; the `DspAdd` column
removed → caught; the matrix deleted → caught. Exit 1 on all eight, exit 0 on
the control.

**S45-4. What this does NOT land, and what it is waiting on.** No matrix was
committed. `gen_dsp.py` cannot generate from the landed pin at all — it exits 1
in `check_proposal()` on the S22–S25 drift, as it has since S22 — so the only
generation that runs today is the candidate one, and those rows have not
passed the hub gate. Run in the tree it is clean and complete (exit 0, D24's
matrix the only artefact changed), and it was restored rather than committed,
per dispatch. **The consequence to hold: from now on
`DSP_LANDED_DIR=proposals/defs/products ./check-contract-drift.sh` leaves a
real 4,985-row diff in `MW/D24/MX/_matrix.csv`. It is correct output with
ungated provenance — do not commit it.** Landing the S44 candidate makes the
landed run work, and D24's 3,737 addresses then land in an ordinary
regeneration with the pin describing them.

## THE GATE NO LONGER DAMAGES THE TREE, AND THE 237 CELLS ARE ONE CLASS (2026-09-13, session 44 — desk only, the unit was never touched)

**S44-1. The contract intake path is atomic, and a restore-on-failure trap
would not have been.** `check-contract-drift.sh` left `MW/D32/MX/_matrix.csv`
with five DSP columns blank on all 6,999 rows whenever it failed (S43-5),
because `sync-defs.sh` wrote the bare expansion over the committed file and
`gen_dsp.py` aborted before the backfill wrote it back. Both halves used
`open(path, 'w')`. **Fixed with temp file + rename, not a trap, and the reason
is the one the gate asked for: a trap needs the process to survive to run it.**
`kill -9`, a segfault, an OOM kill and a power cut all skip it, and that is
exactly the window in which a file is half-written; `rename(2)` is atomic
within a filesystem and needs nothing to survive. **Measured:** a 195 MB
payload written over a 12-byte file with the writer `SIGKILL`ed at fifteen
points — `open(path,'w')` left the target **half-written on 4 of 4** kills that
landed mid-write, the temp+fsync+rename path on **0 of 5** (all five left the
whole old file). **A second fault in the same lines:** `sync-defs.sh` hashed the
expansion against `defs.lock` AFTER writing it over the committed file, so a
lock mismatch — the one thing the lock exists to catch — exited 1 with the tree
already rewritten by the definitions it had just refused. **Per-write atomicity
is not enough**, because the finished D32 matrix is the output of two
processes: `sync-defs.sh` now STAGES D32's bare expansion at
`MW/D32/MX/_matrix.expansion.csv` and `gen_dsp.py` is the only writer of the
finished file, so between them the committed file still holds the last complete
generation. Negative controls, all against the committed tree with nine
contract artefacts hashed together: `sync-defs.sh` `SIGKILL`ed at 9 points,
`gen_dsp.py` at 11 points across its 0.815 s, the pair run to completion 3
times, and the real gate run to its no-fallback exit 1 — **artefacts changed on
0 of 24**. `_matrix.csv` reads `041b19a5…` throughout, the hash it had at
`cea457e0`. Commit `aed43455`, on its own.

**S44-2. The `DSP_LANDED_DIR` banner was invisible in the one gate that needed
it.** `check-contract-drift.sh` runs `gen_dsp.py --force >/dev/null`, and the
"these rows have NOT passed the hub gate and the defs pin does not describe
this build" banner went to **stdout**. A whole contract check could therefore
pass against ungated rows in complete silence. Moved to stderr. Found only
because this session used the flag to run the gate against the candidate.

**S44-3. The 237 D24 cells (and D32's 356) are ONE class: cells the landed
file already names as unmapped.** Not four classes — 237 of 237 are "a cell the
generator now emits that the landed file predates", and **zero** are an address
that moved, a mask/scope difference, or the S42 lane fix. Checked directly:
all 3,737 D24 / 5,409 D32 rows present in both files are identical in **every**
column, nothing is removed from either map, and
`rows(dsp.csv) + rows(dsp-unmapped.csv) == cells(_matrix.csv)` holds on both
sides (D24 3,737+1,248 = 3,974+1,011 = 4,985; D32 5,409+1,590 = 5,765+1,234 =
6,999). The disagreement is entirely a MOVE from the unmapped file into the
mapped one. **Attributed to the commit, summing exactly:** `9ffdb4ee` S22 the
matrix mixer built — 100 (`ChanMatrixOn`/`Send` ×96, `MatrixLevel`/`Mute` ×4);
`4fdfe5ed` S23 the FX returns given a bus and the comp GR meter published —
120 (`FxAuxOn`/`Send` ×96, `ChanCompMtr` ×24); `86f972a3` S24 main outputs
given their level and mute — 17. D32 adds `24f46ca1` S25's 32 `ChanLcrOn` at
the wider strip and send counts. **The dispatch's three guesses are all no:**
not new GEQ cells (the 31-band GEQ landed *in* `defs-v2026.09.08.4`), not the
24-strip mask, not the S42 lane rows — `8f4a9d17` changed the DAC lane ↔ XLR
mapping and the cell set is identical either side of it.

**S44-4. The committed generated tree is ALREADY built from the candidate;
only `defs` lags.** Running `DSP_LANDED_DIR=proposals/defs/products
./check-contract-drift.sh` passes (exit 0) and rewrites every generated
artifact — and leaves **no diff**. `MW/D32/MX/_matrix.csv` carries DSP
addresses on **5,765** of 6,999 rows where the landed map covers **5,409**;
`ghost_cells.h` says `GHOST_CELLS_COUNT 5810`, the proposed union, not the
landed 5,449. So the gate's failure since S22 has not been tree drift at all —
it is a contract bump that was never taken to the hub, and landing the proposal
makes the pin describe the tree again **without moving a byte of the tree**.
The proposal is filed and NOT landed (`proposals/CONTRACT-PROPOSAL-S44.md`):
mapping-only, strictly additive, no cell name repurposed, no existing address
moved, 318 multi-cell addresses before and after, so a host built against the
landed map keeps working unmodified and gains 361 reachable addresses.

**S44-5. `MW/D24/MX/_matrix.csv` carries no DSP addresses at all — 0 of 4,985
rows — and landing the proposal will not change that.** `gen_dsp.py` backfills
D32's matrix and only D32's (`MATRIX_CSV` is D32's path; `CONTRACT_PRODUCTS`
reads D24's matrix for the cell list but never writes it). A D24 app reading
the matrix has no address column and must go to `defs/products/d24/dsp.csv`
directly. That is the single-SOT gap S38-5 named, still open, and it is a
generator item rather than a contract one. Related, unfixed and named rather
than left to be discovered: `tools/dsp/dsp_codegen.py` is now atomic
**per file** but is a two-pass emitter, so a kill between passes leaves 61
whole first-pass node files — no truncation, but not a transactional tree.
`check-sharc-codegen-drift.sh` catches it by content and a rerun repairs it;
making it transactional means generating to a scratch tree and swapping the
directory.

## THE TREE WAS STALE, NOT HAND-EDITED, AND NO SHIPPING BYTE MOVES (2026-09-13, session 43 — desk only, the unit was never touched)

**S43-1. The 117-file divergence is 64 code lines in `C1_FILT_01..32` only,
and they are dead.** S42-5 attributed the code lines to "every `C1_FILT_*` and
`C1_EQ_*` node". Sorted by content, the 117 files are: **32 `C1_FILT_*` files
carrying 64 code lines** (`i6 = BLK_CHAIN_B` or `BLK_CHAIN_B_P1`, plus
`l6 = 0;`, in `_<nid>_process_sample`) and **117 files carrying a superseded
comment paragraph** — the FILT 32 again, 32 `C1_EQ_*`, `chip1/shared_kernels.asm`,
51 chip-2 nodes and `lib/num_selftest.asm`. **The EQ nodes never had the code
lines**: `SHARED_KERNEL_CLASSES` declares a `pool_reg` for `FILT` only, so
there was nothing for the generator's split to remove. Every one of the 64 is
a deletion — the tree carries them, the generator does not emit them. **They
are dead code**: `_shk_filt_smp` (`chip1/shared_kernels.asm:624`–`807`) never
reads `i6` or `l6`, and neither does anything it reaches
(`_shk_filt_start_xfade` `808`–`1034`, `_bq_fx_cascade_N`
`lib/biquad_fx.asm:114`–`236`, `_bq_fx_convert_N`, `_bq_hr_ask`). The BLOCK
half does read `i6` (`.fkb_ss_shkfilt`: `i2 = i6;`) and the generator still
emits it in the `_process` stub, which is unchanged.

**S43-2. The cause is a generator change committed without a full
regeneration — twice, six minutes apart. Not a hand-edit of generated
output.** The 64 code lines and the generator hunk that removes them landed in
the SAME commit, `4807d23d` ("S26 gate 1: the fix sweep, and gate 2's generator
work", 2026-09-10 22:07): it created `chip1/shared_kernels.asm` (954 lines,
new file), **added** the `pool_in_blk`/`pool_in_smp` split to
`dsp_codegen.py` (`grep -c pool_in_smp` on its parent → **0**, on it → **5**)
and committed `C1_FILT_*` stubs generated before that hunk existed. **The
commit's own generator would not produce the commit's own node files.** The
comment hunk is `608a1aa3` ("S26 gate 1 witnessed on the part", 22:13), which
corrected the alpha-overflow wording in `dsp_codegen.py` and `fixed_ref.py`
after the bench measured `fix` at three overflow points — and touched **no
generated file** (three files in its stat: the S26 write-up and those two
tools). So the mandate was not breached in the way the dispatch braced for:
nothing needed to go back into the generator, because the generator already
carried the intent, in a comment it still carries
(`dsp_codegen.py:14535`: *"a stub that loads a register that half never reads
is not tidy-looking waste, it is ~3 M instructions a second. FILT reads it in
the block half only."*).

**S43-3. The reconciled tree builds S42's shipping pair byte for byte, because
those 64 lines have never been compiled into a shipping image.**
`DSP4_SHARED_KERNELS` is not named in `shipping.config` and `build.sh` defaults
it to **0**; the 64 lines are inside `#if (DSP4_SHARED_KERNELS & 8)`. Built on
this machine, `./build.sh clean && ./build.sh all`, before and after the
regeneration: **both arms give
`825f9b7dac5978c973550c8e40819ba9` / `7b1311e8e56f008fa98046cab59293c6`** —
S42's recorded pair, reproduced twice more (four times in total counting the
final restage). **Priced with a control rather than asserted**: built at
`DSP4_SHARED_KERNELS=15`, the arm where the lines DO compile, chip 1 goes
**356,152 B `e2c532794eb64a3bb81a89832d2a8f29` → 355,896 B
`b3b3ee4a461faed9129c22e1792f232b`** — **−256 bytes, exactly 64 lines × 4
bytes of loader stream** — while chip 2 is byte-identical
(`5699b311635fe360b803baecfbb2d7d5`) in both arms, which is what a chip-1-only
change must read. `shared_kernel_check.py`'s record-layout gate passed on the
reconciled tree. **Consequence for the record: no measurement on this project
was taken on the wrong side of this divergence** — every on-part anchor
S19–S39 is a `SHARED_KERNELS=0` image and the comment hunk cannot move bytes at
all. The only casualty is S26's chip-1 code-pool table, taken on the
unreconciled tree, which carries 8 bytes per FILT instance it need not have.
The generator is idempotent: a second `--force` run changes nothing further.

**S43-4. Nothing checked the 726 generated SHARC files, in either script, and
`git status` could not have caught this anyway.**
`check-contract-drift.sh` ran `sync-defs.sh`, `validate-matrix-contract.py` and
`MW/D32/DSP/gen_dsp.py --force` and called that "re-runs the whole generation";
`regenerate-dsp-contract.sh` had the same hole, so "run the regenerate script"
left 726 files untouched. Strict mode would not have helped: it diffs
`git status` over thirteen paths, none of them a node file, and drift that is
already committed is invisible to `git status` by construction — which is
exactly the shape this had. **Fixed by `check-sharc-codegen-drift.sh`**: it
generates into an **empty** scratch directory (never a copy of the tree, which
would let the tree's own content leak into the thing it is checked against) and
requires every emitted file to be byte-identical to its committed counterpart —
**726 emitted, 0 differ, 50 hand-written**. The hand-written 50 are checked by
name too, so a generator that quietly stops emitting a file falls out of the
generated set into the declared set and the list stops matching, rather than
silently leaving the gate. **Three arms run: pass on the reconciled tree; fails
with 117 files on the tree as committed this morning; and `--negative-control`
(one line of `C1_FILT_01.asm` hand-edited to load strip 2's record base — it
assembles, it is wrong, nothing else says so) fails with 1.** Wired in **first**
in both scripts, before `sync-defs.sh`, because the later steps currently fail
for a pre-existing reason (S43-5) and an appended check would be masked by that
failure forever; the SHARC gate depends only on `dsp.csv` and the generator, so
it stands alone. `smoke-checklist.md` carries the negative control as a
standing step.

**S43-5. A failing `check-contract-drift.sh` leaves `MW/D32/MX/_matrix.csv`
damaged, and the failure itself is still the pre-existing hub item.** The gate
cannot pass today, for the reason S38-8 and S42-12 named and not for anything
in this session: `gen_dsp.py --force` exits on the no-fallback policy —
**237 cells on d24** that the landed `defs/products/<p>/dsp.csv` lacks and
`dsp-unmapped.csv` carries. That is the policy working (the graph has advanced
past the pinned `defs-v2026.09.08.4`) and the fix is a new `dsp.csv` proposed
to the hub gate, never a hand-edit of the landed file. **New here:** when it
fails there it leaves the matrix half-regenerated — `sync-defs.sh` re-expands
from `defs/` without the DSP columns and `gen_dsp.py` aborts before backfilling
`DspI2c`/`DspSpi`/`DspPage`/`DspAdd`/`DspAddHex`, so all 7,000 rows are left
with those five columns blank. It reads as a 7,000-line diff and is not drift;
it is a half-finished regeneration. Restored with `git checkout --` here.
**A failing gate should not leave the tree worse than it found it.** Recorded,
not fixed: the fix is a temp-file-and-rename in `sync-defs.sh` or a
restore-on-failure trap, which is a change to the contract intake path and
wants a hub round-trip.

## THE ONE BIT IS AN AKM STRAP, AND AUX 1 WAS LEAVING ON THE WRONG XLR (2026-09-13, session 42 — desk only, the unit was never touched)

**S42-1. The one-bit-late RX capture is `SPORT_MCTL.MFD`, and the value is
2.** S39-4 measured `received = (sample >>> 1)` on all twelve chip-1 lanes:
bit 31 never set, bits 6:0 never set. That is a receive window that opens one
serial clock EARLY — the shift register takes one extra bit before the MSB and
ends holding `{previous bit, sample[31:1]}` — and the extra bit is always zero
because the converters send 24 bits left-justified in a 32-bit slot, so the bit
before slot *n*'s MSB is slot *n−1*'s pad. Three signatures, one mechanism, no
free parameters. **The cause is a strap, read off D24 Analog rev B sheet 13/64
"ADC8": `DIF0-1 = 10 = I2S 24-bit`, `TDM0-1 = 01 = TDM128`** (pin block:
`+3V3→DIF0`, `GND→DIF1`, `GND→TDM0`, `+3V3→TDM1`), and mx26's read of the DAC8
sheet records the same two straps on the AK4458. The I2S TDM variant puts ONE
bit clock between the frame edge and the MSB; `dsp4_clkgen.v` already asserts
FS one BCK8 period before slot 0; so the converter's MSB lands at period 1 and
`MFD` must be **2**, where `sport_config.c` hardcoded **1** (HRM rev 0.3
§21-34/35: with `MFD = 0` the first received bit is sampled in the same serial
clock cycle as the frame sync). **The CPLD's FS phase is not a lever**: the DSP
and the converters are slaved to the same FS, so moving it moves both — only
the converter's strapped frame-to-data delay against the SPORT's MFD changes
their relative alignment. Fixed in the tracked source.

**S42-2. The transmit side has the exact mirror, and the CPLD loopback was
structurally blind to it.** The same `cfg_region()` wrote `MFD = 1` on the
chip-2 TX halves, so the DSP launched slot 0's MSB one BCK before the AK4458's
window opened and the DAC latched `{DSP word[30:0], first bit of the next
slot}` — the value doubled with the sign bit thrown away. The 24-in-32 padding
does not save this direction; the lost bit is the MSB. **`DSP4_LOOPBACK`, the
instrument built to close "sample edge / MFD" by measurement, feeds every DSPA
input lane from the matching DSPB output lane through a wire, so both ends use
the same MFD and a symmetric error cancels exactly.** Its slot-order and
pair-order results stand; this one was never in its reach. The transmit framing
is proved by the analog loop and by nothing else: with RX right, AUX 1 → MIC 1
must return a clean scaled copy, and a still-early transmit returns a doubled,
sign-wrapped one.

**S42-3. MFD is per lane, and that is what lets the fix land without a CPLD
flash.** Two framing peers on one board: the pin-strapped AKM converters
(everything on LOGIC's `conv_bck`/`conv_fs` pair) need `MFD = 2`, and the two
halves the CPLD's own re-framer serves — the Pi PCM lane into DSPA I6 and the
DSPB O3 lane it captures for the Pi's return — are built for `MFD = 1` and say
so in `dsp4_pcm_reframe.v`'s `out_period`/`in_period` comments. The inter-chip
mix fabric is DSP-to-DSP and symmetric, so it is left at 1. Generated result:
`c1_rx_lanes_mfd = {2,2,2,2,2,2,1,2}` (lane 6 = A_I6 = Pi PCM),
`c2_tx_lanes_mfd = {2,2,2,1,2}` (lane 3 = B_O3 = Pi return), fabric all 1. A
single global `MFD = 2` would have misframed the Pi's two lanes against the
bitstream that is on the part; per lane, the converter fix lands on
`s41_mhrx_pullup_off.15f3ae07dae1` with nothing else moving. Bringing the Pi
lanes to the converter convention later is two constants in
`dsp4_pcm_reframe.v` (`out_period + 1 → + 0`, `in_period − 1`) and two table
entries, together.

**S42-4. AUX 1 was leaving the unit on the Aux Out A8 XLR, and that alone
explains S39-6.** The OUT_1-8 analog block is REVERSED — AK4458 U81 channel *n*
comes out of rear XLR `OUT_(9−n)`, traced independently on the analog board and
again on the phone-jack board (mx26 `d24-analog-paths.csv`, 267 completed
paths) — and the DSP slot map did not compensate. mx26 filed exactly this
question in S-11 ("either the dsp slot map compensates already, or the sixteen
`OUT_nn` rows need their `carries` column changed"); this session is that check
and the answer is that it did not. PW's bench cable is AUX OUTPUT 1 → MIC INPUT
1. **The DAC was converting the whole time; the signal was leaving on a
connector nobody had a cable in**, which is sufficient on its own for "the DSP
side is proven good from the strip to the TX DMA buffer, and MIC 1 hears
nothing" with no analog fault anywhere. The OUT_9-16 block is a DIFFERENT
derangement, readable only from sheet 12/64: `DAC_09/10` = PHONES L/R,
**`DAC_11` = MAIN R (J57), `DAC_12` = MAIN L (J56)**, `DAC_13` = U92 channel 5
= **not connected** (pins 32/33 are one-pin nets), `DAC_14` = Centre/LF (J55),
`DAC_15/16` = Monitor L/R (J53/J54). Main Out 1 was on `DAC_13` and Main Out 2
on the Centre/LF XLR, so nothing reached the MAIN XLRs at all. Fixed: aux *n* →
`DAC_(9−n)`, Main Out 1/2 → `DAC_12`/`DAC_11`, aux 11/12 onto the two slots
they vacate. Twelve rows of `dsp.csv`, **no SPI address moved**. Full table and
the six product questions it does not settle:
`docs/d24-dac-lane-xlr-candidate-20260913.md`.

**S42-5. S39-5b's "seven of eight chip-2 TX lanes always zero" is an instrument
artefact.** `dsp4_s39_outpath.py` walks `_c2_tx_off[lane]` for `lane in
range(0, 8)` and prints "TX lane 0..7". That array is not indexed by TDM lane —
it is the 24-entry TX **node** table ordered by (sport, slot), and its first
eight entries were `C2_AUX_OUT_01..08`, all on lane B_O0. "Lane 0 is AUX 1" is
entry 0 and is right; "lanes 1–7 always zero" is aux 2–8 carrying nothing,
which is correct behaviour; and **MAIN was never in the window** —
`C2_MAIN_OUT_01..04` are entries 12–15 and `C2_MAIN_ST_OUT` is entry 18, and
the tool stopped at 7. Same class as S39-1: a reading addressed positionally
through a table that is not indexed the way the label says.
`tools/pi/dsp4_s42_align.py` resolves nodes by NAME through `_c2_tx_ptrs`.

**S42-6. The capacity gap is a configuration the product does not ship, and the
part says so in its own register.** Fit tables: D24 driven 59.8 % / 84.4 %.
Part: 114.9 % / 103.1 %. `shipping.config` → `DIAG_BUILD_CFG2 = 0xC2010244`,
which is exactly what S39 read off both chips; `shipping.config.s26`, the
anchor under every fit table since S20, → `0xC2019E6F`. Six switches differ and
all six are capacity levers: `STRIP_FUSED`, `SIMD_DYN`, `C2_BQ_GRAPH`,
`GATE_LINTHR`, `DYN_LUT`, `SHARED_KERNELS`. **So the shipping configuration
contains nothing the fit tables did not price — it is the other way round.**
GEQ at 31 bands on twelve aux buses / four groups / the main bus, twelve aux
chains, the 24-strip mask and block 16 are all inside the 59.8 % / 84.4 %. S19
measured and said this on 2026-09-10 and `shipping.config.s20` has been the
staged proposal ever since; S39-3 re-found it. Decision sheet with the three
cheapest levers priced:
`MW/D24/DSP/dsp4-capacity-decision-20260913.md`. No configuration or generator
change was made.

**S42-7. The 114.9 % was measured with every input at full scale, by
accident.** S39-4's artefact pinned the meters at −0.00 dBFS peak in every arm
including a muted one, so every gate and compressor on chip 1 was fully engaged
for the whole measurement. On the shipping configuration (`DSP4_DYN_LUT=0`)
driven costs **+42.5 points on chip 1 and +29.3 on chip 2** over silent-loaded.
With S42-1 fixed the inputs return to a −65…−85 dBFS noise floor. **Prediction,
falsifiable in S40's first ten minutes: chip 1 falls toward ~76 %, chip 2 toward
~90 %.** It does not change the decision — a mixer is not specified at idle —
but the number PW decides against should be the honest one.

**S42-8. `logic_flash.sh`'s default rollback was stale again, the same way.**
It read `s37_shipping_step0.c62c024714f2.svf`, which is what S41 rolled back TO
during its control arm, not what it LEFT on the part — S41 finished by
re-flashing the fix. A default rollback that is not what is on the part is a
second unannounced flash, which is the exact defect S41 had fixed one step
earlier and then reintroduced by setting the line before its last flash instead
of after it. Now `s41_mhrx_pullup_off.15f3ae07dae1.svf` (md5
`fc6ce23ed14cda464f277a56cf21ab92`), with both stale values kept in the help
text so the pattern is visible. **Set this line AFTER the flash, from the flash
log.**

**S42-9. The MHRX pull-up is in main's LOGIC tree, and pin 74 alone changed.**
The three qsf lines appended to main's `dsp4_logic.qsf` (the branch is NOT
merged and must not be — its diff also reverts a comment, and its parent would
revert main's 247 LEs). Main was built first as a control and reproduced
`dsp4_logic.4f702a181b61.pof` byte for byte. With the lines:
**`dsp4_logic.ed70d3214c29`, pof md5 `ddab649702a8cf333673b5aa677daa1d`, built
three times byte-identical**, sim gate PASS on 5 testbenches, 403 LEs (29) /
295 registers — **identical**, slot-map hash unchanged. The 145-row package-pin
table differs on **exactly one row**: pin 74, `RESERVED_INPUT_WITH_WEAK_PULLUP`
/ Weak Pull Up On → `mhrx` / input / 3.3-V LVTTL / Weak Pull Up **Off**. The
fitter DID re-place the design (LABs 53→52, every control signal in a different
cell, average interconnect 14.6 %→12.7 %, `blink_led`'s Fast Output Connection
flipping — placement, not termination), said out loud so nothing is later
attributed to a change this artifact does not contain. **This is the 403-LE
step-2 lineage, not step 0**: flashing it puts 247 never-benched logic elements
on the part, which is S37 §4.2's reason for staging it separately. A bench
session's job, under the four-flash discipline, not a side effect.

**S42-10. An svf md5 is not a reproducible identity; a pof md5 is.** Two builds
of the identical design give different svf md5s because the svf carries the
build timestamp in a comment line (`!Device #1: 5M1270Z - ... <date>`); with
`!` lines stripped both are `5edfb2f4eff1bf0fc680cbedf74a5306`. S41 quoted an
svf md5 as identity. The svf md5 is still the right thing for
`logic_flash.sh` to verify — that checks the exact bytes staged on the bench —
but it cannot be re-derived from source, and a manifest that means "this is
rebuildable" should quote the pof.

**S42-11. The committed SHARC tree is not what the generator produces, and 64
of the differing lines are code.** `dsp_codegen.py ... --force` on the
committed tree rewrites **117 files**. Most is comment prose, but the
regenerated `_process_sample` path of every `C1_FILT_*` and `C1_EQ_*` node
drops `i6 = BLK_CHAIN_B_P1; l6 = 0;`. Pre-existing drift — the generator moved
and the node files were regenerated with a `--node-type` filter that did not
cover them. **Reverted, not absorbed**, so S42's diff is only S42; S42's own
generated delta was taken by running the old and new generators into two
scratch trees, diffing them (15 files), verifying each of the 15 byte-identical
between the old-generator output and the committed tree, and copying only
those. The per-sample path is not the hot path under `DSP4_BLOCK_KERNELS`, so
this has not been executing — but either the generator is right and the tree
should be regenerated wholesale, or the tree is right and the generator has a
defect, and nothing checks. Same class as S39-1.

**S42-12. `gen_dsp.py --force` refuses, and it refused before S42 too.** The
graph proposes 356 cells on d32 and 237 on d24 that the landed
`defs/products/<p>/dsp.csv` does not carry — `Chan*CompMtr001`, `Chan*LcrOn001`,
`Chan*MatrixOn/Send*` — and the landed `dsp-unmapped.csv` carries exactly those
same cells. That is the no-fallback policy working: the graph has advanced past
the pinned `defs-v*` tag and the generator will not quietly write the graph's
answer. **Verified pre-existing**: stashing every S42 change and re-running
gives byte-identical error text and the same two counts. **So no contract
artifact moved this session and no contract version bump is warranted** —
S42-4's twelve slot moves changed no SPI address, no cell and no `_matrix.csv`
row. The pin lag is a hub item: a `dsp.csv` proposal for the 356/237 cells.

## MHRX FALLS NOW — THE CPLD WAS THE ONLY PULL-UP, AND THE `poweroff` PROXY DOES NOT TEST THE ACK (2026-09-13, session 41)

**S41-1. The pull-up was the global unused-pin reservation, not an
assignment.** Pin 74 (`M MCU_P17` / G2691 = CM4 GPIO14 UART0 TX; sinks M MCU
U8.32, LOGIC U3.74, power MCU U34.6) is not assigned in the shipping design
and has no RTL port. In the step-0 fit report it reads
`RESERVED_INPUT_WITH_WEAK_PULLUP`, Weak Pull Up **On**, User Assignment blank
— the `RESERVE_ALL_UNUSED_PINS "AS INPUT TRI-STATED WITH WEAK PULL-UP"` line
covering it along with every other unassigned pin. That line is load-bearing
everywhere else (the 2026-08-19 trap: the MH and panel UARTs were ground-driven
when it was left unspecified) so it stays; pin 74 is taken out of it by name.

**S41-2. The defect is measurable from the CM4 alone — no scope needed.**
Release the CM4's GPIO14 from the PL011 and read the net:
`pinctrl set 14 ip pn` -> **hi**, and `pinctrl set 14 ip pd` (the CM4's own
~50 k internal pull-down) -> **still hi**. An external pull-up stronger than
50 k, which is the MAX V weak pull-up (~25 k typ). Restore with
`pinctrl set 14 a0 pn`. This is the instrument for the whole finding and it
costs one ssh command.

**S41-3. One qsf assignment, netlist unchanged — but the fitter re-placed the
design, and that is said out loud.** `s41_mhrx_pullup_off.15f3ae07dae1`
(branch `s41-mhrx-pullup-off` = step 0 + three qsf lines) reserves pin 74 as a
tri-stated input with `WEAK_PULL_UP_RESISTOR OFF`. The 150-row "All Package
Pins" table differs from step 0's on **exactly one row** — pin 74, now
`mhrx / input / 3.3-V LVTTL / User Assignment Y / Weak Pull Up Off` — and the
logic element count is identical (156, 28 registers), same RTL, same sim gate.
The global reserve line is unchanged in both fit reports. **The placement is
not identical**: adding a pin constraint re-seeds the fitter, so LABs go
24 -> 26, peak interconnect 7.6 % -> 10.6 %, every control signal moves cell,
and Fmax moves 66.1 -> 70.05 MHz. "Only pin 74 changed" is true of the pin
table and of the function, not of the bitstream bytes. Built twice from clean
`git archive` trees, pof byte-identical; the step-0 baseline was rebuilt in the
same session and reproduced its recorded pof md5 exactly, so the diff is
between two builds of this toolchain.

**S41-4. THE NET FOLLOWS THE BITSTREAM, PROVED BY A CONTROL ARM, AND U8 IS NOT
A SECOND PULL-UP SOURCE.** Four plays on the part, every one FLASH-OK on
attempt 1, IDCODE `0x020a30dd` before and after each:

| play | on the part | `14 ip pn` | `14 ip pd` |
|---|---|---|---|
| 0 (dry run) | step 0 | hi | hi |
| 1 | **s41 fix** | **lo** | **lo** |
| 2 (control, rollback) | step 0 | hi | hi |
| 3 (re-flash) | **s41 fix** | **lo** | **lo** |

`pinctrl set 14 ip pu` reads **hi** in the fix arm, so the net is not shorted
low and the instrument is live. The control arm reproduces the defect and
removes the alternative explanations at once: **M MCU U8 pin 32 contributes no
pull-up** (nothing about U8 changed between the arms and the net went low), and
neither does the board — the DSP-side CPLD was the whole of it. The net still
reads low after several rail cycles, so the change is in the configuration
flash and survives power.

**S41-5. Step 0's own behaviour is intact.** S38-3's fingerprint, taken with
the `blk_*` pair from `/home/app/s38pre` at BOOT_STAGE 7 on the same recipe
either side of the flash: chip 1 **9540** overruns per 30 s before, **9505**
after (S38 recorded 9602 and 9957 x3), 90,015/90,016 blocks per 30 s in both;
chip 2 **BLK_OK, zero overruns** before and after, `SPORT0_ERR_A 0` throughout.
The converter/option-slot clock pair is still driven and the one-block-in-nine
cost is unchanged to three figures.

**S41-6. THE DISPATCH'S GATE-4 PROXY CANNOT TEST THE ACK, AND THE FIRMWARE
SAYS SO IN ONE LINE.** The gate asked for `sudo poweroff` with the rocker ON,
expecting the power MCU's shutdown sequence to complete in seconds. Read
`ST_ON` in mx26 `src/fw/pwr-mcu/main.c` (ba9b2bc, + 0215bc4 which only adds the
reset log): its **only** exits are `!rocker_on` and `!v12_ok`. **MHRX going low
in ST_ON does nothing.** The Pi-off acknowledge lives inside `ST_SHUTDOWN`,
and `ST_SHUTDOWN` is entered by the rocker or by 12 V failing — never by the Pi
halting. So a `poweroff` with the rocker ON cannot start the sequence, and the
path this fix serves is the other one: **rocker OFF while the Pi is still
running** -> `enter_shutdown(TRIG_SWITCH)` with `pi_alive_at_entry = 1` ->
PI_SD -> the app saves and halts -> MHRX must fall -> ack at
`CFG_MHRX_ACK_LOW_MS` = 100 ms, else `CFG_SHUTDOWN_TIMEOUT_MS` = 60 s. That
test needs a hand on the rocker and was out of this session's scope by the
dispatch's own terms. The MCU also has its own pull-down on PA0 (`board.h`), so
with the CPLD's pull-up gone the sense line is actively held low, not floating.

**What the `poweroff` run actually measured, since it was run before the source
was read:** halt to the next kernel start was **154 s** (network down at +8 s,
kernel start at +162 s, ssh at +180 s). A plain `reboot` — the identical OS
shutdown path with no rail cycle — is **10 s** from network-down to kernel
start, so ~144 s of it was off-Pi. With the rocker ON and 12 V present no
firmware path can cycle the rails, so something reset the MCU; `0215bc4`'s
reset-cause log in no-init SRAM is readable over SWD and would say which. Two
further uncommanded cycles followed within four minutes and then the unit ran
308 s clean and was handed back that way. **Not attributed to this bitstream**
— the CPLD has no rail control — but not explained either, and it is the same
shape as the reset-pulsed-rails loop ba9b2bc was written to kill.

**Bench default rollback was stale and is now the bitstream the bench lives
on.** `logic_flash.sh` defaulted to `dsp4_logic.a1f6672af6c3.svf`; S38 put step
0 on the part on 2026-09-12. A default rollback that is not what is on the part
is a second unannounced flash, not a rollback. It now defaults to
`s37_shipping_step0.c62c024714f2.svf` and the header says the line moves with
the bench.

## THE INSTRUMENT WAS WRONG, THE CONVERTERS ARE RUNNING, AND THE CAPTURE IS ONE BIT LATE (2026-09-12, session 39)

Three S38 findings were readings of a host symbol map that does not belong to
the image on the part, and all three invert when the map is right. Corrected:
the per-strip node state was never zero, the block-cost instrument was never
missing, and the input lanes were never dead — **every one of the twelve chip-1
converter lanes is live and carrying a per-lane-distinct noise floor**, which
settles the converter-clock question by construction. Audio still does not
reach the XLR and there is now a named systemic reason: **the SPORT RX capture
is one bit late on every lane.** Full write-up
`MW/D24/DSP/dsp4-s39-20260912.md`.

### S39-1 — the bench symbol map is not the running image's, and it cost three findings

**Severity: CRITICAL (instrument). Status: CLOSED, with a guard.**

Every "it reads zero" result on this bench came through `peek(sym[name])`. None
of the three conclusions drawn from it follows from the source: the node state
block's `.var` initialisers are `1.0` / `1.0` / `0x10000000`, not zero;
`main.asm` writes `_proc_cyc`/`_proc_cyc_max`/`_proc_passes` on both chips with
**no `#if` around them**, so "an uninstrumented build" is not a state this tree
can produce; and `_rx_slot_C1_IN_nn` is dead by construction (S39-6).

**The discriminator asks the same variable by two routes that share nothing.**
The SPI parameter read resolves its address through `_spi_dispatch_c1` INSIDE
the image, and `spi_handler.asm`'s `.spi_read` reads the very DM word the write
path targets — there is no shadow store in that file. On `blk_*`:

    _gain_coeff_C1_GAIN_01   peek 0x00000000  |  spi 0x0000 read 0x3F800000
    _fdr_level_C1_FDR_01     peek 0x00000000  |  spi 0x0050 read 0x3F800000

`0x3F800000` is `1.0f` — the built initialiser exactly. The kernel is right and
the map is wrong.

**That the MAP is the variable is proved by construction, not argued.** A pair
was built from the tracked tree and its map generated from its own
`chip1.map.xml`. Booted, the same three registers peeked through both maps:

| symbol | new image + **its own** map | new image + the **bench** map |
|---|---|---|
| `_diag_ticks` | 17,355 | 0 |
| `_spi_rx_count` | 179 | 0 |
| `_frame_count` | 63,132 | 0 |

Same part, same instant, same peek window.

**The part says so itself: `blk_*` reads `DIAG_BUILD_CFG2 = 0x00000000` on both
chips.** That register exists in every current build and the shipping value is
`0xC2010244`; the fresh pair reads exactly that. An image answering 0 there
predates the register. The bench map is 216,077 bytes — the size of the map
regenerated from the `build/chip1.map.xml` left in the tree on Sep 11 (S37 arm
A, `6396187c`), a different build from the `ac65ad38` that was booted.

**Consequence: no peek-addressed reading taken on `blk_*` is anchored, and that
is a class of results, not three.** SPI parameter reads, DIAG registers and
meters are unaffected — they resolve inside the image. The guard is
`tools/pi/dsp4_s39_symcheck.py`: three registers, run before trusting any peek.

### S39-2 — what writes per-strip node state on a D24: an SPI parameter write, and nothing else exists

**Severity: HIGH. Status: CLOSED — the gap is a missing WRITER, not a missing mechanism.**

`chip1/dsp_params.asm` is a generated table from SPI address to the DM address
of the node's own variable (`0x0000` is literally `_gain_coeff_C1_GAIN_01`).
`spi_handler.asm` writes the word directly for stride-0 entries and hands the
rest to `_ramp_set_target`, which sets level AND target and clears frames. The
read path indexes the same table to the same word. The change-detect is
`_ctl_epoch[strip]`, bumped at `.spi_write_answer`. **There is no separate
apply, commit or scene step anywhere in the kernel, and none is needed.**

The gap is entirely host-side: `dsp4_config.py --product d24` writes the
product SCOPE only (51 words chip 1, 5 chip 2), and `matrix-app` has no DSP
address for any strip cell (0 `DspAdd` of 4985). **So a D24 boots with every
strip at its build-time initialiser and nothing ever moves it.** That is the
single-SOT item. `tools/pi/dsp4_apply_strip.py <strip> [aux]` is the missing
writer — 13/13 cells written and read back correct, with no `peek` in it.

### S39-3 — GATE 4: the mechanism is "more work", not "the boundary moved"

**Severity: HIGH. Status: CLOSED, and it did not need the bitstream pair.**

Read through a matching map, on the fresh pair:

| | chip 1 | chip 2 |
|---|---|---|
| `_proc_cyc` / `_proc_cyc_max` | 376,593 / 378,202 | 337,969 / 338,703 |
| per-block budget at 983.04 MHz | 327,680 | 327,680 |
| **cost as a share of budget** | **114.9 %** | **103.1 %** |
| `_proc_passes` in 30.0 s | 2612.5/s | 2910.2/s |
| **shortfall against 3000/s** | **12.92 %** | **2.99 %** |
| predicted by 1 − 1/cost | 12.97 % | 3.01 % |

Repeat 20 s later: chip 1 114.3 % predicts 12.51 %, measured 12.49 %; chip 2
104.0 % predicts 3.85 %, measured 3.59 %. The denominator is anchored — the
diag tick rate measures 1000.03 / 1000.00 Hz, ratio 1.00003.

**The discriminator: `DIAG_FRAME_COUNT` advances at 3000.0/s on chip 1 (45,010
in 15.00 s) while `_proc_passes` advances at 2612/s on the same chip in the
same window.** The boundary is on time to five figures; the work does not
finish inside it. Two counters on one boot separate the hypotheses, because
they measure the boundary and the work independently — the old-bitstream arm
could only have said how many cycles the converter clock ADDS.

**The bitstream arm was not available and correctly so:** AN_EN is HIGH,
`logic_flash.sh` refuses at exit 5 before any write with AN_EN high, and GPIO26
must never be written by this session. Recorded as not-run, not skipped.

**The figure that outlives the mechanism: both chips are OVER the per-block
budget on the shipping configuration** — chip 1 by 15 %, chip 2 by 3–4 %. S38-4
said they sit close to it. They are past it.

### S39-4 — the SPORT RX capture is ONE BIT LATE on every input lane

**Severity: CRITICAL. Status: OPEN — this is the defect standing between this
unit and first audio.**

Read where the kernel reads (`_rx_active_buf + _c1_rx_off[e] + i*_c1_rx_stride[e]`),
across all twelve chip-1 lanes, 288 words:

| quarter of the range | words |
|---|---|
| `0x00000000`–`0x3FFFFFFF` (small +) | 140 |
| `0x40000000`–`0x7FFFFFFF` | 148 |
| `0x80000000`–`0xBFFFFFFF` | **0** |
| `0xC0000000`–`0xFFFFFFFF` (small −) | **0** |

**Bit 31 is never set on any word of any lane; the low 7 bits never are
either.** Real signed audio cannot do that; a capture one bit late does exactly
this — the sign bit lands in bit 30, a zero is shifted in above it, so
`0xFFF9F000` arrives as `0x7FFCF800`. Scored both ways: as received, peak
−0.00 dBFS / rms ≈ −3 dBFS on every lane in every arm; shifted left one bit,
peak ≈ −60 dBFS and rms −65 to −85 dBFS **varying per lane** (0.000054 to
0.000593), which a dead, stuck or constant lane cannot do.

**So the converters ARE clocked and converting** — twelve independent lanes,
each with its own noise floor, in their own TDM slots, on a part whose block
loop is locked to the same SPORT at exactly 3000 blocks/s. **This closes S34-1
by construction and the standing `PROBE PLEASE` for J18 P37/P38 is no longer
needed to establish it.** **S38-6 is refuted**: the lanes are not static zero,
the twelve variables it scanned are.

It is one bit, on every lane, so it is a SPORT frame-sync-to-data delay item,
not a per-channel fault. Until it is fixed no level, gain law or meter reading
on this unit means anything: it is what pins every meter at −0.00 dBFS peak /
−3 dBFS rms even on a MUTED strip, saturates the aux bus at Q4.28 8.0
(`Aux001Mtr001` +18.06 dBFS), and drives the AUX 1 DAC lane above full scale.

### S39-5 — the DSP drives AUX 1's DAC lane; MIC 1 does not hear it. The break is analog-side

**Severity: HIGH. Status: OPEN, and now localised.**

Chip-2 TX DMA lane 0 follows `Aux001Mute001` exactly and ignores
`Main001Mute001`, so it is AUX 1's output:

| lane | both open | MAIN muted | **AUX 1 muted** |
|---|---|---|---|
| 0 | 1.538322 | 1.531704 | **0.000000** |
| 1–7 | 0.000000 | 0.000000 | 0.000000 |

1.538 in Q4.28 is +3.75 dBFS — the S39-4 artefact arriving at the DAC. Strip 1
is live at every point in between (chip-1 taps trim/EQ/pre-fader;
`_buf_C2_MIX_AUX_01`, `_buf_C2_AUX_AFB_01`, `_buf_C2_MIX_MAIN_L`,
`_buf_C2_MAIN_FDR`, all 20/20 non-zero).

**MIC 1's lane does not respond**, five arms on one boot, corrected reading:

| arm | what drives AUX 1 | mic 1 lane rms |
|---|---|---|
| A | aux master MUTED, send off | 0.000339 |
| B | aux open, ch1 send OFF | 0.000351 |
| C | aux open, ch1 send −40 dB | 0.000397 |
| D | aux open, ch1 send **0 dB** | 0.000380 |
| E | aux master MUTED again | 0.000373 |

Under 1 dB of spread and no ordering — D is not the loudest, A is not the
quietest. **The DSP side is proven good from the strip to the TX DMA buffer;
the break in the patched loop is on the converter/analog side of it.** Where
exactly — DAC, AUX 1 output stage and its isolation link, XLR, mic front end,
ADC — is still open.

**Separate finding from the same table: only ONE of eight chip-2 TX lanes is
ever non-zero.** MAIN's lanes are silent with MAIN unmuted, `Main001Level001`
at unity and strip 1 routed to it, while `_buf_C2_MAIN_FDR` immediately
upstream is live. Not yet root-caused.

### S39-6 — `_buf_C1_IN_01` and `_rx_slot_C1_IN_nn` are not on the audio path under block kernels

**Severity: HIGH (it invalidated a chain walk). Status: CLOSED.**

`C1_IN_01.asm` says so in its own comment: under block kernels the kernel reads
the DMA buffer directly and "the slot var is unreferenced — kept as a scalar
purely so `block_io.asm`'s tables still resolve". `_C1_IN_01_process` reads the
SPORT DMA buffer straight into `BLK_CHAIN_A`; every node after it works in
BLOCK-word pool slots and the per-node scalars carry only the block's last
sample. On the part, with a matching map: `_rx_slot_C1_IN_01` and
`_buf_C1_IN_01` both `0x00000000`, while `_buf_C1_GAIN_01` reads `0x0FFF0540`
(+0.99976 Q4.28) and `_gain_q_C1_GAIN_01` reads `0x10000000` (unity).

**S38-5 injected into `_buf_C1_IN_01` and read `_buf_C1_GAIN_01`.** The first
is not an input to anything; "the step dies at `_buf_C1_GAIN_01`" is what
writing to a variable nothing reads looks like.

**Instrument limit that applies to every pool reading:** a peek is a
two-transaction handshake serviced once per block, so sixteen consecutive pool
addresses come from sixteen DIFFERENT blocks. A pool read is a mosaic —
"is this point ever non-zero over N blocks" is answerable, a waveform is not.

### S39-7 — the channel fader has authority; the channel gain arm did not resolve

**Severity: MEDIUM. Status: fader CLOSED, gain OPEN pending a stimulus.**

`Chan001Level001` 1.0 → 0.1 against −20 dB expected: `_buf_C2_MIX_MAIN_L`
−18.03 dB, `_buf_C2_MIX_AUX_01` −20.55 dB, `_buf_C2_MAIN_FDR` −21.92 dB, and
the chip-1 **pre**-fader tap +0.78 dB, correctly unmoved. At `Level = 0.0` all
three go to exact silence. The pre-fader tap holding while three post-fader
points move together is what makes this a measurement rather than a
coincidence.

`Chan001Gain001` 1.0 → 0.1 gave −5.63 / −4.89 / −7.23 dB against −20 expected,
and the pre-fader tap — DOWNSTREAM of GAIN — did not move at all. **Recorded
as unresolved, not as a defect**: the stimulus is the S39-4 artefact, whose
amplitude distribution is not linear in the true input, and the estimator's own
scatter is ±2.5 dB (the same point read 0.1167 / 0.1347 / 0.1543 under
identical conditions in one run). Needs a controlled stimulus, which needs
S39-4 fixed.

### S39-8 — the aux-master arm probed upstream of the aux fader and shows nothing

**Severity: LOW (harness). Status: CLOSED — retake named.**

`_buf_C2_MIX_AUX_01` is upstream of `C2_AUX_FDR_01`, so its non-response to
`Aux001Level001` is correct behaviour and not evidence either way. Recorded so
it is not later read as "the aux master has no authority". A retake needs a
point downstream of the aux fader.

### S39-9 — there is no in-kernel tone source, and `build/` is not the shipping image

**Severity: LOW. Status: recorded.**

`C1_NOISE`'s header says "Pink/white noise + tone generator"; the body is an
LFSR and a pinking filter with **no oscillator**, and its output goes nowhere —
`_buf_C1_NOISE` has no consumer in `process_chain.asm` and its route-bitmask
dispatch entry (`0x128B`) is `0`, i.e. unmapped. `scope.asm` offers impulse and
step only, and DC cannot cross an AC-coupled output. A host-toggled square
(±`_scope_amp` in step mode) is possible but limited to a few hundred Hz and
host-jittered. None was needed: the loop question was answered by controls with
a negative arm, which is stronger than a tone.

Separately: **`MW/D32/DSP/SHARC/build/` did not hold a shipping-default
image.** It held `6396187c` / `df5cc181`, whose map contains `_blk_pool1` — a
symbol that exists only with the paired graph on, while `shipping.config` has
`DSP4_SIMD_DYN=0`. Today's plain `./build.sh` gives `30453a38` / `363d94ab`
and no `_blk_pool1`. That is a build ARM left in a scratch directory, not build
nondeterminism, and `build/` must not be read as "the shipping image".

## THE STEP-0 BITSTREAM IS ON THE PART, AND IT COSTS CHIP 1 ITS REAL-TIME MARGIN (2026-09-12, session 38)

The converter-clock flash landed on the first attempt and the unit is on
`s37_shipping_step0.c62c024714f2`. The bar it was supposed to be invisible to
is not met: **chip 1 drops one audio block in nine on the new bitstream and
none on the old**, established with a rollback control rather than asserted
from a single before/after. Chip 2 shows the mirror image — it is the OLD
bitstream it is unstable on. Audio still does not pass, for reasons that have
nothing to do with the flash. Full write-up `MW/D24/DSP/dsp4-s38-20260912.md`.

### S38-1 — the AN_EN interlock is met by READING the pin, with matrix-app running

**Severity: HIGH (it was the blocking gate). Status: CLOSED.**

S35-1 blocked on `AN_EN` (GPIO26) being HIGH whenever `matrix-app` runs, because
the old app asserted it unconditionally in `Boot.Init()`. The gated app
(`a509053ca0a999de1ee7aabd9a234089`) does not. The pin was read at every gate of
this session and was **`lo` every time** — with the app RUNNING at the dry run,
and again with it stopped at each flash:

    26: op -- pd | lo // GPIO26 = output

and the app says so itself in `/home/app/logs/log`:

    Boot.Init() - AN_EN gated (PW 2026-09-10): analogAutoEnable=false,
    chain latch=CM4 GPIO 27 — bring-up runs after S_RUN

So **no waiver was used, `--stop-app` was not needed for the interlock, and
GPIO26 was never written by this session.** The interlock was satisfied on a
reading, which is the whole point of putting it in the tool.

One correction to the dispatch's wording: the log line it told us to confirm is
`AN_EN gated … chain latch=CM4 GPIO 27`, which is present; the *other* line the
app emits is `AnalogBringUp: AN_EN STAYS LOW — digital clocks not proven
stable`, and it names the three gates it cannot yet see (`CPLD running, C1/L0
present (Unknown); DSPs booted and streaming (Unknown); Converters out of RST_C
(Unknown)`). The app states explicitly that **it does not boot the DSPs** — "SPI2
slave boot runs outside this process (dsp4_boot.py, dsp repo) — no boot-state
query" — so those gates stay `Unknown` no matter what the bench does.

### S38-2 — the flash: three plays, three FLASH-OK on attempt 1

**Severity: n/a (the gate). Status: CLOSED.**

`s37_shipping_step0.c62c024714f2` is on the part. IDCODE `0x020a30dd` before and
after every play; the rollback `dsp4_logic.a1f6672af6c3.svf`
(`dd1e09185804cb2e451d5089cdd56be3`) was verified present on the bench before
the first byte was written, and was never needed.

| # | what | result |
|---|---|---|
| 1 | `./logic_flash.sh --dry-run s37_shipping_step0…` | exit 0, nothing written |
| 2 | `./logic_flash.sh s37_shipping_step0…` | **FLASH-OK attempt 1** |
| 3 | `./logic_flash.sh --rollback s37… dsp4_logic.a1f6672af6c3.svf` | FLASH-OK attempt 1 (the control) |
| 4 | `./logic_flash.sh s37_shipping_step0…` | **FLASH-OK attempt 1** (restored) |

The artifact carries no design ID by construction (S37-4), so its identity on the
part is the md5 `d47b74c6c881b82a110491266a6bd31d` (svf) /
`79284dad6e9c27995f91806056c9fba5` (pof) plus `/home/app/logic-flash.log`, and
nothing else. S24's "a MAX V flash that fails twice and then works" did not
recur: four plays, four clean.

### S38-3 — the step-0 bitstream costs chip 1 its real-time margin: one block in nine

**Severity: HIGH (it is the shipping design plus two "zero-cost" fixes).
Status: OPEN — cause attributed, MECHANISM NOT FOUND.**

Gate 4's bar is `blk_*` (`ac65ad38` / `e5dce9e4`), 30 s, zero overruns, both
chips. **Chip 1 does not meet it on the new bitstream and does meet it on the
old one.** This is an A/B/A with the DSP images md5-verified identical across
every arm (`ac65ad386fb910b7bed7736872abae43` / `e5dce9e43c2c72290c115726ca31976c`)
and the same boot+config recipe throughout:

| bitstream | boots | chip 1 `BLK_OVERRUN` delta | verdict |
|---|---|---|---|
| `a1f6672af6c3` (old, pre-flash + control) | 6 | 0, 0, 0, 0, 0, 0 | **6/6 clean** |
| `s37_shipping_step0` | 5 | ~332 /s every window | **5/5 fail** |

The rate is deterministic to three figures: **9957 / 9957 / 9957 in 30 s** on
three consecutive windows of one boot, then 6639 and 6673 in 20 s on two fresh
boots, then 6662 in 20 s after the re-flash and 9602 in 30 s on the final cold start — 331.9…333.7 blocks/s against a
3000/s block rate, i.e. **11.06 % of blocks, one in nine.** A loop that dropped
one block in nine is a loop about 11 % over its per-block budget.

**Four candidate causes are ruled out by measurement, not by argument:**

* **Not the core clock.** The diag timer runs at 999.96 Hz on BOTH chips
  (ratio to nominal 0.99996, identical to five figures). Same cycles available.
* **Not the block rate.** `FRAME_COUNT` is 3000/s on both chips in both arms —
  90,016 ± 3 blocks per 30 s window, every time.
* **Not the transport.** `SPORT0_ERR_A` is `0x00000000` and `DMA0_STAT` is
  `0x00006200` on both chips in both arms.
* **Not input data.** All twelve `_rx_slot_C1_IN_nn` lanes read a **static
  zero** on BOTH bitstreams (`inscan.py`, 6 reads each). The obvious story —
  "the converters now have a clock, so the graph is doing real work on real
  audio instead of taking the dynamics' cheap branch" — is **refuted at the
  DSP input**. See S38-6.

What the flash changed is two commits' worth of RTL: pins 142/141 go from
INPUTS (`ic_strap[1]` / `il_strap[0]`, which fed nothing but the `_unused`
reduction) to OUTPUTS driving `bck8` / `fs8`; and `snake_out` / `dac_main` go
from constantly driven to high-Z with weak pull-ups on a D24. None of that is a
DSP input, which is precisely why the result is surprising.

**The discriminator that would settle it was not available on this image.**
"More work per block" and "the same work against a block boundary that moved"
are separated by the per-block cycle count, and `_proc_cyc`, `_proc_cyc_max`
and `_proc_passes` all read **0 on both chips** — including on healthy chip 2,
which is how we know that is an uninstrumented build and not a hung loop. It
needs a `DSP4_TCOUNT` build of the same pair. **That is S39's first job**, and
it is a desk build plus one boot.

### S38-4 — chip 2 is unstable on the OLD bitstream, so there was never a clean baseline

**Severity: MEDIUM. Status: OPEN.**

The control arm was run five times and chip 2 was measured on each. It is the
mirror image of chip 1:

| bitstream | chip 2 `BLK_OVERRUN` delta per 20 s |
|---|---|
| `a1f6672af6c3` (old) | 0, **1492**, 0, **1493**, **1493** — 3 of 5 fail |
| `s37_shipping_step0` | 0 on every window of every boot — clean |

1492/1493 in 20 s is ~74.6 blocks/s, 2.5 % — a different and equally
reproducible rate from chip 1's 11 %. So **the bitstream this unit has been
running for three weeks does not reliably meet the bar either**, and any earlier
"both chips, zero overruns" reading was a 2-in-5 draw on chip 2. Both chips sit
close enough to the per-block budget that small changes tip them over; the
margin, not either bitstream, is the real finding.

### S38-5 — channel 1 cannot pass audio: the shipping config has no route, and the strip's node state is unwritten

**Severity: HIGH (it blocks the first audio pass). Status: OPEN.**

Gate 5 asked which output the shipping configuration routes channel 1 to. The
answer is **none**: `dsp4_config.py --product d24` writes only the product SCOPE
— `CFG_PRODUCT_ID`, `CFG_CHAN_MASK`, `CFG_AUX_MASK`, `CFG_OUT_MUX`, the patch
list and `CFG_COMMIT` (51 words to chip 1, 5 to chip 2). Per-strip routing is not
in it.

The route was therefore set explicitly, by cell name out of `landed-d24.json`
(`tools/pi/s38_ch1_main.py`, staged on the bench): every strip taken off the main
bus and muted two independent ways first, then

| cell | node | value |
|---|---|---|
| `Chan001Level001` | `C1_FDR_01` | `1.0f` (unity) |
| `Chan001Pan001` | `C1_FDR_01` | centre |
| `Chan001Mute001` | `C1_FDR_01` | 0 |
| `Chan001MainOn001` | `C1_RTG_01` | 1 |
| `Main001Level001` | `C2_MAIN_FDR` | `1.0f` |
| `Main001Mute001` | `C2_MAIN_FDR` | 0 |

**It still will not pass audio, and the chain walk says exactly where it stops.**
Injecting a 0.25 step at `_rx_slot_C1_IN_01` with `dsp4_scope.py`:

    _buf_C1_IN_01     0x04000000  +0.250000000   <- the injection is there
    _buf_C1_GAIN_01   0x00000000  +0.000000000   <- it dies HERE
    _buf_C1_FDR_01    0x00000000  +0.000000000
    _buf_C1_RTG_01    junk (an unwritten buffer, see below)

`C1_GAIN_01`'s **entire node state block is zero** — `_gain_coeff`,
`_gain_target`, `_gain_step`, `_gain_frames`, `_gain_q`, `_mute`, `_polarity`,
`_tap_post_trim`, all `0x00000000`. That is not "a gain of zero", it is a state
block nothing has ever written: `_mute` would be 1 if it had been muted. Writing
`Chan001Gain001` with ramp id 1 (the `gainfix.py` path), 0 and 2, polling ten
seconds each, moves neither coefficient nor target — and `gainfix.py` itself
reports `strip 1 still 0x00000000`.

**A method note, because it nearly produced a wrong finding.** The first
read-back said parameter writes were not landing on EITHER chip, which would
have been a serious claim. It was wrong: `dsp4_conform.py --phase presence` over
addresses 0–90 on chip 1 returns **`ECHO: 81`, part healthy at exit: True** — the
parameter STORE takes every write and reads it back. The error was verifying a
parameter write against the NODE's working symbol rather than against the store.
The store is written; the node never applies it. Those are different defects and
only the second one is real.

So the open question for the first audio pass is **what writes per-strip node
state on a D24**. It is not `dsp4_config.py`, and it is not `matrix-app` as
observed here — `MW/D24/MX/_matrix.csv` carries **no DSP address backfill at all
(0 of 4985 rows have `DspAdd`)**, so the app has no DSP address for
`Chan001Gain001`; on the bench the cell is reachable only through
`landed-d24.json`. Whether that is by design for D24 or a gap is a defs/contract
question, not a bench one.

### S38-6 — driving the converter clock pair did not, by itself, wake the converters

**Severity: MEDIUM. Status: OPEN — needs PW's probe.**

The point of step 0 is that U3 pins 142/141 now drive `bck8` (12.288 MHz) and
`fs8` (48 kHz) to the ADC/DAC FPC and the three option slots, where before they
were sampled as dead straps. The flash landed — and **all twelve chip-1 input
lanes still read a static zero**, identically on both bitstreams. A lane fed by a
clocked converter varies sample to sample on its own noise floor even with
nothing plugged in; these do not move at all.

That does not mean the clock is absent — it means a clock alone is not
sufficient, and the CM4 cannot see the difference (S35-5: no CM4 GPIO reaches
C1/L0/TEST1–4). **PROBE PLEASE: J18 P37 = 12.288 MHz, P38 = 48 kHz, or U3 pins
142/141 at the source.** Until that is on a scope, "the converters have a clock"
is an inference from the RTL diff and the fitter report, not a measurement, and
S34-1 stays open.

### S38-8 — `check-contract-drift.sh` fails on a PRE-EXISTING graph/dsp.csv disagreement

**Severity: MEDIUM (contract). Status: OPEN, NOT TOUCHED — noted so the next
session is not surprised by it.**

Run as an end-of-session sanity check, `./check-contract-drift.sh` reports:

    ERROR: d24/dsp.csv cell set disagrees with the graph — 237 the graph
    proposes and the landed file lacks, 0 the landed file has and the graph
    does not propose.
    ERROR: d24/dsp-unmapped.csv cell set disagrees with the graph — 0 ... 237 ...

The 237 are `Chan*CompMtr001`, `Chan*MatrixOn00n` and `Chan*MatrixSend00n`. It
also rewrites `MW/D32/MX/_matrix.csv` without its six `Ramp*` columns
(`RampProfile`, `RampMode`, `RampUpMs`, `RampDownMs`, `RampCurve`, `RampScope`),
which the committed file has — 7000 lines changed, all of them for that reason.

**None of this is S38's doing and none of it was committed**: the session
touched no def, no matrix and no `defs.lock`, and the working tree was restored
(`git checkout -- .`) so the repo is clean. It is recorded only because the
script's failure is pre-existing and a session that runs it will otherwise think
it broke something. The script names its own fix and this spoke is a CONSUMER:
propose a new `dsp.csv` to the hub gate; never hand-edit the landed file.

### S38-7 — `dsp4_diag.py --rate` has no MAGIC guard and reported a negative clock

**Severity: MEDIUM (instrument). Status: OPEN — worked around, not fixed.**

On chip 1 in its over-budget state, `dsp4_diag.py --chip 1 --rate 2.0` printed:

    diag ticks      -54238  ->  -26274.1 Hz (nominal 1000 Hz at CCLK = 400 MHz)
    implied CCLK    -10509.64 MHz

A negative core clock is not a reading, it is a slipped link — `--rate` takes
`TICKS` and `FRAME_COUNT` unguarded, and on a chip whose main loop is starved the
answer can come from a different request. It does not refuse; it prints. The same
counters read through a MAGIC-bracketed snapshot (`cclk.py`, this session) give
999.96 Hz on the same chip seconds later. **Any CCLK figure taken with `--rate`
on a loaded chip is suspect**; the guarded reader should be folded into the tool.

## THE BENCH MADE HONEST, AND THE GENERATOR DRIFT IS SEMANTIC (2026-09-11, session 37)

Desk only; the unit was not touched and no ssh session was opened. `loadlogic.sh`
now names only artifacts that rebuild from a commit, both proved branches are
merged to `main`, and the step-0 bitstream is built, reproduced and staged. The
one thing that did NOT land is the one the dispatch told us to stop on: the node
ASM drift against its generator is **semantic**, so nothing was regenerated. Full
working: `MW/D24/DSP/dsp4-s37-20260911.md`.

### S37-1 — the two dishonest artifacts are retired, and the svf is not byte-reproducible

**Severity: MEDIUM (bench integrity). Status: CLOSED for the artifacts, and a
new rule recorded for the file format.**

S36-3's two defects are made good. `driveall` moves from `e13b5dec84e0` (matches
no committed state of the tree, at any point in its history) to
`907492a607bd`; `pisel` moves from `bd9c100db7c2` (predates the design-ID stamp,
so it cannot identify itself on the part) to `2c1355bbc69b`. Each replacement was
**rebuilt from its commit** with `git archive` into a fresh scratch tree — not
read off a manifest — and each reproduced its committed label and its committed
**pof byte for byte**: `a096c585` + `DRIVE_ALL=1` -> `907492a607bd`, 401 LEs;
`3152e2b1` + `PI_SELFTEST=1` -> `2c1355bbc69b`, 303 LEs.

**The svf did not reproduce, and it is the svf that gets flashed.** The
difference is one line, and it is an SVF comment: `quartus_cpf` stamps the wall
clock into `!Device #1: ... <date>`. With comment lines removed the two files
hash identically, so the bytes openocd plays ARE reproducible and the file the
bench md5s is not. **Byte-identity is asserted on the POF from here on**, and
`loadlogic.sh`'s header now says so. An svf md5 remains the right check for a
*copy* — which is what `logic_flash.sh` uses it for — but it is not a rebuild
check.

Two more artifacts were rebuilt to underwrite the method rather than assume it:
**`dsp4_logic.a1f6672af6c3` — the bitstream on the part — rebuilds from
`a4ee3d1f` with a byte-identical pof** (157/71, independently confirming
S35-3 today), and S35's step-0 candidate `138dba7274d6` likewise (157/68). And
**two independent clean builds of the same ref produce identical pofs**, so a
rebuild whose bytes differ from a committed artifact's is a real source
difference and not fitter noise — the property S36-3's census depends on.

Nothing was deleted. The retired pair is in
`shared/dsp4-logic/bitstream/retired/` with a README carrying both md5s and both
design IDs. **Deliberately not `attic/`**, which the dispatch asked for: CLAUDE.md
defines `attic/` as the ADAU1466/SigmaStudio material and says never to extend
it.

### S37-2 — `dsp_codegen.py` drift is 85 comments and 32 dead instructions, and nothing was regenerated

**Severity: MEDIUM (latent). Status: MEASURED, NOT FIXED — deliberately.**

S34 recorded that `--force` on an unmodified `dsp.csv` rewrites 117 files.
Classified here by stripping comments and comparing the instruction stream:
**85 comment-only, 0 ordering-only, 32 semantic.**

The 85 are `608a1aa3`'s comment rewrite (the part returns `0xFFFFFFFF` on
positive overflow and it is NOT a two's-complement wrap) which was never re-run
over the tree. Prose only.

The 32 are one change repeated: `C1_FILT_01..32` carry

```
i6 = BLK_CHAIN_B_P1;
l6 = 0;
```

inside `_C1_FILT_nn_process_sample`, which the current generator does not emit.
The block entry point keeps its copy in both versions, and **there is no other
code difference in any of the 117 files**.

**It is dead code, and that was checked rather than assumed.** `i6` appears
**exactly twice** in `chip1/shared_kernels.asm` — `i2 = i6;` at lines 606 and
618, inside `.fkb_ss_shkfilt` and `.fkb_b_shkfilt`. Those labels are referenced
only from lines 564 and 601, both **above** `_shk_filt_smp:` at line 624, and
both regions end in `rts;` before it, so there is no fall-through either:
nothing at or after the sample entry point can reach an `i6` read. The block
path hands it to `_bq_fx_cascade_blk` via `i2`; the sample path calls
`_bq_fx_cascade_N`, and neither that nor `_shk_filt_start_xfade` touches `i6`.

**Where it came from.** At `4807d23d~1` the file had no `i6` lines at all.
`4807d23d` introduced BOTH copies into the committed ASM *and* introduced
`pool_in_blk`/`pool_in_smp` into the generator — the flags that gate the
sample-path emission. The tree was generated by an intermediate state of that
commit's generator, the generator was then refined, and it was never re-run
before commit. The drift is therefore OLDER than the last regeneration, which is
why nothing caught it.

**THE STAGED PAIRS WERE BUILT FROM THE TRACKED TEXT, AND REGENERATING MOVES
CHIP 1 BY 256 BYTES.** Both arms built with CCES 3.0.3, under
`shipping.config.s26` and `.s32`. Arm A (tracked) gives chip 1
`6396187cbb3a521a330517622adf6b33` / 425,668 bytes and chip 2
`9222c2ee49c8af1ecdc5516dbedd3db8` (s26) / `df5cc18144a0cb41babcfe70876f576f`
(s32) — **exactly the staged-pair md5s recorded in `dsp4-s32-20260911.md`
§173-175** and repeated across the S26/S27/S28/S29/S33 write-ups. Arm B
(regenerated) gives chip 1 `a7e27099d9dab316342e64683b669011` / 425,412 bytes
and **reproduces neither pair**. `chip2.ldr` is byte-identical between the arms
in both configurations, as it must be — the 32 changed files are all `C1_*` and
chip 2 has no FILT nodes — and chip 1 is 256 bytes smaller in arm B, identically
in both configurations, for 32 nodes x 2 instructions = 64 instructions removed.

So no staged pair and no recorded figure is retrospectively in doubt. It also
turns the caution below into arithmetic: regenerating is a **256-byte change to
chip 1's shipping image**, in the per-sample path of 32 filter nodes.

**Still a stop**, per the dispatch's own rule: 117 files of firmware text would
change in a session with no bench; the tracked text is what every image on
record was built from; and "dead" is a reading of the kernels, not a
measurement — two instructions leaving a per-sample path is a cycle-count
change, and cycle counts are what this programme measures. The fix is a small,
clean, testable job for a session that has the unit.

### S37-3 — both branches merged; every bench instrument changed bytes, so no bar transfers

**Severity: none (planned change). Status: MERGED, `7eabfa5f`.**

`s34-converter-clock` and `s36-xlogic-park` are exactly the diffs S35 and S36
described, they merged without conflict, and clean builds today reproduce their
numbers: `main` 404/71, +converter 404/68, +park 403/71, **merged main 403/68**.
The fixes compose and do not interact — park -1 LE, converter pair -3 pins.

**Both sim gates were proved to BITE by mutation**, reproducing S35-6 and
S36-4.4 including their timestamps: `conv_fs = fs16` fails at t=52143000,
restoring the unconditional `dac_main` assign fails at t=3000.

The three bench instruments were rebuilt from merged main and **all three
changed bytes**, as predicted — the pin change is in every configuration:
`maincap` `33b6eb00a4e8` (403/68), `pisel` `983656926e3e` (302/68), `driveall`
`14df62d98a4d` (400/68), plus the shipping-configuration build
`4f702a181b61` (403/68).

**So the 82-sample latency bar (S29) and every driven capacity row (S28) are no
longer like-for-like** and must be re-taken ONCE on the new artifacts in the
first session with the unit. `loadlogic.sh` says this in its header and keeps
the old base reachable as `maincap-s36` / `pisel-s36` / `driveall-s36` — because
retiring `d903ae1ac4a9` would break S36 §3 step 1, whose purpose is that 82 ± 1
is a reproduction on an already-flashed platform rather than a fresh number.

### S37-4 — the step-0 artifact exists; it is 156 LEs, and it cannot have a design ID

**Severity: none. Status: BUILT, REPRODUCED, STAGED, DRY-RUN CLEAN. S38 is one
command, gated on PW.**

`s37_shipping_step0.c62c024714f2` = `a4ee3d1f` + the converter clock pair + the
X-logic parking, on branch `s37-step0-shipping-base` (`61e38ce3`, **which must
never be merged to main**). **156 LEs, 68 pins**, Fmax 66.1 MHz, sim gate PASS,
**built twice byte-identical on the pof** (`79284dad6e9c27995f91806056c9fba5`).

**The dispatch's two requirements for it are not simultaneously satisfiable, and
its own numbers pick the winner.** "From merged main, shipping configuration"
is 403 LEs; "156 LEs, pins 68" is the shipping DESIGN with both fixes. Build
switches do not change the RTL. 156/68 is what was asked for numerically and it
agrees with S36 §3 — step 0 is deliberately not main's RTL, because flashing
merged main as step 0 would put 247 never-shipping-benched LEs on the part in
the same operation as a two-pin change. **Both were built**; `4f702a181b61` is
staged as step 2 / S39's artifact.

**It cannot carry a readable design ID.** The design-ID/knock block arrived at
`3152e2b1` and costs +124 LEs; adding it would take step 0 to ~280 LEs and put
never-benched RTL into the one flash the staged plan exists to keep clean.
`a4ee3d1f`'s `build.sh` predates `DESIGN_ID` entirely. Step 0 therefore
identifies itself exactly as the bitstream it replaces does, and as its own
rollback does — by md5 and the flash log. `logic_flash.sh` records the md5 on
the desk and re-verifies it on the bench **before the first byte is written**.
The design ID becomes readable at step 2.

`logic_flash.sh --dry-run` was run against the artifact through `--self-test`
stubs (no ssh session opened): every gate passed, nothing written, **exit 0**.
The same artifact with AN_EN reading `hi` and no dry-run: **exit 5, refused
before any write**, naming S35-1 and PW's two options with no default.

## MAIN'S LOGIC RTL AGAINST THE PART — THE 247 LEs NAMED, AND TWO BARS RE-ATTRIBUTED (2026-09-11, session 36)

Desk only; the unit was not touched and no ssh session was opened. The 247
logic elements between the shipping design and `main` resolve into three
commits, and — contrary to the dispatch that ordered the session — they have
been on the part many times, inside non-shipping bitstreams. Two of
`window-candidate.md`'s headline bars were measured on them. Full working:
`MW/D24/DSP/dsp4-s36-20260911.md`.

### S36-1 — the 247 LEs are three commits, and twelve others cost the shipping build nothing

**Severity: none (it is a census). Status: measured, sixteen clean Quartus
builds.**

`157 → 404` logic elements between `a4ee3d1f` (the design on the part) and
`main`, built one commit boundary at a time from `git archive` into fresh
trees. Three commits carry all 247:

| commit | what it adds | LEs | Δ |
|---|---|---:|--:|
| `1f66f975` | **the CM4 stereo return** — capture path promoted out of `` `ifdef DSP4_LOOPBACK `` into every build; B_O3 slots 2/3 | 312 | **+155** |
| `2bb0b491` | TDM8 rework — flat `cap_flat` register file replaces the two shift/hold pairs; six slots prune in the shipping build | 280 | **−32** |
| `3152e2b1` | **the design-ID / knock block** (S5-9) plus the two-frame splice fix; unconditional by design | 404 | **+124** |

The other twelve are flat at 157, 312, 280 or 404: their work sits behind
`DSP4_LOOPBACK`, `DSP4_PI_SELFTEST`, `DSP4_PI_TDM8` or `DSP4_DRIVE_ALL` and is
pruned when the macro is unset.

**The largest item is a product feature, not scaffolding.** `1f66f975`'s +155
is the CM4's stereo RETURN, allocated on PW's decision; removing it removes
the Pi's path back out of the DSP.

**And `2bb0b491` made the shipping build cheaper**, which is worth saying
because it is the opposite of what a commit titled "TDM8 PROVEN: 8 of 8
channels" reads like: in the shipping configuration only slots 2/3 are read,
so the flat register file costs 32 LEs less than the pairs it replaced.

### S36-2 — the 82-sample latency figure and every driven capacity row were NOT measured on the shipping bitstream

**Severity: MEDIUM (attribution, not measurement — no number moves).
Status: proved by rebuild and from the RTL diff; `window-candidate.md`
corrected in this commit.**

A note added to `window-candidate.md` on 2026-09-11 (S35) says "All of it —
both candidates, every bar, the 82-sample latency figure — was measured with
the LOGIC CPLD carrying `dsp4_logic.a1f6672af6c3`". **Two bars were not.**

* the **82-sample latency figure** (S29, n=3) was measured on
  `dsp4_logic_maincap.d903ae1ac4a9`, which carries `3152e2b1`'s RTL — **all
  404 LEs**, confirmed by rebuilding it and reproducing both its name and its
  logic-element count.
* every **driven capacity row** (§2.1, the `100.82 %` D32 worst-use figure,
  the S28/S31 product rows) was measured on
  `dsp4_logic_driveall.e13b5dec84e0`.

The part carried `a1f6672af6c3` before and after those sessions, not during.
**The latency arm cannot run on the shipping bitstream at all** — there
`pcm_din` is tied to `1'b0` and there is no capture path — which is precisely
why `loadlogic.sh` exists.

**No number moves, and the latency figure is still sound.** Proved from the
RTL rather than asserted: `dsp4_clkgen.v` is byte-identical across the whole
range, so every TDM8 framing strobe the DSP sees is the same logic; the
Pi → DSPA transmit path is cycle-for-cycle identical in the shipping
configuration (same `out_period`, same slot/bit decode, same `bck8_launch`,
`pw_flat` slots 0/1 holding exactly what `left_q`/`right_q` held, written and
read on the same `frame_pos` values); and S29's differential cancels the
Pi-side framing exactly, because both arms are the same commit and
`CAP_EXTRA_DELAY` is 0 in both. What the 82 measures is the DSP's
contribution, and that transfers.

**What has to change is the claim, not the figure**: the latency arm requires
a bitstream the shipping part does not carry.

### S36-3 — six committed bitstreams rebuild from no commit, and one is the bench's daily driver

**Severity: HIGH (provenance). Status: proved exhaustively; the fix is named,
not made — it is a bench change.**

`build.sh`'s `SRC_HASH` is a pure function of committed text, so it can be
recomputed for every (commit × macro combination) across all 34 commits that
have ever touched the logic tree and matched against each artifact's
filename. Twenty of twenty-six map exactly. **Six match no committed state of
the tree at any point in its history** — they were built from a dirty working
tree whose source was never committed:

```
dsp4_logic.454d6cfb7352          dsp4_logic_loopback.7231549d2545
dsp4_logic.dfe9b246f0fc          dsp4_logic_loopback.e5e86945c053
dsp4_logic_driveall.e13b5dec84e0 dsp4_logic_loopback.fe91b66ed525
```

**`dsp4_logic_driveall.e13b5dec84e0` is the one that matters.** It is the
artifact `loadlogic.sh` names for `driveall`, and it is the bitstream every
driven capacity row since S28 was taken on — including the `100.82 %` D32
worst-use figure. A rebuildable equivalent exists and is already committed:
`dsp4_logic_driveall.907492a607bd` (`a096c585`, built 36 minutes later,
differing only in the `design_id` word stamped into it).

**And `loadlogic.sh`'s `pisel` cannot identify itself.**
`dsp4_logic_pisel.bd9c100db7c2` carries `1dc67f39`-era RTL, which predates the
design-ID stamp, so its manifest has no `design_id` line and
`dsp4_logic_id.py` gets nothing back from the part — its identity rests on the
flash records, exactly as `a1f6672af6c3`'s does (S35-3). The stamped
equivalent `dsp4_logic_pisel.2c1355bbc69b` is already committed.

Both are the failure `build.sh`'s own comment block was written about, still
live in the tool the bench uses. **Two one-line changes to `loadlogic.sh`**,
deliberately not made here: changing which bitstream the bench flashes is a
bench change and this session was told not to make any.

### S36-4 — the X-logic parking fix: tri-state on D24, do not move the pins

**Severity: MEDIUM (latent — it bites the day a card is fitted to option slot
2). Status: fixed on branch `s36-xlogic-park` (`07818879`), built on both
bases, NOT merged.**

Pins 110 and 111 are not spare pads. Each is a three-board net reaching option
slot 2's A-row as well as the digital board: `U3.110` = `LOGIC_PLL5_1` =
`G2667` → `opt2 SLOT.A13`; `U3.111` = `LOGIC_PLL5_2` = `G2668` →
`opt2 SLOT.A10`. On a D24 both carried a **constant** driver — `snake_out` a
hard `1'b0`, `dac_main` the live B_O3 TDM8 lane — so a card fitted to slot 2
and driving its own A-row meets two CMOS outputs **with no series resistance
between them**. Unlike the converter-clock pair there is no 33R to absorb it.

**The dispatch's two options were "park on pins 81/85/87, the reserved clock
pads" or "tri-state". Both halves of that description are wrong, and the
answer is still tri-state.**

* They are **not clock pads**: test-built with the three nets moved there,
  `quartus_fit` succeeded with 0 errors and the All Package Pins table types
  all three as plain **`Row I/O`**.
* They **are** genuinely dead: the fan-out table gives pin 81 (`L1`, `G2621`),
  85 (`C2`, `G2450`) and 87 (`C0`, `G2447`) all as
  `(nothing - single-pin net)` on the `dsp` board alone. (The trap: the
  converter pair `C1`/`L0` on pins 142/141 are *not* like this — S35-4.)
* **So parking would work and would still be wrong.** ONE bitstream serves
  D24 and D32 because `strap_d32` is a runtime strap, not a build switch, so
  moving `snake_out`/`dac_main` to dead pads would forfeit the D32 role these
  pins exist for.

The fix is `strap_d32 ? o_dspb[n] : 1'bz` on both, plus explicit
`WEAK_PULL_UP_RESISTOR` on all three — the global `RESERVE_ALL_UNUSED_PINS`
does not cover them, because they are assigned pins, and with slot 2 empty all
three now float. High-Z costs the D24 nothing: the Pi capture reads
`o_dspb[3]` internally as `tdm_in`, never through the pin.

| base | LEs | pins | Fmax | TRI 110/111 | weak PU |
|---|---:|---:|---|---|---|
| `a4ee3d1f` | 157 | 71 | 70.21 | no | Off |
| `a4ee3d1f` + fix | **156** | 71 | 65.64 | **yes** | **On** |
| `main` | 404 | 71 | 68.54 | no | Off |
| `main` + fix | **403** | 71 | 71.26 | **yes** | **On** |

**One LE cheaper on both bases** (the constant-zero driver goes away), pin map
identical either side on both, and `strap_d32` appears in the fit report as an
`Output enable` source — the tri-state is real, not optimised away. The sim
gate was extended and **proved to bite by mutation**: restoring
`assign dac_main = o_dspb[3]` fails it at t=3000. The check uses `===`, so a
driven D24 pin is the wrong answer whatever value it carries.

### S36-5 — `tools/pi/logic_flash.sh`: the AN_EN interlock is in the tool, and fails closed

**Severity: none (new instrument). Status: written and proved against stubs;
NOT run against the unit.**

S35-1 found the interlock unmeetable and, worse, unexecutable-as-written: it
lived as prose in dispatches and every session read GPIO26 by hand. A rule
nobody can execute is not a rule, so it goes in the tool.

`logic_flash.sh` refuses unless `pinctrl get 26` reads LOW and **fails
closed** — an unparseable reading, or no `pinctrl` at all, is treated as *not
met*. The level is taken from the field after the `|` and nowhere else, so a
comment or pin alias containing `hi`/`lo` cannot decide an interlock. The
rollback is verified present and md5-recorded **before the first write**, and
the discipline is **FLASH-OK on attempt 1** or the rollback goes straight
back — no retries, because this script exists for putting something *new* on
the part, not for moving between known-good bitstreams. Success is S27-5's
check (chain reached `shutdown`, no `tdo check error`), not the IDCODE.

**PW's three rulings from S35-1 are flags, not workarounds**, and none is a
default: `--stop-app` stops `matrix-app` and **re-reads** GPIO26 rather than
assuming it follows the app down (S35 could not say whether it does);
`--an-en-waived "<reason>"` takes the shape-3 ruling with a **mandatory**
written reason that is recorded in the log; gating on something that tracks
the rails needs hardware and is not in this tool.

Proved on ten cases against stub `pinctrl`/`openocd`/`systemctl`, with
`--self-test` running the same bytes the ssh path runs: AN_EN high → refuse
(5); unreadable → refuse (5); low + `--dry-run` → pass every gate, no write
(0); flash OK (0); flash fails → rollback restores (7); both fail → loud
unknown state (8); waiver honoured and recorded (0); empty waiver rejected
(2); corrupted staged copy → refuse **before any write** (3); rollback absent
→ refuse **before any write** (3).

### S36-6 — the staged bring-up plan, and why step 0 is not main's RTL

**Severity: none (a plan). Status: written; nothing flashes until PW rules on
the AN_EN interlock (S35-1).**

Five steps, each one feature group, one flash, one CPLD-loop proof, one
rollback point.

* **Step 0 (S37) — the converter clock fix on the shipping base.** Flash
  `dsp4_logic.138dba7274d6` (`a4ee3d1f` + the pin change only, 157 → 157 LEs),
  **not** the branch. Proof: the probe at J18 P37 = 12.288 MHz / P38 = 48 kHz,
  then `blk_*` 30 s zero overruns both chips. **The latency bar is not in this
  step and cannot be** — there is no capture path on this base, so the arm
  cannot run at all (S36-2). Rollback `a1f6672af6c3`. The analog attach is
  proved on this before anything else moves.
* **Step 1 (S38) — main's RTL in the configuration already benched.** Flash
  `dsp4_logic_maincap.d903ae1ac4a9`, already committed, already stamped,
  already flashed for S20/S29/S31. It advances nothing new; it re-establishes
  the known-good measurement platform on top of step 0's pin change and tells
  you whether the two interact. Proof: the S29 latency arm, n=3, expect
  **82 ± 1**. Use `dsp4_logic_pisel.2c1355bbc69b` as the reference, not
  `bd9c100db7c2` — same commit as `maincap`, and it can identify itself
  (S36-3).
* **Step 2 (S39) — the shipping configuration of main, for the first time.**
  Build `c0407483` + step 0's pin change and flash it. This is the genuinely
  new operation in the plan: 404 LEs in the *shipping* configuration, which no
  flash has ever carried. What it tests is that the CM4 stereo return and the
  knock block do no harm in the shipping path; both have run on the part
  inside `maincap`, and what is new is B_O3 slots 2/3 being captured while the
  product graph uses the lane. The latency arm cannot run here either (the
  shipping configuration captures slots 2/3, not slot 0), so that evidence is
  step 1's, carried forward on S36-2's argument.
* **Step 3 (S40) — the driven instrument, rebuilt from a source.** Rebuild
  `driveall` from `a096c585` and repoint `loadlogic.sh` at it, then re-take
  the four fully driven product rows no session has managed since S28. Closes
  S36-3 and `window-candidate.md` §5.5's second gap in one boot.
* **Step 4 — the X-logic parking** (S36-4), merged only after 0–3 hold. It
  changes nothing on a D24 with slot 2 empty, which is every unit today, so it
  has no bar of its own until a card exists to fight with.

## THE CONVERTER CLOCK FIX, PROVED AT THE DESK AND STOPPED AT THE BENCH (2026-09-11, session 35)

The fix reviewed, rebuilt reproducibly, staged on the unit and NOT flashed:
the session's gate 0 interlock — `AN_EN` low — was not met and is not
meetable while `matrix-app` runs. Full working:
`MW/D24/DSP/dsp4-s35-20260911.md`.

### S35-1 — AN_EN is asserted by the app at every boot, so the flash interlock can never be met

**Severity: BLOCKING for every future CPLD flash on this unit, and it is a
bench-procedure defect, not a fault. Status: proved from the app's own log
and from `pinctrl`.**

The dispatch's gate 0 reads "`pinctrl get 26` (AN_EN) — if AN_EN is HIGH
stop and report (PW may have raised it by hand)". It is high, and PW did not
raise it. The Aug 18 binary raises it itself, unconditionally, in
`Boot.Init()` — nine lines before the MCU list is even read:

```
14:24:44.680384: Boot.Init() - AN_EN asserted (GPIO 26 high — analog power requested)
```

`pinctrl get 26` reads `op -- pd | hi` — a driven output, high — and the
only session on the box was this one. The app was last started at 14:24:37
BST after a burst of six stop/start cycles between 14:21 and 14:24, PW's
work, forty minutes before the dispatch was written.

Two consequences, and the second is the one that matters:

1. **This session cannot flash.** The interlock is unambiguous and the
   reason behind it — the analog rails may be up, and the analog board may
   be attached — is stronger here, not weaker, because the assertion is
   automatic rather than deliberate.
2. **No session can flash, on this interlock, while `matrix-app` is
   running**, because the app asserts AN_EN within milliseconds of every
   start. S32 and S33 both recorded "AN_EN never asserted" as bench-as-found
   while the app was active; that phrasing meant *the session* never
   asserted it, and it has been reading as *the pin was low*. It was not.

This needs a ruling from PW before S36, and it is a choice between three
things, none of which this session may make: stop `matrix-app` for the flash
and re-read the pin rather than assume it follows the app down — this
session did not stop the app and so cannot say whether GPIO26 falls, and an
untested assumption is exactly what the interlock exists to prevent; gate the
flash on something that tracks the rails rather than on the request line; or
confirm the analog board is detached and flash with the interlock waived in
writing.

Nothing about `AN_EN` was changed, and the 74HC595 chain, CS_M, the rails
and the +48 V were not approached.

### S35-2 — gate 1: the branch is exactly what it claims, and nothing else

**Status: reviewed against a clean build of both refs; the branch is sound.**

`git diff main..s34-converter-clock` is four files: the qsf pin block, the
top-level port list and the two `assign`s, the testbench, and the removal of
S34's own dispatch block from `tasks.md`. No logic outside the port list
moves.

The fitter agrees. Clean builds of `main` and of the branch, same tool, same
machine, put **exactly five pins** between them and leave every other pin —
name, direction, standard, bank — identical:

| pin | net | main | `s34-converter-clock` |
|-----|-----|------|----------------------|
| 142 | `C1` | `ic_strap[1]` input | **`conv_bck` output** |
| 141 | `L0` | `il_strap[0]` input | **`conv_fs` output** |
| 87 | `C0` | `ic_strap[0]` input | reserved, weak pull-up |
| 85 | `C2` | `ic_strap[2]` input | reserved, weak pull-up |
| 81 | `L1` | `il_strap[1]` input | reserved, weak pull-up |

**Logic elements: 404 → 404, unchanged**, confirming S34's zero-cost claim
on a rebuild of both sides. Pins 71 → 68. Fmax 70.06 MHz against the
baseline's 68.54 — the same pair of numbers S34 quoted as 73.67/64.52, which
is fitter seed noise on a design with ~19 MHz of margin against a 49.152 MHz
`sysclk`; the spread between reruns is larger than the change, and neither
figure means anything beyond "timing is met with room".

**The branch does NOT touch the X-logic parking.** Pins 109/110/111 are
`snake_in`/`snake_out`/`dac_main` on both sides of the diff, still sitting on
option slot 2's lanes exactly as S34-4 found them. That stays for S36.

### S35-3 — the part is not carrying main's logic, and "flash the fix" is 247 LEs of un-benched RTL

**Severity: HIGH — it changes what gate 3's regression is for. Status:
proved by rebuilding the shipping bitstream from its own commit.**

The shipping bitstream on the unit, `dsp4_logic.a1f6672af6c3`, rebuilds
**byte-for-byte** from commit `a4ee3d1f` (2026-08-21) — pof md5
`f08f3b525ff0fe2f7957a96d958842e6`, matching the committed artifact and the
copy staged on the unit (svf `dd1e09185804cb2e451d5089cdd56be3`). So what is
on the part is known exactly, which is worth stating because that bitstream
**predates the design-ID stamp and cannot identify itself** — its manifest
has no `design_id` line, so the readback check build.sh documents does not
exist for it. Its identity rests on the flash records, not on the part.

That design is **157 logic elements**. Today's `main` is **404**. Flashing
the branch would therefore put 247 LEs — the PCM reframe and capture paths,
the design-ID and cfg-bits registers, five weeks of RTL that has never been
on this unit — onto the part *at the same time* as the two-pin direction
change, and gate 3's regression would be measuring all of it at once. If the
latency bar moved, nothing in the method would say which change moved it.

The slot map moved too: the shipping bitstream carries slot-map
`sha256:efd8d5…`, today's tree `sha256:2c53de…` (S34 added pointer notes to
`slot-map.csv`, which is inside the hash whether or not it changes
behaviour).

**So the fix was isolated and built on its own.** `dsp4_logic.138dba7274d6`
is commit `a4ee3d1f` — the exact design on the part — plus nothing but the
pin-direction change:

* **157 → 157 logic elements. The fix is free against the shipping design
  too, not only against main.**
* 71 → 68 pins, the same five pins as S35-2 and no others.
* Fmax 69.92 MHz against the shipping build's 70.21.

It is staged on the unit beside the shipping bitstream. **It is an analysis
artifact and a recommendation for S36, not a sanctioned deliverable** — the
dispatch named the branch, and this is not it. But it is the bitstream that
makes gate 3 mean what gate 3 says: flashed against `a1f6672af6c3`, any
movement in the latency bar is the converter clock pair and can be nothing
else. Advancing main's 404 LEs onto the part is a separate decision with its
own regression, and merging the two into one flash spends the evidence.

### S35-4 — the copper confirms the fix's direction: the analog board is waiting to be clocked

**Status: proved from the global netlist; independent of the RTL argument.**

S34 established that U3 is the only possible driver of `C1`/`L0`. The
remaining risk in making an input an output is the opposite one — something
on the far side of the 33R taps driving back into the pin, which 33R would
not stop.

It does not. The far ends of `R111`/`R112` are `#00716`/`#00717`, which cross
the FPC to the analog board and land on **`U97.2`** and **`U98.2`**. Both
parts have pin 1 N/C, pin 3 GND, pin 5 on `MIC_5-8_17-20_+3V3`, and pin 4 on
the analog-board distribution — single-gate SOT-23-5 buffers, **input facing
the digital board, output facing the analog side**. The analog board does not
generate the converter clock; it is built to receive it from U3 and fan it
out. The fix drives the pin the board already expects to be driven.

The option slots are open and the D32 header unpopulated, so nothing else can
contend today. A future option card that drove `BCK_n`/`FS_n` would fight U3
through 33R, which is what the 33R is for, but that is a card-design rule to
write down, not a defect here.

**A trap for the next reader of the netlist: `C1` and `L0` are each TWO
different nets.** `G2449`/`G2620` are the digital-board clock pair; `G2448`/
`G2619` are unrelated analog-board nets that happen to share the name and
carry seven passives each. The global join keeps them apart by ID; a grep on
the name does not.

### S35-5 — gate 4: nothing on those nets reaches the Pi, so the probe is PW's

**Status: settled from the complete net membership, not inferred.**

**The probe, for PW: with the shipping bitstream, J18 P37 (`C1`) and J18 P38
(`L0`) are dead. With the fix flashed they are 12.288 MHz and 48 kHz. U3 pins
142 and 141 are the same two signals at the source.**

No firmware, no app, no DSP boot is involved either way, and the two readings
are so far apart that a scope-less logic probe or a frequency counter settles
it.

The Pi cannot take that reading itself. Both nets' membership is complete and
closed, and there is no CM4 pin on either:

* `G2449` `C1` — `dsp:J1.37; dsp:J2.37; dsp:U3.142; digital:J18.37;
  digital:R111.1; R61.1; R65.1; R66.1; R67.1`
* `G2620` `L0` — `dsp:J1.38; dsp:J2.38; dsp:U3.141; digital:J18.38;
  digital:R112.1; R60.1; R62.1; R63.1; R64.1`

The TEST pins the RTL already exports are no help either, for the same
reason. `test[0] = fs8` and `test[1] = bck8` — the very pair — reach
`U3.13`/`U3.12`, then `J1/J2.17-18`, `J15.4/6` and `J18.17-18`. `J15` is
marked DNP in the qsf and no CM4 pin is on any of the four nets:

* `G2685` `LOGIC_TEST1` — `dsp:J1.17; J2.17; U3.13; digital:J15.4; J18.17`
* `G2686` `LOGIC_TEST2` — `dsp:J1.18; J2.18; U3.12; digital:J15.6; J18.18`
* `G2687` `LOGIC_TEST3` — `dsp:J1.19; J2.19; U3.8; digital:J15.8; J18.19`
* `G2688` `LOGIC_TEST4` — `dsp:J1.20; J2.20; U3.7; digital:J15.10; J18.20`

So no edge count was attempted and none is possible. Every path from the
converter clock to the Pi ends at a header. Worth recording as a rev-D wish:
one of the four TEST nets to a CM4 GPIO would make this — and every future
clock question — answerable without hands.

### S35-6 — the new sim gate bites, checked by mutation

**Status: negative control run.**

A gate that passes proves nothing unless it can fail. `tb_logic_top`'s new
check samples `conv_bck`/`conv_fs` against `bcki[0]`/`fsi[0]` every `sysclk`
edge and counts mismatches, with a second check that it ran at all
(`conv_samples > 100`).

Driving `conv_fs` from `fs16` instead of `fs8` — a plausible wrong answer,
the other frame sync in the same module, and one that still leaves the pin
driven — fails it:

```
== tb_logic_top: FAIL
   FAIL: conv_bck/conv_fs are not the TDM8 pair (bcki[0]/fsi[0]) (t=52143000)
SIM GATE: FAILED (1 testbench(es))
```

So the gate discriminates the right net from a wrong one, not merely driven
from undriven, and build.sh will not label a bitstream that fails it.

## THE NETLIST AGAINST THE PERSONALITY (2026-09-11, session 34)

Desk session against the hub's new D24 global netlist and TDM map. No unit
touched, nothing flashed, no bitstream produced. Full working:
`MW/D24/DSP/dsp4-s34-20260911.md`.

### S34-1 — the LOGIC bitstream does not drive the converter clock pair

**Severity: BLOCKING (no converter can work). Status: proved from the
netlist and from the fitter's own pin report; the fix is prepared on branch
`s34-converter-clock`, not merged and not flashed.**

`quartus/dsp4_logic.qsf` puts `ic_strap[1]` on PIN_142 and `il_strap[0]` on
PIN_141, and `dsp4_logic_top.v` declares both `input wire`. Today's rebuild
of the shipping source reports them back as `input : 3.3-V LVTTL`, and lists
all five strap pins under "input pin(s) that do not drive logic".

Those two pins are board nets **`C1`** and **`L0`**. Each fans out through
five 33R taps: `R111`/`R112` to the ADC/DAC FPC, and `R65/R66/R67/R61` +
`R62/R63/R64/R60` to `BCK_1..4` / `FS_1..4` — the bit clock and frame sync
of all three option slots and the D32 compatibility header. **U3.142 and
U3.141 are the only active device pins on those nets.** Driven by nothing,
the converters have no clock, and neither does any option slot.

The wire-through lanes say it independently: `i_dspa[0] = ad[0]` is a plain
wire, so the converter frame has to BE the DSP frame, which requires one
generator for both.

How it got in: the rev C LOGIC sheet prints `IC0-IC2`/`IL0-IL1` beside pins
87/142/85/141/81 and the 2026-07-31 extraction read all five as format
straps. Three of them (87 `C0`, 85 `C2`, 81 `L1`) really are dead —
single-pin nets, and the only free user I/O on the part. Two are not.

**One probe settles it and needs no firmware: with today's bitstream, J18
P37 (`C1`) and J18 P38 (`L0`) are dead, not 12.288 MHz and 48 kHz.** The
branch makes them outputs carrying `bck8`/`fs8` — the same pair as
`bcki[0]`/`fsi[0]` — at a cost of 0 LEs (404 before and after), 68 pins
instead of 71, and Fmax 73.67 MHz against the baseline's 64.52. The sim gate
gains a continuous check that the pair is driven and equals the TDM8 pair.

### S34-2 — TDM16 on one net lane: the SHARC allows it, the slot clock does not

**Severity: HIGH (it is the 64-in/64-out question). Status: answered from
the HRM and the netlist; nothing built, because the blocker is copper.**

The premise that a SPORT's A/B halves share one clock and format is wrong.
HRM §21: *"Individual SPORT halves do not share any of its signals across
the pair"* — the sharing is opt-in via `SPORT_CTL2_x.CKMUXSEL`/`FSMUXSEL`
and this design uses none of it. Each half has its own SRU clock and FS
destination (`SPT3_ACLK_I` = `DAI_CLK5.IN0`, `SPT3_BCLK_I` = `IN1`), and
`WSIZE`/`CSn` are per half. The card already depends on this: every DSPA
SPORT runs half A at TDM8 and half B at TDM16.

I5 is also not I3's partner — SPORT3 half A pairs with **half B**, which is
DSPA O3 (`MIX_49_64`), already TDM16 by role and not even enabled today.

So I3 at TDM16 is **two SRU lines**: `SRU(DAI0_PB19_O, SPT3_ACLK_I)` and
`SRU(DAI0_PB20_O, SPT3_AFS_I)` — the DAI0-out pair LOGIC already drives at
24.576 MHz. On I5 it is the DAI1-out pair (`PB20` = BCK3, `PB19` = FS3; note
the DAI0/DAI1 swap). Beyond the two lines, `sport_config.c::cfg_region()`
takes `wsize`/`mcpde` **per region**, so a mixed-format RX region needs both
moved into the per-lane tuple.

**What blocks it is one net.** The option-slot bit clock is not per-slot and
not inverted: `BCK_1..3` are 33R copies of `C1`, which is also the converter
bit clock (same for `FS_1..3` off `L0`). A slot cannot go to TDM16 without
the ADCs and DACs going with it. The escape exists and is a rev-D pin
change: pins 85/81 (`C2`/`L1`) are free pads, and a second LOGIC clock pair
on them re-sources the slot clocks. On rev C it is a six-resistor wire mod.

### S34-3 — LE cost: the ceiling is not what decides this, pins are

**Severity: MEDIUM (it prices the rev-D LOGIC). Status: measured, Quartus
21.1.1, branch `s34-cpld-cost`; no bitstream produced.**

Against a 404 LE / 71 pin baseline rebuilt today (5M1270Z, 1,270 LEs):
slot 3 as a second net card **402** (−2, 79 pins); slot 2 likewise **402**
(79 pins); codec+MEMS+Pi packed onto one TDM8 lane each way **419** (+15);
runtime `net_sel` **452** (+48); all four together **463** (+59, 90 pins).

Worst case is **36 % of the part** with 4.1 ns of setup slack against a
20.35 ns period. The two negative deltas are fitter packing noise — the lane
mux is one LE per lane by construction, and **a second option card costs
pins, not logic**: two slots take I/O from 62 % to 79 %.

The pack stays at 15 LEs only because every source keeps its own slot index
(codec 0–3, MEMS 5, Pi 6–7 replayed there by the re-framer). A source needing
an EARLIER destination slot would cost a full frame of delay — 32 flops a
lane, not 15 LEs for the lot.

### S34-4 — the X-logic parking is sitting on option slot 2's lanes

**Severity: MEDIUM (latent driver fight). Status: found from the netlist;
a corrected parking is in the `s34b_slot2` project on `s34-cpld-cost`.**

`snake_in`, `snake_out` and `dac_main` are parked on U3 pins 109/110/111,
marked PROVISIONAL. Those are `LOGIC_PLL5_0/1/2` = digital `NO6`/`NO7`/`NO4`
= **option slot 2 pins A12/A13/A10**, and two of the three are CPLD outputs.
Harmless until a slot-2 card is fitted, at which point the CPLD and the card
drive the same two lanes. They belong on the PLL1 group (89/91/93), which
reaches only the D32 compatibility header and no device on any D24 board.

### S34-5 — the tracked node ASM is 117 files stale against its generator

**Severity: MEDIUM (hygiene, and it hides real diffs). Status: measured,
not fixed — it wants its own pass.**

`dsp_codegen.py --force` on the UNMODIFIED `dsp.csv` rewrites **117 files**
(+1,180/−536). What was sampled is comment text carried in from later
sessions, but the repo's own rule is that generated files are regenerated,
not edited — and today a regeneration is not a no-op, so no generated-file
diff can be read at a glance. This session kept both option branches clear
of it deliberately, which is why neither carries its node-ASM regeneration.
Fix is one pass: regenerate, review for anything that is not a comment,
land it alone.

## WINDOW CANDIDATE B, PREPARED (2026-09-11, session 33)

Session: `shipping.config.s32` — candidate A plus the off-aux park gate —
taken through candidate A's whole discipline, so that PW's window sign-off
is one word for either candidate. Nothing deployed.

### S33-1 — candidate B measured across the whole range: the twelfth aux fits, with zero missed blocks

**Severity: HIGH (it is the capacity ruling). Status: measured on the part,
sixteen product runs and four scope-class runs, twenty boots, BOTH candidates
on one night with one instrument and one bitstream.**

`shipping.config.s32` — `shipping.config.s26` plus one effective line,
`DSP4_AUXIN_BYPASS=1` — read against candidate A, two boots a row an arm,
270,096 blocks a row (chip 2, average % / worst block):

| product, row | candidate A | **candidate B** | Δ | missed blocks |
|---|--:|--:|--:|---|
| **D32, worst use** (12 aux, 6 reverbs) † | 100.86 / 101.01 | **95.69 / 96.03** | **−5.17** | **1,900 → 0** |
| **D32, silent + loaded** | 100.86 / 101.16 | **95.84 / 95.97** | **−5.02** | **1,900 → 0** |
| D32, driven with the load † | 100.94 / 101.15 | 95.59 / 96.00 | −5.35 | **1,900 → 0** |
| D32, silent default | 76.00 / 76.39 | 70.96 / 71.29 | −5.04 | 0 → 0 |
| D24, driven with the load † | 84.45 / 84.50 | 82.81 / 82.98 | −1.64 | 0 → 0 |
| D16, driven with the load † | 73.18 / 73.19 | 71.35 / 71.45 | −1.83 | 0 → 0 |
| D12, driven with the load † | 66.69 / 66.69 | 64.93 / 64.93 | −1.76 | 0 → 0 |

† partial driven regime — the `driveall` bitstream needs a CPLD reflash this
dispatch forbids — **identically in both arms**, which is what makes the Δ a
measurement. The stimulus-stopped rows are the comparable ones and row B is
the row that overruns.

**THE TWELFTH AUX FITS, BY 4.31 POINTS OF AVERAGE AND 3.97 OF WORST BLOCK**,
and **every row that overruns on candidate A runs clean on candidate B**.

**Twelve nodes on a D32, four on everything else, at the same price.** The
saving is 4.96–5.35 points at D32 and 1.5–1.8 on D24/D16/D12, i.e. **0.41
points a node on four products with four different mask pairs** — and a D32
with the snake scoped off, which has the same four nodes a D24 has, moves
1.39–1.79 (§3.5 of the write-up).

**Chip 1 is a free control and did not move.** Its image is byte-identical in
the two candidates (`6396187c`), and across the six D32 rows it wandered
+0.03, +0.01, +0.03, +0.16, −0.08 and +0.03 points — all inside the ±0.27 the
instrument was measured at (S28).

**The controls reproduce the record on a second, third and fourth night.**
D32 chip 2 rows B/C read 100.86 and 100.94 with 1,900 missed against S28's
100.93/100.82 and 1,914/1,943, S29's 100.78/100.75 and 1,912/1,943 and S32's
100.86/100.83 and 1,898/1,899; D24, D16 and D12 reproduce S28's anchors to a
few hundredths.

### S33-2 — the part cannot tell candidate A from candidate B, and the PROPOSED third config word would not fix it

**Severity: MEDIUM (identification of a shipping image). Status: computed
from both configurations, reproduced on the part in both arms.**

`window-candidate.md` §3.4 records that `shipping.config.s21` and
`shipping.config.s26` produce the same two config words, so `cfgverify`'s
"the part matches the candidate to the bit" does not distinguish them.
**Candidate B is the same shape one level on, and worse**: A and B produce
**identical `DIAG_BUILD_CFG` and `DIAG_BUILD_CFG2`** — `0xCF45FF10` /
`0xC2019E6F` — and every capacity boot of both arms read exactly those two
words back off both chips.

**And S28's designed third word does not separate them either.**
`cfg_words.py --design-cfg3` computes `0xC3000FFA` for candidate A and
**`0xC3000FFA` for candidate B**: `DSP4_AUXIN_BYPASS` has no bit in the
existing two words, and none in the proposed one, because the word was
designed before the flag existed.

So a bench, a factory jig or a field unit holding one of the two candidates
**cannot say which it holds from the part**. The only discriminators are the
chip-2 image md5 (`9222c2ee` vs `df5cc181`) and the presence of the twelve
`_auxin_byp_*` symbols in the build's symbol map — which is a property of the
build artefact, not a word the silicon reports.

**The action, if PW signs candidate B**: `DIAG_BUILD_CFG3`'s bit map needs a
bit for `DSP4_AUXIN_BYPASS` before it lands, or the window ships a
configuration the part cannot name. That is one line in `cfg_words.py`'s
design and one in the generator, taken together with S28 §3's four-edit apply
step — and, as S28 already records, applying CFG3 at all moves every md5
quoted in `window-candidate.md`. It is a hub item, not a session's to smuggle
into a candidate that is being measured.

### S33-3 — resuming from the park drops a pending level ramp, deliberately

**Severity: LOW (behaviour, corner). Status: read out of the emitted source,
designed for, named here because candidate B's deviation list has to be
complete.**

The park stops the node being called, so its level ramp stops advancing too.
The generated control-rate section therefore clears `_auxin_level_frames_`
on the block the node resumes, and the level becomes the **target** rather
than continuing from where the ramp stopped.

That is the right choice and the comment in the emitted code says why: in the
ungated build the ramp advances while the node is off (silently — `q` is
zero) and has long since arrived, so clearing the count reproduces the
**ungated steady state**. The two builds differ only in one corner: a level
written while the node is OFF **and** an `on` 0 → 1 flip inside the same ramp
window (the SPI ramp time, tens of milliseconds). Ungated, the flip lands on
a partly-ramped level and finishes the ramp; gated, it lands on the target.
Both step at the flip, because `on` is an `InstantCtl` cell in both builds —
what differs is the size of that step and whether a ramp follows it.

Nothing in the app writes a level to a switched-off aux input and turns it on
inside the same ramp window today. It is listed as candidate B's fourth
deviation (`window-candidate.md` §5) rather than left to be discovered.

### S33-4 — the gate is in ALL THREE chain orderings, checked rather than inherited

**Severity: NONE (a check that passed). Status: read out of
`chip2/process_chain.asm`.**

`chip2/process_chain.asm` emits the chip-2 chain three times under different
preprocessor arms, and a gate present in only the compiled one would be a
saving that disappears silently the day a configuration selects another. All
three carry twelve gate sites, under three distinct label prefixes —
`.c2brunab*`, `.c2grunab*`, `.sgrunab*` — 36 sites in all, and the two nodes
the generator REORDERS ahead of `C2_MIX_MAIN_L/R` (`C2_USB_IN`, `C2_BT_IN`,
the four standing `dsp_validate` process-order notes) carry the gate at the
MOVED call site.

### S33-5 — the latency bar has now been unavailable to two sessions for the same reason, and it is the last gap in candidate B's set

**Severity: MEDIUM (evidence completeness, not firmware). Status: named, with
what it would take.**

S29's latency method needs the `maincap` bitstream for the through-DSP arm
and `pisel` for the CPLD-loop reference it is measured against. S32 and S33
were both told not to reflash the CPLD while the analog board may be
attached, and both obeyed. The consequence is cumulative and worth stating
once, plainly:

* **candidate B has no latency measurement of its own**, and
* **no session since S29 has taken a FULLY DRIVEN capacity row** on any
  image, because that needs `driveall`.

Everything else in candidate A's evidence set candidate B now carries. One
session that is allowed to flash the CPLD closes both gaps in one boot pair:
`driveall` for the four fully driven product rows, `maincap`/`pisel` for the
82-sample bar. **That is a bench-access ruling, not an engineering question — and
it is the only thing standing between the two candidates having identical
evidence.**

### S33-6 — the worst-block correction is switched off on exactly the rows that need it

**Severity: MEDIUM (instrument). Status: measured across twenty-four D32
chip-2 rows of two arms; worked around in the reading, fix named.**

S21-6 found that about one worst-block figure in six is one `TPERIOD`
(983,040 cycles, 300 % of a block-16 budget) too big, because the tick ISR
can fire between `main.asm`'s two reads. `dsp4_capacity.py` reports a
de-ticked figure beside the raw one — **but only when the arbiter counted
ZERO missed blocks over the dwell.**

That guard is right in principle (a genuine four-times-budget pass really does
drop three blocks) and it has a consequence nobody had hit until a session
measured an overrunning arm twice: **candidate A's rows are exactly the rows
that miss blocks, so they never get a corrected worst block** — and three of
its six D32 rows came back with a raw latch of `400.56 %`, `400.58 %` and
`400.80 %` sitting next to an average of `100.86 %`. Quoted unqualified, that
is a worst-block column that reads 400 % on the candidate PW is being asked
to sign.

`proc_cyc_max_after_clear` — a second latch read over a short window after the
dwell's clear — is available on every row and is sane on every row: across all
twenty-four D32 chip-2 rows of both arms it sits within **0.3 points** of the
de-ticked or under-150 % figure. S33 therefore reads the worst block as
de-tick → raw-if-under-150 % → after-clear, **identically in both arms**, and
says where the fallback was used (§3.2 of the write-up: three candidate-A rows
and one candidate-B row).

**The real fix is still S21-6's own**: read `_diag_ticks`, read `tcount`, read
`_diag_ticks` again and retry the pair if it moved — four instructions per
block in `main.asm`. It is deliberately not made in a session measuring a
candidate, for the reason S21 gave: it would change the image.

### S33-7 — if candidate B ships, S29's scope-class lever is worth 0.15 points instead of 3.5

**Severity: MEDIUM (it retires a question, and it is the one interaction two
levers could have had). Status: measured, two boots an arm, both candidates,
same night, same instrument.**

S29 measured what D32 pays for scope class 0 — the 32 nodes only a D32 boots —
by sending the D24 scope word to a D32: **3.43–3.69 points of chip 2**, and
every overrunning row ran clean without the class. §4a put that to PW as a
product-function question and §3.1 of S29 ruled that the class stays, because
the snake IS the product.

**On candidate B that lever is gone, because the park gate has already taken
what it was worth.** The same arm on candidate B — `CFG_PRODUCT_ID` forced to
1, one config word, the same staged image — moves chip 2 by **0.15 points on
row B and 0.17 on the worst-use rung**, against 3.69 and 3.43 on candidate A.

The two levers overlap almost exactly, and the overlap says what S29's 3.5
points WERE: eight switched-off snake `AUX_INPUT` nodes being CALLED. Gating
the class removes them by product scope; parking them removes them by their
own `on` cell — and the second is the one that does not cost the product a
feature.

**What it means for PW**: on candidate B there is no longer any capacity
argument for gating a D32's snake, so §4a's question does not have to be asked
again. It is not additive headroom either — **the two savings are the same
five points**, and a decision to ship B must not be read as ALSO banking
S29's 3.5.

### S33-8 — `s20restore.sh` reports chip 1 as "NOT diag firmware" on a chip that is running

**Severity: LOW (instrument reporting). Status: reproduced on both restores
this session, disproved by a direct read seconds later; S32's restore did not
show it.**

`PAIR=s26 ./s20restore.sh` printed, twice:

```
  chip1   MAGIC          0x00000000   <-- expected 0xD5B40001: this is NOT diag firmware
  chip1   Everything below is meaningless until MAGIC reads back.
```

and then, four lines further down, chip 1's `build_cfg`, its measured CCLK,
its `_proc_passes` and **90,053 blocks in 30.0 s with ZERO overruns** — read
off the same chip through the same link. A standalone `dsp4_diag.py --chip 1`
moments later reads `MAGIC 0xD5B40001`, `CHIP_ID 1`, `BOOT_STAGE 7`,
`BLK_OVERRUN 0`.

The cause is where the read sits: the restore reads chip 1's diag
**immediately after configuring chip 2**, in the same process, with no
resync — the answer-phase calibration D74 landed is per-Scope, and the first
chip-1 transaction after chip 2 has been driven comes back zero. It is the
same shape as S29-7's "the restore's overrun count is a boot transient, read
pass 3", one register along.

**It matters because of what it says, not what it is**: the line asserts the
part is not running diag firmware, in the script whose whole job is to prove
the bench was left on the window candidate. The fix is a resync-and-retry
around that read, the way `capacity_run.sh`'s `ready()` gate does it. Not made
here — it is a bench script, not an image, but it is also not this session's
to change while the same script is the witness for its own hand-back.


## THE OFF AUX INPUTS, BYPASSED AND MEASURED (2026-09-11, session 32)

Session: S29-4's lead built as a non-shipping pair and driven against the
window candidate on the same night — what twelve switched-off `AUX_INPUT`
nodes cost chip 2, and whether the twelfth aux fits without them.

### S32-1 — twelve switched-off aux inputs cost chip 2 five points, and the D32 worst-use row fits without them

**Severity: HIGH (capacity; it decides PW's "eleven of twelve auxes"
ruling). Status: measured on the part, two boots an arm, both arms on one
night with one instrument and one bitstream.**

`DSP4_AUXIN_BYPASS=1` — a chip-2 `AUX_INPUT` whose `on` cell is 0 publishes
one block of silence and is then **not called** until the cell goes back to 1
— returns **4.84 to 5.20 points of chip 2**, and every row that overruns
without it runs clean with it:

| row | s26 control | s32 arm | Δ chip 2 | missed blocks |
|---|--:|--:|--:|---|
| A silent, default | 75.92 | **71.08** | −4.84 | 0 → 0 |
| **B silent, loaded** | **100.86** | **95.64** | **−5.22** | **1,898 → 0** |
| C stimulus on | 100.83 | 95.75 | −5.08 | 1,899 → 0 |
| use 0:0 | 91.17 | 86.03 | −5.14 | 0 → 0 |
| **use 6:32, WORST USE** | **100.85** | **95.69** | **−5.16** | **1,900 → 0** |

(mean of two boots an arm, 270,096 blocks a row. **Both arms were measured
this session**, on the same bitstream, the same stimulus and the same
partial regime — `driveall` was not loadable under this session's bench
rules, see S32-7 — so every row is like-for-like. Rows A and B are taken
with the stimulus STOPPED and reproduce S29's control: 75.92 against 76.00,
100.86 against 100.78, 1,898 missed blocks against 1,912.)

**Chip 1 does not move and cannot**: it carries no node of this class, and
the arm's `chip1.ldr` is byte-identical to the control's (`6396187c`), so the
0.01–0.24 points it wanders is the instrument's own spread (±0.27, S28).

**Twelve, not eight.** S29-4 named the eight snake returns; the class is
twelve — `C2_SNK_IN_01..08` plus `C2_CODEC_AUX_IN`, `C2_PI_IN`, `C2_USB_IN`
and `C2_BT_IN` — and `dsp4_driven_setup.py`'s `FAM_CLASS` filter leaves every
one of them off in every capacity row this programme has ever taken.

**D32 chip 2 misses fitting by 0.81 points and this returns five.**

### S32-2 — the gate needs TWO words: `on` alone leaves the mix bus reading a stale block for ever

**Severity: HIGH if it had been built that way (audio). Status: designed
around before the first build; the shipped shape is two tests.**

`_blk_<nid>` is read every sample by `C2_MIX_MAIN_L` and `_R`. A gate that
simply stops calling the node when `on` is 0 leaves that block exactly as the
last on-block left it, and the mix bus goes on summing those sixteen samples
3,000 times a second — a switched-off snake return would become a stuck
buzz, not silence.

So the bypass is two mechanisms one block apart: the **park** (S23 gate 2's
mechanism, applied to this class) publishes a block of zeros and sets
`_auxin_byp_<nid>`, and only then does the **chain gate** skip the call. A
1 → 0 flip therefore costs one more call, and a 0 → 1 flip takes effect on
its own block because the gate's first test is the host's own cell — no
config word, no commit, no latency.

### S32-3 — the park leaves `_auxin_q_` stale; inert, one instruction, NOT fixed here

**Severity: LOW (no reader). Status: measured on five nodes, fix named.**

After a node goes back off, `_auxin_q_<nid>` still holds the last
coefficient (`0x10000000`) instead of returning to 0: the park returns
before the body, so the control-rate section that recomputes `q` never runs.

**It cannot reach the audio.** The sample path executes only on blocks where
the node is called and NOT parked — i.e. only when `on` is non-zero — and
sample 0 of every such block recomputes `q` before the first MAC. The
published block is zero either way, measured on all sixteen words of five
nodes.

The fix is one instruction in the park path (`dm(_auxin_q_<nid>) = r0`
beside the flag store, `dsp_codegen.blk_wrap_body`). It is deliberately not
made in the session that measured the image.

### S32-4 — a D24 has four switched-off aux inputs too, and the bypass is worth 1.7 points to it

**Severity: MEDIUM (headroom on every product, not just D32). Status:
measured, one boot an arm, same night.**

The scope gate hides the eight snake returns from a D24, but
`C2_CODEC_AUX_IN`, `C2_PI_IN`, `C2_USB_IN` and `C2_BT_IN` are scoped to NO
product, sit in every product's chain and boot off. So the answer to "does
D24 have off aux inputs in the load" is **yes, four**, and D24 chip 2 moves
by **1.40 / 1.83 / 1.94 points** on rows B / A / C — a mean of 1.72 against
1.72 predicted by scaling the D32 figure 4/12.

**0.43 points a node on a D24 against 0.42 on a D32.** The same per-node
price on two products with different masks and a different scope class is
the strongest evidence the number is what it claims to be.

D24's chip 1 moves −0.16, +0.01, −0.17 — the instrument.

### S32-7 — the driven regime and the bench rules did not compose, and the rule won

**Severity: MEDIUM (scope of the measurement). Status: stated, with what it
does and does not cost.**

Gate 3 asks for the fully driven worst-use row; the driven ladder needs the
`driveall` LOGIC bitstream; and the same dispatch says **do not reflash the
CPLD** because the analog board may be attached and the 74HC595 chain is
never to be approached — which is exactly what a CPLD reconfiguration
tri-states for the length of an SVF. **The CPLD was not touched.**

What that costs: the four rows taken with the stimulus playing ran a partial
regime (`0 of 64` chip-1 envelopes, `27 of 32` chip-2) **in both arms
identically**, so the Δ between them is still a measurement, but those rows
are not the fully driven rows S27/S28/S29 quote and are labelled throughout.

What it does not cost: **rows A and B are taken with the stimulus stopped**,
by the same script in the same order as every previous session, and **row B
is the row that overruns** — 100.86 % with 1,898 missed blocks, 0.03 points
from the fully driven worst-use row S29 measured. The question was answerable
without the stimulus because a per-CALL gate does not care what the signal is
doing, which S29 established across six regimes and this session reproduces
across five.

### S32-8 — `fit-table.csv` could not be regenerated without silently losing every measured row

**Severity: MEDIUM (a generated file that regenerates WRONG). Status: fixed
by committing the missing input.**

The table's header says "GENERATED by tools/dsp/product_fit.py. Do not
hand-edit", and running that script on the repo alone rewrote **twelve of
its sixteen rows**: the measured product rows come from `--measured <json>`,
S28 passed one, and that JSON was never committed — so without it every
`measured` row silently degrades to `construction` and the "1,943 missed
blocks" notes vanish.

Recovered from the table it produced and committed as
`MW/D32/DSP/fit-measured.json`, with the canonical command written into the
script's docstring and into the CSV's own header. Regenerating with it
reproduces all sixteen product rows byte for byte, which is how S32's four
`@s32-lead` rows were appended without touching one of them.

### S32-5 — the committed `src/` tree is NOT what `dsp_codegen.py` emits today

**Severity: MEDIUM (reproducibility of the window candidate). Status:
reproduced at HEAD with the session's own changes stashed.**

Regenerating the whole tree with today's generator rewrites **117 files**:
116 of them carry only the comment change from 608a1aa (the `fix` overflow
wording), but `C1_FILT_01..32` and `chip1/shared_kernels.asm` carry a REAL
one: the per-sample shared-kernel stub no longer loads the block-pool
register (`i6 = BLK_CHAIN_B_P1; l6 = 0;`), because the generator learned to
ask whether each half of the shared body actually reads it.

**So a full regeneration today changes chip 1's image and `6396187c` stops
reproducing** — on a configuration (`DSP4_SHARED_KERNELS=15`) that the window
candidate ships. This session therefore regenerated **only the files its own
change touches** (the twelve AUX_INPUT nodes, `chip2/process_chain.asm`,
`dsp_block.h`) and left the drift where it found it, so that the control arm
could reproduce the candidate byte for byte — which it did.

Whoever regenerates the tree next has to re-measure chip 1 and re-stamp the
candidate's md5s. That is a hub item, not a session's to smuggle in.

### S32-6 — `check-contract-drift.sh --strict` fails at HEAD, and its abort leaves `_matrix.csv` stripped

**Severity: MEDIUM (a dirty tree that reads as contract drift). Status:
reproduced at HEAD with this session's changes stashed.**

The script fails with *"the graph has drifted from the landed dsp.csv /
dsp-unmapped.csv contract"*, naming `Chan<nn>MatrixOn/MatrixSend` — the
matrix-send cells the graph carries as a PROPOSAL and the landed defs do not
have. Nothing in this session touches a cell, an address or the graph, and
the failure reproduces identically with every change stashed.

The part worth recording is what it leaves behind: `sync-defs.sh` re-expands
`MW/<P>/MX/_matrix.csv` and then `gen_dsp.py --force` — the step that
backfills the DSP address columns — **aborts**, so the tree is left holding a
`_matrix.csv` with `DspPage`, `DspAdd`, `DspAddHex` and the whole
`RampProfile` block EMPTY. `git status` then shows a 7,000-line diff that
looks like real drift and is the script's own half-finished work. Restore it
with `git checkout` rather than committing it.

## THE LOST MCU ANNOUNCE IS A COLLISION ON THE MX BUS (2026-09-11, session 31)

Session: the announce measured on the wire with `matrix-app` stopped, the
mechanism named, and B13 / S27-6 / S29 reconciled against it.

### S31-1 — the lost announce is a COLLISION between H1S1 and H1S4, not an app race

**Severity: HIGH (MCU firmware, fw-repo owned). Status: reproduced on the
wire with `matrix-app` STOPPED and no app in the path, 2026-09-11.**

All three slaves answer `S_RUN` on a fixed schedule — the whole announce
burst is three lines inside **7 ms**, 208 ms after `S_RUN`, and on 14 trials
that had the port to themselves it is 3 of 3 every time, millisecond-stable:

```
  +0.003 s   // resuming normal operation
  +0.005 s   // debug only
  +0.208 s   // H1S1 DSP
  +0.211 s   // H1S4 SW Left
  +0.215 s   // H1S3 SW Right
```

**H1S1 and H1S4 are 3 ms apart, and one line-time at 115200 is ~1.2 ms.**
Replaying the same sequence with the host's first read deferred reproduces
the fault with no app running — **6 failures in 40 trials, 15 %** against the
app ladder's 1 in 8 — and what comes back is **not a missing line, it is a
garbled one**:

```
0000  2f 2f 20 72 65 73 75 6d 69 6e 67 20 6e 6f 72 6d  |// resuming norm|
0010  61 6c 20 6f 70 65 72 61 74 69 6f 6e 0a 0a 2f 2f  |al operation..//|
0020  20 64 65 62 75 67 20 6f 6e 6c 79 0a 3a 0a 2f 2f  | debug only.:.//|
0030  20 48 31 50 00 00 10 22 01 9a 5d 81 4c 65 66 74  | H1P..."..].Left|
0040  0a 2f 2f 20 48 31 53 33 20 53 57 20 52 69 67 68  |.// H1S3 SW Righ|
0050  74 0a 2e 0a 3a 0a ...                            |t...:...        |
```

`// H1S1 DSP\n// H1S4 SW Left\n` is 28 bytes. What arrived is `// H1`, then
**nine bytes of framing wreckage**, then `Left\n` — 19 bytes. Two
transmitters drove the line at once, the receiver lost framing, and H1S3,
4 ms further on, came through clean.

**Five of the six failures are this, and all five garble exactly H1S1+H1S4
and leave H1S3 intact** — which is S27-6's "H1S1 and H1S4 fail together or
not at all" **confirmed and explained**: they do not fail together by
coincidence, they fail together because they collide with each other.

`SRX`/`MRX` are multi-drop by design (`MW/D24/HW/hardware-map.md` §3a: the
S/BUSY/SRX/MRX nets "are SHARED with U8 (M MCU) and enter LOGIC (U3)", and
the J3/J4 harness takes them off-card), so several devices drive one net into
the host with no arbitration on it.

**The fix is in MCU firmware** (`mcu/H1S1/`, `mcu/H1S3/`, `mcu/H1S4/` in the
fw tree): stagger the replies to `S_RUN` by more than one line-time — ≥5 ms
with margin, against today's 3 ms — or have MH1 poll the slaves individually
instead of broadcasting and letting all three answer. **Nothing in the app
can fix it**, and no change is warranted to the 8 s verification window
(S31-3).

### S31-2 — the second grade: the bus wedges mid-burst, 0 of 3 and no heartbeat

**Severity: HIGH (same cause). Status: reproduced on the wire 2026-09-11.**

The sixth failure of the forty is different: `resuming` and `debug only`
arrive and then **nothing at all — not even the heartbeat**:

```
trial 17: 0 of 3 []   rx=47B
0000  2f 2f 20 72 65 73 75 6d 69 6e 67 20 6e 6f 72 6d  |// resuming norm|
0010  61 6c 20 6f 70 65 72 61 74 69 6f 6e 0a 0a 2f 2f  |al operation..//|
0020  20 64 65 62 75 67 20 6f 6e 6c 79 0a 3a 0a        | debug only.:.|
```

47 bytes in an 8 s drain against 160 on a clean trial, and MH1's `.`/`:`
running-mode heartbeat — every ~253 ms on a healthy bus — stops dead. **The
collision does not merely corrupt the announce; it can wedge the bus master
mid-burst.**

This grade is what the app's one failing restart shows, one announce further
in: H1S1 logged clean and then no further `//` line at all —

```
  08:11:00.741953  MCU verified: // H1S1 DSP
  08:11:06.973369  WARNING: MCU not verified after S_RUN: H1S3
  08:11:06.973428  WARNING: MCU not verified after S_RUN: H1S4
```

— and it is the grade S29 met five times. So **S29's 0 of 3 is a real state
of this unit**, not only a reading error; what does not stand in S29 is the
evidence it was read from (S31-4).

### S31-3 — the 8 s window has 6.1 s of slack; widening it fixes nothing

**Severity: none — it closes a suspect. Status: measured, 2026-09-11.**

B13's suspects included the announce window. From the app's own log on a
clean restart:

```
  08:11:31.3288  open /dev/serial0 at 115200
  08:11:31.3656  S_RESET '*' x2            (Boot() constructor)
  08:11:34.8359  S_RUN   '+'               = +3.470 s
  08:11:36.6708  MCU verified: // H1S1 DSP = S_RUN +1.835 s
  08:11:36.7091  MCU verified: // H1S3 SW Right = S_RUN +1.873 s
  08:11:42.8368  verdict                   = S_RUN +8.001 s
```

The last announce lands at `S_RUN` +1.87 s and the verdict fires at +8.0 s.
**The window is not the race.** Neither is "restart it twice" a workaround —
S27-6 said so and this session's ladder agrees: the 15 % is per restart and
independent.

### S31-4 — the ladder: 7 of 8, and what in S29's evidence does not stand

**Severity: MEDIUM (record correction + instrument). Status: 2026-09-11.**

Eight `systemctl restart matrix-app; sleep 32` restarts, verdict from the
whole of `/home/app/logs/log` each time (it is rewritten at app start), app
md5 `774752174a7f59637a082031f3fd4231` re-read at every one and unchanged:
**7 of 8 verified 3 of 3, 1 of 8 verified 1 of 3 (H1S1 only), 0 of 8 verified
0 of 3** — against B13/S27's 5/2/0 and S29's 0/0/5.

S27-6's pair claim is confirmed (S31-1). What is wrong is the generalisation
that followed it — "H1S3 announces every time and is never the one that
fails". The one failure here **lost H1S3 and H1S4 and kept H1S1**, because it
is the wedge grade (S31-2) and not the collision grade. **There is no immune
slave.**

**S29's instrument.** S29 records that the app "holds `/dev/ttyAMA0`, and its
journal carries no MCU text at all". `journalctl -u matrix-app` carries **no
MCU text on any restart, ever** — for the whole of 2026-09-11, across the
seven restarts here that each verified 3 of 3, it returns **0** matches for
`MCU verified|MCU boot verified|not verified`. The app writes those lines to
`/home/app/logs/log` alone. An absence was read off an instrument that cannot
show a presence; the conclusion happened to be right (S31-2) and the evidence
never supported it.

**Both discriminators gate 3 nominated are excluded by the unit's own audit.**
The unit was not power-cycled between S29 and this session: uptime 4:25 at
08:06 BST puts boot at **03:40 BST**, which predates the S29 dispatch
(05:05Z). And the CPLD is not the difference — every flash since boot, from
the `sudo` audit:

```
  04:06:14  dsp4_logic_driveall.e13b5dec84e0
  05:47:49  dsp4_logic.a1f6672af6c3        (shipping)
  06:12:22  dsp4_logic_driveall.e13b5dec84e0
  07:19:36  dsp4_logic_maincap.d903ae1ac4a9
  07:37:25  dsp4_logic_pisel.bd9c100db7c2
  07:42:35  dsp4_logic.a1f6672af6c3        (shipping)
```

S29's restarts (05:50:54 / 05:53:20 / 05:55:37 / 05:55:58) ran with the
**shipping** bitstream already loaded at 05:47:49 — the same one loaded now.
The MH/panel UART copper does cross this CPLD (`dsp4_logic.qsf`:18-31 names
`MHRX/MHTX/SRX/MRX/PTRX/S5-7/BUSY` as the pins a mis-built bitstream
ground-drives, hardware-proven 2026-08-19), so the question was fair; the
timeline answers it no. **S28 and S29 differ by nothing but which face of a
15 % dice they saw**, five times in a row against a 1-in-13,000 chance — the
wedge grade evidently clusters, which is itself worth the firmware's
attention.

### S31-5 — the app's only serial reader is started after the thing it must not miss

**Severity: MEDIUM (app, mx26-owned). Status: measured and located in source,
2026-09-11. NOT the cause of S31-1 — a separate defect.**

`// resuming normal operation` and `// debug only` are **2 ms apart on the
wire**. In the app's own trace they are **17.5 ms apart**
(`08:11:00.708267` → `08:11:00.725723`). Two lines that are provably 2 ms
apart take 17.5 ms to come out of the app, so the 18.5/19.8 ms spacing
between the three logged announces — which repeats to better than 1 ms on
every clean restart — is host-side, not bus scheduling.

From the source: `GetRxData()`, the app's only serial reader, is called from
exactly one place — `UiTimerCallback` → `Dispatcher.UIThread.Post`
(`Boot.cs:780`), on the Avalonia UI thread behind a reentrancy guard — and
the timer that drives it is started at the **end** of `Boot.Loop()`
(`Boot.cs:558`), **after** `S_RUN` is written at `Boot.cs:517`. Nothing
drains `/dev/serial0` while the announce is on the wire, so **every announce
the app has ever seen was read out of a backlog** during the busiest seconds
of startup, one line per tick, with a synchronous `AppContext.log` file
append per line (`TxRxData SLOW: 9.78ms / 17.18ms / 19.38ms` in the trace).
`Boot.cs:545` half-knows it already: `WaitForResume()` is disabled with the
comment "MCU sends the string after boot data fills the buffer, which drains
too slowly".

Proposed to the hub (mx26 owns the app; nothing was edited here): start the
reader — or a dedicated reader thread that owns the port and feeds a queue —
**before** `S_RUN` is written, and take the file append off the read path.
It does not fix S31-1, but it removes the app from the suspect list and makes
the announce arrive in 210 ms instead of 1.84 s, which matters because
`RunAnalogBringUp()` is gated on this verification
(`AnalogBringUp.ClockGates` fails the "S MCU (H1S1) alive" gate unless H1S1
is in `_verifiedMcus`).

### S31-6 — two readers on one tty steal each other's bytes

**Severity: instrument, self-inflicted. Status: recorded so it is not
mistaken for signal.**

A 20-trial wire run and a defer sweep were briefly launched concurrently on
`/dev/ttyAMA0`. Trials 1–10 of the wire run are clean and byte-identical
(`lines=44`); from trial 11 the line count collapses to 21–25 and trial 12
reads 2 of 3 — a false positive for exactly the fault under investigation.
Those trials are discarded and every figure in S31-1..S31-5 is from a run
that had the port to itself. `matrix-app` is itself one such reader: the wire
cannot be watched while the app is running, which is why S31-1's separation
had to be done with the app stopped — and why the wire has never been read
on a restart the app itself scored.

## WHAT D32 PAYS FOR SCOPE CLASS 0, AND THE LATENCY BAR (2026-09-11, session 29)

Session: the 32 snake nodes named and weighed on the part as one config
word; the through-DSP latency arm's seven-session null found and the bar
re-measured on the window candidate.

### S29-1 — the FX ladder and the USE ladder could not share a boot

**Severity: instrument, latent. Status: FIXED and witnessed.**

`capacity_run.sh` runs the FX ladder before the USE ladder. The FX ladder's
`off` rung leaves the six engines OFF, and `dsp4_driven_setup.py --mode use`
writes crosspoint families only — it does not touch FX. So an arm setting
both `FXTYPES` and `USELEVELS` would have taken S24's **worst-use** rung with
the plugin load absent and labelled it worst use. No arm had ever set both,
so nothing in the record is wrong; S29 needed rows A/B/C/D and the worst-use
rung on ONE boot and would have been the first.

FIX: the load is re-applied and the regime re-proved between the two ladders,
with a line in the log. Witnessed on every boot of both arms: `chip 1 loadfx:
1632 written, 0 FAILED`, `6 of 6 engines on, Type [3], 6 of 6 comb delay
lines carrying signal`. An arm that sets only one of the two is untouched, so
no row already in the record moves.

### S29-2 — scope class 0 costs chip 2 3.5 points, it is the whole of D32's deficit, and the product cannot decline to pay it

**Severity: none — it is the result. Status: measured on the part, two arms
× two boots, one image.**

`CFG_PRODUCT_ID` gates 34 of the graph's 698 nodes, and it gates the CALL:
under `DSP4_BLOCK_KERNELS && DSP4_SCOPE_GATE` `process_chain.asm` compares
`_product_id` once per contiguous run of scoped nodes and branches over it.
Booting a D32 with the D24 scope word skips 16 chip-1 and 16 chip-2 nodes and
adds 2. Measured as exactly that — same staged bytes, one word different,
both chips asked what they got:

| row | chip 1 Δ | chip 2 Δ | missed blocks ON → OFF |
|---|--:|--:|---|
| A silent, default | −0.40 | −3.53 | 0 → 0 |
| B silent, loaded | −0.28 | −3.69 | **1,912 → 0** |
| D driven, FX off | −0.22 | −3.42 | 0 → 0 |
| C driven, the load | −0.61 | −3.47 | **1,943 → 0** |
| use 0:0 | −0.57 | −3.53 | 0 → 0 |
| **use 6:32 worst use** | −0.48 | −3.43 | **1,943 → 0** |

Chip 2's cost varies by 0.26 points across six regimes, which is what a
per-CALL gate should look like. The resolution is ±0.27 (S28, sixteen
comparisons); 3.43 is thirteen times it. The control arm reproduces S27 and
S28 **to the block** — 1,943 missed, three nights running.

**And it is PRODUCT FUNCTION.** Scope class 0 is the D32R stage-box digital
snake: `io.snake,1` in `defs/products/d32/d32.csv`, `A_I5` TDM8 on SPORT 5
selected by `strap_d32` in the CPLD, `B_O2` on the way out, and **sixteen
cells on the GATED contract** — `Snk[1-8]On[1-1]` / `Snk[1-8]Level[1-1]`,
mode `rw`, page 1 addr 1861–1876, dispatched to `C2_SNK_IN_01..08` and summed
into `C2_MIX_MAIN_L/R`. No other product's mx-master contains one. So the
worst-use ruling stands: **D32 chip 2 does not fit at twelve auxes, 100.81 %
with 0.72 % of blocks missed.**

### S29-3 — S28-6's mechanism is confirmed by measurement

**Severity: method. Status: confirmed; the construction fix is NOT made here.**

S28 inferred the step from four points and a slope. The prediction and the
measurement:

| | S28's segment excess | S29, measured |
|---|--:|--:|
| chip 2 | (3.29 − 2.36) pts/aux × 4 = **+3.7** | **+3.53** |
| chip 1 | (1.82 − 1.755) pts/strip × 8 = **+0.5** | **+0.40** |

`tools/dsp/product_fit.py` interpolates a line through D24 and D32 that
carries a constant it treats as a slope, which is why it under-predicts D12
and D16 with the same sign every time. A corrected construction subtracts
3.53 / 0.40 from the D32 anchor first. That changes predictions only, and it
is left for a session other than the one that measured it — S21-6's
discipline.

### S29-4 — eight aux inputs that are SWITCHED OFF cost 3.5 points of chip 2

**Severity: opportunity. Status: a LEAD, not taken inside the window.**

The chip-2 half of scope class 0 is eight `INTERCHIP_RECV` and eight
`AUX_INPUT`, about 45 cycles a sample a node. **Every one of those AUX_INPUTs
carries `on=0`** — it is their `dsp.csv` default, and
`dsp4_driven_setup.py`'s `FAM_CLASS` filter deliberately keeps the load from
opening them — so they cost 3.5 points of chip 2 while doing nothing. The
price is being CALLED. That is S23-5/S24's block-level-bypass finding one
node class down, where an all-zero aux bus was paying 0.82 points until it
got a bypass.

Skipping an `AUX_INPUT` whose `on` is 0 at the chain, the way a scoped node
is skipped, is worth up to ~3.5 points of chip 2 on a D32 whose snake is
idle — against a **0.81-point** deficit at worst use. Not taken: it changes
the shipping image inside the release window.

### S29-5 — the latency null was the duplex overlay, and S12-10's attribution has been wrong since S17 fixed it

**Severity: method — seven sessions inherited it. Status: found, and the bar
runs.**

S27-7 read four buffers at the END of the main chain, found a constant
`0xfffffffc`, and concluded the stimulus was not reaching the DSP. Reading
the end of a dead chain says it is dead, not where it died.
`tools/pi/dsp4_s29_playpath.py` walks every stage of the playback path on
both chips with the stimulus ON and OFF, and calls a stage live only if it
moves when playing and not when silent. Run on `driveall` and again on
**`maincap`, the very bitstream S27 used**, under the standing
`dsp4-pcm-slave` overlay:

**the whole playback chain is live, every stage, both bitstreams** — Pi
re-framer → `C1_XIN_PI_L/R` → inter-chip slots 27/28 → `C2_XR_PI_L/R` →
`C2_PI_IN` → `C2_MIX_MAIN_L/R` → `C2_MAIN_FDR` → `_DLY` → `C2_MAIN_ST_OUT`,
each reading `0x0fffffff` / `0xf0000000` while playing and a constant while
silent. Two negative controls held: `_buf_C1_IN_01` and `_buf_C2_RECV_MAIN_L`
dead at `0x00000000` in both states.

So the playback side works. What S27 changed was the **PCM overlay**, on
S12-10's advice. S17 had already established the truth and recorded it — the
slave overlay exposes capture on device 0 and playback on device 1, and the
tool drives them separately — but S12-10's "needs a duplex overlay" was never
retired, and `dsp4_dsp_latency.py`'s own refusal message still says it. It
should lose that clause.

### S29-6 — the through-DSP latency contract is measured on the window candidate: 82 samples

**Severity: none — it closes a carried item. Status: measured, n=3.**

| arm | bitstream | boots × reps | median offset | coherent |
|---|---|---|--:|--:|
| LOGIC only, CPLD loop reference | `pisel` | 1 × 20 | **14433** | **100.0 %** |
| window candidate `s26` | `maincap` | 3 × 20 | **14515 / 14515 / 14514** | **100.0 %** |

100.0 % coherent on all 80 reps, against S27's 0.0 % on every rep of every
arm. Through-DSP latency is the difference: **82 / 82 / 81 samples**, 1.708 /
1.708 / 1.688 ms. S20's 82 was carried on the argument that block size and
`DSP4_TX_EARLY` had not moved; it is now the candidate's own number, and it
reproduces S17's 82 and S11's 82. The reference is a control that
discriminates (82 samples lower, peak width 4 against 1) and that **did fail
during the session** when the playback device was busy — the tool refused
rather than scoring a silent capture.

### S29-7 — `s20restore.sh` quotes an overrun count it cannot clear

**Severity: instrument. Status: named, not fixed.**

Restore passes 1 and 2 both reported chip 2 at **exactly 2,240 overruns of
90,049** — the same count S28's pass 1 reported. An identical figure on two
independent boots is not a measurement of the dwell: `blk_*` predates
`DIAG_CLEAR`, the tool says so in the same output (*"THE LATCH DID NOT
DROP"*), and 2,240 is a fixed boot transient accrued before the dwell starts.
Pass 3 read 0 and 0. The restore ladder reads as flaky because the figure it
quotes is unreadable on this pair.

## THE OTHER PRODUCTS' FIT, FROM THE SAME SILICON (2026-09-11, session 28)

Session: D16 and D12 generated from their own definitions, predicted by
construction and measured driven on the part; the CFG2 widening designed.

### S28-1 — D16 and D12 are not new products to the DSP; they are two config words, and their address maps cost nothing

**Severity: none — it is the result. Status: generated 2026-09-11 from
`defs-v2026.09.08.4`, measured on the part the same night.**

The range's two smallest products had never been expanded in this tree. Their
mx-masters have been in `defs/gen/matrix/` all along; `sync-defs.sh` expanded
two products and nothing read the other two. Expanded, they come out as

    cells(D12) ⊂ cells(D16) ⊂ cells(D24)     0 cells outside, either way
    cells(D12) ⊂ cells(D16) ⊂ cells(D32)     0 cells outside

— strict subsets, checked cell by cell. Every one of D16's 2,571 addressed
cells and D12's 1,777 lands on the **same chip, page and address** the D32
map already gives it: **0 disagreements, 0 cells outside the shared map.**
That is decision D3 holding at the third and fourth product rather than the
second.

Nor is there a new graph. The firmware is one image and exactly three words
select a product inside it — `CFG_PRODUCT_ID` (a two-valued scope class),
`CFG_CHAN_MASK` and `CFG_AUX_MASK` — so "the D16 graph" is the same 698 nodes
with 274 of them gated off, and "the D12 graph" is the same 698 with 340 off.
Both were driven on the rev C unit on the byte-for-byte window candidate
(`6396187c` / `9222c2ee`), two boots each, zero missed blocks: **D16 41.69 % of
chip 1 and 73.02 % of chip 2; D12 33.26 % and 66.59 %.** Neither is close to
anything.

D12 and D16 joined the contract flow to get there — `sync-defs.sh` expands
four products, `validate-matrix-contract.py` checks all four, `defs.lock`
gained four declaration hashes and two matrix hashes (`D12_MATRIX_GEN
058dfe9490b9`, `D16_MATRIX_GEN b05bcfc48371`) and the D24/D32 entries are
byte-identical. Zero new cell families: both products' 336 families are inside
the D32 allowlist.

**And the three D32 variants have no fit row because they have no
definition.** `defs/products/d32rack/`, `d32c/` and `d32r/` carry an intake
report and nothing else, whose first line is *"no generated master cell list —
run the def pipeline first"*. No product def, no mx-master, no cell count, no
fit. That is a hub item and it is named rather than guessed at.

### S28-2 — the FX regime bar could not pass on a product with fewer than six FX engines, and it is the same defect the dynamics half of the tool had already fixed

**Severity: instrument. Status: found on D16's first driven row 2026-09-11,
fixed and witnessed on D12 and on D16's re-run the same session.**

`dsp4_c2regime.py --require-fx` enumerates the FX engines off the SYMBOL
TABLE — all six the image carries. `dsp4_driven_setup.py --mode loadfx`
writes the families the LANDED MAP names, which for a D16 or a D12 is
`Fx001..Fx004`. So engines 5 and 6 kept whatever Type the previous boot left
and were never fed, and the check failed the regime three ways at once —
`WRONG TYPE` on two engines, `NO SIGNAL IN THE PLUGIN` on two comb banks,
`KERNEL DID NOT RUN` on two write-pointer banks — for a product behaving
exactly as its definition says.

The dynamics half of the same file has been right about this since the masks
got readers: it reads `_chan_mask_live` / `_aux_mask_live` **off the part**
and reports a masked strip as `masked`, not `dead`, in as many words —
*"a masked node is not a failed regime"*. There is no FX mask on the part to
read, so the count comes from the product definition: `--fx-engines N`, with
`capacity_run.sh` deriving N from the landed map (`max(Fx<nnn>)`) rather than
from the product's name. Engines above N are printed as superset nodes on
their cheap branch and required of nothing.

Witness, D12, the first run with the fix: **4 of 4 engines on, Type [3], 0
parked, 4 of 4 comb delay lines carrying signal, 4 of 4 wptrs advanced, 4 of 4
publishing non-zero** — and `24 of 24` dynamics envelopes live on chip 1 (12
strips × 2 classes) and `24 of 24` on chip 2. D16's re-run adds the scope
line: *"this product defines 4 of the image's 6 engines; C2_FX_ENG_05,
C2_FX_ENG_06 are superset nodes on their cheap branch and are reported, not
required."* D24 and D32, unchanged by the fix, still read `48 of 48` /
`28 of 28` / `6 of 6` and `64 of 64` / `32 of 32` / `6 of 6`.

The general shape is worth naming because this is the third time it has
appeared: **a bar whose scope is the SUPERSET and whose stimulus is the
PRODUCT cannot pass on any product smaller than the superset.** Every
product-scoped bar in the tree should take its count from the landed map.

### S28-3 — the construction had no FX-engine term, and an FX engine is 3.3 points of chip 2

**Severity: method. Status: measured on four products, corrected in
`tools/dsp/product_fit.py` the same session.**

The first cut of the fit table interpolated chip 2 on the aux count alone, so
it predicted a D16's loaded rows as if the D16 ran six reverbs. It runs four —
its definition says `fx,4` and `loadfx` writes exactly the engines the landed
map names.

The correction was available from the anchors the whole time, because the
loaded row minus the FX-off row is a per-engine figure:

| product | engines | chip 2, C − D | per engine | chip 1, C − D |
|---|--:|--:|--:|--:|
| D12 | 4 | 13.23 | **3.31** | +0.15 |
| D16 | 4 | 13.04 | **3.26** | +0.14 |
| D24 | 6 | 20.36 | **3.39** | +0.00 |
| D32 | 6 | 20.24 | **3.37** | −0.09 |

**3.26–3.39 points of chip 2 per live reverb engine, across four products and
two engine counts**, and **chip 1 pays nothing for it** — −0.09 to +0.15,
inside the instrument's own resolution. That figure is now in the
construction, and the product definitions name the engine count, so no product
is predicted with an engine load it does not have.

### S28-4 — `CFG_PRODUCT_ID` is a scope class, not a product identity, and there is no third value

**Severity: design. Status: named 2026-09-11; the fix is the CFG widening's
runtime sibling and is not applied.**

The graph carries exactly two `scope=` classes: `D32`, which is the eight
snake returns with their chip-1 transfers and chip-2 receives (32 nodes), and
`D24`, which is `C2_MON_OUT` and `C2_CODEC_AUX_OUT` (2 nodes).
`_scope_gates_apply` keeps the run whose id EQUALS the booted word and forces
the rest off, so the word selects one of two classes and there is no third
value to give a third product.

D16 and D12 define `mon,1` and no snake, which is the class id 1 selects, so
they boot **`CFG_PRODUCT_ID = 1`** — and the part cannot tell a D16 from a
D24 by that word. It can tell them apart by `_chan_mask_live` and
`_aux_mask_live`, which every bench tool already reads off the part and which
is what S28's rows are identified by, so nothing is unmeasurable. But the word
named `PRODUCT_ID` does not carry the product, and a host tool that trusted it
would be wrong on two of the four products in the range.

It is the same shape as S27-3 one layer down — a configuration the part cannot
name — and the same answer applies: a field wide enough for the thing it is
named after. Not applied inside the window, for the same reason.

### S28-5 — `DIAG_BUILD_CFG2` has no free bits at all, and the comment that named some was naming its own signature

**Severity: correctness of the record. Status: comment corrected
2026-09-11; the widening is designed and not applied.**

`cfg_words.py` carried, beside the S27-3 note, the line *"Free bits in w2 for
the fix: 24 and 26-29."* Bits 24 and 26–29 are the **zero bits of the `0xC2`
signature**, not spare field space — and bit 24 in particular is exactly what
would distinguish a `0xC2` word from a `0xC3` one. A session that had taken
the comment at its word would have widened `DSP4_SHARED_KERNELS` into the
signature and produced a word that decodes as a different register.

Enumerated rather than eyeballed: **every one of bits 0..31 of
`DIAG_BUILD_CFG2` has an owner** (the map is in
`MW/D32/DSP/dsp4-s28-20260911.md` §3.1). So the fix is a THIRD word, for the
same reason `DIAG_BUILD_CFG2` itself exists — the first one ran out and the
answer was another word, not a re-layout. Designed in §3.2, computed today by
`cfg_words.py --design-cfg3`: `shipping.config.s21` would read
**`0xC30003FA`** and `shipping.config.s26` **`0xC3000FFA`**, which is the two
words that are identical today telling themselves apart. Nothing in the
firmware produces it and nothing checks it.

### S28-6 — the two-anchor construction under-predicts every smaller product, and the control proves it is the product and not the night

**Severity: method — it is what gate 2 exists to find. Status: measured on
four products in one session. CONFIRMED 2026-09-11 by S29-2/S29-3 — the
mechanism named below was weighed directly on the part and it is scope class
0: predicted +3.7 / +0.5 from these slopes, measured +3.53 / +0.40.**

Interpolating D24 and D32 and extrapolating below D24 gets chip 1 within
**+0.74…+2.45 points** and chip 2 within **+1.80…+5.35 points**, and **every
one of the sixteen deltas has the same sign**: the construction under-states the
smaller products. The delta is not the instrument and not the session, because
BOTH anchors were re-taken on the same night, on the same image, with the same
script:

| | chip 1 | chip 2 |
|---|--:|--:|
| D24 driven with the load, S27 | 59.82 | 84.37 |
| D24 driven with the load, S28 control | 60.05 | 84.64 |
| D32 driven with the load, S27 | 79.16 | 100.81 |
| D32 driven with the load, S28 control | 79.16 | 100.82 |
| both products, all four rows, S28 − S27 | −0.09 … +0.24 | −0.18 … +0.27 |

**±0.27 points over sixteen comparisons is the resolution.** D12's +5.35 is
twenty times it. D32's two overrunning rows reproduce to the block as well:
1,914 and 1,943 missed of 270,000, against S27's 1,914 and 1,943.

The mechanism is visible once there are four points instead of two. On the
clean row — A, silent, the configuration the product boots with — the
per-unit slopes are:

| segment | chip 1, pts/strip | chip 2, pts/aux |
|---|--:|--:|
| D12 → D16 | +1.77 | +2.32 |
| D16 → D24 | +1.74 | +2.39 |
| **D24 → D32** | **+1.82** | **+3.29** |

The first two segments agree to 0.03 and 0.07. The last one is dearer on both
chips, and the reason is not the strips or the aux buses: **D32 is the only
product that boots scope class 0**, which runs 32 nodes — eight snake returns,
their eight chip-1 transfers, their eight chip-2 receives, and the eight
chip-2 aux inputs — that every other product in the range gates off. The
D24→D32 line carries that step as if it were per-strip and per-aux cost, and
extrapolating it down to twelve channels subtracts it four times over.

Two consequences. **For the range**: the smaller products are cheaper than
D24 by about 1.75 points of chip 1 a strip and 2.36 of chip 2 an aux bus, not
by the 1.82/3.29 the two-anchor line says — a conservative error, in the
direction that makes a product look tighter than it is, which is the harmless
direction to be wrong in. **For the method**: two anchors that differ in more
than one thing cannot separate those things, and this pair differs in three
(channels, aux buses, scope class). The fit table now has four anchors and
`product_fit.py` prints the per-segment slopes so the step is visible rather
than averaged away.

## THE SHARED CLASSES COST NOTHING, AND THREE INSTRUMENTS THAT COULD NOT FAIL (2026-09-10/11, session 27)

Session: the cycle half of S26's result, the window candidate assembled in one
document, and the instrument debt S23–S26 named.

### S27-1 — shared GATE and shared FILT cost nothing, and the null arm is what makes that a measurement rather than a shrug

**Severity: none — it is the result. Status: measured on the part
2026-09-10/11, both products, both chips, two boots, four regimes.**

S26 moved GATE and FILT into shared bodies, recovered 58,072 bytes of chip 1's
code pool, proved the audio byte-identical, and said the CYCLE cost was
unmeasured. Four arms of one tree — `DSP4_SHARED_KERNELS` 3, 7, 11, 15 over
`shipping.config.s21` — priced it driven with the plugin load:

| class | chip-1 avg Δ | chip-1 worst-block Δ |
|---|---|---|
| shared GATE | −0.11 … +0.28 points | −0.26 … +0.70 |
| shared FILT | −0.11 … +0.23 | −0.25 … +0.29 |
| both (the candidate) | −0.12 … +0.12 | −0.06 … +0.29 |

**`chip2.ldr` is byte-identical in all four arms** — GATE and FILT are chip-1
classes — so every chip-2 delta in the same tables is the instrument comparing
one binary with itself. Over twenty-four such comparisons it swings **0.39
points on the average and 0.56 on the worst block**, and chip 1's boot-to-boot
spread is 0.59 at worst over 32 pairs. Every chip-1 excursion above is inside that.

**So both classes ship**, and it is worth recording that the dispatch's
0.5-point revert threshold sits AT this instrument's resolution: a class that
really cost 0.5 points would have been a marginal call.

**The bytes are exactly additive**: GATE alone returns 31,052, FILT alone
27,020, together 58,072 with nothing left over. The control arm rebuilds S25's
and S26's control byte for byte (`c9d0e07b` / `9222c2ee`) and the mask-15 arm
rebuilds S26's candidate byte for byte (`6396187c` / `9222c2ee`).

### S27-2 — a session that forgets DSP_LANDED_DIR measures a lighter product, and chip 2 is where it shows

**Severity: MEDIUM (method). Status: found by doing it, 2026-09-11.**

`capacity.sh` and `famverify.sh` build their cell list from
`tools/dsp/landed_map.py`, which reads the LANDED contract unless
`DSP_LANDED_DIR` points it at the proposal pair. The four-arm ladder above was
taken without that pointer — 5,409 D32 cells instead of 5,765 — so the matrix
sends and the FX-return-to-aux cells were reported ABSENT by `--mode load` and
the buses they open stayed closed.

**On chip 1 it is worth a point; on chip 2 at D32 it is worth ten.** The same
control configuration reads **91.0 %** of budget driven on the landed map and
**100.75 %** on the proposal map, with 0.72 % of blocks missed on the second
and none on the first. A session that quotes the first against the record's
figures is quoting a different product.

It costs nothing in a DELTA measurement — every arm ran against the same map —
which is why the ladder stands. It was caught by `famdiff` reporting six
families moved against S25's golden, five of them MATRIX/MATRIX_OUT/MIX_BUS
verdicts going to `CELL_NOT_IN_CONTRACT`: the diff instrument S26 built said
exactly which thing was wrong. The control and the candidate were re-measured
on the proposal map and reproduce S25 to the digit (D32 78.98 / 100.75 against
S25's 78.97 / 100.75; D24 59.91 / 84.47 against 59.74 / 84.49).

### S27-3 — DIAG_BUILD_CFG2 carries two bits of a four-bit mask, so the part cannot tell `shipping.config.s21` from `shipping.config.s26`

**Severity: HIGH for the window's identification discipline, none for audio.
Status: found 2026-09-11 by reading the candidate's own cfgverify output; NOT
fixed, deliberately.**

`tools/dsp/cfg_words.py` packs `DSP4_SHARED_KERNELS` bit 0 at word-2 bit 5 and
bit 1 at word-2 bit 15. S26 added bits 2 (GATE) and 3 (FILT) to the mask and
no bits to the word. Witness, on the host:

```
  shipping.config.s21  cfg 0xCF45FF10  cfg2 0xC2019E6F  shk=3
  shipping.config.s26  cfg 0xCF45FF10  cfg2 0xC2019E6F  shk=15
```

Identical words. So `cfgverify.sh`'s "**the part matches shipping.config.s26
to the bit**" — which is what it printed on the candidate, on both chips — is
TRUE and would have printed the same on the control. **This is S12-7's shape
one flag along**: two images that differ in what they run, reading back the
same word.

The bench decoder was wrong in a second way that IS decoder-only: its class
table read `((1, 'COMP'), (2, 'class 2'))`, so a mask-3 image printed
`DSP4_SHARED_KERNELS 3 (COMP, class 2)` instead of naming TUBE.

**Not fixed here.** Widening the field moves `DIAG_BUILD_CFG2` on every image
in the tree, including every md5 this session's bars quote, and doing that
inside the window to fix a label is the wrong trade. Instead both ends now say
so out loud: `cfg_words.py` gained an `unrepresented()` that prints **"BUT THE
WORDS DO NOT CARRY: DSP4_SHARED_KERNELS=15 — bits 2 (GATE) and 3 (FILT) are
NOT in DIAG_BUILD_CFG2 ... Identify the arm by its image md5"** beside every
passing check, and `dsp4_buildcfg.py` prints the same caveat under the value
and names TUBE correctly. Free bits for the real fix: word 2's 24 and 26–29.

### S27-4 — the S23-1 first-capture rule is in the capture tool, and the first version of it was inert

**Severity: MEDIUM (instrument). Status: fixed and witnessed on the part
2026-09-11.**

S23-1 measured that the FIRST capture of a boot carries a dynamics-history
term of up to 1,412 LSB that no later capture carries, and that
`busgold`/`ctlgate`/`bqgraph`/`gainsimd` are sound only because they take ONE
capture per boot. That rule lived in a finding. **The run scripts break it by
accident**: `pairgraph_run.sh` retries a failed capture up to four times on
the same boot and compares whichever attempt succeeds against a first-capture
golden.

`dsp4_pairgraph.py` now reads `DIAG_FRAME_COUNT`, keeps a ledger, stamps every
capture with its index in the boot, and refuses to be the second capture of a
boot unless the caller passes `--force` (a within-boot bar with its own
control — `mtxgold.sh`, and it now does) or `--settle` (a throwaway capture
first, so the term is settled whatever the position; stamped, because a
settled capture and an unsettled golden are different measurements).
`compare()` reads the stamps and warns on every incomparable pairing. The
refusal exits non-zero, which the run scripts already answer by re-booting.

**The first version could not read its own witness.** It used `Scope.rd`,
which is a VOTED reader — it asks until one value comes back twice — and
`DIAG_FRAME_COUNT` is free-running:

```
  WARNING: DIAG_FRAME_COUNT unreadable (register 0xE004 never settled:
    {0x9c13: 1, 0x9c1a: 1, 0x9c21: 1, ... 0x9c64: 1})
  boot capture #?
```

Twelve distinct monotonically increasing values — twelve correct readings
rejected for not being identical. `dsp4_capacity.moving()` already had the
rule (single unvoted asks, monotonicity instead of repetition); the guard uses
it now and the next `busgold` run on the same candidate prints **`boot capture
#1`** beside the same `sha256 4126c00730a31f5f`.

The inert version failed exactly as designed — warned, stamped the capture
`None`, let the bar finish — which is the property this guard must keep: every
way it can be wrong makes it PERMIT, never refuse. An instrument guard must
not be able to fail a bar that is sound.

### S27-5 — `loadlogic.sh` decided a CPLD flash had worked by reading the IDCODE, which a MAX V answers either way

**Severity: HIGH (instrument). Status: fixed 2026-09-11; eleven flashes
recorded, no MASK failure.**

S24 needed three attempts to flash the shipping bitstream, with an svf MASK
failure. The script could not have told: its success check was
`scan_chain | grep 0x020a30dd`, and **the tap answers its IDCODE whether or
not the configuration flash took.**

The replacement required openocd's upstream `svf file programmed successfully
for N commands` line. **This openocd does not print it**, so nine good flashes
were reported as failures and retried three times each. The bench was never in
danger — every playback completed and the final state was the intended one —
but an inverted check is worse than none, which is the point of recording it.

**The check was then measured against this openocd** rather than assumed: its
svf driver echoes each SVF command and prints no summary; a completed run ends
with `shutdown command invoked`, because `-c 'init; svf ...; shutdown'` is ONE
chain and a failing svf aborts it before the shutdown; a mismatch prints `tdo
check error at line N`. `Error: Translation from khz to adapter speed not
implemented` appears on EVERY run and is benign, so it is excluded by name.
The script now retries three times with a loud line per attempt, keeps every
attempt in `/home/app/logic-flash.log`, reads the IDCODE before AND after, and
exits 7 naming the CPLD's state as UNKNOWN when nothing succeeded.

**Eleven SVF playbacks across eight invocations this session, every one
reaching its shutdown with no tdo check error. S24's MASK failure did not
recur.**

**And a better restore proof than the IDCODE.** `dsp4_logic_id.py` answers
"no reply" for every bitstream on the `dsp4-pcm-slave` overlay, so its silence
has never meant anything. On the **duplex** overlay it read
`design_id: 32'hae1ac4a9 cfg_bits: 16'h0004 pi_maincap` off the maincap arm
and then "no reply" from the shipping arm ten minutes later on the same proven
path — which IS a positive identification of the shipping bitstream, since it
predates the ID register.

### S27-6 — the matrix-app MCU verify is a race on about one restart in four, and mx26's B13 has it backwards

**Severity: MEDIUM (app, hub-owned). Status: reproduced with the app's own log
2026-09-11; filed to mx26 B13.**

B13 says the FIRST matrix-app restart after reflashing the SHARCs verifies
only H1S3 or none, and the SECOND always verifies all three. Seven restarts on
the restored bench:

```
  03:21:29  (the first after the DSP reflash+reboot)   3 of 3
  03:22:26                                            1 of 3   H1S3 only
  03:23:41  3 of 3      03:24:16  3 of 3      03:24:51  3 of 3
  03:25:27                                            1 of 3   H1S3 only
  03:26:02  3 of 3
```

**Both halves of B13's model are wrong**: the first restart after the reflash
verified all three, and two later ones failed. It is a race, it lands on about
one restart in four, and "restart it twice" is not a workaround — it is
another roll of the same dice.

The signature is exact and identical both times, and the app names the
mechanism:

```
  MCU verified: // H1S3 SW Right
  Boot.Loop() - WARNING: MCU not verified after S_RUN: H1S1 (no startup announcement received)
  Boot.Loop() - MCU boot verified: H1S3
  Boot.Loop() - WARNING: MCU not verified after S_RUN: H1S4 (no startup announcement received)
```

against a good restart where all three announce within 40 ms of each other.
**H1S3 announces every time and is never the one that fails; H1S1 and H1S4
fail together or not at all.** The window is ~9.2 s after the app starts, and
the `Boot.Loop()` verdict lands ~6.2 s later.

**Method note**: `/home/app/logs/log` is REWRITTEN when the app starts, so
"the lines added since a mark" is empty on every restart after the first. Each
restart's verdict must be read from the whole file. The first pass of this
repro reported "0 lines added" for two restarts and nearly filed that.

### S27-7 — S12-10's attribution is incomplete: the latency null survives the duplex overlay and the maincap bitstream

**Severity: MEDIUM (instrument). Status: narrowed, not closed, 2026-09-11.**

S12-10 attributed the through-DSP latency arm's flat field (offset 14779,
coherent fraction 0.0 % on every rep) to the bench living on the
`dsp4-pcm-slave` overlay. This session satisfied both halves of the named
requirement and **positively identified both**: the bench was flipped to
`dsp4-pcm-duplex` (a `config.txt` line and a reboot; the card comes back as
`card 2: dsp4pcm` with ONE device that plays and captures) and the `maincap`
bitstream was flashed and read back as `pi_maincap` / `ae1ac4a9` through that
very capture path.

**The null persists**, 20 reps × 2 boots and again at 2 reps, and
`dsp4_dsp_latency.py` refuses the verdict — the S12-10 fix working.

The new evidence points upstream of the DSP. `dsp4_passthru_setup.py` reports
`chip1: 48 strip cells written` and `chip2: 12 cells written, all present in
the contract`, and the main chain then reads

```
    _buf_C2_MIX_MAIN_L 0xfffffffc   _buf_C2_MAIN_FDR    0xfffffffc
    _buf_C2_MAIN_DLY   0xfffffffc   _buf_C2_MAIN_ST_OUT 0xfffffffc
```

— a constant −4 LSB, identical at every point. Not silence, not the stimulus:
**nothing is arriving at the DSP's input**, so the break is on the PLAYBACK
side of the loop and the capture has nothing to correlate with.

`latency.sh` was also taught to forward `DSP4_PCM_DEV`/`_CAP`/`_PLAY` — the
tool has read them since S17 and no run script could set them, so the duplex
overlay could only ever be used by running the tool by hand.

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

### S25-6 — R5 makes `fixed_ref`'s continuous pan law the wrong model, and famverify says so

**Severity: MEDIUM — a bar is now reporting a mismatch that is the
specified behaviour. Status: measured on the part 2026-09-10, D24, on the
S25 candidate.**

`famverify` D24 on the R5 image reports FADER_PAN numeric FAILED:

    cvt fdr LEFT pan leg    183217856 / 183341408  <-- MISMATCH
    cvt fdr RIGHT pan leg    85217608 /  85094040  <-- MISMATCH

The part's two legs are **table index 40's stored columns, bit for bit**
(`0x0AEBAEC0` / `0x05145148`). The walk writes `Pan = 0.317`; index 40 is
40/126 = 0.317460. The table quantised the write to the nearest of its 127
positions, which is precisely what R5 asks for — "every channel's `Pan`
value is an INDEX into that table". The deviation is **0.058 of one table
step, −0.0059 dB on the left leg and +0.0126 dB on the right.**

So the part is right and the model is stale: `fixed_ref`'s pan conversion
is the continuous linear law, and by PW ruling this graph's pan law is a
127-entry table. Until the bar's model becomes `tools/dsp/pan_table.py`,
FADER_PAN's numeric arm will read MISMATCH for any `Pan` that is not
exactly a table index — which is most of them.

**The model was deliberately NOT changed in the session that changed the
part.** A bar rewritten to agree with the thing it is measuring, in the
same change, is not a bar. The right shape is for `fixed_ref` to consult
`pan_table` when the image carries the table — detectable from the symbol
map (`_pan_tab_lcr`) — and to say in its own output which model it used.
Named, carried, and the honest state today is "MISMATCH, attributed,
0.0126 dB, and it is the specified behaviour".

The pan law is held to account meanwhile by `s25pan.sh`, which scores the
part against the table rather than against the law the table replaced (20
of 20 bit-exact), and by `busgold`, which reproduces the pre-R5 capture
byte for byte.

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

## S74b — defs-v2026.09.19.2 consumed with strict drift; a new sync-defs.sh parse gate

**S74b-1. The fixed expander (`defs-v2026.09.19.2`) parses correctly.**
Checked out and expanded directly: D24 5,002 / D32 7,014 rows under
`csv.DictReader`, every `MxAdd` numeric on both, `Test001SweepOn001` lands at
D24 4874 / D32 6931 exactly as S74-9 predicted it would once the expander
stopped corrupting the row. `gen_dsp.py --check-proposal` on the two
products' existing (pre-RTA) cell sets reproduces the landed contract with
zero errors, confirming the fix touches parsing only, per the upstream
commit message ("no cell, address or master change").

**S74b-2. 0 existing DSP addresses moved; the raw matrix `MxAdd` column is a
different address space and DOES shift — expected, not a regression.**
All eight DSP address artefacts (`dsp.csv`/`dsp-unmapped.csv` proposals,
`gen_dsp.py --propose` output) are byte-identical to `git show HEAD:` for
every pre-existing cell on both D24 and D32 (Table column excluded per the
S53 comparison rule). Separately, the bare expansion's own `MxAdd` column
(the console-facing matrix address `expand_matrix.py` assigns, position-based
over the master's row order, entirely independent of the DSP SPI address
`gen_dsp.py` backfills) DOES shift by +2 for every D24 cell after the
insertion point once the two `Rta` rows land — they insert at master row
position between `Rec001Src001` and `Grp001CompAtt001` (MxAdd 4082/4083 in
the new numbering), not at the tail of the file. This is defs' own cell
ordering, out of this repo's remit, and orthogonal to the "0 addresses
moved" gate, which is about the DSP SPI map this repo owns.

**S74b-3 🔴, for the hub. Gate 1 cannot fully land this session — not a
design question, a missing upstream mirror.** D24's declaring `rta,1`
(`.19.1`) adds `Rta001On001`/`Rta001Src001` to its cell set with no DSP
address (as expected — both are `no-graph-node` in `gen_dsp.py`'s own
`_UNMAPPED_REASONS`, unchanged since S25: RTA control cells have no graph
node backing them, priced not built). `gen_dsp.py`'s no-fallback check
(`check_proposal()`, which gates ALL of `CONTRACT_PRODUCTS = (d32, d24)`
together before anything backfills) therefore refuses — correctly — because
`defs/products/d24/dsp-unmapped.csv` doesn't yet carry these two rows, and
this blocks D32's backfill too even though D32 is untouched by `.19.1`/
`.19.2` (D32 already declared `rta,1` earlier and already carries the
identical two rows). **The fix is a one-file, two-row, zero-risk mirror of
what's already landed for D32**: `proposals/defs/products/d24/dsp-unmapped.csv`
now carries `Rta001On001`/`Rta001Src001`, byte-identical to D32's landed
rows (diffed and confirmed). No dsp.csv change (0 addressed cells added).
Land this in `invirco/defs` (copy the two rows into
`products/d24/dsp-unmapped.csv`, the same handoff S44/S49 used), tag it, and
a following session can consume the pin fully. **`main` is left exactly as
found on the defs side** (submodule back at `defs-v2026.09.16.5`,
`defs.lock` and `MW/{D12,D16}/MX/_matrix.csv` unchanged) for the same reason
S74 gave: landing the pin bump alone would fail `check-contract-drift.sh`
for every session after this one, for a reason this repo cannot fix from
its own side.

**S74b-4. `sync-defs.sh` gains the DictReader parse gate.** Right after
`expand_matrix.py` writes its temp file, before hashing: every non-header
line must produce exactly one `DictReader` row (`rows + 1 == wc -l`), and
every row's `MxAdd` must be a bare integer. Hard `exit 1`, unconditional
(runs under `--update-lock` too — a corrupted expansion must never become
the new accepted baseline). Proven both ways directly:

```
$ git -C defs checkout defs-v2026.09.19.1   # pre-fix expander bug, present here too
$ ./sync-defs.sh
PARSE GATE FAILED: 2297 DictReader rows + 1 header != 2337 lines -- ...
PARSE GATE FAILED: 1 row(s) have a non-numeric MxAdd (first 5): ['Test001SweepOn001']
ERROR: d12's expansion failed the DictReader parse gate -- ...

$ git -C defs checkout defs-v2026.09.19.2   # the fix
$ ./sync-defs.sh --update-lock
Updated defs.lock from defs@defs-v2026.09.19.2 (...)
  D12/D16/D24/D32 all expand cleanly
```

Confirmed FAIL on `.19.1`, PASS on `.19.2`, exactly the class S74-9/S74-10
found. `defs` reverted to `.16.5` afterwards per S74b-3; `sync-defs.sh` /
`gen_dsp.py --check-proposal` / `./check-contract-drift.sh` all confirmed
clean at HEAD with the new gate in place (0 false positives against the
current, uncorrupted `.16.5` expansions).

**What is committed:** `sync-defs.sh` (the parse gate) and
`proposals/defs/products/d24/dsp-unmapped.csv` (+2 rows, the RTA proposal
for the hub). No defs pin change, no matrix change, no DSP address artefact
change.

## S78 — chip 2's ten points bisected, the one-bit shift run to ground, and the driven stimulus made bit-exact

**S78-1. 🔴 CHIP 2's TEN POINTS ARE S22 AND S23, AND BOTH LANDED ON
2026-09-10 — THE SAME DAY AS THE ROWS THEY ARE MEASURED AGAINST.** Eight driven
D24 arms, two boots each, both ends reproducing their references (`s78b74c`
byte-identical to S77's `s77shk0` and reading within 300/500 cycles of it;
`s78b19` reading chip 2 within **13 cycles** of `cap-s19blk` across nine days).
**S22's matrix mixer costs chip 2 +9,583 cycles/block (+2.92 pts) and S23's aux
mix buses + FX returns cost +25,161 (+7.68 pts); the two together are +10.60 of
the +10.69 measured end to end.** Everything else in the range — S24, S32, S42,
S65, S66…S74c — costs chip 2 **+0.09 points**, a twentieth of the instrument's
own chip-2 spread. Chip 1 over the same range: S22 +1.81, S23 +0.98, S32 +0.43,
rest ≤0.16, total +3.30 against S77's +3.60…+3.71. **The record's phrase "nine
days of graph growth since 2026-09-10" is wrong in its premise: the growth
happened within hours of the 2026-09-10 rows and the eight days after are
flat.** The one soft edge is the split between S22 and S23 — `s78b22`'s chip-2
boots differ by 6,729 cycles (2.05 pts) where every other arm's agree to a few
hundred — so S22 is +2.9 ±1 and S23 is +7.7 ∓1; the sum is firm.

**S78-2. 🔴 THE DISPATCH'S TWO NAMED SUSPECTS CHANGE NOT ONE CHIP-2
INSTRUCTION.** S71 (`b361bdb0`, the codec-return lanes) touches only
`chip1/block_io.asm`, `chip1/nodes/C1_TALK_01.asm`, `C1_XIN_CODEC_01/03/04.asm`
and `C1_XS_XFER_CODEC_AUX_L/R.asm` — all chip 1 — plus the `DSP4_TALK_INVERT`
macro in `dsp_block.h`. S74 (`bc22a1cc`) touches no `chip2/` file at all; chip
2's image differs from the arm before it by the config stamp, which is S77's
"two stamp bytes". Both were ruled out **from the generator output before
anything was booted**, and the rows then confirmed it. Two arms (`s78b21`,
`s78b32`) were not booted at all because their images are byte-identical on both
chips to the arm before them — a stronger claim than a measurement.

**S78-3. 🔴 THE ONE-BIT LEFT SHIFT IS PER-LANE MFD, NOT JUSTIFICATION, AND IT IS
THE INSTRUMENT'S ALONE.** Both sides of the CM4 link are I2S and agree
(`pi/dsp4-pcm-slave.dts:62` `format = "i2s"`; `rtl/dsp4_pcm_reframe.v:55`
`PCM_DATA_DELAY = 1`), and the design-ID knock had already proved the de-framer
exact by matching a 64-bit magic word through it. What `DSP4_DRIVE_ALL` did was
broadcast **one** framing onto lanes that do not share one frame delay:
`c1_rx_lanes_mfd[8] = { 2,2,2,2,2,2,1,2 }` (`chip1/lane_config.c:26`) — lane 6
is MFD 1 because LOGIC frames it, the other seven are MFD 2 because a
pin-strapped AKM converter does (`sport_config.c:21-37`, S42-1). MFD one too low
reads `>> 1` (S39-4, measured); one too high reads `<< 1`. **Measured: one boot,
one bitstream, four words, five lanes at once — lane 6 bit-exact on both slots
and every word, lanes 4 and 7 exactly ×2 on every word.** No converter lane in a
shipping build is affected; `DRIVE_ALL` is the only thing that ever puts a
LOGIC-framed stream on a converter half.

**S78-4. THE STIMULUS IS NOW BIT-EXACT ON EVERY LANE, PROVED A/B ON THE PART,
AND THE SIM GATE CAN SEE THE DEFECT.** `rtl/dsp4_pcm_reframe.v` gains
`DRIVE_MFD` (default 2) and launches the broadcast copy one BCK later;
`rtl/dsp4_logic_top.v` leaves lane 6 on `tdm_out`, which is already right for
it, so all eight lanes are exact rather than seven, and lane 6 keeps its
stimulus (its `cs_mask` is `0x0003` and `tdm_out` carries exactly those two
slots). A/B on the part, one change apart: `1ee6b5056fb7` reads **0 exact /
12 ×2**, `c49f4128a083` reads **12 exact / 0 ×2**. Cost: **+16 logic elements,
no pin change**, timing met at 66.19 MHz. `sim/model_tdm_rx.v` had ONE
hard-wired MFD — every testbench instantiated an MFD 1 receiver, which is why a
transmitter aimed at MFD 1 and received by an MFD 2 half read PASS in
simulation and arrived one bit left on the part. Parameterising it forced out a
second model defect: resetting the bit counter at every FS is only correct at
MFD 1, because a TDM8 frame is 256 BCK and the wire is continuous, so at MFD 2
the tail of slot 7 arrives after the next FS. `sim/tb_pcm_drive.v` now carries
the defect as a negative control — a second reframer at `DRIVE_MFD(1)` read by
an MFD 2 half, which must come out `(word << 1)`. **S77-3 fails the suite if it
returns.**

**S78-5. 🔴 THE NO-HANDS LOOP MEASUREMENT COULD NOT BE TAKEN: THE ANALOG RAILS
ARE DOWN AND THIS SESSION IS NOT AUTHORISED TO RAISE THEM.** `GPIO 26 (AN_EN)`
reads `op pd | lo` before and after stopping `matrix-app`, and was left there.
The AUX 1 → talkback loop was run exactly as S70 ran it, on S70's own image
(`chip1 a8dc45eb` / `chip2 251ce3b2`): **the DSP half is perfect** — the route
asserts and proves and the AUX 1 bus tracks the oscillator to `0.000 dB` at five
levels from −80 to −40 dBFS — and **all three received codec lanes read
`-336.124 dBFS`, exact digital zero, at every level including oscillator off.**
S70 read `-75.9 / -98.9 / -68.4` on the same three lanes with the oscillator off
and the rails UP. S70's dispatch said "AN_EN raise authorised in-spec"; S78's
does not. See S78-Q1.

**S78-6. 🔴 MATRIX BUSES 3 AND 4 CANNOT BE ROUTED INTO ON EITHER PRODUCT, AND A
D24 RUNS FOUR AUX MIXES FOR WHICH NO CELL EXISTS.** `Chan001MatrixOn/Send` stops
at `002` in `defs/products/d24/dsp.csv` **and** in `defs/products/d32/dsp.csv`,
while D32's master declares `Matrix003/004 Level+Mute+Name` and D24's declares
neither. So on D32 two matrix buses have an output level, a mute and a name and
nothing that can feed them; on D24 the same two chains have no cell at either
end. Separately, D24 declares `Chan001AuxOn/Send001..008` — eight aux buses —
and the firmware builds twelve `C2_MIX_AUX_*`, so **four run every block on
every D24 for something no cell can turn on**. That is the S23 bypass class
exactly. Both are questions for defs, not for the firmware: S78-Q2.

**S78-7. 🔴 `DSP4_AUXIN_BYPASS` IS OFF IN THE CONFIGURATION THAT SHIPS, AND HAS
NEVER BEEN IN IT.** `build.sh:258` defaults it to 0; `shipping.config.s32:319`
set it to 1; the committed `shipping.config` has no such line, and
`git log -S AUXIN_BYPASS -- shipping.config` returns nothing at all. S32 built
and measured the lever and it was never switched on for the shipping arm. See
S78-Q3.

**S78-8. `dsp4_logic_id.py` DID NOT ANSWER TONIGHT ON THE SAME OVERLAY S77
REPORTED IT WORKING ON.** Two invocations, immediately after a clean
`FLASH OK on attempt 1`: "no reply: nothing in the capture carried the 0xD594
marker." S77-4 recorded the tool fixed and quoted `design_id 0x62d98a4d` read
off this part, on this `dsp4-pcm-slave` overlay, which the standing bench note
says makes the tool useless. **So the one command that identifies a bitstream
from the part is not dependable.** Identity in this session rests on the named
SVF, its md5, the JTAG IDCODE either side — and, better, on behaviour: a part on
which all eight DSPA lanes carry the CM4's playback is running `drive_all`, and
the A/B in §3.3 identifies which `drive_all` it is by what the MFD-2 lanes read.

**S78-9. THE CAPACITY INSTRUMENT REPRODUCES ACROSS SESSIONS AND ACROSS NINE
DAYS.** `s78b74c` against S77's `s77shk0`, byte-identical images: 401,460 /
401,631 against 401,759 / 401,471 on chip 1 and 425,440 / 425,801 against
425,326 / 425,296 on chip 2. `s78b19` against `cap-s19blk` of 2026-09-10:
chip 2 390,725 against 390,712. **After three sessions of repairs the bar is
stable to a few hundred cycles**, which is what makes a step of +9,583 or
+25,161 an attribution rather than a guess.

### 🔴 For the hub

**S78-Q1 — the no-hands loop needs AN_EN, and this dispatch does not authorise
raising it.** The gate asked for the AUX 1 → talkback loop to be played and
read with no hands, on the ground that the loop is "cabled and live". It is
cabled, and it is live on the DSP side — the AUX 1 bus tracks the oscillator to
0.000 dB at five levels — but `GPIO 26` reads `lo`, all three codec return
lanes read exact digital zero, and the converters are not converting. S70 took
this measurement with an explicit "AN_EN raise authorised in-spec" in its
dispatch; the standing bench rule is that a dispatched session never writes
AN_EN. Options:

1. **Authorise the raise in a re-dispatch** (`sudo pinctrl set 26 op dh`, 150 ms,
   measure, `op dl` before handback, exactly as S70 did). ~20 minutes of bench
   time; everything else is staged and the S69/S70 tooling is on the card.
2. **Have the hub or PW raise it** and leave it up for a window a dispatched
   session can measure inside.
3. **Treat §1 and §2 as sufficient** — the shift is located to `DRIVE_ALL` by
   source and by measurement, and no converter lane can see it — and close
   S77-Q1 without the analog check. **This does NOT close the other question the
   loop would have answered**: S70's 6.16 dB between the AK4619's own full scale
   and the ADC full scale it derived at J1 is still attributed to an unmeasured
   loss between J1 and the codec pins, and six decibels is also what one bit is
   worth. Tonight's work makes the MFD class of fault impossible there (the
   codec lane is MFD 2 like every other converter lane) but does not measure the
   loss.

**Recommendation: option 1.** It is cheap, it is the only one that retires the
6.16 dB, and a mic input that is 6 dB hot is not a thing to leave attributed.

**S78-Q2 — two defs questions the bisect turned up, both about cells that do not
exist.** (a) `Chan001MatrixOn/Send` stops at `002` on **both** products while
D32's master declares four matrix buses and D24's declares two — so matrix 3 and
4 are output-only on D32 and absent at both ends on D24, and the firmware builds
four of each matrix node on both. Is that a real product limit (two matrix sends
per channel) or missing rows? (b) D24 declares eight aux buses and the firmware
builds twelve `C2_MIX_AUX_*`, so four run for nothing on every D24. Both are
`defs` changes if they are changes at all; this repo is a consumer and has
invented nothing.

**S78-Q3 — `DSP4_AUXIN_BYPASS` has never been in `shipping.config`.** S32 built
the lever, measured it, and it went into `shipping.config.s32` and no further;
`build.sh` defaults it to 0 and `git log -S` over the shipping file returns
nothing. Is that deliberate, or did the S32 landing simply not carry through to
the configuration that ships? It is points sitting switched off.

**S78-Q4 — the S28/S29 rows are due for re-taking and were not done tonight.**
`cap-s28-{d12,d16,d16oldprover,d24,d32}`, `cap-s29ctl-d32`, `cap-s29ns-d32` —
seven arms — were taken with the full-scale square on the pre-fix bitstream, so
on every MFD-2 lane they were driven at 2 LSB and are silence rows wearing a
driven label. The instrument is now fixed and the recipe is one line per arm
(`ARM=… PRODUCT=… ./capacity.sh --driven` on `loadlogic.sh driveall`). The
night went on the bisect; this is a short session of its own, and the D12/D16
arms will need their own products staged.

**S78-Q5 — what to do with the ten points, now that they are attributed.** S22
and S23 are both architecture rather than options: the matrix mixer and the aux
mix buses are product-defined functions and they have to exist. What is
available is the bypass class in §5 — four `C2_MIX_AUX_*` and six matrix-chain
instances that no cell on a D24 can reach, plus the runtime all-off case — and
it is the same lever S32 built and S78-Q3 says was never switched on. **None of
it is worth designing until Q2 and Q3 are answered**, because both change what
"runs for nothing" means.

## S89d — the DAC fold's handoff code is identical in the folding and clean arms, and `tx_probe` needs a flash

**🔴 S89d-Q1 — `tx_probe.asm` cannot run without a CPLD flash, contradicting
S89c's own framing.** S89c recommended it as "the cheaper route before a scope",
which is true, and also said it needs the `_maincap` LOGIC build — the dispatch
read the recommendation as bench-free. It is not. `_tx_probe_stamp` writes its
stamp INTO the TX DMA ring (`dm(_tx_active_buf + off + sample*stride + 1)`) and
nothing reads it back on-chip; the readback is CPLD → Pi capture, which is why
the file's header names `_maincap` and `CAP_SLOT_L=0 / CAP_SLOT_R=1`. Running it
needs: a `DSP4_TXPROBE=1` build (free), a capture-bitstream flash displacing
shipping `83b3cc22`, the Pi overlay switched from `dsp4-pcm-slave` to duplex plus
a reboot, the S88 double boot+config, the capture, then the whole restore. Two
flashes and an overlay round trip, 45–60 min, no PW hands beyond authorising it.
Note for that session: `DSP4_TXPROBE_LANE` defaults to 18 (SPORT3, the Pi return
lane) rather than the codec lane that folds — which is nevertheless the right
choice, because all five of chip 2's TX lanes share ONE DMA region, ONE
`_tx_active_buf` and ONE ISR, so a write-side handoff fault is common to all of
them. The mirror caveat: each SPORT has its own DDE channel, so a read-side
per-channel skew would NOT show on lane 18, and stamps arriving in order there
would move suspicion to the read side rather than exonerate the transmit path.

**S89d-1 — there is no index or pointer difference to find.** S89c's gate-3 code
search was run and came back empty, decisively. Source: `sport_init.asm`
(`_blk_latch_bufs`), `chip2/block_io.asm` (`_gather_chip2`, `_scatter_chip2`) and
`dma_config.c` contain zero references to `DSP4_SIMD_DYN` or `DSP4_DYN_LUT`;
`main.asm`'s only two are gated by `DSP4_DYN_SELFTEST`, off everywhere here.
Binary: across the signed arm and both single-switch-off arms, `_scatter_chip2`
(55 B), `_gather_chip2` (69 B), `_blk_latch_bufs` (27 B), `_sport_dma_work`
(66 B) and `_meter_scan_chip2` (51 B) are the same length in every arm, and
disassembled they diff to nothing — the raw bytes differ only in relocated DM
operands. So the ring-half selection, the gather, the scatter and the block ISR
are the same instructions in the arm that folds and the two that do not, and any
future explanation must account for identical code behaving differently.

**S89d-2 — data placement raised and refuted the same session.** The only
non-kernel difference between the images is where DM lands, so the TX ring and
its pointers were checked for a memory-block crossing. `c2_tx_buf_ping` sits at
`0x2D3200` on the folding arm and `0x2D2AE0` on the `SIMD_DYN=0` arm — same
region, 0x720 words apart — while it is the *clean* `DYN_LUT=0` arm that
relocates wholesale to `0x2C9D80`. Block membership does not track the fault.
Recorded so it is not raised again.

**Where that leaves it.** Refuted so far: a different ring-half index/pointer
computation (S89d-1), over-budget blocks (S89c), a nonlinearity (S89c, no energy
at 3/6/9 kHz), corruption upstream of the DMA (S89c, slot clean to −110 dBc over
1024 contiguous samples), a shared cause with S89-1 (S89c), and data placement
(S89d-2). Open: a write-side half handoff that is timing-dependent, and a
read-side per-channel DDE skew. Both need `tx_probe` and therefore the flash. A
physical scope is still NOT the next step.

## S89d (executed) — ROOT CAUSE: the core overwrites the last frame of each TX buffer half while it is still being shifted out

PW authorised the flash round trip; it was run and it closed the root cause.
**No scope is needed.**

**The bitstream had to be built, not reused.** All three `maincap` bitstreams in
`bitstream/` carry a different `slot_map` from what is on the part (`4ecc4aa2…`,
`2c53de21…` vs shipping `c4a3ca82…`); flashing one would have mis-framed the
lanes and produced scrambled stamps for a reason unrelated to the DMA — a false
positive, and memory item 16's trap exactly. The shipping RTL was rebuilt as a
control (reproduces `d02d83b3cc22` with a byte-identical POF) and then rebuilt
with `PI_MAINCAP=1` and nothing else: `dsp4_logic_maincap.58ae3dfe6e25`,
design_id `3dfe6e25`, cfg_bits `0x0004`, **slot_map identical to shipping**, sim
gate PASS. Flashed FLASH-OK attempt 1; the part answered `3dfe6e25 pi_maincap`.

**The measurement**, `DSP4_TXPROBE=1`, one second of capture per arm:

| arm | sample idx out of sequence | block counter wrong |
|---|--:|--:|
| `SIMD_DYN=1 + DYN_LUT=1` | 0.0000 % | **12.5006 %** |
| `SIMD_DYN=0` | 0.0000 % | 0.0000 % |
| `DYN_LUT=0` | 0.0000 % | 0.0000 % |

12.5006 % of transitions is **one frame per 16-sample block**, and S89c's
spectral fit predicted ~2 of 16 from the analog side alone — two independent
methods on the same number. The sample index is never wrong and ping/pong
alternates correctly, so the DMA addressing and `_blk_latch_bufs` are both fine.
Exactly one frame is wrong: **index 15, the last frame of the half**, carrying a
stamp **+2 blocks** ahead of its neighbours (`… 1089/14, 1091/15, 1090/0 …`).

**Mechanism.** Two blocks is one full ping-pong cycle, i.e. the same half. The
word that went out on frame 15 is the one the core wrote for the *next* pass over
that half — **the core had already overwritten it**. The core is EARLY, not the
DDE late: the stamp is +2 (future content), not −2 (stale). The DMA's
half-completion interrupt fires when the last word reaches the SPORT, not when it
has been serialised, and the SPORT's transmit FIFO is that gap. `SIMD_DYN +
DYN_LUT` is the fastest configuration in the tree (paired table lookup 54.1
cycles/sample-pair vs the polynomial's 215.2), so it is the only one whose gather
reaches frame 15 inside the drain window — which is why S89c measured the folding
arm as the *lightest* (chip 2 78.81 % vs 86.84 %/93.07 %). S89c's open tension
("`_blk_latch_bufs` is gated by `_block_ready` once per ISR") is resolved: it
does not run twice, it runs once and then writes too quickly.

**Fix, recommended and NOT applied**: (1) gate the gather's final frame on the
SPORT transmit FIFO draining (`SPORT_CTL.DXS` — the field whose bit-30
difference S89c saw and set aside); (2) write frame 15 first (narrows, does not
close); (3) triple-buffer the chip-2 TX region (closes it outright, costs a block
of DM and a block of latency). Recommend (1), fallback (3). Needs verifying on
silicon against `tools/pi/dsp4_loop_thd.sh`. **Free falsifiable prediction:
slowing the folding arm should cure the fold without touching either switch.**

**S89c refinement**: the spectral fit said ~2 samples, the stamp says one frame.
Both hold — `_tx_probe_stamp` writes slot 1 after `_gather_chip2` writes slot 0
for the same frame, so the audio word is exposed slightly longer, and the
reconstruction filter smears a one-sample defect across about two. The stamp
count supersedes the spectral estimate.

**Instrument bug found and fixed**: `dsp4_boot_linked.sh` called FOLDED six times
during the restore when the real fault was GPIO27 coming back from the Pi reboot
as `ip pd` (the CS_M/U2 defect, which presents as "cannot phase the parameter
link"). `s89_signbit.py` let any exception exit 1, which the wrapper read as
FOLDED. It now exits 2 — *a link that will not answer is not a folded link* — and
prints `sudo pinctrl set 27 ip pu`.

## S89e — THE FOLD IS FIXED: the gather's position in the block period was a function of the graph's speed, and is now a constant

Hub dispatch `tasks.md` 2026-09-22 14:03Z. Report:
`MW/D24/DSP/s89/dac-fold-fix.md`.

**S89e-1 🟢 ROOT CAUSE, RESTATED AND MEASURED: neither signed audio switch is
wrong.** The chip-2 transmit ring is a two-row 2D autobuffer; the DDE reads one
row while the core fills the other and `DSP4_TX_EARLY` picks which. The block
gather ran at the END of the block period, so the instant the core wrote the row
was `interrupt + whatever the graph cost` — **which row is safe was a function
of the load, and no file said so.** S9-2 measured the safe row at the
2026-09-09 load and adopted `DSP4_TX_EARLY=2`; S82 then signed `DSP4_SIMD_DYN`
+ `DSP4_DYN_LUT`, chip 2 went from about 93 % of budget to 78.81 %, and the
gather moved roughly 14 % of a period earlier — across the boundary. That is
S88-1's DAC fold. This supersedes S89d's "SPORT transmit FIFO drain" framing:
the drain window is not the mechanism (see S89e-3), the gather's *position* is.

**S89e-2 🟢 GATE 1 HELD, AND THE CURE THRESHOLD IS THE CLEAN ARMS' OWN
POSITION.** `DSP4_GDELAY` burns N cycles on chip 2 before the gather, touching
no switch; `chip1.ldr` is byte-identical across every delay arm. Budget 327,680
cycles/block. 0 → 57.40 % loop THD; 6,000 → 41.28 %; 13,000 → 41.34 %;
20,000 → 57.34 %; **26,000 → 0.3213 %**; 47,000 → 0.3217 %. The threshold is
between 20,000 and 26,000 cycles, i.e. the gather crossing back through about
85 % of the period — and S89c independently put the two clean switch-arms at
**86.84 %** and **93.07 %** against the folding arm's **78.81 %**. Two methods,
one number.

**S89e-3 🔴 THE DISPATCH'S OPTION (1) CANNOT BE MADE TO HOLD, AND NOT BECAUSE
THE POLL IS EXPENSIVE.** S89d recommended gating the gather's final frame on
`SPORT_CTL.DXS` draining. Chip 2's SPORT transmits continuously at 48 kHz, so
its transmit FIFO is **never empty while audio is flowing**: a poll for
"drained" either never returns or returns a status that says nothing about the
row the core is about to write. The fallback the dispatch named (triple
buffering) was not needed either — see S89e-4.

**S89e-4 🟢 THE FIX IS `DSP4_TX_DEFER`, AND IT COSTS NOTHING.** The gather moves
to a FIXED point in the block period: `src/main.asm`, immediately after the
block interrupt and BEFORE `_blk_latch_bufs` advances the row, so
`_tx_active_buf` still names the row the previous block was gathered for and the
node output slots still hold that block's samples. The same 24 outputs × 16
samples, the same instructions, moved — no staging buffer, no copy, no third
row, no change to the DMA topology, and no added output latency (the contract
figure of 82 samples / 1.708 ms is unmoved). Per-chip mask like
`DSP4_TX_EARLY`; **2 = chip 2 only**. Measured on the part over three gated
boots: **0.3212…0.3213 %** at −12 dBFS drive against the unfixed build's
**57.33…57.43 %**, same cable, same route, return level agreeing to 0.01 dB.

**S89e-5 🟢 LOAD-INDEPENDENCE IS THE THING THAT WAS PROVED, NOT MARGIN.** The
unfixed build is clean at some graph speeds and folds at others; the fixed build
was measured at three — the signed graph and the same graph slowed by 26,000 and
47,000 cycles (78.8 %, 86.7 %, 93.1 % of budget) — and is clean at all three.
The complementary control is the other half of the proof: with the gather
deferred, `DSP4_TX_EARLY=0` **folds again** (57.43 %) while `=2` is clean, so
this is a geometry and not a margin. Which is exactly why **`DSP4_TX_EARLY=0`
is not the fix** even though it measures clean today (0.3215 %): it is the same
load-dependent coin landing the other way up.

**S89e-6 🟢 THE CYCLE WINDOW HAD TO MOVE WITH THE GATHER, AND SAYING SO IS THE
POINT.** `_proc_cyc` is taken between `_proc_t0` and the close after the node
graph; the deferred gather runs before that point. Left alone, the measurement
would have dropped the whole gather — about 6,000 cycles, 1.8 % of budget — out
of the window while the part still paid for it, and **the fixed build would
have read cheaper than the folding one for no reason but where a timestamp
sits.** On a deferred build the window now opens before the gather; a build
without the switch keeps the original placement byte for byte, so every number
already on record stays comparable.

**S89e-7 🟢 THE TRIPLE MOVES IN THE THIRD WORD ONLY**: `DIAG_BUILD_CFG3`
`0xC47C0F26` → **`0xC47C0FA6`**, bits 7..6 = `DSP4_TX_DEFER`. CFG and CFG2 are
unchanged. The control (`DSP4_TX_DEFER=0`) rebuilds the S82 signed pair BYTE FOR
BYTE (`e3e25a79…` / `41a6b913…`), and the fix's **chip 1 image differs from it
in exactly ONE BYTE**, which is chip 1's own CFG3 stamp — so the deferred-gather
code is provably inert when the switch is off and chip 1's code does not move.

**S89e-8 🔴 A PINNED LANE READS A PLAUSIBLE THD, AND IT NEARLY COST THIS
SESSION ITS FIRST THREE ARMS.** With the 595 preamp chain wherever `matrix-app`
had left it, the loop returned **−0.7 dBFS at every drive from −12 to −42
dBFS** — 30 dB of stimulus moving the reading 0.9 dB — and a *clean* build then
read **39 %** THD while the folding build read 58 %. Both numbers are
meaningless. The chain was written to gain code 0 (all-zero 25-byte image,
VERIFIED 200/200) and every figure in the S89e record is from after that.
`tools/pi/dsp4_loop_thd.sh` now enforces a return-level window and calls a
reading outside it INCONCLUSIVE, never a pass. Nothing in the S89 record said
the chain state was part of the instrument; it is.

**S89e-9 🟢 THE ACCEPTANCE LEG HAS A VERDICT NOW.**
`tools/pi/dsp4_loop_thd.sh` is rewritten from a printer into a leg whose EXIT
CODE is the gate (0 PASS / 1 FAIL / 2 INCONCLUSIVE), with the loop lane as
`OSC_STRIP`/`MEAS_STRIP` rather than hard-coded; `MW/D32/DSP/SHARC/loopthd.sh`
builds and stages any named configuration for it the way `capacity.sh` does for
a capacity row. `T3L` is in `tools/accept/battery.csv` with three limits in
`tools/accept/limits.csv`, and `docs/acceptance-audio-layer.md` carries the
measured references. The limit (1 %) is the loop's own floor plus margin — six
independent clean arms read 0.321…0.360 % and the defect reads 57.3…59.7 % —
and is **not** a product audio specification.

**S89e-10 🔴 THE LOOP'S 0.32 % FLOOR IS ANALOG, SO GATE 2's "THD ≤ 0.01 %" BAR
IS BELOW THE INSTRUMENT ON THIS PATH.** Six arms built from different switch
positions read 0.3212…0.3217 % at −12 dBFS drive and S89's all-off control read
0.360 % on the same cable; the fixed build is indistinguishable from all of
them. At −22 dBFS drive the same arms read 0.019…0.039 %. The bar as written
cannot be met by a DAC → cable → preamp → ADC loop whatever the firmware does,
and a limit that no passing build can reach is not a gate. `T3L`'s 1 % is what
was landed instead, with the separation stated.

**S89e-11 🔴 A ROUTE THAT WAS NEVER ASSERTED READS AS A PASS, AND THE NEW LEG'S
OWN FIRST RUN PROVED IT.** `MW/D32/DSP/SHARC/loopthd.sh` staged every tool the
leg needs except `s89_set.py`, which lives in this repo and **not** in
`/home/app/dspboot` — so the stage directory's `ln -sfn /home/app/dspboot/*.py`
loop never picked it up (S83-2's trap, one file along) — and the leg wrote its
route with stderr discarded. It measured the DEFAULT configuration, in which the
donor strip's compressor is ON with a threshold near −22 dBFS (S70-3): the
return read −29.61 dBFS, 10 dB of drive moved it 4.9 dB, and the leg reported
**PASS at 0.238 %**. Fixed in both halves: `loopthd.sh` stages `s89_set.py`, and
the leg now checks the route write's exit status AND **requires the return to
track the drive within 2 dB**. That tracking check also catches S89e-8's pinned
chain, which the level window alone did not. Both directions are now proved on
the part: `ARM=s89e ./loopthd.sh` → 0.3216 %, exit 0; `ARM=ctl
DSP4_TX_DEFER=0 ./loopthd.sh` → 57.4803 %, exit 1, same cable, same levels.

**S89e-12 🔴 FOR PW — THE DRIVEN ROW COULD NOT BE TAKEN, AND IT IS THIS
DISPATCH'S OWN BENCH RULE THAT FORBIDS IT.** Gate 3 asks for the driven row
re-priced against the 84.47 % bar; `capacity.sh --driven` needs the `driveall`
LOGIC bitstream on the part, and the dispatch says no CPLD flash. This is
S89b-Q1 unanswered. What was taken is the **silent row, both products, both
chips, two boots each, zero missed blocks in all sixteen chip-rows**: D24 chip 2
77.51 % → 77.51 % (Δ 0.00), D32 chip 2 92.57 % → 92.70 % (Δ +0.13), worst-block
deltas +0.13 and +0.16. Chip 1 is the null arm — its code is byte-identical
between the builds — and its four deltas swing −0.16…+0.10, so the fix is inside
the resolution of the instrument measuring it. The fix adds no instructions and
does not touch the node graph, so the silent delta bounds the driven one; that
is an argument, not a measurement, and the driven row is owed.

**S90-1 🔴 TWO OF THE SELF-TEST SPEC'S FIRMWARE PREREQUISITES MUST NOT BE
BUILT, AND SAYING SO IS THE FINDING.** `docs/spec-d24-selftest.md` asks H1S1 for
a chip-select test command (DC1/DC2) and an `!RST_D` pulse (DR1). H1S1's own
source refuses both: `~/build-h1s1/Core/Src/main.c:362-381` configures **all
eight CS pins as `GPIO_MODE_INPUT`** under *"ALL EIGHT CS pins (CS1-CS8) are
OWNED BY THE CM4 — this MCU must never drive them"*, which is DSP4 architecture
decision D1 written into the firmware, and `RST_D_Pin` is undefined, PA13 absent
from the `.ioc`, and the only two references in `main.c:124-126` commented out.
`!RST_D` has **six places on one net, no series resistor and no arbitration**
(`hardware-map.md:305-324`), so the spec's command would put a second push-pull
driver on an unisolated reset net. **Neither test needed firmware**: DC1, DC2 and
DR1 all ran from the CM4 (CS1 = GPIO6, CS2 = GPIO24, `!RST_D` = GPIO16) and
passed. Proposals S90-P3/P4 are to withdraw both prerequisites, not to land them.

**S90-2 SIX OF THE EIGHT CHIP-SELECT ROWS HAVE NO POSSIBLE SUBJECT ON DSP4.**
`hardware-map.md:410-411`: only CS1/CS2 are live; **CS3/CS4 are wired to
DSPA/DSPB SPI_RDY and are INPUTS**; CS5–CS8 are 8-DSP scaling provision with no
fitted part. Workbook rows 105-110 can therefore never answer, whatever firmware
lands — they are not NO DATA waiting on a prerequisite but rows that belong in a
different class. Related: `fw.csv` `Dsp1..Dsp8` declare a pin and a net, **not a
part number**, so DC2's "id matches the declared part" has nothing to match; what
CS1/CS2 prove is CHIP_ID, BUILD_ID and the signed triple
`0xCF45FF10/0xE2018E6F/0xC47C0F26`, which is what was recorded.

**S90-3 THE PANEL MCUs ARE PEERS ON MH1's BUS, NOT BEHIND AN H1S1 UART MUX — AND
ENUMERATION WAS ALREADY FREE.** H1S3 (SW_RIGHT) and H1S4 (SW_LEFT) are peer MCUs
on the matrix bus (`defs/products/d24/fw.csv:26,66`), each with its own
`testMessage[]`; `S_TEST` makes all three answer, and `matrix-app` has been
logging `MCU verified: // H1S1 DSP` / `// H1S3 SW Right` / `// H1S4 SW Left` on
every boot all along. ML-P1/ML-P2 pass today with no firmware change. Only the
VERSION is missing, from all three, and the cheapest fix is to extend the string
already being transmitted (S90-P2) rather than add cells.

**S90-4 🔴 `matrix-app`'s `H1S1.shex` md5 IS STALE BY CONSTRUCTION AND WOULD MAKE
A VERSION CELL WORSE THAN USELESS.** The app logs
`779c5665f9992fbf814eeed2043d9280 95552B firmware/H1S1.shex` from
`deploy-manifest.txt` (`generatedUtc=2026-08-18`); the file on the unit is
**`5dc7acdea662f9153b09b816f9ae76b2`, 100216 B, dated 2026-09-20** — the S81
pack, flashed by hand through `app cli loadfw H1S1`. The manifest is a
deploy-time record and does not track hand-flashed firmware, so ML2's
"equals the version in H1S1.shex's manifest" compares a live value against one
that has been wrong for two days and will stay wrong. Landing a version cell
(S90-P1) without also writing that literal into the shex pack leaves the test
worse off than no test.

**S90-5 THE UNIT DROPS ~1 % OF A 5 Hz PING AND IT IS `matrix-app`, NOT THE
ETHERNET.** NW3 fails, and two controls name the cause. *Target*: loss appears
toward the unit's own default gateway one switch hop away as well as toward the
bench host — worst-of-3 **1.5 %** and **1.0 %** — so it is not the driving host's
path. *Load*: with `matrix-app` **stopped, 6 of 6 passes read 0.0 % loss** (three
per target) and the max RTT to the bench host falls 0.703 → 0.624 ms; load
average goes ~1.0 → 0.04 on a four-core CM4. Everything else about the link is
clean — `1000Mb/s Full`, zero interface error counters, 94 Mbit/s each way, which
is line rate for the 100 Mb/s path it was measured over. The row is landed FAIL
because the criterion is about the unit as it ships, but it should be read as
"the CM4 drops ICMP under matrix-app's load", not as a cabling fault.

**S90-6 A ONE-SHOT 200-PACKET PING DOES NOT SETTLE A 0 % BAR, AND THE INSTRUMENT
HAD TO LEARN IT.** Five consecutive one-shot NW3 passes on the same path read
**2.0 %, 0.5 %, 0.0 %, 0.0 %, 0.5 %**. Whichever verdict a single run lands is
the one the scheduler handed it, and re-running until it passes is not a
measurement. NW3 now takes three passes per target and scores the WORST, which
makes the reading reproducible in the only sense that counts: it does not improve
if you run it again. The same restraint was applied to NW2, whose FAIL
(`rx_dropped` +2 across the test window, 0 in the idle control) was **not**
re-taken for a better number.

**S90-7 U15's LANES ARE ALIVE; IT IS THE FRONT END THAT IS ABSENT.** AS-ADC's
per-converter grouping puts numbers on S86's conclusion: **all eight of U15's
lanes carry a real dithered floor at −117.7…−115.0 dBFS, the same as U39's
(−119.2…−114.6) and U60's (−119.5…−113.8)**. The converter converts; what
MW-D24-2 has not got is the front end for panel mics 1-4 and 13-16 (XLRs J15-J22,
preamps U17-U31). A lane test cannot see a missing preamp and should not be asked
to. Lane 3's eight entries read STATIC `0xFFFFFFFF` and that is the product, not
a fault: input strips 25-32 have no analog source on a D24 at all.

**S90-8 THREE SECTION-1 ROWS CANNOT REACH PASS UNATTENDED AND THE SPEC SHOULD
SAY WHICH.** AS-ADC, MM1 and AS-DAC each depend on something the unit's as-found
state does not have: the analog rails (AN_EN is CM4 GPIO26, `lo`, and **a
dispatched session may not raise it** — bench note 19 / S49-15), and a stimulus
(TEST_OSC exists only under `DSP4_TEST_NODES=1`; the pair under test is the
shipping pair). AS-CPLD adds a third: `dsp4_logic_id.py` needs the DUPLEX PCM
overlay and answers "no reply" for every bitstream under `dsp4-pcm-slave`, which
is what this unit's `config.txt` selects — so its silence carries no information
and flipping it needs a reboot. All four are landed NO DATA naming the
prerequisite; none was softened into a FAIL, because a converter marked FAIL for
having its rails down is a defect invented by the harness.

**S90-10 A 60-SAMPLE SOAK AT 60 s SPANS 3540 s, NOT 3600.** HD0-2's first
harvest reported itself 60 s short of the spec's hour — correct behaviour from
incorrect code, and the useful half is that it said so rather than rounding a
3540 s window up into "a soak". Two fixes: the sampler takes one extra sample so
the span is the window that was asked for, and the duration is read off the log's
own timestamps instead of being multiplied out of a sample count, which assumes
every sleep landed. The re-take is the landed row — **61 of 61 samples
`connected` over a full 3600 s, DRM hotplug count unmoved** — and it supersedes
the short one by stamp, which is the first live exercise of the results
contract's newest-wins rule. Both readings are kept in the CSV.

**S90-9 TWO RUNNER DEFECTS FOUND BY READING THE ARTIFACT, NOT THE SUMMARY.**
(a) `s89_signbit.py` takes the symbol directory as `argv[1]`; called bare it
raised `IndexError` before reading the part, so the **inter-chip link gate scored
nothing while appearing to run** — the first section-C pass was therefore taken
through an unverified boot (~1 in 7 fold silently, S89-1). Fixed, and every
landed section-C row was re-taken on a boot gated **CLEAN on both lanes**.
(b) `pkill -f "iperf3 -s"` matched the shell running that very command, so NW4's
launcher killed itself before launching anything and the test read as a network
failure; it is `pkill -x iperf3` now.
