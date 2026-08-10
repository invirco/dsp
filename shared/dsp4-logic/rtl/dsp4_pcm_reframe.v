// dsp4_pcm_reframe.v — Pi PCM (I2S) to TDM8 re-framer (slot map A_I6)
//
// LOGIC masters the Pi's PCM interface as standard I2S (64 BCK/frame,
// BCK 3.072 MHz, LRCLK 48 kHz) and re-frames the stereo samples into
// slots 0 (PI_PCM_L) and 1 (PI_PCM_R) of the TDM8 line toward DSPA I6.
//
// I2S in: LRCLK changes on a BCK falling edge and the MSB of the new
// word is driven PCM_DATA_DELAY falling edges later, so a receiver
// sampling on rising edges sees the MSB at the (PCM_DATA_DELAY+1)'th
// rising edge after the LRCLK transition. PCM_DATA_DELAY=1 is Philips
// I2S — what the bcm2835 PCM block programs as CH1POS=1 in I2S mode.
// PCM_DATA_DELAY=0 is the left-justified variant; the parameter exists
// because CH1POS is programmable, so if bring-up shows the Pi framed
// differently this constant moves instead of the logic. Left = LRCLK
// low. Capture runs a frame behind playback onto the TDM line (one full
// stereo frame of latency, constant).
//
// Clocking: pcm_bck = sysclk/16 (3.072 MHz), pcm_lrck = 48 kHz, both
// launched on falling edges per the locked timing convention (the Pi
// samples/drives per I2S: data changes on falling BCK, sampled rising).
//
// TDM8 out: the bit launched on the falling edge of BCK8 period P is
// sampled by the DSP on the RISING edge of period P+1, and MFD=1 puts
// slot 0 bit 31 on the rising edge AFTER the one that reads FS high
// (period 255). So the launch at period P must carry the bit belonging
// to period P+1 — see `out_period` below. Verified in sim against
// model_tdm_rx (sim/tb_pcm_reframe.v).

module dsp4_pcm_reframe #(
    parameter integer PCM_DATA_DELAY = 1     // 1 = I2S, 0 = left-justified
) (
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
    // PCM BCK rising edge lands at frame_pos[3:0]==1; sampling one
    // sysclk early keeps the capture in the same BCK period while the
    // Pi's data has been stable for 7 sysclk (~142 ns) since its
    // falling-edge launch.
    wire pcm_bck_sample = (frame_pos[3:0] == 4'b0000); // BCK rising

    assign pcm_din = 1'b0;   // capture path to the Pi: future work

    // ---- I2S capture: one shift register + two holding registers ----
    // LRCLK goes LOW at the falling edge of BCK period 0 and HIGH at the
    // falling edge of period 32, so with the MSB delayed PCM_DATA_DELAY
    // periods the words are complete at:
    //   left  : period PCM_DATA_DELAY + 32
    //   right : period PCM_DATA_DELAY (of the FOLLOWING frame)
    localparam [5:0] LEFT_DONE  = PCM_DATA_DELAY + 32;
    localparam [5:0] RIGHT_DONE = PCM_DATA_DELAY;

    reg [31:0] shift;
    reg [31:0] left_q, right_q;      // captured previous frame
    always @(posedge sysclk) begin
        if (pcm_bck_sample) begin
            shift <= {shift[30:0], pcm_dout};
            if (frame_pos[9:4] == LEFT_DONE)
                left_q <= {shift[30:0], pcm_dout};
            if (frame_pos[9:4] == RIGHT_DONE)
                right_q <= {shift[30:0], pcm_dout};
        end
    end

    // ---- TDM8 output: slots 0/1 carry L/R, slots 2-7 zero ----
    // TDM8 frame: 256 BCK8 periods = frame_pos[9:2]; 8 slots x 32 bits,
    // so slot = period[7:5] and bit = period[4:0]. The launch at period
    // P drives the bit the DSP samples in period P+1 (MFD=1, see header).
    wire [7:0] out_period = frame_pos[9:2] + 8'd1;
    wire [2:0] slot   = out_period[7:5];
    wire [4:0] bit_ix = out_period[4:0];

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
