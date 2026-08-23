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
    parameter integer PCM_DATA_DELAY = 1,    // 1 = I2S, 0 = left-justified
    // Which TDM8 slots of tdm_in are de-framed to the Pi's L/R channels.
    // These are the Pi's stereo RETURN slots and they ship: the CM4
    // needs a send and a return, and the send (A_I6 slots 0/1) already
    // existed.
    // Pi CM4 stereo RETURN slots on the captured lane. B_O3 slots 2/3
    // per slot-map.csv (PI_RET_L / PI_RET_R): B_O3 is the emptiest TDM8
    // output lane -- only slots 0/1 were used, and both are provisional
    // DAC_MAIN -- so taking two costs nothing and leaves 4-7 spare.
    // Avoiding slots 0/1 keeps the return clear of DAC MAIN on D32,
    // where that lane becomes the real main DAC.
    parameter integer CAP_SLOT_L = 2,
    parameter integer CAP_SLOT_R = 3,
    // PI_TDM8 = 1 runs the CM4 link at 4x rate so it carries EIGHT
    // channels each way instead of two.
    //
    // The BCM2711 PCM block can only place two channels in a frame
    // (Broadcom peripherals sec.8; bcm2835_i2s_hw_params only ever writes
    // CH1_POS/CH2_POS), so eight channels cannot be had by lengthening
    // the frame. They CAN be had by shortening it: 2 x 32 bits at a
    // 192 kHz frame rate is 12.288 MHz -- the same bit rate as TDM8 at
    // 48 kHz -- so four Pi frames fit inside one DSP TDM8 frame and carry
    // its eight slots. The Pi runs -c 2 -r 192000 and interleaves eight
    // logical 48 kHz channels; LOGIC does the re-framing, as it already
    // does today.
    parameter integer PI_TDM8 = 0,
    // PI_SELFTEST = 1 feeds the Pi's capture from its OWN de-framed
    // playback words instead of the DSP lane, so aplay -> LOGIC ->
    // arecord closes without the DSP in it. That isolates the two
    // re-framing directions and duplex operation, which is exactly what
    // is unproven; the DSP path is measured separately. Evaluation only.
    parameter integer PI_SELFTEST = 0,
    // Extra BCK periods of delay on the capture launch, on top of
    // PCM_DATA_DELAY. MEASURED, not guessed: with 0, the CM4 recorded
    // 0xB4B40000 / 0xB4B40002 where the DSP was transmitting
    // 0x5A5A0000 / 0x5A5A0001 -- the expected words shifted LEFT exactly
    // one bit, 100% stable over 96,000 frames. Left-shifted by one means
    // the receiver started a bit early, so the launch needs one more BCK
    // of delay. The playback direction does not need it because it is
    // launched against a different edge of the same frame.
    parameter integer CAP_EXTRA_DELAY = 1
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
    input  wire        bck8_sample,  // sysclk strobe of BCK8 rising edge
    input  wire        tdm_in,       // TDM8 line to de-frame toward the Pi
    output reg         tdm_out
);

    // ---- PCM clock generation: BCK = sysclk/16, LRCLK = frame ----
    // frame_pos[3:0] counts the 16 sysclk per PCM BCK; [9:4] = 64 BCK.
    // In PI_TDM8 the Pi runs a 64-BCK frame at 12.288 MHz (192 kHz frame
    // rate): pcm_clk = sysclk/4, and frame_pos[7] is a 50% 192 kHz sync.
    // Four of those frames tile one 48 kHz DSP frame, selected by
    // frame_pos[9:8].
    always @(posedge sysclk) begin
        if (PI_TDM8) begin
            pcm_clk <= ~frame_pos[1];
            if (frame_pos[1:0] == 2'b10)        // BCK falling launch
                pcm_fs <= frame_pos[7];
        end else begin
            pcm_clk <= ~frame_pos[3];
            // LRCLK: low = left = first half of frame (I2S convention)
            if (frame_pos[3:0] == 4'b1000)      // PCM BCK falling launch
                pcm_fs <= frame_pos[9];          // low first half
        end
    end

    // Launch/sample strobes and the word position within the Pi frame,
    // chosen by mode so the datapaths below can stay common.
    wire pi_launch = PI_TDM8 ? (frame_pos[1:0] == 2'b10)
                             : (frame_pos[3:0] == 4'b1000);
    wire pi_sample = PI_TDM8 ? (frame_pos[1:0] == 2'b00)
                             : (frame_pos[3:0] == 4'b0000);
    wire [5:0] pi_word_pos = PI_TDM8 ? frame_pos[7:2] : frame_pos[9:4];
    wire [1:0] pi_subframe = frame_pos[9:8];   // which Pi frame in the DSP frame
    // PCM BCK rising edge lands at frame_pos[3:0]==1; sampling one
    // sysclk early keeps the capture in the same BCK period while the
    // Pi's data has been stable for 7 sysclk (~142 ns) since its
    // falling-edge launch.
    wire pcm_bck_sample = (frame_pos[3:0] == 4'b0000); // BCK rising

    // ---- Capture path: DSPB TDM8 slots -> Pi (pcm_din) ----
    //
    // PRODUCT FEATURE, built in every configuration: the CM4 needs a
    // stereo send AND return. It costs no pin and no PCB change -- B_O3
    // is an existing DSPB output already routed to LOGIC as dac_main, and
    // pcm_din is an existing net to Pi GPIO20.
    //
    // All eight slots are captured regardless of mode; the mode only
    // decides which pair is presented in a given Pi frame. In PI_TDM8 the
    // four Pi frames of a DSP frame carry slots (0,1) (2,3) (4,5) (6,7),
    // so the Pi sees all eight as a 192 kHz stereo stream.
    //
    // The transmitter runs MFD = 1, so slot s bit b is on the wire during
    // period (s*32 + b + 1); undo that +1 to index the incoming bit.
    wire [7:0] in_period = frame_pos[9:2] - 8'd1;
    wire [2:0] in_slot   = in_period[7:5];
    wire [4:0] in_bit    = in_period[4:0];

    // Flat 8x32 register file, NOT a Verilog array. A doubly-indexed
    // array (slot, then bit) makes the MAX V flow try to infer memory the
    // device does not have -- quartus_map segfaults after reporting
    // "Cannot find Memory Initialization File ... for ROM instance".
    // Flattened, the read is a plain 256:1 bit mux and the write a
    // 32-bit slice at a slot-aligned offset. MAX V registers power up
    // cleared, so no initialiser is needed (and an initialiser is itself
    // enough to trigger the ROM inference).
    reg [31:0]  cap_sh;
    reg [255:0] cap_flat;

    always @(posedge sysclk) begin
        if (bck8_sample) begin
            cap_sh <= {cap_sh[30:0], tdm_in};
            if (in_bit == 5'd31)
                cap_flat[{in_slot, 5'd0} +: 32] <= {cap_sh[30:0], tdm_in};
        end
    end

    wire [2:0] sel_l = PI_TDM8 ? {pi_subframe, 1'b0} : CAP_SLOT_L[2:0];
    wire [2:0] sel_r = PI_TDM8 ? {pi_subframe, 1'b1} : CAP_SLOT_R[2:0];

    // Launch on the PCM BCK FALLING edge so the Pi samples mid-bit on the
    // rising edge. CAP_EXTRA_DELAY is measured, not guessed -- see its
    // declaration.
    // CAP_EXTRA_DELAY compensates the DSP transmitter's framing and is
    // measured against it. In PI_SELFTEST the words come from the Pi's own
    // playback, never crossing the DSP, so applying it there would shift
    // the result by one bit -- which is exactly what the first duplex run
    // showed (captured words were the stimulus >> 1).
    wire [5:0] cap_extra = PI_SELFTEST ? 6'd0 : CAP_EXTRA_DELAY[5:0];
    wire [5:0] out_word_pos = pi_word_pos - PCM_DATA_DELAY[5:0] - cap_extra;
    // Hoisted out of the index expression: a ternary inside a
    // concatenation used as a bit select does not bind in all tools.
    wire [2:0] cap_sel = out_word_pos[5] ? sel_r : sel_l;
    wire [4:0] cap_bit = 5'd31 - out_word_pos[4:0];
    wire [7:0] cap_idx = {cap_sel, cap_bit};

    reg  pcm_din_r;
    always @(posedge sysclk) begin
        if (pi_launch)
            pcm_din_r <= PI_SELFTEST ? pw_flat[cap_idx] : cap_flat[cap_idx];
    end
    assign pcm_din = pcm_din_r;

    // ---- Pi -> LOGIC: de-frame the Pi's I2S into TDM8 slots ----
    // The word boundaries sit PCM_DATA_DELAY periods after the frame
    // sync, so within a Pi frame the left word completes at
    // PCM_DATA_DELAY+31 and the right at PCM_DATA_DELAY+63. The latter
    // wraps past the end of the frame, which is why the subframe index in
    // force when the LEFT word completed is held and reused for the
    // right -- by then pi_subframe has already moved on.
    // Word-complete positions, unchanged from the two-channel design:
    //   left  : PCM_DATA_DELAY + 32
    //   right : PCM_DATA_DELAY, of the FOLLOWING frame
    // The right word therefore lands after pi_subframe has already moved
    // on, so it is written to the PREVIOUS subframe's odd slot.
    localparam [5:0] LEFT_DONE  = PCM_DATA_DELAY[5:0] + 6'd32;
    localparam [5:0] RIGHT_DONE = PCM_DATA_DELAY[5:0];

    reg [31:0]  shift;
    reg [255:0] pw_flat;             // de-framed Pi words, by TDM8 slot
    wire [1:0] sub_prev = pi_subframe - 2'd1;
    wire [2:0] pw_sel_l = PI_TDM8 ? {pi_subframe, 1'b0} : 3'd0;
    wire [2:0] pw_sel_r = PI_TDM8 ? {sub_prev,    1'b1} : 3'd1;

    always @(posedge sysclk) begin
        if (pi_sample) begin
            shift <= {shift[30:0], pcm_dout};
            if (pi_word_pos == LEFT_DONE)
                pw_flat[{pw_sel_l, 5'd0} +: 32] <= {shift[30:0], pcm_dout};
            if (pi_word_pos == RIGHT_DONE)
                pw_flat[{pw_sel_r, 5'd0} +: 32] <= {shift[30:0], pcm_dout};
        end
    end

    // ---- TDM8 output toward DSPA I6 ----
    // 8 slots x 32 bits over frame_pos[9:2]; slot = period[7:5],
    // bit = period[4:0]. The launch at period P drives the bit the DSP
    // samples at P+1 (MFD = 1), hence the +1.
    //
    // In PI_TDM8 every slot carries Pi audio. Otherwise only slots 0/1 do
    // and the rest are silent, exactly as before.
    wire [7:0] out_period = frame_pos[9:2] + 8'd1;
    wire [2:0] slot   = out_period[7:5];
    wire [4:0] bit_ix = out_period[4:0];
    wire [4:0] tdm_bit = 5'd31 - bit_ix;
    wire [7:0] tdm_idx = {slot, tdm_bit};

    always @(posedge sysclk) begin
        if (bck8_launch) begin
            if (PI_TDM8 || slot < 3'd2)
                tdm_out <= pw_flat[tdm_idx];
            else
                tdm_out <= 1'b0;
        end
    end

endmodule
