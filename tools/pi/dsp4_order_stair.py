"""Does the through-DSP loop preserve SAMPLE ORDER? A staircase, 64 frames
a step, so a stream that merely jitters comes back as clean 64-long runs
and one that interleaves comes back as neighbouring steps alternating."""
import struct, subprocess, time
from collections import Counter
HOLD=64; STEPS=1500
stim=[]
for k in range(STEPS): stim += [((k+1)<<8)]*HOLD
open("/tmp/s.raw","wb").write(b"".join(struct.pack("<ii",v,v) for v in stim))
rec=subprocess.Popen(["arecord","-D","hw:dsp4pcm,0","-f","S32_LE","-c","2","-r","48000",
  "-d","4","--period-size=1024","--buffer-size=8192","-t","raw","-q","/tmp/sc.raw"],stderr=subprocess.DEVNULL)
time.sleep(0.3)
subprocess.run(["aplay","-D","hw:dsp4pcm,0","-f","S32_LE","-c","2","-r","48000",
  "--period-size=1024","--buffer-size=8192","-t","raw","-q","/tmp/s.raw"],capture_output=True)
rec.wait()
raw=open("/tmp/sc.raw","rb").read(); m=len(raw)//8
f=struct.unpack("<%di"%(m*2),raw[:m*8]); L=f[0::2]
nz=[i for i,v in enumerate(L) if v]
print("frames",m,"nonzero",len(nz),"span",(nz[0],nz[-1]) if nz else None)
runs=[]; cur=None; n=0
for v in L[nz[0]:nz[-1]+1]:
    if v==cur: n+=1
    else:
        if cur is not None: runs.append((cur,n))
        cur=v; n=1
runs.append((cur,n))
print("runs",len(runs),"(a clean loop gives ~%d)"%STEPS)
print("mid 12 runs:", " ".join("%08x:%d"%(v&0xffffffff,n) for v,n in runs[len(runs)//2:len(runs)//2+12]))
idx=[(v>>8) for v,n in runs if v and (v&0xFF)==0]
mono=sum(1 for a,b in zip(idx,idx[1:]) if b==a+1)
print("value-run indices: n=%d, strictly +1 on %d of %d transitions"%(len(idx),mono,max(1,len(idx)-1)))
print("index range",(min(idx),max(idx)) if idx else None)
print("run-length histogram (non-zero values):",Counter(n for v,n in runs if v).most_common(6))
