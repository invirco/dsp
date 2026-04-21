# AK4619 Direct-to-ADC Mic Preamp — Low Noise Implementation

## Schematic

3.3V supply, discrete Class A diff pair with current mirror load, cascode, bootstrap tail.
Target EIN: −128 dBu (150 Ω, unweighted, 20 Hz – 20 kHz).

```
                            3.3V
                             │
                  ┌──────────┤──────────┐
                  │          │          │
                 [R7]       [R8]       [R9]
                 1K0        1K0       10K
                  │          │          │
            ┌─────┤          ├─────┐   │
            │     │          │     │   │
            │  Q3a├──┐  ┌──┤Q3b   │   │      Q3: MMDT4403 (PNP dual)
            │  PNP│  │  │  │PNP   │   │      Current Mirror Load
            │     │  └──┘  │      │   │      (bases tied)
            │     │  bases │      │   │
            │     │          │      │   │
            │   [R10]      [R11]   │   │      R10,R11: 100R (mirror degeneration)
            │    100R       100R   │   │
            │     │          │      │   │
      OUT_P ●─────┤          ├─────● OUT_N    Differential output to AK4619
            │     │          │      │   │
            │  Q4a│          │Q4b   │   │      Q4: MMDT2227 (NPN dual)
            │  NPN├─[R12]──┤NPN   │   │      Cascode — common base
            │     │  10K    │      │   │      R12: bias divider
            │     │          │      │   │
            │  ┌──┘          └──┐   │   │
            │  C               C   │   │      (collectors of diff pair)
            │  │               │   │   │
            │  Q1a             Q1b │   │      Q1: DMMT3904W (NPN dual)
            │  NPN             NPN │   │      Differential Input Pair
            │  │\              /│  │   │
            │  │ \            / │  │   │
            │  B  E          E  B  │   │
            │  │   \        /   │  │   │
            │  │    └──┬───┘    │  │   │
            │  │       │        │  │   │
            │  │      [R3]      │  │   │
            │  │      220R      │  │   │      Tail — emitter degeneration
            │  │       │        │  │   │
            │  │    Q2a│        │  │   │      Q2a: DMMT3904W (NPN)
            │  │    NPN│        │  │   │      Tail Current Source
            │  │       │\       │  │   │
            │  │       │ E      │  │   │
            │  │       B  │     │  │   │
            │  │       │  │     │  │   │
            │  │      [R4]│     │  │   │
            │  │      10K │     │  │   │
            │  │       │  │     │  │   │
            │  │       ├──┘     │  │   │
            │  │       │        │  │   │
            │  │      [R5]      │  │   │
            │  │      3K3       │  │   │
            │  │       │        │  │   │
            │  │      GND       │  │   │
            │  │                │  │   │
      ┌─────┘  │                │  └───┤
      │        │                │      │
      │       [R1]            [R2]     │
      │      100M             100M     │
      │        │                │      │
      │       VBIAS            VBIAS   │      VBIAS = 1.65V (3.3V / 2)
      │        │                │      │
      │        │                │      │
      │    IN_P (hot)      IN_N (cold) │
      │        │                │      │
      │       [C1]            [C2]     │
      │       10uF            10uF     │      DC blocking (input coupling)
      │        │                │      │
      │        ● pin 2          ● pin 3│
      │        │                │      │
      │       [R13]           [R14]    │      Phantom feed (6K8 each)
      │       6K8              6K8     │
      │        │                │      │
      │        ├────────────────┤      │
      │        │   48V_PHANTOM  │      │
      │        │                │      │
      └────────┴────────────────┴──────┘

                    J1
              XLR / Combo Jack
              Pin 1 = GND (shield)
              Pin 2 = Hot (+)
              Pin 3 = Cold (−)
```

### Bootstrap Detail

```
                   3.3V
                    │
                   [R9]
                   10K
                    │
                    ├──── Q2a base
                    │
                   [C5]
                   10uF         Bootstrap cap — AC-couples the
                    │           emitter signal back to the tail,
                    ├──── Q1 emitter junction
                    │           increasing effective Ic at signal
                   [R5]        frequencies while maintaining
                   3K3          DC operating point
                    │
                   GND
```

### Output to AK4619

```
      OUT_P ──[R15]──[C3]──┐
               100R   220pF │
                            ├── AK4619 LRIN1+ (pin 5)
                            │
                           [C6]     AK4619 input
                           100pF    common-mode
                            │       filter
                            ├── AK4619 LRIN1− (pin 6)
                            │
      OUT_N ──[R16]──[C4]──┘
               100R   220pF

      VCOM ───[R17]──── AK4619 VCOM (pin 13)
               100R
               │
              [C7]
              10uF
               │
              GND
```

### Power Supply Decoupling

```
      3.3V ──┬──[C8]──┬──[C9]──┬── GND
             │  100nF  │  10uF  │
             │         │        │
             └─────────┴────────┘

      AK4619 AVDD (pin 14) ──┬──[C10]──┬──[C11]──┬── GND
                              │  100nF   │  10uF   │
                              └──────────┴─────────┘

      AK4619 DVDD (pin 26) ──┬──[C12]──┬──[C13]──┬── GND
                              │  100nF   │  10uF   │
                              └──────────┴─────────┘
```

## Bill of Materials (per channel)

| Ref | Value | Description | Package | Qty | Est. Cost |
|-----|-------|-------------|---------|-----|-----------|
| Q1 | DMMT3904W | NPN dual, diff pair | SOT-363 | 1 | $0.02 |
| Q2 | DMMT3904W | NPN dual, tail current src (1 half used) | SOT-363 | 1 | $0.02 |
| Q3 | MMDT4403 | PNP dual, current mirror load | SOT-363 | 1 | $0.02 |
| Q4 | MMDT2227 | NPN dual, cascode | SOT-363 | 1 | $0.02 |
| R1, R2 | 100M | Input bias (DC path) | 0402 | 2 | $0.02 |
| R3 | 220R | Tail emitter degeneration | 0402 | 1 | $0.01 |
| R4 | 10K | Tail base bias | 0402 | 1 | $0.01 |
| R5 | 3K3 | Tail current set | 0402 | 1 | $0.01 |
| R7, R8 | 1K0 | Mirror collector load | 0402 | 2 | $0.02 |
| R9 | 10K | Cascode/bootstrap bias | 0402 | 1 | $0.01 |
| R10, R11 | 100R | Mirror degeneration | 0402 | 2 | $0.02 |
| R12 | 10K | Cascode bias divider | 0402 | 1 | $0.01 |
| R13, R14 | 6K8 | Phantom feed | 1206 | 2 | $0.06 |
| R15, R16 | 100R | Output series (ADC protection) | 0402 | 2 | $0.01 |
| R17 | 100R | VCOM filter | 0402 | 1 | $0.01 |
| C1, C2 | 10µF | Input DC blocking | 0603 | 2 | $0.02 |
| C3, C4 | 220pF NP0 | Output HF filter | 0402 | 2 | $0.01 |
| C5 | 10µF | Bootstrap cap | 0603 | 1 | $0.01 |
| C6 | 100pF NP0 | ADC CM filter | 0402 | 1 | $0.01 |
| C7 | 10µF | VCOM bypass | 0603 | 1 | $0.01 |
| C8–C13 | 100nF / 10µF | Supply decoupling | 0402/0603 | 6 | $0.04 |
| J1 | Combo XLR/TRS | Input connector | — | 1 | $0.73 |
| **Total** | | | | **33** | **~$1.07** |

## DC Operating Point (3.3 V)

| Node | Voltage | Notes |
|------|---------|-------|
| 3.3V rail | 3.30 V | |
| VBIAS | 1.65 V | Mid-rail, from resistive divider or AK4619 VCOM |
| Q1 bases | 1.65 V | Via 100 MΩ bias resistors |
| Q1 emitters | 1.0 V | VB − VBE (0.65 V) |
| Tail current (R5) | 0.45 mA | (1.0 V − 0.65 V) / 3K3 × bootstrap boost |
| Q4 cascode base | 2.2 V | Set by R9/R12 divider |
| Q3 mirror output | 2.5 V | Collector of cascode, ~0.8 V below rail |
| OUT_P, OUT_N | ~2.5 V | Quiescent, differential = 0 V |
| Max differential swing | ±0.5 Vrms | Before ADC clipping |

## Performance Summary

| Parameter | Value |
|-----------|-------|
| Topology | Class A, discrete diff pair, current mirror, cascode |
| Supply | 3.3 V single (shared with AK4619 AVDD) |
| Gain (analog, fixed) | ×40 (32 dB) |
| Gain control | Digital (DSP / AK4619 volume register) |
| EIN (150 Ω, unweighted) | −128 dBu (theoretical) |
| EIN (150 Ω, expected measured) | −125 to −127 dBu |
| Max input level (0 dB gain) | −4 dBu |
| Output to ADC | Differential, DC-coupled via RC filter |
| Phantom power | 48 V switchable (external switch not shown) |
| Parts per channel | 33 (vs 111 in current op-amp design) |
| Cost per channel (@1000) | ~$1.07 (vs $2.62 in current design) |

## vs Current Design

| | Current (op-amp) | This (ADC-direct) |
|---|-----------------|-------------------|
| Parts | 111 | 33 |
| Cost @1000 | $2.62 | $1.07 |
| EIN (measured est.) | −126 to −128 dBu | −125 to −127 dBu |
| Max input | +21.5 dBu | −4 dBu |
| Gain control | Analog (64-step FET) | Digital only |
| PCB area | Large | ~30% of current |
| Phantom | Integrated | Integrated |
| Dynamic range | 150 dB | 135 dB |

The main trade-off is max input level and dynamic range. The 3.3 V direct design clips at −4 dBu input, which is fine for microphones but not line-level signals. For a mic-only input this saves 60% of cost and 70% of PCB area with only ~1 dB EIN penalty.

## Gain Switching Extension — 4-Step Series-R (Topology E)

Adding two series emitter degeneration resistors (R_A = 150R, R_B = 470R), each bypassed by a relay, gives **4 analog gain steps from only 2 relays + 2 resistors**:

| Relay A | Relay B | Degeneration | Gain | Max Input | EIN |
|---|---|---|---|---|---|
| Closed | Closed | 0 Ω | ×40 (32 dB) | −4 dBu | −128 dBu |
| Open | Closed | 150R | ×10 (20 dB) | +8 dBu | −122 dBu |
| Closed | Open | 470R | ×4 (12 dB) | +16 dBu | −115 dBu |
| Open | Open | 620R | ×2.5 (8 dB) | +20 dBu | −112 dBu |

Combined with AK4619 digital volume (−12 to +36 dB, 0.5 dB steps): **−4 to 68 dB** total range. Adds ~4 parts and ~$0.30/ch. Handles pro line level (+4 dBu with 16 dB margin) and hot signals up to +20 dBu.

See [gain_topology_comparison.md](gain_topology_comparison.md) for full trade-off analysis across all topologies.
