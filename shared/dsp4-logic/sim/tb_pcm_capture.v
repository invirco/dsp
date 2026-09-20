// tb_pcm_capture.v — the CAPTURE direction of the re-framer, which until
// 2026-09-09 had no testbench at all (tb_pcm_reframe leaves tdm_in and
// bck8_sample dangling). That gap is why a splice defect shipped:
//
//   model_tdm_tx -> [tdm_in] -> dsp4_pcm_reframe -> [pcm_din] -> model_pi_i2s_rx
//        (DSPB TDM8, MFD=1)                            (CM4 PCM, I2S slave)
//
// The DSP transmits a DIFFERENT word in every slot on every frame, so a
// read-out that walks the live register file while it is being rewritten
// cannot pass: it would deliver {frame N-1 high bits, frame N low bits},
// which equals neither frame's word. The check is therefore not "the
// value looks plausible" but "L and R are both exactly the words of ONE
// frame, and the same frame, on every pair, at a constant lag".
//
// Two configurations, because the defect's bit position depends on which
// slot is presented and both were wrong:
//   A = CAP_SLOT 0/1 — the PI_MAINCAP instrument (measured tear: bit 25)
//   B = CAP_SLOT 2/3 — the SHIPPING CM4 return  (measured tear: bit 9)
//
// Third check: the design-ID knock. The Pi plays {KNOCK_L, KNOCK_R} and
// the capture must answer DESIGN_ID / {ID_MAGIC, CFG_BITS} — this is the
// only readback path off the part (S5-9).

`timescale 1ns/1ps
`default_nettype none

module tb_pcm_capture;

    localparam real SYS_HALF = 10.1725;      // 49.152 MHz

    localparam [31:0] TB_DESIGN_ID = 32'hDEAD_BEEF;
    localparam [15:0] TB_CFG_BITS  = 16'h001F;
    localparam [31:0] KNOCK_L      = 32'hD5D5_1D1D;
    localparam [31:0] KNOCK_R      = ~KNOCK_L;
    localparam [15:0] ID_MAGIC     = 16'hD594;
    localparam [31:0] KNOCK2_L     = 32'hCD04_32B4;
    localparam [31:0] KNOCK2_R     = ~KNOCK2_L;
    localparam [15:0] CDC_MAGIC    = 16'hCD04;
    // Witness words the S81 knock must hand back VERBATIM. They are fed in
    // from here rather than computed, so this checks the knock path alone;
    // whether dsp4_logic_top counts cdc_o correctly is tb_logic_top's job.
    localparam [31:0] TB_CDC_L     = 32'h0055_00AA;
    localparam [31:0] TB_CDC_R     = {CDC_MAGIC, 16'h1234};
    // The S84 ad[0..2] knock. Its low two bits SELECT the lane, so unlike
    // the two above it has a reply that must DEPEND on what was knocked --
    // which is the part worth testing, and the part a fixed reply word
    // would not test at all. The witness words below are therefore a
    // function of the `ad_sel` the reframer drives back out, so a decode
    // that ignored the low bits, or held the wrong lane across the reply
    // window, answers the wrong word here and fails.
    localparam [31:0] KNOCK3_BASE  = 32'hAD07_5E20;
    localparam [15:0] AD_MAGIC     = 16'hAD07;

    // With the period decode corrected and CAP_EXTRA_DELAY back at 0, the
    // capture link is plain Philips I2S and the CM4 model is the ordinary
    // one. If this ever has to become 2 again, something has re-introduced
    // a one-BCK offset in the capture datapath -- that is the whole point
    // of asserting it here rather than compensating for it.
    localparam integer RX_DELAY = 1;

    reg sysclk = 1'b0;
    always #(SYS_HALF) sysclk = ~sysclk;

    wire bck8, bck16, fs8, fs16;
    wire bck8_launch, bck8_sample, bck16_launch, bck16_sample;
    wire [9:0] frame_pos;

    dsp4_clkgen u_clkgen (
        .sysclk(sysclk), .bck8(bck8), .bck16(bck16), .fs8(fs8), .fs16(fs16),
        .bck8_launch(bck8_launch), .bck8_sample(bck8_sample),
        .bck16_launch(bck16_launch), .bck16_sample(bck16_sample),
        .frame_pos(frame_pos)
    );

    // ---- DSP-side transmitter: every slot different, every frame different ----
    reg [31:0] txf = 32'd1;            // transmitted frame counter
    wire [255:0] tx_slots;

    // A per-(frame,slot) word that differs from its neighbours in every
    // bit region, so a splice at ANY bit position is detectable.
    function [31:0] w;
        input [31:0] f;
        input [31:0] s;
        begin
            w = (f * 32'h9E37_79B9) ^ (s * 32'h85EB_CA6B) ^ 32'h1234_5678;
        end
    endfunction

    genvar gs;
    generate
        for (gs = 0; gs < 8; gs = gs + 1) begin : g_tx
            assign tx_slots[gs*32 +: 32] = w(txf, gs);
        end
    endgenerate

    wire tdm_line;
    model_tdm_tx #(.SLOTS(8)) u_tx (
        .bck(bck8), .fs(fs8), .slots(tx_slots), .d(tdm_line)
    );

    // Advance the frame counter just after the frame has been latched by
    // the transmitter model (fs8 is asserted through the last BCK period).
    always @(negedge fs8) txf <= txf + 32'd1;

    // ---- A: capture slots 0/1 (PI_MAINCAP) ----
    wire a_clk, a_fs, a_din, a_tdm_out;
    reg  a_dout = 1'b0;
    dsp4_pcm_reframe #(.CAP_SLOT_L(0), .CAP_SLOT_R(1),
                       .DESIGN_ID(TB_DESIGN_ID), .CFG_BITS(TB_CFG_BITS)) u_a (
        .sysclk(sysclk), .frame_pos(frame_pos),
        .pcm_clk(a_clk), .pcm_fs(a_fs), .pcm_dout(a_dout), .pcm_din(a_din),
        .bck8_launch(bck8_launch), .bck8_sample(bck8_sample),
        .tdm_in(tdm_line), .tdm_out(a_tdm_out)
    );
    wire [31:0] a_l, a_r, a_pairs;
    model_pi_i2s_rx #(.DATA_DELAY(RX_DELAY)) u_a_rx (
        .bck(a_clk), .ws(a_fs), .sd(a_din),
        .left(a_l), .right(a_r), .pairs(a_pairs));

    // ---- B: capture slots 2/3 (shipping CM4 return) ----
    wire b_clk, b_fs, b_din, b_tdm_out;
    reg  b_dout = 1'b0;
    dsp4_pcm_reframe #(.DESIGN_ID(TB_DESIGN_ID), .CFG_BITS(TB_CFG_BITS)) u_b (
        .sysclk(sysclk), .frame_pos(frame_pos),
        .pcm_clk(b_clk), .pcm_fs(b_fs), .pcm_dout(b_dout), .pcm_din(b_din),
        .bck8_launch(bck8_launch), .bck8_sample(bck8_sample),
        .tdm_in(tdm_line), .tdm_out(b_tdm_out)
    );
    wire [31:0] b_l, b_r, b_pairs;
    model_pi_i2s_rx #(.DATA_DELAY(RX_DELAY)) u_b_rx (
        .bck(b_clk), .ws(b_fs), .sd(b_din),
        .left(b_l), .right(b_r), .pairs(b_pairs));

    // ---- C: the knock, on the shipping capture configuration ----
    wire c_clk, c_fs, c_din, c_dout, c_tdm_out;
    reg [31:0] pi_left  = 32'h0000_0000;
    reg [31:0] pi_right = 32'h0000_0000;
    // Stand-in for dsp4_logic_top's per-lane witness registers: lane n
    // answers a word that names n, so the round trip knock -> ad_sel ->
    // reply word is checkable here without counting anything.
    // THE LAYOUT HERE IS THE REAL ONE, bit for bit, and that is the point.
    // The first version of this stand-in packed the lane one bit lower than
    // dsp4_logic_top's `ad_wit_l` does, so the testbench passed while the
    // reader on the bench -- written from the same mistaken layout -- read
    // {lane[0], ones_last[8]} and reported a lane mismatch on a part that was
    // answering perfectly. A stand-in whose shape does not match the thing it
    // stands in for tests the knock and nothing else.
    //   L = {3'b0, bck_ratio_ok, edge, lane[1:0], ones_last[8:0],
    //        7'b0, ones_max[8:0]}
    // S85 adds the edge selector, and the stand-in answers a word that names
    // BOTH selectors -- a reply that varied only with the lane would pass a
    // decode that dropped the edge bit on the floor, which is the one new
    // mistake this knock can make.
    wire [1:0]  c_ad_sel;
    wire        c_ad_edge;
    wire [8:0]  tb_ad_ones = 9'h0A0 + {7'd0, c_ad_sel}
                                    + (c_ad_edge ? 9'h010 : 9'h000);
    wire [31:0] tb_ad_l = {3'd0, 1'b1, c_ad_edge, c_ad_sel,
                           tb_ad_ones, 7'd0, 9'h0F0};
    wire [31:0] tb_ad_r = {AD_MAGIC, 9'h123, 4'd0, c_ad_edge, c_ad_sel};
    dsp4_pcm_reframe #(.DESIGN_ID(TB_DESIGN_ID), .CFG_BITS(TB_CFG_BITS)) u_c (
        .sysclk(sysclk), .frame_pos(frame_pos),
        .pcm_clk(c_clk), .pcm_fs(c_fs), .pcm_dout(c_dout), .pcm_din(c_din),
        .bck8_launch(bck8_launch), .bck8_sample(bck8_sample),
        .tdm_in(tdm_line), .tdm_out(c_tdm_out),
        .cdc_wit_l(TB_CDC_L), .cdc_wit_r(TB_CDC_R),
        .ad_wit_l(tb_ad_l), .ad_wit_r(tb_ad_r), .ad_sel(c_ad_sel),
        .ad_edge(c_ad_edge)
    );
    model_pi_i2s_tx u_c_tx (.bck(c_clk), .ws(c_fs),
                            .left(pi_left), .right(pi_right), .sd(c_dout));
    wire [31:0] c_l, c_r, c_pairs;
    model_pi_i2s_rx #(.DATA_DELAY(RX_DELAY)) u_c_rx (
        .bck(c_clk), .ws(c_fs), .sd(c_din),
        .left(c_l), .right(c_r), .pairs(c_pairs));

    // ---- power-up-cleared state (no reset on U3) ----
    integer i;
    initial begin
        u_clkgen.cnt  = 10'd0;
        u_clkgen.bck8 = 1'b0;  u_clkgen.bck16 = 1'b0;
        u_clkgen.fs8  = 1'b0;  u_clkgen.fs16  = 1'b0;
        u_a.cap_sh = 32'd0; u_a.cap_flat = 256'd0; u_a.pw_flat = 256'd0;
        u_a.shift  = 32'd0; u_a.id_count = 8'd0;
        u_a.cap_hold_l = 32'd0; u_a.cap_hold_r = 32'd0;
        u_b.cap_sh = 32'd0; u_b.cap_flat = 256'd0; u_b.pw_flat = 256'd0;
        u_b.shift  = 32'd0; u_b.id_count = 8'd0;
        u_b.cap_hold_l = 32'd0; u_b.cap_hold_r = 32'd0;
        u_c.cap_sh = 32'd0; u_c.cap_flat = 256'd0; u_c.pw_flat = 256'd0;
        u_c.shift  = 32'd0; u_c.id_count = 8'd0;
        u_c.cap_hold_l = 32'd0; u_c.cap_hold_r = 32'd0;
    end

    // ---- checking ----
    integer errors  = 0;
    integer checked = 0;
    integer lag_a   = -1;
    integer lag_b   = -1;

    // Does (l,r) equal slots (sl,sr) of ONE transmitted frame within the
    // last 8? Returns the lag in frames, or -1.
    function integer find_lag;
        input [31:0] l;
        input [31:0] r;
        input [31:0] sl;
        input [31:0] sr;
        integer k;
        begin
            find_lag = -1;
            for (k = 1; k <= 8; k = k + 1)
                if (find_lag == -1
                    && l === w(txf - k, sl) && r === w(txf - k, sr))
                    find_lag = k;
        end
    endfunction

    task check_one;
        input [8*8-1:0] name;
        input [31:0] l;
        input [31:0] r;
        input [31:0] sl;
        input [31:0] sr;
        inout integer lag;
        integer got;
        integer k;
        begin
            got = find_lag(l, r, sl, sr);
            checked = checked + 1;
            if (got == -1) begin
                errors = errors + 1;
                if (errors <= 2) begin
                    $display("  %0s SPLICE/MISMATCH: L=%08x R=%08x match no single frame",
                             name, l, r);
                    for (k = 1; k <= 8; k = k + 1)
                        $display("      frame -%0d was L=%08x R=%08x",
                                 k, w(txf - k, sl), w(txf - k, sr));
                end
            end else if (lag == -1) begin
                lag = got;
                $display("  %0s locked at lag %0d frame(s)", name, got);
            end else if (got != lag) begin
                errors = errors + 1;
                if (errors <= 6)
                    $display("  %0s LAG MOVED: %0d -> %0d", name, lag, got);
            end
        end
    endtask

    reg [31:0] a_seen = 32'd0;
    reg [31:0] b_seen = 32'd0;

    always @(a_pairs) if (a_pairs > 32'd4) begin
        a_seen = a_seen + 32'd1;
        check_one("A(0/1)", a_l, a_r, 32'd0, 32'd1, lag_a);
    end
    always @(b_pairs) if (b_pairs > 32'd4) begin
        b_seen = b_seen + 32'd1;
        check_one("B(2/3)", b_l, b_r, 32'd2, 32'd3, lag_b);
    end

    integer knock_errors = 0;
    integer k;

    initial begin
        if ($test$plusargs("vcd")) begin
            $dumpfile("tb_pcm_capture.vcd");
            $dumpvars(0, tb_pcm_capture);
        end

        // --- 1/2: capture coherence, both slot configurations ---
        #(1024.0 * 2.0 * SYS_HALF * 40);

        if (checked < 60) begin
            $display("  too few pairs checked (%0d)", checked);
            errors = errors + 1;
        end
        $display("  capture pairs checked: %0d (A %0d, B %0d), errors %0d",
                 checked, a_seen, b_seen, errors);

        // --- 3: the design-ID knock ---
        pi_left  = KNOCK_L;
        pi_right = KNOCK_R;
        #(1024.0 * 2.0 * SYS_HALF * 6);
        pi_left  = 32'h0000_0000;
        pi_right = 32'h0000_0000;
        #(1024.0 * 2.0 * SYS_HALF * 4);

        if (c_l !== TB_DESIGN_ID) begin
            $display("  KNOCK: design id read %08x, expected %08x", c_l, TB_DESIGN_ID);
            knock_errors = knock_errors + 1;
        end
        if (c_r !== {ID_MAGIC, TB_CFG_BITS}) begin
            $display("  KNOCK: config word read %08x, expected %08x",
                     c_r, {ID_MAGIC, TB_CFG_BITS});
            knock_errors = knock_errors + 1;
        end
        if (knock_errors == 0)
            $display("  knock answered %08x / %08x", c_l, c_r);

        // The reply must EXPIRE: 128 frames after the knock the capture is
        // audio again, or the ID register would be a permanent mute.
        #(1024.0 * 2.0 * SYS_HALF * 140);
        if (c_l === TB_DESIGN_ID && c_r === {ID_MAGIC, TB_CFG_BITS}) begin
            $display("  KNOCK: reply never expired");
            knock_errors = knock_errors + 1;
        end else begin
            $display("  knock reply expired back to audio (%08x / %08x)", c_l, c_r);
        end

        // --- 4: the CDC_O witness knock (S81) ---
        // A DIFFERENT word pair must fetch a DIFFERENT pair of words, and
        // the audio path must come back afterwards. Both halves matter: a
        // knock that answered whatever the last knock answered would be an
        // instrument that cannot report a change, which is the only thing
        // this one exists to do.
        pi_left  = KNOCK2_L;
        pi_right = KNOCK2_R;
        #(1024.0 * 2.0 * SYS_HALF * 6);
        pi_left  = 32'h0000_0000;
        pi_right = 32'h0000_0000;
        #(1024.0 * 2.0 * SYS_HALF * 4);

        if (c_l !== TB_CDC_L) begin
            $display("  KNOCK2: witness L read %08x, expected %08x", c_l, TB_CDC_L);
            knock_errors = knock_errors + 1;
        end
        if (c_r !== TB_CDC_R) begin
            $display("  KNOCK2: witness R read %08x, expected %08x", c_r, TB_CDC_R);
            knock_errors = knock_errors + 1;
        end
        if (c_r[31:16] === ID_MAGIC) begin
            $display("  KNOCK2: answered with the ID magic, not the CDC magic");
            knock_errors = knock_errors + 1;
        end

        #(1024.0 * 2.0 * SYS_HALF * 140);
        if (c_l === TB_CDC_L && c_r === TB_CDC_R) begin
            $display("  KNOCK2: reply never expired");
            knock_errors = knock_errors + 1;
        end else begin
            $display("  knock2 answered and expired back to audio");
        end

        // --- 5: the ad[0..2] witness knock, all six (lane, edge) ---
        // The knock's low three bits choose the lane (1:0) and the counter
        // bank (2), so the reply must CHANGE with BOTH. Six fixed replies
        // would pass a decode that ignored either selector, which is the one
        // mistake this knock can make that the other two cannot -- and S84-9
        // is what happens when it is made: the reader read the lane one bit
        // low, which is right for lane 0 and wrong for 1 and 2.
        // k[2] is the edge, k[1:0] the lane; k = 3 and k = 7 are the lane-3
        // patterns and are tested below as the negative control instead.
        for (k = 0; k < 8; k = k + 1) begin
          if (k[1:0] !== 2'd3) begin
            pi_left  = KNOCK3_BASE | k;
            pi_right = ~(KNOCK3_BASE | k);
            #(1024.0 * 2.0 * SYS_HALF * 6);
            pi_left  = 32'h0000_0000;
            pi_right = 32'h0000_0000;
            #(1024.0 * 2.0 * SYS_HALF * 4);

            if (c_r[31:16] !== AD_MAGIC) begin
                $display("  KNOCK3[%0d]: R read %08x, no AD magic", k, c_r);
                knock_errors = knock_errors + 1;
            end else if (c_r[1:0] !== k[1:0] || c_l[26:25] !== k[1:0]) begin
                $display("  KNOCK3[%0d]: answered for lane %0d/%0d, not %0d",
                         k, c_l[26:25], c_r[1:0], k[1:0]);
                knock_errors = knock_errors + 1;
            end else if (c_l[27] !== k[2] || c_r[2] !== k[2]) begin
                $display("  KNOCK3[%0d]: answered for edge %0d/%0d, not %0d",
                         k, c_l[27], c_r[2], k[2]);
                knock_errors = knock_errors + 1;
            end else if (c_l[24:16] !== (9'h0A0 + {7'd0, k[1:0]}
                                         + (k[2] ? 9'h010 : 9'h000))) begin
                // The counters themselves must come from the selected bank,
                // not merely the echo: a mux that echoed the selector while
                // always reading bank 0 would pass every check above.
                $display("  KNOCK3[%0d]: echo says edge %0d lane %0d, counter word %03x",
                         k, c_l[27], c_l[26:25], c_l[24:16]);
                knock_errors = knock_errors + 1;
            end else begin
                $display("  knock3 lane %0d edge %0d answered %08x / %08x",
                         k[1:0], k[2], c_l, c_r);
            end

            #(1024.0 * 2.0 * SYS_HALF * 140);
            if (c_r[31:16] === AD_MAGIC) begin
                $display("  KNOCK3[%0d]: reply never expired", k);
                knock_errors = knock_errors + 1;
            end
          end
        end

        // --- 6: lane 3 is NOT a knock, ON EITHER EDGE ---
        // The negative control for the decode: the same bits with both lane
        // selector bits set must fall through to audio, not answer about some
        // lane. Without this, `knock3_lane != 3` could be deleted and every
        // test above would still pass. Taken on both edges because S85 widened
        // the compare from [31:2] to [31:3], and a compare that had been
        // widened one bit too far would accept lane 3 on the launch edge only.
        for (k = 0; k < 8; k = k + 4) begin
            pi_left  = KNOCK3_BASE | k | 2'd3;
            pi_right = ~(KNOCK3_BASE | k | 2'd3);
            #(1024.0 * 2.0 * SYS_HALF * 6);
            pi_left  = 32'h0000_0000;
            pi_right = 32'h0000_0000;
            #(1024.0 * 2.0 * SYS_HALF * 4);
            if (c_r[31:16] === AD_MAGIC) begin
                $display("  KNOCK3: lane 3 edge %0d answered %08x / %08x -- it must not",
                         k[2], c_l, c_r);
                knock_errors = knock_errors + 1;
            end else begin
                $display("  knock3 lane 3 edge %0d correctly not a knock", k[2]);
            end
        end

        if (errors == 0 && knock_errors == 0)
            $display("tb_pcm_capture: PASS");
        else
            $display("tb_pcm_capture: FAIL (%0d capture, %0d knock)",
                     errors, knock_errors);
        $finish;
    end

endmodule

`default_nettype wire
