#!/usr/bin/env python3
"""s63_latch_analyse.py DATA_DIR [XLR] — which CS_M edge applies the gain (s63_latch.py captures): the sample where the
1-cycle amplitude envelope first crosses 50 % of the way to the new level, against the pass-1 and pass-2 rising edges."""
import json, math, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import s63_analyse as A

ddir = sys.argv[1]
xlr = sys.argv[2] if len(sys.argv) > 2 else 'J25'
for r in A.load(ddir, 'latch_' + xlr):
    x = r['x']
    f, w, cpre, cpost, e50, env = A.tone_model(x, r['s_p1_hi'])
    print('gap %3.0f ms  code %d -> %d  p1 lo %.0f hi %.0f  p2 lo %.0f hi %.0f  50%% at %d = p1 hi %+.0f samples (%+.2f ms), '
          'p2 hi %+.0f samples' % (r['gap_s'] * 1000, r['from'][0], r['to'][0], r['s_p1_lo'], r['s_p1_hi'], r['s_p2_lo'],
                                   r['s_p2_hi'], e50, e50 - r['s_p1_hi'], (e50 - r['s_p1_hi']) / 48.0, e50 - r['s_p2_hi']))
