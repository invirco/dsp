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

def slack_loop(x, b0, b1, b2, a1, a2, w1, w2):
    """.bqfl_qsamp -- the SIX-SLOT schedule (S14), BLOCK-1 passes, last peeled.

    Same eleven operations, same operands, SAME ORDER OF THE ADDITIONS as
    both loops above, so it is bit-exact against them by construction. What
    changed is only WHERE each one issues.

    WHY SIX AND NOT FIVE. bq_probe.asm measured the rule the ADSP-2156x
    Hardware Reference does not state: instructions issue at 1.000 cycles
    each, but a COMPUTE result is not readable by the next instruction --
    every producer->consumer edge between adjacent instructions costs
    exactly one extra cycle, the same for mul->mul, ALU->ALU and mul<->ALU
    (0.984 measured, three ways). A memory load's result IS readable next
    instruction, at zero cost. So the five-instruction schedule cost
    5 + 4 stalls and the eight-instruction one 8 + 2 -- which is the whole
    of why the 8->5 rewrite bought 5.5 % where the instruction count said
    25 %.

    Under that rule the floor is not the instruction count and not
    max(multiplies, ALU, moves): it is the LOOP-CARRIED DEPENDENCE CHAIN.
    For this arithmetic the cycle is y -> q1 -> w1' -> y, three dependent
    operations at two cycles an edge = SIX cycles per sample, against five
    instructions to issue. Six slots is therefore the exact floor for a
    bit-exact schedule, and this is a schedule that reaches it: every
    dependence is at least two slots deep and nothing stalls.

      S1  p0 = x*b0    w1  = t  - q1
      S2  p1 = x*b1    w2  = p2 - q2
      S3  p2 = x*b2    y   = w1 + p0
      S4                t   = w2 + p1     load  x(n+1)
      S5  q1 = y*a1                       store y(n)
      S6  q2 = a2*y

    Registers are placed for the dual-compute operand quadrants -- the
    multiplier takes X from R0-R3 and Y from R4-R7, the ALU takes X from
    R8-R11 and Y from R12-R15 -- with a2 in R0-R3 because S6 is the one
    multiply with no ALU partner and a standalone multiply is unrestricted,
    which is the same reason the two loops above put it there.

    PASS 0 SEEDS the two ALU ops that read the previous sample: t(-1) = w1
    and p2(-1) = w2 with q1(-1) = q2(-1) = +0.0, so S1 and S2 recover the
    incoming state exactly (x - 0.0 == x for every finite float, including
    -0.0). That is the same trick the five-slot loop already uses for w2
    and which bqeverify has certified at 0 ULP on the part.
    """
    R = {}
    R['f4'], R['f5'], R['f6'], R['f7'], R['f3'] = b0, b1, b2, a1, a2
    N = len(x)
    out = [None] * N
    i2 = 0
    i3 = 0
    # preamble: t(-1) = w1, p2(-1) = w2, q1(-1) = q2(-1) = +0.0
    R['f8'] = w1
    R['f9'] = w2
    R['f12'] = 0.0
    R['f13'] = 0.0
    R['f0'] = x[i2]; i2 += 1
    for _ in range(N - 1):
        R['f14'], R['f10'] = R['f0'] * R['f4'], R['f8'] - R['f12']
        R['f15'], R['f11'] = R['f0'] * R['f5'], R['f9'] - R['f13']
        R['f9'],  R['f1']  = R['f0'] * R['f6'], R['f10'] + R['f14']
        R['f8'], _ld = R['f11'] + R['f15'], x[i2]
        R['f0'] = _ld; i2 += 1
        R['f12'] = R['f1'] * R['f7']
        out[i3] = R['f1']; i3 += 1
        R['f13'] = R['f3'] * R['f1']
    # the peeled last sample: the same six, without the read-ahead
    R['f14'], R['f10'] = R['f0'] * R['f4'], R['f8'] - R['f12']
    R['f15'], R['f11'] = R['f0'] * R['f5'], R['f9'] - R['f13']
    R['f9'],  R['f1']  = R['f0'] * R['f6'], R['f10'] + R['f14']
    R['f8'] = R['f11'] + R['f15']
    R['f12'] = R['f1'] * R['f7']
    out[i3] = R['f1']; i3 += 1
    R['f13'] = R['f3'] * R['f1']
    # the state the next block starts from
    w1n = R['f8'] - R['f12']
    w2n = R['f9'] - R['f13']
    return out, w1n, w2n, i2, i3

random.seed(20260909)
BLOCK = 16
bad = 0
for trial in range(4000):
    x  = [random.uniform(-1, 1) for _ in range(BLOCK)]
    b0, b1, b2 = (random.uniform(-2, 2) for _ in range(3))
    a1, a2     = random.uniform(-2, 2), random.uniform(-1, 1)
    w1, w2     = random.uniform(-1, 1), random.uniform(-1, 1)
    # run several consecutive BLOCKS so the state hand-off is exercised too
    s1 = (w1, w2); s2 = (w1, w2); s3 = (w1, w2)
    for blk in range(4):
        xb = [random.uniform(-1, 1) for _ in range(BLOCK)]
        o1, n1w1, n1w2 = old_loop(xb, b0, b1, b2, a1, a2, *s1)
        o2, n2w1, n2w2, i2end, i3end = pipe_loop(xb, b0, b1, b2, a1, a2, *s2)
        o3, n3w1, n3w2, i2e3, i3e3 = slack_loop(xb, b0, b1, b2, a1, a2, *s3)
        if o1 != o3 or n1w1 != n3w1 or n1w2 != n3w2:
            bad += 1
            if bad == 1:
                print('SIX-SLOT MISMATCH trial %d block %d' % (trial, blk))
                for k, (a, b) in enumerate(zip(o1, o3)):
                    if a != b:
                        print('  sample %d: old %r six %r' % (k, a, b)); break
                print('  w1 old %r six %r' % (n1w1, n3w1))
                print('  w2 old %r six %r' % (n1w2, n3w2))
            break
        assert i2e3 == BLOCK and i3e3 == BLOCK, (i2e3, i3e3)
        s3 = (n3w1, n3w2)
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
print('THREE schedules compared: 8-instruction, 5-instruction, 6-SLOT')
print('pointer advance: i2 %d, i3 %d, both = BLOCK  (the rewind by -2*BLOCK holds)'
      % (BLOCK, BLOCK))
print('MISMATCHES: %d' % bad)
print('RESULT: %s' % ('BIT-IDENTICAL' if bad == 0 else 'DIVERGES'))
