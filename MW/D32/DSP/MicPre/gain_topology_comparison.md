# Mic Preamp Gain Topology Comparison

All figures: 150 Ω source, 20 Hz – 20 kHz unweighted, improved discrete front-end (DMMT3904W, current mirror, cascode).

## Topology Overview

| # | Topology | Analog Gain | Gain Control | Gain Switching Hardware |
|---|----------|-------------|--------------|------------------------|
| A | **Current design** (op-amp + 6-bit FET network) | 0–54 dB (64 steps) | Analog (FETs) + DSP trim | 6× 2N7002DW + 74HC595 + 12 precision R |
| B | **Direct-to-ADC, fixed gain** | ×40 (32 dB) fixed | Digital only (AK4619 + DSP) | None |
| C | **Direct-to-ADC, 2 switched steps** | ×40 / ×4 (32 / 12 dB) | 1 relay + digital | 1× relay + 1 resistor |
| D | **Direct-to-ADC, 3 switched steps** | ×40 / ×10 / ×4 (32 / 20 / 12 dB) | 2 relays + digital | 2× relay + 2 resistors |
| E | **Direct-to-ADC, 4-step series-R** | ×40 / ×10 / ×4 / ×2.5 (32 / 20 / 12 / 8 dB) | 2 relays + digital | 2× relay + 2 series resistors (R_A=150R, R_B=470R) |

## Performance Comparison

| Parameter | A: Op-amp + FETs | B: Fixed ×40 | C: 2-step relay | D: 3-step relay | E: 4-step series-R |
|-----------|-------------------|-------------|-----------------|-----------------|--------------------|
| **EIN (best)** | −128 dBu | −128 dBu | −128 dBu | −128 dBu | −128 dBu |
| **EIN (worst setting)** | −128 dBu | −128 dBu | −115 dBu (×4) | −115 dBu (×4) | −112 dBu (×2.5) |
| **Max input level** | +21.5 dBu | −4 dBu | +16 dBu | +16 dBu | +20 dBu |
| **Total gain range** | 0–54 dB | 20–68 dB | 0–68 dB | 0–68 dB | **−4 to 68 dB** |
| **Dynamic range** | 150 dB | 124 dB | 131 dB (×4) | 131 dB (×4) | 132 dB (×2.5) |
| **Gain resolution** | 1 dB (analog+DSP) | 0.5 dB (digital) | 0.5 dB (digital) | 0.5 dB (digital) | 0.5 dB (digital) |
| **Handles line level (+4 dBu)** | ✅ Yes | ❌ Clips | ✅ Yes (12 dB margin) | ✅ Yes (12 dB margin) | ✅ Yes (16 dB margin) |
| **Handles hot line (+16 dBu)** | ✅ Yes | ❌ Clips | ✅ At limit | ✅ At limit | ✅ Yes (4 dB margin) |
| **Handles +20 dBu** | ✅ Yes | ❌ Clips | ❌ Clips | ❌ Clips | ✅ At limit |

## Source Suitability

| Source Type | Typical Level | A: Op-amp + FETs | B: Fixed ×40 | C: 2-step | D: 3-step | E: 4-step series-R |
|-------------|---------------|-------------------|-------------|-----------|-----------|--------------------|
| Ribbon mic | −60 to −40 dBu | ✅ −128 dBu EIN | ✅ −128 dBu EIN | ✅ −128 dBu EIN (×40) | ✅ −128 dBu EIN (×40) | ✅ −128 dBu EIN (×40) |
| Dynamic mic | −55 to −20 dBu | ✅ −128 dBu EIN | ✅ −128 dBu EIN | ✅ −128 dBu EIN (×40) | ✅ −128 dBu EIN (×40) | ✅ −128 dBu EIN (×40) |
| Condenser mic | −40 to −10 dBu | ✅ −128 dBu EIN | ✅ −128 dBu EIN | ✅ −128 dBu EIN (×40) | ✅ −128 dBu EIN (×40) | ✅ −128 dBu EIN (×40) |
| Hot condenser (close, loud) | −10 to 0 dBu | ✅ | ⚠️ 4 dB margin | ✅ −128 dBu (×40) | ✅ −128 dBu (×40) | ✅ −128 dBu (×40) |
| Line level (pro) | +4 dBu | ✅ | ❌ Clips | ✅ −115 dBu (×4) | ✅ −122 dBu (×10) | ✅ −122 dBu (×10) |
| Line level (hot/peaks) | +10 to +20 dBu | ✅ | ❌ Clips | ⚠️ 6 dB margin (×4) | ⚠️ 6 dB margin (×4) | ✅ +20 dBu max (×2.5) |

## Cost & Complexity

| Parameter | A: Op-amp + FETs | B: Fixed ×40 | C: 2-step | D: 3-step | E: 4-step series-R |
|-----------|-------------------|-------------|-----------|-----------|--------------------|
| **Parts per channel** | 111 | 33 | ~35 | ~37 | ~37 (same as D) |
| **Cost @1000 pcs** | $2.62 | $1.07 | ~$1.22 | ~$1.37 | ~$1.37 (same as D) |
| **PCB area** | Large | ~30% of A | ~32% of A | ~34% of A | ~34% of A |
| **Supply voltage** | ±15 V | 3.3 V | 3.3 V | 3.3 V | 3.3 V |
| **MCU control** | SPI (6-bit shift register) | I²C only (AK4619) | 1 GPIO + I²C | 2 GPIO + I²C | 2 GPIO + I²C |
| **Gain switching noise** | FET transients | None | Relay click (at switch) | Relay click (at switch) | Relay click (at switch) |
| **Firmware complexity** | 64-step lookup + DSP trim | Trivial | Simple (2 ranges + digital) | Moderate (3 ranges + digital) | Moderate (4 ranges + digital) |

## EIN Detail by Analog Gain Step

| Analog Gain | ADC Noise Referred (nV/√Hz) | Total Noise (nV/√Hz) | EIN | Max Input | Usable DR |
|---|---|---|---|---|---|
| ×40 (32 dB) | 0.88 | 2.05 | −128 dBu | −4 dBu | 124 dB |
| ×20 (26 dB) | 1.75 | 2.54 | −126 dBu | +2 dBu | 128 dB |
| ×10 (20 dB) | 3.50 | 3.96 | −122 dBu | +8 dBu | 130 dB |
| ×4 (12 dB) | 8.75 | 8.94 | −115 dBu | +16 dBu | 131 dB |
| ×2.5 (8 dB) | 14.0 | 14.1 | −112 dBu | +20 dBu | 132 dB |

*ADC noise density: 35 nV/√Hz (AK4619). Diff pair: 0.95 nV/√Hz. Source: 1.58 nV/√Hz (150 Ω thermal).*

## Gain Coverage — AK4619 Digital Volume

The AK4619 provides digital volume from −12 to +36 dB in 0.5 dB steps per channel (registers 0x08–0x0B, 0x00 = mute, 0x18 = 0 dB, 0xFF = +36 dB).

### Combined Analog + Digital Range (Topology E: 4-step series-R)

Two series emitter degeneration resistors (R_A = 150R, R_B = 470R), each with its own relay bypass. Four relay combinations give four analog gain steps:

```
Q1a emitter ──[R_A 150R]──[R_B 470R]──── tail current
                 │             │
              relay A        relay B
              (bypass)       (bypass)
```

| Relay A | Relay B | Degeneration | Analog Gain | Gain (dB) | + Digital (−12 to +36 dB) | Total Range | EIN | Max Input |
|---|---|---|---|---|---|---|---|---|
| Closed | Closed | 0 Ω | ×40 | 32 dB | 32 + (−12) to 32 + 36 | **20–68 dB** | −128 dBu | −4 dBu |
| Open | Closed | R_A = 150R | ×10 | 20 dB | 20 + (−12) to 20 + 36 | **8–56 dB** | −122 dBu | +8 dBu |
| Closed | Open | R_B = 470R | ×4 | 12 dB | 12 + (−12) to 12 + 36 | **0–48 dB** | −115 dBu | +16 dBu |
| Open | Open | R_A + R_B = 620R | ×2.5 | 8 dB | 8 + (−12) to 8 + 36 | **−4 to 44 dB** | −112 dBu | +20 dBu |

Full coverage: **−4 to 68 dB** in 0.5 dB steps. Same 2 relays, same 2 resistors as Topology D — the 4th step is free from the "both in" combination.

### Optimal Analog Step Selection (Topology E)

| Total Gain | Best Analog Step | EIN | Max Input | Digital Setting |
|---|---|---|---|---|
| −4 to −1 dB | ×2.5 only | −112 dBu | +20 dBu | −12 to −9 dB |
| 0–7 dB | ×4 (×2.5 available too) | −115 dBu | +16 dBu | −12 to −5 dB |
| 8–19 dB | ×10 (best EIN available) | −122 dBu | +8 dBu | −12 to −1 dB |
| 20–68 dB | ×40 (best EIN) | −128 dBu | −4 dBu | −12 to +36 dB |

### Below 0 dB (Attenuation)

**Topology E provides −4 to 0 dB natively** (×2.5 analog + −12 to −8 dB digital), handling signals up to +20 dBu without any additional hardware.

For attenuation below −4 dB (very hot signals >+20 dBu):

1. **Switchable input pad** — resistive divider (e.g., −20 dB) before the diff pair, switched by a third relay. Extends range to −24 to +44 dB on the ×2.5 step, with +40 dBu max input.
2. **DSP attenuation** — software can attenuate after ADC, but the analog stage still amplifies by ×2.5 minimum, so this cannot prevent front-end clipping from signals above +20 dBu.

For mic preamp use, −4 dB minimum gain is more than sufficient.

### Beyond 60 dB

The ×40 analog step with +36 dB digital reaches **68 dB** total — 8 dB above the typical 60 dB maximum. This is useful for ribbon mics with very quiet sources. At 68 dB total gain, max input is −40 dBu (still suitable for ribbon mic output levels of −65 to −40 dBu).

## Recommendation

**Topology E (4-step series-R)** is the best overall design:

- Same hardware as Topology D (2 relays + 2 resistors), but the series-R trick gives a **free 4th step**
- −4 to 68 dB total range in 0.5 dB steps covers everything from attenuation to ribbon mic boost
- +20 dBu max input handles hot line level without any additional pad
- −128 dBu EIN for microphones (identical to current design)
- ~37 parts, ~$1.37/ch @ 1000 pcs (48% less than current design)
- 2 GPIO + I²C — simple firmware (4 gain ranges + AK4619 digital volume)

**Topology C (2-step relay)** remains viable for cost-optimised designs where +16 dBu max input and 0–68 dB range is sufficient. Saves one relay.

**Topology B (fixed)** is ideal for mic-only inputs where line level is never expected (e.g., dedicated mic channels in a high-count snake/stage box).
