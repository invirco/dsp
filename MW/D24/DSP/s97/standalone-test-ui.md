provenance: AI-drafted 2026-09-23 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S97 — the test display is its own process, and it never lets go of the screen

PW: *"can the test app be separate from the mixer app, i'd prefer to keep test
app display on continuously during all tests."*

It can, and it now is — but not by handing the display over. **Gate 1's answer is
NO: two processes cannot share or cleanly transfer the DRM display on this
unit**, and that finding is what the architecture is built on rather than
around. The screen stays on because the process drawing it **never stops**, not
because it passes the display to anything.

---

## 1. Gate 1 — the DRM handoff, measured

### 1.1 Only one process may be DRM master, and the incumbent must leave first

`MW/D24/DSP/s97/drm_master_probe.py` opens `/dev/dri/card0` (the vc4 display
card; `card1` is v3d, render-only) and asks to be master while `matrix-app`
holds it. It sets no mode and touches no framebuffer, so it is safe with the app
up:

```
root: masters before open : app/39403
root: opened /dev/dri/card0 as fd 3
root: masters after  open : app/39403          <- the open did NOT grant master
root: SET_MASTER: FAILED errno=16 Device or resource busy
app:  SET_MASTER: FAILED errno=13 Permission denied
```

Two facts, both load-bearing:

- **Even root gets `EBUSY`.** `drm_setmaster_ioctl` refuses while `dev->master`
  is set, whatever your privileges. There is no "take over" and no "share".
- **As `app` it is `EACCES`.** A client that has never been master needs
  `CAP_SYS_ADMIN` to ask at all. The app only ever becomes master because
  opening the card **when it has no master** grants it implicitly — which means
  a would-be successor cannot even sit there pre-opened waiting its turn. It has
  to open *after* the incumbent has gone.

### 1.2 The gap is not black — it is the fbdev buffer, and it is ~24 seconds

`MW/D24/DSP/s97/drm_witness.py` samples the atomic state and the client list at
20 Hz and prints one line per change. Across a plain `stop matrix-app` / wait /
`start matrix-app`:

```
  0.003  scanout: plane-3@pixelvalve-2 fb=721 owner=app      master: app/38969
  2.973  scanout: plane-3@pixelvalve-2 fb=722 owner=[fbcon]  master: none
 27.280  scanout: plane-3@pixelvalve-2 fb=722 owner=[fbcon]  master: app/39403
 27.541  scanout: plane-3@pixelvalve-2 fb=723 owner=app      master: app/39403
```

Within **one frame** of the last DRM fd closing, the kernel's fb helper puts its
own fbdev emulation buffer — `/dev/fb0` — back on the CRTC and leaves it there
until somebody else sets a mode. So:

- the display is **never signal-dark** between two processes; it shows whatever
  `/dev/fb0` last held, which until today was the mixer's boot splash
  (`Program.WriteSplashToFramebuffer` writes it there before Avalonia starts);
- the interruption is **24.6 s** — 2.97 s to 27.54 s — and essentially all of it
  is the replacement process booting, not the handover;
- a *perfect* relay would still flash `/dev/fb0` for at least one frame, because
  the successor cannot open the card until the incumbent has closed it.

**Conclusion: there is no clean two-process handoff on this stack, and no
arrangement of two processes can produce one.** Anything built on "hand the
screen over quickly" is built on a fiction.

### 1.3 What that leaves, and the one thing it does buy

Two consequences, and the second is a genuine gain:

1. **The display must have exactly one owner for the whole factory session.**
   Not a fast handover — no handover.
2. **The gap can be painted.** Since the gap *is* `/dev/fb0`, writing to
   `/dev/fb0` decides what a gap looks like, in advance, for free. `Program`
   now has `WriteCurtainToFramebuffer(title, line2)`: the test display writes
   `FACTORY TEST MODE` there before it takes DRM, and `LEAVING TEST MODE /
   starting the mixer…` before it stands down. The one deliberate transition in
   the design is therefore a legible frame rather than a stale mixer splash.

---

## 2. Gate 2 — the architecture: one binary, two roles, two systemd units

The dispatch asked whether to factor the wizard's rendering out for sharing or
to duplicate the minimum in a small new app. **Neither.** The split that matters
is not between two codebases, it is between two *jobs* — owning the H1S1/MX bus
and owning the display — and those two jobs are already separable inside the
process that does both.

```
matrix-app.service      /home/app/app              the mixer   — owns the bus
d24-testui.service      /home/app/app --testui     the display — owns the screen
                        Conflicts=matrix-app.service
```

**Same executable. Same skin system. Same `TestSkinStore`. Same
`D24TEST.mxs`.** `--testui` does exactly three things:

| | |
|---|---|
| `Boot()` | does **not** open `/dev/serial0`, send `S_RESET`, or start the MX bus reader |
| `AppBootstrap` | does **not** call `Boot.Loop()` — no `S_RUN`, no analog bring-up. `Boot.Init()` still runs, so the power button still works |
| `DrmMainView` | loads `D24TEST` regardless of `settings.csv` |

### 2.1 Why not a second app

The wizard is drawn by `MixerControl`'s five `TEST*` `SubType` branches on top
of the whole skin pipeline — `SkinLoader`, `SkinView`, the `.mxs` package, the
`DrawingContext` text and rectangle primitives, the 20 Hz repaint timer. A
standalone renderer would be a second implementation of all of it, kept in step
by hand, for a page whose entire content already comes from two CSVs. Factoring
it into a shared library is the textbook answer and is the wrong one here for
the same reason: the thing to extract *is* `MixerControl` (3 871 lines) and the
skin system under it, which is a refactor of the product's renderer paid for by
a factory fixture.

There is also a bench cost that is not theoretical: the published binary is
**116 MB** and the unit's rootfs runs at 85 %. A second self-contained .NET
publish would be a second 116 MB binary and a second ~100 MB single-file
extraction cache on a disk that has already been found at 99 % and restart-looped
an app because of it (S95 §6.1).

### 2.2 Why not a flag on one long-running process

The obvious alternative — one process that never releases DRM and simply
switches between "mixing" and "testing" internally — fails on the requirement
that makes this hard in the first place: **a section-B/C test needs the H1S1/MX
bus to itself**, which is why the runner stops `matrix-app` at all (S95 §6.3,
S96 §1). A process that keeps the bus open cannot be the process that stays on
screen. Splitting the two jobs across two units is what lets one of them be
stopped freely.

### 2.3 What the test-display role is NOT allowed to do

Stated because it is the whole safety argument: the test display **never opens
the bus, never sends `S_RUN`, never drives the 595 chain, never touches AN_EN**.
It reads `test-catalog.csv` and `item-status.csv`, draws, and spawns the runner
into its own transient systemd unit exactly as S96 built it. Everything that
touches hardware is the runner's, and the runner's handback rules (§4.5 of the
spec) are unchanged.

---

## 3. matrix-app's role during a test session: it is not running

The dispatch left this as a real design call. **The mixer is stopped for the
whole factory session.** Reasons, in order of weight:

1. **One DRM master, ever.** §1 rules out co-residency on the display. A
   matrix-app that ran without a display would need a rendering path that does
   not exist today, added for no test's benefit.
2. **It has to be stopped for 31 of the 36 automatable rows anyway.** Keeping it
   alive between them buys nothing any test reads.
3. **The wizard does not need the bus, and the runner owns the bus while it
   runs.** At every instant of a session there is exactly one owner of the
   display and at most one owner of the bus.

**The cost, stated:** `AS-CM4` gated on `systemctl is-active matrix-app`, so a
session that stops the mixer would have scored the CM4 **red for running exactly
the software the session asked for**. That is fixed at the criterion rather than
worked around: the test now asks whether **the product application is running in
either role** — `matrix-app` or `d24-testui` — because what it is really
proving is that the CM4 boots and runs the product software. `docs/spec-d24-selftest.md`
and the skin's remedial line for `AS-CM4` say so in the same words.

The second cost is smaller and is recorded rather than hidden: the runner's
handback prints an `MCU verify (whole log)` line harvested from the app log
after it restarts the mixer. With `--no-app-restart` that line reads
`not read — the app was not restarted`. It was evidence, never a verdict.

### 3.1 The runner keeps stopping the mixer, and stops restarting it

`tools/pi/d24_selftest.py --no-app-restart`: the section-B/C leg still issues
`systemctl stop matrix-app` — a no-op when it is already down, and a real safety
belt if somebody started the mixer mid-session — and the hardware handback is
untouched: the SAFE 595 image goes on last, `CS_M` goes back to `ip pu`, `AN_EN`
is reported. **Only the `systemctl start matrix-app` is skipped**, because that
one line would take the DRM display away from the process drawing the wizard.

The transient-unit launch S96 proved (`systemd-run --collect --unit=d24-selftest
--property=User=app`, outside the app's cgroup) is **unchanged and still
required**: the run must outlive `systemctl stop matrix-app`, and it still
issues one.
---

## 4. Live on MW-D24-2 — four runs, and the screen never changed hands

Unit `app@192.168.1.219`, binary `dc558ff11d78ea61480b697106af693e` md5-matched
against the local publish, `d24-testui` up the whole time. Presses went in
through `/dev/uinput` (`d24_touch_inject.py --serve`) exactly as in S94–S96:
**they prove the skin, the store, the queue and the runner, and nothing about
the ILITEK panel or its cable.** That is still PW's finger.

| # | row | tests | section | start → verdict |
|---|---|---|---|---|
| 1 | #56 Panel MEMS mic | `MM1` | C | 12:29:45 → 12:29:58 |
| 2 | #57 Speaker | `SP1` | C | 12:31:13 → 12:31:24 |
| 3 | #105 DSP chip-select CS3 | `DC1-CS3,DC2-CS3` | **B** | 12:32:48 → 12:33:00 |
| 4 | #56 Panel MEMS mic, on the **final** binary | `MM1` | C | 12:39:17 → 12:39:31 |

Every one of them issued `systemctl stop matrix-app`, booted the DSP pair, ran
the inter-chip link gate `OVERALL: CLEAN`, and handed back with
`SAFE image: VERIFIED 200/200`, `CS_M: 27: ip pu`, `AN_EN: 26: … lo` — and then
`matrix-app: left stopped (--no-app-restart); the test display owns the screen`.

### 4.1 The witness

`drm_witness.py` samples the vc4 card's atomic state and client list at 20 Hz
and prints one line per **change** plus a **heartbeat** every 3 s, so "nothing
changed" is positively recorded rather than being indistinguishable from "the
witness died". Two runs under it, saved beside this report:

| file | window | samples | distinct owner/master states |
|---|---|---|---|
| `drm-witness-section-b.txt` | 37.8 s over run 3 | 218 (5 heartbeats) | **1** — `owner=app master=app/40560` throughout |
| `drm-witness-section-c.txt` | 32.1 s over run 4 | 211 (4 heartbeats) | **1** — `owner=app master=app/43001` throughout |

**One state. The whole run. No `[fbcon]` frame, no master change, the same PID
at the start and at the end.** The 200-odd "changes" are the double-buffer flip
(`fb=721 ↔ fb=723`) driven by the wizard's own 20 Hz progress animation — so the
record does not merely show the display present, it shows it **actively
repainting** while the mixer was stopped and the DSPs were being booted
underneath it. 249 and 228 forced repaints logged by the store on runs 1 and 2.

Compare with the same measurement across a plain `matrix-app` stop/start (§1.2):
`[fbcon]` on the CRTC from 2.97 s to 27.54 s. **24.6 s of interruption, in the
middle of a test, is now 0.**

### 4.2 The two deliberate transitions, measured

Entering and leaving test mode DO change hands, and cannot not (§1.1). Both were
witnessed:

| | display owner gone | next master | next frame | gap |
|---|---|---|---|---|
| **EXIT TO MIXER** (`drm-witness-exit-to-mixer.txt`) | 4.502 | 8.076 | 8.337 | **3.8 s** |
| **entering test mode** (`drm-witness-enter-test-mode.txt`) | 6.514 | 10.489 | 10.750 | **4.2 s** |

Both gaps are `/dev/fb0`, and both are legible rather than black. Leaving, the
glass carries the `LEAVING TEST MODE` curtain until `matrix-app` overwrites
`/dev/fb0` with its own splash on the way up (logged at 13:40:10.78). Entering,
it carries the mixer's splash until the test display's frame lands.

**On a unit switched to test mode once, neither transition happens at all**:
`d24-testmode.sh on` disables `matrix-app` and enables `d24-testui`, so the unit
powers up straight into the wizard and the display has one owner from boot to
power-down.

### 4.3 The curtain, read back off the glass

`fb0-curtain.png` is `/dev/fb0` dumped off the unit at 13:33 **while
`d24-testui` held DRM** and converted from RGB565 — i.e. the frame that was
primed and waiting behind the live display:

```
FACTORY TEST MODE
the test display is starting
```

That is what the screen shows if the test display ever stops unexpectedly.
Stated honestly: on **entry** the curtain is written at essentially the same
moment DRM is taken, so it is never actually seen — it is insurance, not a
transition screen. On **exit** it is seen, for the few seconds before the mixer
paints its own splash into the same buffer.

`fb0-mixer-splash-during-handback.png` is the same buffer dumped 6 s into the
EXIT transition and is the M&W splash, not the curtain — because `matrix-app`
had already overwritten `/dev/fb0` on its way up. Kept because it is the direct
evidence for the second half of the handback, and because it is what caught the
ordering: the curtain owns the gap only until the incoming process claims the
buffer for its own.

### 4.4 What the page says — and the first real screenshot

`wizard-as-drawn.png` is the **actual render tree** of the running test display,
1920×1080, via `MX_DRM_CAPTURE_PATH` (a facility that was already in
`App.axaml.cs` and that S94–S96 did not use). **The claim in the spec that this
unit "cannot be screenshotted" was wrong, and is now corrected** — `fbgrab`,
`modetest` and friends are still absent, but the app can render its own view to
a PNG on demand.

It also caught two sentences that S97 had made false, and they are fixed:

| was | is |
|---|---|
| "press START TEST twice. **The display goes away for the run and comes back with the result.**" | "press START TEST twice. The run needs the matrix bus to itself, so **the mixer** is stopped for it; **this display stays up throughout**." |
| "section C **STOPS THIS APP** for the run and restarts it afterwards. The display goes away…" | "section C needs the matrix bus to itself, so **the mixer is STOPPED** for the run. This display is a separate process and **stays up throughout**." |

The first is authored in the generator and lands in `test-catalog.csv` (31 rows
changed — exactly the 31 `stops_app` rows). The second is in the app and is
**role-aware**: run the wizard inside `matrix-app` and it still says the display
will go away, because there it would.
---

## 5. What changed

**mx26**

| file | |
|---|---|
| `src/sw/app/Program.cs` | `--testui` / `MX_TESTUI=1`; `WriteCurtainToFramebuffer`; the framebuffer blit factored out of the splash writer and shared |
| `src/sw/app/Core/AppState.cs` | `TestUiMode` |
| `src/sw/app/Core/Boot.cs` | the test-display role does not open `/dev/serial0`, reset the MCUs, or start the bus reader |
| `src/sw/app/Core/AppBootstrap.cs` | …and does not call `Boot.Loop()` — no `S_RUN`, no analog bring-up. `Boot.Init()` still runs, so the power button still works |
| `src/sw/app/Views/DrmMainView.axaml.cs` | the role forces the `D24TEST` skin |
| `src/sw/app/Core/TestSkinStore.cs` | `WizardSkin` / `MixerUnit`; `HandBackToMixer()`; `RunnerInvocation()` extracted and given `--no-app-restart` in the role; the run notes made role-aware |
| `src/sw/app/Controls/MixerControl.cs` | `EXIT` in the role hands back instead of following its `SkinLink` |
| `src/sw/app.Tests/TestSkinWizardTests.cs` | **+3** — the flag is present in one role and absent in the other, and the two roles' unit names |
| `scripts/cm4-setup-pi.sh` | creates `d24-testui.service` (not enabled) |
| `scripts/d24-testmode.sh` | **new** — `on` / `off` / `status` |
| `tools/d24/build-d24-test-skin.py` | the `stops_app` instruction line and the `AS-CM4` remedial line |
| `tools/d24/preview-d24-test-skin.py` | the same run note, so the preview still matches the page |
| `docs/spec-d24-selftest.md` | `AS-CM4`'s criterion: the product app in **either** role |
| `docs/spec-d24-test-skin.md` | new §0 (the two roles), §6/§7 corrected |

**dsp**

| file | |
|---|---|
| `tools/pi/d24_selftest.py` | `--no-app-restart`; `AS-CM4` accepts either role |
| `MW/D24/DSP/s97/` | this report, the two probes, four witness logs, the catalog as deployed, the render capture, the curtain, the results file as handed back |

Test suite **153/153 green** (150 before this session, +3).

---

## 6. What is not done

- **`needs_bench_host` / `needs_soak_window` / `can_fail` flags** — asked for by
  S95 and S96, still open. Untouched here.
- **No way into test mode from the mixer's own screen.** `d24-testmode.sh on` is
  a shell command. A button on the product skin would need a matrix-less SW
  control in `H_1_24_V2_Ben`, which is a shipped product skin and not this
  session's to edit.
- **`EXIT TO MIXER` is one-way from the screen.** Coming back is the shell
  again. On a factory unit that is the right shape — you switch it to test mode
  once — but a technician who presses EXIT by accident needs a bench host to
  undo it.
- **The panel's own touch controller is still unproven.** Every press here was
  injected through `/dev/uinput`.
- **The curtain is one static frame.** It does not say which row was running or
  how far the session had got. It could.

---

## 7. The unit as handed back

| | |
|---|---|
| role | **`d24-testui` active and enabled at boot; `matrix-app` inactive and disabled** — the unit powers up into the wizard, with one DRM owner from boot to power-down |
| app binary | `dc558ff11d78ea61480b697106af693e`, md5-matched on the unit; rollback at `/home/app/app.bak-s97-pre` (`e009e805…`, the S96 build) |
| skin | `D24TEST.mxs` `bff6c5f768b36a8b996e14bf5f4ac4fa` — **byte-identical to S96**; the regenerated skin diffed clean, only the catalog changed |
| catalog | `test-catalog.csv` `64c57c7a550a0b03ee2a315df8d72a21`, 204 rows; previous kept at `test-catalog.csv.bak-s97-pre` |
| runner | `d24_selftest.py` `2af38d9a7027bcfa5c71e9236c000ecc` |
| mixer's boot skin | back to `H_1_24_V2_Ben` (261 controls, verified loaded). **It lives in the encrypted `settings.mxe`, not `settings.csv`** — editing the CSV alone did nothing, and `app cli settings-set skin …` is what actually changes it. Previous at `settings.mxe.bak-s97-pre` |
| injected touch device | destroyed, `d24-touchinj` stopped, FIFO removed |
| transient units | `d24-selftest`, `d24-touchinj`, `d24-drmwitness` all `--collect`ed; none left behind |
| systemd drop-in | the `MX_DRM_CAPTURE_PATH` override was removed and `daemon-reload`ed; `d24-testui` carries no extra environment |
| AN_EN (GPIO26) | never raised — `lo` throughout, including across four section-B/C DSP boots |
| CS_M (GPIO27) | `ip pu` |
| 595 chain | SAFE image `VERIFIED 200/200` by the runner's own handback after every run |
| CPLD / DSPs | CPLD untouched; the DSP pair booted four times by the runs' own `boot_pair` and handed back each time |
| disk | 84 %, 1.1 GB free (was 85 %, 980 MB) — two superseded app backups and the .NET extraction cache pruned |
| `defs.lock` | unmoved; no generated DSP artifact touched, so no contract note is due |
| results | 5 new rows, all NO DATA and all correctly so; score unchanged at **19 / 204 PASSED · 4 FAIL · 181 not resolved · 17 runnable now · 168 not yet automated** |
