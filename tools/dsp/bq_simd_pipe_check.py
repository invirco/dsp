"""Simulate the two inner loops INSTRUCTION BY INSTRUCTION and compare.

Not a model of a biquad -- a model of the two register machines. Each
routine below executes exactly the instructions in biquad_fx.asm, in order,
on a dict of registers, so a seeding or peel error in the pipelined arm
shows up as a differing output word rather than as an argument."""
import random, struct

def f32(x):                      # the part keeps 40-bit extended internally;
    return x                     # both arms do the SAME ops in the SAME order,
                                 # so any consistent precision proves equality

def old_loop(x, b0, b1, b2, a1, a2, w1, w2):
    """.bqfl_ssamp -- eight instructions, BLOCK passes."""
    R = {}
    R['f4'], R['f5'], R['f6'], R['f7'], R['f2'] = b0, b1, b2, a1, a2
    R['f8'], R['f10'] = w1, w2
    out = []
    for n in range(len(x)):
        R['f0'] = x[n]
        R['f12'] = R['f0'] * R['f4']
        R['f13'], R['f1'] = R['f0'] * R['f5'], R['f8'] + R['f12']
        R['f9'],  R['f11'] = R['f0'] * R['f6'], R['f10'] + R['f13']
        R['f14'] = R['f1'] * R['f7']
        R['f15'] = R['f2'] * R['f1']
        R['f8'] = R['f11'] - R['f14']
        R['f10'] = R['f9'] - R['f15']
        out.append(R['f1'])
    return out, R['f8'], R['f10']

def pipe_loop(x, b0, b1, b2, a1, a2, w1, w2):
    """.bqfl_psamp -- five instructions, BLOCK-1 passes, last peeled."""
    R = {}
    R['f4'], R['f5'], R['f6'], R['f7'], R['f2'] = b0, b1, b2, a1, a2
    R['f8'], R['f10'] = w1, w2
    N = len(x)
    out = [None] * N
    i2 = 0
    i3 = 0
    # preamble
    R['f0'] = x[i2]; i2 += 1        # f0 = dm(i2,2)
    R['f9'] = R['f10']              # f9 = pass f10
    R['f15'] = 0.0                  # r15 = 0
    for _ in range(N - 1):
        R['f12'], R['f10'] = R['f0'] * R['f4'], R['f9'] - R['f15']
        R['f13'], R['f1']  = R['f0'] * R['f5'], R['f8'] + R['f12']
        R['f14'], R['f11'] = R['f1'] * R['f7'], R['f10'] + R['f13']
        _m, _a, _st = R['f0'] * R['f6'], R['f11'] - R['f14'], R['f1']
        R['f9'], R['f8'] = _m, _a
        out[i3] = _st; i3 += 1
        _m2, _ld = R['f2'] * R['f1'], x[i2]
        R['f15'], R['f0'] = _m2, _ld; i2 += 1
    # the peeled last sample
    R['f12'], R['f10'] = R['f0'] * R['f4'], R['f9'] - R['f15']
    R['f13'], R['f1']  = R['f0'] * R['f5'], R['f8'] + R['f12']
    R['f14'], R['f11'] = R['f1'] * R['f7'], R['f10'] + R['f13']
    _m, _a, _st = R['f0'] * R['f6'], R['f11'] - R['f14'], R['f1']
    R['f9'], R['f8'] = _m, _a
    out[i3] = _st; i3 += 1
    R['f15'] = R['f2'] * R['f1']
    R['f10'] = R['f9'] - R['f15']
    return out, R['f8'], R['f10'], i2, i3

random.seed(20260909)
BLOCK = 16
bad = 0
for trial in range(4000):
    x  = [random.uniform(-1, 1) for _ in range(BLOCK)]
    b0, b1, b2 = (random.uniform(-2, 2) for _ in range(3))
    a1, a2     = random.uniform(-2, 2), random.uniform(-1, 1)
    w1, w2     = random.uniform(-1, 1), random.uniform(-1, 1)
    # run several consecutive BLOCKS so the state hand-off is exercised too
    s1 = (w1, w2); s2 = (w1, w2)
    for blk in range(4):
        xb = [random.uniform(-1, 1) for _ in range(BLOCK)]
        o1, n1w1, n1w2 = old_loop(xb, b0, b1, b2, a1, a2, *s1)
        o2, n2w1, n2w2, i2end, i3end = pipe_loop(xb, b0, b1, b2, a1, a2, *s2)
        if o1 != o2 or n1w1 != n2w1 or n1w2 != n2w2:
            bad += 1
            if bad == 1:
                print('MISMATCH trial %d block %d' % (trial, blk))
                for k, (a, b) in enumerate(zip(o1, o2)):
                    if a != b:
                        print('  sample %d: old %r pipe %r' % (k, a, b)); break
                print('  w1 old %r pipe %r' % (n1w1, n2w1))
                print('  w2 old %r pipe %r' % (n1w2, n2w2))
            break
        s1 = (n1w1, n1w2); s2 = (n2w1, n2w2)
        assert i2end == BLOCK and i3end == BLOCK, (i2end, i3end)

print('%d random cascades x 4 consecutive blocks x %d samples' % (4000, BLOCK))
print('pointer advance: i2 %d, i3 %d, both = BLOCK  (the rewind by -2*BLOCK holds)'
      % (BLOCK, BLOCK))
print('MISMATCHES: %d' % bad)
print('RESULT: %s' % ('BIT-IDENTICAL' if bad == 0 else 'DIVERGES'))
