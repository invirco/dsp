# DSP Block Diagram (partial)

> Generated from `mx_master.csv` by `gen_diagram.py`.  
> Rows with `Save2Mix=false` (UI-only / sys control) are excluded.  
> Each strip shows the DSP processing stages in signal-flow order
> derived from the `StripOrder` column.

## Channel Strip → Bus Overview

```mermaid
flowchart LR

    %% ── Sources ──────────────────────────────────────────────────
    MIC(["Mic / Line\nInput ×32"])
    DIG(["Digital / USB\nInput"])

    %% ── Chan ─────────────────────────────────────────────
    subgraph Chan["Channel Strip
(×32)"]
        Chan_ChanInput["Input\n(Gain/HPF/Pol/Insert)"]
        Chan_Chan_Eq["EQ\n(HPF + 4-band PEQ)"]
        Chan_ChanGate["Gate"]
        Chan_ChanComp["Compressor"]
        Chan_ChanDelay["Delay"]
        Chan_Chan_Rtg["Fader / Pan\n& Routing"]
        Chan_ChanInput --> Chan_Chan_Eq
        Chan_Chan_Eq --> Chan_ChanGate
        Chan_ChanGate --> Chan_ChanComp
        Chan_ChanComp --> Chan_ChanDelay
        Chan_ChanDelay --> Chan_Chan_Rtg
    end

    %% ── Grp ─────────────────────────────────────────────
    subgraph Grp["Group Bus
(×4)"]
        Grp_GrpEq["EQ\n(HPF + 4-band PEQ)"]
        Grp_GrpGate["Gate"]
        Grp_GrpComp["Compressor"]
        Grp_GrpRtg["Fader"]
        Grp_GrpEq --> Grp_GrpGate
        Grp_GrpGate --> Grp_GrpComp
        Grp_GrpComp --> Grp_GrpRtg
    end

    %% ── Fx ─────────────────────────────────────────────
    subgraph Fx["FX Engine
(×6)"]
        Fx_FxCtrl["FX Engine\n(Echo/Reverb/Chorus…)"]
    end

    %% ── Aux ─────────────────────────────────────────────
    subgraph Aux["Aux Bus
(×12)"]
        Aux_AuxRtg["Level / Pan\n& Routing"]
        Aux_AuxEq["EQ\n(HPF + GEQ + PEQ)"]
        Aux_AuxLimiter["Limiter"]
        Aux_AuxAntiFb["Anti-Feedback\n(6 notch filters)"]
        Aux_AuxDelay["Delay"]
        Aux_AuxRtg --> Aux_AuxEq
        Aux_AuxEq --> Aux_AuxLimiter
        Aux_AuxLimiter --> Aux_AuxAntiFb
        Aux_AuxAntiFb --> Aux_AuxDelay
    end

    %% ── Main ─────────────────────────────────────────────
    subgraph Main["Main L/R"]
        Main_MainEq["GEQ + 4-band PEQ"]
        Main_MainComp["Compressor"]
        Main_MainLimiter["Limiter"]
        Main_MainCrossover["Crossover"]
        Main_MainPeq["Graphic EQ (PEQ)"]
        Main_MainRtg["Level / Routing"]
        Main_MainEq --> Main_MainComp
        Main_MainComp --> Main_MainLimiter
        Main_MainLimiter --> Main_MainCrossover
        Main_MainCrossover --> Main_MainPeq
        Main_MainPeq --> Main_MainRtg
    end

    %% ── Sub ─────────────────────────────────────────────
    subgraph Sub["Sub"]
        Sub_SubEq["EQ\n(HPF + 4-band PEQ)"]
        Sub_SubComp["Compressor"]
        Sub_SubLimiter["Limiter"]
        Sub_SubRtg["Level"]
        Sub_SubEq --> Sub_SubComp
        Sub_SubComp --> Sub_SubLimiter
        Sub_SubLimiter --> Sub_SubRtg
    end

    %% ── Mon ─────────────────────────────────────────────
    subgraph Mon["Monitor"]
        Mon_MonCtrl["Level / Source\n& Delay"]
    end

    %% ── Sinks ──────────────────────────────────────────────────
    MAIN_OUT(["Main L/R\nOutput"])
    SUB_OUT(["Sub\nOutput"])
    AUX_OUT(["Aux Outputs\n×12"])
    MON_OUT(["Monitor\nOutput"])
    FX_RET(["FX Return\n×6"])

    %% ── Routing ─────────────────────────────────────────────────
    MIC --> Chan_ChanInput
    DIG -.-> Chan_ChanInput
    Chan_Chan_Rtg -->|Grp send| Grp_GrpEq
    Chan_Chan_Rtg -->|Aux send| Aux_AuxRtg
    Chan_Chan_Rtg -->|FX send|  Fx_FxCtrl
    Chan_Chan_Rtg -.->|Main assign| MAIN_OUT
    Fx_FxCtrl --> FX_RET
    FX_RET --> MAIN_OUT
    Grp_GrpRtg -->|Grp→Main| MAIN_OUT
    Grp_GrpRtg -.->|Grp→Sub| Sub_SubEq
    Aux_AuxDelay --> AUX_OUT
    Main_MainRtg --> MAIN_OUT
    Sub_SubRtg --> SUB_OUT
    MAIN_OUT -.->|Mon src| Mon_MonCtrl
    Mon_MonCtrl --> MON_OUT
```

## Strip Types Decoded

| StripType | Count | Processing Chain |
|-----------|-------|------------------|
| **Chan** | ×32 | ChanInput → Chan_Eq → ChanGate → ChanComp → ChanDelay → Chan_Rtg |
| **Grp** | ×4 | GrpEq → GrpGate → GrpComp → GrpRtg |
| **Fx** | ×6 | FxCtrl |
| **Aux** | ×12 | AuxRtg → AuxEq → AuxLimiter → AuxAntiFb → AuxDelay |
| **Main** | ×1 | MainEq → MainComp → MainLimiter → MainCrossover → MainPeq → MainRtg |
| **Sub** | ×1 | SubEq → SubComp → SubLimiter → SubRtg |
| **Mon** | ×1 | MonCtrl |
