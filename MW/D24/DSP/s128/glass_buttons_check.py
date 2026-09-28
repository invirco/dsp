#!/usr/bin/env python3
"""glass_buttons_check.py -- every screen that says "press ENTER" has an ENTER
button on it (S128 hotfix).

Runs the analog station's DRY RUN with a real `live.json` behind it, watches
that file, and checks one rule against every distinct screen the pass writes:

    an instruction that asks for ENTER must come with `enter` in `buttons`.

That rule is what broke. `buttons` is chosen from the STATE, and the pipeline
leaves the screen on `verdict` -- the next patch's instruction is written by
`announce()` and the last patch's banner by `record()` over the top of it -- so
every patch after the first began in a state whose button list is `['pause']`.
Only the pre-armed tone rows climbed back out of it, which is why gain steps,
the EIN plug and every no-tone row had no ENTER at all.

It also reports WHICH ROW TYPES were seen, because the point of the check is
coverage: a run that only walked tone rows would have passed the rule before
the fix.

    glass_buttons_check.py                       the full list
    glass_buttons_check.py --block K1 --block K5 two leads, quicker
"""
import argparse
import contextlib
import io
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..', '..'))
PI = os.path.join(ROOT, 'tools', 'pi')
sys.path.insert(0, PI)

# What a screen is asking for, from its own words. Nothing here reads the patch
# list: the check is on what the WORKER is told, which is the only thing that
# can disagree with the buttons they are given.
WANTS_ENTER = ('press ENTER', 'press ENTER again')


# The lead each row is made with is what the operator has in their hand, and it
# is what the hub asked for coverage of. `expect` and `gain_code` are what
# decide the code path inside `Station.detect` -- in particular `prearm_ok` is
# true ONLY for a tone row with no gain code, which is the whole class that used
# to recover its ENTER button and the reason the fault looked intermittent.
LEAD_KIND = {'K1': 'XLR', 'K2': 'TRS jack', 'K3': 'mini-jack',
             'K4': 'line (jack-to-XLR)', 'K5': 'EIN plug (150 ohm)'}


def row_kind(r):
    gain = str(r.get('gain_code') or '') != ''
    lead = LEAD_KIND.get(r.get('lead'), r.get('lead') or '?')
    what = {'tone': 'tone', 'noise': 'no-tone', 'null': 'null'}.get(
        r.get('expect'), str(r.get('expect')))
    return '%s, %s%s' % (lead, what, ', GAIN STEP' if gain else '')


def kinds(rows):
    """Every row type the list contains, and how many of each."""
    out = {}
    for r in rows:
        k = row_kind(r)
        out[k] = out.get(k, 0) + 1
    return out


def by_instruction(plist):
    """The instruction each row puts on the glass -> that row's type.

    Built from `d24_live` the same way the station builds it, so a screen can
    be attributed to the row that wrote it without the station being asked.
    """
    import d24_live as LV
    out = {}
    for r in plist.paths:
        for confirm in (True, False):
            out.setdefault(LV.instruction_for(r, confirm), row_kind(r))
            if r.get('expect') == 'noise':
                out.setdefault(LV.swap_for_plug(r['in'], confirm), row_kind(r))
    return out


def record_every_screen():
    """Every screen the pass writes, not a sample of them.

    Watching `live.json` from outside is a poll, and a poll misses screens: the
    dry run writes one every few virtual milliseconds and a 20 ms watcher caught
    103 of 245. The rule this checks is about the screens that ARE written, so
    the recorder hooks the writer -- `Live._flush`, the one place every change
    goes through -- and sees all of them.
    """
    import d24_live as LV
    out = []
    original = LV.Live._flush

    def flush(self):
        original(self)
        out.append(dict(self.d))
    LV.Live._flush = flush
    return out, (lambda: setattr(LV.Live, '_flush', original))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--list-dir', default=os.path.join(ROOT, 'MW/D24/DSP/s121'))
    ap.add_argument('--block', action='append')
    ap.add_argument('--fault', action='append')
    ap.add_argument('--verbose', action='store_true')
    a = ap.parse_args()

    import d24_patch as PT
    plist = PT.PatchList(PT.find_list_dir(a.list_dir))
    print('list: %s -- %d paths, row types: %s'
          % (plist.dir, len(plist.paths),
             ', '.join('%s %d' % kv for kv in sorted(kinds(plist.paths).items()))))

    tmp = tempfile.mkdtemp(prefix='s128-glass-')
    every, unhook = record_every_screen()
    # `--confirm-enter` IS THE MODE THIS CHECK IS ABOUT, and since PW's ruling
    # of 2026-09-28 it has to be asked for: signal arrival is the go-ahead, so a
    # default run puts no ENTER on any screen and there would be nothing here to
    # check. The ENTER path still exists -- it is what a before/after timing run
    # uses -- and S128's fault (an instruction that says "press ENTER" on a
    # screen with no ENTER button) is still a fault in it. The auto path has its
    # own check, S145's `patch_auto_advance_check.py`, which asserts the
    # opposite: no ENTER anywhere, and NO SIGNAL on every waiting screen.
    argv = ['--simulate', '--confirm-enter',
            '--list-dir', a.list_dir, '--live', tmp, '--dir', tmp]
    for b in (a.block or []):
        argv += ['--block', b]
    for f in (a.fault or []):
        argv += ['--fault', f]
    out = io.StringIO()
    try:
        with contextlib.redirect_stdout(out):
            PT.main(argv)
    finally:
        unhook()
    if a.verbose:
        print(out.getvalue()[-2000:])
    # Collapse only consecutive identical screens: two different patches that
    # happen to draw the same thing are still two screens, but the heartbeat
    # rewrites the same one twice a second and those are not.
    seen, last = [], None
    for d in every:
        key = (d.get('state'), (d.get('instruction') or '').strip(),
               (d.get('status') or '').strip(),
               (d.get('banner') or ''), tuple(d.get('buttons') or []))
        if key != last:
            last = key
            seen.append(d)

    bad, asked = [], 0
    states = {}
    attrib = by_instruction(plist)
    covered = {}
    for d in seen:
        instr = (d.get('instruction') or '')
        st = d.get('state')
        states[st] = states.get(st, 0) + 1
        if not any(w in instr for w in WANTS_ENTER):
            continue
        # A SCREEN WHERE THE UNIT IS WORKING IS NOT ASKING. `CHECKING`,
        # `STARTING` and `STOPPING` leave the last instruction up while the
        # unit reads, and there must be no ENTER on them -- the operator has
        # already pressed it. (Not `busy`: that flag is true for WAITING too,
        # because it means "a run is going", not "the unit is working".)
        # Every other state carrying an ENTER instruction IS asking, and that
        # includes `verdict`, which is the state the bug left behind.
        if d.get('state') in ('checking', 'starting', 'stopping'):
            continue
        asked += 1
        kind = attrib.get(instr.strip())
        if kind is None:
            # Not one of the list's own patch instructions: the find-a-loop
            # walk's "move the lead" pages, the wrong-socket retry, the plug
            # swap. Keyed by the words so the table names them.
            kind = 'off-list: %s' % instr.strip()[:46]
        ok = 'enter' in (d.get('buttons') or [])
        c = covered.setdefault(kind, [0, 0])
        c[0] += 1
        c[1] += 1 if ok else 0
        if not ok:
            bad.append(d)
    print('%d distinct screens; states seen: %s'
          % (len(seen), ', '.join('%s %d' % kv for kv in sorted(states.items()))))
    print('%d of them asked for ENTER. By row type, screens with an ENTER '
          'button / screens that asked:' % asked)
    for k in sorted(covered):
        c = covered[k]
        print('   %-34s %3d / %3d %s' % (k, c[1], c[0],
                                         '' if c[1] == c[0] else '  <-- SHORT'))
    if a.verbose:
        for d in seen:
            print('   [%-9s] %-14s %-30s %s'
                  % (d.get('state'), '+'.join(d.get('buttons') or []),
                     (d.get('status') or '')[:30], (d.get('instruction') or '')[:70]))
    if bad:
        print('\nFAIL: %d screen(s) asked for ENTER with no ENTER button:' % len(bad))
        for d in bad[:20]:
            print('   [%s] buttons=%s status=%r :: %s'
                  % (d.get('state'), d.get('buttons'), d.get('status'),
                     d.get('instruction')))
        return 1
    if not asked:
        print('\nFAIL: no screen asked for ENTER at all -- this check proved '
              'nothing. Was the list empty, or auto-advance on?')
        return 1
    print('\nOK: every screen that asks for ENTER has one.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
