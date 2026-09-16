#!/usr/bin/env python3
"""s64_peekstate.py — the RTA's control and a few state words, by peek (diagnostic)."""
import struct
import s64lib as L
T, X = L.T, L.X
R = T.Rig()
A = L.Rta(R)
f = lambda w: struct.unpack('<f', struct.pack('<I', w))[0]
print('ON', A.rd(L.RTA_ON), 'MODE', A.rd(L.RTA_MODE), 'SRC_L 0x%X' % A.rd(L.RTA_SRC_L), 'SRC_R 0x%X' % A.rd(L.RTA_SRC_R),
      'blk AUX1 0x%X' % A.sc.sym['_blk_C2_MIX_AUX_01'], 'SEQ', A.sc.rd_counter(L.RTA_SEQ))
for name, n in (('_rta_x_l', 2), ('_rta_d', 16), ('_rta_st_l', 6 * 3), ('_rta_e', 3), ('_rta_a_cur', 1), ('_rta_h_cur', 1),
                ('_rta_coef', 7)):
    a = A.sc.sym[name]
    print(name, '0x%X' % a, ['%.6g' % f(A.peek(a + i)) for i in range(n)])
