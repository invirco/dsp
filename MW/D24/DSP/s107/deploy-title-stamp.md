# S107 — catalog deploy-date stamp on the D24 SELF-TEST title

Hub dispatch `HUB DISPATCH 2026-09-24 14:23Z`. Design was already specified —
`test-catalog.csv`'s own last-write time, appended to the `TITLE` field.
Applied it, hit a real layout conflict the dispatch flagged as a possibility,
fixed it, and deployed.

## What changed

`mx26 src/sw/app/Core/TestSkinStore.cs`:

- New `_catalogStamp` field (`DateTime`, alongside `_lastLoad`), reset to
  `DateTime.MinValue` in `LoadCatalog()` and `ReloadForTests()`, set via
  `File.GetLastWriteTime(CatalogPath)` right after the CSV rows finish
  parsing (inside `LoadCatalog()`'s existing try/catch — a missing/unreadable
  catalog takes the same `_loadError` path it already did, no new failure
  path added).
- `Field("TITLE")`: the success branch now returns
  `"D24 SELF-TEST · " + _catalogStamp.ToString("yyyy-MM-dd HH:mm")`. The
  `_loadError` branch is untouched.
- `TestSkinLayoutTests.cs` has no test asserting the exact `TITLE` string —
  nothing to update there.

## 🔴 The dispatch's proposed shape didn't fit — trimmed, not truncated

The dispatch's example shape, `"D24 SELF-TEST   catalog 2026-09-24 14:46"`,
overflows the `TITLE` control's box (`tools/d24/build-d24-test-skin.py`:
`sw("title", "TESTINFO", "TITLE", 500, 26, 560, 44, siz=30, ...)` — 560×44 at
font size 30). It wraps to a second line that lands directly on the
`QUEUEPOS` line underneath (that box starts at y=74, 4px below TITLE's own
bottom edge) — proven on the unit, `live-title-overlap-v1.png`.

Cut the word `catalog` and shortened the separator: `"D24 SELF-TEST · " +
yyyy-MM-dd HH:mm`. Still full date + time, still one line, no overlap —
confirmed on a second live capture, `live-title-landed.png`. Didn't touch
`build-d24-test-skin.py`'s box geometry: widening the control is a layout
decision beyond what this dispatch specified (D24TEST skin regen + redeploy),
so left it as the smallest change that fits inside what was actually asked
for. If PW wants the fuller `catalog YYYY-MM-DD HH:mm` shape on screen, that
needs a `TITLE` box width bump (room exists: next control right of it is
`SCORE` at x=1430, so ~870px is free) and a skin rebuild/redeploy — flagging
rather than doing it unasked.

## Build

`dotnet test src/sw/app.Tests -r linux-x64`: 163/163 pass, both before and
after the title-format trim (obj/bin were stale from a prior machine's
osx-arm64 RID — cleared them, `-r linux-x64` pins the right one going
forward).

`dotnet publish src/sw/app/app.csproj -c Release -r linux-arm64
--self-contained true -p:PublishSingleFile=true -o
src/sw/app/bin/Publish/linux-arm64/single-selfcontained` — the same
publish step `scripts/broadcast-build.sh` uses, run directly rather than
through the MXU-signing wrapper (no MXU package needed, just the binary the
device already runs unpackaged at `/home/app/app`).

Two publishes: the first with the overflowing title (deployed, captured,
found broken), the second with the trimmed one (deployed, captured, landed).

## Deploy, verify — `app@192.168.1.219`

Checked before touching anything: `who` showed only this session's own ssh
connection, no `touch_inject`/`drm_witness`/runner processes running,
`d24-testui` active / `matrix-app` inactive — matches the idle state S105
handed back, no sign of anyone at the panel.

| artefact | md5 | rollback |
|---|---|---|
| `/home/app/app` | `5981fd34614cd29f5fc304908e251a1e` | `/home/app/app.bak-s107-pre` (`998a12bfe5daaca4dd924f9dc8673397`, the S102 build S105 also left in place) |

Both publishes' md5s matched their scp'd copies before install
(`7e7e1aa2…` for the overflowing build, `5981fd34…` for the landed one — only
the second is what's live now). `d24-testui` stopped for the binary swap
each time, `matrix-app` never touched.

Capture: reused S97's `MX_DRM_CAPTURE_PATH`/`MX_DRM_CAPTURE_MS` systemd
drop-in mechanism, own file (`s107-capture.conf`, distinct path from S105's
still-present `s105-capture.conf` — left that one exactly as found, it isn't
this dispatch's to clean up). Removed my own drop-in and `daemon-reload`ed
once the second capture confirmed the fix; did not restart `d24-testui`
again afterward since the running instance already reflects the landed
title and a further restart wasn't needed for anything this dispatch asked.

**On-glass confirmation**: `live-title-landed.png` — title bar reads
`D24 SELF-TEST · 2026-09-24 14:49`, one line, `QUEUEPOS`/`SCORESUB` below it
un-overlapped, `d24-testui` running the newly deployed binary.

## Handback

`d24-testui` active, `matrix-app` inactive, `AN_EN` (GPIO26) still `lo`
throughout — never written, matches every reading taken this session.
Capture drop-in this session added (`s107-capture.conf`) removed; S105's own
leftover (`s105-capture.conf`) left in place, not this dispatch's item.
Local capture PNGs on the unit deleted after pulling copies down.

## Status: 🟢 done

Title stamp landed (`D24 SELF-TEST · 2026-09-24 14:49` shape, not the
dispatch's literal example — see the 🔴 above for why and what a fuller
shape would need), rebuild confirmed necessary and done, deploy md5-matched
both ways, on-glass capture taken. Committed and pushed to `main`.
