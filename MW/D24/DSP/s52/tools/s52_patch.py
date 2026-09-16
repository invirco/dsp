"""s52_patch.py identity|d24 — rewrite chip-1 INPUT_PATCH and CONFIG_COMMIT; print node_entry 16/20."""
import sys
A = sys.argv[1:]
import s52lib as X
c1 = X.Chip(1)
print('before: node_entry[16]=%d node_entry[20]=%d' % (X.node_entry(c1, 16), X.node_entry(c1, 20)))
X.apply_patch(c1, list(range(46)) if A[0] == 'identity' else X.D24_PATCH)
print('after %s: node_entry[16]=%d node_entry[20]=%d' % (A[0], X.node_entry(c1, 16), X.node_entry(c1, 20)))
