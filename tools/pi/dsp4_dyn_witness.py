#!/usr/bin/env python3
"""dsp4_dyn_witness.py — prove the dynamics are on their SIGNAL path.

A ceiling measured with the TDM inputs silent is a measurement of the
cheap branch: _compgain_fx returns unity at `if le jump .cg_unity` before
it ever reaches log2, and GATE takes .gkb_below without calling
_log2q_fx. A signal-present sweep is only worth quoting if the stimulus
actually opened those paths, so this reads the witnesses that only the
expensive path can produce:

  _gate_envelope  ~ |x|        follower has a non-zero input
  _gate_gain      = 0x10000000 gate OPEN (log2 compare cleared the -40 dB
                               threshold; the closed value is the range
                               floor, 0.001)
  _comp_envelope  ~ |x|
  _comp_gain      < unity      the compressor computed gain reduction,
                               which is log2 -> knee -> exp2 end to end

With the shipping defaults (-20 dB threshold, ratio 4, hard knee) and the
-6 dBFS stimulus the predicted comp gain is 2^-(0.75*log2(0.5/0.1)) =
0.2988 -> 0x04C7xxxx, i.e. -10.5 dB of gain reduction. A reading near
that is a much stronger witness than "non-zero": it says the polynomial
pair ran and produced the arithmetically correct answer.

Reads are taken twice and must agree -- the diag link intermittently
answers 0xFFFFFFFF to a peek and one read cannot tell that from a value.

Usage:  dsp4_dyn_witness.py [n_strips]
"""
import math
import sys
import time

sys.path.insert(0, '/home/app/dspboot')
import dsp4_scope as S

N = int(sys.argv[1]) if len(sys.argv) > 1 else 4
UNITY = 0x10000000


def q28(v):
    """Q4.28 word -> float, signed."""
    if v is None:
        return None
    v &= 0xFFFFFFFF
    if v & 0x80000000:
        v -= 1 << 32
    return v / float(1 << 28)


def db(x):
    if x is None or x <= 0:
        return float('-inf')
    return 20.0 * math.log10(x)


def main():
    sc = S.Scope(1)
    sc.check_chip()

    def peek(name):
        if name not in sc.sym:
            return None
        a = sc.sym[name]
        last = None
        for _ in range(24):
            try:
                v = sc.peek(a)
            except Exception:
                last = None
                time.sleep(0.05)
                continue
            if v is None or v == 0xFFFFFFFF:
                last = None
                time.sleep(0.03)
                continue
            if v == last:
                return v
            last = v
            time.sleep(0.03)
        return None

    open_n = shut_n = comp_n = unity_n = unread = 0
    print('strip  gate_env      gate_gain            comp_env      comp_gain')
    for i in range(1, N + 1):
        ge = peek('_gate_envelope_C1_GATE_%02d' % i)
        gg = peek('_gate_gain_C1_GATE_%02d' % i)
        ce = peek('_comp_envelope_C1_COMP_%02d' % i)
        cg = peek('_comp_gain_C1_COMP_%02d' % i)
        if None in (ge, gg, ce, cg):
            unread += 1
            print('%5d  UNREADABLE (%s)' % (i, ' '.join(
                n for n, v in (('gate_env', ge), ('gate_gain', gg),
                               ('comp_env', ce), ('comp_gain', cg))
                if v is None)))
            continue
        if gg > UNITY * 0.999:
            open_n += 1
            gs = 'OPEN'
        else:
            shut_n += 1
            gs = 'SHUT'
        if cg < UNITY * 0.999:
            comp_n += 1
            cs = '%+.2f dB GR' % db(q28(cg))
        else:
            unity_n += 1
            cs = 'unity (cheap path)'
        print('%5d  %9.6f  0x%08X %-4s  %9.6f  0x%08X %s'
              % (i, q28(ge), gg, gs, q28(ce), cg, cs))

    print('')
    print('gate OPEN %d / SHUT %d, comp ACTIVE %d / unity %d, unreadable %d'
          % (open_n, shut_n, comp_n, unity_n, unread))
    if open_n == N and comp_n == N:
        print('SIGNAL PRESENT ON ALL %d STRIPS — dynamics on the real path' % N)
        return 0
    if open_n == 0 and comp_n == 0 and unread == 0:
        print('SILENT — every strip on the cheap branch (this is the control)')
        return 3
    print('MIXED/UNPROVEN — do not quote a ceiling from this build')
    return 1


if __name__ == '__main__':
    sys.exit(main())
