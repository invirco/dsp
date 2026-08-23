"""Rung 0 proof: alternating write/read round-trips, counting phase slips."""
import sys
sys.argv = ['rt']
import dsp4_diag as D

def run(chip, n=200):
    cs = 6 if chip == 1 else 24
    rdy = 8 if chip == 1 else 12
    link = D.SpiLink('0.0', 1000000, cs, rdy_gpio=rdy)
    diag = D.DiagLink(link)
    diag.resync()
    slips = errors = 0
    for i in range(n):
        v = 0 if (i % 2) else 1
        diag.write(D.DIAG_LED_MODE, v)
        try:
            got = diag.read(D.DIAG_LED_MODE)
            if got != v:
                slips += 1
        except IOError:
            errors += 1
    diag.write(D.DIAG_LED_MODE, 0)
    print(f'chip {chip}: {n} write/read round-trips, '
          f'{slips} wrong-value, {errors} out-of-step')
    return slips + errors

bad = 0
for c in (1, 2):
    bad += run(c)
print('RUNG 0 PASS' if bad == 0 else f'RUNG 0 FAIL ({bad})')
