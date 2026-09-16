provenance: AI-drafted 2026-09-16 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# Contract proposal S58 — `products/d24/inputs.csv`: the mic XLR ↔ converter slot ↔ strip declaration that generates the input patch

**Status: PROPOSED, not landed.** Nothing in `defs/` is written by this repo. What S58 DID land is the bug fix the hub
ruled (the hand-typed `D24_INPUT_PATCH` replaced by the netlist order, `tools/pi/dsp4_config.py`), proven on the
part (`findings.md` S58-1..3, data `MW/D24/DSP/s58/`). This proposal moves the fact that patch encodes into defs so
the patch is generated, not typed.

## Contract note (per `release-notes-contract-convention.md`)

- **Contract version proposed against:** `defs-v2026.09.16.2` as pinned (the hub has tagged `.4` since, CaptureArm/
  CaptureReady; this proposal touches neither and rebases trivially)
- **Products affected:** D24 (the declaration); D32/D16/D12 gain the optional file slot, no content
- **Change class:** one new product declaration + one generated host artifact; no cell, no address, no graph change
- **Risk:** low — the generated patch must equal the landed one byte for byte (gate below)

## 1. Why it belongs in defs

"Which XLR is on which converter slot, and which strip it feeds" is a product hardware fact (PW 09-16: *"channels were
assigned for best PCB layout, not ch number mapping"*). Today it lives in three hand-kept places that already
disagreed once: the patch list in `dsp4_config.py` (wrong until S58), the channel table in mx26
`AnalogControlChain.ChannelOrder` (right), and the prose table in mx26 `docs/d24-analog-xlr-map.md`. Every bench tool
S48–S57 hard-coded a fourth copy ("MIC 5 = lane 20"). One declaration, generated consumers.

## 2. The two numbers a row must carry — lane and strip are different things

`dsp.csv`'s `INPUT_TDM` rows name LANES: `C1_IN_16` = `sport_id=1;slot_start=7`. That row is right for D24 and D32
and stays untouched (one graph, `dsp4-architecture-decisions.md`). The console STRIP a lane feeds is chosen by the host
patch. J25 (MIC 5) is lane `C1_IN_16` and strip 5. S58 measured all three patches on the same cable:

| patch | J25 tone on strip | |
|---|---:|---|
| pre-S58 (half-frame) | 20 | the bug |
| identity | 16 | lane = strip: correct lane, wrong console channel |
| S58 netlist order (landed) | **5** | strip = panel channel |

So a row carries both `rx_cell` (the lane, a reference into `dsp.csv`) and `strip` (the console channel).

## 3. The file — `defs/products/d24/inputs.csv`

Proposed copy: `proposals/defs/products/d24/inputs.csv` (written from `tools/pi/d24_inputs.py`).

| column | meaning | checked against |
|---|---|---|
| `panel` | panel legend (`MIC n`) | d24-io.csv once the Lexan extraction lands |
| `xlr` | board refdes of the XLR | d24-hw-inventory.csv (`D24 Analog PCBA rev B`) |
| `preamp_595` | refdes of that channel's 74HC595 | hw inventory |
| `chain_index` | position from the 595 head, U34 = 0 | the app's `ChannelOrder` |
| `send_pos` | byte position on the wire, `24 − chain_index` | derived; the generator asserts it |
| `adc` | AK5558 refdes | hw inventory |
| `sport_id` | converter lane (AD0..AD2) | `dsp.csv` row of `rx_cell` |
| `ain` | AK5558 analog input number | netlist |
| `tdm_slot` | 0-based TDM slot, `ain − 1` | derived; asserted |
| `rx_cell` | the `INPUT_TDM` cell with that (sport, slot) | must exist in `products/d24/dsp.csv` with equal params |
| `strip` | console channel the lane is delivered to | 1..`ch` of d24.csv; unique |

```csv
panel,xlr,preamp_595,chain_index,send_pos,adc,sport_id,ain,tdm_slot,rx_cell,strip
MIC 1,J15,U17,1,23,U15,0,8,7,C1_IN_08,1
MIC 2,J17,U21,3,21,U15,0,6,5,C1_IN_06,2
MIC 3,J19,U25,5,19,U15,0,3,2,C1_IN_03,3
MIC 4,J21,U29,7,17,U15,0,1,0,C1_IN_01,4
MIC 5,J25,U41,9,15,U39,1,8,7,C1_IN_16,5
MIC 6,J27,U45,11,13,U39,1,6,5,C1_IN_14,6
MIC 7,J29,U49,13,11,U39,1,3,2,C1_IN_11,7
MIC 8,J31,U53,15,9,U39,1,1,0,C1_IN_09,8
MIC 9,J35,U62,17,7,U60,2,8,7,C1_IN_24,9
MIC 10,J37,U66,19,5,U60,2,6,5,C1_IN_22,10
MIC 11,J39,U70,21,3,U60,2,3,2,C1_IN_19,11
MIC 12,J41,U74,23,1,U60,2,1,0,C1_IN_17,12
MIC 13,J16,U19,2,22,U15,0,7,6,C1_IN_07,13
MIC 14,J18,U23,4,20,U15,0,5,4,C1_IN_05,14
MIC 15,J20,U27,6,18,U15,0,4,3,C1_IN_04,15
MIC 16,J22,U31,8,16,U15,0,2,1,C1_IN_02,16
MIC 17,J26,U43,10,14,U39,1,7,6,C1_IN_15,17
MIC 18,J28,U47,12,12,U39,1,5,4,C1_IN_13,18
MIC 19,J30,U51,14,10,U39,1,4,3,C1_IN_12,19
MIC 20,J32,U55,16,8,U39,1,2,1,C1_IN_10,20
MIC 21,J36,U64,18,6,U60,2,7,6,C1_IN_23,21
MIC 22,J38,U68,20,4,U60,2,5,4,C1_IN_21,22
MIC 23,J40,U72,22,2,U60,2,4,3,C1_IN_20,23
MIC 24,J42,U76,24,0,U60,2,2,1,C1_IN_18,24
```

## 4. The generator change (dsp repo, after the tag)

1. **`tools/dsp/gen_input_patch.py`** (new, shared by all products): reads `defs/products/<p>/inputs.csv` and
   `products/<p>/dsp.csv`; resolves each `rx_cell` to its packed RX index by the block_io sort (sport, slot) — the same
   order `gen_block_io` emits, so no "8 × AD + slot" assumption survives; emits `MW/<P>/DSP/input_patch.json`
   (`{"contract": ..., "patch": [46 ints], "rows": [...]}`). Rows absent from inputs.csv stay identity. A product
   without inputs.csv gets no file (D32/D16/D12 today = identity, as now).
   **Fails loudly** (no-fallback policy) on: an `rx_cell` not in dsp.csv or not `INPUT_TDM`; its (sport, slot) ≠
   (`sport_id`, `tdm_slot`); `tdm_slot ≠ ain − 1`; `send_pos ≠ 24 − chain_index`; a duplicate strip, rx_cell,
   xlr or chain index; a strip outside the product's `ch`; the result not a permutation over the analog entries.
2. **`regenerate-dsp-contract.sh`** runs it; **`check-contract-drift.sh`** compares the JSON (generated, never edited).
3. **`tools/pi/dsp4_config.py`**: `D24_INPUT_PATCH` is loaded from `input_patch.json` (staged next to the tool on the
   Pi, like `landed-d24.json`); the literal list is deleted. `PRODUCT_CONFIG[p]['input_patch']` is set for every
   product that has the file.
4. **`tools/pi/d24_inputs.py`** reads the rows from the same JSON (XLR, panel, chain, send, ADC, lane) instead of its
   `CONVERTERS`/`PANEL`/`POS_AIN` constants; its public API (`strip()`, `xlr_on()`, `MIC5_STRIP`, `PRE_S58_PATCH`)
   is unchanged, so no bench tool changes again.
5. mx26 (hub's call): `AnalogControlChain.ChannelOrder` generated from the same rows (`chain_index` → `panel`).

**Landing gate:** the generated D24 patch equals today's landed `D24_INPUT_PATCH` exactly (46 entries), and
`d24_inputs.check()` passes on the loaded rows. Then a boot of the running pair reads `_c1_rx_node_entry[1..24]`
equal to the S58 readback (`MW/D24/DSP/s58/data/s58_prove.json` `entry_new`).

## 5. Open points

- U15 (J15–J22) rows follow the same permutation from the netlist; that section has no rails, so they are unmeasured.
- `panel` binds to d24-io.csv only once the top-surface (Lexan) legends are extracted.
