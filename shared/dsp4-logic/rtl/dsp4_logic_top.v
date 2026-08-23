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

    // ---- DSP clock: SYS_CLKIN0 = sysclk / 2 = 24.576 MHz ----
    // The ADSP-2156x CLKIN range is fCKIN = 20-30 MHz (datasheet Rev. A
    // Table 23, crystal and external clock alike). The raw 49.152 MHz XO
    // is OUT OF RANGE: at reset the CGU defaults to MSEL = 60, DF = 0, so
    // PLLCLK would be 49.152 x 60 = 2.95 GHz and the PLL cannot lock — a
    // part in that state never runs its boot ROM. Divided by 2 the same
    // default gives 24.576 x 60 = 1.47 GHz, in range, and the clock stays
    // audio-rational (512 x 48 kHz).
    //
    // A single toggle flop, registered straight to the pin: exact 50 %
    // duty (the datasheet asks 45-55 %) and glitch-free by construction.
    // U3 has no reset — MAX V macrocells power up cleared — so no reset
    // term here, matching the rest of this design.
    // `preserve` keeps this its own macrocell: without it the synthesiser
    // spots that hb[0] toggles identically and merges the two, putting the
    // DSPs' only clock on an LE inside the heartbeat counter's carry chain.
    // Functionally the same, but this is the most critical net on the card
    // — 1 LE buys it a dedicated flop and a direct route to pin 140.
    reg dsp_clk_q /* synthesis preserve */;
    always @(posedge sysclk)
        dsp_clk_q <= ~dsp_clk_q;
    assign dsp_clk = dsp_clk_q;

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
    // DSP4_PI_TDM8 runs the CM4 link at 4x rate so it carries eight
    // channels each way instead of two -- see dsp4_pcm_reframe.v. It is a
    // build-time evaluation switch, not a shipping default, until the
    // eight-channel path is proven on hardware.
    // The two evaluation switches are independent: PI_TDM8 sets the 4x
    // frame rate, PI_SELFTEST loops the Pi's playback back to its capture
    // inside LOGIC. Stereo self-test (no TDM8) is what the differential
    // latency measurement needs, so they must combine freely.
`ifdef DSP4_PI_SELFTEST
 `ifdef DSP4_PI_TDM8
    dsp4_pcm_reframe #(.PI_TDM8(1), .PI_SELFTEST(1)) u_pcm (
 `else
    dsp4_pcm_reframe #(.PI_SELFTEST(1), .CAP_SLOT_L(0), .CAP_SLOT_R(1)) u_pcm (
 `endif
`elsif DSP4_PI_MAINCAP
    // Latency measurement through the DSP: capture B_O3 slot 0, which is
    // C2_MAIN_ST_OUT and the only slot the node graph drives today. The
    // product allocation stays slots 2/3.
    dsp4_pcm_reframe #(.CAP_SLOT_L(0), .CAP_SLOT_R(1)) u_pcm (
`elsif DSP4_PI_TDM8
    dsp4_pcm_reframe #(.PI_TDM8(1)) u_pcm (
`else
    dsp4_pcm_reframe u_pcm (
`endif
        .sysclk      (sysclk),
        .frame_pos   (frame_pos),
        .pcm_clk     (pcm_clk),
        .pcm_fs      (pcm_fs),
        .pcm_dout    (pcm_dout),
        .pcm_din     (pcm_din),
        .bck8_launch (bck8_launch),
        .bck8_sample (bck8_sample),
        // Capture source for the Pi. In the loopback bring-up build this
        // is a DSPB output lane, so the Pi can record what DSPB actually
        // transmits; the shipping build ties pcm_din off inside the
        // reframer and this input is unused.
        // Capture the MAIN stereo output lane. C2_MAIN_ST_OUT writes
        // SPORT3 slot 0 on chip 2, which is o_dspb[3] (the CPLD's
        // dac_main). That is where a Pi -> DSP -> Pi pass-through lands:
        // XIN_PI -> XS_XFER -> inter-chip -> C2_XR_PI -> C2_PI_IN ->
        // MIX_MAIN -> MAIN_FDR -> MAIN_DLY -> MAIN_ST_OUT. Lane 0 slots
        // 0/1 are AUX_OUT_01/02 and carry nothing in a pass-through.
`ifdef DSP4_PI_TDM8
        // EVALUATION: lane 0 is the only DSPB output the DSP4_PATTERN
        // firmware drives on ALL EIGHT slots (c2_tx cs_mask 0x00FF), so
        // it is the one that can prove eight distinct channels arriving.
        // The product capture stays on o_dspb[3] below.
        .tdm_in      (o_dspb[0]),
`else
        .tdm_in      (o_dspb[3]),
`endif
        .tdm_out     (pcm_tdm)
    );

    // ---- Input-lane sources (fixed per product) ----
    // D24: lanes 0-2 = ADC8s, lane 3 = NET (no AD3 converter).
    // D32: personality TBD with the D32 board work.
    wire [3:0] net_sel = strap_d32 ? 4'b1000 : 4'b1000;

`ifdef DSP4_LOOPBACK
    // ---- NON-SHIPPING BRING-UP BUILD: fabric feedback loop ----
    //
    // Every DSPA input lane is fed from the matching DSPB output lane,
    // so DSPB can emit a known per-lane pattern and DSPA can check it
    // without a single converter, analog board or scope. That closes
    // BCKI/FSI pair order, sample edge / MFD, within-TDM8 slot order and
    // the NET crossed-index question by measurement instead of by
    // assumption.
    //
    // NOTHING else changes: same clkgen, same reframer, same DA/NO
    // output routing, same pinout. This define is never set for a
    // shipping build, and build.sh labels the artifact
    // dsp4_logic_loopback.<hash> so the two can never be confused.
    // Lane 6 is the EXCEPTION and it has to be: it carries the Pi's
    // playback (pcm_tdm, from the reframer). Feeding it from o_dspb too
    // would tie off the only path the Pi has INTO the DSP, and rung 2 is
    // a Pi -> DSPA -> fabric -> DSPB -> Pi round trip. Everything else
    // still comes from the matching DSPB output lane.
    assign i_dspa[5:0] = o_dspb[5:0];
    assign i_dspa[6]   = pcm_tdm;
    assign i_dspa[7]   = o_dspb[7];
`else
    assign i_dspa[0] = net_sel[0] ? ni[0] : ad[0];
    assign i_dspa[1] = net_sel[1] ? ni[1] : ad[1];
    assign i_dspa[2] = net_sel[2] ? ni[2] : ad[2];
    assign i_dspa[3] = net_sel[3] ? ni[3] : ad[3];
    assign i_dspa[4] = cdc_o;
    assign i_dspa[5] = strap_d32 ? snake_in : 1'b0;
    assign i_dspa[6] = pcm_tdm;
    assign i_dspa[7] = mems;
`endif

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
