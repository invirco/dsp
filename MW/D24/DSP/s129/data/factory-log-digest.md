provenance: AI-drafted 2026-09-27 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# D24 unit 10000000830b03af — factory.log digest for S129

Read-only trawl. Every number below carries `factory.log:<line>` or a JSON path
into one of the two report files. Timestamps are UTC as logged; bench clock is
BST (UTC+1), so e.g. `15:04:11Z` reads 16:04:11 on the bench.

## 0. Run inventory and report mapping (needed before anything else)

`factory.log` has 14 `D24 RUN ALL --` blocks plus an unmarked preamble
(lines 1–214, a crashed `Scope()` init followed by two `--patch-only`
rehearsal passes that pause themselves — not a real run, mentioned only
where it bears on MIC 7 in §1).

| # | lines | start (UTC) | content reached | report written |
|---|---|---|---|---|
| 1–6,8,10 | various, ≤134 lines each | 12:36–14:50Z | auto/self-test only, stopped before or at first `MIC 7` patch prompt | `...T144937Z` (run10, line 2346–2347) and others, no analog data |
| 7 | 1333–1871 | 13:24:52Z | reached network (NW1/NW3/NW4/NW2), stopped before patch loop | — |
| 9 | 2040–2322 | 14:42:35Z | reached NW3 start, stopped before it finished | `...T144937Z` (line 2318–2319) |
| **11** | **2457–2920** | **15:04:11Z** | full network block + MIC 7 loop + MIC 7 gain/terminator + MIC 9, 10, into MIC 11 — **STOPPED** mid-patch | **`10000000830b03af-2026-09-27T151419Z.md`** (confirmed below) |
| **12** | **2921–3528** | **15:30:13Z** | auto + full network block only, stopped before any `MIC 7` patch verdict | **`10000000830b03af-2026-09-27T154323Z`** (log says so at line 3523–3524; files not supplied to this trawl) |
| **13** | **3529–4700** | **15:57:53Z** | full run to completion (network + all analog patches) | **`10000000830b03af-2026-09-27T161356Z.md/.json`** (confirmed below) |
| 14 | 4701–4815 | 16:14:03Z | auto self-test only, `Stopped` exception at line 4761 (SIGNAMES) before any patch | — |

**How runs were matched to the two supplied reports** (the report's own
"pass N" label does **not** track chronological order — it is the tool's
internal retry counter and is not reliable for this):

- Report `10000000830b03af-2026-09-27T151419Z.md` (self-labelled "pass 2",
  607 s wall, "This pass did not finish: it was stopped") — its row 128
  network reading `worst 3.0% loss over 3 passes [1.0, 3.0, 1.0], max RTT
  0.640 ms` is the exact text at `factory.log:2752`, inside run 11
  (15:04:11Z). Arithmetic check: 15:04:11 + 607 s = 15:14:18, and the report
  stamp is `2026-09-27T15:14:19Z`. Confirmed.
- Report `10000000830b03af-2026-09-27T161356Z.md/.json` (self-labelled
  "pass 1", 962.6 s wall) — its row 128 reading `worst 4.0% loss over 3
  passes [3.0, 4.0, 3.0], max RTT 0.647 ms` is the exact text at
  `factory.log:4068`, inside run 13 (15:57:53Z). Arithmetic: 15:57:53 +
  962.6 s = 16:13:56, and the stamp is `2026-09-27T16:13:56Z`. Confirmed.
- Run 12's own log line 3522–3524: `pass 1: 22 PASS / 1 FAIL / 58 NO DATA /
  0 ignored / 0 skipped / 88 not tested (of 202 rows) in 790 s` /
  `report: /home/app/selftest/reports/10000000830b03af-2026-09-27T154323Z.md`
  — this is PW's middle pass; the file itself was not among the three
  supplied to this trawl, so its per-row detail below comes only from
  `factory.log`.

So: **PW pass 1 = run 11 (15:04:11Z) → T151419Z. PW pass 2 = run 12
(15:30:13Z) → T154323Z (log only). PW pass 3 = run 13 (15:57:53Z) →
T161356Z.** Run 14 (16:14:03Z) is a fourth, immediately-aborted attempt
with no data, started right after run 13 finished.

---

## 1. MIC 7

MIC 7 is exercised in three distinct sub-tests, back to back, in both run 11
and run 13. A fourth thing depends on it: MIC 7 is also the **measurement
return path** for several output-jack checks, so when MIC 7 is dead those
outputs report NO DATA too, not because the outputs are bad.

### 1.1 Sub-test A — "the loop": AUX/MAIN busses patched into MIC 7 (XLR)

Donor order and result, both runs identical in outcome (all PASS,
`factory.log:2719-2830` for run 11, `factory.log:4014-4107` for run 13):

| donor (lead K1) | run 11 result | run 11 line | run 13 result | run 13 line |
|---|---|---|---|---|
| AUX 1 (reference) | "the loop is AUX 1 into MIC 7: that input is the reference for the pass" | 2724 | same | 4019 |
| AUX 4 | PASS "the tone arrived on MIC 7 and nowhere else" | 2736 | PASS | 4031 |
| AUX 5 | PASS | 2743 | PASS | 4038 |
| AUX 6 | PASS | 2750 | PASS | 4045 |
| AUX 7 | PASS | 2761 | PASS | 4052 |
| AUX 8 | PASS | 2769 | PASS | 4059 |
| MAIN L | PASS | 2780 | PASS | 4066 |
| MAIN R | PASS | 2818 | 2× "nothing reached MIC 7 -- prompting again" (4071, 4078) then NO DATA "the lane sat -21.8 dB over its own floor" (4103), retried, eventually PASS | 4095 |
| AUX 2 | PASS | 2826 | PASS (reported as P7, line 4095 above) | — |
| AUX 3 | PASS | 2828 | NO DATA once ("P8 NO DATA: no tone reached MIC 7: the lane sat -21.8 dB over its own floor", line 4103) then PASS (4105) | 4105 |

Run 13 needed extra prompts here that run 11 did not; run 11's loop phase
was clean. (Verdict text lags its triggering patch by one full patch cycle
for this sub-test's paired "pre-armed P<n>" / "P<n> PASS" prints — the
donor identity is unambiguous either way since the text itself always names
"MIC 7".)

### 1.2 Sub-test B — mic-pre gain/terminator step, MIC 7

Both runs: patch `AUX 1 to MIC 7` re-labelled "7 checks on this one patch",
loops the pre-amp through gain codes 0 and 63 (no intermediate codes swept
for MIC 7 — see §3, MIC 7 has no adjustable-gain sweep the way MIC 9+ do):

Run 11 (`factory.log:2832-2866`):
```
2837  .. P11: nothing reached MIC 7 -- prompting again      [code 0]
2845  .. P11: nothing reached MIC 7 -- prompting again      [code 0, retry]
2853  .. mic-pre chain MIC 7 at gain code 63: verified       [code 63, forced]
2866  .. P11 NO DATA: no tone reached MIC 7 after 3 attempts [final, printed under next patch]
```
Run 13 (`factory.log:4140-4174`) is byte-for-byte the same pattern and the
same final verdict text: `P11 NO DATA: no tone reached MIC 7 after 3
attempts` (line 4174).

This is the noise/EIN step (150 Ω terminator fitted, `factory.log:2855`
run 11 / `4163` run 13, "Fit the 150 ohm terminator in MIC 7"). **MIC 7
never returns a valid reading here in either run — not even a noise-floor
number** — where MIC 9, 10, 11, 12, 17–24, 8 all cleanly return `P<n> PASS:
the input noise was measured with a 150 ohm source` on the very next line
after their own terminator patch (e.g. MIC 9: `factory.log:2880` run 11,
`4188` run 13; MIC 8: `4452` run 13). So MIC 7's failure is not merely "the
loop tone didn't arrive" — its dedicated dummy-load noise measurement fails
outright, both passes.

### 1.3 Sub-test C — "the line inputs": AUX 2 into the TRS centre of MIC 7

Run 13 only (run 11 was stopped before this section). `factory.log:4568`
patches `AUX 2 to the TRS centre of MIC 7`; verdict (delayed two patches,
see §2 for how that lag was established) is **PASS**: `.. P46 PASS: the
tone arrived on MIC 7 line and nowhere else` (`factory.log:4586`). So the
TRS/jack contact of MIC 7 does pass its own routing check — it is the XLR
sub-test (1.1/1.2) that fails, not the jack contact.

### 1.4 What MIC 7 blocks downstream (output verification)

MIC 7 also serves as the return-path measurement input for four AUX-output
jack checks and three more output rows. All fail as a direct consequence
of MIC 7 not passing tone, all with the identical 3-attempts-then-NO-DATA
pattern, run 13 (`factory.log:4464-4586`):

| catalog row | patch used | result | line(s) |
|---|---|---|---|
| 34 Main Out R | `MAIN R to MIC 7` | NO DATA "the lane sat -21.8 dB over its own floor" | 4103 (shared text w/ row 22) |
| 36 Monitor Out L (TRS) | `MONITOR L to MIC 7` | NO DATA | 4464-4477 area |
| 37 Monitor Out R (TRS) | `MONITOR R to MIC 7` | NO DATA (JSON gives "-13.1 dB over its own floor" — **this exact figure is not found verbatim anywhere in factory.log**, JSON-only: `10000000830b03af-2026-09-27T161356Z.json` → `rows[num=37].measured`) | 4471-4491 |
| 39 Aux Out A 1-2 (TRS, Phone Jack) | `AUX A 1-2 to MIC 7` | NO DATA "the lane sat -24.6 dB over its own floor" after 3 attempts | 4486-4491 |
| 40 Aux Out A 3-4 (TRS, Phone Jack) | `AUX A 3-4 to MIC 7` | NO DATA after 3 attempts | 4507-4519 |
| 41 Aux Out A 5-6 (TRS, Phone Jack) | `AUX A 5-6 to MIC 7` | NO DATA after 3 attempts | 4527-4539 |
| 42 Aux Out A 7-8 (TRS, Phone Jack) | `AUX A 7-8 to MIC 7` | NO DATA after 3 attempts | 4547-4559 |

Source: `10000000830b03af-2026-09-27T161356Z.md` rows 34/36/37/39-42 all
read "no data … no tone reached MIC 7 …" — confirming MIC 7 is a single
point of failure for 7 unrelated catalog rows, not 7 independent faults.

### 1.5 Did MIC 7 ever pass anything?

Yes: the XLR "loop" tone-routing sub-test (§1.1, all 9 non-reference donors
PASS in both runs) and the TRS-centre "line" routing sub-test (§1.3, run 13,
PASS). **No** on the noise/EIN measurement (§1.2, NO DATA both runs, 3
attempts each) and consequently no verdict was ever written to the row 22
catalog cell — the T161356Z report (run 13, the only pass that reached a
final tally) grades row 22 **NO DATA** overall:
`10000000830b03af-2026-09-27T161356Z.json` → row `num=22`: `"verdict":
"NO DATA"`, `"measured": "no tone reached MIC 7: the lane sat -21.8 dB over
its own floor (8 of 18 checks on this item)"`. In the T151419Z pass (run
11, stopped early) row 22 shows **no verdict / "not run in this pass"**
even though the raw log for that same run shows the identical NO DATA
result at line 2866 — the run was killed (right after MIC 11's element-6
check, `factory.log:2919-2920`) before that verdict got persisted to the
report.

### 1.6 MIC 7 vs MIC 6 vs MIC 8 (noise/EIN comparison)

- **MIC 6**: has no test row content at all — `10000000830b03af-2026-09-27T161356Z.json`
  row `num=10`, item `MIC 6`: `"verdict": "NOT TESTED"`, `"reason": "no
  signal path in the patch list reaches this row"`. Not comparable; it is
  simply absent from the patch catalog.
- **MIC 8**: its own XLR "loop" tone check fails (NO DATA, "the lane sat
  -24.6 dB over its own floor", `10000000830b03af-2026-09-27T161356Z.json`
  row `num=23`) but **its 150 Ω terminator/noise step passes cleanly**:
  `.. P36 PASS: the input noise was measured with a 150 ohm source`
  (`factory.log:4452`).
- **MIC 7**: fails both the tone check *and* the noise/terminator step
  (§1.2). It is the only channel in the whole MIC 6–24 range whose
  dedicated EIN/noise-floor measurement never returns a reading.

### 1.7 send_pos / lane / gain_code / route

None of `send_pos`, `lane` (as a numeric field), or `route` appear
anywhere in `factory.log` or either JSON as structured fields — grepped for
literal field names, zero hits. `gain_code` as a *word* does appear: MIC 7
is held at gain code 0 throughout its own patch section and is forced to
code 63 once, for the terminator/EIN attempt (`factory.log:2853` run 11,
`4161` run 13: `.. mic-pre chain MIC 7 at gain code 63: verified`) — MIC 7
has **no intermediate gain-code sweep** at all (contrast MIC 9+ in §3,
which step through 0,1,2,4,8,16,32,63). "Lane" appears only inside prose
reason strings ("the lane sat -21.8 dB over its own floor") describing an
internal measurement-channel floor, not a numbered field tied to MIC 7
specifically — the same phrase recurs, generically, for MIC 8, Main Out R,
Monitor Out L/R (§1.4). Treat `send_pos`/`lane`/`gain_code`/`route` as
**absent** as structured data; only the gain-code-0/63 prose value exists.

---

## 2. Jack polarity

All the numeric evidence is in the run-13 "line inputs" section
(`factory.log:4568-4665`), patch `AUX 2 to the TRS centre of MIC <n>`, lead
K4. **No numeric phase-in-degrees value is ever printed for these
jack/TRS checks** — the verdict is categorical text only. This contrasts
with the XLR "balanced reference" checks, which do carry an exact phase
figure, from the JSON.

### 2.1 Attribution method (why the mapping below, not the immediately-preceding patch header)

Verdicts for the TRS-centre gain/routing check are delayed **two** patch
instructions, exactly as in §1.1 — confirmed independently: the pre-armed
number for the `MIC 7` TRS patch is `P46` (`factory.log:4571`), and its
PASS text appears two patches later, under the `TRS centre of MIC 10`
header (`factory.log:4586`, `P46 PASS: the tone arrived on MIC 7 line and
nowhere else`). The same lag is what lets `P50`, pre-armed under `TRS
centre of MIC 12` (`factory.log` — see table), surface under the `TRS
centre of MIC 18` header. Mapping below is by P-number, not by the header
each line sits under.

### 2.2 Jack/TRS results (run 13 — the only run that reaches this section)

| socket (TRS centre) | P# | verdict text | printed at line | pre-armed at line |
|---|---|---|---|---|
| MIC 7 | P46 | PASS "the tone arrived on MIC 7 line and nowhere else" | 4586 | 4572 |
| MIC 9 | P47 | PASS "the tone arrived on MIC 9 line and nowhere else" | 4593 | 4580 |
| MIC 10 | P48 | PASS "the tone arrived on MIC 10 line and nowhere else" | 4600 | 4587 |
| MIC 11 | P49 | PASS "the tone arrived on MIC 11 line and nowhere else" | 4607 | 4594 |
| **MIC 12** | **P50** | **FAIL "this channel came back inverted, which on a stereo jack is tip and ring swapped"** | 4614 | 4601 |
| **MIC 17** | **P51** | **FAIL, same inverted text** | 4622 | 4608 |
| **MIC 18** | **P52** | **FAIL, same inverted text** | 4636 | 4615 |
| **MIC 19** | **P53** | **FAIL, same inverted text** | 4644 | 4608→ retried at 4629 (first attempt at 4608 mis-hit: "P53: the tone came back on MIC 18, not MIC 19 line -- prompting again", line 4623) |
| **MIC 20** | **P54** | **FAIL, same inverted text** | 4652 | 4637 |
| **MIC 21** | **P55** | **FAIL, same inverted text** | 4660 | 4645 |
| **MIC 22** | **P56** | **FAIL, same inverted text** | 4667 | 4653 |
| MIC 23 | P57 | *(verdict never printed — only the pre-arm exists before the section ends)* | absent | 4661 |
| MIC 24 | P58 | "nothing reached MIC 24 line -- prompting again" ×2 (lines 4668, 4674), then final **NO DATA "no tone reached MIC 24 line after 3 attempts"** | 4687 | (consumed across the 3 retries) |
| MIC 8 | P59 | *(verdict never printed — run ends right after P58's NO DATA)* | absent | 4685 |

(All line numbers read directly off `factory.log:4560-4700`. FAIL text is
identical every time it occurs: `.. P<n> FAIL: this channel came back
inverted, which on a stereo jack is tip and ring swapped` at lines 4614,
4622, 4636, 4644, 4652, 4660, 4667.)

**MIC 12, MIC 17 and MIC 18 (the three the debug session asked about by
name) are all in the FAIL/inverted set.** So is MIC 19, 20, 21, 22 — **seven
consecutive jack sockets, MIC 12 through MIC 22, all report tip/ring
inversion, without exception**, wherever the check actually completed. Only
MIC 7, 9, 10, 11 (the low end of the range, checked first) pass clean. MIC
23's and MIC 8's own jack verdicts are never printed before the analog
section ends (`factory.log:4682-4684`, `pass 1: 59 PASS / 6 FAIL / 48 NO
DATA …`) — genuinely absent from the source, not inferred.

**No numeric phase reading accompanies any jack/TRS FAIL or PASS line** —
`grep -n "deg" factory.log` restricted to run 13 returns nothing relevant
(only an unrelated SPI clock-rate line, `factory.log:3663`). Level is
likewise not printed for these checks; only the re-read "window spread"
figures exist (see §2.1 pre-arm lines, e.g. `factory.log:4573`
"window spread 1.23 dB" — a connector-settling metric, not a level
reading).

### 2.3 XLR phase distribution, for comparison

From `10000000830b03af-2026-09-27T161356Z.json`, the "balanced reference"
checks (AUX 1 loop, XLR side) — every one of these passed and every one
clusters tightly around **-145.2° to -145.3°**, i.e. none show the
jack-side inversion:

| item | JSON row | level | phase | THD+N |
|---|---|---|---|---|
| MIC 11 | num=13 | 5.55 dB | -145.3° | -78.50 dB = 0.012% |
| MIC 12 | num=14 | 5.55 dB | -145.3° | -78.03 dB = 0.013% |
| MIC 17 | num=15 | 5.57 dB | -145.2° | -78.72 dB = 0.012% |
| MIC 18 | num=16 | 5.57 dB | -145.2° | -78.74 dB = 0.012% |
| MIC 19 | num=17 | 5.57 dB | -145.3° | -78.62 dB = 0.012% |
| MIC 20 | num=24 | 5.58 dB | -145.3° | -78.20 dB = 0.012% |
| MIC 21 | num=18 | 5.55 dB | -145.2° | -78.49 dB = 0.012% |
| MIC 22 | num=19 | 5.55 dB | -145.2° | -78.55 dB = 0.012% |
| MIC 23 | num=20 | 5.54 dB | -145.3° | -78.57 dB = 0.012% |
| MIC 24 | num=21 | 5.55 dB | -145.3° | -78.65 dB = 0.012% |

(Source text, verbatim, e.g. MIC 18: `"this reading is now MIC 18's
balanced reference: 5.57 dB, -145.2 deg; THD+N -78.74 dB = 0.012 %"`.)

**Conclusion**: every XLR (mic) input on these same physical sockets reads
a consistent ~-145.2/-145.3° phase and passes; every jack/TRS (line)
contact on MIC 12 through MIC 22 reads back inverted (categorically, no
degree number given) — the fault tracks the TRS contact, not the channel,
and is present on every jack row that completed the check, without a
single passing exception in that band.

---

## 3. Line inputs

"The line inputs" is literally the section header at `factory.log:4585`
(run 13) / would be reached in run 11 but the run stopped first — covering
MIC 7, 9, 10, 11, 12, 17–24, 8 via `AUX 2 to the TRS centre of MIC <n>`
(§2 table). Socket named in the operator instruction is always `the TRS
centre of MIC <n>` (lead K4).

**`level_dbfs`, explicit drive/expected/tolerance numbers, `since_drive_s`
and `settle_windows` are absent from both factory.log and the JSON for
this specific check** — greped for literally, zero hits in either report
JSON or the log. The TRS-centre check only ever returns: PASS ("tone
arrived … line and nowhere else"), FAIL ("inverted … tip and ring
swapped"), or NO DATA ("nothing reached … line"). No dB figures accompany
any of these three outcomes.

The only numeric level data that exists anywhere near "MIC 7-11 as line
patches" is from the **separate** mic-pre gain-accuracy check (§4, a
different sub-test, on the XLR side, not the TRS/jack side) — from
`10000000830b03af-2026-09-27T161356Z.json`:

- MIC 9: `"gain element 1: measured +16.24 dB, expected +12.85 dB
  (measured), drive -42.8 dBFS, lane -24.06 dBFS (the meter, which is not
  what this is judged on, read -16.73)"` (row `num=11`).
- MIC 10: `"gain element 3: measured +31.15 dB, expected +26.89 dB
  (measured), drive -56.9 dBFS, lane -23.20 dBFS (the meter, which is not
  what this is judged on, read -12.99)"` (row `num=12`).

These are drive levels for the **AUX-1-loop/gain-sweep** test, not the
TRS-centre "line" test — they should not be read as evidence about the
jack contact. **There is no headroom figure anywhere in the source
comparing a correct jack/line reading to the same signal on XLR** — the
line test carries no level number at all (previous paragraph), so this
specific comparison cannot be made from what's logged; call it absent
rather than estimate it.

---

## 4. Gain steps

Sweep codes are always 0, 1, 2, 4, 8, 16, 32, 63 (8 codes; the patch header
text says "7 checks on this one patch", which does not match the 8-code
sweep count — quoted as-is, not reconciled). Only **element 6** (code 32)
is echoed to `factory.log` as an explicit `P<n> PASS/FAIL: gain element 6
adds X dB, Y dB from expected` line; the other 7 codes print only
`.. mic-pre chain gain step, MIC <n> at code <c>: verified`, which is *not*
a pass/fail grade — it just means a reading was taken. Any fail on a
non-element-6 code is therefore only visible in the JSON rollup, not in
plain factory.log text (demonstrated directly below for MIC 9/MIC 10).

Verdict-under-header lag for this sub-test is **one** patch cycle (unlike
the two-patch lag in §1/§2) — confirmed directly: `factory.log:4184-4196`
shows `Fit the 150 ohm terminator in MIC 9` produces no verdict in its own
block, and the very next patch (`AUX 1 to MIC 10`) opens with `P13 FAIL:
MIC 9 gain step 6 is wrong…` — one cycle, not two. Terminator/noise checks
(the `P<n> PASS: the input noise was measured…` lines) are lag-**zero** —
each appears inside its own `Fit terminator` block.

### 4.1 Run 11 (15:04:11Z, T151419Z, stopped mid-sweep)

| socket | P# | element-6 result | line |
|---|---|---|---|
| MIC 9 | P13 | PASS "gain element 6 adds 48.5 dB, 0.5 dB from expected" | 2864 (printed under MIC 10's own patch header) |
| MIC 10 | P15 | PASS "gain element 6 adds 48.5 dB, 0.5 dB from expected" | 2919 (printed under MIC 11's own patch header, immediately before `STOPPED`) |
| MIC 11 | — | run stopped before its own element-6 verdict could print (needed one more patch cycle) | `factory.log:2920-2921` `STOPPED` |

No per-code (non-element-6) FAILs are visible for run 11 — and none could
be checked against a JSON, because the T151419Z report marks MIC 9–12,
17-24, 7, 8, 20 as **"no verdict … not run in this pass"** (report table,
rows 11-24) despite the raw log showing these two clean element-6 passes;
the run was killed before the catalog rows were finalized.

### 4.2 Run 13 (15:57:53Z, T161356Z, completed)

| socket | P# | element-6 (code 32) result, as printed in factory.log | line | other-code fail, JSON only |
|---|---|---|---|---|
| **MIC 9** | P13 | **FAIL "MIC 9 gain step 6 is wrong: it adds 54.9 dB and should add 48.0 dB"** | 4196 | JSON says the *graded* fail is actually **element 1**: measured +16.24 dB vs expected +12.85 dB, "(6 of 8 checks on this item)" — `...T161356Z.json` row `num=11` |
| **MIC 10** | P15 | PASS "gain element 6 adds 49.4 dB, 1.4 dB from expected" | 4218 | JSON: separately **FAILS element 3**: measured +31.15 dB vs expected +26.89 dB, "(1 of 8 checks on this item)" — row `num=12`. This fail is **not present anywhere as literal text in factory.log** — confirmed absent by direct grep for "31.15"/"26.89". |
| MIC 11 | P17 | PASS "…48.1 dB, 0.1 dB from expected" | 4240 | JSON row `num=13`: PASS, 8/8 |
| MIC 12 | P19 | PASS "…48.2 dB, 0.2 dB from expected" | 4262 | JSON row `num=14`: PASS, 8/8 |
| MIC 17 | P21 | PASS "…48.3 dB, 0.3 dB from expected" | 4284 | PASS, 8/8 |
| MIC 18 | P23 | PASS "…48.2 dB, 0.2 dB from expected" | 4306 | PASS, 8/8 |
| MIC 19 | P25 | PASS "…48.2 dB, 0.2 dB from expected" | 4328 | PASS, 8/8 |
| MIC 20 | P27 | PASS "…48.2 dB, 0.2 dB from expected" | 4350 | PASS, 8/8 |
| MIC 21 | P29 | PASS "…48.3 dB, 0.2 dB from expected" | 4372 | PASS, 8/8 |
| MIC 22 | P31 | PASS "…48.2 dB, 0.2 dB from expected" | 4394 | PASS, 8/8 |
| MIC 23 | P33 | PASS "…48.3 dB, 0.2 dB from expected" | 4416 | PASS, 8/8 |
| MIC 24 | P35 | PASS "…48.3 dB, 0.2 dB from expected" | 4438 | PASS, 8/8 |
| MIC 8 | P37 | PASS "…48.2 dB, 0.1 dB from expected" | 4458 | (MIC 8's own tone-routing row is NO DATA — §1.6 — but its gain-element-6 accuracy check still runs and passes) |

**Drift between run 11 and run 13**: MIC 9 element 6 measured **48.5 dB
(+0.5)** in run 11 vs **54.9 dB (+6.9, FAIL)** in run 13 — a swing of
roughly 6.4 dB on the same element between the two passes, ~53 minutes
apart. MIC 10 element 6 measured 48.5 dB (+0.5) in run 11 vs 49.4 dB (+1.4)
in run 13 — smaller drift, still passing both times, but MIC 10 picked up
a *different*, element-3 fail in run 13 that wasn't graded/visible at all
in run 11 (run 11 never reached MIC 10's other codes' final grading before
being stopped).

`since_drive_s` / `settle_windows` fields: **absent**, grepped for
literally in both the JSON and factory.log, zero hits in either run.

---

## 5. Network

Bench host target: **192.168.1.211** (all runs, all NW3 lines). Gateway
target: **192.168.1.254** — this only appears in the JSON (`...T161356Z.json`
row `num=128`, `"measured"` field), never in factory.log itself, because
every NW3 line in factory.log is hard-truncated at 126 characters, always
cut off right at `gatew` (e.g. `factory.log:2752`, `:3476`, `:4068`,
`:1828` — confirmed by `awk '{print length}'`, all exactly 126 chars).
Interface name (e.g. `eth0`): **absent**, not printed anywhere; NW1 only
reports `Link detected: yes, Speed: 1000Mb/s, Duplex: Full, carrier=1`
(identical text at lines 1824, 2297, 2708, 3395, 4003 — every run that
reaches NW1 gets the same link state).

| run (start UTC) | NW1 | NW3 (loss / RTT, bench host) | NW4 | NW2 (rx_dropped etc.) | row 128 verdict |
|---|---|---|---|---|---|
| 7 (13:24:52Z) | PASS, line 1824 | FAIL "worst 6.0% loss over 3 passes [3.0, 6.0, 4.0], max RTT 0.632 ms" — line 1828 | NO DATA "unit rx 5722 Mbit/s, unit tx 9444 Mbit/s…" — line 1832 | FAIL `{'rx_errors': 0, 'rx_dropped': 1, 'rx_missed': 0, 'tx_errors': 0, 'tx_dropp…}` (truncated at 126 chars) — line 1836 | (run stopped before final report table) |
| 9 (14:42:35Z) | PASS, line 2297 | started, never completed — run stopped, line 2318-2322 | — | — | — |
| **11 (15:04:11Z)** | PASS, line 2708 | **FAIL "worst 3.0% loss over 3 passes [1.0, 3.0, 1.0], max RTT 0.640 ms"** — line 2752 | NO DATA "…unit rx 8689…" — line 2771 | **FAIL `rx_dropped: 1`** — line 2783 | FAIL, `T151419Z.md` row 128 |
| **12 (15:30:13Z)** | PASS, line 3395 | FAIL "worst 4.0% loss over 3 passes [3.0, 4.0, 4.0], max RTT 1.202 ms" — line 3476 | NO DATA "…unit rx 1314…" — line 3486 | **PASS `rx_dropped: 0`** — line 3490 | (log-only; `T154323Z` not supplied) |
| **13 (15:57:53Z)** | PASS, line 4003 | **FAIL "worst 4.0% loss over 3 passes [3.0, 4.0, 3.0], max RTT 0.647 ms; gateway 192.168.1.254: worst 4.0% loss over 3 passes [3.0, 4.0, 3.0], max RTT 6.788 ms"** (gateway clause from JSON only) — line 4068 | NO DATA "…unit rx 8879…" — line 4080 | **FAIL `rx_dropped: 2`** — line 4115 | **FAIL, `T161356Z.json` row `num=128`, `"source": "NW3"`, `"tests": ["NW1","NW2","NW3","NW4"]`** |

**Specifically asked for — NW2 rx_dropped and NW3 loss in the 16:13Z
(run 13) pass**: `rx_dropped: 2` (`factory.log:4115`, the highest of the
three completed runs — run 11 had 1, run 12 had 0), and NW3 worst loss
4.0% over passes `[3.0, 4.0, 3.0]` against the bench host, with a max RTT
of 0.647 ms to the bench host and 6.788 ms to the gateway
(`10000000830b03af-2026-09-27T161356Z.json`, row `num=128`, `"measured"`).

Every run that reaches NW3 fails it (0% loss / <5 ms RTT is the limit —
`.md` row 128 `limit` column — and every measured pass shows 3-6% loss,
comfortably inside the RTT limit but never at 0% loss). NW1 (link) always
passes; NW4 is always NO DATA by design ("this ran from the unit to
itself, so nothing was measured about its network socket") in every run
that reaches it. NW2 is the only one of the four that varies pass/fail
run to run (FAIL/PASS/FAIL across runs 11/12/13) and tracks its own
`rx_dropped` counter directly (0 → PASS, ≥1 → FAIL), consistent across all
three completed instances of the test in this log.
