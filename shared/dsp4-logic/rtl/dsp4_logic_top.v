// dsp4_logic_top.v — DSP4 LOGIC CPLD (U3, 5M1270ZT144C4N) top level
//
// Architecture per the rev C schematic (LOGIC sheet, page 2/10):
//  - The inter-chip mix fabric (DSPA O0-7 -> DSPB I0-7) is DIRECT PCB
//    routing between the DSPs and does NOT pass through this CPLD.
//  - LOGIC owns: all 8 BCK/FS pairs (BCKI/FSI 0-7), the DSPA input
//    lines I[0..7], the DSPB output lines O[0..7], converter lanes
//    AD0-3 / DA0-3, network lanes NI/NO[0..3], the codec pair on
//    PLL8_0/PLL8_1, MEMS, the Pi PCM port and DSP_CLK.
//  - There is NO reset input: MAX V registers power up cleared.
//
// Slot map (generated/dsp4_slot_map.vh, hash-pinned): DSPA in — I0-I3
// = AD0-2 / NET (AD3 lane is NET-only on D24), I4 = codec return,
// I5 = snake (D32), I6 = Pi PCM (re-framed), I7 = MEMS. DSPB out —
// O0 -> DA0, O1 -> DA3 (DA1/DA2 spare on D24), O2 -> codec (D24) /
// snake (D32), O3 -> DAC MAIN (no D24 sink by design; parked on an
// X-logic pin), O4-7 -> NO0-3.
//
// Input-lane source selection is FIXED per product (D24: lanes 0-2
// ADC, lane 3 NET; input patching is a DSP-side product-config
// concern). Runtime lane muxing, if ever needed, arrives via the
// provisioned S-MCU SPI interface (ISPI0/ISPI1/ICS_L pins) — not
// implemented. Product personality via the S4 line (S-MCU driven,
// PROVISIONAL until the S-MCU firmware defines it).
//
// UART pass-through pins (SRX/MRX/MHRX/MHTX/STRX/PTRX) and the H1S2
// harness are TODO(uart-passthrough) — routing matrix not yet defined.

`default_nettype none

module dsp4_logic_top (
    input  wire        sysclk,      // pin 88, 49.152 MHz XO

    // Format/config straps (IC0=TDM16, IC1=TDM8, IC2=I2S; IL0=FS,
    // IL1=WC). DSP4 roles are fixed; sampled for future use.
    input  wire [2:0]  ic_strap,    // {IC2, IC1, IC0}
    input  wire [1:0]  il_strap,    // {IL1, IL0}
    input  wire        strap_d32,   // S4: product personality (PROV.)

    output wire        dsp_clk,     // pin 140 -> both DSPs' SYS_CLKIN0

    // DSP-side clock pairs (schematic BCKI/FSI index)
    output wire [7:0]  bcki,
    output wire [7:0]  fsi,

    output wire [7:0]  i_dspa,      // LOGIC -> DSPA I0..I7
    input  wire [7:0]  o_dspb,      // DSPB O0..O7 -> LOGIC

    input  wire [3:0]  ad,          // AD0..AD3 (AD3 unused on D24)
    output wire [3:0]  da,          // DA0..DA3 (DA1/DA2 spare on D24)

    input  wire [3:0]  ni,          // NET in lanes
    output wire [3:0]  no,          // NET out lanes

    input  wire        cdc_o,       // PLL8_0: codec ADC -> DSPA I4
    output wire        cdc_i,       // PLL8_1: DSPB O2 -> codec (D24)

    input  wire        snake_in,    // D32 snake return (X-logic, PROV.)
    output wire        snake_out,   // D32 snake out    (X-logic, PROV.)
    output wire        dac_main,    // B_O3 lane, parked (X-logic, PROV.)

    input  wire        mems,        // ADAU7302 TDM8 (slot 5)

    // Pi PCM (LOGIC masters; roles per hardware-map: PCM0=CLK,
    // PCM1=DOUT (Pi->LOGIC), PCM2=DIN (LOGIC->Pi), PCM3=FS)
    output wire        pcm_clk,
    output wire        pcm_fs,
    input  wire        pcm_dout,
    output wire        pcm_din,

    output wire        blink_led,   // heartbeat -> LD1

    // Bring-up test points, pins 13/12/8/7 -> J1/J2 P17-P20 -> D24
    // Digital J15 (a DNP DIL254-10: pin 1/2 = +3V3, odd 3-9 = GND, even
    // 4-10 = TEST1..TEST4, so every signal has a ground beside it).
    // Nothing else on either board drives these nets.
    output wire [3:0]  test         // {TEST4, TEST3, TEST2, TEST1}
);

    `include "../generated/dsp4_slot_map.vh"

    // ---- Clocks ----
    wire bck8, bck16, fs8, fs16;
    wire bck8_launch, bck8_sample, bck16_launch, bck16_sample;
    wire [9:0] frame_pos;

    dsp4_clkgen u_clkgen (
        .sysclk       (sysclk),
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

    // Clock pair roles. BCKI/FSI 0-3 serve DSPA, 4-7 serve DSPB; per
    // DSP the four pairs are {DAI0-in, DAI0-out, DAI1-in, DAI1-out}.
    // DSPA: in = TDM8 (ADC/superset), out = TDM16 (mix fabric).
    // DSPB: in = TDM16 (mix fabric), out = TDM8 (DAC/codec/NET).
    // Index<->DSP-pin pairing is fixed by the PCB; verify the
    // in/out order of each pair at bring-up (swap here if needed).
    assign bcki = {bck8, bck16, bck8, bck16,    // 7..4: DSPB
                   bck16, bck8, bck16, bck8};   // 3..0: DSPA
    assign fsi  = {fs8, fs16, fs8, fs16,
                   fs16, fs8, fs16, fs8};

    // ---- Pi PCM re-framer -> DSPA I6 ----
    wire pcm_tdm;
    dsp4_pcm_reframe u_pcm (
        .sysclk      (sysclk),
        .frame_pos   (frame_pos),
        .pcm_clk     (pcm_clk),
        .pcm_fs      (pcm_fs),
        .pcm_dout    (pcm_dout),
        .pcm_din     (pcm_din),
        .bck8_launch (bck8_launch),
        .tdm_out     (pcm_tdm)
    );

    // ---- Input-lane sources (fixed per product) ----
    // D24: lanes 0-2 = ADC8s, lane 3 = NET (no AD3 converter).
    // D32: personality TBD with the D32 board work.
    wire [3:0] net_sel = strap_d32 ? 4'b1000 : 4'b1000;

    assign i_dspa[0] = net_sel[0] ? ni[0] : ad[0];
    assign i_dspa[1] = net_sel[1] ? ni[1] : ad[1];
    assign i_dspa[2] = net_sel[2] ? ni[2] : ad[2];
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
    assign dac_main = o_dspb[3];                    // parked lane
    assign no[0] = o_dspb[4];                       // NET 1-8
    assign no[1] = o_dspb[5];
    assign no[2] = o_dspb[6];
    assign no[3] = o_dspb[7];

    // ---- Bring-up test points ----
    // Existing clkgen nets only, so LE count is unchanged (156); the
    // cost is 4 pins plus the extra output loading on these nets, which
    // moved 1270Z Fmax 68.24 -> 67.06 MHz. Keep it that way: D8's STA
    // gate is the guard, and on the rev-D 570Z part the margin is both
    // thinner and noisy (50.67 MHz measured 2026-08-07, 55.88 MHz on
    // 2026-08-11 with these pins added — that spread is fitter placement
    // variance, not a real improvement, so trust the gate, not a
    // remembered percentage).
    // Together these prove clock generation and frame alignment on a
    // scope without a DSP image loaded.
    assign test[0] = fs8;             // TEST1: 48 kHz frame sync, TDM8
    assign test[1] = bck8;            // TEST2: 12.288 MHz bit clock
    assign test[2] = fs16;            // TEST3: 48 kHz frame sync, TDM16
    assign test[3] = frame_pos[9];    // TEST4: 24 kHz square, frame phase

    // ---- Heartbeat (~1.4 Hz from a 25-bit divider) ----
    reg [24:0] hb;
    always @(posedge sysclk)
        hb <= hb + 25'd1;
    assign blink_led = hb[24];

    // Sanity: generated slot map says B_O1 drives DA lane 3
    initial begin
        if (DA_LANE_B_O1 != 3)
            $display("slot-map mismatch: DA_LANE_B_O1");
    end

    // Straps/strobes currently unused; keep referenced.
    wire _unused = ^{ic_strap, il_strap, bck8_sample,
                     bck16_sample, bck16_launch, fs16, bck16};

endmodule

`default_nettype wire
