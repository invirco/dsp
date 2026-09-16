import time
import s52lib as X
cs = [X.Chip(1), X.Chip(2)]
a = [c.sc.peek(c.sc.sym['_diag_blk_overrun']) for c in cs]
time.sleep(5.0)
b = [c.sc.peek(c.sc.sym['_diag_blk_overrun']) for c in cs]
for n in range(2):
    print('chip %d _diag_blk_overrun %d -> %d in 5 s (+%d)' % (n + 1, a[n], b[n], b[n] - a[n]))
