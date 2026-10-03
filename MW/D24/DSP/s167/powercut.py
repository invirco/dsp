import time, sys
sys.argv=["x"]
import d24_pedal as P
img=open("P1-cc.bin","rb").read(); img=img+b"\xff"*((-len(img))%8)
lt=time.localtime(); start=time.mktime((lt.tm_year,lt.tm_mon,lt.tm_mday,16,33,0,0,0,-1))
r=P.Relay(); rom=P.Rom(r)
P.log("relay %s" % r.open("N")); r.send(b"V"); P.log("app V: %r" % r.recv(90,0.6).split(b"\n")[0])
assert start > time.time()
while time.time()<start: time.sleep(0.005)
r.send(b"!BOOT\n"); P.log("!BOOT -> %r" % r.recv(6,1.0))
P.log("relay %s" % r.open("E")); time.sleep(0.2)
P.log("sync %s" % rom.sync())
P.log("before: " + P.optr_text(int.from_bytes(rom.read(P.OPTR_ADDR,4),"little")))
rom.mass_erase(); P.log("mass erase ACK")
cut=None; n=0
for off in range(0,len(img),64):
    t=start+3+n
    while time.time()<t: time.sleep(0.005)
    try:
        rom.write(P.FLASH_BASE+off, img[off:off+64]); P.log("block %2d @0x%08X ACK" % (n, P.FLASH_BASE+off))
    except P.RomError as e:
        cut=time.time(); P.log("block %2d @0x%08X FAILED: %s  <-- power cut" % (n, P.FLASH_BASE+off, e)); break
    n+=1
if cut is None:
    P.log("VOID: every block was written before any cut; finishing normally")
else:
    t0=time.time(); ok=False
    while time.time()-t0<240:
        r.drain(0.01); r.send(b"\x7f"); b=r.recv(1,0.6)
        if b==bytes([P.ACK]): ok=True; break
        if b: P.log("sync got %s" % b.hex())
        time.sleep(0.4)
    P.log("ROM back after cut: %s (%.1f s after the failed block)" % (ok, time.time()-cut))
    if not ok: sys.exit(1)
    P.log("Get ID 0x%03X" % rom.get_id())
    P.log("after cut: " + P.optr_text(int.from_bytes(rom.read(P.OPTR_ADDR,4),"little")))
    w=rom.read(P.FLASH_BASE, 64*max(n,1)); P.log("flash after cut, first %d B match image: %s" % (64*n, w[:64*n]==img[:64*n]))
t=rom.flash(img, go=True); P.log("RETRY FLASH: %s" % t)
time.sleep(2)
P.log("relay %s" % r.open("N")); r.drain(0.05)
r.send(b"V"); P.log("app V: %r" % r.recv(90,1.0))
r.send(b":"); P.log("all on %r" % r.recv(2,0.5))
P.log(r.info()); r.close()
