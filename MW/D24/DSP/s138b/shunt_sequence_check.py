#!/usr/bin/env python3
"""shunt_sequence_check.py -- S138b: the 595 bit-0 rename and PW's shunt-first
phantom sequence, proved off the bench. No SPI, no unit, no rails, no phantom.

Two things are being proved, and the first one matters more than it looks:

  1. THE RENAME MOVED A NAME AND NOT A BIT. `d24_chain.byte()` used to be
     `byte(mute, phantom, gain)` and is now `byte(shunt, phantom, gain)` --
     because Q0 IS the phantom shunt (PW 2026-09-16, mx26
     `docs/ref-d24-analog-attach.md`) and never was a mute; the channel mute is
     digital, in the DSP strip. All 256 encodings are checked against the
     pre-rename arithmetic literally, so a wire that has been right since S51
     cannot have been changed by a docstring.

  2. THE SEQUENCE IS PW'S, STEP BY STEP. "Phantom is therefore never switched
     by one image": shunt on, wait t1, phantom toggled with the shunt still on,
     wait t2, shunt restored to whatever it was. Each of the three images is
     asserted bit by bit, both directions, on one channel and on a set, with a
     channel that arrives ALREADY shunted (step 5 must leave it shunted, not
     released -- "restored to whatever it was before", not "off"), and the
     failure path is checked to leave the shunt ENGAGED, which PW names as the
     safe end state.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', '..', '..', 'tools', 'pi'))
import d24_chain as CH   # noqa: E402

FAILS = []


def check(name, cond, detail=''):
    print('%-4s %s%s' % ('ok' if cond else 'FAIL', name,
                         (': ' + detail) if detail and not cond else ''))
    if not cond:
        FAILS.append(name)


# The arithmetic as it stood before the rename, copied here deliberately rather
# than imported: this is the thing the new code must still equal.
def byte_before_the_rename(mute=0, phantom=0, gain=0):
    return (gain & 63) << 2 | (phantom & 1) << 1 | (mute & 1)


def test_encoding_is_byte_identical():
    bad = []
    for gain in range(64):
        for phantom in (0, 1):
            for shunt in (0, 1):
                want = byte_before_the_rename(mute=shunt, phantom=phantom,
                                              gain=gain)
                got = CH.byte(shunt=shunt, phantom=phantom, gain=gain)
                if got != want:
                    bad.append((shunt, phantom, gain, got, want))
    check('all 256 encodings byte-identical to the pre-rename arithmetic',
          not bad, repr(bad[:4]))


def test_deprecated_alias():
    check('mute= still writes the same bit',
          all(CH.byte(mute=m, phantom=p, gain=g)
              == CH.byte(shunt=m, phantom=p, gain=g)
              for m in (0, 1) for p in (0, 1) for g in (0, 7, 63)))
    try:
        CH.byte(shunt=1, mute=0)
        ok = False
    except AssertionError:
        ok = True
    check('shunt= and mute= disagreeing is refused, not silently resolved', ok)


def test_split_is_the_inverse():
    bad = [(s, p, g) for g in range(64) for p in (0, 1) for s in (0, 1)
           if CH.split(CH.byte(shunt=s, phantom=p, gain=g)) != (s, p, g)]
    check('split() inverts byte() on every encoding', not bad, repr(bad[:4]))


def test_safe_image_is_shunted():
    safe = [0x01] * 24 + [0x00]
    shunts = [CH.split(b)[0] for b in safe[:24]]
    check('the SAFE image has the shunt engaged on all 24 preamps',
          shunts == [1] * 24, repr(shunts))
    check('... phantom off and gain 0 on all 24',
          all(CH.split(b)[1:] == (0, 0) for b in safe[:24]))


def test_the_trailing_byte_is_unreachable():
    """Byte 24 is U34's, whose Q0 is INSTR1 and not a shunt at all."""
    for fn in (CH.with_shunt, CH.with_phantom):
        try:
            fn([0x00] * 25, [24], True)
            ok = False
        except AssertionError:
            ok = True
        check('%s refuses transmit position 24 (U34/INSTR1, not a preamp)'
              % fn.__name__, ok)


def test_sequence_on_one_channel():
    base = [0x00] * 24 + [0x00]        # everything released, phantom off
    steps = CH.phantom_sequence(base, [3], True)
    check('the sequence is three images', len(steps) == 3, repr(len(steps)))
    (s1, _w1, t1), (s3, _w3, t3), (s5, _w5, t5) = steps
    check('step 1: shunt ON, phantom still OFF',
          CH.split(s1[3]) == (1, 0, 0), repr(CH.split(s1[3])))
    check('step 1 waits t1 = ShuntSettleMs', abs(t1 - 0.050) < 1e-9, repr(t1))
    check('step 3: phantom ON, shunt STILL ON',
          CH.split(s3[3]) == (1, 1, 0), repr(CH.split(s3[3])))
    check('step 3 waits t2 = PhantomSettleMs', abs(t3 - 0.300) < 1e-9, repr(t3))
    check('step 5: shunt back to what it was (released), phantom ON',
          CH.split(s5[3]) == (0, 1, 0), repr(CH.split(s5[3])))
    check('step 5 waits for nothing', t5 == 0.0, repr(t5))
    for i, img in enumerate((s1, s3, s5)):
        check('step %d touches no other channel and no gain code'
              % (1, 3, 5)[i],
              all(b == 0x00 for j, b in enumerate(img) if j != 3),
              repr([hex(b) for b in img]))


def test_sequence_restores_an_already_shunted_channel():
    """PW's step 5 is "restored to whatever it was before", not "off"."""
    base = CH.with_shunt([0x00] * 24 + [0x00], [7], True)
    s1, s3, s5 = [img for img, _w, _t in CH.phantom_sequence(base, [7], True)]
    check('an already-shunted channel comes out of step 5 STILL shunted',
          CH.split(s5[7]) == (1, 1, 0), repr(CH.split(s5[7])))


def test_sequence_on_a_set_keeps_each_channel_its_own():
    """Step 1 is "every channel whose phantom is about to change", and step 5
    is per channel -- so a set with mixed incoming shunt states must come out
    with each channel back where it started."""
    base = [0x00] * 24 + [0x00]
    base = CH.with_shunt(base, [1, 5], True)          # two arrive shunted
    base[9] = CH.byte(shunt=0, phantom=0, gain=63)    # one arrives at gain 63
    s1, s3, s5 = [img for img, _w, _t in
                  CH.phantom_sequence(base, [1, 5, 9], True)]
    check('step 1 shunts every channel in the set',
          [CH.split(s1[c])[0] for c in (1, 5, 9)] == [1, 1, 1])
    check('step 3 moves phantom on every channel in the set',
          [CH.split(s3[c])[1] for c in (1, 5, 9)] == [1, 1, 1])
    check('step 5 gives each channel back its OWN incoming shunt state',
          [CH.split(s5[c])[0] for c in (1, 5, 9)] == [1, 1, 0],
          repr([CH.split(s5[c]) for c in (1, 5, 9)]))
    check('the gain code on the set is carried through untouched',
          all(CH.split(img[9])[2] == 63 for img in (s1, s3, s5)))


def test_phantom_off_direction():
    base = CH.with_phantom([0x00] * 24 + [0x00], [11], True)
    s1, s3, s5 = [img for img, _w, _t in CH.phantom_sequence(base, [11], False)]
    check('off direction, step 1: shunt on, phantom still ON',
          CH.split(s1[11]) == (1, 1, 0), repr(CH.split(s1[11])))
    check('off direction, step 3: phantom OFF, shunt still on',
          CH.split(s3[11]) == (1, 0, 0), repr(CH.split(s3[11])))
    check('off direction, step 5: shunt released again, phantom OFF',
          CH.split(s5[11]) == (0, 0, 0), repr(CH.split(s5[11])))


# ---------------------------------------------------------------------------
# The station's own verified loads around it, and the failure end state
# ---------------------------------------------------------------------------
class FakeAnalog(object):
    """`Analog.phantom` with the wire replaced by a list, so the three verified
    loads and the failure path can be asserted without an SPI device."""

    def __init__(self, fail_on=None):
        sys.path.insert(0, os.path.join(HERE, '..', '..', '..', '..',
                                        'tools', 'pi'))
        import d24_patch as PT
        self.PT = PT
        self.an = PT.Analog(enabled=False)
        self.an.image = [0x00] * 24 + [0x00]
        self.an.safe_image = [0x01] * 24 + [0x00]
        self.sent = []
        self.fail_on = fail_on          # 1-based index of the load that fails
        self.an.chain = self._chain
        self.an.log = lambda s: None

    def _chain(self, image, what):
        self.sent.append((list(image), what))
        if self.fail_on is not None and len(self.sent) == self.fail_on:
            return False
        self.an.image = list(image)
        return True


def test_three_verified_loads():
    f = FakeAnalog()
    ok, steps = f.an.phantom([2], True, what='MIC 3')
    check('a good sequence reports ok', ok)
    check('a good sequence is exactly three loads', len(f.sent) == 3,
          repr([w for _i, w in f.sent]))
    check('the three loads are steps 1, 3 and 5',
          [s['step'] for s in steps] == [1, 3, 5], repr(steps))
    check('the loads go out in the ruled order',
          [CH.split(img[2]) for img, _w in f.sent]
          == [(1, 0, 0), (1, 1, 0), (0, 1, 0)],
          repr([CH.split(img[2]) for img, _w in f.sent]))


def test_failure_leaves_the_shunt_engaged():
    for fail_on, name in ((1, 'step 1'), (2, 'step 3'), (3, 'step 5')):
        f = FakeAnalog(fail_on=fail_on)
        ok, steps = f.an.phantom([4], True, what='MIC 5')
        check('a failure at %s stops the sequence' % name, not ok)
        last = f.sent[-1][0]
        check('a failure at %s leaves the shunt ENGAGED on that channel' % name,
              CH.split(last[4])[0] == 1,
              '%s -> %s' % (name, [CH.split(img[4]) for img, _w in f.sent]))
        check('a failure at %s re-asserts the shunt explicitly and stops' % name,
              len(f.sent) == fail_on + 1 and 're-asserted' in f.sent[-1][1],
              repr([w for _i, w in f.sent]))
        check('a failure at %s leaves phantom where the last VERIFIED load '
              'put it' % name,
              CH.split(last[4])[1] == (0 if fail_on < 3 else 1),
              repr(CH.split(last[4])))


def main():
    test_encoding_is_byte_identical()
    test_deprecated_alias()
    test_split_is_the_inverse()
    test_safe_image_is_shunted()
    test_the_trailing_byte_is_unreachable()
    test_sequence_on_one_channel()
    test_sequence_restores_an_already_shunted_channel()
    test_sequence_on_a_set_keeps_each_channel_its_own()
    test_phantom_off_direction()
    test_three_verified_loads()
    test_failure_leaves_the_shunt_engaged()
    print()
    if FAILS:
        print('%d check(s) FAILED: %s' % (len(FAILS), ', '.join(FAILS)))
        return 1
    print('all checks passed -- no SPI, no unit, no rails, no phantom applied')
    return 0


if __name__ == '__main__':
    sys.exit(main())
