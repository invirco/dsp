// dsp4_logic_top.v — DSP4 LOGIC CPLD (U3, 5M1270ZT144C4N) top level
//
// Architecture per the rev C schematic (LOGIC sheet, page 2/10):
//  - The inter-chip mix fabric (DSPA O0-7 -> DSPB I0-7) is DIRECT PCB
//    routing between the DSPs and does NOT pass through this CPLD.
//  - LOGIC owns: all 8 BCK/FS pairs to the two DSPs, the DSPA input
//    lines I[0..7], the DSPB output lines O[0..7], the converter lanes
//    AD0-3 / DA0-3, network lanes NI/NO[0..3], the codec pair
//    CDC_O/CDC_I (PLL8 group), MEMS, the Pi PCM port and DSP_CLK.
//
// Slot map (generated/dsp4_slot_map.vh, hash-pinned): DSPA in — I0-I3
// = AD0-2 / NET (AD3 lane is NET-only on D24), I4 = codec return,
// I5 = snake (D32), I6 = Pi PCM (re-framed), I7 = MEMS. DSPB out —
// O0 -> DA0, O1 -> DA3 (DA1 is a spare at Digital J18), O2 -> codec
// (D24) / snake (D32), O3 -> DAC MAIN (no D24 sink by design; lane
// reserved), O4-7 -> NO0-3.
//
// Clock roles (BCKI/FSI index -> DSP pin pairs fixed by the PCB; the
// exact index mapping is confirmed at constraint time):
//   DSPA: in-pairs TDM8 (CG0/CG2), out-pairs TDM16 (CG1/CG3)
//   DSPB: in-pairs TDM16, out-pairs TDM8 (mirrored)
//
// Product variant: `strap_d32` selects the D32 personality (snake on
// I5/O2); D24 keeps the codec on O2. NET return muxing onto I0-I3 is
// enabled per-lane by `net_sel` (future host/strap control; defaults
// to converters, AD3 lane always NET on D24).

`default_nettype none

module dsp4_logic_top (
    input  wire        sysclk,      // 49.152 MHz XO (SYSCLK)
    input  wire        rst_n,

    // Format/config straps (schematic: IC0=TDM16, IC1=TDM8, IC2=I2S,
    // IL0=FS, IL1=WC) — sampled but the DSP4 roles are fixed; kept as
    // inputs for board compatibility / future use.
    input  wire [2:0]  ic_strap,
    input  wire [1:0]  il_strap,
    input  wire        strap_d32,   // product personality

    // DSP clock out (both DSPs' SYS_CLKIN0)
    output wire        dsp_clk,

    // DSP-side clock pairs (index mapping fixed at constraint time)
    output wire [7:0]  bcki,
    output wire [7:0]  fsi,

    // DSPA input data lines (LOGIC -> DSPA I0..I7)
    output wire [7:0]  i_dspa,

    // DSPB output data lines (DSPB O0..O7 -> LOGIC)
    input  wire [7:0]  o_dspb,

    // Converter lanes (FPC via card edge)
    input  wire [3:0]  ad,          // AD0..AD3 (AD3 unused on D24)
    output wire [3:0]  da,          // DA0..DA3 (DA1/DA2 spare on D24)

    // Network lanes (option cards, muxed here)
    input  wire [3:0]  ni,          // NET in 1-8..25-32
    output wire [3:0]  no,          // NET out 1-8..25-32
    input  wire [3:0]  net_sel,     // per-lane: 1 = NET return on I0-3

    // Codec (AK4916 on the Analog PCBA, PLL8 group)
    input  wire        cdc_o,       // codec ADC -> DSPA I4
    output wire        cdc_i,       // DSPB O2 -> codec DAC (D24)

    // D32 snake (X-logic/option pins)
    input  wire        snake_in,    // -> DSPA I5 (D32)
    output wire        snake_out,   // DSPB O2 -> snake (D32)

    // MEMS talkback (ADAU7302 TDM8, slot 5 per strap)
    input  wire        mems,

    // DAC MAIN lane (no D24 sink by design; reserved for D32/future)
    output wire        dac_main,

    // Pi PCM (LOGIC masters)
    output wire        pcm_clk,
    output wire        pcm_fs,
    input  wire        pcm_dout,
    output wire        pcm_din
);

    `include "../generated/dsp4_slot_map.vh"

    // ---- Clocks ----
    wire bck8, bck16, fs8, fs16;
    wire bck8_launch, bck8_sample, bck16_launch, bck16_sample;
    wire [9:0] frame_pos;

    dsp4_clkgen u_clkgen (
        .sysclk       (sysclk),
        .rst_n        (rst_n),
        .bck8         (bck8),
        .bck16        (bck16),
        .fs8          (fs8),
        .fs16         (fs16),
        .bck8_launch  (bck8_launch),
        .bck8_sample  (bck8_sample),
        .bck16_launch (bck16_launch),
        .bck16_sample (bck16_sample),
        .frame_pos    (frame_pos)
    );

    assign dsp_clk = sysclk;   // SYS_CLKIN0 pass-through

    // Clock pair roles (index mapping verified against the PCB nets at
    // constraint time): 0-3 = DSPA {in8, out16, in8, out16},
    // 4-7 = DSPB {in16, out8, in16, out8}.
    assign bcki = {bck8, bck16, bck8, bck16, bck16, bck8, bck16, bck8};
    assign fsi  = {fs8,  fs16,  fs8,  fs16,  fs16,  fs8,  fs16,  fs8};

    // ---- Pi PCM re-framer -> DSPA I6 ----
    wire pcm_tdm;
    dsp4_pcm_reframe u_pcm (
        .sysclk      (sysclk),
        .rst_n       (rst_n),
        .frame_pos   (frame_pos),
        .pcm_clk     (pcm_clk),
        .pcm_fs      (pcm_fs),
        .pcm_dout    (pcm_dout),
        .pcm_din     (pcm_din),
        .bck8_launch (bck8_launch),
        .tdm_out     (pcm_tdm)
    );

    // ---- DSPA input routing (slot map A_I0..A_I7) ----
    assign i_dspa[0] = net_sel[0] ? ni[0] : ad[0];
    assign i_dspa[1] = net_sel[1] ? ni[1] : ad[1];
    assign i_dspa[2] = net_sel[2] ? ni[2] : ad[2];
    // AD3 has no D24 converter: NET return unless a converter exists
    assign i_dspa[3] = net_sel[3] ? ni[3] : ad[3];
    assign i_dspa[4] = cdc_o;
    assign i_dspa[5] = strap_d32 ? snake_in : 1'b0;
    assign i_dspa[6] = pcm_tdm;
    assign i_dspa[7] = mems;

    // ---- DSPB output routing (slot map B_O0..B_O7) ----
    assign da[0] = o_dspb[0];                       // DAC 1-8
    assign da[1] = 1'b0;                            // spare (Digital J18)
    assign da[2] = 1'b0;                            // D32_COMPAT only
    assign da[3] = o_dspb[1];                       // DAC 9-16 (DA_LANE_B_O1)
    assign cdc_i = strap_d32 ? 1'b0 : o_dspb[2];    // D24 codec DAC
    assign snake_out = strap_d32 ? o_dspb[2] : 1'b0;
    assign dac_main = o_dspb[3];                    // reserved lane
    assign no[0] = o_dspb[4];                       // NET 1-8
    assign no[1] = o_dspb[5];
    assign no[2] = o_dspb[6];
    assign no[3] = o_dspb[7];

    // Sanity: generated slot map says B_O1 drives DA lane 3
    initial begin
        if (DA_LANE_B_O1 != 3)
            $display("slot-map mismatch: DA_LANE_B_O1");
    end

    // Straps currently unused (roles fixed for DSP4); referenced to
    // keep the fitter from pruning the pins.
    wire _unused_straps = ^{ic_strap, il_strap, bck8_sample,
                            bck16_sample, bck16_launch, fs16, bck16};

endmodule

`default_nettype wire
