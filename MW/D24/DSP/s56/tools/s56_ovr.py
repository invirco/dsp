import os, sys, time
ARG = list(sys.argv)
os.environ.setdefault('SYMDIR', '/home/app/s56')
sys.path.insert(0, '/home/app/s54')
import s52lib as X
subprocess = __import__('subprocess'); subprocess.run(['sudo', 'pinctrl', 'set', '6,24', 'op', 'dh'])
c = X.Chip(int(ARG[1]))
print('chip', ARG[1], 'overrun', c.sc.peek(c.sc.sym['_diag_blk_overrun']), 'proc_cyc_max', c.sc.peek(c.sc.sym['_proc_cyc_max']))
