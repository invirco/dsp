#!/usr/bin/env python3
"""d24_inputs.py — the D24 mic XLR <-> 595 register <-> converter slot <-> strip map, ONE table for every tool.

Source: the D24 Analog rev B netlist walk (mx26 docs/d24-analog-xlr-map.md), measured on the part in S51-4/S52-1/S55.
Within each AK5558 the XLRs were placed for layout, not channel number: XLR position 1..8 -> AIN 8,7,6,5,3,4,1,2 ->
TDM slot 7,6,5,4,2,3,0,1. Converter lanes: U15 = AD0 (sport 0), U39 = AD1 (sport 1), U60 = AD2 (sport 2).

The STRIP an XLR arrives on is not in this table: it is computed from `dsp4_config.D24_INPUT_PATCH` (packed RX index
`rx` = 8 * AD + slot -> strip PATCH[rx] + 1), so the patch the host writes and the lane every tool reads cannot
disagree. `PRE_S58_PATCH` is the half-frame table every S48-S57 record was taken under; use `strip(xlr, PRE_S58_PATCH)`
to read the "lane" column of those records back to an XLR.

Proposed as a defs declaration (products/d24/inputs.csv) in proposals/CONTRACT-PROPOSAL-S58.md; until it lands this
module is the one copy.

  d24_inputs.py              print the table (XLR, panel, chain index, send position, ADC, AIN, slot, rx lane, strip)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dsp4_config import D24_INPUT_PATCH  # noqa: E402

# Packed RX -> strip index as written before S58 (AD slots 0-3 = ch 1-4, 4-7 = ch 13-16: the wrong slot order).
PRE_S58_PATCH = ([0, 1, 2, 3, 12, 13, 14, 15] + [4, 5, 6, 7, 16, 17, 18, 19]
                 + [8, 9, 10, 11, 20, 21, 22, 23] + list(range(24, 46)))

CONVERTERS = (('U15', 0, 'J15 J16 J17 J18 J19 J20 J21 J22'),
              ('U39', 1, 'J25 J26 J27 J28 J29 J30 J31 J32'),
              ('U60', 2, 'J35 J36 J37 J38 J39 J40 J41 J42'))
PREAMP_595 = ('U17 U19 U21 U23 U25 U27 U29 U31 U41 U43 U45 U47 U49 U51 U53 U55 '
              'U62 U64 U66 U68 U70 U72 U74 U76').split()     # chain index 1..24 (U34 = index 0 = SHIFT/INSTR)
POS_AIN = (8, 7, 6, 5, 3, 4, 1, 2)               # XLR position 1..8 on its converter -> AIN n
# Panel channel per chain index 1..24 (rows alternate bottom 1-12 / top 13-24 along the board).
PANEL = (1, 13, 2, 14, 3, 15, 4, 16, 5, 17, 6, 18, 7, 19, 8, 20, 9, 21, 10, 22, 11, 23, 12, 24)


class Xlr:
    __slots__ = ('xlr', 'panel', 'preamp', 'chain', 'send', 'adc', 'ad', 'ain', 'slot', 'rx')

    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)

    def strip(self, patch=D24_INPUT_PATCH):
        return patch[self.rx] + 1

    @property
    def lane(self):
        """The C1_IN_nn INPUT_TDM cell whose (sport, slot) this XLR's converter slot is (dsp.csv; identity packing)."""
        return 'C1_IN_%02d' % (self.rx + 1)

    @property
    def name(self):
        return 'MIC %d' % self.panel


def _build():
    rows, chain = [], 0
    for adc, ad, xlrs in CONVERTERS:
        for pos, x in enumerate(xlrs.split()):
            chain += 1
            ain = POS_AIN[pos]
            rows.append(Xlr(xlr=x, panel=PANEL[chain - 1], preamp=PREAMP_595[chain - 1], chain=chain, send=24 - chain,
                            adc=adc, ad=ad, ain=ain, slot=ain - 1, rx=8 * ad + ain - 1))
    return rows


XLRS = _build()
BY_XLR = {r.xlr: r for r in XLRS}


def strip(xlr, patch=D24_INPUT_PATCH):
    """Chip-1 strip (1-based: MeasChan, ChanNNN cells, C1_GAIN_nn) XLR `xlr` is patched onto. Its converter lane is .lane."""
    return BY_XLR[xlr].strip(patch)


def xlr_on(strip_n, patch=D24_INPUT_PATCH):
    """The Xlr row whose converter slot is patched onto strip `strip_n`, or None (25-32: NET)."""
    for r in XLRS:
        if r.strip(patch) == strip_n:
            return r
    return None


def by_panel(n):
    return next(r for r in XLRS if r.panel == n)


MIC5 = BY_XLR['J25']
MIC5_STRIP = MIC5.strip()


def check():
    """The patch must be a permutation over the 24 analog RX entries and put every XLR on its panel strip."""
    s = sorted(D24_INPUT_PATCH[:24])
    assert s == list(range(24)), 'D24_INPUT_PATCH[0:24] is not a permutation of 0..23'
    bad = [r.xlr for r in XLRS if r.strip() != r.panel]
    assert not bad, 'XLR not on its panel strip: %s' % bad
    return True


if __name__ == '__main__':
    check()
    print('%-4s %-7s %5s %4s %-4s %3s %4s %4s %3s %6s %10s' % ('XLR', 'panel', 'chain', 'send', 'ADC', 'AD', 'AIN', 'slot',
                                                              'rx', 'strip', 'pre-S58'))
    for r in XLRS:
        print('%-4s %-7s %5d %4d %-4s %3d %4d %4d %3d %6d %10d' % (r.xlr, r.name, r.chain, r.send, r.adc, r.ad, r.ain,
                                                                  r.slot, r.rx, r.strip(), r.strip(PRE_S58_PATCH)))
