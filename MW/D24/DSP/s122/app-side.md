provenance: AI-drafted 2026-09-26 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S122 — the app side of the panel haptic, for the hub

What the console app has to do to make the screen click, stated so the hub can
dispatch it without reading the DSP report. Nothing here is built by S122; the
DSP side is.

## 1. The one sentence

**A touch event writes one word to the DSP and that is the whole feature.**
There is no audio file, no mixer routing, no level to set up and nothing to
turn off afterwards: the DSP holds the clicks, plays one when it is asked, and
writes digital zero the rest of the time.

## 2. The write

Today, by address (the cell family is proposed and not landed —
`proposals/CONTRACT-PROPOSAL-S122.md`):

| what | chip | SPI address | value |
|---|---|---|---|
| play one shot | 2 | 2175 (`0x087F`) | `1` |
| which click (1–3) | 2 | 2176 (`0x0880`) | `1`, `2` or `3` |
| click level | 2 | 2177 (`0x0881`) | IEEE-754 float, `1.0` = as stored |
| busy (read-back) | 2 | 2180 (`0x0884`) | `1` while playing |

After PW rules the names these become ordinary cell writes
(`Hpt001Trig001=1`) and the app should use those, not the addresses.

**Ramp 0 on every one of them.** The words are InstantCtl and have no ramp
companions; a ramped write walks the three words above the one addressed. The
app's existing parameter-write path takes a ramp argument — it must pass 0
here.

**Fire and forget.** The DSP clears `Trig` itself on the block it consumes it,
so the app never writes 0 back and never polls. A second trigger during a click
restarts the click; it does not layer.

## 3. Where it hooks in

On the **press** (touch-down), not on the release and not on the widget's
action handler: the click is feedback for the finger, so it wants to be the
first thing that happens, ahead of whatever the button does. If the app also
wants a release tick, `Sample` 2 is the 3 kHz release click PW auditioned.

One write is about 1 ms on the parameter link. That is inside a touch frame, so
it can be done inline on the UI thread; if the app's link is serialised behind
a queue that can be deep (a config commit, a scene recall), the click should go
down a path that does not queue behind it, or it will arrive late enough to
read as a fault rather than as feedback.

## 4. What the app must NOT do any more

- **Do not touch `Mon001Level001/002` to make the speaker work.** They no
  longer reach it. The monitor bus reaches no converter output on a D24 at all
  (see the report §3 — it is part of the open PW question about the rear
  Monitor jacks, the Centre/LF XLR and the headphone jack).
- **Do not route anything to the speaker.** A build that routes a mixer node
  to the speaker slot now fails with a named error, so an attempt will be
  caught, but nothing in the app should try.

## 5. Settings the app will eventually want

Not built, not proposed as cells beyond §2, listed so the hub can decide
whether they are app-local or contract:

- **Haptics on/off** and **volume** in the user settings — almost certainly
  app-local state that scales the `Level` word it writes, not a second DSP
  word.
- **Which click for which control.** Three are stored; the app picks per
  widget. Again app-local unless PW wants it in a show file.

## 6. The self-test's claim on the same node

`AL1` (the acoustic loop, row 56/57 of the catalog) drives `TestOn` /
`TestLevel` — the steady 1 kHz tone — and turns them off again with a read-back.
It runs only under `d24-testui`, where the app is not running, so the two can
never collide. Nothing in the app should ever write those two words.

## 7. The drum-sample engine this shares its shape with

The haptic node is a stored-sample player with a trigger, a select and a level.
A drum-replacement engine is the same three controls over a bigger table, a
pitch/rate and a mix into a bus instead of a single slot. Two things generalise
cleanly and one does not:

- **Generalises:** the trigger discipline (host writes 1, kernel consumes it on
  its own block, no handshake) and the table layout (one offset/length table
  plus one sample pool, so adding a sample is data and not code).
- **Does not:** this node writes ONE TDM slot directly and takes no input,
  because that is what makes the speaker's separation checkable in one hop. A
  drum engine has to sum into a bus like every other source, so it is a
  different node class that borrows the player, not this node grown up.
