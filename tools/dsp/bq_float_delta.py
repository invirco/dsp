"""RIG A2 numeric delta (biquad shootout spike, 2026-09-02).

Answers the dispatch's question "state the numeric delta vs the current
contract as MAX ERROR IN dB ON REAL EQ CURVES, not as 'different'".

RIG A2 numeric delta: float DF-II-T (relaxed rounding) vs the current
fixed offset-form contract, stated as MAX ERROR IN dB ON REAL EQ CURVES.

Both are driven with the SAME quantised RBJ designs and the SAME stimulus;
the response is measured by driving an impulse through each cascade and
taking the FFT, which is what an EQ curve actually is. float32 is enforced
with numpy float32 at every step so the 24-bit mantissa is real, not a
float64 stand-in.
"""
import sys, math
sys.path.insert(0, 'tools/dsp')
import numpy as np
import fixed_ref as F

FS = 48000.0

def rbj_peak(f0, q, gain_db, fs=FS):
    a = 10.0 ** (gain_db / 40.0)
    w = 2*math.pi*f0/fs
    al = math.sin(w)/(2*q)
    b0, b1, b2 = 1+al*a, -2*math.cos(w), 1-al*a
    a0, a1, a2 = 1+al/a, -2*math.cos(w), 1-al/a
    return (b0/a0, b1/a0, b2/a0, a1/a0, a2/a0)

def rbj_shelf(f0, q, gain_db, high, fs=FS):
    A = 10.0**(gain_db/40.0); w = 2*math.pi*f0/fs
    cw, sw = math.cos(w), math.sin(w)
    al = sw/2*math.sqrt((A+1/A)*(1/q-1)+2)
    tsa = 2*math.sqrt(A)*al
    if high:
        b0 =    A*((A+1)+(A-1)*cw+tsa); b1 = -2*A*((A-1)+(A+1)*cw)
        b2 =    A*((A+1)+(A-1)*cw-tsa); a0 =    (A+1)-(A-1)*cw+tsa
        a1 =    2*((A-1)-(A+1)*cw);     a2 =    (A+1)-(A-1)*cw-tsa
    else:
        b0 =    A*((A+1)-(A-1)*cw+tsa); b1 =  2*A*((A-1)-(A+1)*cw)
        b2 =    A*((A+1)-(A-1)*cw-tsa); a0 =    (A+1)+(A-1)*cw+tsa
        a1 =   -2*((A-1)+(A+1)*cw);     a2 =    (A+1)+(A-1)*cw-tsa
    return (b0/a0, b1/a0, b2/a0, a1/a0, a2/a0)

def run_fixed(x, designs):
    """The CURRENT contract: quantised offset form, per-stage rns+sat,
    error feedback. Bit-for-bit fixed_ref, which is normative."""
    coeffs = [F.biquad_coeffs_q(*d) for d in designs]
    state  = [F.biquad_state() for _ in designs]
    out = []
    for s in x:
        v = F.to_q(s)
        for c, st in zip(coeffs, state):
            v = F.biquad(v, c, st)
        out.append(F.from_q(v))
    return np.array(out, dtype=np.float64)

def run_float(x, designs):
    """RIG A2: float32 DF-II-T, NO per-stage rounding, converted to Q4.28
    once at the cascade output. Coefficients are the SAME quantised words
    the fixed path uses, de-quantised -- so this isolates the ARITHMETIC
    change and not a coefficient change."""
    cо = []
    for d in designs:
        b0, n1h, n2, c1, c2 = F.biquad_coeffs_q(*d)
        # back out the direct form from the stored offset words, exactly
        # as the kernel's regrouping does
        b0f = np.float32(F.from_q(b0))
        b1f = np.float32(F.from_q(2*n1h) - 2*F.from_q(b0))
        b2f = np.float32(F.from_q(n2) + F.from_q(b0))
        a1f = np.float32(F.from_q(c1) - 2.0)
        a2f = np.float32(1.0 - F.from_q(c2))
        cо.append((b0f, b1f, b2f, a1f, a2f))
    w1 = [np.float32(0)]*len(cо); w2 = [np.float32(0)]*len(cо)
    out = []
    for s in x:
        v = np.float32(s)
        for k, (b0f, b1f, b2f, a1f, a2f) in enumerate(cо):
            y  = np.float32(b0f*v + w1[k])
            w1[k] = np.float32(b1f*v - a1f*y + w2[k])
            w2[k] = np.float32(b2f*v - a2f*y)
            v = y
        # round ONCE, at the cascade output, into Q4.28 and back
        out.append(F.from_q(F.sat32(F.rns(int(round(float(v)*(1<<28)))<<28, 28))))
    return np.array(out, dtype=np.float64)

def curve_db(y, n):
    Y = np.fft.rfft(y, n)
    return 20*np.log10(np.maximum(np.abs(Y), 1e-30))

N = 8192
imp = np.zeros(N); imp[0] = 0.5      # -6 dBFS impulse, inside Q4.28 range

CASES = {
 '1-band peak +15 dB Q3':        [rbj_peak(1000, 3.0, 15.0)],
 '1-band peak -15 dB Q3':        [rbj_peak(1000, 3.0, -15.0)],
 'EXTREME +15 dB Q0.1 @ 20 Hz':  [rbj_peak(20, 0.1, 15.0)],
 'EXTREME +15 dB Q10 @ 20 Hz':   [rbj_peak(20, 10.0, 15.0)],
 'LF shelf +15 dB Q3.16 @ 20 Hz':[rbj_shelf(20, 3.16, 15.0, False)],
 '4-band EQ, mixed':             [rbj_peak(80,1.1,8.0), rbj_peak(400,1.5,-6.0),
                                  rbj_peak(2500,2.0,6.0), rbj_peak(9000,0.8,-4.0)],
 '28-band GEQ all +6 dB':        [rbj_peak(25*(2**(i/6.0)), 4.3, 6.0) for i in range(28)],
 '28-band GEQ alternating ±6':   [rbj_peak(25*(2**(i/6.0)), 4.3, 6.0*(-1)**i) for i in range(28)],
}

print(f"{'design':32s} {'max |dB| err':>13s} {'@ Hz':>9s} {'err @20Hz':>10s}")
print('-'*70)
freqs = np.fft.rfftfreq(N, 1/FS)
band = (freqs >= 20) & (freqs <= 20000)
worst_all = 0.0
for name, designs in CASES.items():
    yf = run_fixed(imp, designs)
    yl = run_float(imp, designs)
    cf, cl = curve_db(yf, N), curve_db(yl, N)
    d = np.abs(cl - cf)
    d_b = d[band]; f_b = freqs[band]
    i = int(np.argmax(d_b))
    i20 = int(np.argmin(np.abs(freqs - 20)))
    worst_all = max(worst_all, d_b[i])
    print(f"{name:32s} {d_b[i]:13.4f} {f_b[i]:9.1f} {d[i20]:10.4f}")
print('-'*70)
print(f"WORST OVER ALL DESIGNS, 20 Hz - 20 kHz: {worst_all:.4f} dB")
print(f"golden_harness response bar for reference: 0.046 dB")
