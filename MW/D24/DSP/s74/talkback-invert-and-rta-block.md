provenance: AI-drafted 2026-09-19 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S74 — talkback polarity signed in code (D24 shipping ON), and the RTA defs bump BLOCKED by an upstream expander defect

Desk only. The unit was not touched — no boot, no flash, no config, no
rails. Two PW rulings were dispatched (2026-09-19 evening): (1) "tb polarity
can be signed in code" → `DSP4_TALK_INVERT` becomes ON for the D24 shipping
build; (2) "d24 requires rta" → consume `defs-v2026.09.19.1`, which adds
`rta,1` to the D24 product def. **Gate 1 passed. Gate 2 is BLOCKED** — not by
a design question, but by a data-corruption defect in `defs/tools/
expand_matrix.py` discovered while attempting it. `main` is left exactly as
found on the defs side: still pinned at `defs-v2026.09.16.5`.

## Gate 1 — `DSP4_TALK_INVERT` ON for the D24 shipping build

**S74-1. `shipping.config` now carries `DSP4_TALK_INVERT=1`.** This tree's
one `shipping.config` (`MW/D32/DSP/SHARC/shipping.config`) is the D24's —
`DSP4_CHAN_MASK=1`, "a D24 runs 24 strips" (S72 G1) — so this is
unambiguously "the D24 product build" the dispatch names. `DIAG_BUILD_CFG2`
moves **0xC2010244 → 0xE2010244** (bit 29, S72's design), confirmed by
`cfg_words.py`:

```
$ python3 tools/dsp/cfg_words.py --check 0xCF45FF10,0xE2010244
...
the part matches shipping.config to the bit
```

**S74-2. `check_shipping_config.sh` had a real gap, closed.** `DSP4_TALK_INVERT`
was in `DIAG_BUILD_CFG2` since S72 (`cfg_words.py`'s `WORD2` list, `words()`,
and `tools/pi/dsp4_buildcfg.py`'s `FLAGS2`) but was **never in this script's
`want2` dict**, and the WORD1 loop that checks every `shipping.config` key
against `mirror` (the word-1 `SHIPPING` dict) silently skips it too — `mk in
mirror` is false for a word-2-only key. So `shipping.config` could have
disagreed with `dsp4_buildcfg.SHIPPING2` on this one flag and nothing would
have said so. Added to `want2` (read the same way the other word-2 switches
are: `bdefault('DSP4_TALK_INVERT', 0)`, then `shipping.config`'s override),
and to the word-2 formula the script prints for a bench eyeball. Runs clean:

```
$ bash MW/D32/DSP/SHARC/check_shipping_config.sh
shipping config: consistent; DIAG_BUILD_CFG must read 0xCF45FF10 and DIAG_BUILD_CFG2 0xE2010244
```

**S74-3. `tools/pi/dsp4_buildcfg.py`'s `SHIPPING2` mirror updated** —
`DSP4_TALK_INVERT` 0 → 1 — so a part read on the bench with `--expect-shipping`
scores against the new default rather than flagging the correct image as
"NOT THE SHIPPING KERNEL CONFIGURATION". Decoding the new word back through
it confirms `on2` now lists `DSP4_TALK_INVERT` and `diff_shipping2` returns
empty.

**S74-4. `diag.h` says the D24 ships inverted-corrected**, appended to the
S72 note rather than rewritten (the S72 narrative — why bit 29, why not bit
25 — is still exactly right and still the load-bearing part). States the
ruling, the new word, and that this tree carries no D32 `shipping.config` to
prove "D32 unchanged" against — see S74-8.

**S74-5. `build.sh`'s comment updated** from "OFF UNTIL PW RULES" (stale)
to the ruling, and the runtime banner changed from "NOT a shipping switch
position until PW rules" to "the D24 shipping switch position since S74".
The default in code (`DSP4_TALK_INVERT="${DSP4_TALK_INVERT:-0}"`) is
UNCHANGED and must stay 0 — it is the fallback for a bare invocation with no
config file; the shipping value comes from `shipping.config`, same as every
other shipping switch.

**S74-6. `tools/dsp/dsp_codegen.py`'s source comment updated** (the
generator that emits `dsp_block.h`'s copy of the same `#ifndef
DSP4_TALK_INVERT` guard) from "DEFAULT 0 UNTIL PW RULES" to the ruling, and
`dsp_block.h` regenerated per the hard rule (never hand-edit a generated
file). `./check-sharc-codegen-drift.sh` passed before this change (1 file
differed, `dsp_block.h`, exactly the expected comment) and passes clean
after regeneration — 732 files, 0 differ. The regenerated header's diff is
the comment only; the `#define DSP4_TALK_INVERT 0` fallback line is
unchanged, as it must be.

**S74-7. The T5 phase correction, computed, not measured.** S70-6 (T5)
found the talkback input's phase extrapolated to DC = **+181.56°** over a
21-point unwrapped scan, residual 0.19° max — "inverted... the 1.56° residual
over a 2.27 ms loop is the fit's own error." Negating a real signal is an
exact 180° phase shift at every frequency, so applying the sign the flag now
applies:

```
181.56° − 180° = 1.56°
```

which is the same 1.56° S70-6 already attributed to the fit's own error, not
a new residual — i.e. with the sign applied the captured lane's phase lands
at the fit's noise floor, ≈ 0°, exactly the prediction. This is arithmetic
on the S70 capture data (`MW/D24/DSP/s70/talkback.md` §T5, `data/set.json`),
not a new measurement — the unit was not touched this session.

**S74-8. New shipping pair built here, NOT deployed. Chip 2 changes by
exactly the config word.**

| build | chip1 md5 | bytes | chip2 md5 | bytes |
|---|---|---:|---|---:|
| **new D24 shipping** (`DSP4_TALK_INVERT=1`, from `shipping.config` as committed) | `10a413005e0647f5c66476f6a0b4ab60` | 452,388 | `e88a7a4302950d088a6c023c949c916e` | 307,980 |
| control (`DSP4_TALK_INVERT=0` override — the PREVIOUS shipping arm) | `7d1ab146447a1f9d7c010ce9fa104e56` | 452,388 | `3a9c950d3551b6c5d7ff58925a47ec81` | 307,980 |

Both hashes are exactly what S72's G5 already recorded for the two arms —
this build reproduces them byte for byte, which is expected: nothing about
the node code changed, only which arm `shipping.config` now names by
default. `cmp -l` between the two:

* **chip 1: 2 bytes differ** — offset 114892 (`0xC2`→`0xE2`, the config
  word's top byte) and offset 290584 (`0x4D`→`0xCD`, the sign of the Q4.28
  scale constant `C1_TALK_01` already multiplies by) — the same two offsets
  S71/S72 identified.
* **chip 2: 1 byte differs** — offset 134588 (`0xC2`→`0xE2`), the config
  word only. **Chip 2 is otherwise byte-identical to every shipping chip 2
  on record since S67.**

Not deployed: the unit is untouched, and no `.ldr` was written to it.

## Gate 2 — BLOCKED. `defs/tools/expand_matrix.py` corrupts a shared cell's description under CSV quoting, and it is upstream

**What was attempted.** `git -C defs checkout defs-v2026.09.19.1`, `git add
defs`, `./sync-defs.sh --update-lock`. The submodule and the manifest
verified; the four `_matrix.csv` expansions matched their own generation ids
with no error from `sync-defs.sh` itself (it only hashes bytes). D24 and D32
are backfilled products, so their expansions staged at
`MW/{D24,D32}/MX/_matrix.expansion.csv` rather than installing.

**S74-9 🔴 `defs/tools/expand_matrix.py` reads its input with a bare
`line.split(',')` (line 59) — no CSV quoting awareness at all — and at
least one row in `common/cells/mx_master.csv` now needs it.** Since
`defs-v2026.09.16.6` (S60, "the Test SweepOn/SweepStep descriptions now name
the periodic log chirp the firmware implements") the `Test[1-1]SweepOn[1-1]`
cell's description is properly CSV-quoted in the SOURCE and contains an
embedded comma:

```
Test[1-1]SweepOn[1-1],1,,,true,false,"Periodic log sine sweep (chirp) 20Hz-20kHz on OscChan at OscLevel; needs OscOn; 0 = tone, 1 = chirp",,,2,...
```

`expand_matrix.py`'s naive split breaks this into extra fields instead of
one, and the corruption cascades: every downstream row's field alignment
after that point degrades, and the *effect* on `csv.DictReader` (which is
what `gen_dsp.py`, `check-contract-drift.sh` and every gate in this repo
actually uses) is that the tail of the file merges into one field —
**6,931 of 7,014 D32 rows parse, 4,874 of ~5,000 D24 rows parse** — while
`wc -l`/`grep` (byte/line tools, which is all `sync-defs.sh` uses) see
nothing wrong, because the physical bytes are all still there. Reproduced
directly and deterministically, outside this repo's own tooling entirely:

```
$ python3 defs/tools/expand_matrix.py defs/gen/matrix/d32-mx-master.csv -o /tmp/fresh_d32.csv
$ python3 -c "import csv; print(len(list(csv.DictReader(open('/tmp/fresh_d32.csv')))))"
6931
```

This is present at `defs-v2026.09.16.6` and every tag since, **including
the target `defs-v2026.09.19.1`**, and it is present regardless of the RTA
change — `common/cells/mx_master.csv`'s `Test[1-1]SweepOn[1-1]` row is
untouched by the `.19.1` commit. It went uncaught until now because no dsp
session advanced the defs pin past `.16.5` between `.16.6` landing
(2026-09-17-ish) and this one — S71/S72/S73 were desk-only DSP-side
sessions that never ran `sync-defs.sh` against a newer tag.

**Consequence for `gen_dsp.py`'s own drift check**, run against the
corrupted expansions: it reported 54 D24 / 9 D32 cells "the landed file has
and the graph does not propose" (`MainCtr*`, `Usb*`, `MainSub*Crossover*`,
some of `Test*`) and 74 `Aux*Name*` cells on both, on top of the 2 real new
`Rta001On001`/`Rta001Src001` rows. **Isolated and shown to be an artefact of
the corruption, not real drift**: a clean worktree at the OLD pin
(`defs-v2026.09.16.5`, no expansion re-run) passes `gen_dsp.py
--check-proposal` with **zero** errors for both products; the physical cell
list of the new D24 expansion, read as plain text (immune to the quoting
bug), is **identical to the committed `HEAD` matrix plus exactly two
appended rows, `Rta001On001` and `Rta001Src001`** — confirmed with a plain
`diff` of sorted `_Cell` columns, D24 and D32 both. So had the expander not
been broken, gate 2's "0 existing addresses moved, 2 new unmapped rows
appended" would have been exactly true and exactly what the dispatch
expected.

**What was NOT done, and why.** `gen_dsp.py`'s own fatal check refused to
proceed past the corrupted comparison (by design — no-fallback), so nothing
was installed or backfilled from it; the tree cannot have been silently
damaged by this attempt. But landing the defs bump here — even just the
submodule pointer and `defs.lock` — would leave `main` in a state where
`check-contract-drift.sh` fails for every session after this one, for a
reason with nothing to do with RTA, until the defect is fixed upstream. That
is a bigger blast radius than one blocked gate, so **the bump was reverted**:
`git -C defs checkout defs-v2026.09.16.5`, matrix expansions removed,
`defs.lock` and `MW/{D12,D16}/MX/_matrix.csv` restored (D12/D16 install
directly, not staged, and were already corrupted the same way in the working
tree before the revert — caught before anything was committed).
`./sync-defs.sh` / `gen_dsp.py --check-proposal` confirmed clean at HEAD
after the revert.

**🔴 S74-10, for the hub.** `defs/tools/expand_matrix.py` needs a real CSV
reader (or at minimum, quote-aware field counting) — it currently is not
compatible with the CSV-quoted, comma-containing description fields
`common/cells/mx_master.csv` has carried since `defs-v2026.09.16.6`, and
every product master downstream of that file silently loses rows in any
tool that parses its output as real CSV. This blocks the D24 RTA landing
(gate 2 of this dispatch) and will block anything else that tries to
advance the defs pin past `.16.5` until it is fixed. Options, not decided
here: (a) fix `expand_matrix.py` in `invirco/defs` to use `csv.reader`/
`csv.writer` instead of `line.split(',')`; (b) as a stopgap, remove the
comma from the `Test[1-1]SweepOn[1-1]` description in
`common/cells/mx_master.csv` (content change, not a tooling fix — the next
free-text field with a comma reintroduces this). Either is defs-repo work,
outside this tree's remit as a consumer.

## What is committed

Gate 1 only: `shipping.config`, `check_shipping_config.sh`, `diag.h`,
`build.sh`, `dsp_codegen.py`, `dsp_block.h` (regenerated), `dsp4_buildcfg.py`.
No defs pin change, no matrix change, no address artefact change — all eight
compared clean against `git show HEAD:` because none of gate 1's files are
among them and gate 2 was reverted in full.
