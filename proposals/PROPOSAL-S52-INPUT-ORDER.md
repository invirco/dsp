provenance: AI-drafted 2026-09-16 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# PROPOSAL S52 — D24 input order: the 595 chain byte order and the chip-1 input patch

**Status: PROPOSED, NOT LANDED.** Two independent defects, both on the host
side. Neither needs a firmware, CPLD or `defs` change. PW rules; the hub
lands. Evidence: `findings.md` S52-1..S52-4, S51-4/S51-5.

## 0. What is wrong, in one paragraph each

**(i) The 595 image is sent backwards.** A 200-bit shift clocks the FIRST
byte sent to the FAR end of the chain (U76, chain index 24), so image byte
`p` lands on chain index `24−p` (S51-4, and every row of S52's table
below). `AnalogControlChain.BuildImage` puts SHIFT/U34 at byte 0 and the
channel at physical index `k` at byte `k`, so every `ch<N>` reaches the
register of a different XLR. The comment in the class already names this
as the one unverified fact of the first attach; it is now measured.

**Safety consequence today, not only a labelling one:** the SAFE image's
byte 0 (`0x00`, meant for U34) lands on **J42's register: mute OFF**,
and byte 24 (`0x01`, meant as ch24 muted) lands on **U34: INSTR1 ON**.
Every image with ch24 muted and instr1=0 (the boot-time safe image, the
bench restore scripts, every S48–S51 image) left J42 unmuted and INSTR1
asserted. Until the fix lands, "MIC 5 alone" is
`chain-set 27 ch8:mute=0,gain=0 ch24:mute=0 instr1=1`. And **a phantom request goes to the
wrong XLR**: `ch1:phantom=1` switches phantom on J41, not J15.

**(ii) The chip-1 input patch assumes the wrong in-converter slot order.**
The half-frame order (lanes 1–12 = every converter's slots 0–3, lanes 13–24
= slots 4–7) is NOT the reframer and NOT the frame-sync edge (S52-1). It is
`D24_INPUT_PATCH` in `tools/pi/dsp4_config.py`, written at boot to
`INPUT_PATCH[i]` (0xF010+) and applied at CONFIG_COMMIT. It encodes
"AD0 slots 0–3 = ch 1–4, slots 4–7 = ch 13–16", and
`MW/D32/DSP/product-config.md` itself says *"verify the within-ADC8 slot
order ... the table assumes block order"*. The netlist order is
`slot 7,6,5,4,2,3,0,1` for XLR positions 1..8, alternating front/rear rows.
Proven on the part: with an identity patch MIC 5 moves from C1_IN_20 to
C1_IN_16, with the D24 patch back it returns to 20 (S52-1).

## 1. Fix (i) — chain byte order

**Change:** build the image in PHYSICAL chain order (index 0 = U34 … index
24 = J42's register, i.e. exactly today's `ChannelOrder` table read as
head→tail), then **transmit it reversed**, so transmit byte `p` = physical
index `24−p`. Readback needs no change: pass 2 returns the bits in the
order they were sent, so the compare stays byte-for-byte against the
transmitted buffer. Printing should label by physical index, not by send
position.

Every consumer that must change **together** (a partial change leaves the
safe image unsafe on whichever path was missed):

| where | what | change |
|---|---|---|
| mx26 `src/sw/app/Core/AnalogControlChain.cs` | `BuildImage`, `SafeImage`, `ShiftPosition`, `ChannelOrder` use, `MismatchHint`, `BitsAnnotated`, class comment | reverse on transmit (or `ShiftPosition = 24` and `ChannelOrder` reversed); relabel |
| mx26 `src/sw/app/Services/CommandLine.cs` | `chain-safe` / `chain-set` SENT/READ BACK listings ("chain position 0 first") | print physical index and XLR, not send position |
| mx26 `src/sw/app/Core/ChainSetSpec.cs` | grammar indexes channels 1..24 → `BuildImage` | no code change if `BuildImage` is fixed; doc comment example ("ch1" = J15) becomes true |
| mx26 `src/sw/app/Core/AnalogBringUp.cs` | loads `SafeImage()` before AN_EN | none beyond `SafeImage`, but its test must assert J42 muted and INSTR1 off |
| mx26 `src/sw/app/Services/AnalogChainHardware.cs` | SPI transfer | none (transfers the buffer it is given) |
| mx26 `src/sw/app.Tests/AnalogControlChainTests.cs` | position tests (`expectedPosition = IndexOf(ChannelOrder)+1`, SHIFT at byte 0) | rewrite to the transmit-reversed layout; ADD a test that the safe image's LAST transmitted byte is U34's and the FIRST is J42's muted byte |
| mx26 `docs/ref-d24-analog-attach.md`, `docs/d24-analog-xlr-map.md` | chain-order narrative, "lane = dsp.csv C1_IN_nn" | record the measured order; lanes read by the scan tools are strips AFTER the input patch |
| bench Pi `/home/app/chain_bitbang.sh`, `chain_hold.sh`, `chain_probe.sh`, `chain_contention.sh`, `chain_stream.sh`, `chain_stream_pu.sh`, `chain_speed.py` | each hard-codes the SAFE image as "0x00 then 24×0x01 (transmit order)" | becomes "24×0x01 then 0x00" — these scripts are the hand-run restore path and currently leave J42 unmuted + INSTR1 on |
| bench Pi `/home/app/chain_rotation.sh` | rotation patterns, then the safe image | same safe-image fix |

No dsp-repo tool builds a 595 image (`tools/pi/chain.py`, `dsp4_s39_chain.py`,
`dsp4_xpoint_chain.py` are the DSP strip chain, unrelated).

## 2. Fix (ii) — the D24 input patch (recommended form)

**Change the patch preset, not the graph.** `INPUT_TDM` rows describe
(sport, slot) lanes and are shared by D24 and D32 through the ONE DSP4
firmware and ONE address map (`dsp4-architecture-decisions.md`). The
rows are right: slot 7 of the AD1 lane IS `sport 1, slot 7`. What is
product-specific — which console strip a converter slot feeds — already has
its mechanism, INPUT_PATCH, and its value is what is wrong.

Proposed `D24_INPUT_PATCH` (`tools/pi/dsp4_config.py`), packed RX index
i → strip index (strip k = index k−1):

```python
D24_INPUT_PATCH = (
    [3, 15, 2, 14, 13, 1, 12, 0]        # AD0 = U15 (J15-J22) slots 0-7
    + [7, 19, 6, 18, 17, 5, 16, 4]      # AD1 = U39 (J25-J32)
    + [11, 23, 10, 22, 21, 9, 20, 8]    # AD2 = U60 (J35-J42)
    + list(range(24, 32))               # AD3 lane: NET returns, identity
    + list(range(32, 46))               # superset sources, identity
)
```

and the `product-config.md` D24 preset table replaced by the XLR table
below (its "verify before bring-up" NOTE is then discharged).

**The XLR ↔ C1_IN table** (netlist: XLR position 1..8 → AIN 8,7,6,5,3,4,1,2
→ slot 7,6,5,4,2,3,0,1; panel channel per chain index from the hub's facts /
the app's `ChannelOrder`; AD lane per S51-4 measured for U39/U60, U15
inferred — its section is unpowered):

| XLR | ADC | pos | AIN | slot | AD lane | packed RX i | today lands on C1_IN | panel ch = proposed C1_IN | chain idx | today reached by send p (label) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| J15 | U15 | 1 | 8 | 7 | AD0 | 7 | 16 | **01** | 1 | 23 (`ch12`) |
| J16 | U15 | 2 | 7 | 6 | AD0 | 6 | 15 | **13** | 2 | 22 (`ch23`) |
| J17 | U15 | 3 | 6 | 5 | AD0 | 5 | 14 | **02** | 3 | 21 (`ch11`) |
| J18 | U15 | 4 | 5 | 4 | AD0 | 4 | 13 | **14** | 4 | 20 (`ch22`) |
| J19 | U15 | 5 | 3 | 2 | AD0 | 2 | 03 | **03** | 5 | 19 (`ch10`) |
| J20 | U15 | 6 | 4 | 3 | AD0 | 3 | 04 | **15** | 6 | 18 (`ch21`) |
| J21 | U15 | 7 | 1 | 0 | AD0 | 0 | 01 | **04** | 7 | 17 (`ch9`) |
| J22 | U15 | 8 | 2 | 1 | AD0 | 1 | 02 | **16** | 8 | 16 (`ch20`) |
| J25 | U39 | 1 | 8 | 7 | AD1 | 15 | 20 | **05** | 9 | 15 (`ch8`) |
| J26 | U39 | 2 | 7 | 6 | AD1 | 14 | 19 | **17** | 10 | 14 (`ch19`) |
| J27 | U39 | 3 | 6 | 5 | AD1 | 13 | 18 | **06** | 11 | 13 (`ch7`) |
| J28 | U39 | 4 | 5 | 4 | AD1 | 12 | 17 | **18** | 12 | 12 (`ch18`) |
| J29 | U39 | 5 | 3 | 2 | AD1 | 10 | 07 | **07** | 13 | 11 (`ch6`) |
| J30 | U39 | 6 | 4 | 3 | AD1 | 11 | 08 | **19** | 14 | 10 (`ch17`) |
| J31 | U39 | 7 | 1 | 0 | AD1 | 8 | 05 | **08** | 15 | 9 (`ch5`) |
| J32 | U39 | 8 | 2 | 1 | AD1 | 9 | 06 | **20** | 16 | 8 (`ch16`) |
| J35 | U60 | 1 | 8 | 7 | AD2 | 23 | 24 | **09** | 17 | 7 (`ch4`) |
| J36 | U60 | 2 | 7 | 6 | AD2 | 22 | 23 | **21** | 18 | 6 (`ch15`) |
| J37 | U60 | 3 | 6 | 5 | AD2 | 21 | 22 | **10** | 19 | 5 (`ch3`) |
| J38 | U60 | 4 | 5 | 4 | AD2 | 20 | 21 | **22** | 20 | 4 (`ch14`) |
| J39 | U60 | 5 | 3 | 2 | AD2 | 18 | 11 | **11** | 21 | 3 (`ch2`) |
| J40 | U60 | 6 | 4 | 3 | AD2 | 19 | 12 | **23** | 22 | 2 (`ch13`) |
| J41 | U60 | 7 | 1 | 0 | AD2 | 16 | 09 | **12** | 23 | 1 (`ch1`) |
| J42 | U60 | 8 | 2 | 1 | AD2 | 17 | 10 | **24** | 24 | 0 (`SHIFT`) |

"today lands on" is what the S51-4 scan measured (every U39/U60 row matches
the scan's hit for that register). "proposed" = the panel channel, so that
after both fixes `chain-set chN` and strip N name the same XLR.

**Verification when landed** (bench, ~10 min): S52's recipe — oscillator
strip 6 → AUX 1, loop cable in J25 — with the new patch MIC 5 must read on
C1_IN_05; `chain-set ch5:mute=0,gain=0` (after fix i) must open it; and one
register of each converter (J31 → 08, J41 → 12) confirms the pattern. U15's
rows need the MIC 1–4 section powered.

## 3. Alternative the dispatch named: rewriting INPUT_TDM rows (NOT recommended)

The same routing could be written into `dsp.csv` by giving `C1_IN_nn` the
(sport, slot) of its panel channel — `C1_IN_05` = `sport_id=1;slot_start=7`,
and so on per the table — with an identity patch. It is not recommended:
(a) the rows are the D32 lane definition too, so it forks the one graph
(or makes D32 inherit the D24 wiring); (b) `block_io`'s packed RX order is
sorted by (sport, slot), so the generated DMA tables would not move at all
and the change would only relabel which node reads which packed channel —
precisely what INPUT_PATCH does at boot without a contract version;
(c) it is a graph change that has to go through `regenerate-dsp-contract.sh`
and a contract version for what is a host-configuration fact. If
PW prefers it anyway, the table above is the complete row set; the D32
rows stay untouched and D24 needs its own graph, which the architecture
decisions forbid today.
