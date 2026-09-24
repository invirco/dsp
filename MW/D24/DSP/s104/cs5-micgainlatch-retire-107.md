# S104 — rename CS5 to MicGainLatch, retire test 107 in favour of MC1/MC2/MC3

Hub dispatch `HUB DISPATCH 2026-09-24 12:17Z`. Step 1 (the `defs` rename) and
step 2 (retiring row 107) are both done and pushed. One piece of step 1 —
advancing *this* repo's own `defs.lock` pin — is blocked on something outside
this dispatch's scope, named below rather than worked around.

## Step 1 — `defs/products/d24/fw.csv`

`defs` was at `404669d` (tag `defs-v2026.09.24`, S101's own CS3/CS4/CS7/CS8
rename) — landed upstream earlier today but never pulled into either spoke's
pin. Checked out `main`, pulled, made the CS5 edit on top, bumped
`defs.toml`, regenerated references, tagged `defs-v2026.09.24.1`, pushed.

Exact `fw.csv` diff:

```diff
-DSP,Dsp5,spare SPI2 select - rev-A leftover with no part fitted on rev C (PW 2026-08-18); a proto wire carries CM4 CS5 (GPIO27) to the CS_M pad on this unit (D8 amendment) so driving it moves mic gain,C13,CS5,...
+DSP,MicGainLatch,CM4 GPIO27 drives !CS_M - the 74HC595 mic-gain chain latch on the analog board; H1S1 releases the pin as input/no-pull and plays no active role (D8 amendment, fitted rev C proto 2026-09-12, permanent rev-D copper). Not a DSP chip-select despite the H1S1 pin C13 / CS5 net legacy naming,C13,CS5,...
```

This supersedes 404669d's own "rev-A leftover / proto wire" framing of the
same row, landed earlier the same day and predating PW's live-review-session
ruling this dispatch carries.

**Byte-neutral confirmation**: `python3 tools/def_reference.py --all` touched
only `defs.toml` (tag string) and the six `gen/matrix/*-reference.md` files;
of those, five products changed only the tag-string line, and D24's changed
the tag string plus its own `fw.csv` sha. `common/cells/mx_master.csv`,
every product master, every matrix expansion — untouched. `git diff --stat`
on the whole commit: 8 files, all the ones named above, nothing else.

Tag `defs-v2026.09.24.1` pushed to `invirco/defs` (`041d4ac`). mx26's
submodule and `CLAUDE.md` pin text (`defs-v2026.09.24` → `defs-v2026.09.24.1`)
both advanced and pushed (`invirco/mx26@024cc17`) — mx26 does not run this
spoke's DSP-matrix regenerate pipeline, so there was nothing else to
reconcile there.

### 🔴 What did NOT move: this repo's own `defs.lock`

Advancing `dsp/defs.lock` from `defs-v2026.09.19.3` to `defs-v2026.09.24.1`
necessarily also consumes every commit in between (a single linear trunk,
per the org mandate — there is no way to cherry-pick just the CS5 rename
onto the old pin). Two of those intervening commits are S101's own
CS3/4/7/8 rename (harmless — already understood, already the precedent this
dispatch mirrors) and `defs-v2026.09.20`'s `Usb[1-1]HostSync[1-1]` +
`Usb[1-1]HostSyncWhy[1-1]` cells (net N67/N68's proposal, `common/cells/mx_master.csv`
end-of-master, 0 addresses moved).

Running `./regenerate-dsp-contract.sh --update-lock`:

- `sync-defs.sh --update-lock` — clean, `defs.lock` updated, D12/D16 expanded,
  D24/D32 staged.
- `validate-matrix-contract.py` — **ERROR: Unexpected D12/D16/D24/D32 matrix
  families detected: UsbHostSync, UsbHostSyncWhy.** Adopting them into
  `matrix-families-allowlist.txt` via `--update-allowlist` (the same
  mechanical, intentional-adoption step S50 used for the Test family) cleared
  that gate —
- `MW/D32/DSP/gen_dsp.py` — **ERROR: cell 'Usb001HostSync001' (Usb/HostSync)
  reaches no DSP address and `_UNMAPPED_REASONS` in `gen_dsp.py` does not say
  why. Give the family a reason, or map it to a graph node.**

That second gate is not a formality: it asks a real design question (does a
DSP node read this, or is it host-managed and needs an explicit reason like
`Bt/Src`'s `hardware-control`?) that this dispatch has no standing to answer.
mx26's own `tasks.md`/`HANDOVER-ADDENDUM.md` still carry it as open —
`Usb[1-1]HostSync[1-1]`/`HostSyncWhy[1-1]` have UNDECLARED units in the wire
table, and "net's defs.lock re-pin is N68's or later." Inventing a mapping or
a reason-string here would be exactly the kind of improvised fix the
dispatch says to stop short of instead.

**Reverted cleanly, nothing half-applied**: `defs.lock`,
`matrix-families-allowlist.txt`, `MW/D12/MX/_matrix.csv`,
`MW/D16/MX/_matrix.csv` restored to their last-committed state; the
`MW/D24/MX/_matrix.expansion.csv` / `MW/D32/MX/_matrix.expansion.csv` staging
files (gen_dsp.py never got to install them) removed; the `defs/` submodule
checked back out at `6fd9159` (the pin `defs.lock` still records). `git
status` on this repo is clean apart from the step-2 files below.

**Needs from the hub**: a ruling on the `Usb[1-1]HostSync` mapping (a graph
node, or an explicit `_UNMAPPED_REASONS` entry with its category) from
whoever owns net N67/N68 — or an explicit instruction to resolve it some
other way. Once that lands, a short follow-up re-runs
`./regenerate-dsp-contract.sh --update-lock` (already proven clean up to
exactly that point) and this bullet closes on its own.

## Step 2 — retire row 107

Unlike CS3/CS4 (S101), whose corrected question needed a new runner (`DY1`)
and so kept their catalog row under a new test, CS5's corrected question is
already fully answered by `MC1`/`MC2`/`MC3` — same wire, CM4 GPIO27 → `!CS_M`,
end to end. Retired outright.

**mx26 `tools/d24/build-d24-connector-status.py`**: `CS_DECL` loses its CS5
tuple. `--export-keys` before/after: 204 → 203 rows. `STAMP` bumped.

**This repo's `tools/pi/d24_selftest.py`**: `DC_SELECTS = (1, 2, 5, 6, 7, 8)`
→ `(1, 2, 6, 7, 8)`; `DC_NO_DATA[5]` removed; `t_dc1`'s docstring and the
`DC_NO_DATA` header comment updated. Removing one catalog row shifts every
subsequent row's position by one — not anticipated in the dispatch text, and
caught by the runner's own `--keys` cross-check (`check_keys()`, S98): every
`# NNN` trailing comment in the `ITEMS` table for an item at or after the old
row 107 needed the same -1. Reconciled against a fresh `--export-keys` pull;
`python3 tools/pi/d24_selftest.py --keys <export>` now reads *"35 distinct
items, all present in the export; 28 row numbers in the table match their
position"* — clean.

**`MW/D24/DSP/accept/item-status.csv`**: the four now-orphaned `DC1-CS5` /
`DC2-CS5` history rows removed. Unlike CS3/CS4, whose catalog row persisted
(so their old evidence rows still match a live key and were left as
history), CS5's catalog row is gone outright — the generator's own rule is
*"unknown key ... is an error, never skipped"*, so those four rows would
have broken every future `--status` run. Confirmed clean: `python3
tools/d24/build-d24-connector-status.py --status
MW/D24/DSP/accept/item-status.csv` → `merged 58 tests over 35 items... rows: 203`.

**mx26 `docs/spec-d24-selftest.md`**: DC1's row (`CS1, CS2, CS5–CS8 (103, 104,
107–110)` → `CS1, CS2, CS6–CS8 (103, 104, 107–109)`) carries an explicit
redirect where CS5 used to sit:

> **CS5 has no row here at all** — old row 107. CS5 → renamed `MicGainLatch`
> in `fw.csv` (PW ruling, 2026-09-24): it is the CM4's drive for the
> mic-gain chain latch `!CS_M`, not a DSP chip-select. Tested as part of
> MC1/MC2/MC3 below, not as its own row — see those

MC1's own row text now names the wire and the old row number. Prerequisite 2
and the S99 GATING table's `DC1 (CS1, CS2, CS5–CS8)` / `DC2 (...)` labels
updated to match. Coverage count corrected: 36 → 35 workbook rows,
`103–110` → `103–109`.

## Row-number renumbering, in full (old → new)

CS6 108→107, CS7 109→108, CS8 110→109, DR1/DR2 111→110, MC1/2/3 112→111,
CC1/2 113→112, Codec AK4619 200→199, SHARC DSP A 195→194, `dig-dsp-a`
140→139, SHARC DSP B 196→195, `dig-dsp-b` 141→140, CPLD 197→196, ADC
199→198, `dig-analog-adc` 142→141, DAC 198→197, `dig-analog-dac` 143→142,
Power MCU 201→200, HD0-1 128→127, TFT display 204→203, `hdmi-pwr` 152→151,
Ethernet 129→128, AS-CM4 194→193, ML1's `S MCU H1S1` 203→202, ML-M 202→201,
ML-P1 126→125 / `dig-panel-a` 144→143, ML-P2 127→126 / `dig-panel-b`
145→144. (ML1's own H1S1 row, 102, and MM1/SP1, 56/57, are before/well after
the shift and are unchanged.) Every one of these was looked up against the
regenerated `--export-keys` output, not computed by hand.

## Acceptance, against the dispatch's own list

- `defs` tagged and pushed — **done** (`defs-v2026.09.24.1`).
- this repo and mx26 both point at the new tag — **mx26 done; this repo
  blocked** (see above).
- `fw.csv`'s `Dsp5` row reads `MicGainLatch` with the note — **done**.
- `docs/spec-d24-selftest.md` row 107 replaced with the redirect note, not
  silently deleted — **done**.
- workbook/catalog generator's row count drops by one and runs clean —
  **done** (204 → 203, verified against this repo's own `item-status.csv`).
- `MC1`/`MC2`/`MC3`'s own text checked and updated — **done** (MC1's row
  text now names the wire and the old row number).

## Unit / bench

Not touched. This dispatch is definitions and catalog bookkeeping only.

## Commits

- `invirco/defs@041d4ac` — the rename, tagged `defs-v2026.09.24.1`.
- `invirco/mx26@78bdcd4` — retire row 107 in the generator and the spec.
- `invirco/mx26@024cc17` — advance `defs.lock`/`CLAUDE.md` pin.
- `invirco/dsp` — this commit (`item-status.csv`, `d24_selftest.py`,
  `tasks.md`, this report).
