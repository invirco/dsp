# FPGA platform shortlist (32 / 64 / 128 ch @ 96 kHz, ≥2× GbE)

Status: proposal, 2026-08-02. Vendor research points at Xilinx/AMD as
class leader for this space; this doc sizes the tiers and names parts.
Nothing binding until a numbered architecture decision.

## Sizing reality (from README budget math)

- **DSP compute does not drive part selection.** 128 ch @ 96 kHz —
  16,384 matrix sends + ~6,000 biquad MACs per sample — needs <15 DSP
  slices at 250-400 MHz. Every candidate part has hundreds.
- **d128.csv check (mx26 src/pd, concept draft)**: the real worst case
  is 128 ch × ~68 buses, per-channel FIR, 4 reverbs + 20 insert slots,
  128-track recording. FIR is the one real DSP consumer (512 taps ×
  128 ch @ 96 kHz ≈ 25 TM slices) — total demand still <100 slices.
  OPEN: `ch.fir` has no tap count in d128.csv; FIR length × 128 ch is
  the biggest swing factor in DSP + BRAM budgets — get a ceiling into
  the product definition. Recording + FX control land on the A53s,
  reinforcing the SoC choice for this tier.
- Real constraints: **BRAM** (delay lines, FX tanks), a **DDR
  interface** (long delays), **pins** (TDM lanes), and **where the
  control CPU lives** (float control plane, coeff derivation, FX).
- **The proprietary link shrinks the pin problem**: if most I/O
  arrives over the P2P network link, 2-4 GbE PHYs carry hundreds of
  channels; local TDM is only for the Dante option card and local
  converters.
- **GbE subtlety**: hard Ethernet MACs on SoC parts (Zynq GEMs) are
  processor-side — fine for management, wrong for the isochronous
  audio link. The link uses external RGMII PHYs + our own thin fabric
  MAC on ANY part. So "2× GbE" costs 2 PHY footprints + ~24 pins,
  independent of silicon choice.

## Proposed Xilinx parts

| Tier | Part | Rationale | Price (checked 2026-08-02) |
|---|---|---|---|
| 32 ch | Zynq-7000 **XC7Z020**-CLG484 | 220 DSP, 4.9 Mb BRAM, dual A9 (control/coeff plane), hard DDR3; most proven SoC FPGA, huge SoM ecosystem (Trenz, MYIR, iWave) | $145 @1 catalog; ~$90-120 @1k (quote lower) |
| 64 ch | same XC7Z020 | Same silicon genuinely covers 64 ch; differentiate by I/O fit-out — one bitstream + product config (mirrors D3) | — |
| 128 ch | Zynq US+ via **Kria K26 SoM** (XCK26 ≈ ZU5EV: 1,248 DSP, 5.1 Mb BRAM + 18 Mb UltraRAM, quad A53 + dual R5, 4 GB DDR4 on-module) | A53s absorb FX + coeff plane; UltraRAM suits reverb networks; SoM removes DDR4 layout risk; in free Vivado tier. **At ~1k/yr the SoM IS the volume plan** — $325 buys silicon + DDR4 + eMMC + power tree; AMD positions Kria for production | $325 MSRP commercial (~$406 spot) |
| 128 ch chip-down | **XCZU5EV-1SFVC784** | Same silicon as K26. SFVC784 is pin-compatible ZU2CG/ZU3EG/ZU4EV/ZU5EV — one flagship PCB depopulates down-family. Hard USB 3.0 serves d128's 128-track recording. Only wins over the SoM at ~5-10k+/yr with a negotiated quote | catalog $2.3-2.5k @1 is FICTION (whole K26 SoM = $325); real quote plausibly $200-400 |
| 128 ch escape hatch | **XCZU7EV** (1,728 DSP, 11 Mb BRAM + 27 Mb URAM) | Only if FX scope outgrows ZU5EV URAM + A53s; larger package (FBVB900-class) = board respin. Fallback, not default | quote only |
| cost-down later | **Spartan UltraScale+ SU35P/SU55P** (XCSU35P-2SBVB625E) | 16 nm cost-optimized family, volume production ramped 2025-26 (SU200P July 2026); chip-down candidate for the 32-ch tier at volume | $87 @1 catalog; ~$60-75 @1k |

Pure-fabric alternative (keeps Pi as sole master, D1 unchanged, no
SoC): Artix-7 XC7A100T/200T (32/64 ch), Artix US+ AU25P (128 ch).
Trade: no ARM to absorb FX — FX becomes fabric redesign or DSP
sidecar. For d128's FX-heavy spec + 128-track recording this route
fights the product; better matched to the 32/64 tiers.

## Single-chip fit: everything on one ZU5EV (128×128 check)

All functions land on one chip; per-function budget:

- **Mixing/processing**: all TM engines (biquads, dynamics, ~4 MAC
  summing lanes for 128×68, FIR ~25 slices) total <100 of 1,248 DSP
  slices. Not in question at any tier.
- **SAI/TDM**: just LVCMOS pins (~200 user I/O on SFVC784); Dante
  card + local converters + clocks = a few dozen.
- **GbE streaming ports**: per port, one external RGMII PHY (~12
  signals) + a few hundred LUTs of fabric MAC/packetizer. 2-4 ports
  negligible; PS hard GEMs stay free for management.
- **Delays/memory**: 128 ch of DDR delay r/w @ 96 kHz ≈ 100 MB/s vs
  ~19 GB/s DDR4 — noise, even shared with the ARM side. Reverb tanks
  + FIR state in the 18 Mb UltraRAM.
- **Recording/control/host**: quad A53 + hard USB 3.0, no fabric cost.
- **The one margin variable is FX** (4 reverbs + 20 inserts): fabric
  (TM delay-network engine — real design effort, the only block whose
  utilization could genuinely grow) vs A53/NEON (comfortable for this
  count; block-latency and determinism need care) vs hybrid. Both
  homes are on the same chip, so single-chip holds either way; the FX
  decision determines margin and whether the ZU7EV hatch is ever
  pulled. Settle FX placement early (README open question 2).

## 128-track recording to USB SSD

Bandwidth-priority requirement (2026-08-02): USB-SSD recording and
DAW streaming MAY be channel-limited as product decisions; the Dante
option card and the prop link may NOT — both are full-mixer-bandwidth
paths (see README I/O sketch; rules out Brooklyn-II-class Dante
modules at 96 kHz — needs Dante HC / IP-core class or ganged
modules).

- Bandwidth: 128 trk × 96 kHz × 32-bit ≈ **49 MB/s** (24-bit packed
  ≈ 37 MB/s). USB 3.0 practical ~350-400 MB/s → ~8× headroom.
  **USB 2.0 (~35-40 MB/s practical) can NOT carry it** — the
  recording spec silently depends on the ZU+ tier's hard USB3.
- Real issue is SSD write stalls (GC pauses, SLC-cache cliffs), not
  bandwidth. Fix: DDR4 ring buffer between fabric/DMA fill and a
  Linux writer thread (512 MB ≈ 10 s of 128-trk audio) → survives
  multi-second stalls. Stack is ordinary Linux on the A53s: UAS mass
  storage, exFAT/ext4. Testable on the dev kit day one.
- Upgrade paths without touching fabric: the 4× PS-GTR transceivers
  also do SATA 3.1 and PCIe Gen2 (NVMe) — the answer if a future spec
  wants higher rates or record+playback punch-in guarantees.

## Cost: multi-2156x vs single FPGA, DSP-only basis (2026-08-02)

Silicon-only @ 1k, **96 kHz** (the platform rate; at 48 kHz the DSP
column halves and multi-SHARC wins outright — the FPGA cost case is
specifically a high-sample-rate story). ADSP-21569 (1 GHz) $33.97 @1
catalog → ~$28-30 @1k. Per 1 GHz SHARC @96k: ~10,400 cycles/sample;
d128's per-channel FIR (512 taps × 32 ch ≈ 16,400 MACs/sample) alone
overflows one chip per 32-ch block → 2 chips/block at full spec.

Scenario A — full d128-grade strips (WITH FIR):

| Tier | Multi-DSP | Single FPGA |
|---|---|---|
| 64 ch | 4× 21569 + FX chip + mux + PSRAM/flash ≈ **$185-200** | 7020 + DDR3 + flash ≈ **$115-135** |
| 128 ch | 10 chips + mux + memories ≈ **$370-390** | ZU5EV/K26 ≈ **$300-350** |

Scenario B — light strips (no FIR, ~4-band EQ), 1 chip/32-ch block:

| Tier | Multi-DSP | Single FPGA |
|---|---|---|
| 64 ch | ≈ **$100-130** | ≈ **$115-135** |
| 128 ch | ≈ **$180-220** | ≈ **$300-350** |

**Conclusion:** SHARC only wins under a light processing spec that
d128.csv already rules out (FIR, 8-band EQ, 4 reverbs, 20 inserts).
At 96 kHz with the real spec the single FPGA is equal-or-cheaper on
silicon AND deletes the 10-chip system tax (backplane, connectors,
per-chip boot/power/PSRAM, inter-chip TDM scheduling — which needs a
CPLD/FPGA mux anyway). Structural point: SHARC spec-creep costs
discrete chips/respins; FPGA spec-creep costs utilization % (<20%
DSP even at full d128 scope). Streaming was excluded here by
construction — the real product requires MW-Net + Dante, both native
to the FPGA. What remains for SHARC: the shipping D32/D24 path
(D3/D5 undisturbed), mature FX kernels as a possible transition
sidecar, lower near-term NRE. Transition facts, not counterarguments.
NOTE: `ch.fir` tap count is now worth ~$150-200 of BOM in this
comparison — the action item has a price tag.

## DAW + recording connectivity strategy (2026-08-02)

**DAW play/rec — class-compliant USB at the edges, no native MW-Net
computer endpoints:**

- Primary: **console-hosted USB gadget port** (rear USB-B/C, Linux
  UAC2 gadget on the A53s). Class-compliant → zero custom drivers on
  Windows/macOS/Linux. Market norm is ~32×32 (USB2-era silicon:
  X32/M32, SQ, CL/QL); our USB3 plausibly does 64 @ 96 kHz —
  a quiet leapfrog. This is d128.csv's `rec.usb`.
- Above the USB port's count, computer recording rides the **Dante
  card + Audinate's computer-side ecosystem** (DVS ≈64×64, less at
  96 kHz; full 128 @ 96 kHz → customer buys a Dante PCIe-class card).
  This matches the industry pattern — consoles handle >32-ch computer
  recording by pointing at Audinate — and it's the same
  driver-tax-outsourcing decision as the option card itself.
- **POLICY — ruled out: native MW-Net computer endpoints** (PCIe card
  or NIC + custom audio driver, the SoundGrid/DVS model). Permanent
  multi-OS kernel/ASIO/CoreAudio driver treadmill (Audinate and Waves
  fund standing teams for this), and a commodity NIC fights
  clock-from-link (forces timestamp+buffer machinery back in). Same
  spirit as the no-COTS-switch rule.
- Optional catalog item later: **MW-Net↔USB bridge box** (module link
  block minus converters + XMOS-class UAC2 USB side) — lets a laptop
  join the network anywhere (FOH rig, stage). Not needed for launch.
- The onboard USB-SSD 128-track recorder is the differentiator, not
  the USB port: full-bandwidth capture + virtual-soundcheck playback
  with no computer (the X-Live lesson, at 4× the track count).

**Recording media decision tree:**

- **PRIMARY: removable SSD on front-panel USB3, USB-C connector**
  (~10k mating cycles). Wins on cycle rating, capacity economics
  (128 trk @ 96 kHz writes ~177 GB/hour — SSD $/GB beats cards
  decisively), universal readers, zero exotic software. Reliability:
  DDR4 ring buffer (~10 s stall tolerance) + format-in-console +
  qualified-drive list. **Dual USB3 ports with mirrored recording**
  as the redundancy feature (ring buffer grows a second drain
  thread — nearly free).
- **CONTINGENCY: internal SATA M.2** via PS-GTR (hard SATA 3.1 in
  the PS, standard AHCI) for a premium guaranteed-capture SKU.
  Internal-only: the SATA connector is rated ~50 mating cycles —
  unusable for pull-every-show removable media. Reserve the PS-GTR
  lane now, decide later.
- **REJECTED**: eSATA (dead standard, don't put it on a 2026
  product); SD cards (needs V60/V90 to survive 49 MB/s sustained,
  and 177 GB/h kills card economics — right for X-Live's 32 trk,
  wrong at 128); CFexpress Type B (removable NVMe done right, but
  media $/GB and PCIe surprise-removal complexity make it a premium
  slot option at most, not the baseline).
- **COMPLEMENT**: post-show network offload of internal recordings
  over GbE/SMB — convenience, not a replacement for removable media.

## Alternatives (non-Xilinx)

- **Intel Cyclone V SoC (5CSEBA6)** — direct 7020 analog; Quartus
  already in-house (CPLD flow). Family is old, Agilex 3 still
  ramping → Xilinx is the safer bet.
- **Lattice ECP5 / CertusPro-NX** — wrong for the console, RIGHT for
  the I/O modules: link block + TDM + converter glue on a ~$25-50
  part, open-toolchain option. Consequence: write the link block in
  vendor-neutral Verilog so console (Xilinx) and modules (Lattice)
  share it unchanged.
- **Microchip PolarFire SoC (MPFS025T)** — RISC-V, very low power
  (fanless), free toolchain; weaker ecosystem. Consider if thermals
  dominate.
- **Efinix Titanium** — cheap, ecosystem too young for a console
  platform. Watch only.

## Prototype path

- Flagship: **KR260 robotics kit** (~$349-399) over the KV260 (~$249)
  — same K26 SoM, but the KR260 has TWO GbE ports routed through the
  PL (RGMII, TI DP83867 PHYs — the same PHY class a product board
  would carry) plus SFP+ on a PL GTH. That is the proprietary-link
  dev target exactly: fabric MAC → PL RGMII → real ports; two boards
  rehearse star AND daisy-chain. Also 4× USB3 (SSD recording test)
  and Pmod/HAT PL I/O for TDM codec breakouts.
- Eval-kit prices (2026-08): KV260 $249 (refreshed 2025, same price);
  KR260 ~$349-399; ZCU104 (ZU7EV) ~$1.7-1.9k — buy ONLY if the
  escape hatch is pulled. There is no traditional standalone ZU5EV
  eval board; Kria carriers took that role.
- Realistic bring-up spend: one KR260 (two for chain tests) + RGMII
  PHY breakouts + codec breakout, $0 tooling.
- Entry tier: any commodity 7020 board/SoM.
- All proposed parts are covered by free Vivado tiers. Toolchain rule
  extends: never commit Vivado/Vitis (same as Quartus).

## Action items when this activates

1. **Get real Avnet/AMD 1k quotes for XC7Z020 and SM-K26** — the
   catalog-vs-quote gap is the whole pricing story for AMD parts
   (see table: ZU5EV catalog is fiction).
2. Get a tap-count ceiling for `ch.fir` into the d128 product
   definition (biggest DSP+BRAM swing factor).
3. Settle FX placement (fabric vs A53 vs hybrid) before freezing
   BRAM/URAM budgets — it alone decides ZU5EV vs ZU7EV.
4. Check KR260 schematic for which RJ45s land on PL before buying.
5. Fix the PS-GTR lane allocation early (4 lanes: USB3 + DP +
   reserved SATA/PCIe spare) — it's board-level and gates the
   internal-drive contingency.

## Sources (checked 2026-08-02)

- Spartan US+ production: amd.com blogs "spartan-ultrascale-plus-fpgas-
  in-production" (2025), "amd-spartan-fpga-grows-up" (2026, SU200P).
- Kria K26 pricing/availability: amd.com Kria K26 page ($325 MSRP
  commercial); DigiKey SK-KV260-G listing (~$406 spot / ~$562
  industrial).
- Chip catalog prices: DigiKey XC7Z020-1CLG484C ($145),
  XCZU5EV-1SFVC784I ($2,285-2,473, backorder), XCSU35P-2SBVB625E
  ($86.89, in stock).
- KV260 refresh at $249: amd.com blog "kria-kv260-vision-ai-starter-
  kit-refresh" (2025).
- KR260 PL Ethernet detail: UG1092 (KR260 user guide); Xilinx
  kria-apps-firmware device trees (DP83867 PHYs, GMII-to-RGMII);
  kria-apps-docs TSN/PTP reference designs.
