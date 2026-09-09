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

// Design-ID defaults. build.sh overrides both with --verilog_macro; an
// unstamped build reads back DESIGN_ID = 0, which the reader treats as
// "no identity in this bitstream" rather than as a hash that happens to
// be zero.
`ifndef DSP4_DESIGN_ID
 `define DSP4_DESIGN_ID 32'h0000_0000
`endif
`ifndef DSP4_CFG_BITS
 `define DSP4_CFG_BITS 16'h0000
`endif

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
    // PCM_DATA_DELAY.
    //
    // This was 1, and it was compensation for a bug rather than for the
    // link. 2026-08-23 the CM4 recorded 0xB4B40000 / 0xB4B40002 where the
    // DSP was transmitting 0x5A5A0000 / 0x5A5A0001 -- the expected words
    // shifted LEFT exactly one bit, 100% stable over 96,000 frames -- and
    // one more BCK of launch delay made the recording read correctly. It
    // did, but the shift was never in the launch: `in_period` decoded the
    // incoming TDM one BCK period early (see below), so cap_flat[s] held
    // {slot_s[30:0], slot_s+1[31]} and the extra BCK slid the read-out
    // back over it. The two errors cancelled in every bit except the top
    // one, which came from the OTHER slot -- invisible on every word the
    // bench ever sent, because all of them had bit 31 clear.
    //
    // With `in_period` corrected the link is plain I2S and this is 0. It
    // stays a parameter, not a constant, because the Pi's CH1POS is
    // programmable and this is the knob if a future CM4 frames differently.
    parameter integer CAP_EXTRA_DELAY = 0,
    // Design identity, read back off the part (see the KNOCK block below).
    // Both are GENERATED by build.sh and passed in as Verilog macros, so the
    // value in the register is the value in the manifest by construction and
    // has never been typed by hand. Defaults are what a hand-run iverilog or
    // an un-parameterised Quartus run produces, and 0 is reserved to mean
    // "this build did not stamp an ID".
    parameter [31:0] DESIGN_ID = `DSP4_DESIGN_ID,
    parameter [15:0] CFG_BITS  = `DSP4_CFG_BITS
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
    // Period indices name the BCK period in which a bit is SAMPLED, which
    // is the same convention `out_period` uses on the transmit side (there
    // the launch is one period earlier, hence its +1). MFD = 1 puts slot 0
    // bit 31 on the rising edge AFTER the one that reads FS high, and FS is
    // high through period 255, so slot 0 bit 31 is sampled at period 0 and
    // slot s bit b at period (s*32 + 31 - b). No offset belongs here.
    //
    // It carried -8'd1 until 2026-09-09, which shifted every captured word
    // one bit left and pulled the next slot's MSB into its LSB; see
    // CAP_EXTRA_DELAY above for how that hid, and sim/tb_pcm_capture.v for
    // the check that now catches it. Nothing had ever simulated this
    // direction -- tb_pcm_reframe leaves tdm_in dangling.
    wire [7:0] in_period = frame_pos[9:2];
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

    // ---- Design-ID register, and the one path there is to read it ----
    //
    // S5-9: until now "which bitstream is running" cost a measurement --
    // flash, then infer identity from how the capture behaves. That is
    // sound but indirect, and it cannot distinguish two builds that differ
    // in something the capture does not expose.
    //
    // MAX V has no configuration readback over SVF, the DSPs have no link
    // into this CPLD (the S-MCU SPI pins ISPI0/ISPI1/ICS_L are provisioned
    // and unimplemented), and the TEST pins land on a DNP header. The ONE
    // path off this part that exists today and needs no hands is the CM4's
    // PCM capture. So the register is read by KNOCKING on the link:
    //
    //   the Pi plays the 64-bit pair {L = KNOCK_L, R = KNOCK_R} for a few
    //   frames; LOGIC answers with {L = DESIGN_ID, R = {ID_MAGIC, CFG_BITS}}
    //   for the next 128 Pi frames, then returns to audio.
    //
    // Shipping-safe by construction and by scope: the knock is a specific
    // 64-bit word pair (KNOCK_R is the exact bit-inverse of KNOCK_L), a
    // false trigger costs 128 frames -- 2.7 ms -- of the CM4's OWN return
    // stream, and nothing on the DSP-facing side, the DAC lanes, the NET
    // lanes or the panel is touched in any way. It is therefore built in
    // every configuration, which is the point: every future flash, shipping
    // or not, answers "what are you?" in one aplay + one arecord.
    localparam [31:0] KNOCK_L  = 32'hD5D5_1D1D;
    localparam [31:0] KNOCK_R  = ~KNOCK_L;      // 32'h2A2A_E2E2
    localparam [15:0] ID_MAGIC = 16'hD594;      // marks the reply frame

    // Checked one Pi word after the right-hand word lands, so both halves
    // of the pair are settled in pw_flat and the compare is against
    // registers, not against a word still shifting in.
    wire knock_hit = pi_sample
                     && (pi_word_pos == (PCM_DATA_DELAY[5:0] + 6'd1))
                     && (pw_flat[31:0]  == KNOCK_L)
                     && (pw_flat[63:32] == KNOCK_R);

    reg [7:0] id_count;
    wire id_reply = (id_count != 8'd0);
    always @(posedge sysclk) begin
        if (knock_hit)
            id_count <= 8'd128;
        else if (cap_snap && id_reply)
            id_count <= id_count - 8'd1;
    end

    // ---- FRAME-LOCKED SNAPSHOT -- this is not decoration ----
    //
    // cap_flat is rewritten slot by slot as the DSP frame arrives: slot s
    // completes at frame_pos = (s+1)*128. The Pi's read-out of one 32-bit
    // word spans nearly the whole frame (bit 31 launches around frame_pos
    // 32, bit 0 around 536), so for most CAP_SLOT choices the register the
    // read-out is walking gets OVERWRITTEN part-way through, and the word
    // the Pi records is SPLICED from two consecutive DSP frames at a fixed
    // bit position.
    //
    // Measured on the part 2026-09-09, rev C, PI_MAINCAP (slots 0/1), with
    // the DSP alternating two known words A and B: the CM4 recorded
    // {A[31:25], B[24:0]} and {B[31:25], A[24:0]} -- never A or B. Slot 0
    // completes at frame_pos 128, which is out_word_pos 6, which is bit 25.
    // The same arithmetic puts the shipping return (slot 2, complete at
    // frame_pos 384) at bit 9, so the product capture path had the defect
    // too, one octave quieter.
    //
    // The fix is to read a SNAPSHOT, never the live register file. Both
    // presented slots are latched together, one Pi word before the left
    // read-out starts (out_word_pos 63 -- the last bit of the right word,
    // which still launches from the OLD register, so nothing tears there
    // either). A recorded stereo frame is then a coherent pair from ONE
    // DSP frame, at the cost of one extra frame of constant latency.
    //
    // PI_SELFTEST is bit-identical before and after: its source words are
    // written at frame_pos 528 (L) and 16 (R), both outside the read-out
    // window, so the snapshot picks up exactly the words the live read
    // would have. That is what makes the fix testable -- _pisel must not
    // move.
    wire [31:0] cap_src_l = PI_SELFTEST ? pw_flat[{sel_l, 5'd0} +: 32]
                                        : cap_flat[{sel_l, 5'd0} +: 32];
    wire [31:0] cap_src_r = PI_SELFTEST ? pw_flat[{sel_r, 5'd0} +: 32]
                                        : cap_flat[{sel_r, 5'd0} +: 32];
    wire cap_snap = pi_launch && (out_word_pos == 6'd63);

    reg [31:0] cap_hold_l, cap_hold_r;
    always @(posedge sysclk) begin
        if (cap_snap) begin
            cap_hold_l <= id_reply ? DESIGN_ID : cap_src_l;
            cap_hold_r <= id_reply ? {ID_MAGIC, CFG_BITS} : cap_src_r;
        end
    end

    // Hoisted out of the index expression: a ternary inside a
    // concatenation used as a bit select does not bind in all tools.
    wire [31:0] cap_word = out_word_pos[5] ? cap_hold_r : cap_hold_l;
    wire [4:0]  cap_bit  = 5'd31 - out_word_pos[4:0];

    reg  pcm_din_r;
    always @(posedge sysclk) begin
        if (pi_launch)
            pcm_din_r <= cap_word[cap_bit];
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
