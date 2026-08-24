"""GAIN -> FDR -> RTG -> BUS, end to end, reading the pool and the bus."""
import sys, struct, time
sys.argv=["x"]
import dsp4_scope as S
from dsp4_tubedly_probe import wrv, f32
sc=S.Scope(1); sc.check_chip()
P=sc.sym["_blk_pool"]; AMP=0x08000000
def sgn(v): return v-(1<<32) if v&0x80000000 else v
def cap(addr):
    sc.arm(addr, P, AMP, 2); sc.wait(); return sgn(sc.fetch(1)[0])
wrv(sc, 0x0000, f32(1.0), ramp_id=1, settle=0.05)      # GAIN unity
for lv, pn in ((1.0,0.5),(0.5,0.5),(0.25,0.5),(1.0,0.0),(1.0,0.25),(1.0,0.75),(0.5,0.25)):
    wrv(sc, 0x0053, f32(1.0), ramp_id=1, settle=0.05)  # DCA
    wrv(sc, 0x0050, f32(lv), ramp_id=1, settle=0.05)
    wrv(sc, 0x0051, f32(pn), ramp_id=1, settle=0.05)
    time.sleep(0.4)
    print("CHAIN lv=%g pn=%g in=%d mono=%d L=%d bus=%d"
          % (lv, pn, AMP, cap(P), cap(P+2*32), cap(sc.sym["_buf_C1_BUS_MAIN_L"])))
