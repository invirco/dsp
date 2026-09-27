# S130 item 3 — the PSU rail monitor was NOT built, and here is why

Item 3 asked for an automatic check reading `fw.csv` `Psu1`-`Psu12` (12
channels) through "the existing power-MCU/H1S1 path", graded INFORMATIONAL,
read-only.

**There is no such path on this unit, and building one would contradict a
dated, explicit ruling already in `defs`.** `defs/products/d24/fw.csv`,
every one of the twelve `Psu1`..`Psu12` rows, carries this comment verbatim:

> PSU-monitor ADC channel - WHICH RAIL it measures is not declared anywhere;
> PAD0-11 are N/C on the Digital board on rev C so there is no PSU monitor
> path (PW 2026-09-22: do not test them; do not infer rails from them)

That is current at HEAD (`defs-v2026.09.27.3`, the pin this repo is on) —
not stale. Cross-checked against `MW/D24/HW/hardware-map.md` §3a: PAD0-11
("PSU ADC monitoring... per-8-channel-bank analog PSU reads") belongs to the
**rev-D DSP4 card's S MCU (U7)**, a board and a revision that do not exist on
the bench unit (MW-D24-2 is a rev-C Digital board). The pads are pinned out
in that MCU's silicon but nothing on rev C's fab wires a rail to them — they
are floating inputs, not PSU rails, on the part this dispatch is for.

Confirmed independently: no tool in this repo or on the bench (`tools/pi/`,
`d24_selftest.py`, `d24_live.py`) reads a PAD/ADC housekeeping channel at
all today. There is no existing "power-MCU/H1S1 path" to reuse — item 3's
own premise ("read each rail through the existing... path") does not hold.

**What building it anyway would have produced:** twelve channels of floating
ADC noise, reported as if they were rail voltages, on a station whose whole
design principle (`CLAUDE.md`, the no-fallback rule) is that an unmeasurable
or undeclared thing fails loudly rather than being reported as a number.
Even INFORMATIONAL grading would put twelve meaningless readings in every
report from tonight on, which is worse than no row at all — a future reader
has no way to tell them from a real (if unruled) measurement.

**Not built.** No `short`/`declared_status` change to test-catalog.csv either
(there is no existing PSU row to touch; nothing here proposes adding one).

**For the hub / PW:** if a PSU monitor is wanted for this line, it needs one
of two things first, neither of which is this session's to decide:
1. a rev-D board (or a rev-C rework) that actually wires PAD0-11 to rails, or
2. a different, already-wired measurement path PW can point at (the M MCU
   "Board manager: PSU monitor" role in the hardware-map summary table is a
   description of intended function, not a proven wired path on this unit —
   worth PW confirming whether U8 has ANY working rail-sense input on rev C
   before the next dispatch asks for this again).

Until one of those lands, the honest state of §1.1 in the gaps doc is "no
rail-sense hardware on this unit", not "not built yet".
