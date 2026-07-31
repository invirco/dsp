// dsp4_pcm_reframe.v — Pi PCM (I2S) to TDM8 re-framer (slot map A_I6)
//
// LOGIC masters the Pi's PCM interface as standard I2S (64 BCK/frame,
// BCK 3.072 MHz, LRCLK 48 kHz) and re-frames the stereo samples into
// slots 0 (PI_PCM_L) and 1 (PI_PCM_R) of the TDM8 line toward DSPA I6.
//
// I2S in: MSB one BCK after LRCLK edge, 32-bit slots, left = LRCLK low.
// Capture runs a frame behind playback onto the TDM line (one full
// stereo frame of latency, constant).
//
// Clocking: pcm_bck = sysclk/16 (3.072 MHz), pcm_lrck = 48 kHz, both
// launched on falling edges per the locked timing convention (the Pi
// samples/drives per I2S: data changes on falling BCK, sampled rising).

module dsp4_pcm_reframe (
    input  wire        sysclk,       // 49.152 MHz
    input  wire [9:0]  frame_pos,    // from dsp4_clkgen (1024/frame)

    // Pi PCM pins (LOGIC masters)
    output reg         pcm_clk,      // 3.072 MHz to Pi
    output reg         pcm_fs,       // LRCLK 48 kHz to Pi
    input  wire        pcm_dout,     // Pi -> LOGIC (playback data)
    output wire        pcm_din,      // LOGIC -> Pi (capture, tied off)

    // TDM8 line toward DSPA I6 (launched with the TDM8 clock role)
    input  wire        bck8_launch,  // sysclk strobe of BCK8 falling edge
    output reg         tdm_out
);

    // ---- PCM clock generation: BCK = sysclk/16, LRCLK = frame ----
    // frame_pos[3:0] counts the 16 sysclk per PCM BCK; [9:4] = 64 BCK.
    always @(posedge sysclk) begin
        pcm_clk <= ~frame_pos[3];
        // LRCLK: low = left = first half of frame (I2S convention)
        if (frame_pos[3:0] == 4'b1000)          // PCM BCK falling launch
            pcm_fs <= frame_pos[9];              // low first half
    end
    wire pcm_bck_sample = (frame_pos[3:0] == 4'b0000); // BCK rising

    assign pcm_din = 1'b0;   // capture path to the Pi: future work

    // ---- I2S capture: two 32-bit shift registers ----
    reg [31:0] shift;
    reg [31:0] left_q, right_q;      // captured previous frame
    reg [5:0]  bit_cnt;              // 0..63 across the frame
    always @(posedge sysclk) begin
        if (pcm_bck_sample) begin
            bit_cnt <= frame_pos[9:4];
            shift   <= {shift[30:0], pcm_dout};
            // End of each 32-bit half: latch (I2S MSB delay of one BCK
            // handled by latching one bit later, at half-boundaries).
            if (frame_pos[9:4] == 6'd32)
                left_q <= {shift[30:0], pcm_dout};
            if (frame_pos[9:4] == 6'd0)
                right_q <= {shift[30:0], pcm_dout};
        end
    end

    // ---- TDM8 output: slots 0/1 carry L/R, slots 2-7 zero ----
    // TDM8 frame: 256 BCK8 periods = frame_pos[9:2]; slot = [9:7]...
    // 8 slots x 32 bits: slot index = bck8_period[7:5], bit = [4:0].
    wire [7:0] bck8_period = frame_pos[9:2];
    wire [2:0] slot = bck8_period[7:5];
    wire [4:0] bit_ix = bck8_period[4:0];

    always @(posedge sysclk) begin
        if (bck8_launch) begin
            case (slot)
                3'd0: tdm_out <= left_q[5'd31 - bit_ix];
                3'd1: tdm_out <= right_q[5'd31 - bit_ix];
                default: tdm_out <= 1'b0;
            endcase
        end
    end

endmodule
