# S131 report — MW-D24-2 executed onto generation `46109e9fb812`, evidence archive

S131 itself ran at the bench today (2026-09-28, hub + PW), moving MW-D24-2 to
D24 generation `46109e9fb812` (`defs-v2026.09.28.2`). This report and the
files beside it are S141's archive of that session's evidence, written after
the fact — S131 had no report of its own.

## Outcome

App `dfebca8275940e68b6ec906c6e8f44fe` (mx26 `dff4bb3`), pack sha256
`44cb57a8…`. Three MCUs flashed and verified:

| MCU  | image | md5 | notes |
|------|-------|-----|-------|
| H1S1 | `H1S1/H1S1.shex` | `19a5492d76e0f2faeda6059a045b3f2a` | see WRONG SOURCE below |
| H1S3 | (talkback variant B, this session's rebuild) | `43efd43f100dc9396fa1f351cbdd0ba6` | `H1S3-B/H1S3.B.shex` |
| H1S4 | S139's `f54848b0d63751fb8cf3fbb17dc17ebe` | — | unchanged from S139 |

`d24_panel.py --mode resolve` = Skin 4360 / Enc 4176 / SwLeft 4643 / SwTalk
4644. PW verified every switch/LED combination on both panels at the bench
(right panel's bottom row dim — supplier note, hardware, not this session's
concern).

## H1S1: WRONG SOURCE, corrected

S139's `s139/gen/H1S1/H1S1.shex` (`8067f1d4…`, 2174 records) was built from
the unit's `/home/app/fwbuild/H1S1`, which was **stale**: `matrix.cs` dated
2025-12-30, predating S69's `CodecPoll()`. Flashing it during S131 regressed
ML1/CC/MC and the DSP boot.

The hub rebuilt from the real source, `~/build-h1s1` (hub machine; scratch
copy `~/s131/H1S1`, built via `Debug/fw.sh`):

- **Unmodified rebuild** reproduced the pre-S131 flashed image byte-for-byte:
  `H1S1.pre-s131-repro.shex` md5 `272868c889fc87ead0a3b4bb277f55e2`
  (2279 records) — proof the source tree itself was sound, only the unit's
  copy of it was stale.
- **With `s139/gen/matrix.h` swapped in** (the only change needed —
  generation `46109e9fb812`'s `#define`s): `H1S1.shex` md5
  `19a5492d76e0f2faeda6059a045b3f2a`, same `text`/`data`/`bss`
  (35760/661/1944) as the pre-S131 build, one `.shex` record differs (the
  header address table). This is what was flashed and verified.

`s139-report.md`'s H1S1 bullet and `s131-runbook.md` step 6 are both marked
with this correction (S141). `/home/app/fwbuild/H1S1` on the unit has been
synced from `~/build-h1s1` (`matrix.h`, `matrix.cs`, `main.c`; old stale
copies kept as `*.bak-s141-stale-20260928-124440`) so a future on-unit
rebuild from that path cannot reproduce the stale image.

## H1S3 variant B: talkback logic, rebuilt at the new generation

`H1S3-B/` is S131's rebuild of S135's talkback variant B (`WrTalkbackLeds()`
+ `RdTalkbackSwitch()`) against `46109e9fb812`'s `matrix.h`. Built clean:
`text` 20932, `data` 1216, `bss` 2080 (`H1S3-B/H1S3.elf`). Flashed image
`H1S3-B/H1S3.B.shex`, md5 `43efd43f100dc9396fa1f351cbdd0ba6`, header id
`H1S3` — socket-correct per S135's crossing fix. PW verified: press/release
edges both register, both LEDs lit at 3.

## Auto passes

Two fresh auto passes ran today, archived here as `pass/` (first, S131's own
post-flash check) and `pass2/` (re-run after the H1S1 correction above):

- `pass/`: `d24_runall.py --auto-only` into `/home/app/s131fw/pass`.
- `pass2/`: same, into `/home/app/s131fw/pass2`, after the corrected H1S1
  was flashed — **20 PASS / 1 FAIL / 16 NO DATA**: MC1-3, DR, DY, DC CS1/2,
  AS-DSPA/B, AS-ADC, AL1 all PASS.

**Still NO DATA in `pass2`, despite having PASSed on 09-27: ML1, ML-M, CC1,
CC2.** Root cause (found and fixed by S141, see `MW/D24/DSP/s141/` and
`tasks.md`'s S141 dispatch): `d24_bus_probe.py` imports `codec4619` from
`/home/app/dspboot/codec4619.py`, which still carried the pre-S136 literal
`SYS001TEST001 = 0x1526` (5414) — the S136 name-resolving copy never reached
the pair drop. `--mode cell` asked for cell 5414; the current pack resolves
`Sys001Test001` to 4361. S141 deployed the fix and confirmed ML1/ML-M/CC1/CC2
PASS in a third pass (`MW/D24/DSP/s141/pass1/`).

## Archive contents

- `H1S1/` — the hub's `~/s131/H1S1` rebuild: `H1S1.hex`, `H1S1.shex` (the
  flashed image), `H1S1.pre-s131-repro.shex` (the unmodified-rebuild proof),
  `matrix.h`, `build_linux_H1S1.log`.
- `H1S3-B/` — the unit's `/home/app/s131fw/H1S3-B` rebuild: `H1S3.hex`,
  `H1S3.B.shex` (the flashed image), `matrix.h`, `build_linux_H1S3.log`.
- `pass/`, `pass2/` — `results.csv` and `reports/` from both auto passes run
  during S131, copied from `/home/app/s131fw/pass{,2}` on the unit.

## Unit state

NO flashing, no app deploy, no rails work happened in S141 (this archive
session). `app` unchanged (`dfebca82…`), AN_EN (GPIO26) low, matrix-app
active throughout — verified before and after.
