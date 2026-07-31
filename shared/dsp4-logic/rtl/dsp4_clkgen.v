// dsp4_clkgen.v — TDM clock generation for the DSP4 LOGIC CPLD (U3)
//
// 49.152 MHz XO in; generates the four clock roles (slot-map CG0-CG3):
//   TDM8  : BCK 12.288 MHz (/4), FS 48 kHz, 8 slots x 32 bits
//   TDM16 : BCK 24.576 MHz (/2), FS 48 kHz, 16 slots x 32 bits
//
// Timing conventions LOCKED per generated/dsp4_slot_map.vh:
//   - receivers sample on BCK RISING edge; we LAUNCH BCK-synchronous
//     outputs (FS, data) on the FALLING edge;
//   - MFD=1: FS is a one-BCK-wide pulse asserted one BCK period before
//     slot 0 bit 31 (frame-sync-early, matches SPORT MFD=1).
//
// Everything runs on the sysclk domain (49.152 MHz); BCKs are generated
// as registered divided clocks, and "falling edge" launches happen on
// the sysclk tick where the BCK register transitions 1->0. Frame length
// checks: TDM8 8x32=256 BCK8 = 1024 sysclk; TDM16 16x32=512 BCK16 =
// 1024 sysclk — one common 1024-cycle frame counter serves both.

module dsp4_clkgen (
    input  wire sysclk,        // 49.152 MHz XO
    input  wire rst_n,

    output reg  bck8,          // 12.288 MHz TDM8 bit clock
    output reg  bck16,         // 24.576 MHz TDM16 bit clock
    output reg  fs8,           // TDM8 frame sync (1 BCK8 wide, MFD=1)
    output reg  fs16,          // TDM16 frame sync (1 BCK16 wide, MFD=1)

    // Launch/sample strobes for data movers in the sysclk domain:
    output wire bck8_launch,   // sysclk tick of BCK8 falling edge
    output wire bck8_sample,   // sysclk tick of BCK8 rising edge
    output wire bck16_launch,
    output wire bck16_sample,
    output wire [9:0] frame_pos // sysclk position within the 1024-cycle frame
);

    // 1024-cycle frame counter (48 kHz)
    reg [9:0] cnt;
    always @(posedge sysclk or negedge rst_n) begin
        if (!rst_n)
            cnt <= 10'd0;
        else
            cnt <= cnt + 10'd1;
    end
    assign frame_pos = cnt;

    // BCK16 = sysclk/2 (toggles every cycle), BCK8 = sysclk/4.
    // cnt[0] high half = BCK16 high; cnt[1:0]==2'b1x = BCK8 high.
    always @(posedge sysclk or negedge rst_n) begin
        if (!rst_n) begin
            bck16 <= 1'b0;
            bck8  <= 1'b0;
        end else begin
            bck16 <= ~cnt[0];
            bck8  <= ~cnt[1];
        end
    end

    // Edge strobes (valid the sysclk cycle in which the new BCK value
    // appears on the registered output).
    assign bck16_sample = (cnt[0] == 1'b0);          // bck16 goes 0->1
    assign bck16_launch = (cnt[0] == 1'b1);          // bck16 goes 1->0
    assign bck8_sample  = (cnt[1:0] == 2'b00);       // bck8 0->1
    assign bck8_launch  = (cnt[1:0] == 2'b10);       // bck8 1->0

    // Frame syncs, MFD=1: assert during the LAST BCK period of the
    // frame so the receiver's slot 0 starts one BCK later, and launch
    // on the falling edge.
    //   TDM8:  BCK8 periods run cnt[9:2]; last period = 8'hFF.
    //   TDM16: BCK16 periods run cnt[9:1]; last period = 9'h1FF.
    always @(posedge sysclk or negedge rst_n) begin
        if (!rst_n) begin
            fs8  <= 1'b0;
            fs16 <= 1'b0;
        end else begin
            if (bck8_launch)
                fs8 <= (cnt[9:2] == 8'hFE);   // high through final period
            if (bck16_launch)
                fs16 <= (cnt[9:1] == 9'h1FE);
        end
    end

endmodule
