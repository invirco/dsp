#!/usr/bin/env python3
"""factory_log_table.py -- every patch prompt of every auto-advance run in
factory.log, one row each, and the stall counts per run (S157 item 1).

    factory_log_table.py factory.log                 the table + the counts
    factory_log_table.py factory.log --counts        the counts only
    factory_log_table.py factory.log --since 2026-09-30T18:00:00Z

A RUN is one `D24 RUN ALL -- ... -- <stamp>` header to the next. Runs before
the auto-advance landed (the first `rise after` line, 2026-09-29 15:16Z) are
skipped: ENTER decided those, so they say nothing about the detector.

A PROMPT is one `== PATCH: <prompt>  (lead Kn)` header. The runner's own lines
for it are `   .. P<n>: ...` up to the next header; `P<n> VERDICT: ...` lines
are the PREVIOUS patch's verdict, printed late by the pipeline, and are hung
on that patch id, not on the prompt they sit under.

Per prompt:
  kind     fresh      a different input from the prompt before
           other-end  same input, different output (the parked-end shape)
           repeat     same input, same output (a re-prompt of the same patch)
           after-noise  a fresh socket straight after a 150 ohm step
           noise      the 150 ohm step itself
           trs / mini-jack / line   by lead (K2 / K3 / K4)
           loop-walk  the find-a-loop walk moving P1 to another socket
  outcome  rise / drop / nosignal / timeout / reprompt / stopped / (none)
  hot0     True/False where the S155 prompt line exists, else '' (older runs)
  removal  'seen' where a "lead came out" line exists
  wrong    the wrong-socket claims made while this prompt was up
  t_s      prompt-to-stable time for a rise/drop, wait for a NO SIGNAL press
  cause    see classify()
The STALL count is prompts that raised the timeout question ("nothing has
reached ... asking"), which is what the hub counted.
"""
import argparse
import re
import sys

RUN_RE = re.compile(r'^D24 RUN ALL -- .* -- (\d{4}-\d\d-\d\dT[\d:]+Z)')
HDR_RE = re.compile(r'^== PATCH: (.*?)\s+\(lead (K\d)\)')
EV_RE = re.compile(r'^   \.\. (P\d+):\s?(.*)$')
VERDICT_RE = re.compile(r'^   \.\. (P\d+) (PASS|FAIL|NO DATA|SKIPPED|IGNORED)'
                        r'(?::\s?(.*))?$')
ENDS = ('STOPPED', 'the pass stopped at', 'Paused')


def parse_prompt(p):
    """(out, in, expect) from a prompt line, in the list's words."""
    m = re.match(r'Patch (.+?) to (.+?)(?:, with .*)?$', p)
    if m:
        return m.group(1), m.group(2), 'tone'
    m = re.match(r'(?:Fit the 150 ohm terminator in|Put .*150 ohm.* into) '
                 r'(.+)$', p)
    if m:
        return '', m.group(1), 'noise'
    return '', p, '?'


def runs(lines):
    cur = None
    for i, ln in enumerate(lines):
        m = RUN_RE.match(ln)
        if m:
            if cur:
                yield cur
            cur = dict(stamp=m.group(1), line=i + 1, body=[])
        elif cur is not None:
            cur['body'].append((i + 1, ln))
    if cur:
        yield cur


def prompts(run):
    out = []
    cur = None
    verdicts = {}
    for n, ln in run['body']:
        if ln.startswith('   [') and not ln.startswith('   [nosignal') \
                and not ln.startswith('   [done') \
                and not ln.startswith('   [notlit'):
            continue                      # background station output
        m = HDR_RE.match(ln)
        if m:
            cur = dict(prompt=m.group(1), lead=m.group(2), line=n, ev=[],
                       pid=None)
            out.append(cur)
            continue
        m = VERDICT_RE.match(ln)
        if m:
            verdicts.setdefault(m.group(1), []).append(
                (m.group(2), m.group(3) or ''))
            continue
        m = EV_RE.match(ln)
        if m and cur is not None:
            if cur['pid'] is None:
                cur['pid'] = m.group(1)
            if m.group(1) == cur['pid']:
                cur['ev'].append(m.group(2))
            continue
        if cur is not None and ln.startswith(ENDS):
            cur['ev'].append('STOPPED')
    return out, verdicts


def kind_of(p, prev, prev_prev_noise):
    out, inp, expect = parse_prompt(p['prompt'])
    if expect == 'noise':
        return 'noise'
    if p['lead'] == 'K3':
        return 'mini-jack'
    if p['lead'] == 'K2':
        return 'trs'
    if p['lead'] == 'K4':
        return 'line'
    if prev is None:
        return 'fresh'
    pout, pin, pexp = parse_prompt(prev['prompt'])
    if prev.get('pid') == p.get('pid') and p.get('pid') == 'P1' \
            and pin != inp:
        return 'loop-walk'
    if pexp == 'noise' and pin != inp:
        return 'after-noise'
    if pin == inp and pout == out:
        return 'repeat'
    if pin == inp:
        return 'other-end'
    return 'fresh'


def outcome_of(p):
    ev = p['ev']
    o = dict(outcome='', t_s='', hot0='', removal='', wrong=[], stall=False,
             went_away=0)
    for e in ev:
        m = re.search(r'hot0 (True|False)', e)
        if m:
            o['hot0'] = m.group(1)
        if e.startswith('the lead came out of'):
            o['removal'] = 'seen'
        m = re.match(r'the tone is on (.+?), not (.+)$', e)
        if m:
            o['wrong'].append(m.group(1))
        if e.startswith('nothing has reached'):
            o['stall'] = True
        if 'the signal went away again' in e:
            o['went_away'] += 1
        m = re.match(r'(rise|drop) after (\d+) ms', e)
        if m:
            o['outcome'] = m.group(1)
            o['t_s'] = '%.1f' % (int(m.group(2)) / 1000.0)
        m = re.match(r'NO SIGNAL pressed on .* after ([\d.]+) s', e)
        if m:
            o['outcome'] = 'nosignal'
            o['t_s'] = m.group(1)
        if 'prompting again' in e and not o['outcome']:
            o['outcome'] = 'reprompt'
        if e == 'STOPPED' and not o['outcome']:
            o['outcome'] = 'stopped'
    if not o['outcome'] and o['stall']:
        o['outcome'] = 'timeout'
    return o


def classify(p, o, prev, kind, verdict, same_input):
    """The cause class, in the words of the S157 block.

    runner:peak-latch  arrival / removal / "already carrying" read off the
                       strip peak-hold meter and not seen: a fresh socket
                       with no arrival and no removal line (hot0 on an idle
                       or still-draining lane), or a same-input patch whose
                       removal or rise never cleared the latch's history
    runner:loop-walk   the find-a-loop walk moved P1 to another socket by
                       itself, with the lead still where it was asked for
    runner:wrong-claim a wrong-socket claim on a patch that then arrived
                       where it was asked for (a latch, not a lead)
    wrong-socket       claims that persisted and never arrived: a lead
                       really elsewhere, or a latch -- the log cannot tell
    slow-hands         the timeout was raised and the lead then arrived
    unit               arrived and graded FAIL / NO DATA on the reading
    ok                 a clean rise or drop, graded PASS
    """
    graded = verdict[0] if verdict else ''
    if o['outcome'] in ('rise', 'drop') and not o['stall']:
        if graded in ('FAIL', 'NO DATA'):
            return 'unit'
        return 'ok'
    if kind == 'loop-walk':
        return 'runner:loop-walk'
    if o['wrong'] and o['outcome'] in ('rise', 'drop'):
        return 'runner:wrong-claim'
    if o['stall'] and o['outcome'] in ('rise', 'drop'):
        return 'slow-hands'
    if o['hot0'] == 'True' or (same_input and o['outcome'] != 'rise'):
        return 'runner:peak-latch'
    if not o['removal'] and not o['wrong'] and o['stall']:
        return 'runner:peak-latch'
    if o['wrong']:
        return 'wrong-socket'
    return 'unresolved'


def table(lines, since=None):
    out = []
    for run in runs(lines):
        ps, verdicts = prompts(run)
        if not any('rise after' in e or 'drop after' in e
                   for p in ps for e in p['ev']):
            if not any(e.startswith('nothing has reached')
                       for p in ps for e in p['ev']):
                continue                # an ENTER-era run, or no patching
        if since and run['stamp'] < since:
            continue
        prev = None
        first_cause = {}
        for p in ps:
            k = kind_of(p, prev, False)
            o = outcome_of(p)
            v = verdicts.get(p['pid'] or '', [])
            v = v[-1] if v else None
            same_input = bool(prev) and parse_prompt(prev['prompt'])[1] == \
                parse_prompt(p['prompt'])[1] and k not in ('noise',)
            key = (p['pid'], p['prompt'])
            c = classify(p, o, prev, k, v, same_input)
            if k == 'repeat' and key in first_cause:
                c = first_cause[key]
            first_cause.setdefault(key, c)
            # DID THE RUNNER MOVE ON BY ITSELF? A re-prompt it issued, a
            # NO DATA after its own retries, or the loop walk.
            moved = (o['outcome'] in ('reprompt',) or k == 'loop-walk'
                     or (v and v[0] == 'NO DATA' and 'attempt' in v[1]))
            out.append(dict(run=run['stamp'], pid=p['pid'] or '',
                            prompt=p['prompt'], lead=p['lead'], kind=k,
                            verdict=(v[0] if v else ''),
                            why=(v[1] if v else ''), cause=c,
                            moved_on=bool(moved), **o))
            prev = p
    return out


def counts(rows):
    by = {}
    for r in rows:
        c = by.setdefault(r['run'], dict(prompts=0, rises=0, drops=0,
                                         stalls=0, nosignal=0, wrong=0,
                                         moved=0))
        c['moved'] += bool(r['moved_on'])
        c['prompts'] += 1
        c['rises'] += r['outcome'] == 'rise'
        c['drops'] += r['outcome'] == 'drop'
        c['stalls'] += bool(r['stall'])
        c['nosignal'] += r['outcome'] == 'nosignal'
        c['wrong'] += bool(r['wrong'])
    return by


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('log')
    ap.add_argument('--counts', action='store_true')
    ap.add_argument('--since')
    a = ap.parse_args(argv)
    with open(a.log, errors='replace') as fh:
        lines = fh.read().splitlines()
    rows = table(lines, a.since)
    if not a.counts:
        print('| run | patch | prompt | kind | outcome | t s | hot0 | removal '
              '| wrong-socket claims | verdict | cause |')
        print('|---|---|---|---|---|---|---|---|---|---|---|')
        for r in rows:
            print('| %s | %s | %s | %s | %s%s | %s | %s | %s | %s | %s | %s | %s |'
                  % (r['run'][5:16], r['pid'], r['prompt'], r['kind'],
                     r['outcome'] or '-', ' (stall)' if r['stall'] and
                     r['outcome'] != 'timeout' else '', r['t_s'], r['hot0'],
                     r['removal'], ', '.join(r['wrong']), r['verdict'],
                     r['cause'], 'YES' if r['moved_on'] else ''))
        print()
    print('| run | prompts | rises | drops | stalls (timeout raised) | '
          'NO SIGNAL | wrong-socket claims | runner moved on by itself |')
    print('|---|---|---|---|---|---|---|---|')
    for run, c in counts(rows).items():
        print('| %s | %d | %d | %d | %d | %d | %d | %d |'
              % (run, c['prompts'], c['rises'], c['drops'], c['stalls'],
                 c['nosignal'], c['wrong'], c['moved']))
    causes = {}
    for r in rows:
        if r['cause'] != 'ok':
            causes[r['cause']] = causes.get(r['cause'], 0) + 1
    print()
    print('causes (every prompt that did not end in a clean rise/drop): %s'
          % ', '.join('%s %d' % kv for kv in sorted(causes.items())))
    return 0


if __name__ == '__main__':
    sys.exit(main())
