"""LIM sweep: capture the limiter's own input and output at each level, so
the model is driven by what the limiter actually saw rather than by an
assumption about the four nodes upstream of it."""
import sys
sys.argv = ["x"]
import dsp4_scope as S

sc = S.Scope(2)
sc.check_chip()
inj = sc.sym["_rx_ic_slot_C2_RECV_AUX_01"]
IN, OUT = sc.sym["_buf_C2_AUX_AFB_01"], sc.sym["_buf_C2_AUX_LIM_01"]
N = 300
for amp in (0x08000000, 0x0E000000, 0x0F000000, 0x10000000, 0x18000000, 0x20000000):
    row = []
    for src in (IN, OUT):
        sc.arm(src, inj, amp, 2)          # step
        sc.wait()
        v = sc.fetch(N)[N - 1]
        row.append(v - (1 << 32) if v & 0x80000000 else v)
    print("AMP 0x%08X IN %d OUT %d" % (amp, row[0], row[1]))
