// tb_pcm_drive.v — self-checking testbench for the DRIVE_ALL stimulus tap.
//
//   model_pi_i2s_tx -> [pcm_dout] -> dsp4_pcm_reframe -> [tdm_drive] -> model_tdm_rx
//
// `tdm_drive` is the broadcast copy of the de-framed Pi stream that the
// DRIVE_ALL build puts on EVERY DSPA input lane, so one stereo playback
// on the CM4 drives all of chip 1's input kernels (S19's driven-capacity
// instrument). The claim it has to earn is exactly:
//
//   * all EIGHT TDM8 slots carry audio — not two, which is what the
//     product tap does — because a slot left silent is a strip left on
//     its cheap branch and the capacity number is then a silence number
//     again for that strip;
//   * even slots carry L and odd slots carry R, so the eight slots are
//     not eight copies of one sample and a per-slot mix-up in the index
//     arithmetic cannot hide behind them being identical;
//   * the product tap `tdm_out` is UNCHANGED by the new register —
//     slots 0/1 and six silent slots — so the same reframer serves the
//     shipping build and this one.
//
// Framing, launch edge and receiver conventions are the shared models',
// not this file's: if the RTL and model_tdm_rx disagree, the RTL is
// wrong.

`timescale 1ns/1ps
`default_nettype none

module tb_pcm_drive;

    localparam real SYS_HALF = 10.1725;      // 49.152 MHz
    localparam real FRAME_NS = 1024.0 * 2.0 * SYS_HALF;

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

    reg [31:0] pi_left  = 32'h0000_0000;
    reg [31:0] pi_right = 32'h0000_0000;

    wire pcm_clk, pcm_fs, pcm_din, pcm_dout, tdm_out, tdm_drive;

    dsp4_pcm_reframe #(.PCM_DATA_DELAY(1)) u_pcm (
        .sysclk(sysclk), .frame_pos(frame_pos),
        .pcm_clk(pcm_clk), .pcm_fs(pcm_fs),
        .pcm_dout(pcm_dout), .pcm_din(pcm_din),
        .bck8_launch(bck8_launch), .tdm_out(tdm_out), .tdm_drive(tdm_drive)
    );
    model_pi_i2s_tx #(.DATA_DELAY(1)) u_pi (
        .bck(pcm_clk), .ws(pcm_fs),
        .left(pi_left), .right(pi_right), .sd(pcm_dout)
    );
    // The lane every DSPA input sees in the DRIVE_ALL build ...
    model_tdm_rx #(.SLOTS(8)) u_rx_drv (.bck(bck8), .fs(fs8), .d(tdm_drive));
    // ... and the product tap beside it, as the control.
    model_tdm_rx #(.SLOTS(8)) u_rx_prd (.bck(bck8), .fs(fs8), .d(tdm_out));

    // power-up-cleared state (no reset on U3)
    initial begin
        u_clkgen.cnt    = 10'd0;
        u_clkgen.bck8   = 1'b0;
        u_clkgen.bck16  = 1'b0;
        u_clkgen.fs8    = 1'b0;
        u_clkgen.fs16   = 1'b0;
        u_pcm.pcm_clk   = 1'b0;
        u_pcm.pcm_fs    = 1'b0;
        u_pcm.shift     = 32'd0;
        u_pcm.pw_flat   = 256'd0;
        u_pcm.cap_flat  = 256'd0;
        u_pcm.tdm_out   = 1'b0;
        u_pcm.tdm_drive = 1'b0;
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
            #(FRAME_NS * 4.0);
            for (i = 0; i < 8; i = i + 1)
                expect32(u_rx_drv.mem[i], (i % 2) ? r : l,
                         "DRIVE_ALL: slot does not carry the Pi word");
            // the product tap is unchanged by the new register
            expect32(u_rx_prd.mem[0], l, "product tap: slot 0 (PI_PCM_L)");
            expect32(u_rx_prd.mem[1], r, "product tap: slot 1 (PI_PCM_R)");
            for (i = 2; i < 8; i = i + 1)
                expect32(u_rx_prd.mem[i], 32'd0, "product tap: unused slot not silent");
        end
    endtask

    initial begin
        if ($test$plusargs("vcd")) begin
            $dumpfile("tb_pcm_drive.vcd");
            $dumpvars(0, tb_pcm_drive);
        end

        #(FRAME_NS * 3.0);

        // Full scale both ways is the stimulus the capacity rows use, so
        // it is the first case; the others prove it is the DATA and not a
        // constant that reaches the slots.
        drive_and_check(32'h7FFF_FFFF, 32'h8000_0000);
        drive_and_check(32'h1234_5678, 32'h0BAD_F00D);
        drive_and_check(32'hFFFF_FFFF, 32'h0000_0001);
        drive_and_check(32'h0000_0000, 32'h0000_0000);   // silence stays silent

        if (u_rx_drv.frames < 8) begin
            $display("FAIL: receiver saw only %0d frames", u_rx_drv.frames);
            errors = errors + 1;
        end
        if (u_rx_drv.misframes != 0) begin
            $display("FAIL: %0d mid-frame FS marks", u_rx_drv.misframes);
            errors = errors + 1;
        end

        $display("tb_pcm_drive: %0d frames, %0d errors", u_rx_drv.frames, errors);
        if (errors == 0) $display("tb_pcm_drive: PASS");
        else             $display("tb_pcm_drive: FAIL (%0d)", errors);
        $finish;
    end
endmodule

`default_nettype wire
