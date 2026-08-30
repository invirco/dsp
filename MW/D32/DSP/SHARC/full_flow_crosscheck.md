# D32 SHARC Full Flow Cross-Check Diagram

This layout mirrors the older reference style from [../D24/DSP/SHARC/dsp_diagram.png](../../D24/DSP/SHARC/dsp_diagram.png) while using the current D32 graph structure from [dsp.csv](dsp.csv).

## Full printable view

```mermaid
flowchart TB
    PI([Pi / Matrix App])
    DCA([DCA masters ×8<br/>HOST-SIDE since 2026-08-30:<br/>folded into the fader target,<br/>no DSP address at all])
    DCA -. effective fader = fader dB + DCA dB .-> PI
    MCU([H1S1 MCU<br/>STM32U575<br/>SPI control])
    PI -->|Serial| MCU

    subgraph CHIP2[CHIP 2 — Output DSP]
      direction LR
      RX([INTERCHIP_RECV ×25<br/>Main L/R, Aux×12, Grp×4, Sub, FX×6])
      BUSMAIN([Main Mix L/R<br/>MIX_BUS ×2])
      AUX([Aux Strips ×12<br/>Fader → EQ → GEQ → AntiFB → Lim → Delay → Out])
      GRP([Group Strips ×4<br/>Fader → EQ → Gate → Comp → Main feed])
      SUB([Sub Chain<br/>Fader → EQ → Comp → Lim → Delay → Out])
      FX([FX Engines ×6<br/>Recv → Engine → Return Fader])
      MAIN([Main Chain<br/>Master Fader → 28b GEQ → Comp → Lim → Delay → Xover])
      OUT([Main Outputs ×4<br/>Per-out EQ → Comp → Lim → OUTPUT_TDM])
      MON([Monitor / Phones<br/>Source select → L/R level → Delay → Out])
      USB([USB / BT Inputs ×2])
      M2([Meters<br/>Aux / Main / Group / Sub / FX taps])

      RX --> AUX
      RX --> BUSMAIN
      RX --> GRP
      RX --> SUB
      RX --> FX
      GRP --> BUSMAIN
      FX --> BUSMAIN
      USB --> BUSMAIN
      BUSMAIN --> MAIN --> OUT
      BUSMAIN --> MON
      AUX -. metering .-> M2
      OUT -. metering .-> M2
      SUB -. metering .-> M2
      FX -. metering .-> M2
      GRP -. metering .-> M2
    end

    subgraph CHIP1[CHIP 1 — Input DSP]
      direction LR
      IN([INPUT_TDM ×32])
      G([GAIN ×32])
      FLT([HPF / LPF ×32])
      EQ([EQ_BIQUAD ×32<br/>4-band PEQ])
      GT([GATE ×32<br/>self-key default<br/>SC HPF / LPF / Q])
      CP([COMPRESSOR ×32<br/>self-key default<br/>parallel / knee / type])
      TS([TUBE_SAT ×32])
      DLY([DELAY ×32<br/>20 ms local + 250 ms max])
      FD([FADER_PAN ×32<br/>pan / mute])
      RT([ROUTING ×32<br/>Main / Sub / Grp switching<br/>Aux / FX pickoff select<br/>PreEQ / PostEQ / PreFdr / PostFdr])
      TX([INTERCHIP_SEND ×25])
      TALK([TALKBACK ×2])
      NOISE([NOISE_GEN ×1])
      TTRIM([Tap A<br/>post trim / pre-EQ])
      TEQ([Tap B<br/>post EQ])
      TPRE([Tap C<br/>pre-fader])
      TPOST([Tap D<br/>post-fader])
      M1([Meters ×32<br/>post trim / post fader / gate GR / comp GR])

      IN --> G --> FLT --> EQ --> GT --> CP --> TS --> DLY --> FD --> RT --> TX
      TALK --> RT
      NOISE --> RT
      G -. tap .-> TTRIM
      EQ -. tap .-> TEQ
      DLY -. tap .-> TPRE
      FD -. tap .-> TPOST
      TTRIM -. selectable send source .-> RT
      TEQ -. selectable send source .-> RT
      TPRE -. selectable send source .-> RT
      TPOST -. selectable send source .-> RT
      G -. tap .-> M1
      FD -. tap .-> M1
      GT -. GR .-> M1
      CP -. GR .-> M1
    end

    MCU -. SPI .-> IN
    MCU -. SPI / LP0 .-> BUSMAIN
    TX == TDM32 ==> RX

    classDef io fill:#4CAF50,stroke:#222,color:#fff;
    classDef gain fill:#2196F3,stroke:#222,color:#fff;
    classDef eq fill:#9C27B0,stroke:#222,color:#fff;
    classDef dyn fill:#FF9800,stroke:#222,color:#fff;
    classDef lim fill:#E91E63,stroke:#222,color:#fff;
    classDef mix fill:#009688,stroke:#222,color:#fff;
    classDef chip fill:#FFC107,stroke:#222,color:#111;
    classDef out fill:#F44336,stroke:#222,color:#fff;
    classDef ctrl fill:#455A64,stroke:#222,color:#fff;

    class IN,TALK,NOISE io;
    class G gain;
    class FLT,EQ eq;
    class GT,CP,FX dyn;
    class MAIN,GRP,AUX,BUSMAIN,MON,SUB,M1,M2 mix;
    class OUT lim;
    class TX,RX chip;
    class PI,MCU,DCA ctrl;
```