provenance: AI-drafted 2026-09-27 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# The first full analog pass with a real lead — one page

MW-D24-2, `app@192.168.1.219`. Rewritten for S126: the kit is parked at START,
the pass is confirmed with ENTER, and it is started on the D24's own screen.
Takes about 10 minutes plus whatever the leads take. Nothing here changes the
unit's configuration permanently: the station shuts every route it opens and
silences the monitor bus on the way out.

**The seven gain steps have never been run through a real preamp.** Everything
about them is right on paper and proved against the part with no lead in
(S125); what has never happened is a tone arriving at a socket and each of the
six gain elements being switched in under it. That is the point of this pass,
and it is the reason to do MIC 7 carefully and slowly before letting the rest
of it run.

## What to have in hand

| | lead | where to get one | where it is parked |
|---|---|---|---|
| **K1** | XLR female → XLR male | any mic lead | far end on **AUX 1** |
| **K4** | XLR female → 6.35 mm TRS plug (pin 2 → tip, pin 3 → ring) | a standard balanced jack-to-XLR lead | XLR end on **AUX 2** |
| **K3** | XLR female → 3.5 mm TRS plug | a standard mini-jack-to-XLR lead | XLR end on **AUX 3** |
| **K2** | 6.35 mm TRS plug → XLR male (tip → pin 2, ring → pin 3) | the same lead the other way round — **it is a different lead**, the XLR gender is opposite | XLR end in the **second working input** |
| **K5** | 150 Ω terminator, male XLR, 150 Ω across pins 2–3 | the EIN plug from the 09-16 survey | on the bench, in reach |

You do not have to remember the table. The test walks you through it, one
socket per screen, before it asks for a single patch.

## Before you start

```
ssh app@192.168.1.219
sudo systemctl stop matrix-app          # if it is running
sudo systemctl start d24-testui         # the factory screen; they conflict
pinctrl set 27 op dh                    # CS_M driven, or the DSP link reads zeros
pinctrl set 7,8 op dh
```

Then let go of the keyboard. **Everything after this is on the D24's own
screen**, and START is the one thing to press.

## The pass

Press **START**.

1. **The bench setup, seven or eight pages.** One instruction each, `n of N` in
   the corner, ENTER to confirm. The network lead, the two USB sticks, then
   each kit lead onto the socket it hangs on. Where the unit can see the thing
   arrive — the network link, the two sticks — the page says so under the
   instruction. The parked leads it cannot see, and does not pretend to.

   The unit is checking its own panel and codec buses while you do this, so
   these pages are free.

2. **The panel loops.** The button that is lit is the button to press. The
   audio processors are being checked underneath; if the panel speaker sounds,
   the next button waits about a second before it lights, because the panel
   microphone can hear a click.

3. **The patch pass.** One patch per screen: plug it in, then press ENTER. The
   reading is already taken by the time your finger gets there — the tester
   starts it the moment the tone arrives and re-checks at ENTER that nothing
   moved, so the verdict is up almost at once. If the lead goes in the wrong
   socket it says which one and asks again; that is not a failure.

   The network checks run underneath this, so nothing waits for them.

4. **One report**, when both halves are done.

### What to watch on the first input

The first input the walk reaches takes **nine screens' worth of readings from
one lead**: the tone reference, then six gain elements one at a time, then the
terminator. The lead does not move for the first eight. **Leave it in until
the screen changes** — it says so.

This is the bit that has never run through a preamp. Worth watching:

* every one of the seven steps should land within **0.05 dB** of what the gain
  law says (S125 measured that on this unit's own preamps with no lead);
* a step that is wrong says so in a whole sentence, naming the input and the
  step;
* the whole input, all nine readings, should be about **1.6 s** of machine
  time.

If a step reads low on the first input and on no other, it is that input. If it
reads low on every input, stop and say so — that is the gain law or the drive
level, not the unit.

## The blocks, in the order you will meet them

| block | patches | what moves |
|---|---|---|
| the outputs | 10 | the input end stays in the reference input; the output end walks the ten XLR outputs. **AUX 2 and AUX 3 come last**, and each says "take the … off first" — that is the parked lead coming back into your hand |
| the inputs | 25 | the output end stays on AUX 1; the input end walks the mic inputs and the talkback, seven gain steps and a terminator at each. **The input the jack-to-XLR lead is parked in comes last** |
| the TRS outputs | 6 | the XLR end goes back into the input the walk has just proved; the TRS end walks Monitor L, Monitor R and the four Aux Out A jacks |
| the line inputs | 24 | the XLR end stays on AUX 2; the TRS end walks the combo jacks |
| the mini-jacks | 2 | the XLR end stays on AUX 3 |

At the end it prints the per-patch seconds and the projected pass. **The number
worth having is the real hand time**: the projection assumes 3 s or 5 s per
move, and whatever it actually turns out to be is what sizes the station.

## If you want it on the terminal instead

```
cd /home/app/selftest
python3 d24_patch.py --run --stdin --hand 5 --list-dir /home/app/selftest/quick
```

Same pass, same order, prompts on the terminal. Type `done` and Enter where the
screen would have said ENTER; `skip` or `pause` to leave one out or stop.

## Afterwards

The station shuts everything it opened. Worth confirming:

```
python3 /home/app/selftest/s89_set.py /home/app/loopthd/s122 \
    Test001OscOn001 Mon001Level001 Mon001Level002
```

All three should read zero. If the monitor levels are not zero the panel
speaker is live — the amplifier runs from the digital 5 V and stays on as long
as the unit is powered.

## What it will not do

Three rear sockets get no patch at all and say why: **Centre/LF** and the
**headphone jack** have no host-reachable source on a D24 (S121-5), and the
screen-link row is not an audio path. If PW wants those three proved, that is a
product decision about where their signal comes from, not a test to write.
