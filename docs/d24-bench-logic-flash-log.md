provenance: AI-drafted 2026-09-20 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# D24 bench (MW-D24-2) — the dated LOGIC (CPLD) flash log

S84 gate 1. This settles S83-Q3: a dated record of every LOGIC/CPLD flash on
the MW-D24-2 bench (192.168.1.219) since the artifact's history became
visible in the bench's own log, cross-referenced against the session record
in this repo.

**Raw record**: `/home/app/logic-flash.log` on MW-D24-2, 2,284,436 lines,
56 flash events (56 `=== ` header lines). This document does not re-fetch
that file — the bench was not touched to produce it — it works from the
56 header lines the dispatching session already extracted, in file order,
reproduced as Table 1's first three columns.

**Method**:
- Table 1's `#`, `UTC timestamp`, `artifact` and `rc` columns are the
  `=== ` header lines verbatim, renumbered 1–56.
- `design_id` is read from the named artifact's own `.manifest` file in
  `shared/dsp4-logic/bitstream/` (or `retired/` for the three artifacts moved
  there). Where a manifest carries no `design_id:` line at all, the table
  says `NONE` and a footnote gives the reason on record.
- `md5_svf` is the artifact's md5. Two manifests (`s37_shipping_step0` and
  `s41_mhrx_pullup_off`) state `md5_svf` explicitly — those values are used
  as written. No other manifest in this tree carries an `md5_svf` field (the
  design-ID-bearing artifacts identify themselves on the part by knock
  instead), so for those artifacts the value shown is `md5sum` computed
  directly against the `.svf` file **already present in this tree**, marked
  `†`. This is not an invented number: for the one artifact where an
  independent manifest also quotes it (`a1f6672af6c3`'s md5 is given as the
  rollback line in `s37_shipping_step0`'s manifest), the quoted and computed
  values agree byte for byte.
- Every one of the 56 log entries names an artifact that is still present in
  this tree, either in `shared/dsp4-logic/bitstream/` or in its `retired/`
  subfolder — none of the 56 rows reads `not in tree`.
- `session` is inferred by bracketing each flash timestamp between
  consecutive HUB DISPATCH headers in `tasks.md` and matching the artifact
  named against what that session's own report says it flashed. Sessions
  that state their exact flash sequence in prose (S38, S77, S78, S79, S80,
  S81, S82, S83) are matched artifact-for-artifact and the mapping is
  reported with high confidence. Where no dated dispatch or report claims a
  block of flashes, the table says `?` — see Note A below Table 1.

## Table 1 — every flash event

| # | UTC timestamp | artifact | design_id | md5_svf | rc | session |
|---|---|---|---|---|---|---|
| 1 | 2026-09-11T02:05:08Z | `dsp4_logic.a1f6672af6c3` | NONE¹ | `dd1e09185804cb2e451d5089cdd56be3` | rc=0 | ? (Note A) |
| 2 | 2026-09-11T02:06:10Z | `dsp4_logic.a1f6672af6c3` | NONE¹ | `dd1e09185804cb2e451d5089cdd56be3` | rc=0 | ? (Note A) |
| 3 | 2026-09-11T02:07:12Z | `dsp4_logic.a1f6672af6c3` | NONE¹ | `dd1e09185804cb2e451d5089cdd56be3` | rc=0 | ? (Note A) |
| 4 | 2026-09-11T02:08:15Z | `dsp4_logic_driveall.e13b5dec84e0` | 32'h5dec84e0 | `424031b1e16e56b34527980ec99a34e2`† | rc=0 | ? (Note A) |
| 5 | 2026-09-11T02:09:17Z | `dsp4_logic_driveall.e13b5dec84e0` | 32'h5dec84e0 | `424031b1e16e56b34527980ec99a34e2`† | rc=0 | ? (Note A) |
| 6 | 2026-09-11T02:10:19Z | `dsp4_logic_driveall.e13b5dec84e0` | 32'h5dec84e0 | `424031b1e16e56b34527980ec99a34e2`† | rc=0 | ? (Note A) |
| 7 | 2026-09-11T02:11:23Z | `dsp4_logic.a1f6672af6c3` | NONE¹ | `dd1e09185804cb2e451d5089cdd56be3` | rc=0 | ? (Note A) |
| 8 | 2026-09-11T02:12:24Z | `dsp4_logic.a1f6672af6c3` | NONE¹ | `dd1e09185804cb2e451d5089cdd56be3` | rc=0 | ? (Note A) |
| 9 | 2026-09-11T02:13:25Z | `dsp4_logic.a1f6672af6c3` | NONE¹ | `dd1e09185804cb2e451d5089cdd56be3` | rc=0 | ? (Note A) |
| 10 | 2026-09-11T02:17:36Z | `dsp4_logic_driveall.e13b5dec84e0` | 32'h5dec84e0 | `424031b1e16e56b34527980ec99a34e2`† | rc=0 | ? (Note A) |
| 11 | 2026-09-11T02:18:41Z | `dsp4_logic.a1f6672af6c3` | NONE¹ | `dd1e09185804cb2e451d5089cdd56be3` | rc=0 | ? (Note A) |
| 12 | 2026-09-11T02:29:24Z | `dsp4_logic_maincap.d903ae1ac4a9` | 32'hae1ac4a9 | `e08a52d06bf60a2ba64037566c70d67f`† | rc=0 | ? (Note A) |
| 13 | 2026-09-11T02:40:07Z | `dsp4_logic.a1f6672af6c3` | NONE¹ | `dd1e09185804cb2e451d5089cdd56be3` | rc=0 | ? (Note A) |
| 14 | 2026-09-11T03:07:12Z | `dsp4_logic_driveall.e13b5dec84e0` | 32'h5dec84e0 | `424031b1e16e56b34527980ec99a34e2`† | rc=0 | ? (Note A) |
| 15 | 2026-09-11T04:48:47Z | `dsp4_logic.a1f6672af6c3` | NONE¹ | `dd1e09185804cb2e451d5089cdd56be3` | rc=0 | ? (Note A) |
| 16 | 2026-09-11T05:13:20Z | `dsp4_logic_driveall.e13b5dec84e0` | 32'h5dec84e0 | `424031b1e16e56b34527980ec99a34e2`† | rc=0 | ? (Note A) |
| 17 | 2026-09-11T06:20:34Z | `dsp4_logic_maincap.d903ae1ac4a9` | 32'hae1ac4a9 | `e08a52d06bf60a2ba64037566c70d67f`† | rc=0 | ? (Note A) |
| 18 | 2026-09-11T06:38:23Z | `dsp4_logic_pisel.bd9c100db7c2` | NONE² | `931955799fa5a07d978f1724453304d9`† | rc=0 | ? (Note A) |
| 19 | 2026-09-11T06:43:33Z | `dsp4_logic.a1f6672af6c3` | NONE¹ | `dd1e09185804cb2e451d5089cdd56be3` | rc=0 | ? (Note A) |
| 20 | 2026-09-12T17:41:41Z | `s37_shipping_step0.c62c024714f2` | NONE³ | `d47b74c6c881b82a110491266a6bd31d` | rc=0 | S38 |
| 21 | 2026-09-12T17:52:07Z | `dsp4_logic.a1f6672af6c3` | NONE¹ | `dd1e09185804cb2e451d5089cdd56be3` | rc=0 | S38 |
| 22 | 2026-09-12T17:58:03Z | `s37_shipping_step0.c62c024714f2` | NONE³ | `d47b74c6c881b82a110491266a6bd31d` | rc=0 | S38 |
| 23 | 2026-09-13T13:08:44Z | `s41_mhrx_pullup_off.15f3ae07dae1` | NONE³ | `fc6ce23ed14cda464f277a56cf21ab92` | rc=0 | S41 |
| 24 | 2026-09-13T13:10:00Z | `s37_shipping_step0.c62c024714f2` | NONE³ | `d47b74c6c881b82a110491266a6bd31d` | rc=0 | S41 |
| 25 | 2026-09-13T13:11:14Z | `s41_mhrx_pullup_off.15f3ae07dae1` | NONE³ | `fc6ce23ed14cda464f277a56cf21ab92` | rc=0 | S41 |
| 26 | 2026-09-19T21:47:06Z | `dsp4_logic_driveall.14df62d98a4d` | 32'h62d98a4d | `b07b03f5169239c84839c8d638205b82`† | rc=0 | S77 |
| 27 | 2026-09-19T22:10:12Z | `dsp4_logic_driveall.907492a607bd` | 32'h92a607bd | `c925426d4e5eaa71008130880ae404cd`† | rc=0 | S77 |
| 28 | 2026-09-19T22:20:29Z | `dsp4_logic_pisel.983656926e3e` | 32'h56926e3e | `6270023ea2ab0ea9e11e3d144442ee10`† | rc=0 | S77 |
| 29 | 2026-09-19T22:22:09Z | `dsp4_logic_driveall.14df62d98a4d` | 32'h62d98a4d | `b07b03f5169239c84839c8d638205b82`† | rc=0 | S77 |
| 30 | 2026-09-19T22:25:59Z | `dsp4_logic_driveall.907492a607bd` | 32'h92a607bd | `c925426d4e5eaa71008130880ae404cd`† | rc=0 | S77 |
| 31 | 2026-09-19T22:28:52Z | `dsp4_logic_driveall.14df62d98a4d` | 32'h62d98a4d | `b07b03f5169239c84839c8d638205b82`† | rc=0 | S77 |
| 32 | 2026-09-19T23:47:59Z | `dsp4_logic_driveall.907492a607bd` | 32'h92a607bd | `c925426d4e5eaa71008130880ae404cd`† | rc=0 | S77 |
| 33 | 2026-09-20T00:03:33Z | `dsp4_logic_driveall.14df62d98a4d` | 32'h62d98a4d | `b07b03f5169239c84839c8d638205b82`† | rc=0 | S77 |
| 34 | 2026-09-20T00:34:29Z | `dsp4_logic.a1f6672af6c3` | NONE¹ | `dd1e09185804cb2e451d5089cdd56be3` | rc=0 | S77 |
| 35 | 2026-09-20T00:56:22Z | `dsp4_logic_driveall.14df62d98a4d` | 32'h62d98a4d | `b07b03f5169239c84839c8d638205b82`† | rc=0 | S78 |
| 36 | 2026-09-20T03:03:32Z | `dsp4_logic_driveall.1ee6b5056fb7` | 32'hb5056fb7 | `49deb0ebca34a3037a388fe8564a93de`† | rc=0 | S78 |
| 37 | 2026-09-20T03:05:21Z | `dsp4_logic_driveall.c49f4128a083` | 32'h4128a083 | `b85cd28172a33ddd1eb4bc962568839f`† | rc=0 | S78 |
| 38 | 2026-09-20T03:15:16Z | `dsp4_logic.a1f6672af6c3` | NONE¹ | `dd1e09185804cb2e451d5089cdd56be3` | rc=0 | S78 |
| 39 | 2026-09-20T03:40:23Z | `dsp4_logic_driveall.c49f4128a083` | 32'h4128a083 | `b85cd28172a33ddd1eb4bc962568839f`† | rc=0 | S79 |
| 40 | 2026-09-20T05:55:50Z | `dsp4_logic.a1f6672af6c3` | NONE¹ | `dd1e09185804cb2e451d5089cdd56be3` | rc=0 | S79 |
| 41 | 2026-09-20T05:57:25Z | `dsp4_logic.a1f6672af6c3` | NONE¹ | `dd1e09185804cb2e451d5089cdd56be3` | rc=0 | S79 |
| 42 | 2026-09-20T06:27:59Z | `dsp4_logic_driveall.c49f4128a083` | 32'h4128a083 | `b85cd28172a33ddd1eb4bc962568839f`† | rc=0 | S80 |
| 43 | 2026-09-20T09:06:02Z | `dsp4_logic.a1f6672af6c3` | NONE¹ | `dd1e09185804cb2e451d5089cdd56be3` | rc=0 | S80 |
| 44 | 2026-09-20T09:51:58Z | `dsp4_logic.7a6a4529f29c` | 32'h4529f29c | `48ddd02299b166127429eb2ad10db492`† | rc=0 | S81 |
| 45 | 2026-09-20T09:57:44Z | `dsp4_logic.a1f6672af6c3` | NONE¹ | `dd1e09185804cb2e451d5089cdd56be3` | rc=0 | S81 |
| 46 | 2026-09-20T10:02:34Z | `dsp4_logic.7a6a4529f29c` | 32'h4529f29c | `48ddd02299b166127429eb2ad10db492`† | rc=0 | S81 |
| 47 | 2026-09-20T10:04:17Z | `dsp4_logic.a1f6672af6c3` | NONE¹ | `dd1e09185804cb2e451d5089cdd56be3` | rc=0 | S81 |
| 48 | 2026-09-20T10:29:25Z | `dsp4_logic.7a6a4529f29c` | 32'h4529f29c | `48ddd02299b166127429eb2ad10db492`† | rc=0 | S82 |
| 49 | 2026-09-20T11:20:00Z | `dsp4_logic_driveall.c49f4128a083` | 32'h4128a083 | `b85cd28172a33ddd1eb4bc962568839f`† | rc=0 | S82 |
| 50 | 2026-09-20T11:53:57Z | `dsp4_logic.7a6a4529f29c` | 32'h4529f29c | `48ddd02299b166127429eb2ad10db492`† | rc=0 | S82 |
| 51 | 2026-09-20T11:55:20Z | `dsp4_logic_maincap.33b6eb00a4e8` | 32'heb00a4e8 | `33bd49193173e0d57012ed27417bd00c`† | rc=0 | S82 |
| 52 | 2026-09-20T11:56:21Z | `dsp4_logic_maincap.33b6eb00a4e8` | 32'heb00a4e8 | `33bd49193173e0d57012ed27417bd00c`† | rc=0 | S82 |
| 53 | 2026-09-20T12:09:01Z | `dsp4_logic.7a6a4529f29c` | 32'h4529f29c | `48ddd02299b166127429eb2ad10db492`† | rc=0 | S82 |
| 54 | 2026-09-20T13:04:48Z | `dsp4_logic_maincap.33b6eb00a4e8` | 32'heb00a4e8 | `33bd49193173e0d57012ed27417bd00c`† | rc=0 | S83 |
| 55 | 2026-09-20T13:10:37Z | `dsp4_logic_pisel.983656926e3e` | 32'h56926e3e | `6270023ea2ab0ea9e11e3d144442ee10`† | rc=0 | S83 |
| 56 | 2026-09-20T13:15:54Z | `dsp4_logic.7a6a4529f29c` | 32'h4529f29c | `48ddd02299b166127429eb2ad10db492`† | rc=0 | S83 |

Footnotes on `design_id` / `md5_svf`:

- `¹` `dsp4_logic.a1f6672af6c3`'s own manifest (`retired/dsp4_logic.a1f6672af6c3.manifest`)
  carries no `design_id:` line at all — it was built 2026-08-21, before the
  design-ID/knock readback block existed in the RTL (added at commit
  `3152e2b1`, per `s37_shipping_step0`'s manifest). Its md5 is quoted, not
  computed here: `s37_shipping_step0.c62c024714f2`'s manifest states it
  explicitly as the rollback artifact's md5 (`dd1e09185804cb2e451d5089cdd56be3`,
  svf), and this matches the tree file byte for byte.
- `²` `dsp4_logic_pisel.bd9c100db7c2`'s manifest (`retired/`) likewise carries
  no `design_id:` line — built 2026-09-09, also before the design-ID feature.
- `³` `s37_shipping_step0.c62c024714f2` and `s41_mhrx_pullup_off.15f3ae07dae1`
  state `design_id: NONE` explicitly and give the reason in writing: the
  design-ID/knock block costs +124 logic elements, which the staged-bring-up
  step-0 and step-0-plus-one-pin artifacts are deliberately not allowed to
  carry (S36 §1.1, S37, S41 manifests).
- `†` no md5 field exists in this artifact's own manifest; the value shown is
  `md5sum` computed directly against the `.svf` file already committed in
  `shared/dsp4-logic/bitstream/` (or `retired/`), not a manifest field.

**Note A (rows 1–19, 2026-09-11 02:05–06:43Z).** No HUB DISPATCH entry and no
session report in this repo claims this block. The only D24-labelled
dispatches for that calendar day are S34 (13:32Z), S35 (14:03Z), S36 (14:19Z)
and S37 (14:47Z) — all several hours *after* this window closes, and all
four say explicitly that nothing was flashed that session (S34/S36/S37 are
titled "desk:" and touched no unit; S35's own report states in its first
finding "NOTHING WAS FLASHED", CPLD "not touched — shipping `a1f6672af6c3`
left in place"). So whoever ran these 19 flashes did so before any dispatch
that day existed, on a bitstream (`a1f6672af6c3`) that predates the converter
clock fix (built 2026-08-21) and alternated it repeatedly against two other
pre-fix artifacts (`driveall.e13b5dec84e0`, `maincap.d903ae1ac4a9`,
`pisel.bd9c100db7c2`, all built 2026-09-09/10). It reads as bench/tool
exercise ahead of the day's dispatched work, not as a numbered session's
result, and is marked `?` rather than guessed.

## Table 2 — residency: what the part actually carried, and for how long

Consecutive flashes of the same artifact are collapsed into one interval.
This table has one row per *change of what was on the part*, not one row
per flash command.

| # | bitstream resident | from (UTC) | to (UTC) | duration | what was running |
|---|---|---|---|---|---|
| 1 | `dsp4_logic.a1f6672af6c3` | 2026-09-11T02:05:08Z | 2026-09-11T02:08:15Z | 3m 7s | ? (Note A) |
| 2 | `dsp4_logic_driveall.e13b5dec84e0` | 2026-09-11T02:08:15Z | 2026-09-11T02:11:23Z | 3m 8s | ? (Note A) |
| 3 | `dsp4_logic.a1f6672af6c3` | 2026-09-11T02:11:23Z | 2026-09-11T02:17:36Z | 6m 13s | ? (Note A) |
| 4 | `dsp4_logic_driveall.e13b5dec84e0` | 2026-09-11T02:17:36Z | 2026-09-11T02:18:41Z | 1m 5s | ? (Note A) |
| 5 | `dsp4_logic.a1f6672af6c3` | 2026-09-11T02:18:41Z | 2026-09-11T02:29:24Z | 10m 43s | ? (Note A) |
| 6 | `dsp4_logic_maincap.d903ae1ac4a9` | 2026-09-11T02:29:24Z | 2026-09-11T02:40:07Z | 10m 43s | ? (Note A) |
| 7 | `dsp4_logic.a1f6672af6c3` | 2026-09-11T02:40:07Z | 2026-09-11T03:07:12Z | 27m 5s | ? (Note A) |
| 8 | `dsp4_logic_driveall.e13b5dec84e0` | 2026-09-11T03:07:12Z | 2026-09-11T04:48:47Z | 1h 41m 35s | ? (Note A) |
| 9 | `dsp4_logic.a1f6672af6c3` | 2026-09-11T04:48:47Z | 2026-09-11T05:13:20Z | 24m 33s | ? (Note A) |
| 10 | `dsp4_logic_driveall.e13b5dec84e0` | 2026-09-11T05:13:20Z | 2026-09-11T06:20:34Z | 1h 7m 14s | ? (Note A) |
| 11 | `dsp4_logic_maincap.d903ae1ac4a9` | 2026-09-11T06:20:34Z | 2026-09-11T06:38:23Z | 17m 49s | ? (Note A) |
| 12 | `dsp4_logic_pisel.bd9c100db7c2` | 2026-09-11T06:38:23Z | 2026-09-11T06:43:33Z | 5m 10s | ? (Note A) |
| 13 | `dsp4_logic.a1f6672af6c3` | 2026-09-11T06:43:33Z | 2026-09-12T17:41:41Z | 1d 10h 58m 8s | standing overnight/daytime; S34–S37 (desk only, nothing flashed) ran inside this window |
| 14 | `s37_shipping_step0.c62c024714f2` | 2026-09-12T17:41:41Z | 2026-09-12T17:52:07Z | 10m 26s | S38 gate 2, first flash |
| 15 | `dsp4_logic.a1f6672af6c3` | 2026-09-12T17:52:07Z | 2026-09-12T17:58:03Z | 5m 56s | S38's deliberate rollback CONTROL — six minutes, not a live-audio measurement ("audio still does not pass" at this point regardless) |
| 16 | `s37_shipping_step0.c62c024714f2` | 2026-09-12T17:58:03Z | 2026-09-13T13:08:44Z | 19h 10m 41s | S38's restore; standing through S39/S40 ("first audio", 09-12 evening) |
| 17 | `s41_mhrx_pullup_off.15f3ae07dae1` | 2026-09-13T13:08:44Z | 2026-09-13T13:10:00Z | 1m 16s | S41 gate, first flash |
| 18 | `s37_shipping_step0.c62c024714f2` | 2026-09-13T13:10:00Z | 2026-09-13T13:11:14Z | 1m 14s | S41's rollback control |
| 19 | `s41_mhrx_pullup_off.15f3ae07dae1` | 2026-09-13T13:11:14Z | 2026-09-19T21:47:06Z | **6d 8h 35m 52s** | **THE SIX-DAY GAP.** S54, S55, S58 (09-16) and S69, S70, S71, S72 (09-19 daytime) all ran inside this single interval — nothing touched the CPLD between S41 and S77. |
| 20 | `dsp4_logic_driveall.14df62d98a4d` | 2026-09-19T21:47:06Z | 2026-09-19T22:10:12Z | 23m 6s | S77 arm (driven ceiling) |
| 21 | `dsp4_logic_driveall.907492a607bd` | 2026-09-19T22:10:12Z | 2026-09-19T22:20:29Z | 10m 17s | S77 bitstream-base control (pre-S34/S36 driveall) |
| 22 | `dsp4_logic_pisel.983656926e3e` | 2026-09-19T22:20:29Z | 2026-09-19T22:22:09Z | 1m 40s | S77 CM4↔CPLD link check |
| 23 | `dsp4_logic_driveall.14df62d98a4d` | 2026-09-19T22:22:09Z | 2026-09-19T22:25:59Z | 3m 50s | S77 arm, resumed |
| 24 | `dsp4_logic_driveall.907492a607bd` | 2026-09-19T22:25:59Z | 2026-09-19T22:28:52Z | 2m 53s | S77 control, resumed |
| 25 | `dsp4_logic_driveall.14df62d98a4d` | 2026-09-19T22:28:52Z | 2026-09-19T23:47:59Z | 1h 19m 7s | S77 arm, resumed |
| 26 | `dsp4_logic_driveall.907492a607bd` | 2026-09-19T23:47:59Z | 2026-09-20T00:03:33Z | 15m 34s | S77 control, resumed |
| 27 | `dsp4_logic_driveall.14df62d98a4d` | 2026-09-20T00:03:33Z | 2026-09-20T00:34:29Z | 30m 56s | S77 arm, resumed |
| 28 | `dsp4_logic.a1f6672af6c3` | 2026-09-20T00:34:29Z | 2026-09-20T00:56:22Z | 21m 53s | S77's own "as found" restore at handback |
| 29 | `dsp4_logic_driveall.14df62d98a4d` | 2026-09-20T00:56:22Z | 2026-09-20T03:03:32Z | 2h 7m 10s | S78 bisect baseline — "what was on the CPLD for every capacity row in this report" |
| 30 | `dsp4_logic_driveall.1ee6b5056fb7` | 2026-09-20T03:03:32Z | 2026-09-20T03:05:21Z | 1m 49s | S78 A/B control (`main`, pre-fix) |
| 31 | `dsp4_logic_driveall.c49f4128a083` | 2026-09-20T03:05:21Z | 2026-09-20T03:15:16Z | 9m 55s | S78 A/B fixed arm |
| 32 | `dsp4_logic.a1f6672af6c3` | 2026-09-20T03:15:16Z | 2026-09-20T03:40:23Z | 25m 7s | S78's restore at handback |
| 33 | `dsp4_logic_driveall.c49f4128a083` | 2026-09-20T03:40:23Z | 2026-09-20T05:55:50Z | 2h 15m 27s | S79 driven ladders |
| 34 | `dsp4_logic.a1f6672af6c3` | 2026-09-20T05:55:50Z | 2026-09-20T05:57:25Z | 1m 35s | S79 restore (1st of two back-to-back flashes of the same artifact — report does not explain the second) |
| 35 | `dsp4_logic.a1f6672af6c3` | 2026-09-20T05:57:25Z | 2026-09-20T06:27:59Z | 30m 34s | S79 restore, standing |
| 36 | `dsp4_logic_driveall.c49f4128a083` | 2026-09-20T06:27:59Z | 2026-09-20T09:06:02Z | 2h 38m 3s | S80 driven ladders |
| 37 | `dsp4_logic.a1f6672af6c3` | 2026-09-20T09:06:02Z | 2026-09-20T09:51:58Z | 45m 56s | S80's restore at handback; standing into S81's start |
| 38 | `dsp4_logic.7a6a4529f29c` | 2026-09-20T09:51:58Z | 2026-09-20T09:57:44Z | 5m 46s | S81 CDC witness knock #1 (post-fix tree — first time this artifact is ever on the part, not yet named `shipping`) |
| 39 | `dsp4_logic.a1f6672af6c3` | 2026-09-20T09:57:44Z | 2026-09-20T10:02:34Z | 4m 50s | S81 A-B-A control, leg 2 |
| 40 | `dsp4_logic.7a6a4529f29c` | 2026-09-20T10:02:34Z | 2026-09-20T10:04:17Z | 1m 43s | S81 CDC witness knock #2 |
| 41 | `dsp4_logic.a1f6672af6c3` | 2026-09-20T10:04:17Z | 2026-09-20T10:29:25Z | 25m 8s | S81's restore at handback — **the last time `a1f6672af6c3` is ever flashed in this log** |
| 42 | `dsp4_logic.7a6a4529f29c` | 2026-09-20T10:29:25Z | 2026-09-20T11:20:00Z | 50m 35s | **S82 — shipping formally moves to `7a6a4529f29c`** |
| 43 | `dsp4_logic_driveall.c49f4128a083` | 2026-09-20T11:20:00Z | 2026-09-20T11:53:57Z | 33m 57s | S82 converter re-take on driveall |
| 44 | `dsp4_logic.7a6a4529f29c` | 2026-09-20T11:53:57Z | 2026-09-20T11:55:20Z | 1m 23s | S82, back to shipping |
| 45 | `dsp4_logic_maincap.33b6eb00a4e8` | 2026-09-20T11:55:20Z | 2026-09-20T12:09:01Z | 13m 41s | S82 maincap for latency (flashed twice, same artifact) |
| 46 | `dsp4_logic.7a6a4529f29c` | 2026-09-20T12:09:01Z | 2026-09-20T13:04:48Z | 55m 47s | S82's close / S83's start, standing on shipping |
| 47 | `dsp4_logic_maincap.33b6eb00a4e8` | 2026-09-20T13:04:48Z | 2026-09-20T13:10:37Z | 5m 49s | S83 latency arm (maincap) |
| 48 | `dsp4_logic_pisel.983656926e3e` | 2026-09-20T13:10:37Z | 2026-09-20T13:15:54Z | 5m 17s | S83 latency arm (pisel, LOGIC-only reference) |
| 49 | `dsp4_logic.7a6a4529f29c` | 2026-09-20T13:15:54Z | *(current, at S84's dispatch)* | ongoing | S83's final restore — still resident as of this table |

## Table 3 — the named sessions, dated

| session | date(s) it ran | bitstream(s) resident during it | evidence | measurements taken on |
|---|---|---|---|---|
| S54 | 2026-09-16 (dispatched 08:40Z) | `s41_mhrx_pullup_off.15f3ae07dae1` (whole six-day-gap interval, Table 2 row 19) | No CPLD flash between 2026-09-13T13:11:14Z and 2026-09-19T21:47:06Z (Table 1 rows 25→26); S54 dispatched 09-16, entirely inside that window | **`s41_mhrx_pullup_off.15f3ae07dae1`**, not `a1f6672af6c3` |
| S55 | 2026-09-16 (dispatched 10:53Z) | `s41_mhrx_pullup_off.15f3ae07dae1` | same interval as S54 | **`s41_mhrx_pullup_off.15f3ae07dae1`** |
| S58 | 2026-09-16 (dispatched 13:38Z) | `s41_mhrx_pullup_off.15f3ae07dae1` | same interval | **`s41_mhrx_pullup_off.15f3ae07dae1`** |
| S69 | 2026-09-19 (dispatched 07:22Z) | `s41_mhrx_pullup_off.15f3ae07dae1` | dispatched 07:22Z, well inside the gap (ends 21:47Z that evening); S69 flashed MCU firmware (H1S1) only — `MW/D24/DSP/s69/talkback.md` records no LOGIC/CPLD flash | **`s41_mhrx_pullup_off.15f3ae07dae1`** (its AK4619/H1S1 work never touched the CPLD) |
| S70 | 2026-09-19 (dispatched 08:23Z) | `s41_mhrx_pullup_off.15f3ae07dae1` | dispatched 08:23Z, inside the gap; `MW/D24/DSP/s70/talkback.md` records the SHARC pair restored but no LOGIC flash | **`s41_mhrx_pullup_off.15f3ae07dae1`** — the T1 (MGN2R law) and T3 (THD+N) numbers in S70's report were taken on this bitstream |
| S71 | 2026-09-19 (dispatched 09:05Z) | `s41_mhrx_pullup_off.15f3ae07dae1` | `MW/D24/DSP/s71/codec-lanes.md`: "Desk only, 2026-09-19. No unit was touched: no boot, no flash, no config, no rails." | n/a — desk only, but the unit it reasoned about was carrying this bitstream |
| S72 | 2026-09-19 (dispatched 09:40Z) | `s41_mhrx_pullup_off.15f3ae07dae1` | `MW/D24/DSP/s72/aux-in-right-leg.md`: "Desk only, 2026-09-19. No unit was touched." | n/a — desk only |
| S79 | 2026-09-20 (dispatched 03:20Z) | `dsp4_logic_driveall.c49f4128a083` (driven ladders, Table 2 row 33), `dsp4_logic.a1f6672af6c3` (as-found restore, rows 34–35) | `MW/D24/DSP/s79/bypass.md`: "`dsp4_logic_driveall.c49f4128a083` was flashed for the driven ladders (FLASH OK on attempt 1), and `dsp4_logic.a1f6672af6c3` — the shipping bitstream — restored" | **`dsp4_logic_driveall.c49f4128a083`** for the driven-ladder rows; `a1f6672af6c3` only as the closing as-found state |
| S81 | 2026-09-20 (dispatched 09:23Z) | alternating `dsp4_logic.a1f6672af6c3` and `dsp4_logic.7a6a4529f29c` (Table 2 rows 37–41) | `MW/D24/DSP/s81/witnesses.md` line ~491: "Three flashes this session, all first-attempt: witness → shipping → witness → shipping" | Both — this is the A-B-A comparison that first showed the converters are not dark, the flashed bitstream (`a1f6672af6c3`) is; **AK5558/mic lanes read exact digital zero on `7a6a4529f29c` too** (S81 §3.6) |
| S82 | 2026-09-20 (dispatched 10:19Z) | `dsp4_logic.7a6a4529f29c` (shipping, from 10:29:25Z on), `dsp4_logic_driveall.c49f4128a083`, `dsp4_logic_maincap.33b6eb00a4e8` (Table 2 rows 42–46) | `MW/D24/DSP/s82/signed.md` line ~734: "Five flashes this session, all first-attempt: shipping → driveall → shipping → maincap → shipping" | **`dsp4_logic.7a6a4529f29c`** becomes the shipping bitstream in `loadlogic.sh` from this session on; `a1f6672af6c3` is retired to `shared/dsp4-logic/bitstream/retired/` and never flashed again |
| S83 | 2026-09-20 (dispatched 12:18Z) | `dsp4_logic.7a6a4529f29c` (start/end), `dsp4_logic_maincap.33b6eb00a4e8`, `dsp4_logic_pisel.983656926e3e` (Table 2 rows 46–49) | `MW/D24/DSP/s83/contract-lanes.md` line ~378: "`maincap` and `pisel` flashed for the latency arms... `dsp4_logic.7a6a4529f29c` — shipping — restored last" | **`dsp4_logic.7a6a4529f29c`** — the 82-sample latency contract row and the mic-lane dark finding (S83-6) are both taken on it |

## FINDINGS

1. **The "one month on `dsp4_logic.a1f6672af6c3`" claim is FALSE.** The log
   shows `a1f6672af6c3` resident for roughly 35 hours total between S37's
   merge (09-11 06:43) and S38's flash of `s37_shipping_step0` (09-12
   17:41), then not resident again at all until S77's closing restore on
   09-20 00:34 — a gap of essentially the entire intervening week. For the
   19 hours from 09-12 18:00 to 09-13 13:09, and again for the 6 days 8.6
   hours from 09-13 13:11 to 09-19 21:47, the part actually carried
   `s37_shipping_step0.c62c024714f2` and then `s41_mhrx_pullup_off.15f3ae07dae1`
   respectively — both of which, unlike `a1f6672af6c3`, DRIVE the converter
   clock pair. `loadlogic.sh`'s `shipping` *label* pointed at `a1f6672af6c3`
   continuously from S37 to S82, but the *part* did not carry that bitstream
   for most of that window.

   The mechanism matters and is not the one the retirement note states, so
   it is set down here from the source rather than inferred from dates.
   `git merge-base --is-ancestor ded71079 61e38ce3` returns FALSE: the
   step-0 shipping base that `s41_mhrx_pullup_off` branches from does NOT
   contain `ded71079`, the S34 converter-clock commit. It does not need to.
   At `61e38ce3` the top module already reads

       output wire conv_bck,    // pin 142 (C1): 12.288 MHz, TDM8
       output wire conv_fs,     // pin 141 (L0): 48 kHz frame sync
       ...
       assign conv_bck = bck8;
       assign conv_fs  = fs8;

   — the same two lines, character for character, that HEAD carries. At
   `a4ee3d1f` (`a1f6672af6c3`'s commit) those ports do not exist at all;
   the pins are straps. So there are TWO lineages that drive the pair, the
   step-0 shipping branch and post-`ded71079` `main`, and exactly one that
   does not. **"Pre-S34" is therefore not the discriminator and must not be
   used as one** — `s41_mhrx_pullup_off` is pre-S34 by ancestry and drives
   the clock, which S41 confirmed by measurement at the time (U3 pin 142 =
   12.288 MHz, pin 141 = 48 kHz, recorded in its manifest's `S41_PROOF`)
   and S84 confirmed again by reading all four codec lanes live on it. The
   discriminator is the artifact.
2. **S54–S58's live preamp-noise measurements of 2026-09-16 were taken on
   `s41_mhrx_pullup_off.15f3ae07dae1`.** That bitstream was flashed once, at
   2026-09-13T13:11:14Z, and nothing touched the CPLD again until
   2026-09-19T21:47:06Z (Table 2 row 19) — a single, unbroken six-day
   residency that covers all three sessions with room either side. The same
   residency also covers S69, S70, S71 and S72 on 09-19: none of those four
   sessions flashed the LOGIC either (S69 flashed MCU firmware only; S70
   made no LOGIC flash; S71/S72 are desk-only), so S70's talkback/MGN2R/T1/T3
   numbers were likewise taken on `s41_mhrx_pullup_off`, not on any
   bitstream built afterward.
3. **`dsp4_logic.a1f6672af6c3` was never resident on a date when any session
   reported live AK5558/mic-ADC data, and it structurally could not have
   been.** S35 (2026-09-11) measured directly that with `a1f6672af6c3` on
   the part, J18 P37/P38 (the converter clock pair at the CPLD, U3 pins
   142/141 at the source) are dead — "nothing drives the converter bit clock
   or frame sync at all" is in the RTL's own comment on the pre-fix design,
   confirmed again by S81's git ancestry check
   (`a4ee3d1f` → `ded71079`, `a1f6672af6c3` predates the fix). The AK5558s
   and the AK4619 codec share that same clock pair, so no live conversion —
   mic-ADC or codec — is possible while `a1f6672af6c3` is flashed. Table 1
   confirms it independently: the only sessions in this record that report
   live converter data (S39/S40's first audio, S54–S58's preamp noise,
   S69/S70's codec/AK4619 work, S81/S82/S83's codec-lane and AK5558
   readings) all fall on intervals where the resident bitstream was
   `s37_shipping_step0`, `s41_mhrx_pullup_off`, `driveall`/`pisel`/`maincap`,
   or `dsp4_logic.7a6a4529f29c` — never `a1f6672af6c3`. Note that even the
   post-fix, clock-driving bitstreams still read the AK5558 lanes at exact
   digital zero (S81 §3.6, S82, S83-6) — that is a separate fault, and this
   flash log does not speak to it.

   It is no longer open. S84 repeated the sweep on `s41_mhrx_pullup_off`
   itself — the bitstream this table puts under S54–S58 — and got the same
   32 of 32 exact zeros with all four codec lanes live in the same pass, so
   there is no bitstream on which this instrument has ever seen those lanes
   work and no bisect to run. The authorised `ad[0..2]` witness then found
   all three AK5558 output lanes CARRYING DATA at the CPLD while the DSP's
   buffers read zero in the same pass on the same bitstream. The fault is
   downstream of the CPLD's input pins, not on the analog board. See
   `MW/D24/DSP/s84/mic-lanes.md`.
4. **What the hardcoded `shipping` label actually caused, per the log, is
   narrower than S83-Q3 feared.** S83-Q3's fear was that "any handback in
   [the S37–S82] window silently reflashed a bitstream driving no converter
   clock" — i.e., that calling `loadlogic.sh shipping` at the end of a
   session could, at any point across six-plus weeks, silently overwrite
   whatever real (clock-driving) bitstream was on the part with the dead
   `a1f6672af6c3`, unrecorded. The log says this did NOT happen during the
   long gap: zero LOGIC flashes of any kind occur between 2026-09-13T13:11:14Z
   and 2026-09-19T21:47:06Z, so `s41_mhrx_pullup_off` sat untouched through
   S54, S55, S58, S69, S70, S71 and S72 — the "shipping" label was never
   invoked in that window at all. The actual, measured cost of the
   hardcoded label is confined to the single night of 09-19/09-20, once
   sessions began treating "restore to shipping / as found" as routine
   bench hygiene at handback: S77, S78, S79 and S80 each genuinely re-flashed
   the clock-dead `a1f6672af6c3` for real, for 22–46 minutes at a stretch
   between their own diagnostic flashes (Table 2 rows 28, 32, 34–35, 37),
   making the unit briefly non-functional for any converter-clock-dependent
   audio at each handback, until S82 repointed the label at
   `dsp4_logic.7a6a4529f29c` and made `loadlogic.sh` refuse any artifact
   whose manifest carries no `design_id:` line (which `a1f6672af6c3` does
   not, and now cannot pass). So the label caused real, bounded,
   self-correcting outages measured in tens of minutes on one night — not
   the silent, unrecorded, multi-day corruption of the measurement record
   that S83-Q3 raised as a possibility. S38's own 6-minute rollback to
   `a1f6672af6c3` on 09-12 (row 21) was a deliberate, documented control,
   not an instance of the label problem.
5. Every one of the 56 flash events reads `rc=0` and every artifact named is
   still present in `shared/dsp4-logic/bitstream/` or its `retired/`
   subfolder — nothing in this log points at a missing or an orphaned
   artifact.
6. Rows 1–19 (2026-09-11, 02:05–06:43Z) cannot be attributed to any
   dispatched session in `tasks.md` (Note A) and are marked `?` rather than
   guessed; whoever ran them was exercising `a1f6672af6c3` against three
   other pre-converter-clock-fix artifacts before that day's dispatched desk
   work (S34–S37) began.

---

## S85 addendum (2026-09-20 evening)

Six more flashes, all FLASH-OK on attempt 1 with the design ID read back and
MATCHED before any reading was taken; the table above stops at S84 and this is
the continuation rather than a rewrite of it.

| artifact | design_id | what it was for |
|---|---|---|
| `dsp4_logic_adwit.f2f33d97f578` | `32'h3d97f578` | S85 gate 1 — the two bck8 edges, rails down and rails up |
| `dsp4_logic_adrt_adwit.43ec02c13e1a` | `32'h02c13e1a` | S85-5 — `ad[0..2]` as a register output |
| `dsp4_logic_adcdc_adwit.3490d03fcc18` | `32'hd03fcc18` | S85-6 — the mic lanes fed from `cdc_o` |
| `dsp4_logic_laneid_adwit.12f4fd1cbfc1` | `32'hfd1cbfc1` | S85-7 — every DSPA input pin names itself |
| `dsp4_logic_driveall.943f27966c28` | `32'h27966c28` | the S82 D24 driven capacity row, re-taken |
| `dsp4_logic.d02d83b3cc22` | `32'h83b3cc22` | **the adopted shipping label**, left on the part |

`logic_flash.sh`'s default rollback is now `dsp4_logic.d02d83b3cc22.svf` — set
from this table, after the flash, which is the rule the S84 entry above spells
out and the reason that line has been stale three times.

---

## S86 (2026-09-20 evening/night)

All FLASH-OK on attempt 1 with the design ID read back and MATCHED both before
the reading it was flashed for and after the restore.

| # | artifact | design_id | what it was for |
|---|---|---|---|
| 1 | `dsp4_logic_laneid_adwit.12f4fd1cbfc1` | `32'hfd1cbfc1` | S86-4 — every RX DMA entry decodes its own pin and slot |
| 2 | `dsp4_logic.d02d83b3cc22` | `32'h83b3cc22` | shipping restored for the EIN rows and the survey |
| 3 | `dsp4_logic_driveall.943f27966c28` | `32'h27966c28` | the S82 D24 driven capacity row |
| 4 | `dsp4_logic.d02d83b3cc22` | `32'h83b3cc22` | **shipping restored, and what the part is left carrying** |

`logic_flash.sh`'s default rollback stays `dsp4_logic.d02d83b3cc22.svf` — set
from this table, after the last flash, which is the rule the S84 entry spells
out.

## Procedure (S88, 2026-09-21) — two items the runbook was missing

S88 opened with the CPLD carrying `driveall` (`32'h27966c28`) instead of shipping, on a
unit S86 had logged as restored to shipping at handback the night before (Table 1's #4,
above). Nothing between S86's handback and S88's start is on record as a flash — so either
S86's restore-and-verify step didn't survive a power cycle, or the two are separated by an
untracked flash. Either way, "the log says shipping" was not sufficient; two procedure gaps
follow from it, both binding on every session that flashes or boots this bench from here on.

**1. `logic_flash.sh`'s own next-step line stops one step short, and a DSP boot+config must
follow every LOGIC flash before any reading is trusted.** The tool already prints "NEXT:
confirm what is actually on the part" and names `dsp4_logic_id.py` — that check is necessary
but not sufficient. A CPLD reflash changes `conv_bck`/`conv_fs`, and the DSP's SPORT
peripherals stay configured against the *pre-flash* clock relationship until
`dsp4_boot.py`/`dsp4_config.py` are re-run (S88 found this the hard way: the first
double-boot after the S88-1 reflash left MIC 5 dark; an identical second one brought it up).
**Runbook addition: every LOGIC flash ends with (a) `dsp4_logic_id.py` design-ID readback,
matched against the artifact's manifest, AND (b) a full DSP double boot+config
(`dsp4_boot.py` + `dsp4_config.py --chip 1` + `--chip 2`, twice, the standing S46/S70
recipe) before any audio reading is taken on that pair.** A design-ID match alone is not
proof the DSP side is caught up.

**2. Unit-as-found must be proven by a power cycle, not assumed from the last flash log
entry.** "Shipping bitstream restored" in a session's handback note is a statement about
what was written, not about what a MAX V answers after the bench has sat untouched. Add to
every session's unit-as-found checklist: **the shipping bitstream must be confirmed IN
FLASH by a power cycle (or, short of a full cycle, at minimum a fresh `dsp4_logic_id.py`
readback taken at the *start* of the next session, before trusting any prior session's
handback note)** — this is exactly the gap S88 fell into.

**3. Dead-lane triage order, going forward (S88's own path there was expensive — this is
what should have been step one).** When RX lanes read exact digital zero (or float around
the noise floor with no correlation to a known stimulus) on this bench:

1. **CPLD design-ID readback first** (`dsp4_logic_id.py`) — rules out or confirms the
   cheapest, most totalizing fault (wrong bitstream in flash) before touching anything else.
2. **AN_EN / 595 chain / DMA-alive checks** — GPIO26 state, a 595 chain readback (pass-2 =
   current state; CS_M should read `op pu|hi`, driven, once anything has written the chain),
   and confirm the RX DMA engine is actually running (`_rx_active_buf` ping-ponging,
   `FRAME_COUNT` advancing) — these separate "no rails/no chain/no DMA" from "wrong data."
3. **Only then `dsp4_rxscan.py`** (the S86-proven RX-DMA-region instrument, not `TEST_MEAS`
   or a raw `_buf_C1_IN_nn` peek under `DSP4_BLOCK_KERNELS` — see S86) — and read its
   built-in controls (`FRAME_COUNT` must move, the two `_rx_slot`/`_buf` symbols nothing
   writes must not move) before trusting any per-lane verdict it prints.

Skipping straight to step 3, as S88 initially did, produced two full rounds of "the
instrument must be lying" before the CPLD state was actually checked.

---

## S109 (2026-09-25) — one flash, and the shipping label MOVES

FLASH-OK on attempt 1, `AN_EN` read low by `logic_flash.sh`'s own interlock,
IDCODE `0x020a30dd` before and after, rollback `dsp4_logic.d02d83b3cc22.svf`
staged and md5-checked before the first byte was written.

| # | artifact | design_id | what it was for |
|---|---|---|---|
| 1 | `dsp4_logic.90e24de0dd4a` | `32'h4de0dd4a` | **the CPLD I/O fix — MEMS on pins 119/120/121, `cdc_i` unconditional, `strap_d32`/snake pins removed. Left on the part.** |

**The part carried `dsp4_logic.d02d83b3cc22` (`32'h83b3cc22`) when this session
opened**, confirmed by a `dsp4_logic_id.py --expect 83b3cc22` read-back before
anything was written — the S88 procedure rule, met.

**`logic_flash.sh`'s default rollback is updated to
`dsp4_logic.90e24de0dd4a.svf`** — set from this table, after the flash, which
is the rule the S84 entry spells out and the reason that line has been stale
three times. `d02d83b3cc22` is no longer what the bench lives on.

**The shipping label moves with it.** `90e24de0dd4a` is a SHIPPING build
(`cfg_bits 16'h0010`, no non-shipping switch set, sim gate PASS, STA gate
PASS); it is the shipping bitstream from S109 onwards and `d02d83b3cc22` is
superseded. The post-flash DSP double boot+config was run and the pair reached
`BOOT_STAGE 7 / BOOT_CFG 1` before any reading was taken.
