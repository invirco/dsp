// tb_pcm_reframe.v — end-to-end check of the Pi PCM -> TDM8 re-framer.
//
//   model_pi_i2s_tx  -> [pcm_dout] -> dsp4_pcm_reframe -> [tdm_out] -> model_tdm_rx
//        (Philips I2S, LOGIC-mastered clocks)              (DSPA I6, CKRE=1/MFD=1)
//
// Both ends are the SPEC, not the implementation: the Pi model follows
// the I2S standard and the receiver model follows the locked slot-map
// conventions. A stereo sample put on the Pi pins must reappear
// bit-exact in TDM8 slots 0/1 (PI_PCM_L / PI_PCM_R), with slots 2-7
// silent. Capture deliberately runs one frame behind, so the check
// looks at the frames that have settled after a hold.
//
// Run twice over, once per framing variant, with the RTL parameter and
// the Pi model moved together:
//   A = PCM_DATA_DELAY 1 (Philips I2S — the shipping default)
//   B = PCM_DATA_DELAY 0 (left-justified — the bring-up fallback if the
//       Pi's CH1POS turns out to be programmed differently)
// Variant B is not dead weight: it is the evidence that the parameter
// actually re-aligns the capture rather than just existing.

`timescale 1ns/1ps
`default_nettype none

module tb_pcm_reframe;

    localparam real SYS_HALF = 10.1725;      // 49.152 MHz
    localparam real FRAME_NS = 1024.0 * 2.0 * SYS_HALF;

    reg sysclk = 1'b0;
    always #(SYS_HALF) sysclk = ~sysclk;

    // ---- clkgen (shared) ----
    wire bck8, bck16, fs8, fs16;
    wire bck8_launch, bck8_sample, bck16_launch, bck16_sample;
    wire [9:0] frame_pos;

    dsp4_clkgen u_clkgen (
        .sysclk(sysclk), .bck8(bck8), .bck16(bck16), .fs8(fs8), .fs16(fs16),
        .bck8_launch(bck8_launch), .bck8_sample(bck8_sample),
        .bck16_launch(bck16_launch), .bck16_sample(bck16_sample),
        .frame_pos(frame_pos)
    );

    reg [31:0] pi_left  = 32'h0000_0000;
    reg [31:0] pi_right = 32'h0000_0000;

    // ---- A: Philips I2S ----
    wire a_pcm_clk, a_pcm_fs, a_pcm_din, a_tdm_out, a_pcm_dout;

    dsp4_pcm_reframe #(.PCM_DATA_DELAY(1)) u_pcm_a (
        .sysclk(sysclk), .frame_pos(frame_pos),
        .pcm_clk(a_pcm_clk), .pcm_fs(a_pcm_fs),
        .pcm_dout(a_pcm_dout), .pcm_din(a_pcm_din),
        .bck8_launch(bck8_launch), .tdm_out(a_tdm_out)
    );
    model_pi_i2s_tx #(.DATA_DELAY(1)) u_pi_a (
        .bck(a_pcm_clk), .ws(a_pcm_fs),
        .left(pi_left), .right(pi_right), .sd(a_pcm_dout)
    );
    model_tdm_rx #(.SLOTS(8)) u_rx_a (.bck(bck8), .fs(fs8), .d(a_tdm_out));

    // ---- B: left-justified ----
    wire b_pcm_clk, b_pcm_fs, b_pcm_din, b_tdm_out, b_pcm_dout;

    dsp4_pcm_reframe #(.PCM_DATA_DELAY(0)) u_pcm_b (
        .sysclk(sysclk), .frame_pos(frame_pos),
        .pcm_clk(b_pcm_clk), .pcm_fs(b_pcm_fs),
        .pcm_dout(b_pcm_dout), .pcm_din(b_pcm_din),
        .bck8_launch(bck8_launch), .tdm_out(b_tdm_out)
    );
    model_pi_i2s_tx #(.DATA_DELAY(0)) u_pi_b (
        .bck(b_pcm_clk), .ws(b_pcm_fs),
        .left(pi_left), .right(pi_right), .sd(b_pcm_dout)
    );
    model_tdm_rx #(.SLOTS(8)) u_rx_b (.bck(bck8), .fs(fs8), .d(b_tdm_out));

    // ---- power-up-cleared state (no reset on U3) ----
    initial begin
        u_clkgen.cnt    = 10'd0;
        u_clkgen.bck8   = 1'b0;
        u_clkgen.bck16  = 1'b0;
        u_clkgen.fs8    = 1'b0;
        u_clkgen.fs16   = 1'b0;
        u_pcm_a.pcm_clk = 1'b0;
        u_pcm_a.pcm_fs  = 1'b0;
        u_pcm_a.shift   = 32'd0;
        u_pcm_a.pw_flat  = 256'd0;
        u_pcm_a.cap_flat = 256'd0;
        u_pcm_a.tdm_out  = 1'b0;
        u_pcm_b.pcm_clk = 1'b0;
        u_pcm_b.pcm_fs  = 1'b0;
        u_pcm_b.shift   = 32'd0;
        u_pcm_b.pw_flat  = 256'd0;
        u_pcm_b.cap_flat = 256'd0;
        u_pcm_b.tdm_out  = 1'b0;
    end

    integer errors = 0;
    task expect32;
        input [31:0] got;
        input [31:0] want;
        input [1023:0] what;
        begin
            if (got !== want) begin
                $display("FAIL: %0s got %08h want %08h (t=%0t)", what, got, want, $time);
                errors = errors + 1;
            end
        end
    endtask

    task drive_and_check;
        input [31:0] l;
        input [31:0] r;
        integer i;
        begin
            pi_left  = l;
            pi_right = r;
            // 4 frames: Pi presents it, capture pipeline settles, the
            // TDM frame goes out, one spare.
            #(FRAME_NS * 4.0);
            expect32(u_rx_a.mem[0], l, "I2S: TDM8 slot 0 (PI_PCM_L)");
            expect32(u_rx_a.mem[1], r, "I2S: TDM8 slot 1 (PI_PCM_R)");
            expect32(u_rx_b.mem[0], l, "LJ:  TDM8 slot 0 (PI_PCM_L)");
            expect32(u_rx_b.mem[1], r, "LJ:  TDM8 slot 1 (PI_PCM_R)");
            for (i = 2; i < 8; i = i + 1) begin
                expect32(u_rx_a.mem[i], 32'd0, "I2S: TDM8 unused slot not silent");
                expect32(u_rx_b.mem[i], 32'd0, "LJ:  TDM8 unused slot not silent");
            end
        end
    endtask

    initial begin
        if ($test$plusargs("vcd")) begin
            $dumpfile("tb_pcm_reframe.vcd");
            $dumpvars(0, tb_pcm_reframe);
        end

        #(FRAME_NS * 3.0);                       // settle

        drive_and_check(32'h1234_5678, 32'h7FFF_FFFF);
        drive_and_check(32'h8000_0001, 32'hA5A5_5A5A);
        drive_and_check(32'hFFFF_FFFF, 32'h0000_0001);
        drive_and_check(32'h0000_0000, 32'hFFFF_FFFE);

        if (u_rx_a.frames < 8) begin
            $display("FAIL: receiver saw only %0d frames", u_rx_a.frames);
            errors = errors + 1;
        end
        if (u_rx_a.misframes != 0 || u_rx_b.misframes != 0) begin
            $display("FAIL: %0d/%0d mid-frame FS marks (frame length mismatch)",
                     u_rx_a.misframes, u_rx_b.misframes);
            errors = errors + 1;
        end

        $display("tb_pcm_reframe: %0d frames, %0d errors", u_rx_a.frames, errors);
        if (errors == 0) $display("tb_pcm_reframe: PASS");
        else             $display("tb_pcm_reframe: FAIL (%0d)", errors);
        $finish;
    end
endmodule

`default_nettype wire
