# Mic Preamp Schematic — micpre.pdf

## Overview

Single-channel microphone preamplifier with digitally-controlled analog gain switching. Part of the D24 analog board (component references R345–R414, Q98–Q116, U24–U25, J19). The design provides 0–60 dB of gain in 1 dB effective steps using a combination of 6-bit analog switching and DSP trim.

## Classification

**Hybrid Class A** — discrete Class A differential pair input stage followed by an IC op-amp gain stage. The MMDT2227 NPN pairs are biased for continuous conduction (always on, no crossover distortion), which defines the Class A character. The NJM2068M op-amp (internally Class AB) operates within its linear region as the gain block. This is the same topology used in professional interfaces like the Focusrite ISA and Audient preamps: discrete front-end for low noise and low distortion, IC gain stage for precise digitally-switched gain control.

## Input — J19

**CT-PJ-12HE-EP** Chunsheng vertical combo jack (XLR + 1/4″ TRS). Accepts balanced microphone or line-level signals.

## Phantom Power (48 V)

- **Q115, Q116** (MMDT4403 PNP) and **Q113, Q114** (MMDT5451 complementary NPN/PNP) form the switchable 48 V phantom power supply.
- **R348, R400, R414** (6K8, 0.5 W) are the phantom feed resistors on pins 2 and 3.
- **D29–D32** (1N4148WS) provide phantom blocking / polarity protection.
- **C208, C209** (470 µF, 6.3 V) decouple the phantom supply.
- **R346, R392** (10R, 0.5 W) limit surge current when phantom is engaged.

## Discrete Input Stage

**Q99, Q106–Q109, Q111** (MMDT2227, NPN dual SOT-363) form a discrete differential input buffer. This low-noise front-end converts the balanced signal to single-ended before the gain stage. Biased via high-value resistors (**R350, R365–R375**: 100 MΩ) and precision dividers (**R349, R354–R358**: 100 K; **R352, R353**: 33 K).

## Gain Stage — U24

**NJM2068M** dual low-noise op-amp in a non-inverting configuration:

- **Rf = 4K99** (R345, R404 — 0.1%, matching pair)
- **Rg** = parallel combination of up to 6 switched resistors
- **Gain = 1 + Rf / Rg**

### Gain Resistors (Rg network)

Six precision resistors (0.1%) are individually switched in/out by N-channel MOSFETs:

| Ref  | Value | Solo Gain | Role      |
|------|-------|-----------|-----------|
| R396 | 15R   | 50.5 dB   | Bit 0 (MSB conductance) |
| R395 | 37R4  | 42.5 dB   | Bit 1     |
| R397 | 93R1  | 35.1 dB   | Bit 2     |
| R398 | 232R  | 27.0 dB   | Bit 3     |
| R399 | 590R  | 18.8 dB   | Bit 4     |
| R394 | 1K47  | 11.2 dB   | Bit 5 (LSB conductance) |

With all six engaged the parallel Rg drives the maximum analog gain of ≈ 54 dB. Each MOSFET contributes approximately 3 Ω (Rds_on) in series with its resistor.

### 64 Analog Gain Steps

6 switches produce 64 unique parallel combinations covering 0–54 dB. The maximum gap between adjacent analog steps is ≤ 6 dB (first step, all switches off → LSB only). Above that the gaps compress to sub-dB spacing. A DSP trim of up to ≈ 6 dB fills every gap to achieve exact 1 dB output steps from 0–60 dB.

## Gain Switch Control

### MOSFET Switches

**Q98, Q100–Q104, Q110–Q112** (2N7002DW, dual N-channel 60 V MOSFET, SOT-363) — 8 packages providing the 6 gain switches plus spares / pad attenuation. Each FET shorts its gain resistor to ground (Rg path) when turned on.

### Shift Register — U25

**74HC595** 8-bit serial-in / parallel-out shift register (TSSOP-16). Receives the 6-bit gain code over SPI (data, clock, latch) from the system MCU. Outputs drive the MOSFET gates via **R376–R384** (10 K, 0.1%) current-limiting resistors. Gate pull-downs **R365–R374** (100 MΩ) ensure switches default to off when un-driven.

## Output Filtering

- **C203–C205** (220 pF, NP0) provide HF roll-off on the op-amp output.
- **C190** (33 µF) and **C191–C196** (decoupling, 100 pF / 0.1 µF / 10 µF) bypass the supply rails.
- **R388, R389** (4K99) set the output impedance / downstream attenuation.

## Signal Flow Summary

```
J19 (XLR/TRS combo)
  │
  ├─ Phantom 48V ──► Q115/Q116 + R348/R400/R414 (6K8) + D29-D32
  │
  ▼
Discrete differential input (Q99, Q106-Q109, Q111 — MMDT2227)
  │
  ▼
U24 NJM2068M — non-inverting gain stage
  │  Rf = 4K99
  │  Rg = parallel switched network (15R … 1K47)
  │       controlled by 2N7002DW FETs ◄── U25 74HC595 ◄── MCU SPI
  │
  ▼
Output filter (220pF NP0) ──► ADC / downstream
```

## Cost (per channel)

| Qty | Parts | @ 25 pcs | @ 1000 pcs |
|-----|-------|----------|------------|
| 111 | All   | $3.74    | $2.62      |

Connector J19 dominates at $0.90 / $0.73. Next largest costs are the MOSFET switches ($0.37 / $0.15) and shift register ($0.26 / $0.26).

## EIN Performance (±15 V rails)

At full gain with a 150 Ω source, 20 Hz – 20 kHz.

### Theoretical model (ideal)

| Source | nV/√Hz | Notes |
|--------|--------|-------|
| 150 Ω thermal | 1.58 | Absolute floor = −130.8 dBu |
| Discrete diff pair (MMDT2227) | 0.87 | Ic ≈ 1 mA, rbb' ≈ 10 Ω |
| NJM2068M (input-referred) | ~0.3 | 0.8 nV/√Hz reduced by discrete stage gain |
| **Total amplifier** | **0.92** | |
| **Combined (amp + source)** | **1.83** | **−129 dBu** |

### Measured vs theoretical

| Condition | Theoretical | Measured |
|-----------|-------------|----------|
| Unweighted, 150 Ω | −129 dBu | **−126 to −128 dBu** |
| A-weighted, 150 Ω | −131 dBu | — |
| Thermal floor, 150 Ω | −130.8 dBu | — |

The 1–3 dB gap is accounted for by real-world noise sources absent from the ideal model:

### Revised model (matching measurement)

| Source | nV/√Hz | Notes |
|--------|--------|-------|
| 150 Ω thermal | 1.58 | |
| Diff pair (rbb' = 20 Ω realistic) | 1.05 | MMDT2227 is general-purpose, not low-noise audio |
| NJM2068M (input-referred) | 0.3 | |
| FET Rds_on thermal + 1/f | 0.4 | 6× 2N7002 all on at max gain, MOSFET 1/f noise |
| Current noise (in × Rs) | 0.2 | Shot noise: IB ≈ 5 µA → 1.3 pA/√Hz × 150 Ω |
| **Total** | **~2.05** | **−127.5 dBu** |

Key contributors to the gap:
- **MMDT2227 rbb'**: general-purpose BJT, likely 15–30 Ω vs the 10 Ω assumed — biggest single factor
- **MOSFET Rds_on noise**: 6 FETs in parallel contribute thermal and 1/f noise in the Rg path
- **100 MΩ bias resistors**: 41 µV/√Hz thermal noise, partially coupled to signal path
- **PCB parasitics**: leakage, digital switching (74HC595/SPI) coupling into analog

### Potential improvements

| Change | Expected gain | Trade-off |
|--------|---------------|-----------|
| Low-noise BJT pair (THAT340, SSM2212) | +1 to 1.5 dB | Higher part cost |
| Increase diff pair Ic to 2 mA | +0.5 dB | More heat, reduced headroom |
| Relay bypass of FETs at max gain | +0.3 dB | Added relay, complexity |

### EIN vs Supply Voltage

EIN is dominated by the 150 Ω source thermal noise (1.58 nV/√Hz, floor = −130.8 dBu) and changes little with supply voltage. What drops significantly is output headroom and dynamic range.

**Theoretical (150 Ω, 20 Hz – 20 kHz, unweighted):**

| Supply | Diff pair Ic | en_diff (nV/√Hz) | Total (nV/√Hz) | EIN | Max output | Dynamic range |
|--------|-------------|------------------|----------------|-----|------------|---------------|
| ±15 V | 1.0 mA | 1.05 | 2.0 | −129 dBu | +21.5 dBu | 150 dB |
| ±12 V | 1.0 mA | 1.05 | 2.0 | −129 dBu | +19.2 dBu | 148 dB |
| ±6 V | 0.5 mA | 1.24 | 2.1 | −128 dBu | +11.2 dBu | 139 dB |
| ±2.5 V | 0.15 mA | 1.88 | 2.8 | −126 dBu | +5.2 dBu | 131 dB |

**Expected measured (applying real-world offset from ±15 V measurement):**

| Supply | Theoretical | Expected measured |
|--------|-------------|-------------------|
| ±15 V | −129 dBu | −126 to −128 dBu |
| ±12 V | −129 dBu | −126 to −128 dBu |
| ±6 V | −128 dBu | −125 to −127 dBu |
| ±2.5 V | −126 dBu | −123 to −125 dBu |

Notes:
- ±15 V to ±2.5 V costs only ~3 dB of EIN but 19 dB of dynamic range
- NJM2068M requires ±3 V minimum; ±2.5 V would need a rail-to-rail op-amp (worse noise, ~3.6 nV/√Hz)
- Supply voltage choice is about headroom, not noise

### Op-Amp Comparison

All with 150 Ω source, discrete diff pair front-end (Ic = 1 mA), ±15 V supply, 20 Hz – 20 kHz unweighted.

**Op-amp specs:**

| Parameter | NJM2068M | NJM4580 | NJM4560 | TL072 |
|-----------|----------|---------|---------|-------|
| Input type | BJT | BJT | BJT | JFET |
| en (nV/√Hz) | 0.8 | 0.8 | 8 | 18 |
| in (pA/√Hz) | 0.4 | 0.4 | 0.5 | 0.01 |
| GBW (MHz) | 12 | 15 | 10 | 3 |
| Slew rate (V/µs) | 8 | 5 | 4 | 13 |
| Vcc min | ±3 V | ±2 V | ±2 V | ±3.5 V |
| Vcc max | ±18 V | ±18 V | ±18 V | ±18 V |
| THD+N (typ.) | 0.003% | 0.001% | 0.01% | 0.003% |
| Supply current (mA) | 5 | 4 | 5 | 2.5 |
| Package | SOP8 | SOP8 | SOP8 | SOP8 |
| Typical cost | ~$0.14–0.20 | ~$0.10–0.15 | ~$0.06–0.10 | ~$0.08–0.12 |

**EIN impact with discrete front-end (±15 V):**

The discrete diff pair dominates the noise so the op-amp matters less — its noise is divided by the front-end gain when referred to input. With ~8 dB discrete stage gain (÷2.5):

| Op-amp | en_opamp (nV/√Hz) | Referred to input | Combined amp noise | EIN (150 Ω) | Delta vs NJM2068M |
|--------|-------------------|-------------------|-------------------|-------------|-------------------|
| NJM2068M | 0.8 | 0.32 | 1.10 | −129.0 dBu | — |
| NJM4580 | 0.8 | 0.32 | 1.10 | −129.0 dBu | 0 dB |
| NJM4560 | 8.0 | 3.20 | 3.37 | −124.7 dBu | +4.3 dB |
| TL072 | 18.0 | 7.20 | 7.28 | −118.0 dBu | +11.0 dB |

**EIN without discrete front-end (op-amp only, non-inverting):**

If the discrete diff pair is removed and the op-amp runs the entire gain directly:

| Op-amp | en_opamp (nV/√Hz) | Combined with 150 Ω | EIN (150 Ω) | Delta vs NJM2068M |
|--------|-------------------|---------------------|-------------|-------------------|
| NJM2068M | 0.8 | 1.77 | −129.8 dBu | — |
| NJM4580 | 0.8 | 1.77 | −129.8 dBu | 0 dB |
| NJM4560 | 8.0 | 8.15 | −116.5 dBu | +13.3 dB |
| TL072 | 18.0 | 18.07 | −109.6 dBu | +20.2 dB |

**EIN vs supply voltage (with discrete front-end):**

| Op-amp | ±15 V | ±12 V | ±6 V | ±3 V | ±2.5 V |
|--------|-------|-------|------|------|--------|
| NJM2068M | −129.0 | −129.0 | −128.0 | −127.5 | N/A (min ±3 V) |
| NJM4580 | −129.0 | −129.0 | −128.0 | −127.5 | −127.0 |
| NJM4560 | −124.7 | −124.7 | −124.0 | −123.5 | −123.0 |
| TL072 | −118.0 | −118.0 | −117.5 | N/A (min ±3.5 V) | N/A |

All values in dBu, 150 Ω source, unweighted.

**Summary:**
- **NJM4580** is interchangeable with NJM2068M — same noise, lower Vcc min (±2 V), industry standard
- **NJM4560** is viable only where cost is paramount and −125 dBu is acceptable; the discrete front-end partially masks its 10× worse noise
- **TL072** is unsuitable for mic preamps — the JFET input has very low current noise (good for high-impedance sources like guitars/piezo) but its 18 nV/√Hz voltage noise overwhelms even the discrete front-end gain

### Direct-to-ADC Topology (No Op-Amp)

Concept: eliminate the op-amp entirely, run the discrete diff pair on the same supply as the ADC, and feed the diff pair collector output directly into the ADC input. Gain control would move to the digital domain (ADC PGA or DSP gain).

**Advantages:** fewer components, lower cost, no op-amp distortion, single supply domain.
**Trade-off:** ADC noise floor becomes a significant contributor since the discrete stage alone provides limited gain.

**ADC specs:**

| Parameter | AK4619 | AK5558 |
|-----------|--------|--------|
| Type | 4-in/4-out codec | 8-ch premium ADC |
| Resolution | 24-bit | 32-bit |
| SNR (A-wt) | 106 dB | 112 dB |
| SNR (unweighted, est.) | 103 dB | 109 dB |
| AVDD | 3.3 V | 5 V |
| Full-scale input | ~0.7 Vrms (SE) | ~2.8 Vrms (diff) |
| ADC noise (RMS, 20 Hz–20 kHz) | 5.0 µV | 9.9 µV |
| ADC noise density | 35 nV/√Hz | 70 nV/√Hz |

**Discrete stage at ADC supply voltage:**

| Parameter | AK4619 (3.3 V) | AK5558 (5 V) |
|-----------|-----------------|--------------|
| Diff pair Ic | 0.15 mA | 0.5 mA |
| re = VT / Ic | 173 Ω | 52 Ω |
| Discrete gain (practical) | ×10 (20 dB) | ×25 (28 dB) |
| en_diff (rbb' = 20 Ω) | 1.9 nV/√Hz | 1.24 nV/√Hz |
| Max output swing | ~0.5 Vrms | ~1.5 Vrms |

**EIN calculation (150 Ω source, 20 Hz – 20 kHz, unweighted):**

| Noise source | AK4619 (nV/√Hz) | AK5558 (nV/√Hz) |
|-------------|-----------------|-----------------|
| 150 Ω source thermal | 1.58 | 1.58 |
| Discrete diff pair | 1.90 | 1.24 |
| ADC noise (referred to mic input) | 3.50 (35 ÷ 10) | 2.80 (70 ÷ 25) |
| **Total (RSS)** | **4.3** | **3.5** |
| **EIN** | **−122 dBu** | **−124 dBu** |

**Comparison with op-amp topologies (all at ±15 V / 150 Ω):**

| Topology | EIN | Components | Cost delta |
|----------|-----|------------|------------|
| Discrete + NJM2068M (current design) | −129 dBu | 111 parts | Baseline |
| Discrete + NJM4580 | −129 dBu | 111 parts | ~$0 |
| Discrete → AK5558 direct (5 V) | −124 dBu | ~80 parts | −$0.40 |
| Discrete → AK4619 direct (3.3 V) | −122 dBu | ~80 parts | −$0.50 |
| NJM2068M only (no discrete) | −130 dBu | ~70 parts | −$0.60 |

**Why the direct-to-ADC approach loses 5–7 dB:**

The ADC noise floor (35–70 nV/√Hz) is 40–90× higher than a good op-amp (0.8 nV/√Hz). The discrete stage can only provide ×10 to ×25 gain at these supply voltages, so the ADC noise referred to the mic input is 2.8–3.5 nV/√Hz — comparable to or larger than the source thermal noise. With the op-amp at ±15 V, the same ADC noise is buried under 50+ dB of clean analog gain.

**When direct-to-ADC makes sense:**
- High channel-count products where −122 dBu is acceptable (live sound, broadcast)
- Cost-driven designs where saving the op-amp + gain network offsets the EIN loss
- Applications relying heavily on digital gain / DSP processing
- When the ADC has an integrated PGA (some codecs offer +20 dB), which could recover 2–3 dB of EIN

### Improving the Direct-to-ADC Concept

The ADC noise referred to input is the dominant term, so the primary lever is increasing discrete stage gain.

**1. Current mirror load (biggest single improvement)**

Replace the resistive collector load with an active current mirror (e.g., 2× MMDT4403 PNP). Increases voltage gain from ×10–25 to ×40–80:

| Parameter | Resistive load | Current mirror |
|-----------|---------------|----------------|
| Gain (3.3 V) | ×10 (20 dB) | ×40 (32 dB) |
| Gain (5 V) | ×25 (28 dB) | ×80 (38 dB) |
| ADC noise referred (AK4619) | 3.50 nV/√Hz | 0.88 nV/√Hz |
| ADC noise referred (AK5558) | 2.80 nV/√Hz | 0.88 nV/√Hz |
| Added parts | — | 2× PNP dual (SOT-363) |
| Added cost | — | ~$0.04 |

**2. Bootstrap the diff pair tail**

Bootstrap capacitor on the tail current source allows higher Ic at low supply:

| Parameter | Without bootstrap | With bootstrap |
|-----------|-------------------|----------------|
| Ic (3.3 V) | 0.15 mA | 0.45 mA |
| re | 173 Ω | 58 Ω |
| en_diff (rbb' = 20 Ω) | 1.90 nV/√Hz | 1.27 nV/√Hz |
| Added parts | — | 1× cap (10 µF), 1× resistor |

**3. Lower-noise transistor**

| Transistor | rbb' (typ.) | en @ 1 mA | Cost | Package |
|-----------|-------------|-----------|------|---------|
| MMDT2227 (current) | 15–30 Ω | 1.0–1.2 nV/√Hz | $0.02 | SOT-363 |
| DMMT3904W | 10–15 Ω | 0.85 nV/√Hz | $0.02 | SOT-363 |
| BCM857BS (PNP pair) | 5–8 Ω | 0.65 nV/√Hz | $0.03 | SOT-363 |
| SSM2212 / THAT340 | 2–4 Ω | 0.45 nV/√Hz | $0.80+ | SOIC-8 |

DMMT3904W is the sweet spot — same cost, same package, lower rbb'.

**4. Cascode stage**

Add common-base cascode (1× MMDT2227) above collectors. Increases output impedance and stabilises gain at high frequencies. Cost: ~$0.02.

**5. Optimise collector resistor Rc**

For resistive-load case, maximise Rc within ADC headroom:

| ADC | Full-scale input | Optimal Rc (Ic = 0.5 mA) | Gain |
|-----|-----------------|--------------------------|------|
| AK4619 | 0.7 Vrms | 1K0 | ×15 |
| AK5558 | 2.8 Vrms | 3K3 | ×35 |

**Combined improvement — AK4619 (3.3 V):**

| Noise source | Before (nV/√Hz) | After (nV/√Hz) |
|-------------|-----------------|-----------------|
| 150 Ω source | 1.58 | 1.58 |
| Diff pair (DMMT3904W, bootstrapped) | 1.90 | 0.95 |
| ADC referred (mirror, gain ×40) | 3.50 | 0.88 |
| **Total** | **4.3** | **2.05** |
| **EIN** | **−122 dBu** | **−128 dBu** |

**Combined improvement — AK5558 (5 V):**

| Noise source | Before (nV/√Hz) | After (nV/√Hz) |
|-------------|-----------------|-----------------|
| 150 Ω source | 1.58 | 1.58 |
| Diff pair (DMMT3904W, Ic = 1 mA) | 1.24 | 0.85 |
| ADC referred (mirror, gain ×80) | 2.80 | 0.88 |
| **Total** | **3.5** | **2.0** |
| **EIN** | **−124 dBu** | **−129 dBu** |

**Improvement summary:**

| Change | EIN gain | Added cost | Complexity |
|--------|----------|------------|------------|
| Current mirror load | +4 to 5 dB | $0.04 | Low — 1 package |
| Bootstrap tail | +1 to 2 dB (3.3 V) | $0.01 | Low — passive |
| DMMT3904W swap | +0.5 to 1 dB | $0 | None — drop-in |
| Cascode | +0.5 dB (stability) | $0.02 | Low — 1 package |
| Optimise Rc | +2 to 4 dB | $0 | None — value change |
| **All combined** | **+5 to 6 dB** | **~$0.07** | **Moderate** |

With all changes the direct-to-ADC approach reaches −128 to −129 dBu — matching the op-amp topology while eliminating the op-amp, gain switching FETs, shift register, and ~30 passive components.
