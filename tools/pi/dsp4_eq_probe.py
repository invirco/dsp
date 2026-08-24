#!/usr/bin/env python3
"""dsp4_eq_probe — load EQ coefficients, capture the impulse response.

Runs on the Pi. Drives one channel strip's EQ through the parameter link
and captures its output with the DSP-side scope (src/scope.asm), so the
measurement never touches the Pi audio path.

Chain (chip 1, strip 1):
    _rx_slot_C1_IN_01 -> GAIN_01 -> FILT_01 -> EQ_01 -> _buf_C1_EQ_01

GAIN and FILT default to unity, so injecting at the strip input puts a
clean impulse on the EQ's doorstep with NO matrix routing involved --
routes are host-written parameters nothing sets at boot, and needing them
is what stalled the earlier latency attempt.

The EQ takes FLOAT RBJ coefficients on the wire and converts to the
Q4.28 offset form itself, so tools/dsp/fixed_ref.py::biquad_coeffs_q
predicts the stored values exactly and the impulse response can be
checked BIT-EXACTLY rather than to a dB tolerance.

Prints one value per line as "idx value"; the comparison against
fixed_ref happens on the dev box where the normative model lives.
"""
import argparse, json, struct, sys, time

sys.path.insert(0, '/home/app/dspboot')
import dsp4_scope as S

GAIN_ADDR = 0x0000          # C1_GAIN_01 gain coeff (float)
EQ_COEFF0 = 0x0010          # 20 float words
EQ_SWAP   = 0x0024
HPF_COEFF0, HPF_SWAP = 0x0004, 0x0009   # C1_FILT_01, 5 float words each
LPF_COEFF0, LPF_SWAP = 0x000A, 0x000F


def f32(x):
    return struct.unpack('<I', struct.pack('<f', float(x)))[0]


def wr_verified(sc, addr, val, tries=12):
    """Parameter writes are dropped under audio load exactly as reads are.
    Every write here is read back, because a coefficient that silently
    failed to land produces a perfectly plausible wrong impulse response."""
    val &= 0xFFFFFFFF
    for _ in range(tries):
        sc.d.write(addr, val)
        time.sleep(S.SETTLE)
        try:
            if sc.rd(addr) == val:
                return
        except IOError:
            pass
    raise IOError('SPI 0x%04X would not take 0x%08X' % (addr, val))


def rbj_peaking(f0, q, gain_db, fs=48000.0):
    import math
    A = 10.0 ** (gain_db / 40.0)
    w0 = 2.0 * math.pi * f0 / fs
    alpha = math.sin(w0) / (2.0 * q)
    b0 = 1 + alpha * A
    b1 = -2 * math.cos(w0)
    b2 = 1 - alpha * A
    a0 = 1 + alpha / A
    a1 = -2 * math.cos(w0)
    a2 = 1 - alpha / A
    return [b0 / a0, b1 / a0, b2 / a0, a1 / a0, a2 / a0]


UNITY = [1.0, 0.0, 0.0, 0.0, 0.0]


def set_biquad(sc, base, swap, band):
    for i, c in enumerate(band):
        wr_verified(sc, base + i, f32(c))
    for _ in range(3):
        sc.d.write(swap, 1)
        time.sleep(S.SETTLE)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--n', type=int, default=256)
    ap.add_argument('--amp', default='0x08000000')
    ap.add_argument('--bands', default='peak1k',
                    choices=('unity', 'peak1k', 'four', 'custom'))
    ap.add_argument('--rbj', help='band 0 as b0,b1,b2,a1,a2 (others unity)')
    ap.add_argument('--filt', help='FILT instead of EQ: hpf b0,..,a2 / lpf b0,..,a2 '
                                   'separated by a semicolon')
    ap.add_argument('--pool-inj', type=int, default=None,
                    help='inject at _blk_pool + N*32 (per-block kernels: the\n'
                         'input kernel reads DMA directly, so the stimulus goes\n'
                         'into the pool from inside the chain)')
    ap.add_argument('--pool-src', type=int, default=None,
                    help='capture _blk_pool + N*32 instead of the node buffer '
                         '(per-block kernels put node outputs in the shared pool)')
    ap.add_argument('--baseline', action='store_true',
                    help='inject nothing: prove the EQ is at rest')
    a = ap.parse_args()

    sc = S.Scope(1)
    inj = (sc.sym['_blk_pool'] + a.pool_inj * 32) if a.pool_inj is not None \
          else sc.sym['_rx_slot_C1_IN_01']
    src = sc.sym['_buf_C1_EQ_01']

    # RESET THE WHOLE CHAIN, every run. Leaving the previous test's
    # coefficients in an upstream node is how an EQ measurement ends up
    # being taken through somebody else's low-pass: bench 2026-08-23, a
    # peaking response looked wrong for an hour because FILT still held
    # lpf b0 = 0.1 from the FILT sweep and the EQ sat downstream of it.
    wr_verified(sc, GAIN_ADDR, f32(1.0))
    if not a.filt:
        set_biquad(sc, HPF_COEFF0, HPF_SWAP, UNITY)
        set_biquad(sc, LPF_COEFF0, LPF_SWAP, UNITY)
        time.sleep(0.3)

    if a.filt:
        # HPF/LPF cascade in C1_FILT_01, captured at its own output. Same
        # _bq_fx_convert_N path as the EQ, so it carried the same b1 bug.
        hpf, lpf = [[float(x) for x in part.split(',')] for part in a.filt.split(';')]
        set_biquad(sc, HPF_COEFF0, HPF_SWAP, hpf)
        set_biquad(sc, LPF_COEFF0, LPF_SWAP, lpf)
        time.sleep(0.5)
        src = (sc.sym['_blk_pool'] + a.pool_src * 32) if a.pool_src is not None \
              else sc.sym['_buf_C1_FILT_01']
        amp = 0 if a.baseline else int(a.amp, 16)
        sc.arm(src, inj, amp, 1)
        sc.wait()
        print('COEFFS ' + json.dumps([hpf, lpf]))
        for i, v in enumerate(sc.fetch(a.n)):
            print('%d %d' % (i, v - (1 << 32) if v & 0x80000000 else v))
        return

    if a.bands == 'custom':
        bands = [[float(x) for x in a.rbj.split(',')]] + [UNITY] * 3
    elif a.bands == 'unity':
        bands = [UNITY] * 4
    elif a.bands == 'peak1k':
        bands = [rbj_peaking(1000.0, 1.0, 6.0)] + [UNITY] * 3
    else:
        bands = [rbj_peaking(120.0, 0.7, -8.0), rbj_peaking(1000.0, 1.0, 6.0),
                 rbj_peaking(3500.0, 2.0, -4.0), rbj_peaking(9000.0, 0.9, 5.0)]

    flat = [c for band in bands for c in band]
    for i, c in enumerate(flat):
        wr_verified(sc, EQ_COEFF0 + i, f32(c))
    # The swap trigger CANNOT be read back: the node consumes it (clears
    # _eq_swap_pending as it starts the crossfade), so a read always
    # returns 0 and says nothing. Write it a few times, then prove the
    # swap really happened by scoping _eq_active, which toggles on swap.
    for _ in range(3):
        sc.d.write(EQ_SWAP, 1)
        time.sleep(S.SETTLE)
    time.sleep(0.5)                              # EqSafe crossfade is 18 blocks

    sc.arm(sc.sym['_eq_active_C1_EQ_01'], 0, 0, 1)
    sc.wait()
    active = sc.fetch(1)[0]
    print('EQ_ACTIVE %d' % active)

    amp = 0 if a.baseline else int(a.amp, 16)
    sc.arm(src, inj, amp, 1)                     # impulse
    if not sc.wait():
        raise SystemExit('scope never disarmed - sample loop not turning')
    vals = sc.fetch(a.n)

    print('COEFFS ' + json.dumps(bands))
    for i, v in enumerate(vals):
        print('%d %d' % (i, v - (1 << 32) if v & 0x80000000 else v))


if __name__ == '__main__':
    main()
