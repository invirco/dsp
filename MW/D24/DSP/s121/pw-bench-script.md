provenance: AI-drafted 2026-09-26 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# Timing a real analog pass — one page

MW-D24-2, `app@192.168.1.219`. Takes about 10 minutes plus whatever the leads
take. Nothing here changes the unit's configuration permanently: the station
shuts every route it opens and silences the monitor bus on the way out.

## What to have in hand

| | lead | where to get one |
|---|---|---|
| **K1** | XLR female → XLR male | any mic lead |
| **K5** | 150 Ω terminator, male XLR, 150 Ω across pins 2–3 | the EIN plug from the 09-16 survey |
| **K4** | XLR female → 6.35 mm TRS plug (pin 2 → tip, pin 3 → ring) | a standard balanced jack-to-XLR lead |
| **K2** | 6.35 mm TRS plug → XLR male (tip → pin 2, ring → pin 3) | the same lead the other way round — **it is a different lead**, the XLR gender is opposite |
| **K3** | XLR female → 3.5 mm TRS plug | a standard mini-jack-to-XLR lead |

## Before you start

```
ssh app@192.168.1.219
sudo systemctl stop matrix-app          # if it is running
pinctrl set 27 op dh                    # CS_M driven, or the DSP link reads zeros
pinctrl set 7,8 op dh
```

## The two patches that settle the biggest open question first

Do these before the full pass. They answer whether a TRS jack's tip really
sits 6 dB under the XLR beside it — the one window in the whole station that
rests on topology rather than on a measurement (**S121-4**).

```
cd /home/app/selftest/s121
python3 - <<'EOF'
import sys; sys.path.insert(0, '/home/app/selftest')
import d24_patch as PT
pl = PT.PatchList(PT.find_list_dir()); u = PT.Unit(); u.write(pl.standing())
def read(route, lane):
    u.write(pl.routes[route]); u.osc(chan=24, freq=1000.0, level_dbfs=-12.0, on=True)
    u.meas_chan(lane); m = u.measure(1000.0, -12.0, settle=PT.ROUTE_SETTLE_WINDOWS)
    return m
input('Patch AUX 1 (XLR) to MIC 1, then press Enter: ')
a = read('aux1@24', 1)
input('Move the AUX 1 end to the AUX A 1-2 jack (TRS), same MIC 1: ')
b = read('aux1@24', 1)
print('  balanced      %8.2f dB   %7.1f deg' % (a['h_db'], a['h_deg']))
print('  single-ended  %8.2f dB   %7.1f deg' % (b['h_db'], b['h_deg']))
print('  DIFFERENCE    %8.2f dB   %7.1f deg' % (b['h_db'] - a['h_db'],
                                                b['h_deg'] - a['h_deg']))
u.osc(on=False); u.write(pl.routes['_standing_close'], verify=False)
EOF
```

Expect about **−6 dB** and about **0°**. If it comes out near 0 dB instead, the
TRS tip is buffered rather than tapped off one leg, and `single_ended_db` in
`patch-limits.csv` becomes 0.0. Either way, put the number PW measures into
that file — it is the only place the station reads it from.

## The pass

```
cd /home/app/selftest/s121
python3 /home/app/selftest/d24_patch.py --run --stdin --hand 5
```

`--stdin` puts the prompts on the terminal instead of the glass. It prints the
lead to pick up, then one patch at a time.

**You do not press Enter.** Make the patch; it moves on by itself as soon as
the lead is in. Type `skip` or `pause` and Enter if you want to leave one out
or stop. If the tone turns up somewhere else it says so and asks again — that
is not a failure, it is the tester telling you which socket the lead is really
in.

Five blocks, in this order, lead change between each:

| block | patches | what moves |
|---|---|---|
| K1, the mic inputs | 25 | the input end walks MIC 1…24 and TALKBACK; the output end moves once per output for the first ten, then stays on AUX 1 |
| K5, the noise rows | 24 | just the terminator, MIC 1…24 |
| K4, the line inputs | 24 | the output end stays on AUX 1; the TRS end walks the 24 combo jacks |
| K2, the TRS outputs | 6 | the XLR end stays in MIC 1; the TRS end walks Monitor L, Monitor R and the four Aux Out A jacks |
| K3, the mini-jacks | 2 | the XLR end stays on AUX 1 |

At the end it prints the per-patch seconds and the projected pass. **The
number worth having is the real hand time**: the projection assumes 5 s per
move, and whatever it actually turns out to be is what sizes the station.

## Afterwards

The station shuts everything it opened. Worth confirming:

```
python3 /home/app/selftest/s89_set.py /home/app/loopthd/s109 \
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
