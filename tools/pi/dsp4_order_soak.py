"""Sample-order soak for the CM4 link at 48 kHz: 0 reorders, 0 drops.

The 2026-09-08 "the link reorders samples" finding was withdrawn as an
artefact of running the Pi at 192 kHz against a bitstream whose Pi link
was not 192 kHz. This re-runs the question at 48 kHz on a bitstream that
NAMES its own configuration, and it streams instead of buffering: the
stimulus is generated into aplay's stdin and the capture is verified out
of arecord's stdout, so a ten-minute run costs no disk and the verdict is
a running count rather than a post-hoc pass over half a gigabyte.

The stimulus is a per-sample counter that wraps at WRAP, so every word
carries its own index. Once locked, the next word must be exactly
+STEP (modulo the wrap); anything else is a reorder, a drop or a
duplicate, and each is counted separately:

    drop        the counter jumped FORWARD by more than one step
    reorder     the counter went BACKWARD
    stall       the counter repeated
    dropout     a zero word BETWEEN counter words

A single count above zero fails the gate. Silence at the start (before
the loop fills) and the trailing silence after aplay finishes -- arecord
is asked for two seconds more than the stimulus, deliberately, so the
capture cannot end early -- are not defects and are not counted. A zero
run is only charged once counter words resume after it.
"""
import os, struct, subprocess, sys, threading, time

RATE    = 48000                        # 48 kHz only -- see dsp4_loop_latency.py
SECS    = int(os.environ.get('SECS', 600))
DEV     = os.environ.get('DEV', 'hw:dsp4pcm,0')
PERIOD  = os.environ.get('PERIOD', '1024')
BUFFER  = os.environ.get('BUFFER', '8192')
STEP    = 256
WRAP    = 65535                        # counter indices 1..65535, never 0
CHUNK   = 4096                         # frames per write

TOTAL = RATE * SECS


def feed(pipe):
    """Generate the counter straight into aplay, chunk by chunk.

    Count in SAMPLES, not in chunks-per-second: RATE // CHUNK truncates
    (48000 // 4096 = 11), and pacing the generator by that ratio silently
    delivers 45,056 samples per nominal second. A 630 s request then runs
    591 s and a ten-minute gate is missed by nine seconds while every
    line of the report still says 630.
    """
    i = 0
    try:
        while i < TOTAL:
            buf = bytearray()
            for _ in range(min(CHUNK, TOTAL - i)):
                v = ((i % WRAP) + 1) * STEP
                buf += struct.pack('<ii', v, v)
                i += 1
            pipe.write(bytes(buf))
        pipe.flush()
    except (BrokenPipeError, ValueError):
        pass
    finally:
        try: pipe.close()
        except Exception: pass


rec = subprocess.Popen(
    ['arecord', '-D', DEV, '-f', 'S32_LE', '-c', '2', '-r', str(RATE),
     '-d', str(SECS + 2), '--period-size=' + PERIOD, '--buffer-size=' + BUFFER,
     '-t', 'raw', '-q', '-'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
time.sleep(0.3)
pl = subprocess.Popen(
    ['aplay', '-D', DEV, '-f', 'S32_LE', '-c', '2', '-r', str(RATE),
     '--period-size=' + PERIOD, '--buffer-size=' + BUFFER, '-t', 'raw', '-q', '-'],
    stdin=subprocess.PIPE, stderr=subprocess.PIPE)
threading.Thread(target=feed, args=(pl.stdin,), daemon=True).start()

print(f'order soak: {SECS} s at {RATE} Hz on {DEV}, counter step {STEP} wrap {WRAP}')
t0 = time.time()
prev = None
checked = drops = reorders = stalls = dropouts = lead_silence = 0
pending_zeros = 0
nonmultiple = 0
buf = b''
while True:
    data = rec.stdout.read(65536)
    if not data:
        break
    buf += data
    n = len(buf) // 8
    if not n:
        continue
    f = struct.unpack('<%di' % (n * 2), buf[:n * 8])
    buf = buf[n * 8:]
    for v in f[0::2]:
        if prev is None:
            if v == 0:
                lead_silence += 1
                continue
            if v % STEP:
                nonmultiple += 1
                continue
            prev = v
            continue
        if v == 0:
            pending_zeros += 1
            continue
        if pending_zeros:
            # zeros only count once the stream came back -- otherwise this
            # is the trailing silence after aplay ended
            dropouts += pending_zeros
            pending_zeros = 0
            prev = None
        if v % STEP:
            nonmultiple += 1
            prev = None
            continue
        checked += 1
        want = prev + STEP
        if want > WRAP * STEP:
            want = STEP
        if v != want:
            d = (v - prev) // STEP
            if v == prev:
                stalls += 1
            elif d > 0:
                drops += 1
            else:
                reorders += 1
        prev = v

_, rerr = rec.communicate()
try: pl.wait(timeout=5)
except Exception: pl.kill()

el = time.time() - t0
bad = drops + reorders + stalls + dropouts + nonmultiple
print(f'  elapsed {el:.1f} s, words checked {checked:,} '
      f'({checked/RATE:.1f} s of audio), lead-in silence {lead_silence:,}')
print(f'  drops {drops}  reorders {reorders}  stalls {stalls}  '
      f'dropouts {dropouts}  non-counter words {nonmultiple}')
print(f'  trailing silence after the stimulus ended: {pending_zeros:,} words '
      f'(expected, not a defect)')
print('  arecord stderr:', (rerr or b'').decode().strip()[:80] or '(none)')
print('  aplay   stderr:', (pl.stderr.read() or b'').decode().strip()[:80] or '(none)')
ok = bad == 0 and checked >= 0.99 * TOTAL
print('ORDER SOAK: PASS' if ok else
      'ORDER SOAK: FAIL (%d defects, %d of %d words checked)'
      % (bad, checked, TOTAL))
