"""The CHAN_MASK / AUX_MASK reader, witnessed on the part.

Three things in one run, because they are one claim:

  1. THE MASK REACHED THE PART. `_chan_mask` / `_aux_mask` are the words
     the host wrote; `_chan_mask_live` / `_aux_mask_live` are the ones the
     process chain tests, and only CONFIG_COMMIT moves one to the other.
     Reading the STAGED word alone proves the SPI write landed and nothing
     more -- which is exactly the state the firmware was in before
     2026-09-09, when the staged word was all there was.

  2. EVERYTHING THE D24 CONTRACT CAN SILENCE, SILENCED. MainOn=0 and
     Mute=1 on Chan001..Chan024, the four groups, and the three fixed
     sources that reach main (USB, Bluetooth, codec aux), all by NAME out
     of the LANDED D24 map -- so this writes only cells D24 actually has.
     Strips 25-32 are deliberately NOT written: a D24 has no cell for
     them, that is the whole point, and reaching for D32's rows to silence
     them by hand is what `dsp4_silence_2532.py` had to do while
     CFG_CHAN_MASK had no reader.

  3. THE OUTPUT. One second of B_O3 slot 0 = C2_MAIN_ST_OUT off the CM4
     capture path with NO PLAYBACK AT ALL, summarised as a value
     histogram. Needs a bitstream with a capture path pointed at
     MAIN_ST_OUT (`dsp4_logic_maincap`) and the duplex overlay.

  PASS is 0x00000000 for every frame of the capture. Before the fix the
  same run reads 0x7FFFFFE0 -- positive full scale -- for every frame,
  because the eight strips the product does not have were summing into
  C2_RECV_MAIN_L unmuted.

  Usage:  python3 dsp4_mask_witness.py [--no-silence] [--seconds 1]
"""
import argparse, json, struct, subprocess, sys, time
from collections import Counter

BOOT = '/home/app/dspboot'
sys.path.insert(0, BOOT)

ap = argparse.ArgumentParser()
ap.add_argument('--no-silence', action='store_true',
                help='read the masks and capture, write nothing')
ap.add_argument('--seconds', type=int, default=1)
ap.add_argument('--dev', default='hw:dsp4pcm,0')
ap.add_argument('--map', default=BOOT + '/landed-d24.json')
ap.add_argument('--tag', default='mask')
args = ap.parse_args()
sys.argv = ['m']
from dsp4_conform import Part                       # noqa: E402

RATE = 48000
cells = json.load(open(args.map))['cells']

# ---- 1. the live masks, off both parts --------------------------------
parts = {}
for cid in (1, 2):
    # dsp4_conform.Part EXITS rather than raising when it cannot phase,
    # and the parameter link on this graph phases about two boots in
    # three -- so a chip that will not answer must not take the run with
    # it. Retried here, and a chip that stays down is reported and
    # skipped, because the capture below does not need either link.
    for _try in range(4):
        try:
            parts[cid] = Part(cid)
            break
        except (Exception, SystemExit) as e:        # noqa: BLE001
            err = e
            time.sleep(1.5)
    else:
        print('chip %d: NO LINK (%s)' % (cid, err))

print('--- the words the chain reads ---')
for cid, p in parts.items():
    sym = p.sc.sym
    row = []
    for nm in ('_chan_mask', '_chan_mask_live', '_aux_mask', '_aux_mask_live'):
        if nm not in sym:
            row.append('%s=ABSENT' % nm)
            continue
        try:
            row.append('%s=0x%08X' % (nm, p.sc.peek(sym[nm])))
        except Exception as e:                      # noqa: BLE001
            row.append('%s=UNREADABLE(%s)' % (nm, e))
    print('  chip %d  %s' % (cid, '  '.join(row)))

# ---- 2. silence what the D24 contract can silence ---------------------
if not args.no_silence:
    want = []
    for n in range(1, 25):
        want += [('Chan%03dMainOn001' % n, 0), ('Chan%03dMute001' % n, 1)]
    for n in range(1, 5):
        # a group has no MainOn cell in the D24 map; Mute is the whole
        # contract for it.
        want += [('Grp%03dMute001' % n, 1)]
    # The three fixed sources into main. Each has an On cell and a Level
    # cell and no mute; both are written, because Level is a ramped word
    # and On is instant, and either alone leaves a path open.
    for tag in ('Usb001', 'Bt001', 'CodecAux001'):
        want += [(tag + 'On001', 0), (tag + 'Level001', 0)]
    done, missing = 0, []
    for name, val in want:
        if name not in cells:
            missing.append(name)
            continue
        chip, _page, addr = cells[name][0], cells[name][1], cells[name][2]
        if chip not in parts:
            missing.append(name + '(no link)')
            continue
        parts[chip].write(addr, val)
        done += 1
    print('--- silenced %d D24 cells (%d not in the landed map) ---'
          % (done, len(missing)))
    if missing:
        print('    ' + ' '.join(missing[:12])
              + (' ...' if len(missing) > 12 else ''))
    time.sleep(0.7)

# ---- 3. what the main output is doing, with nothing playing -----------
raw = '/tmp/maskwit.raw'
subprocess.run(['arecord', '-D', args.dev, '-f', 'S32_LE', '-c', '2',
                '-r', str(RATE), '-d', str(args.seconds),
                '--period-size=1024', '--buffer-size=8192', '-t', 'raw',
                '-q', raw], stderr=subprocess.DEVNULL)
data = open(raw, 'rb').read()
m = len(data) // 8
f = struct.unpack('<%di' % (m * 2), data[:m * 8])
L, R = f[0::2], f[1::2]
print('--- capture (%s), NOTHING PLAYING, %d frames ---' % (args.tag, m))
verdict = 'NO CAPTURE'
for nm, ch in (('L = C2_MAIN_ST_OUT', L), ('R', R)):
    c = Counter(ch)
    top = ' '.join('%08x x%d' % (v & 0xFFFFFFFF, n) for v, n in c.most_common(3))
    print('  %-20s distinct %-6d  %s' % (nm, len(c), top))
    if nm.startswith('L') and m:
        z = c.get(0, 0)
        print('  %-20s ZERO on %d of %d frames' % ('', z, m))
        verdict = 'MASK WITNESS: PASS' if z == m else 'MASK WITNESS: FAIL'
print(verdict)
