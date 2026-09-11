provenance: AI-drafted 2026-09-11 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S34 CPLD cost study — what the proposed LOGIC additions cost in LEs

**This branch is a measurement, not a candidate.** Nothing here is merged,
nothing here was flashed, and no `.pof` was produced. Every number below
came from a real Quartus 21.1.1 map/fit/sta run on this machine against
the 5M1270ZT144C4 (1,270 LEs), on 2026-09-11.

Each project selects one proposal with a `VERILOG_MACRO`; the RTL is the
shipping RTL with `ifdef`-guarded additions, so a build with no macro set
is bit-identical to today's shipping personality.

## Results

| build | what it adds | LEs | Δ vs base | pins | Fmax |
|---|---|---|---|---|---|
| `quartus/dsp4_logic` | shipping today (baseline, rebuilt today) | 404 | — | 71 | 64.52 MHz |
| `s34a_slot3` | option slot 3 as a second net card | 402 | **−2** | 79 | 69.78 MHz |
| `s34b_slot2` | option slot 2 as a second net card | 402 | **−2** | 79 | 63.70 MHz |
| `s34c_pack` | codec + MEMS + Pi packed onto one TDM8 lane each way | 419 | **+15** | 71 | 61.62 MHz |
| `s34d_netsel` | runtime `net_sel` over the S-MCU SPI path | 452 | **+48** | 74 | 61.90 MHz |
| `s34e_all` | all four at once | 463 | **+59** | 90 | 66.51 MHz |

Everything fits with room to spare: the worst case is **463 / 1,270 =
36 %**, and the part still has 24 free I/O after it. The 49.152 MHz sysclk
needs 20.35 ns; the worst variant closes with **4.1 ns of setup slack**
(`s34c_pack`), and hold slack is 1.118 ns in every build including the
baseline.

## How to read the two negative deltas

A 2-LE *reduction* from adding two multiplexers is not a saving — it is
the fitter packing 400-odd LEs differently. Run-to-run the placement moves
by a few LEs and Fmax by several MHz for the same reason (the shipping
build's own manifests record 68–70 MHz where today's rebuild reads 64.5).
Read the slot-2/slot-3 rows as **"below the noise floor, call it under
5 LEs"**, and the pack and `net_sel` rows — 15 and 48 — as real.

The lane mux itself is one LE per lane by construction: the cost of a
second option card is **pins, not logic** (8 per slot, both slots
together take the part from 62 % to 79 % of its I/O).

## What each build actually builds

- **`s34a_slot3` / `s34b_slot2`** — the slot's four card-output lanes
  arrive at U3 on the PLL3/PLL5 group and two of them are strap-selected
  onto DSPA I5/I7; three DSPB lanes (O3/O6/O7) drive the card's input
  lanes on the PLL4/PLL6 group. Pin locations are the netlist's, including
  the pairwise `_0/_1 ↔ _2/_3` swap that slots 2 and 3 have (slot 1's
  mirroring is a *reversal*; these two are not the same shape).
  `s34b_slot2` also **re-parks** `snake_in`/`snake_out`/`dac_main`, which
  the shipping qsf puts on pins 109/110/111 — three of the slot-2 lanes.
- **`s34c_pack`** — one TDM8 lane carries codec (slots 0–3), MEMS (slot 5,
  its own strapped slot) and the Pi (slots 6–7, replayed there by the
  re-framer), freeing A_I6 and A_I7; the return lane carries codec out in
  slots 0–3 and the Pi return in 6–7, freeing B_O3. Each source keeps its
  own slot index, which is what makes this a bit mux instead of a 32-flop
  store-and-forward per lane.
- **`s34d_netsel`** — a listen-only 16-bit SPI slave framed by CS_L, with
  the select applied at a frame boundary. See the session write-up for why
  it is listen-only and what the S-MCU has to promise.

## Re-running

```
cd shared/dsp4-logic/quartus/s34
Q=/opt/intelFPGA_lite/21.1/quartus/bin
$Q/quartus_map --read_settings_files=on s34c_pack && $Q/quartus_fit s34c_pack && $Q/quartus_sta s34c_pack
grep -E "Total logic elements|Total pins" output_files/s34c_pack.fit.summary
```
