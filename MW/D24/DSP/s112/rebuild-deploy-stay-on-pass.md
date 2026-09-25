# S112 — rebuild+deploy test app: wizard stays on row after PASS

Hub dispatch `HUB DISPATCH 2026-09-25 16:07Z`. Build and deploy only — the
design (`ReapRun()` stays on a PASS the same way it already stays on a FAIL,
`AdvanceAfterPass()` deleted) was already committed on mx26 `main`
(`0fed2d64`) before this dispatch started.

## Build

`dotnet test src/sw/app.Tests -r linux-x64`: 163/163 pass. No test asserted
the old auto-advance-after-PASS behaviour, so nothing needed fixing.

`dotnet publish src/sw/app/app.csproj -c Release -r linux-arm64
--self-contained true -p:PublishSingleFile=true -o
src/sw/app/bin/Publish/linux-arm64/single-selfcontained` — the S107 recipe.

## Deploy — `app@192.168.1.219`

Checked before touching anything: `who` showed only this session's own ssh
connection, `d24-testui` active / `matrix-app` inactive, `/home/app/app` md5
`5981fd34614cd29f5fc304908e251a1e` (S107's build, still live — nothing
between S107 and S112 touched the app binary).

| artefact | md5 | rollback |
|---|---|---|
| `/home/app/app` | `432ae0fcba2400e74e9916e979103720` | `/home/app/app.bak-s112-pre` (`5981fd34614cd29f5fc304908e251a1e`, S107's) |

Publish md5 matched the scp'd copy before install. `d24-testui` stopped for
the swap, `matrix-app` never touched. On restart the log confirmed the
catalog: `TestSkinStore: catalog 202 rows from
/home/app/selftest/test-catalog.csv`.

## On the glass, through the wizard's own START

Same method as S110/S111: `d24_touch_inject.py --serve /tmp/tap`, device
created before restarting `d24-testui` (Avalonia's DRM backend enumerates
input once at startup — a one-shot injector run after start is invisible to
it, which is what the first attempt hit). Captures are real
`MX_DRM_CAPTURE_PATH` renders (S105's `s105-capture.conf`, already in place,
1 Hz).

A restart resets the wizard's in-memory row selection, so this session had
to navigate back to row 56 through the wizard's own QUEUE/PREV/NEXT buttons
(ALL ROWS mode, then 50×PREV) — not a shortcut, the position math (row 56
absorbed the old row 57 in S110's merge, so ALL ROWS position == workbook
`num` for num≤56 and `num-1` above it) was checked against the log's own
`step` lines at each stage.

- **Row 56 (AL1), START pressed at 17:13:47** → `TestSkinStore: #56 finished
  at 17:14:11 — PASS` → `TESTSKIN: PASS — staying on Left Switch PCBA|Panel
  MEMS mic (talkback) + Speaker for the operator`. Capture
  `s112-row56-pass-tile.png`: still row 56/202, green **PASS** tile, full
  result line (`AL1 PASS 2026-09-25T16:14:09Z — PASS base -48.0 tone -35.8
  SNR 12.2 dB THD+N -16.4 dB 15.0%`), START still live for a re-run. This is
  the behaviour the dispatch asked for — the wizard used to jump to #58 on
  its own the instant the run finished.
- **NEXT from row 56** → `step NEXT → #58 ... (57/202)`, capture
  `s112-after-next.png`. Matches S110's own note that NEXT from 56 goes to
  58 (57 was merged into 56).
- **A non-PASS row, to show FAIL/NO-DATA handling is unchanged**: row 107
  (`DC1-CS6,DC2-CS6`, a genuinely idle DSP chip-select with no fitted part
  behind it — reliably NO DATA, cheap and harmless to press). START at
  17:15:31 → `TestSkinStore: #107 finished at 17:15:43 — UNTESTED`, capture
  `s112-row107-nodata.png`: still on row 107, remedial lines shown, START
  still live. `ReapRun()`'s non-PASS branch is untouched by this dispatch's
  diff, and this proves it — the row stayed put exactly as it did before
  S112, same as it always has for a non-passing verdict.

## Handback

Navigated back to row 56 (ALL ROWS queue, 50×PREV then confirmed by the
log's own `step PREV → #56` line) to leave the unit exactly where S111 left
it. `AN_EN` (GPIO26) `lo`, `CS_M` (GPIO27) `op -- pd | hi` DRIVEN — both
unwritten by this dispatch, matching every reading taken this session.
`d24-testui` active, `matrix-app` inactive. Injector's uinput device and
FIFO removed (`s112-touch-serve2` stopped, `/tmp/tap` gone); no systemd
drop-in added (reused S105's `s105-capture.conf` as-is). On-unit temp
capture PNGs deleted after pulling copies down.

## Status: 🟢 done

Rebuilt, tests green (163/163, no fixture needed), deployed with rollback
and matched md5s, catalog confirmed 202 rows, PASS-stays-on-row proved live
through the wizard's own START/NEXT, a non-PASS row proved unchanged.
Committed and pushed to `main`.
