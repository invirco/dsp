"""dsp4_bqwire — what a biquad coefficient word on the SPI wire means, for the image that is running.

The EQ, FILT (HPF/LPF) and comp side-chain filter nodes stage five float32 words per stage. What those words ARE
depends on one build switch (tools/dsp/dsp_codegen.py, the "SPI staging -- the WIRE" comments):

  DSP4_BQ_FLOAT=1  (shipping since 2026-09-03)  D5's OFFSET encoding  (b0, b1+2*b0, b2-b0, 2+a1, 1-a2)
  DSP4_BQ_FLOAT=0  (the fixed arm)              direct-form RBJ       (b0, b1, b2, a1, a2), a0 normalised

Writing direct form into a float-arm image is a DIFFERENT filter, and for real designs an unstable one: S67-5
measured a +6 dB peaking band written that way take strip 5 to -186 dB and MAIN L to the Q4.28 ceiling. Direct
"unity" (1,0,0,0,0) survives by accident -- as offset words it is (1-2z+z^2)/(1-2z+z^2), a pole-zero cancellation
AT DC, not a bypass -- which is how the tools that wrote it went unnoticed.

Tools keep taking and printing DIRECT form (it is what the models consume) and encode at the wire with `encode`.
The arm is read from the part (DIAG_BUILD_CFG bit 12), never assumed.
"""
DIAG_BUILD_CFG = 0xE0EA
BQ_FLOAT_BIT = 12
UNITY = (1.0, 0.0, 0.0, 0.0, 0.0)          # direct form


def offset_form(c):
    """Direct form -> the float arm's wire words (tools/dsp/geq_ref.offset_form)."""
    b0, b1, b2, a1, a2 = c
    return (b0, b1 + 2.0 * b0, b2 - b0, 2.0 + a1, 1.0 - a2)


def float_arm(sc, wire='auto'):
    """True if the running image's wire is the offset form. wire: 'auto' (read the part), 'offset', 'direct'."""
    if wire == 'offset':
        return True
    if wire == 'direct':
        return False
    if wire != 'auto':
        raise ValueError('wire must be auto, offset or direct, not %r' % wire)
    import dsp4_buildcfg as B
    word = sc.d.read(DIAG_BUILD_CFG)
    return bool(B.decode(word)['DSP4_BQ_FLOAT'])     # decode raises on a non-config word: no guessing


def encode(band, is_float_arm):
    """One stage, direct form in, the five wire words (floats) out."""
    if len(band) != 5:
        raise ValueError('a biquad stage is 5 coefficients, got %d' % len(band))
    return tuple(offset_form(band)) if is_float_arm else tuple(band)
