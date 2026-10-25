provenance: AI-drafted 2026-10-25 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# Contract proposal S173 — the DSP card revision cell

**Status: PROPOSED, not landed.** Nothing here edits `defs/`, a master row, a
generated `matrix.h` or a `_matrix.csv` row. **Cell names are forever**, so the
name below is a proposal and PW rules it (Q1 in the S173 block).

## 1. Why a cell

PW 2026-10-25: *"the app must be compatible with both dsp card revs, and allow
for the differences, esp ram addition to revD."* The app needs to know which
card it is driving before it touches anything that differs (the difference
list: `MW/D24/HW/dspcard-revC-vs-revD.md`). The card carries three straps for
exactly this (DSPC-L11, ruled 2026-10-25): U7 PC1-PC3 = REV_ID0-2, read by H1S1,
rev D = code 1. H1S1 already talks to the host over the MH1 matrix bus, so the
answer belongs in one matrix cell that H1S1 owns.

## 2. The proposed row

`common/cells/mx_master.csv` spelling, in the `Sys` family beside `Sys[1-1]Test`:

| proposed `_Cell` | Seq | Hxf | Save2Mix | MxDatS | Neutral | Notes |
|---|---|---|---|---|---|---|
| `Sys[1-1]DspCardRev[1-1]` | 1 | true | false | 255 | `-` | DSP card hardware revision code, read-only, owned by H1S1. Values 0-7 = the REV_ID2..0 strap code (U7 PC3..PC1, DSPC-L11): **1 = rev D**; 2-7 reserved for later revisions; 0 is never sent by a strapped card. **Rev C sends nothing** (its U7 is an STM32U575 with no straps, PW L11 Q4): the app treats "no reply" as rev C. Writing **0xFF** asks H1S1 to send it again; any other write is ignored. |

Expanded name: **`Sys001DspCardRev001`**.

Why this name: `DspCard` says which board (the D24 has a digital board with its
own future straps — the L11 report §6 item 4 proposes the same scheme there, which
would become `Sys[1-1]DigCardRev[1-1]` on the same pattern), `Rev` says what is
reported, and a single instance needs no suffix beyond the family's `[1-1]`.
Alternatives, if PW prefers: `Sys[1-1]HwRev[1-2]` (one family, instance 1 = DSP
card, 2 = digital board) — shorter, but an instance number is a worse name for a
board than the board's name.

`MxDatS` 255, not 8: the request sentinel 0xFF must be a legal value on the wire.
`Seq` 1 and `Save2Mix` false as `Test[1-1]`: it is hardware identity, never show
state. `Hxf` true: it is a code, not a level.

## 3. Behaviour, exactly (H1S1, rev D image)

- **Boot:** read the straps ONCE, internal pulls off (`dsp_card_rev_read()`,
  `MW/D24/FW/H1S1/revd/dsp_card_rev.h`, compile-checked for Cortex-M0+), set the
  cell's TXD to the code and flag it once for transmit.
- **Request:** a host write of 0xFF re-flags it. The reply (0-7) can never equal
  the request, so H1S1 hearing its own reply on the multi-drop bus cannot
  re-trigger — the S81 CodecPoll free-run cannot happen on this cell.
- **Rev C image:** unchanged, the cell is absent from its table, it never answers.

## 4. What else in defs has to know about rev D (not part of this row)

Flagged here because the landing session will touch the same files:

1. `products/d24/fw.csv` row 2 declares H1S1 as `STM32U575RIT6`. Rev D's U7 is an
   `STM32G0B1RET6` with a different pin-out (DSPC MOD 5). The fw def has no
   notion of a board revision; it needs one, or a second MCU row.
2. `products/d24/fw.csv` rows 5/6 (`RdyDspA` / `RdyDspB`) say "10K pulldown
   R34/R22 so an undriven net rests low". Rev D pulls them **up** (MOD C).
3. The codec select moves off H1S1 on rev D (CS6 → !CS_C, H1S1 PA15 off the net):
   the `Sys001Test001/002` codec path through H1S1 does not exist on rev D.

## 5. What landing it costs

One `mx_master.csv` row and one `d24.csv` declaration in defs (hub), a defs tag,
`./sync-defs.sh` here, and a regenerated `matrix.h` for the rev D H1S1 build
(through the app's pack tool, as the README there requires). Nothing on the DSP
side: the cell has no DSP address.
