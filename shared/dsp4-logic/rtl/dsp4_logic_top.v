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

`ifdef DSP4_S34_SLOT3
    // S34 COST BRANCH (not shipping): option slot 3's eight lanes, which
    // the rev C copper already routes to U3 as the PLL3/PLL4 groups.
    // PLL3 (U3 101-104) = digital NO8..NO11 = the CARD's outputs, so they
    // are LOGIC inputs; PLL4 (U3 105-108) = digital NI8..NI11 = the
    // card's inputs, so LOGIC outputs. Index order on slots 2 and 3 is a
    // pairwise _0/_1 <-> _2/_3 swap, NOT slot 1's full reversal; the
    // qsf's location assignments carry that, not this port list.
    input  wire [3:0]  slot3_in,
    output wire [3:0]  slot3_out,
`endif
`ifdef DSP4_S34_SLOT2
    // As above for option slot 2: PLL5 (U3 109-112) are the card's
    // outputs (LOGIC inputs), PLL6 (U3 113/114/117/118) the card's
    // inputs (LOGIC outputs). NOTE what this displaces: the shipping qsf
    // parks snake_in/snake_out/dac_main on pins 109/110/111, which ARE
    // three of these slot-2 lanes -- see the S34 write-up.
    input  wire [3:0]  slot2_in,
    output wire [3:0]  slot2_out,
`endif
`ifdef DSP4_S34_NETSEL
    // S34 COST BRANCH: the provisioned S-MCU SPI path (U3 60/61/62).
    // 60/61 are the SHARED SPI0/SPI1 bus (Pi SCK/MOSI, DSP boot, mic-gain
    // shift chain); 62 (CS_L) is private to U7. Listen only: this design
    // never drives 60/61, and there is no MISO to answer on.
    input  wire        ispi_sck,
    input  wire        ispi_mosi,
    input  wire        ics_l,
`endif

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
    // The broadcast copy of the Pi stream (all eight TDM8 slots), used
    // only by the DRIVE_ALL capacity-stimulus build below.
    wire pcm_drive;
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
`elsif DSP4_S34_PACK
    // S34 COST BRANCH: the Pi's two channels move to slots 6/7 of the
    // packed lane, and its RETURN comes off slots 6/7 of the packed
    // DSPB lane (o_dspb[2]) instead of B_O3.
    dsp4_pcm_reframe #(.PI_OUT_SLOT_L(6), .PI_OUT_SLOT_R(7),
                       .CAP_SLOT_L(6), .CAP_SLOT_R(7)) u_pcm (
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
`ifdef DSP4_S34_PACK
        .tdm_in      (o_dspb[2]),
`elsif DSP4_PI_TDM8
        // EVALUATION: lane 0 is the only DSPB output the DSP4_PATTERN
        // firmware drives on ALL EIGHT slots (c2_tx cs_mask 0x00FF), so
        // it is the one that can prove eight distinct channels arriving.
        // The product capture stays on o_dspb[3] below.
        .tdm_in      (o_dspb[0]),
`else
        .tdm_in      (o_dspb[3]),
`endif
        .tdm_out     (pcm_tdm),
        .tdm_drive   (pcm_drive)
    );

    // ---- Input-lane sources (fixed per product) ----
    // D24: lanes 0-2 = ADC8s, lane 3 = NET (no AD3 converter).
    // D32: personality TBD with the D32 board work.
`ifdef DSP4_S34_NETSEL
    // ---- S34 COST BRANCH: runtime net_sel over the S-MCU SPI path ----
    //
    // Listen-only 16-bit slave on the SHARED SPI0/SPI1 bus, framed by
    // CS_L (the one pin of the three that is private to U7). Frame,
    // MSB first: {8'hA5, sel[3:0], ~sel[3:0]}. The inverted copy is the
    // whole integrity story -- U3 has no MISO to the S-MCU, so nothing
    // can be read back, and a frame that does not carry a complement
    // is dropped rather than applied.
    //
    // Two-flop synchronisers because SCK is asynchronous to sysclk and
    // has TWO masters with opposite idle polarity (the Pi at mode 0/1,
    // the S-MCU at CPOL=1); sampling MOSI on the SCK rising edge is
    // correct for both as long as CS_L frames the transaction.
    reg [1:0] sck_s, mosi_s, cs_s;
    always @(posedge sysclk) begin
        sck_s  <= {sck_s[0],  ispi_sck};
        mosi_s <= {mosi_s[0], ispi_mosi};
        cs_s   <= {cs_s[0],   ics_l};
    end
    reg sck_d;
    always @(posedge sysclk)
        sck_d <= sck_s[1];
    wire sck_rise = sck_s[1] & ~sck_d;
    wire cs_active = ~cs_s[1];

    reg [15:0] spi_sh;
    reg [4:0]  spi_cnt;
    reg        cs_d;
    always @(posedge sysclk) begin
        cs_d <= cs_s[1];
        if (!cs_active) begin
            spi_cnt <= 5'd0;
        end else if (sck_rise) begin
            spi_sh  <= {spi_sh[14:0], mosi_s[1]};
            spi_cnt <= spi_cnt + 5'd1;
        end
    end

    // Applied on the CS_L RISING edge, and then only at a frame
    // boundary: a select that moves mid-frame splits one TDM word
    // across two sources. Held here, released by fs8's frame start, so
    // the DSP gets one whole frame of the old lane and one whole frame
    // of the new one -- a step in the audio, not a torn sample.
    wire spi_valid = (spi_cnt == 5'd16) && (spi_sh[15:8] == 8'hA5)
                     && (spi_sh[7:4] == ~spi_sh[3:0]);
    reg [3:0] net_sel_pend;
    reg       net_sel_arm;
    reg [3:0] net_sel_q;
    always @(posedge sysclk) begin
        if (cs_s[1] && !cs_d && spi_valid) begin
            net_sel_pend <= spi_sh[7:4];
            net_sel_arm  <= 1'b1;
        end else if (net_sel_arm && bck8_launch && (frame_pos[9:2] == 8'd255)) begin
            net_sel_q   <= net_sel_pend;
            net_sel_arm <= 1'b0;
        end
    end
    // U3 has no reset and MAX V registers power up CLEARED, so a raw
    // register would come up 4'b0000 = every lane on the ADCs -- and on
    // D24 lane 3 has no ADC at all (no AD3 converter), so the NET inputs
    // would be dead until the S-MCU spoke. The register therefore holds
    // a DELTA against the product's static map: cleared = the shipping
    // personality, exactly as today, and the S-MCU only ever changes it.
    wire [3:0] net_sel_default = strap_d32 ? 4'b1000 : 4'b1000;
    wire [3:0] net_sel = net_sel_q ^ net_sel_default;
`else
    wire [3:0] net_sel = strap_d32 ? 4'b1000 : 4'b1000;
`endif

`ifdef DSP4_DRIVE_ALL
    // ---- NON-SHIPPING MEASUREMENT BUILD: the driven-capacity stimulus ----
    //
    // Every DSPA input lane carries the Pi's playback, broadcast across
    // all eight TDM8 slots, so a single stereo stream played by the CM4
    // puts full-scale signal on all 46 of chip 1's input kernels at once.
    //
    // WHY IT IS IN THE CPLD AND NOT IN THE FIRMWARE. Until S19 the only
    // way to measure the graph with its dynamics engaged was
    // DSP4_PROFILE_SIGNAL, which synthesises a square INSIDE the 46 input
    // kernels. The part then pays for its own stimulus, so every driven
    // figure has to be netted against a cost nobody could measure
    // independently -- and S18 mis-attributed chip 1's whole 113 % to that
    // synthesis on exactly that reasoning. Driven from here the DSP
    // executes not one instruction for the stimulus, and the 113 % turned
    // out to be the product. What is left is measured per session on a
    // graph with the dynamics switched off and stated beside the number
    // (S19: 0.28 points on chip 1, 0.53 on chip 2).
    //
    // It is also RUNTIME-SWITCHED, which is the point of using the Pi's
    // stream rather than a counter in the CPLD: the silent row and the
    // driven row are taken on ONE bitstream and one boot, and the only
    // difference between them is whether `aplay` is running.
    //
    // NOTHING else changes: same clkgen, same reframer, same DSPB output
    // routing, same pinout. Never set for a shipping build; build.sh
    // labels the artifact dsp4_logic_driveall.<hash>.
    assign i_dspa = {8{pcm_drive}};
`elsif DSP4_LOOPBACK
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

    // ---- S34 COST BRANCH: a second net card on option slot 2 or 3 ----
    // Two of the card's four output lanes reach DSPA. Which lanes are
    // free depends on whether the pack is also built: without it the
    // TDM map's proposed columns use A_I5 and A_I7 (I5 is the retired
    // D32 snake lane, I7 is MEMS); with it the pack has already freed
    // A_I6 and A_I7, so the card takes those and MEMS keeps its place
    // inside the packed lane.
`ifdef DSP4_S34_SLOT3
    wire net2_a = slot3_in[0];
    wire net2_b = slot3_in[1];
    `define DSP4_S34_HAVE_NET2
`elsif DSP4_S34_SLOT2
    wire net2_a = slot2_in[0];
    wire net2_b = slot2_in[1];
    `define DSP4_S34_HAVE_NET2
`endif

`ifdef DSP4_S34_PACK
    // ---- S34 COST BRANCH: codec + MEMS + Pi on ONE TDM8 lane ----
    //
    // Slot budget of the packed lane (A_I4): 0-3 codec (CODEC_RET_1..4),
    // 4 spare, 5 MEMS (the ADAU7302's own strapped slot, so it needs no
    // re-timing), 6-7 Pi L/R (the re-framer replays them there). Every
    // source keeps its OWN slot index where it has one, which is what
    // makes this a bit-level mux and not a 32-bit store-and-forward: a
    // source whose destination slot came EARLIER than its own would need
    // a full frame of delay, 32 flops a lane.
    //
    // The select is registered on the BCK8 FALLING edge on purpose. The
    // raw slot index changes at frame_pos multiples of 128, which is
    // exactly a BCK8 RISING edge -- the instant the DSP samples. Moving
    // it to the falling edge puts the mux transition half a bit period
    // (about 40 ns at 12.288 MHz) away from both the codec's launch and
    // the DSP's sample.
    reg [2:0] pack_slot;
    always @(posedge sysclk)
        if (bck8_launch)
            pack_slot <= frame_pos[9:7];
    wire pack_cdc  = ~pack_slot[2];             // slots 0-3
    wire pack_mems = (pack_slot == 3'd5);

    assign i_dspa[4] = pack_cdc ? cdc_o : (pack_mems ? mems : pcm_tdm);
    assign i_dspa[5] = strap_d32 ? snake_in : 1'b0;
 `ifdef DSP4_S34_HAVE_NET2
    assign i_dspa[6] = strap_d32 ? 1'b0 : net2_a;   // FREED by the pack
    assign i_dspa[7] = strap_d32 ? 1'b0 : net2_b;   // FREED by the pack
 `else
    assign i_dspa[6] = 1'b0;                        // FREED by the pack
    assign i_dspa[7] = 1'b0;                        // FREED by the pack
 `endif
`else
    assign i_dspa[4] = cdc_o;
    assign i_dspa[6] = pcm_tdm;
 `ifdef DSP4_S34_HAVE_NET2
    assign i_dspa[5] = strap_d32 ? snake_in : net2_a;
    assign i_dspa[7] = strap_d32 ? mems     : net2_b;
 `else
    assign i_dspa[5] = strap_d32 ? snake_in : 1'b0;
    assign i_dspa[7] = mems;
 `endif
`endif
`endif

    // ---- DSPB output routing (slot map B_O0..B_O7) ----
    assign da[0] = o_dspb[0];                       // DAC 1-8
    assign da[1] = 1'b0;                            // spare (Digital J18)
    assign da[2] = 1'b0;                            // D32_COMPAT only
    assign da[3] = o_dspb[1];                       // DAC 9-16 (DA_LANE_B_O1)
`ifdef DSP4_S34_PACK
    // ---- S34 COST BRANCH: the return half of the pack ----
    // ONE DSPB lane (B_O2) carries codec out in slots 0-3 and the Pi's
    // return in slots 6-7, which frees B_O3. The codec must not be
    // handed the Pi's words in the slots beyond its own four, so the
    // lane is GATED to slots 0-3 on the way to CDC_I -- one AND, and it
    // is the difference between packing and cross-talk.
    //
    // The window here counts LAUNCH periods: DSPB drives, at period P,
    // the bit its receiver samples at P+1 (MFD=1), the same convention
    // dsp4_pcm_reframe's `out_period` uses.
    reg [2:0] pack_out_slot;
    wire [7:0] pack_out_period = frame_pos[9:2] + 8'd1;
    always @(posedge sysclk)
        if (bck8_launch)
            pack_out_slot <= pack_out_period[7:5];
    assign cdc_i = (strap_d32 || pack_out_slot[2]) ? 1'b0 : o_dspb[2];
    assign dac_main = 1'b0;                         // FREED by the pack
`else
    assign cdc_i = strap_d32 ? 1'b0 : o_dspb[2];    // D24 codec DAC
    assign dac_main = o_dspb[3];                    // parked lane
`endif
    assign snake_out = strap_d32 ? o_dspb[2] : 1'b0;
    assign no[0] = o_dspb[4];                       // NET 1-8
    assign no[1] = o_dspb[5];
    assign no[2] = o_dspb[6];
    assign no[3] = o_dspb[7];

`ifdef DSP4_S34_SLOT3
    // Second net card, out: the TDM map's proposed columns give it
    // B_O3, B_O6 and B_O7. The fourth card lane has no DSP lane behind
    // it and is held low rather than left to float.
    assign slot3_out[0] = o_dspb[3];
    assign slot3_out[1] = o_dspb[6];
    assign slot3_out[2] = o_dspb[7];
    assign slot3_out[3] = 1'b0;
`endif
`ifdef DSP4_S34_SLOT2
    assign slot2_out[0] = o_dspb[3];
    assign slot2_out[1] = o_dspb[6];
    assign slot2_out[2] = o_dspb[7];
    assign slot2_out[3] = 1'b0;
`endif

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
