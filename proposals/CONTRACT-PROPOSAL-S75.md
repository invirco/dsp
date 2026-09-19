provenance: AI-drafted 2026-09-19 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# Contract proposal S75 — `dsp.extram`, the product's position on the external delay RAM

**Status: PROPOSED, not landed.** Nothing here writes a def, a master row or a
`_matrix.csv` row. The DSP side exists behind `DSP4_EXTRAM` (0 in
`shipping.config`; with it off both shipping images are byte for byte
`10a413005e0647f5c66476f6a0b4ab60` / `e88a7a4302950d088a6c023c949c916e`, which
is S74c's pair unchanged). Evidence: `MW/D24/DSP/s75/extram-pool.md`,
findings S75-1..9.

## 1. The key

| proposed key | file | type | default | meaning |
|---|---|---|---|---|
| `dsp.extram` | `products/<p>/<p>.csv` | integer | `1` (allow) | `0` = this product never uses the external delay RAM. The DSP keeps the L2 backend, does not touch the xSPI bus, and every delay line behaves exactly as it does today. `1` = allow: the DSP probes at boot and uses the RAM **only if a part answers**. |

It is a **product-def key and not a build flag** because one firmware serves
D24 and D32 (decision D8) and because the answer differs per product and per
board revision, not per image. A product whose card is not modified, or whose
cost case never carries the part, says so once in its def rather than needing
an image of its own.

**The default is `1` and that is safe**, because allowing is not using: on
every card that exists today the probe finds nothing and the backend stays L2.
`0` exists for the case where the part IS fitted and the product still must not
use it — a qualification arm, or a product whose delay spec is short enough
that the L2 tiering is not a limitation worth the bus traffic.

## 2. How it reaches the DSP

The host writes it to the existing product-configuration register block, at a
new register:

| register | value | firmware symbol |
|---|---|---|
| `CFG_EXTRAM` = `0xF005` | 0 = allow (default), non-zero = force L2 | `_cfg_extram_off` (`src/product_config.asm`) |

`0xF005` is the next free word after `CFG_COMMIT` (`0xF004`) and below
`CFG_PATCH_BASE` (`0xF010`). It must be written **before** `CFG_COMMIT`:
`main.asm` calls `_pool_init` immediately after the configuration commits, and
that call is the only moment the decision is taken.

Until this key lands, nothing writes the register and it holds its default —
so an image built with `DSP4_EXTRAM=1` on an unmodified card probes, finds
nothing and falls back, which is the intended behaviour with or without the
contract change.

## 3. New diagnostic words

These are **firmware diagnostics, not matrix cells** — they take addresses in
the `0xE0xx` diag space, which is not part of the matrix contract. They are
listed here so the contract record has them in one place.

| address | name | R/W | meaning |
|---|---|---|---|
| `0xE0EC` | `DIAG_BUILD_CFG3` | R | third build-config word. `31..24` = `0xC4` signature, `23..1` reserved zero, bit 0 = `DSP4_EXTRAM`. A read of 0 means the image has no CFG3, i.e. it was built without the pool. |
| `0xE0ED` | `DIAG_EXTRAM_STAT` | R | bit 0 backend (1 EXTRAM), bit 1 device present, `7..4` fail code (0 none, 1 controller init, 2 STIG timeout, 3 ID floated, 4 pattern test, 5 forced off), `31..16` this chip's pool line count. |
| `0xE0EE` | `DIAG_EXTRAM_ID0` | R | raw HyperBus register-space ID word 0. |
| `0xE0EF` | `DIAG_EXTRAM_ID1` | R | raw HyperBus register-space ID word 1. |
| `0xE0F2` | `DIAG_EXTRAM_XFERS` | R | MDMA staging transfers issued, free-running. |
| `0xE0F3` | `DIAG_EXTRAM_STALLS` | R | blocks whose staging was skipped because MDMA0 was still busy. |

**`DIAG_BUILD_CFG3` is a new word and not a widening of `DIAG_BUILD_CFG2`
because `diag.h` says so in as many words**: CFG2's signature is down to six
bits and its bits 23..0 are full, and the note added with `DSP4_TALK_INVERT`
(S72/S74) ends "THE NEXT flag of this kind needs a third word
(`DIAG_BUILD_CFG3`), not a seventh narrowing". `DSP4_EXTRAM` is that next flag.

**A limitation with a date on it:** CFG3 is itself behind `#if DSP4_EXTRAM`
today, because a `.var` in `diag.asm` is a word of DM and a word of DM moves
every address behind it — which would cost this session the proof that the L2
arm rebuilds the shipping pair byte-identical. It becomes unconditional at the
next authorised shipping-image change. Until then `0xE0EC` reading 0 means
exactly one thing: this image has no external-RAM pool.

## 4. What does NOT change

No matrix cell moves, no address moves, no master row changes. The delay cells
(`Chan[1-32]Delay*`, `Aux[1-12]Delay*`, the main and monitor delays) keep their
addresses, their laws and their ranges. What changes, **only on a card with the
RAM fitted and only once `dsp.extram` allows it**, is that the 250 ms the cell
law already promises becomes available on every channel at once instead of on
eight at a time. The contract was always written for the full spec; the tiering
was an implementation limit, and this removes it without touching the contract.
