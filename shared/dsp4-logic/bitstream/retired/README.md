# Retired LOGIC bitstreams

Nothing here is deleted and nothing here is flashed. These are artifacts
`loadlogic.sh` used to name, kept because the bench records point at them by
md5 and those records must stay resolvable.

They are here rather than in the repo's `attic/` because `attic/` is defined
by CLAUDE.md as the retired D24 ADAU1466/SigmaStudio material and is never
extended. This directory does the same job, next to the artifacts it retires.

**Do not build from these and do not flash them.** Each has a live
replacement named in `MW/D32/DSP/SHARC/loadlogic.sh`.

---

## `dsp4_logic_driveall.e13b5dec84e0` — retired S37, because it has no source

The DRIVEN-CAPACITY stimulus. Every driven capacity row since S28 was taken
on it, including the `100.82 %` D32 worst-use figure in
`MW/D32/DSP/window-candidate.md` §2.1.

**It matches no committed state of the logic tree at any point in its
history** (S36-3): it was built from a dirty working tree and that tree was
never committed. `build.sh`'s `SRC_HASH` is a pure function of committed text,
so this was settled exhaustively — 4,352 candidate labels across all 34
commits that have ever touched the tree, at all four `cfg:` line shapes and
all 32 macro combinations — not by failing to find it.

Its rebuildable equivalent is `dsp4_logic_driveall.907492a607bd`, the same
work committed at `a096c585` 36 minutes later; the two differ only in the
stamped `design_id` word. S37 rebuilt `907492a607bd` from `a096c585` in a
clean tree and got the same label and a **byte-identical pof**.

| | pof md5 | design_id |
|---|---|---|
| retired `e13b5dec84e0` | `ab6781b2edee4cfec312b56cd0dee9f4` | `32'h5dec84e0` |
| rebuildable `907492a607bd` | `8d52c5d3a3e09267da8a9ffa5913ce0a` | `32'h92a607bd` |

## `dsp4_logic_pisel.bd9c100db7c2` — retired S37, because it cannot say what it is

The CPLD-only loop reference, the far end of the S29 latency differential.
Built from `1dc67f39`, which **predates the design-ID stamp** (`3152e2b1`), so
its manifest carries no `design_id` line and `dsp4_logic_id.py` gets nothing
back from the part. Its identity rests on the flash records, not on the
silicon.

The stamped equivalent from the same work is
`dsp4_logic_pisel.2c1355bbc69b` (`3152e2b1`) — S37 rebuilt it from that
commit in a clean tree and got the same label and a byte-identical pof.

| | pof md5 | design_id |
|---|---|---|
| retired `bd9c100db7c2` | `9f0d2bcbf1fa2e31ef6529335fb461ae` | none — predates the stamp |
| stamped `2c1355bbc69b` | `621599e288c7cc6f9ba200a4bb0f506b` | `32'h55bbc69b` |

---

Both are the precise failure `shared/dsp4-logic/build.sh`'s own comment block
was written about, and both were still live in the tool the bench used every
day until S37.
