// tb_logic_top.v — self-checking testbench for dsp4_logic_top.
//
// The top level is mostly wires, and wires are exactly what a fitted-
// but-never-simulated design gets wrong silently. Checks:
//   1. Clock-pair ROLES: bcki/fsi[0..3] serve DSPA (in TDM8 / out TDM16),
//      [4..7] serve DSPB (in TDM16 / out TDM8). A swapped pair here is a
//      dead board, and the pairing is only verifiable by format.
//   2. DSPA input-lane sources for the D24 personality (lanes 0-2 = ADC,
//      lane 3 = NET) and the codec/MEMS/snake lanes.
//   3. DSPB output routing incl. the schematic-review facts: B_O1 -> DA3
//      (NOT DA1), DA1/DA2 driven low, B_O2 = codec on D24 / snake on D32,
//      B_O3 (DAC MAIN) parked with no D24 sink.
//   4. dsp_clk is sysclk/2 = 24.576 MHz with a 50% duty cycle — the
//      ADSP-2156x CLKIN range is 20-30 MHz, so passing the raw 49.152 MHz
//      XO through (as rev C does in copper) leaves the DSPs' PLL unable to
//      lock and their boot ROM never runs.
//   5. The TEST1-4 bring-up pins carry the clkgen nets they claim to,
//      and none of them is stuck — a dead test point is worse than no
//      test point, because it reads as a dead board at bring-up.

`timescale 1ns/1ps
`default_nettype none

module tb_logic_top;

    localparam real SYS_HALF = 10.1725;

    reg sysclk = 1'b0;
    always #(SYS_HALF) sysclk = ~sysclk;

    reg  [2:0] ic_strap  = 3'b000;
    reg  [1:0] il_strap  = 2'b00;
    reg        strap_d32 = 1'b0;
    reg  [7:0] o_dspb    = 8'h00;
    reg  [3:0] ad        = 4'h0;
    reg  [3:0] ni        = 4'h0;
    reg        cdc_o     = 1'b0;
    reg        snake_in  = 1'b0;
    reg        mems      = 1'b0;
    reg        pcm_dout  = 1'b0;

    wire dsp_clk, cdc_i, snake_out, dac_main, blink_led;
    wire pcm_clk, pcm_fs, pcm_din;
    wire [7:0] bcki, fsi, i_dspa;
    wire [3:0] da, no, test;

    dsp4_logic_top dut (
        .sysclk(sysclk), .ic_strap(ic_strap), .il_strap(il_strap),
        .strap_d32(strap_d32), .dsp_clk(dsp_clk),
        .bcki(bcki), .fsi(fsi), .i_dspa(i_dspa), .o_dspb(o_dspb),
        .ad(ad), .da(da), .ni(ni), .no(no),
        .cdc_o(cdc_o), .cdc_i(cdc_i),
        .snake_in(snake_in), .snake_out(snake_out), .dac_main(dac_main),
        .mems(mems),
        .pcm_clk(pcm_clk), .pcm_fs(pcm_fs), .pcm_dout(pcm_dout),
        .pcm_din(pcm_din), .blink_led(blink_led), .test(test)
    );

    initial begin
        dut.u_clkgen.cnt   = 10'd0;
        dut.u_clkgen.bck8  = 1'b0;
        dut.u_clkgen.bck16 = 1'b0;
        dut.u_clkgen.fs8   = 1'b0;
        dut.u_clkgen.fs16  = 1'b0;
        dut.u_pcm.pcm_clk  = 1'b0;
        dut.u_pcm.pcm_fs   = 1'b0;
        dut.u_pcm.shift    = 32'd0;
        dut.u_pcm.pw_flat  = 256'd0;
        dut.u_pcm.cap_flat = 256'd0;
        dut.u_pcm.tdm_out  = 1'b0;
        dut.hb             = 25'd0;
        dut.dsp_clk_q      = 1'b0;
    end

    integer errors = 0;
    task check;
        input cond;
        input [1023:0] what;
        begin
            if (cond !== 1'b1) begin
                $display("FAIL: %0s (t=%0t)", what, $time);
                errors = errors + 1;
            end
        end
    endtask

    // ---- 1. clock-pair roles, measured as period in sysclk cycles ----
    // DSPA (0-3): {in TDM8, out TDM16, in TDM8, out TDM16}
    // DSPB (4-7): {in TDM16, out TDM8, in TDM16, out TDM8}
    integer sysclk_ticks = 0;
    always @(posedge sysclk) sysclk_ticks = sysclk_ticks + 1;

    // ---- dsp_clk = sysclk/2, 50% duty (SYS_CLKIN0 must be 20-30 MHz) ----
    integer dsp_last_rise  = -1;
    integer dsp_edges      = 0;
    integer dsp_bad_period = 0;
    integer dsp_bad_duty   = 0;
    always @(posedge dsp_clk) begin
        if (dsp_last_rise >= 0 && (sysclk_ticks - dsp_last_rise) != 2) begin
            $display("FAIL: dsp_clk period %0d sysclk, expected 2 (t=%0t)",
                     sysclk_ticks - dsp_last_rise, $time);
            dsp_bad_period = dsp_bad_period + 1;
        end
        dsp_last_rise = sysclk_ticks;
        dsp_edges     = dsp_edges + 1;
    end
    always @(negedge dsp_clk)
        if (dsp_last_rise >= 0 && (sysclk_ticks - dsp_last_rise) != 1) begin
            $display("FAIL: dsp_clk high for %0d sysclk, expected 1 (t=%0t)",
                     sysclk_ticks - dsp_last_rise, $time);
            dsp_bad_duty = dsp_bad_duty + 1;
        end

    integer exp_div [0:7];
    integer last_edge [0:7];
    integer seen [0:7];
    integer k;

    genvar g;
    generate
        for (g = 0; g < 8; g = g + 1) begin : pair_check
            always @(posedge bcki[g]) begin
                if (last_edge[g] >= 0) begin
                    if ((sysclk_ticks - last_edge[g]) != exp_div[g]) begin
                        $display("FAIL: bcki[%0d] period %0d sysclk, expected %0d (t=%0t)",
                                 g, sysclk_ticks - last_edge[g], exp_div[g], $time);
                        errors = errors + 1;
                    end
                    seen[g] = seen[g] + 1;
                end
                last_edge[g] = sysclk_ticks;
            end
        end
    endgenerate

    // FS pulse width must match the same line's format.
    integer fs_rise [0:7];
    generate
        for (g = 0; g < 8; g = g + 1) begin : fs_check
            always @(posedge fsi[g]) fs_rise[g] = sysclk_ticks;
            always @(negedge fsi[g])
                if (fs_rise[g] >= 0 &&
                    (sysclk_ticks - fs_rise[g]) != exp_div[g]) begin
                    $display("FAIL: fsi[%0d] width %0d sysclk, expected %0d (t=%0t)",
                             g, sysclk_ticks - fs_rise[g], exp_div[g], $time);
                    errors = errors + 1;
                end
        end
    endgenerate

    // ---- 5. test points ----
    // Two independent checks: each pin mirrors its clkgen net at every
    // sample (sampled on the falling sysclk edge, after the registered
    // clkgen outputs have settled), AND each pin actually toggles — a
    // pin stuck at the same value as a stuck source passes the first
    // check alone. Counted, not printed, so a failure is one line.
    integer test_mismatch [0:3];
    always @(negedge sysclk) begin
        if (test[0] !== dut.fs8)          test_mismatch[0] = test_mismatch[0] + 1;
        if (test[1] !== dut.bck8)         test_mismatch[1] = test_mismatch[1] + 1;
        if (test[2] !== dut.fs16)         test_mismatch[2] = test_mismatch[2] + 1;
        if (test[3] !== dut.frame_pos[9]) test_mismatch[3] = test_mismatch[3] + 1;
    end

    integer test_edges [0:3];
    generate
        for (g = 0; g < 4; g = g + 1) begin : test_toggle
            always @(test[g]) test_edges[g] = test_edges[g] + 1;
        end
    endgenerate

    // ---- 2/3. static routing ----
    task check_routing;
        begin
            // DSPA inputs. D24 and D32 both take lanes 0-2 from the ADCs
            // and lane 3 from NET today (net_sel is fixed per product in
            // RTL; the D32 personality is still TBD).
            check(i_dspa[0] === ad[0], "i_dspa[0] != AD0");
            check(i_dspa[1] === ad[1], "i_dspa[1] != AD1");
            check(i_dspa[2] === ad[2], "i_dspa[2] != AD2");
            check(i_dspa[3] === ni[3], "i_dspa[3] != NI3 (A_I3 is NET-only)");
            check(i_dspa[4] === cdc_o, "i_dspa[4] != codec return");
            check(i_dspa[5] === (strap_d32 ? snake_in : 1'b0),
                  "i_dspa[5] snake lane wrong for personality");
            check(i_dspa[7] === mems, "i_dspa[7] != MEMS");

            // DSPB outputs.
            check(da[0] === o_dspb[0], "DA0 != B_O0");
            check(da[1] === 1'b0,      "DA1 driven (dead-ends at Digital J18)");
            check(da[2] === 1'b0,      "DA2 driven (D32_COMPAT only)");
            check(da[3] === o_dspb[1], "DA3 != B_O1 (DA_LANE_B_O1)");
            check(cdc_i === (strap_d32 ? 1'b0 : o_dspb[2]),
                  "codec DAC lane wrong for personality");
            check(snake_out === (strap_d32 ? o_dspb[2] : 1'b0),
                  "snake out lane wrong for personality");
            check(dac_main === o_dspb[3], "DAC MAIN != B_O3");
            check(no[0] === o_dspb[4], "NO0 != B_O4");
            check(no[1] === o_dspb[5], "NO1 != B_O5");
            check(no[2] === o_dspb[6], "NO2 != B_O6");
            check(no[3] === o_dspb[7], "NO3 != B_O7");
        end
    endtask

    task sweep_routing;
        integer p;
        begin
            for (p = 0; p < 8; p = p + 1) begin
                o_dspb   = (8'h01 << p);
                ad       = ~ad;
                ni       = {~ni[3], ni[2:0]};
                cdc_o    = ~cdc_o;
                snake_in = ~snake_in;
                mems     = ~mems;
                #3;
                check_routing;
            end
            o_dspb = 8'hA5; ad = 4'h5; ni = 4'hC;
            #3; check_routing;
            o_dspb = 8'h5A; ad = 4'hA; ni = 4'h3;
            #3; check_routing;
        end
    endtask

    initial begin
        if ($test$plusargs("vcd")) begin
            $dumpfile("tb_logic_top.vcd");
            $dumpvars(0, tb_logic_top);
        end

        for (k = 0; k < 8; k = k + 1) begin
            last_edge[k] = -1;
            fs_rise[k]   = -1;
            seen[k]      = 0;
        end
        for (k = 0; k < 4; k = k + 1) begin
            test_edges[k]    = 0;
            test_mismatch[k] = 0;
        end
        // TDM8 = sysclk/4, TDM16 = sysclk/2
        exp_div[0] = 4;  exp_div[1] = 2;  exp_div[2] = 4;  exp_div[3] = 2;
        exp_div[4] = 2;  exp_div[5] = 4;  exp_div[6] = 2;  exp_div[7] = 4;

        strap_d32 = 1'b0;              // D24 personality
        sweep_routing;
        strap_d32 = 1'b1;              // D32 personality
        sweep_routing;

        #(1024.0 * 2.0 * SYS_HALF * 2.5);   // let the clock checks run

        check(dsp_edges > 100, "dsp_clk is not toggling");
        check(dsp_bad_period == 0, "dsp_clk period is not 2 sysclk cycles");
        check(dsp_bad_duty == 0, "dsp_clk is not 50% duty (1 sysclk high)");
        for (k = 0; k < 8; k = k + 1)
            if (seen[k] < 4) begin
                $display("FAIL: bcki[%0d] barely toggled (%0d edges)", k, seen[k]);
                errors = errors + 1;
            end

        for (k = 0; k < 4; k = k + 1) begin
            if (test_mismatch[k] != 0) begin
                $display("FAIL: TEST%0d does not mirror its clkgen net (%0d samples)",
                         k + 1, test_mismatch[k]);
                errors = errors + 1;
            end
            if (test_edges[k] < 4) begin
                $display("FAIL: TEST%0d stuck (%0d edges)", k + 1, test_edges[k]);
                errors = errors + 1;
            end
        end

        $display("tb_logic_top: %0d errors", errors);
        if (errors == 0) $display("tb_logic_top: PASS");
        else             $display("tb_logic_top: FAIL (%0d)", errors);
        $finish;
    end
endmodule

`default_nettype wire
