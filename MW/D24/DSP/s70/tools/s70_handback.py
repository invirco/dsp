"""Leave the unit as S70 found it. AN_EN IS ALREADY LOW when this runs -- it goes down
FIRST, by hand, before anything else is torn down (the mandate: analog last up, first down).

Order here, after that: the codec back to its init image and verified on the lane, the
SHIPPING pair booted and configured, the 595 SAFE image written LAST (after the final DSP
boot, because a boot clocks half a megabyte through the chain and only a CS_M edge decides
what gets latched -- S70-7), CS_M back to the input-pull-up it was found at, then the app.
"""
import subprocess
import sys
import time

sys.path.insert(0, '/home/app/s70')


def sh(cmd, **kw):
    print('$', cmd, flush=True)
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, **kw)
    print((r.stdout + r.stderr).rstrip(), flush=True)
    return r


assert 'hi' not in sh('pinctrl get 26').stdout, 'AN_EN IS STILL HIGH -- refusing to hand back'

# ---- the codec back to its init image -------------------------------------------------
sh('sudo pinctrl set 6,24 op dh')
sh('python3 /home/app/s69/codec4619.py --mgn2r 11 --mgn2l 11')
time.sleep(0.2)
sh('python3 /home/app/s69/codec4619.py --reinit')
time.sleep(0.5)

import s70lib as T                                                       # noqa: E402
r = T.Rig.__new__(T.Rig)                     # no route(): the graph is about to be replaced
T.S69.Rig.__init__(r, '/home/app/s70/s70.jsonl')
r.osc(on=False)
floors = {}
for ch in (51, 52, 53):
    r.meas(ch)
    floors[ch] = r.point(3)['rms_dbfs']
print('codec floors after reinit (AN_EN low):', {k: round(v, 3) for k, v in floors.items()},
      flush=True)
r.meas(0)
r._close()

# ---- the shipping pair ----------------------------------------------------------------
sh('sudo pinctrl set 6,24 op dh')
for i in (1, 2):
    sh('cd /home/app/s69 && python3 dsp4_boot.py --dir /home/app/s70ship')
    sh('sudo pinctrl set 6,24 op dh')
    sh('cd /home/app/s69 && python3 dsp4_config.py --product d24 --chip 1')
    sh('sudo pinctrl set 6,24 op dh')
    sh('cd /home/app/s69 && python3 dsp4_config.py --product d24 --chip 2')
    sh('sudo pinctrl set 6,24 op dh')
for c, rdy in ((1, ''), (2, ' --rdy-gpio 12')):
    sh('cd /home/app/s69 && python3 dsp4_diag.py --chip %d%s | head -6' % (c, rdy))
    sh('sudo pinctrl set 6,24 op dh')

# ---- the 595 SAFE image, LAST ----------------------------------------------------------
sh('''sudo python3 -c "
import sys; sys.path.insert(0,'/home/app/s55')
import s55_chain as CH
ok,got=CH.send([0x01]*24+[0x00])
print('before :', ' '.join('%02X'%b for b in got[0]))
print('VERIFIED 200/200' if ok else 'MISMATCH')
"''')

# ---- pins as found, then the app -------------------------------------------------------
sh('sudo pinctrl set 27 ip pu')
sh('pinctrl get 26; pinctrl get 27')
sh('sudo systemctl start matrix-app')
time.sleep(12)
sh('systemctl is-active matrix-app')
sh('grep -c "MCU boot verified" /home/app/logs/log; grep -n "MCU verified\\|MCU boot verified\\|MCU not verified\\|AN_EN" /home/app/logs/log | tail -15')
sh('pinctrl get 26; pinctrl get 27')
