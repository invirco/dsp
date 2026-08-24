"""GAIN bit-exactness under per-block kernels: same law, same rounding."""
import sys, struct, time
sys.argv=["x"]
import dsp4_scope as S
from dsp4_tubedly_probe import wrv, transparent_chain, f32
sc=S.Scope(1); sc.check_chip()
transparent_chain(sc)
inj=sc.sym["_rx_slot_C1_IN_01"]; src=sc.sym["_blk_pool"]+32   # BLK_CHAIN_B: GAIN's pooled output
AMP=0x08000000
for g in (1.0, 0.5, 0.25, 2.0, 0.001, 7.94328):
    wrv(sc, 0x0000, f32(g), ramp_id=1, settle=0.05)
    time.sleep(0.3)
    sc.arm(src, inj, AMP, 2); sc.wait()
    v=sc.fetch(8)
    vals=[x-(1<<32) if x&0x80000000 else x for x in v]
    print("GAIN g=%.6g in=%d out=%d all_equal=%s" % (g, AMP, vals[0], len(set(vals))==1))
