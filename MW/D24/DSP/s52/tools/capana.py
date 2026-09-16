import json, math, statistics, sys
d=json.load(open(sys.argv[1])); f0=float(sys.argv[2]) if len(sys.argv)>2 else 1000.0
def s32(w): return w-(1<<32) if w&0x80000000 else w
v=[s32(w)/2**28 for w in d['samples']]
n=len(v); w=2*math.pi*f0/48000
S=sum(a*math.sin(w*i) for i,a in enumerate(v)); C=sum(a*math.cos(w*i) for i,a in enumerate(v))
A=2*S/n; B=2*C/n; m=statistics.mean(v)
res=[a-m-A*math.sin(w*i)-B*math.cos(w*i) for i,a in enumerate(v)]
amp=math.hypot(A,B)
big=[(i,round(v[i],4),round(r,4)) for i,r in enumerate(res) if abs(r)>0.02]
print('amp %.4f (%.2f dBFS pk), resid rms %.5f (%.2f dBc), outliers>0.02: %d' % (amp,20*math.log10(amp),math.sqrt(sum(r*r for r in res)/n),20*math.log10(math.sqrt(sum(r*r for r in res)/n)/(amp/math.sqrt(2))),len(big)))
print(big[:40])
# smooth residual (exclude outliers)
good=[r for r in res if abs(r)<=0.02]
print('resid rms excl outliers %.5f (%.2f dBc)'%(math.sqrt(sum(r*r for r in good)/len(good)),20*math.log10(math.sqrt(sum(r*r for r in good)/len(good))/(amp/math.sqrt(2)))))
