#!/usr/bin/env python3
"""geq_splice.py — shared single-pass chain-splice helper for
gen_dsp_csv.py's GEQ insertion (review §2.4/§3.2, patch §5.2): point
`after`'s matching output and `before`'s matching input at the new row,
then insert it, in one pass over `rows` instead of a pop + linear-search
+ insert sequence repeated per call site. Raises a contextual ValueError
naming the missing id(s) if the graph is out of sync with what the caller
expected, instead of a bare StopIteration.
"""


def relink_and_insert(rows, after_id, before_id, new_row, context):
    """Splice `new_row` into the chain between `after_id` and `before_id`.

    `rows` is mutated in place: the row whose id is `after_id` has
    `before_id` replaced by `new_row['id']` in its (';'-joined) outputs,
    the row whose id is `before_id` has `after_id` replaced by
    `new_row['id']` in its inputs, and `new_row` is inserted immediately
    after `after_id`'s row.
    """
    after_idx = None
    seen_before = False
    for idx, r in enumerate(rows):
        if r['id'] == after_id:
            after_idx = idx
            r['outputs'] = ';'.join(
                new_row['id'] if o == before_id else o
                for o in r['outputs'].split(';'))
        elif r['id'] == before_id:
            r['inputs'] = ';'.join(
                new_row['id'] if i == after_id else i
                for i in r['inputs'].split(';'))
            seen_before = True
    if after_idx is None or not seen_before:
        raise ValueError(
            f'{context}: expected both {after_id!r} and {before_id!r} in '
            f'the graph (found after={after_idx is not None}, '
            f'before={seen_before}); the chain this node is being spliced '
            f'into has changed')
    rows.insert(after_idx + 1, new_row)
