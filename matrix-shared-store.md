# Dropbox `_Matrix` — cross-repo shared data store

Status: adopted 2026-08-06
Authority: **mx26** (hub). Absorbed from mx26 commit `fbaf2be`
("docs: document _Matrix cross-repo store and D24 hw schematic/pdsprj
population", 2026-08-06) — `sot.md` concept 16, `docs/decision-mx26-mandates.md`
§"cross-repo shared data store", `matrix_direction.md`.
Purpose: tell this repo (a spoke) how to read from, and what may be added to,
the shared Dropbox store — without redefining anything mx26 owns.

## What it is

`_Matrix` is the canonical Dropbox folder for essential data shared across
**all** matrix repos (mx26 hub + spokes: net, dsp, fw, logic, hw). mx26
controls it and defines its structure; **spokes consume it, they do not own or
redefine the layout.** Nothing under `_Matrix` is required to build mx26 or
this repo — repos link to it by path.

Root (as documented by mx26): `~/Dropbox-Stonepower/Peter Watts/_Matrix`.
On this machine the Dropbox folder is named differently:

```
~/Stonepower Dropbox/Peter Watts/_Matrix
```

Resolve it the way `sync-from-mx26.sh` and the mx26 launch scripts already do —
probe `$HOME/Dropbox-Stonepower/Peter Watts`, `$HOME/Stonepower Dropbox/Peter
Watts`, `$HOME/Dropbox/Peter Watts` — never hard-code one spelling in tooling.

## Layout (mx26-defined)

```
_Matrix/
    readme.md                  # store-level intent (authored by mx26)
    Products/<Product>/        # one folder per product (D24, D32, ...)
        readme.md              # per-product intent
        dsp/    fw/    hw/     # same canonical domain subfolders as mx26 src/
        logic/  net/   pd/
        sw/     sys/
```

Per-domain intent for a product folder (from `Products/D24/readme.md`):

| Domain | Holds |
|---|---|
| `dsp/` | tuning captures, coefficient sets, validation vectors |
| `fw/` | vendor SDKs, flash images, MCU build artifacts |
| `hw/` | gerbers/fab outputs, schematics, datasheets, CAD exports |
| `logic/` | bitstreams, IP, sim outputs |
| `net/` | protocol captures, certification material |
| `pd/` | product-definition *reference* material (authored CSV defs stay in mx26 `src/pd/`) |
| `sw/` | built MXU packages, skins, installers |
| `sys/` | large system diagrams/exports too big for any repo |

## Rules (binding, from mx26)

- **mx26 owns the structure.** This repo consumes; it does not add new
  top-level folders, rename domains, or invent per-product variations.
- **D24 is the reference template.** New products copy D24's subfolder set as
  their starting point — nothing more, until a domain proves it needs extras.
- **Essential and durable only.** Same mandate as mx26's "essential code and
  durable docs" — not a dump for every legacy file.
- **No bulk migration.** Legacy per-product folder systems (the old ad-hoc
  `_mx/MW/D24` layout, `FW - Copy`, `old DSP`, and similar) are not copied in
  wholesale; classify each item keep-now / migrate-later / archive first.
- **Nothing there is a build input.** Builds must not depend on Dropbox being
  present or synced.

## What this means for mx-dsp

- **The contract flow is unchanged.** `defs.lock` + `sync-from-mx26.sh` still
  read the mx26 checkout (`$MX26_REPO`, `~/mx26`, or the Dropbox `mx26/`
  mirror). `_Matrix` is *not* wired into the contract path today; mx26's
  `matrix_direction.md` names it as the eventual concrete home for the
  "Dropbox mirror" a spoke pins from, but that has not happened yet. Do not
  point sync tooling at `_Matrix` until mx26 says so.
- **Derived, versioned artifacts stay in git here** — `dsp.csv`, node ASM,
  `dsp_address_map.md`, `ghost_cells.h`, hardware maps, decision docs. The
  store is for the bulky/binary source material behind them.
- **Large binaries this repo references belong in the store, not in git** —
  board manufacturing outputs, CAD projects, vendor SDKs, flash images,
  bitstreams. Reference them by path from in-repo docs.
- **`Products/<P>/dsp/` is this repo's slot** in the store (tuning captures,
  coefficient sets, validation vectors). It is currently empty; populating it
  is a keep-now/migrate-later decision per item, not an automatic dump.

## Current contents (verified 2026-08-06)

- `Products/D24/hw/` — **9 board folders**, the complete D24 PCBA set: Analog
  rev B, Digital rev C, DSP (MW DSP4 rev C), Left Switch rev B, Right Switch
  rev B, Phone Jack rev B, Mini Jack rev B, HDMI FPC rev B, P1 rev B. Each
  carries BOM, top/bottom/front renders, CADCAM gerber zip, base design file,
  schematic PDF, and the DipTrace `.pdsprj` source project (DipTrace combines
  schematic + PCB layout in one file — there is no schematic-only format in
  this project, per the mx26 changelog entry).
- All other D24 domains (`dsp/ fw/ logic/ net/ pd/ sw/ sys/`) exist but are
  empty. `Products/` currently holds D24 only.
- ~110 MB total, fully downloaded locally (no online-only placeholders).
- The three schematic PDFs mirrored in `MW/D24/HW/schematics/` (`D24 DSP.pdf`,
  `D24 Digital.pdf`, `D24 Analog.pdf`) are byte-identical to the store copies,
  so `MW/D24/HW/hardware-map.md` derivations remain valid.

## Not to be confused with

| Location | Owner | Contents |
|---|---|---|
| Dropbox `_Matrix/` | mx26, **cross-repo** | shared essential per-product data (this doc) |
| Dropbox `mx26/` | mx26, **mx26-only** | that repo's own out-of-git binaries, team/candidate material (mx26 `sot.md` concept 10) |
| Dropbox `_mx/<Brand>/<Product>/` | sw app runtime | generated `_matrix.csv`, settings, product data the control app loads |
| Dropbox `_skins-shared/` | sw app runtime | skins (config, follows the MXU path) |
| Dropbox `TransferOnly/` | ad-hoc | transfer scratch: `PCB mods/`, `D24 schematics/`, `Ideas/` — **not** canonical |

## Open items

- PCB mod lists still live in `TransferOnly/PCB mods/` (`dsp4-revD-modlist.md`,
  `d24 digital mods.*`) under the 2026-08-05 cross-repo convention. `hw/` in
  the shared store is now the better home; migrating them is mx26's/PW's
  keep-now/migrate-later call, so nothing has been moved. Referenced from
  `MW/D24/HW/hardware-map.md` and `tasks.md`.
- `Products/D32/` does not exist yet. When the D32 flagship needs shared
  binaries, create it by copying D24's subfolder set — no new layout.
