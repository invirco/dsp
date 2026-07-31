# shared/dsp4-logic — DSP4 LOGIC CPLD + single-sourced TDM slot map

Card-level, product-agnostic tree for the DSP4 LOGIC CPLD (Intel MAX V
5M1270ZT144C4N, U3) per decision D2 in
[dsp4-architecture-decisions.md](../../dsp4-architecture-decisions.md).
Serves both D24 and D32; nothing in here may fork per product (product
differences are expressed via the `scope` column).

## The slot map is defined ONCE, here

| File | Role |
|---|---|
| `tdm-lines.csv` | Physical TDM line inventory: DSP DAI port(s), external net, DSP-facing format, slot count, clock pair, scope, status |
| `slot-map.csv` | Per-slot signal assignments (`line_id`, `slot`, `signal`, `scope`, `note`) |
| `gen_slot_map.py` | Generator + validator. Run: `python3 gen_slot_map.py` |
| `generated/sport_map.json` | SPORT config for `tools/dsp/gen_dsp_csv.py` (firmware consumer) |
| `generated/dsp4_slot_map.vh` | Verilog constants/LUT for the CPLD HDL (hardware consumer) |

Rules (same as the rest of the repo):

- **Never hand-edit `generated/`** — change the CSVs and re-run
  `gen_slot_map.py`. Both outputs are stamped with the SHA-256 of the two
  source CSVs.
- A slot-map or CPLD change is behaviourally a **contract bump**: record the
  `source_hash` (and, once HDL exists, the bitstream hash) per
  `release-notes-contract-convention.md`.
- This table migrates into the mx_master.csv SOT when that lands
  (see `ideas.md` milestones); the schema here is shaped for that move
  (scope column = ProductScope).

## Conventions encoded

- **SPORT convention:** `sport_id` = DAI port index; `I` ports are RX, `O`
  ports are TX; chip 1 = DSPA (input engine), chip 2 = DSPB (output engine).
- **Mix fabric:** MIX_0..MIX_7 are the inter-chip lines (DSPA O`n` → DSPB
  I`n`), TDM16 each → 128 global mix slots (`16*line + slot`). The 25 D32
  logical buses occupy global slots 0–24 in the SAME order as the legacy
  single-SPORT model (`sport_id=7` slot n → line n/16, slot n%16), so
  existing bus numbering survives the fabric rework. Slots 25–127 and lines
  MIX_2..MIX_7 are reserved for 128-bus growth.
- **Formats are DSP-facing:** LOGIC re-frames odd sources (Pi I2S → TDM8
  slots 0–1 on A_I6; ADAU7302 MEMS strap = TDM8 slot 5 on A_I7) so each DSP
  sees uniform framing: chip 1 in=TDM8/out=TDM16, chip 2 in=TDM16/out=TDM8.
- **Schematic-review findings baked in (2026-07-30):** DSPB O1 routes to
  **DA3**, not DA1 (DA1 dead-ends at Digital J18) — emitted as
  `DA_LANE_B_O1 = 3`; A_I3 has no D24 ADC (NET-only inputs 25–32); B_O3
  "DAC MAIN" has no D24 sink BY DESIGN (D24 main outs are line outs on
  the Analog PCBA; lane reserved for D32/future).

`status` values: `ok` (verified against schematic rev C / review markup),
`provisional` (assignment plausible but unverified — confirm before HDL
freeze), `reserved` (line defined, no signals yet).

## Timing conventions (LOCKED 2026-07-31)

Encoded in the generated outputs (`timing` in sport_map.json,
`TDM_SAMPLE_EDGE_RISING`/`TDM_MFD` in dsp4_slot_map.vh) and consumed by
BOTH sides: receivers sample on the BCK **rising** edge, transmitters
launch on the **falling** edge (AKM converter convention); FS is a
one-BCK pulse asserted one BCK before slot 0 (MFD=1). Firmware sets
SPORT `CKRE=1` (per the 2156x HRM, CKRE picks the sampling edge and the
SPORT drives on the opposite edge); the RTL clkgen/reframer launch on
falling-edge strobes.

## RTL (`rtl/` + `quartus/`)

Key architecture fact from the rev C LOGIC sheet: **the inter-chip mix
fabric is direct DSP-to-DSP PCB routing** — it does not pass through
this CPLD. LOGIC owns the 8 BCK/FS pairs, the DSPA input lines
(AD/NET mux, codec, snake, re-framed Pi PCM, MEMS), the DSPB output
routing (DA0/DA3, codec-vs-snake per `strap_d32`, DAC MAIN, NET), and
DSP_CLK. DAC MAIN (B_O3) has **no D24 sink by design** — D24 main outs
are line outs on the Analog PCBA (resolved 2026-07-31).

- `rtl/dsp4_clkgen.v` — 49.152 MHz → TDM8/TDM16 BCK + MFD=1 FS pulses.
- `rtl/dsp4_pcm_reframe.v` — LOGIC masters the Pi PCM as I2S and
  re-frames stereo into TDM8 slots 0-1 (A_I6).
- `rtl/dsp4_logic_top.v` — routing per the slot map (sanity-checked
  against `dsp4_slot_map.vh`).
- `quartus/` — 5M1270ZT144C4 project. Status: map+fit+STA clean,
  Fmax 118.8 MHz (2.4x margin). **Pin assignments are NOT yet real**
  (free placement) — extract them from the LOGIC sheet (D24 DSP.pdf
  page 2/10) before building a committable `.pof`; until then no
  bitstream is committed. Toolchain: Quartus Prime Lite 21.1.1 at
  `/opt/intelFPGA_lite/21.1` (never committed); programming via
  USB-Blaster or Pi GPIO JTAG (SVF + OpenOCD).
