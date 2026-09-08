"""Put the MAIN bus in a PASS-THROUGH state for the Pi loop, addressing
every cell BY NAME out of the landed contract.

Seventeen sources sum into C2_MIX_MAIN_L (the graph's own input list):
    C2_RECV_MAIN_L            chip 1's whole 32-strip bus
    C2_GRP_COMP_01..04        the four group buses
    C2_USB_IN C2_BT_IN C2_CODEC_AUX_IN C2_PI_IN
    C2_SNK_IN_01..08          the snake returns
Every one of them except C2_PI_IN is silenced here. The snake returns have
NO cell in the landed map at all -- nothing on the contract can silence
them -- so they are measured rather than assumed.
"""
import json, sys, time
sys.argv = ['p']
sys.path.insert(0, '/home/app/dspboot')
from dsp4_conform import Part, f32

L = json.load(open('/home/app/dspboot/landed-d24.json'))['cells']


def w(part, cell, val, ramp=0):
    if cell not in L:
        return False
    part.write(L[cell][2], val, ramp)
    return True


def silence_chip1(p1):
    """Chip 1 contributes through C2_RECV_MAIN_L. Take every strip off the
    main bus AND mute it -- two independent ways, because one cell being
    inert would otherwise leave the bus live and look like a pedestal."""
    n = 0
    for s in range(1, 33):
        n += w(p1, 'Chan%03dMainOn001' % s, 0)
        # MUTE IS A BOOL on this wire (wire-units.csv: 'bool 0/1 ->
        # coefficient fold to exact 0'), so the word is 1, not f32(1.0).
        n += w(p1, 'Chan%03dMute001' % s, 1)
    return n


def silence_chip2(p2, keep='Pi'):
    done = {}
    for fam in ('Usb', 'Bt', 'CodecAux', 'Pi'):
        on = '%s001On001' % fam
        done[on] = w(p2, on, 1 if fam == keep else 0)
    for g in range(1, 5):
        done['Grp%03dMute001' % g] = w(p2, 'Grp%03dMute001' % g, 1)
    # the injected path, wide open
    done['Pi001Level001'] = w(p2, 'Pi001Level001', f32(1.0), 4)
    # main chain to unity/bypass
    done['Main001Level001'] = w(p2, 'Main001Level001', f32(1.0), 4)
    done['Main001Mute001'] = w(p2, 'Main001Mute001', 0)
    done['Main001Delay001'] = w(p2, 'Main001Delay001', f32(0.0))
    for b in range(1, 29):
        w(p2, 'Main%03dGeq%03d' % (1, b), f32(0.0))
    return done


def main():
    p1, p2 = Part(1), Part(2)
    n1 = silence_chip1(p1)
    d2 = silence_chip2(p2)
    time.sleep(1.0)
    print('chip1: %d strip cells written' % n1)
    missing = [k for k, v in d2.items() if not v]
    print('chip2: %d cells written, %s'
          % (sum(1 for v in d2.values() if v),
             ('missing from the contract: ' + ', '.join(missing)) if missing
             else 'all present in the contract'))
    for sym in ('_buf_C2_MIX_MAIN_L', '_buf_C2_MAIN_FDR', '_buf_C2_MAIN_DLY',
                '_buf_C2_MAIN_ST_OUT'):
        if sym in p2.sc.sym:
            v = p2.sc.peek(p2.sc.sym[sym])
            print('  %-24s %s' % (sym, hex(v)))


if __name__ == '__main__':
    main()
