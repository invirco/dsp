"""Prove the ramped-write fix: known word in, read back the whole block.

Writes a known value to C2_PI_IN's level through a ramp profile and reads
level/target/step/frames back. Correct behaviour: target == the value
written, step is a small delta, frames counts down to 0, and level ends
equal to target. The old bug put the STEP in the target slot and the
target value in the level slot.
"""
import sys, struct, time
CHIP = int(sys.argv[1]) if len(sys.argv) > 1 else 2
sys.argv = ['r']
import dsp4_diag as D

# C2_PI_IN block: on, level, target, step, frames
if CHIP == 2:      # C2_PI_IN: on, level, target, step, frames
    ADDR = {'level': 0x951DD, 'target': 0x951DE,
            'step': 0x951DF, 'frames': 0x951E0}
    SPI_ADDR = 0x071C
else:              # C1_GAIN_01: coeff, target, step, frames
    ADDR = {'level': 0x9230C, 'target': 0x9230D,
            'step': 0x9230E, 'frames': 0x9230F}
    SPI_ADDR = 0x0000

link = D.SpiLink('0.0', 1000000, 6 if CHIP == 1 else 24,
                 rdy_gpio=8 if CHIP == 1 else 12)
diag = D.DiagLink(link); diag.resync()

def rd(a):
    for _ in range(14):
        try:
            if diag.read(0xE000) != 0xD5B40001: continue
            v = diag.peek(a)
            if diag.read(0xE000) == 0xD5B40001: return v
        except IOError: pass
    return None

def show(tag):
    out = {}
    for n, a in ADDR.items():
        v = rd(a)
        out[n] = v
        f = struct.unpack('<f', struct.pack('<I', v))[0] if v is not None else None
        print(f'  {tag:9s} {n:7s} = ' + ('?' if v is None else f'0x{v:08X}  {f:.9g}'))
    return out

for want in (0.5, 2.0, 1.0):
    w = struct.unpack('<I', struct.pack('<f', want))[0]
    print(f'--- write {want} (0x{w:08X}) with ramp_id 1 ---')
    link.write(SPI_ADDR, w, 1)
    time.sleep(0.05)
    show('mid-ramp')
    time.sleep(0.6)
    st = show('settled')
    t = st['target']
    if t is None:
        print('  UNREADABLE'); continue
    tf = struct.unpack('<f', struct.pack('<I', t))[0]
    lf = struct.unpack('<f', struct.pack('<I', st['level']))[0]
    ok = abs(tf - want) < 1e-6 and abs(lf - want) < 1e-3
    print(f'  => target {tf:.9g} level {lf:.9g}  {"OK" if ok else "WRONG"}')
