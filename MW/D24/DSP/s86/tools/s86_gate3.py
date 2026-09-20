#!/usr/bin/env python3
"""s86_gate3.py — THE EIN ROW, on lanes that are now known to carry samples.

S54's T4 recipe, driven from `s54lib`, but per XLR rather than MIC 5 only, so
the second witness the dispatch asks for can be taken on the same pass and on
the same 595 image discipline: every register muted except the one under test,
phantom off, the INSTR byte 0x00.

EIN in dBu at the input (the S55/S57-R convention, `s55_ingest.py`):

    EIN = P_dBFS + 3.01 + 23.13 - G_loop(code)

with P the TEST_MEAS NoiseResult, 3.01 the FS-sine reference, 23.13 dBu the
measured DAC full scale at J45, and G_loop the channel's OWN loop gain at that
code. **G_loop is a per-channel calibration and only MIC 5's is on record**
(S54 T1, 64-code sweep, with the loop cable in place): 58.717 dB at code 63,
5.578 dB at code 0. A channel with no loop gain of its own is reported in
dBFS, and its dBu column is marked as borrowed rather than quietly printed.

THE FIXTURE IS NOT ASSUMED. The first thing this does is put the S54 loop
check on the record: 1 kHz at -20 dBFS into AUX 1 with the preamp at code 0.
With the loop cable on J25 that arrives at -14.42 dBFS coherent peak (S54).
With 150 ohm across pins 2-3 and the cable off it must not arrive at all. The
reading is printed whatever it says and the rows are labelled from it.
"""
import json
import math
import os
import sys
import time

_ARGV = list(sys.argv)
os.environ.setdefault('SYMDIR', '/home/app/s83tn')
sys.path.insert(0, '/home/app/s55')
sys.path.insert(0, '/home/app/s54')
import s54lib as T                                                  # noqa: E402
import s55_chain as CH                                              # noqa: E402
import d24_inputs as D24                                            # noqa: E402

P = lambda *a: print(*a, flush=True)                                # noqa: E731

# S54 T1, MIC 5, 64-code sweep with the loop in place.
MIC5_GLOOP = {63: 58.717, 0: 5.578}
DAC_FS_DBU = 23.13
FS_SINE = 3.0103

# what to take, in order: (xlr, panel mic, strip, 595 send position)
def targets():
    out = []
    for want in ('J25', 'J18'):
        x = [q for q in D24.XLRS if q.xlr == want][0]
        out.append((x, x.strip(D24.D24_INPUT_PATCH)))
    return out


def chain_only(send_pos, code, mute=0):
    """The 25-byte image with ONE register open. s54lib.Rig.chain does this
    for MIC 5 alone; this is the same image with the position as a parameter."""
    img = [0x01] * 25
    img[send_pos] = CH.byte(mute=mute, gain=code)
    img[24] = 0x00
    ok = False
    for _ in range(4):
        ok, got = CH.send(img)
        if ok:
            break
    if not ok:
        raise SystemExit('595 image for send %d code %d NOT VERIFIED' % (send_pos, code))
    return img


def main():
    outdir = '/home/app/s86'
    os.makedirs(outdir, exist_ok=True)
    R = T.Rig(os.path.join(outdir, 's86_gate3.jsonl'))
    rec = {'fixture_check': None, 'rows': []}

    tg = targets()
    P('targets:')
    for x, strip in tg:
        P('  %-4s panel MIC %-2d  preamp %-4s  ADC %-4s ad[%d] slot %d  rx entry %-2d  -> strip %d'
          % (x.xlr, x.panel, x.preamp, x.adc, x.ad, x.slot, x.rx, strip))

    # ---- the fixture check, before any row is labelled -------------------
    mic5, mic5_strip = tg[0]
    P('\n=== fixture check: is the S54 loop cable still on %s? ===' % mic5.xlr)
    chain_only(mic5.send, 0)
    R.code = 0
    R.meas(mic5_strip)
    R.osc(1000.0, -20.0)
    m = R.windows(4, settle_windows=8, tag='s86_loopcheck')
    coh = T.summ(m, 'coh_pk_dbfs')
    rms = T.summ(m, 'rms')
    loop_in = coh is not None and coh > -40.0
    P('  coherent peak %.2f dBFS, RmsResult %.2f dBFS   (S54 with the loop: -14.42)'
      % (coh if coh is not None else float('nan'), rms))
    P('  VERDICT: %s' % ('THE LOOP CABLE IS STILL ON — this is NOT the 150 ohm row'
                         if loop_in else
                         'no tone arrives — the loop is off, the source is whatever is fitted'))
    rec['fixture_check'] = {'coh_pk_dbfs': coh, 'rms_dbfs': rms, 'loop_in': loop_in}
    R.osc(on=False)
    time.sleep(0.5)

    # ---- the rows --------------------------------------------------------
    for x, strip in tg:
        for code in (63, 0):
            P('\n=== %s (panel MIC %d) strip %d, code %d ===' % (x.xlr, x.panel, strip, code))
            chain_only(x.send, code)
            R.code = code
            R.meas(strip)
            m = R.windows(8, settle_windows=16, tag='s86_ein_%s_c%d' % (x.xlr, code))
            rms = T.summ(m, 'rms')
            nse = T.summ(m, 'noise')
            spread = T.spread(m, 'rms')
            row = {'xlr': x.xlr, 'panel': x.panel, 'strip': strip, 'adc': x.adc,
                   'ad': x.ad, 'slot': x.slot, 'rx': x.rx, 'send': x.send,
                   'code': code, 'rms_dbfs': rms, 'noise_dbfs': nse,
                   'rms_spread_db': spread,
                   'windows': [r['rms'] for r in m['rows']]}
            g = MIC5_GLOOP.get(code) if x.xlr == 'J25' else None
            if g is not None:
                row['g_loop_db'] = g
                row['ein_dbu'] = nse + FS_SINE + DAC_FS_DBU - g
                P('  RmsResult %.2f dBFS   NoiseResult %.2f dBFS   spread %.2f dB'
                  % (rms, nse, spread))
                P('  EIN = %.2f + %.2f + %.2f - %.3f = %.2f dBu at the input'
                  % (nse, FS_SINE, DAC_FS_DBU, g, row['ein_dbu']))
            else:
                borrowed = nse + FS_SINE + DAC_FS_DBU - MIC5_GLOOP[code]
                row['ein_dbu_borrowed'] = borrowed
                P('  RmsResult %.2f dBFS   NoiseResult %.2f dBFS   spread %.2f dB'
                  % (rms, nse, spread))
                P("  no loop gain of its own on record — on MIC 5's G_loop that"
                  " would read %.2f dBu, BORROWED, not a measurement" % borrowed)
            rec['rows'].append(row)

    json.dump(rec, open(os.path.join(outdir, 's86_gate3.json'), 'w'), indent=1)
    P('\nwrote %s/s86_gate3.json' % outdir)


if __name__ == '__main__':
    main()
