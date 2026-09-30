provenance: AI-drafted 2026-09-30 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S157 — the patch station's detector, redesigned (written before the code)

## What went wrong, in one sentence

Arrival, removal and "already carrying" were all inferred from the strip
PEAK-HOLD meter, a latch that drains at 6.5 dB/s. So whether a correct patch
passed depended on how fast the operator moved, and on what the previous
patch had left in the latch. The log table (`factory-log-table.md`) shows
every face of it. P1 on an idle MIC 1: peak against an RMS floor. P6: an
other-end swap faster than the ~1.9 s drain. P56: an empty socket still
draining from the gain-63 step. Around those sat a runner that moved on by
itself: the find-a-loop walk, the auto re-prompt, NO DATA after
`MAX_RETRIES`, and the re-park.

## The rules (PW 2026-09-30, S155 addenda, S157 block)

1. The instrument for a tone row is the MEASUREMENT NODE. The peak meter is
   a hint and never decides anything.
2. Every patch is one lead, plugged fresh at both ends. Arrival is always a
   fresh arrival. There is no parked end, no "move the other end", no
   removal edge on a tone row, and no `swap_for_plug`, `check_parks`,
   `unpark` or `reparked`.
3. Every threshold is relative to that lane's own idle floor. None is
   absolute.
4. The outcome must not depend on operator speed: a 1 s plug and a 10 s
   plug both pass.
5. The runner never moves past a fail without the operator. It stops on
   the step, names the failure, and waits for NO SIGNAL (record it and move
   on), RETRY (run it again from the prompt) or PAUSE. There is no
   auto-repark, no auto re-prompt and no auto NO DATA. Auto-advance happens
   only on the PASS path.

## Instruments

| what | instrument | reference | cost |
|---|---|---|---|
| tone arrival (every tone row, every lane) | node, one window, **coherent level** `coh_dbfs` (the fit against the oscillator the verdict uses) | the lane's idle node RMS floor (`measure_floors`, oscillator off) | one 85 ms window per poll |
| terminator arrival (noise rows) | node RMS plateaus (S153, unchanged) | the plateaus since the prompt | one window per poll |
| wrong socket / isolation | peak sweep, **hint only** | each lane's own peak floor + `detect_rise_db` | 32 ms per sweep |

Why coherent and not RMS. The coherent level counts only energy at the
oscillator's frequency and phase. An open input at gain 63 (−54 dBFS RMS)
has a coherent level about 30 dB lower, and an idle lane's coherent reading
sits below its own RMS floor. So "coherent ≥ floor + rise" means the tone is
on this lane NOW. Noise cannot pass it, whatever residual or decay the lane
carries, and the node has no memory to decay. The floor is RMS on purpose.
It is the ceiling of what an idle lane's coherent reading can be, so the
test is conservative.

Why the peak meter can stay as a hint. A lane that is really carrying a
tone reads flat on a peak-hold meter; a latch that is draining falls
6.5 dB/s. A hint becomes a claim ("Signal on MIC 7, expected MIC 5") only
if all three hold:

- the lane is at least `rise` over its own PEAK floor,
- it is the same lane on two sweeps `WRONG_INPUT_POLL_S` (1 s) apart,
- the two readings agree within `DETECT_STEADY_DB` (1 dB).

A draining latch loses 6.5 dB in that second and can never be claimed.
That is what the P1 "MIC 15" and P7 "MIC 23" claims were.

## The step, as a state machine (one log line at every transition)

Every transition logs `P<n> <STATE>: <in> level <x> floor <f> (<instrument>)
<why>`.

```
PROMPTED ──read──▶ WAITING ──coh ≥ floor+rise──▶ ARRIVING ──3 blocks, ≥2 readings, spread ≤1 dB──▶ ARRIVED ─▶ measure ─▶ PASS: next prompt (auto)
                     │  ▲                          │                                                    │
                     │  └────── fell back ─────────┘                                                    └▶ graded FAIL ─▶ FAILED
                     ├─ steady hint elsewhere (2 sweeps) ─▶ WRONG_SOCKET (red, keeps listening; clears when the hint goes)
                     └─ detect_timeout_s ─▶ FAILED (red, keeps listening: a lead pushed home still ARRIVES)
FAILED ── nosignal (LEADS CORRECT) ─▶ RECORDED (FAIL, "no signal detected" / the graded reason) ─▶ next prompt
       ── retry ─▶ PROMPTED (same patch, re-prepared, re-announced)
       ── pause ─▶ PAUSED
       ── (graded FAIL only) the lead comes OUT (coh < floor+rise, steady) ─▶ PROMPTED   ← retry by hand, no button needed
```

- There is no hard bound. A station left alone waits on its failed step
  with the heartbeat going. That is the ruling: nothing advances by
  itself.
- A NO SIGNAL press while a steady hint shows the tone on another socket is
  refused. The screen names the socket, exactly as before. A wrong patch is
  still never a fail.
- The 150 Ω step's first plateau is the prompt's own settled node reading.
  It is not a stability window, because that made a fast pull unpassable.
  The input must be open for about 0.35 s between the lead coming out and
  the plug going in.
- The removal edge exists in exactly one place: a same-socket, same-route
  repeat. That is the 150 Ω step (lead out → open → plug in, read as node
  RMS plateaus) and the hand retry of a graded fail. Both are on the node,
  so neither depends on speed. On the node, a 1 s unplug is 12 windows.

## The find-a-loop step (P1)

P1 is an ordinary prompt: "Patch AUX 1 to MIC 1". If it fails, it stops
like any other step. The next candidate socket is offered only after the
operator has recorded NO SIGNAL on that one. It never happens by itself.
A candidate the operator confirms dead is logged and listed with the
confirmations, not recorded as a row. The inputs walk still visits it (MIC
1–24 in order, no exceptions) and grades it there, with its own
confirmation. There is no `walked_past` skip.

## RUN ALL, every station

| station | failed step | what it does now |
|---|---|---|
| analog patch | timeout, wrong socket, graded FAIL, graded NO DATA | FAILED screen as above |
| switch panels (and the encoder turn) | no key code in `--panel-timeout`, wrong key, wrong board, no ack | the glass goes red and names it. YES records the fail and moves on, NO lights it again and asks for the press again, PAUSE pauses. NOT LIT is already the operator's own confirmation and is unchanged |
| panel sense rows | NO DATA because the panel firmware does not send the cell | a declared fixture gap: one line on the glass in panel words, for `NODATA_SAY_S`, and no stop |
| setup pages | nothing fails; every page is ENTER-confirmed | unchanged |
| background auto sets | no operator step | listed in the end-of-run report, as before |

## Buttons, and what the deployed app draws

The deployed app is mx26 `1f2a7db` (hub, 2026-09-30 19:55; on the unit
`app` md5 `409e52aa`, backup `app.bak-pre-retry-1f2a7db`, `d24-testui`
active). `FactoryView` draws ENTER, YES + NO, LEADS CORRECT (`nosignal`),
START, EXIT and PAUSE. Since `1f2a7db` it also draws **RETRY in the NO
slot** whenever the runner offers `retry` without yes/no, and a press sends
`command: retry`.

- The patch FAILED screen offers `['nosignal', 'retry', 'pause']`, and all
  three are drawn: LEADS CORRECT, RETRY and PAUSE. RETRY runs the step again
  from the prompt. Re-making the patch by hand still works as a retry too:
  push the lead home on a timeout, or pull it and plug it again after a
  graded fail. The station watches for both.
- The panel FAILED screen offers `['yes', 'no', 'pause']`. YES records the
  fail and moves on, NO lights the button again and asks for the press
  again, PAUSE pauses. YES/NO is kept there because it reads as an answer to
  the question on that screen, and the app has drawn it since `d2b745e`.
