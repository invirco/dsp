provenance: AI-drafted 2026-09-08 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# findings — dsp spoke

Numbered findings D1–D8x are recorded in `review-dsp-20260828.md` and in the
dispatch blocks of `tasks.md`. This file carries findings raised by dispatched
sessions after that review, newest first.

## dsp.csv proposal (2026-09-08)

Session: propose `defs/products/{d24,d32}/dsp.csv` against `defs-v2026.09.08`.
Write-up: `MW/D32/DSP/dsp4-dspcsv-proposal-20260908.md`.

### S1-1 — CLOSED by ruling; four outputs, four strips

PW confirmed the 2026-08-25 main section model mid-session: `Main[1-1]` is the
stereo mix-bus strip and L / R / Ctr / Sub are each a post-crossover OUTPUT
strip. The four chains off `C2_MAIN_XOVER` map to `MainL` / `MainR` /
`MainCtr` / `MainSub` in DAC_13..16 order, `C2_SUB_*` is retired, and the
eight graph nodes that S1 could only report as unnamed now either reach a
strip or say what replaces them. `defs/tools/def_master.py` corroborates the
ruling independently: `MainCtr` is gated on `main.ctr` and the D24-only cell
`Main001Out3Mode001` — an OUT 3 MODE cell — is gated on the same key.

`MainCtr` is emitted for BOTH products at one address; D24 reaches it and D32
lists it out of product scope. That is decision D3's one shared address map
made structural rather than promised: 3,658 cells appear in both proposals
with **zero** address disagreements.

### S1-4 — the meter `taps=` declaration was wrong about what the DSP writes

**Severity: major. Status: fixed.**

A meter node meters ONE tap point and lays `peak` at +0, `rms` at +1, `gr` at
+2 and its own state array at +3. `taps=` therefore names meter WORDS, and
reading it as tap points produced two wrong cells:

- `taps=L;R` on the four mono main-output meters made the RMS word into an
  `R` channel, giving each output strip an `Mtr002` no master defines (two of
  the 23 orphans S1 found). The word keeps its dispatch entry — the host can
  still read it — and loses only the cell.
- `Chan*CompMtr001` (32 cells) was addressed at base+3, which is
  `_mtr_st[0]`, the meter's internal peak-hold state. A cell pointed at
  another variable's scratch is not reaching a DSP address; CompMtr is now
  listed as `unbacked-meter`. This is the read side of recorded defect 4:
  `gate_gr` is declared and never written, `comp_gr` has no word at all.

### S1-5 — `_parse_taps`: `parse_params()` splits on the tap separator

**Severity: major (would have been silent). Status: fixed in the same change.**

The first rewrite of `expand_meter` read the declaration with
`parse_params()`, which splits on `;` — the character that also separates the
taps. `taps=post_trim;post_fader;gate_gr;comp_gr` came back as
`{'taps': 'post_trim'}` and three of the four channel-meter words vanished
without a warning. Caught by the cell counts, not by a test. `_parse_taps()`
reads to the end of the params or the next `key=`.

### S1-6 — the post-crossover output strips have no fader, mute or delay

**Severity: major. Owner: PW / capacity. Status: open (Q1).**

All four output strips define `Level`, `Mute` and `Delay`; chain N in the
graph is EQ + COMP + LIM only. Twelve cells across the four strips reach no
word. Retiring `C2_SUB_*` makes this visible on `MainSub`, which had those
addresses through the sub bus strip; `MainL`, `MainR` and `MainCtr` never had
them. Closing it is four `FADER_PAN` and four `DELAY` nodes on chip 2, which
is the tighter part at 83.16% — a capacity decision, not a desk one.

### S1-7 — `CtrOn` and the retired sub bus cannot both be right

**Severity: major. Owner: PW. Status: open (Q3).**

Every channel defines `CtrOn[1-1]` — on D32 too, which has no `MainCtr` — and
its DSP word is `_rtg_sub_on_<nid>`, a per-channel assign to the `BUS_SUB`
mix bus that feeds the strip the ruling retires. If there is no centre/sub
mix bus, `CtrOn` has no destination; if `CtrOn` is real, that bus is real and
outputs 3 and 4 are not simply crossover taps. The cell keeps its address in
the proposal; one of the two has to give.

### S1-8 — D24's legacy SHARC graph is not a second address map

**Severity: minor (a trap avoided). Status: recorded.**

`MW/D24/DSP/SHARC/dsp.csv` is 201 nodes with no faders, routing, aux, groups,
meters or crossover. Deriving D24's addresses from it would have produced
exactly the second address map D3 forbids. D24's proposal is derived from the
superset DSP4 graph and filtered by D24's own cell set. The legacy file's
three `dsp_validate` parameter errors were fixed in place
(`source_gains` → `source_count`, `wet`/`dry`/`width` → `mix`); both product
files now validate clean.

## defs S1 (2026-09-08)

Session: adopt the `invirco/defs` submodule at `defs-v2026.09.08`, retire the
dsp-side expander and back-fill. Write-up:
`MW/D32/DSP/dsp4-defs-s1-20260908.md`.

### S1-1 — the graph has four main outputs and the product definition has three

**Severity: major. Owner: dsp.csv (the next dispatch). Status: open, now loud.**

This is review finding **D52** and S1 makes it visible instead of resolving it.
`defs-v2026.09.08` models the main section as one L/R bus strip (`Main001`:
fader, mute, DCA, 250 ms delay, 28-band GEQ, cue) plus **three** post-crossover
output strips — `MainL001`, `MainR001`, `MainSub001`, each with its own EQ,
compressor, limiter, delay, fader, mute and meter. `MW/D32/DSP/SHARC/dsp.csv`
builds **four** post-crossover chains off `C2_MAIN_XOVER` (DAC_13..16) plus a
separate sub-bus strip `C2_SUB_*` out to NET_OUT_01.

The consumer-side mapping now says exactly what it can defend and reports the
rest:

- `C2_SUB_*` → `MainSub001`. The master row notes came across verbatim
  ("Subwoofer compressor attack", "Subwoofer output level meter"), so the
  standalone `Sub` category was folded into the main section, not deleted.
- `C2_MAIN_O{EQ,COMP,LIM}_01/02`, `C2_MTR_MAIN_01/02` → `MainL001`, `MainR001`.
- `C2_MAIN_O{EQ,COMP,LIM}_{03,04}`, `C2_MTR_MAIN_{03,04}` → **nothing**. Eight
  graph nodes hold SPI addresses the DSP will answer on and no cell in the
  product definition names them. `gen_dsp.py` lists all eight by id and type.
- `C2_MAIN_COMP` and `C2_MAIN_LIM` (the main BUS dynamics) emit 21 cells the
  masters no longer carry: output dynamics moved onto the per-output strips.
  With `MainL001Mtr002`/`MainR001Mtr002` — the L;R meter taps on what is now a
  mono output strip — that is the 23 cells `validate()` reports as not in
  `_matrix.csv`.
- `MainL001Level001`, `MainL001Mute001`, `MainL001Delay001` and their `MainR`
  and `MainSub` twins are documented and unimplemented: the graph has one main
  delay and one main fader, not one per output strip.

**Why it was not fixed here:** the S1 dispatch bounds the session out of
dsp.csv authoring ("that is the next dispatch: dsp proposes `dsp.csv`, hub
lands it at the gate"). Choosing three chains over four, or giving each output
strip its own fader and delay, is a product decision with a cycle cost, not a
naming fix.

### S1-2 — two families the prune step called aliases are definitions again

**Severity: minor. Owner: hub (defs). Status: open, reported.**

`alias-retire-families.txt` deleted eight families from every expansion up to
`defs-v2026.08.20`, on the reading that they were compatibility aliases.
`defs-v2026.09.08` carries two of them:

| formerly pruned | D32 rows now | alongside |
|---|---:|---|
| `FxDuckThr` | 6 | `FxDuckSens` (6) |
| `PeqGain` | 12 on `MainL`, 12 on `MainR` | `Main001Geq[1-28]` |

Neither reaches a DSP address. They may be intentional (a per-side output PEQ
is a real feature; a duck threshold and a duck sensitivity are not obviously
the same control) or they may be the alias the July prune thought they were.
`defs` is the source of truth either way, so this repo carries them and says
so rather than deleting them again — deleting rows from the expansion and
renumbering `MxAdd` behind them is what made this repo a second source of
truth in the first place. Tracked in `alias-audit.md`.

### S1-3 — the H1S1 dispatch map was missing 2,064 cells and nothing said so

**Severity: major, and closed by this session. Owner: dsp. Status: fixed.**

`mx_dsp_map.h` keys matrix rows to `ghost_cells[]` indices **by cell name**.
Under the old pin the ghost table spelled the current master names
(`Chan001Mute001`) while `_matrix.csv` spelled the pinned ones
(`Chan001RtgMute001`), so those rows silently produced no map entry: the map
held 3,417 entries against 5,481 ghost cells, and `DspDispatch()` could not
reach a routing cell at all. `gen_dsp.py` reported the split as an INFO line
about legacy-spelling hits, which is a true statement that does not read as
"the MCU cannot dispatch to a third of the table".

One spelling closes it: the map now carries **5,393** entries. Nothing in the
DSP image changes (the dispatch tables key on `dsp.csv` node ids, not on cell
names, and all four W0 witnesses rebuild byte for byte), and **H1S1 was not
rebuilt in this session** — the fix is proven in the generated header, not on
an MCU.
