#!/usr/bin/env python3
"""S163: a row whose precondition is known absent is NO DATA at once."""
import os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', '..', '..', 'tools', 'pi'))
os.environ.setdefault('MATRIX_ADDR_HOME', os.path.join(HERE, '..', 's138b', 'fixtures'))
import d24_panel as PL
FAILS = []
def check(n, c, d=''):
    print('%-4s %s%s' % ('ok' if c else 'FAIL', n, '' if c else ': %r' % (d,)))
    if not c: FAILS.append(n)
class Bus:
    def flush(self): raise AssertionError('listened')
    def poll(self): raise AssertionError('listened')
asked = []
t = time.time()
got = PL.sense_sweep(Bus(), 'right', lambda *a: asked.append(a), timeout=30.0,
                     log=lambda s: None, idle=lambda: asked.append('idle'))
dt = time.time() - t
check('row 94 (temperature sense) is NO DATA with the reason', 94 in got
      and got[94][0] == PL.NODATA and PL.KNOWN_ABSENT[94] in got[94][1], got)
check('... instantly: no listen window (30 s timeout offered), no bus read',
      dt < 0.5, dt)
check('... no operator prompt and no idle listen', asked == [], asked)
check('... the note carries the tag the glass uses to skip the hold',
      got[94][1].startswith(PL.KNOWN_ABSENT_TAG))
saved = dict(PL.KNOWN_ABSENT); PL.KNOWN_ABSENT.clear()
class Silent:
    def flush(self): pass
    def poll(self): return []
got = PL.sense_sweep(Silent(), 'right', lambda *a: (lambda: None), timeout=0.2,
                     log=lambda s: None, idle=lambda: None)
check('delete the table line and the row listens again (then times out NO DATA)',
      got[94][0] == PL.NODATA and not got[94][1].startswith(PL.KNOWN_ABSENT_TAG), got)
print()
print('%d FAILED' % len(FAILS) if FAILS else 'all checks passed -- no unit, no bus, no write, no rails')
sys.exit(1 if FAILS else 0)
