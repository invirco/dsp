// tb_clkgen.v — self-checking testbench for dsp4_clkgen.
//
// Asserts the LOCKED timing conventions rather than the implementation:
//   1. BCK8 = sysclk/4 (12.288 MHz), BCK16 = sysclk/2 (24.576 MHz).
//   2. One FS pulse per 48 kHz frame on each line, exactly one BCK wide.
//   3. FS reads high at exactly ONE BCK rising edge per frame (MFD=1
//      frame marker), and the frame is 256 BCK8 / 512 BCK16 long.
//   4. The launch strobe marks the sysclk boundary at which BCK falls,
//      and the sample strobe the boundary at which it rises — i.e. a
//      register clocked by *_launch changes its output exactly on the
//      BCK falling edge, which is what the "launch falling / sample
//      rising" convention requires.

`timescale 1ns/1ps
`default_nettype none

module tb_clkgen;

    // 49.152 MHz XO
    localparam real SYS_HALF = 10.1725;

    reg sysclk = 1'b0;
    always #(SYS_HALF) sysclk = ~sysclk;

    wire bck8, bck16, fs8, fs16;
    wire bck8_launch, bck8_sample, bck16_launch, bck16_sample;
    wire [9:0] frame_pos;

    dsp4_clkgen dut (
        .sysclk(sysclk), .bck8(bck8), .bck16(bck16),
        .fs8(fs8), .fs16(fs16),
        .bck8_launch(bck8_launch), .bck8_sample(bck8_sample),
        .bck16_launch(bck16_launch), .bck16_sample(bck16_sample),
        .frame_pos(frame_pos)
    );

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

    // MAX V macrocells power up CLEARED and the board gives U3 no reset;
    // model that explicitly (unset regs would otherwise stay X forever).
    initial begin
        dut.cnt   = 10'd0;
        dut.bck8  = 1'b0;
        dut.bck16 = 1'b0;
        dut.fs8   = 1'b0;
        dut.fs16  = 1'b0;
    end

    // ---- 1. BCK divide ratios, measured in sysclk cycles ----
    integer sysclk_ticks = 0;
    always @(posedge sysclk) sysclk_ticks = sysclk_ticks + 1;

    integer t_bck8 = -1, t_bck16 = -1;
    always @(posedge bck8) begin
        if (t_bck8 >= 0) check((sysclk_ticks - t_bck8) == 4, "BCK8 period != 4 sysclk");
        t_bck8 = sysclk_ticks;
    end
    always @(posedge bck16) begin
        if (t_bck16 >= 0) check((sysclk_ticks - t_bck16) == 2, "BCK16 period != 2 sysclk");
        t_bck16 = sysclk_ticks;
    end

    // ---- 3. FS seen by a receiver sampling on the BCK rising edge ----
    integer fs8_edges = 0, fs16_edges = 0;          // rising edges w/ FS high
    integer bck8_since_fs = -1, bck16_since_fs = -1;
    integer fs8_frames = 0, fs16_frames = 0;

    always @(posedge bck8) begin
        if (bck8_since_fs >= 0) bck8_since_fs = bck8_since_fs + 1;
        if (fs8 === 1'b1) begin
            fs8_edges = fs8_edges + 1;
            if (bck8_since_fs >= 0) begin
                check((bck8_since_fs == 256), "TDM8 frame != 256 BCK8 between FS marks");
                fs8_frames = fs8_frames + 1;
            end
            bck8_since_fs = 0;
        end
    end

    always @(posedge bck16) begin
        if (bck16_since_fs >= 0) bck16_since_fs = bck16_since_fs + 1;
        if (fs16 === 1'b1) begin
            fs16_edges = fs16_edges + 1;
            if (bck16_since_fs >= 0) begin
                check((bck16_since_fs == 512), "TDM16 frame != 512 BCK16 between FS marks");
                fs16_frames = fs16_frames + 1;
            end
            bck16_since_fs = 0;
        end
    end

    // ---- 2. FS pulse width, in sysclk cycles, vs one BCK period ----
    integer fs8_rise = -1, fs16_rise = -1;
    always @(posedge fs8)  fs8_rise  = sysclk_ticks;
    always @(negedge fs8)
        if (fs8_rise >= 0) check((sysclk_ticks - fs8_rise) == 4, "FS8 not 1 BCK8 wide");
    always @(posedge fs16) fs16_rise = sysclk_ticks;
    always @(negedge fs16)
        if (fs16_rise >= 0) check((sysclk_ticks - fs16_rise) == 2, "FS16 not 1 BCK16 wide");

    // ---- 4. launch/sample strobes vs the BCK edges they name ----
    reg bck8_prev, bck16_prev;
    reg l8 = 1'b0, s8 = 1'b0, l16 = 1'b0, s16 = 1'b0;
    always @(posedge sysclk) begin
        // A strobe asserted at cycle N must be followed by the named
        // transition between cycle N and N+1.
        if (l8 === 1'b1)  check((bck8_prev  === 1'b1) && (bck8  === 1'b0), "bck8_launch not on BCK8 1->0");
        if (s8 === 1'b1)  check((bck8_prev  === 1'b0) && (bck8  === 1'b1), "bck8_sample not on BCK8 0->1");
        if (l16 === 1'b1) check((bck16_prev === 1'b1) && (bck16 === 1'b0), "bck16_launch not on BCK16 1->0");
        if (s16 === 1'b1) check((bck16_prev === 1'b0) && (bck16 === 1'b1), "bck16_sample not on BCK16 0->1");
        bck8_prev  = bck8;
        bck16_prev = bck16;
        l8  = bck8_launch;
        s8  = bck8_sample;
        l16 = bck16_launch;
        s16 = bck16_sample;
    end

    // ---- run ----
    initial begin
        if ($test$plusargs("vcd")) begin
            $dumpfile("tb_clkgen.vcd");
            $dumpvars(0, tb_clkgen);
        end
        // 8 audio frames
        #(1024.0 * 2.0 * SYS_HALF * 8.5);

        // Frame rate: 1024 sysclk = 48 kHz -> 20833.3 ns
        check((fs8_frames >= 6) && (fs16_frames >= 6), "too few FS frames observed");

        $display("tb_clkgen: %0d TDM8 frames, %0d TDM16 frames, %0d errors",
                 fs8_frames, fs16_frames, errors);
        if (errors == 0) $display("tb_clkgen: PASS");
        else             $display("tb_clkgen: FAIL (%0d)", errors);
        $finish;
    end
endmodule

`default_nettype wire
