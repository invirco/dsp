// tb_revd_id.v — the REV D revision's board-strap report (S173), through the
// real top level: dsp4_logic_revd_top = the unchanged dsp4_logic_top plus
// dsp4_revd_id_tap.
//
// Two parts are simulated side by side, identical except for U3.81:
//   G (strap to GND)  = rev D image on rev D copper  -> CFG word 0x0C10
//   O (strap open)    = rev D image on rev C copper  -> CFG word 0x0410
// The Pi plays the ID knock to both, and each must answer its own word.
//
// Then the property that makes the tap safe to ship: OUTSIDE the one bit it
// owns, the pin carries exactly the core's bit, one sysclk later. Checked on
// every sysclk edge for the whole run, knock included, on both parts -- so
// a tap that touched audio, or spliced the wrong bit position, fails here.
//
// DESIGN_ID / CFG_BITS are set as build.sh sets them (macros), so the core
// and the tap agree on the ID exactly as they must in the bitstream.

`define DSP4_DESIGN_ID 32'hC0DE_5EED
`define DSP4_CFG_BITS  16'h0410

`timescale 1ns/1ps
`default_nettype none

module tb_revd_id;

    localparam real SYS_HALF = 10.1725;
    localparam [31:0] KNOCK_L  = 32'hD5D5_1D1D;
    localparam [31:0] KNOCK_R  = ~KNOCK_L;
    localparam [15:0] ID_MAGIC = 16'hD594;

    reg sysclk = 1'b0;
    always #(SYS_HALF) sysclk = ~sysclk;

    reg [31:0] pi_left  = 32'h0000_0000;
    reg [31:0] pi_right = 32'h0000_0000;

    // ---- part G: BOARD_REV0 tied to GND (rev D copper) ----
    wire g_clk, g_fs, g_din, g_dout;
    wire g_dsp_clk, g_cdc_i, g_blink, g_mbck, g_mfs, g_cbck, g_cfs;
    wire [7:0] g_bcki, g_fsi, g_i;
    wire [3:0] g_da, g_no, g_test;
    dsp4_logic_revd_top g (
        .sysclk(sysclk), .conv_bck(g_cbck), .conv_fs(g_cfs),
        .dsp_clk(g_dsp_clk), .bcki(g_bcki), .fsi(g_fsi), .i_dspa(g_i),
        .o_dspb(8'h00), .ad(4'h0), .da(g_da), .ni(4'h0), .no(g_no),
        .cdc_o(1'b0), .cdc_i(g_cdc_i),
        .mems_bck(g_mbck), .mems_fs(g_mfs), .mems_i2s(1'b0),
        .pcm_clk(g_clk), .pcm_fs(g_fs), .pcm_dout(g_dout), .pcm_din(g_din),
        .blink_led(g_blink), .test(g_test), .board_rev0(1'b0)
    );
    model_pi_i2s_tx u_g_tx (.bck(g_clk), .ws(g_fs),
                            .left(pi_left), .right(pi_right), .sd(g_dout));
    wire [31:0] g_l, g_r, g_pairs;
    model_pi_i2s_rx u_g_rx (.bck(g_clk), .ws(g_fs), .sd(g_din),
                            .left(g_l), .right(g_r), .pairs(g_pairs));

    // ---- part O: BOARD_REV0 open (rev C copper, weak pull-up = 1) ----
    wire o_clk, o_fs, o_din, o_dout;
    wire o_dsp_clk, o_cdc_i, o_blink, o_mbck, o_mfs, o_cbck, o_cfs;
    wire [7:0] o_bcki, o_fsi, o_i;
    wire [3:0] o_da, o_no, o_test;
    dsp4_logic_revd_top o (
        .sysclk(sysclk), .conv_bck(o_cbck), .conv_fs(o_cfs),
        .dsp_clk(o_dsp_clk), .bcki(o_bcki), .fsi(o_fsi), .i_dspa(o_i),
        .o_dspb(8'h00), .ad(4'h0), .da(o_da), .ni(4'h0), .no(o_no),
        .cdc_o(1'b0), .cdc_i(o_cdc_i),
        .mems_bck(o_mbck), .mems_fs(o_mfs), .mems_i2s(1'b0),
        .pcm_clk(o_clk), .pcm_fs(o_fs), .pcm_dout(o_dout), .pcm_din(o_din),
        .blink_led(o_blink), .test(o_test), .board_rev0(1'b1)
    );
    model_pi_i2s_tx u_o_tx (.bck(o_clk), .ws(o_fs),
                            .left(pi_left), .right(pi_right), .sd(o_dout));
    wire [31:0] o_l, o_r, o_pairs;
    model_pi_i2s_rx u_o_rx (.bck(o_clk), .ws(o_fs), .sd(o_din),
                            .left(o_l), .right(o_r), .pairs(o_pairs));

    // ---- power-up-cleared state (no reset on U3), as tb_logic_top ----
    initial begin
        g.u_core.u_clkgen.cnt = 10'd0;  o.u_core.u_clkgen.cnt = 10'd0;
        g.u_core.u_clkgen.bck8 = 1'b0;  o.u_core.u_clkgen.bck8 = 1'b0;
        g.u_core.u_clkgen.bck16 = 1'b0; o.u_core.u_clkgen.bck16 = 1'b0;
        g.u_core.u_clkgen.fs8 = 1'b0;   o.u_core.u_clkgen.fs8 = 1'b0;
        g.u_core.u_clkgen.fs16 = 1'b0;  o.u_core.u_clkgen.fs16 = 1'b0;
        g.u_core.u_pcm.pcm_clk = 1'b0;  o.u_core.u_pcm.pcm_clk = 1'b0;
        g.u_core.u_pcm.pcm_fs = 1'b0;   o.u_core.u_pcm.pcm_fs = 1'b0;
        g.u_core.u_pcm.shift = 32'd0;   o.u_core.u_pcm.shift = 32'd0;
        g.u_core.u_pcm.pw_flat = 256'd0;  o.u_core.u_pcm.pw_flat = 256'd0;
        g.u_core.u_pcm.cap_flat = 256'd0; o.u_core.u_pcm.cap_flat = 256'd0;
        g.u_core.u_pcm.cap_sh = 32'd0;  o.u_core.u_pcm.cap_sh = 32'd0;
        g.u_core.u_pcm.id_count = 8'd0; o.u_core.u_pcm.id_count = 8'd0;
        g.u_core.u_pcm.cap_hold_l = 32'd0; o.u_core.u_pcm.cap_hold_l = 32'd0;
        g.u_core.u_pcm.cap_hold_r = 32'd0; o.u_core.u_pcm.cap_hold_r = 32'd0;
        g.u_core.u_pcm.tdm_out = 1'b0;  o.u_core.u_pcm.tdm_out = 1'b0;
        g.u_core.hb = 25'd0;            o.u_core.hb = 25'd0;
        g.u_core.dsp_clk_q = 1'b0;      o.u_core.dsp_clk_q = 1'b0;
    end

    // ---- the tap is transparent outside its one bit ----
    // On each edge the pin takes either the core's current bit or the
    // strap; record which, and check it after the edge.
    integer pass_errors = 0, spliced_g = 0, spliced_o = 0;
    reg g_exp, o_exp, g_spl, o_spl;
    always @(posedge sysclk) begin
        g_exp = g.pcm_din_core;  g_spl = g.u_rev.splice;
        o_exp = o.pcm_din_core;  o_spl = o.u_rev.splice;
        #1;
        if (g_spl) begin
            spliced_g = spliced_g + 1;
            if (g_din !== 1'b1) pass_errors = pass_errors + 1;
        end else if (g_din !== g_exp) pass_errors = pass_errors + 1;
        if (o_spl) begin
            spliced_o = spliced_o + 1;
            if (o_din !== 1'b0) pass_errors = pass_errors + 1;
        end else if (o_din !== o_exp) pass_errors = pass_errors + 1;
    end

    integer errors = 0;
    initial begin
        if ($test$plusargs("vcd")) begin
            $dumpfile("tb_revd_id.vcd");
            $dumpvars(0, tb_revd_id);
        end

        // settle, with silence on the link
        #(1024.0 * 2.0 * SYS_HALF * 20);
        if (spliced_g != 0 || spliced_o != 0) begin
            $display("  tap spliced %0d/%0d sysclk with no knock", spliced_g, spliced_o);
            errors = errors + 1;
        end

        // the ID knock
        pi_left = KNOCK_L; pi_right = KNOCK_R;
        #(1024.0 * 2.0 * SYS_HALF * 6);
        pi_left = 32'h0; pi_right = 32'h0;
        #(1024.0 * 2.0 * SYS_HALF * 4);

        if (g_l !== `DSP4_DESIGN_ID || g_r !== {ID_MAGIC, 16'h0C10}) begin
            $display("  rev D copper: read %08x / %08x, expected %08x / %08x",
                     g_l, g_r, `DSP4_DESIGN_ID, {ID_MAGIC, 16'h0C10});
            errors = errors + 1;
        end else
            $display("  rev D copper answered %08x / %08x", g_l, g_r);
        if (o_l !== `DSP4_DESIGN_ID || o_r !== {ID_MAGIC, 16'h0410}) begin
            $display("  rev C copper: read %08x / %08x, expected %08x / %08x",
                     o_l, o_r, `DSP4_DESIGN_ID, {ID_MAGIC, 16'h0410});
            errors = errors + 1;
        end else
            $display("  rev C copper answered %08x / %08x", o_l, o_r);

        // reply expires, audio (zeros here) comes back, splice stops
        #(1024.0 * 2.0 * SYS_HALF * 140);
        if (g_r === {ID_MAGIC, 16'h0C10} || o_r === {ID_MAGIC, 16'h0410}) begin
            $display("  reply never expired");
            errors = errors + 1;
        end
        // one spliced bit per reply frame: 16 sysclk (launch to launch),
        // for 128 frames after the LAST knock frame -- so 133 x 16 here
        if (spliced_g == 0 || spliced_g != spliced_o) begin
            $display("  splice counts G %0d / O %0d", spliced_g, spliced_o);
            errors = errors + 1;
        end
        if (pass_errors != 0) begin
            $display("  tap altered %0d non-strap bit(s)", pass_errors);
            errors = errors + 1;
        end
        $display("  spliced sysclk: %0d per part; pass-through mismatches %0d",
                 spliced_g, pass_errors);

        if (errors == 0) $display("tb_revd_id: PASS");
        else             $display("tb_revd_id: FAIL (%0d)", errors);
        $finish;
    end

endmodule

`default_nettype wire
