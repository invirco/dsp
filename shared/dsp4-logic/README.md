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
  re-frames stereo into TDM8 slots 0-1 (A_I6). Parameter
  `PCM_DATA_DELAY` (default 1 = Philips I2S, 0 = left-justified) sets
  where the Pi's MSB is expected relative to the LRCLK edge; the Pi's
  CH1POS is programmable, so this is the one constant to move if bring-up
  shows different framing. Both settings are covered by the sim suite.
- `rtl/dsp4_logic_top.v` — routing per the slot map (sanity-checked
  against `dsp4_slot_map.vh`).
- `quartus/` — 5M1270ZT144C4 project with the REAL pin assignments
  (all 144 pins extracted 2026-07-31 from the LOGIC sheet, D24 DSP.pdf
  p2/10 at 300 DPI). map/fit/STA/asm clean; Fmax 75.9 MHz with pins
  (1.5x margin over 49.152). PROVISIONAL pin choices, marked in the
  qsf: S4 = product personality; snake/DAC-MAIN parked on PLL5_0-2.
  Discovered provisions: ISPI0/ISPI1/ICS_L (pins 60-62) are an S-MCU
  SPI interface to LOGIC — the future home of runtime lane-mux
  control; UART pass-through pins are TODO(uart-passthrough).
  Current build: **156 LE / 1270 (12%), 67 pins, Fmax 68.24 MHz**
  (setup slack +5.690 ns on the 20.345 ns period). On the rev-D
  5M570ZT144C4 the same RTL fits at 27% but closes at only
  **50.67 MHz — +0.611 ns slack, ~3% margin** over the required
  49.152 MHz (measured 2026-08-07 in a scratch run, PIN_137/mems
  released for the fitter per D8). Treat every RTL addition on that
  part as timing-relevant.
- `build.sh` — full flow (slot-map regen -> **sim gate** -> map/fit/sta/asm
  -> pof/svf) with an STA gate; artifacts land in `bitstream/` labelled
  with the first 12 hex of sha256(slot-map hash + RTL + qsf/sdc), plus a
  manifest recording whether the sim gate passed. `bitstream/` is
  committed (D2). Toolchain: Quartus Prime Lite 21.1.1 at
  `/opt/intelFPGA_lite/21.1` (never committed); programming via
  USB-Blaster or Pi GPIO JTAG (SVF + OpenOCD).

## Simulation (`sim/`) — the gate that runs before any bitstream

Icarus Verilog, Verilog-2001, self-checking, no waveform inspection
required: `./sim/run.sh` (or `VCD=1 ./sim/run.sh` for traces in
`sim/work/`). `build.sh` runs it and refuses to produce a bitstream if it
fails; `SKIP_SIM=1` overrides and is recorded in the manifest.

The testbenches assert the **conventions**, not the implementation. Two
behavioural models are the arbiters, and if RTL and model disagree the
RTL is wrong (or the convention changes deliberately, in both places):

| File | Role |
|---|---|
| `sim/model_tdm_rx.v` | DSP-side TDM receiver as a SPORT with CKRE=1/MFD=1 sees the wire: sample on BCK rising, FS one BCK before slot 0, MSB first |
| `sim/model_pi_i2s_tx.v` | Pi PCM block transmitting I2S as a clock slave; `DATA_DELAY` matches the RTL's `PCM_DATA_DELAY` |
| `sim/tb_clkgen.v` | BCK divide ratios, FS pulse width, 256-BCK8 / 512-BCK16 frame length, launch/sample strobes land on the BCK edges they name |
| `sim/tb_pcm_reframe.v` | Pi pins → TDM8 slots 0/1 bit-exact, slots 2-7 silent; run for both `PCM_DATA_DELAY` settings |
| `sim/tb_logic_top.v` | Clock-pair roles by measured format (a swapped BCKI/FSI pair is a dead board), input-lane sources, DSPB output routing incl. B_O1→DA3 and the D24/D32 personality split |

The testbenches also model the board fact that **U3 has no reset** — MAX V
macrocells power up cleared — by initialising DUT state explicitly
instead of letting it sit at X.
- Host tool: `tools/pi/dsp4_config.py` (repo root) writes the boot
  product config over Pi SPI (GPIO-driven CS; SPI_RDY flow control is
  a bring-up TODO).
