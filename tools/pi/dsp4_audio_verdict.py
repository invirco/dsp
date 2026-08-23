"""Judge the card by AUDIO TRUTH, not by how responsive the link feels.

usage: audio_verdict.py <window_s> [proc_passes_addr_hex]

FRAME_COUNT is incremented by the block ISR, so it advancing proves the
SPORT/DMA transport is running -- NOT that the main loop finished its
work. _proc_passes counts completed block passes, so comparing the two
is what actually says "real time":

  frames/s ~ 1500 and passes/s ~ 1500  -> REAL TIME
  frames/s ~ 1500 and passes/s < that  -> transport fine, loop OVER BUDGET

Three link outcomes are kept distinct: UNKNOWN (link never answered) says
nothing about the audio, and conflating it with dead is the error that
made a loaded-but-running graph look like a hang.
"""
import sys, time
WINDOW = float(sys.argv[1]) if len(sys.argv) > 1 else 3.0
PASSES = int(sys.argv[2], 16) if len(sys.argv) > 2 and sys.argv[2] != '-' else None
CHIP = int(sys.argv[3]) if len(sys.argv) > 3 else 1
sys.argv = ['v']
import dsp4_diag as D

link = D.SpiLink('0.0', 1000000, 6 if CHIP == 1 else 24,
                 rdy_gpio=8 if CHIP == 1 else 12)
diag = D.DiagLink(link); diag.resync()

def read_block(patience=40):
    for _ in range(patience):
        try:
            if diag.read(0xE000) != 0xD5B40001:
                continue
            fc = diag.read(0xE004); st = diag.read(0xE002)
            dm = diag.read(0xE013); se = diag.read(0xE012)
            pp = diag.peek(PASSES) if PASSES else None
            if diag.read(0xE000) != 0xD5B40001:
                continue                      # link moved under us
            return fc, dm, se, st, pp
        except IOError:
            continue
    return None

a = read_block()
if a is None:
    print('UNKNOWN: link never answered — says nothing about the audio'); sys.exit(2)
t0 = time.time(); time.sleep(WINDOW); b = read_block()
if b is None:
    print(f'UNKNOWN: link answered once (FRAME_COUNT {a[0]}) then stopped'); sys.exit(2)
dt = time.time() - t0

frate = (b[0] - a[0]) / dt
print(f'FRAME_COUNT {a[0]} -> {b[0]}  = {frate:.0f}/s (expect ~1500)')
prate = None
if PASSES and a[4] is not None and b[4] is not None:
    prate = (b[4] - a[4]) / dt
    print(f'_proc_passes {a[4]} -> {b[4]}  = {prate:.0f}/s')
print(f'DMA0_STAT 0x{b[1]:08X}  SPORT0_ERR_A 0x{b[2]:08X}  BOOT_STAGE {b[3]}')

transport = frate > 1200 and b[2] == 0
if not transport:
    print('AUDIO_DEAD'); sys.exit(1)
if prate is None:
    print('AUDIO_ALIVE (transport only — no pass rate available)'); sys.exit(0)
if prate > 1450:            # 97% of 1500 — below this it is dropping blocks
    print(f'REAL_TIME ({prate:.0f} passes/s)'); sys.exit(0)
print(f'OVER_BUDGET: transport {frate:.0f}/s but only {prate:.0f} passes/s'); sys.exit(1)
