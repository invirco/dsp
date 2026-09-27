provenance: AI-drafted 2026-09-27 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# Bench card: which input order is faster?

**For PW, on MW-D24-2. Twenty minutes, a stopwatch, and six good inputs.**

Ruling (g) of 2026-09-27 left this to a stopwatch rather than to an estimate,
and the estimate is why: nobody has timed either order, and the model the
station carries cannot tell them apart. It charges the same seconds for a hand
move whether the hand travels to the next socket or swaps a lead in the socket
it is already at, so running both through the dry run gives the same number
twice. That is not a result. Six inputs with a stopwatch is.

Both orders are already generated. Nothing has to be built for this.

---

## What the two orders are

At each XLR input the test wants three things: the XLR lead in, for seven gain
steps; the 150 ohm plug in, for the input's own noise; and the jack lead in the
same socket's jack centre, for the line path.

* **Three walks** (today's order, and the default). The XLR lead walks every
  input, one after another. Then the plug walks every input. Then the jack lead
  walks every input. Three traverses of the input row, one lead in hand each
  time.
* **One stop per input.** At each input: the XLR lead and its seven gain steps,
  then the plug, then the jack lead — then move on to the next input. One
  traverse, three lead ends juggled at every socket.

The case for one stop: twenty-four traverse moves become in-place swaps, which
is worth 29 s to a trained worker and 48 s to a typical one **if** a swap is
about 60 % of a traverse. The case against: juggling three ends at one socket
could easily cost more than it saves, and only a hand knows.

---

## The six inputs

**MIC 7, 8, 9, 10, 11 and 12.** They are the first six of this unit's populated
inputs. MIC 1-6 and MIC 13-16 have no front end on this board, and MIC 5 and
MIC 6 are dead between the socket and the preamp (S125-6), so all ten are out.

---

## Setting up

The kit is parked first, as it now is at START of a real pass:

| lead | where it goes |
|---|---|
| the XLR lead | its far end hangs on **AUX 1** |
| the XLR-to-jack lead | its XLR end hangs on **AUX 2** |
| the 150 ohm plug | on the bench, in reach |

On the dsp machine, write the two lists:

```
cd ~/dsp
python3 tools/accept/gen_patch_paths.py \
    --exclude MIC1-6,MIC13-16,MIC17-24 --exclude-lead mini-jack \
    --input-order three-walks --out /tmp/order-a
python3 tools/accept/gen_patch_paths.py \
    --exclude MIC1-6,MIC13-16,MIC17-24 --exclude-lead mini-jack \
    --input-order one-stop --out /tmp/order-b
scp /tmp/order-a/patch-*.csv app@192.168.1.219:/home/app/selftest/order-a/
scp /tmp/order-b/patch-*.csv app@192.168.1.219:/home/app/selftest/order-b/
```

(make the two directories on the unit first: `ssh app@192.168.1.219 'mkdir -p
/home/app/selftest/order-a /home/app/selftest/order-b'`)

---

## The two runs

On the unit, one at a time:

```
cd /home/app/selftest
python3 d24_patch.py --run --list-dir /home/app/selftest/order-a
```

and then the same with `order-b`.

Start the stopwatch on the **first instruction** and stop it on the **last
verdict**. Do not stop it for anything in between: a pause to think about the
screen is part of what is being timed.

Run each order **twice**, and run them **A B B A** rather than A A B B, so that
getting better at the job does not land on whichever order went second.

---

## What to write down

| run | order | seconds | anything awkward |
|---|---|---|---|
| 1 | three walks | | |
| 2 | one stop | | |
| 3 | one stop | | |
| 4 | three walks | | |

The second column is the answer. The fourth is the one that matters if the two
numbers come out close: a fumble, a lead that would not seat, a socket that was
hard to reach past the one next to it, a moment of not knowing which lead was
meant. Write those down in the words they happened in.

**Six inputs is a quarter of a full unit**, so multiply the difference by four
for the per-unit figure. If the two are within about 10 s over six inputs, the
difference over a whole unit is inside the noise of one worker having a better
morning than another, and the answer is to keep today's order — it is the one
the bench already knows.

---

## Then

Send the four numbers back to the hub. If one stop wins, the change is one
word: `--input-order one-stop` when the factory list is generated. Nothing else
moves — the same patches, the same readings, the same rows.
