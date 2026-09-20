// dsp4_logic_top.v — DSP4 LOGIC CPLD (U3, 5M1270ZT144C4N) top level
//
// Architecture per the rev C schematic (LOGIC sheet, page 2/10):
//  - The inter-chip mix fabric (DSPA O0-7 -> DSPB I0-7) is DIRECT PCB
//    routing between the DSPs and does NOT pass through this CPLD.
//  - LOGIC owns: all 8 BCK/FS pairs (BCKI/FSI 0-7), the DSPA input
//    lines I[0..7], the DSPB output lines O[0..7], converter lanes
//    AD0-3 / DA0-3, network lanes NI/NO[0..3], the codec pair on
//    PLL8_0/PLL8_1, MEMS, the Pi PCM port and DSP_CLK.
//  - There is NO reset input: MAX V registers power up cleared.
//
// Slot map (generated/dsp4_slot_map.vh, hash-pinned): DSPA in — I0-I3
// = AD0-2 / NET (AD3 lane is NET-only on D24), I4 = codec return,
// I5 = snake (D32), I6 = Pi PCM (re-framed), I7 = MEMS. DSPB out —
// O0 -> DA0, O1 -> DA3 (DA1/DA2 spare on D24), O2 -> codec (D24) /
// snake (D32), O3 -> DAC MAIN (no D24 sink by design; parked on an
// X-logic pin), O4-7 -> NO0-3.
//
// Input-lane source selection is FIXED per product (D24: lanes 0-2
// ADC, lane 3 NET; input patching is a DSP-side product-config
// concern). Runtime lane muxing, if ever needed, arrives via the
// provisioned S-MCU SPI interface (ISPI0/ISPI1/ICS_L pins) — not
// implemented. Product personality via the S4 line (S-MCU driven,
// PROVISIONAL until the S-MCU firmware defines it).
//
// UART pass-through pins (SRX/MRX/MHRX/MHTX/STRX/PTRX) and the H1S2
// harness are TODO(uart-passthrough) — routing matrix not yet defined.

`default_nettype none

module dsp4_logic_top (
    input  wire        sysclk,      // pin 88, 49.152 MHz XO

    // ---- Converter / option-slot clock pair (U3 pins 142 and 141) ----
    //
    // THESE WERE INPUTS, AND THAT IS WHY NO CONVERTER CAN WORK. The rev C
    // LOGIC sheet prints IC0-IC2 / IL0-IL1 beside pins 87/142/85/141/81
    // and this design read all five as format-config STRAPS. The copper
    // says otherwise for two of them (mx26 docs/d24-netlist-global.md (b)
    // and (e), docs/d24-cpld-fanout.csv, netlist 2026-09-11):
    //
    //   pin 142 = board net C1. Fans out through five 33R taps: R111 to
    //             the ADC/DAC FPC, and R65/R66/R67/R61 to BCK_1 (slot 2),
    //             BCK_2 (slot 1), BCK_3 (slot 3), BCK_4 (D32 header J33).
    //   pin 141 = board net L0. Same shape: R112 to the FPC, R62/R63/R64
    //             /R60 to FS_1/FS_2/FS_3/FS_4.
    //
    // U3.142 and U3.141 are the ONLY active device pins on those two
    // nets. Nothing else can drive them, so as inputs the converters and
    // all three option slots get no bit clock and no frame sync at all.
    // That the ADC lanes pass through this CPLD as a plain WIRE
    // (i_dspa[0] = ad[0]) is the same fact from the other side: the
    // converter frame has to BE the DSP frame, which it can only be if
    // one generator makes both.
    //
    // The three that really are spare are pins 87 (C0), 85 (C2) and 81
    // (L1): single-pin nets, routed to nothing, the second and third
    // clock pairs the design reserved and never used. They are dropped
    // from the port list here rather than read as straps -- an input pin
    // on a net with no driver samples noise -- and the qsf's global
    // RESERVE_ALL_UNUSED_PINS leaves them tri-stated with a weak pull-up.
    output wire        conv_bck,    // pin 142 (C1): 12.288 MHz, TDM8
    output wire        conv_fs,     // pin 141 (L0): 48 kHz frame sync
    input  wire        strap_d32,   // S4: product personality (PROV.)

    output wire        dsp_clk,     // pin 140 -> both DSPs' SYS_CLKIN0

    // DSP-side clock pairs (schematic BCKI/FSI index)
    output wire [7:0]  bcki,
    output wire [7:0]  fsi,

    output wire [7:0]  i_dspa,      // LOGIC -> DSPA I0..I7
    input  wire [7:0]  o_dspb,      // DSPB O0..O7 -> LOGIC

    input  wire [3:0]  ad,          // AD0..AD3 (AD3 unused on D24)
    output wire [3:0]  da,          // DA0..DA3 (DA1/DA2 spare on D24)

    input  wire [3:0]  ni,          // NET in lanes
    output wire [3:0]  no,          // NET out lanes

    input  wire        cdc_o,       // PLL8_0: codec ADC -> DSPA I4
    output wire        cdc_i,       // PLL8_1: DSPB O2 -> codec (D24)

    input  wire        snake_in,    // D32 snake return (X-logic, PROV.)
    output wire        snake_out,   // D32 snake out    (X-logic, PROV.)
    output wire        dac_main,    // B_O3 lane, parked (X-logic, PROV.)

    input  wire        mems,        // ADAU7302 TDM8 (slot 5)

    // Pi PCM (LOGIC masters; roles per hardware-map: PCM0=CLK,
    // PCM1=DOUT (Pi->LOGIC), PCM2=DIN (LOGIC->Pi), PCM3=FS)
    output wire        pcm_clk,
    output wire        pcm_fs,
    input  wire        pcm_dout,
    output wire        pcm_din,

    output wire        blink_led,   // heartbeat -> LD1

    // Bring-up test points, pins 13/12/8/7 -> J1/J2 P17-P20 -> D24
    // Digital J15 (a DNP DIL254-10: pin 1/2 = +3V3, odd 3-9 = GND, even
    // 4-10 = TEST1..TEST4, so every signal has a ground beside it).
    // Nothing else on either board drives these nets.
    output wire [3:0]  test         // {TEST4, TEST3, TEST2, TEST1}
);

    `include "../generated/dsp4_slot_map.vh"

    // ---- Clocks ----
    wire bck8, bck16, fs8, fs16;
    wire bck8_launch, bck8_sample, bck16_launch, bck16_sample;
    wire [9:0] frame_pos;

    dsp4_clkgen u_clkgen (
        .sysclk       (sysclk),
        .bck8         (bck8),
        .bck16        (bck16),
        .fs8          (fs8),
        .fs16         (fs16),
        .bck8_launch  (bck8_launch),
        .bck8_sample  (bck8_sample),
        .bck16_launch (bck16_launch),
        .bck16_sample (bck16_sample),
        .frame_pos    (frame_pos)
    );

    // ---- DSP clock: SYS_CLKIN0 = sysclk / 2 = 24.576 MHz ----
    // The ADSP-2156x CLKIN range is fCKIN = 20-30 MHz (datasheet Rev. A
    // Table 23, crystal and external clock alike). The raw 49.152 MHz XO
    // is OUT OF RANGE: at reset the CGU defaults to MSEL = 60, DF = 0, so
    // PLLCLK would be 49.152 x 60 = 2.95 GHz and the PLL cannot lock — a
    // part in that state never runs its boot ROM. Divided by 2 the same
    // default gives 24.576 x 60 = 1.47 GHz, in range, and the clock stays
    // audio-rational (512 x 48 kHz).
    //
    // A single toggle flop, registered straight to the pin: exact 50 %
    // duty (the datasheet asks 45-55 %) and glitch-free by construction.
    // U3 has no reset — MAX V macrocells power up cleared — so no reset
    // term here, matching the rest of this design.
    // `preserve` keeps this its own macrocell: without it the synthesiser
    // spots that hb[0] toggles identically and merges the two, putting the
    // DSPs' only clock on an LE inside the heartbeat counter's carry chain.
    // Functionally the same, but this is the most critical net on the card
    // — 1 LE buys it a dedicated flop and a direct route to pin 140.
    reg dsp_clk_q /* synthesis preserve */;
    always @(posedge sysclk)
        dsp_clk_q <= ~dsp_clk_q;
    assign dsp_clk = dsp_clk_q;

    // Clock pair roles. BCKI/FSI 0-3 serve DSPA, 4-7 serve DSPB; per
    // DSP the four pairs are {DAI0-in, DAI0-out, DAI1-in, DAI1-out}.
    // DSPA: in = TDM8 (ADC/superset), out = TDM16 (mix fabric).
    // DSPB: in = TDM16 (mix fabric), out = TDM8 (DAC/codec/NET).
    // Index<->DSP-pin pairing is fixed by the PCB; verify the
    // in/out order of each pair at bring-up (swap here if needed).
    assign bcki = {bck8, bck16, bck8, bck16,    // 7..4: DSPB
                   bck16, bck8, bck16, bck8};   // 3..0: DSPA
    assign fsi  = {fs8, fs16, fs8, fs16,
                   fs16, fs8, fs16, fs8};

    // ---- CDC_O WITNESS (S81) ----
    //
    // The converters have been dark since S71 and S80 bisected the fault to
    // UPSTREAM OF THIS CPLD: under `driveall` every slot of i_dspa[4] carries
    // the stimulus at exactly -6.02 dBFS, so the SHARC pin, SPORT, RX DMA,
    // slot map and graph buffers are good end to end, and on the shipping
    // bitstream the same lane reads exact digital zero. What nobody could say
    // without a scope on the converter board was whether `cdc_o` -- the
    // codec's own data return, the one thing on the far side of the bisect
    // this part can actually SEE -- carries anything at all.
    //
    // WHAT THIS CAN AND CANNOT WITNESS, stated because the dispatch asked for
    // "BCLK/FS present at the codec": conv_bck and conv_fs are OUTPUTS of
    // this CPLD. It knows it is generating them; it cannot know they arrive
    // at the codec's pins, and nothing in a MAX V can. What it can witness is
    // the consequence -- a codec that is clocked and converting drives cdc_o,
    // a codec that is not leaves it static -- and that is the measurement
    // below. A static lane does NOT by itself distinguish "no clock" from "no
    // conversion"; taken with the SPI read arm (S81 gate 2), which has the
    // codec answering its own register image with RSTN set, it narrows to the
    // clock/frame pair or the analog rails.
    //
    // Three statistics per 48 kHz frame, which is what separates the cases a
    // single "is it zero" bit would fuse together:
    //   ones     bit periods in the frame with cdc_o high -- 0 is exact
    //            digital silence, 256 is stuck high, anything between is data
    //   toggles  transitions in the frame -- a stuck lane has none whatever
    //            its level, so this separates "tied off" from "carrying zero
    //            samples in a live frame"
    //   max      high-water mark of `ones` since power-up, so a single burst
    //            of activity between two knocks is not averaged away
    //
    // Plus a free-running frame counter, which is the INSTRUMENT'S OWN
    // negative control: if two knocks a few tens of milliseconds apart return
    // the same counter, the witness is dead and its zeros mean nothing. The
    // S80 lesson is that an instrument answering static zero on a build where
    // it cannot work is worse than no instrument, and a counter that must
    // move is the cheapest guard against being that.
    localparam [15:0] CDC_MAGIC = 16'hCD04;

    reg        cdc_o_q;
    reg [8:0]  cdc_ones_c, cdc_tog_c;      // this frame; 0..256 needs 9 bits
    reg [8:0]  cdc_ones_l, cdc_tog_l;      // the last COMPLETE frame
    reg [8:0]  cdc_ones_max;               // high-water since power-up
    reg [15:0] cdc_frames;                 // free-running, 48 kHz

    // Power-up state stated rather than inherited -- see the note beside
    // cdc_count in dsp4_pcm_reframe.v. MAX V comes up cleared; saying so
    // keeps simulation and silicon in agreement and keeps an unwritten
    // counter from propagating X into the capture word.
    initial begin
        cdc_o_q = 1'b0;
        cdc_ones_c = 9'd0; cdc_tog_c = 9'd0;
        cdc_ones_l = 9'd0; cdc_tog_l = 9'd0;
        cdc_ones_max = 9'd0;
        cdc_frames = 16'd0;
    end

    // cdc_o is sampled on the same edge the DSP samples the lane on, so the
    // count is of the bit periods the DSP itself sees and not of a phase
    // nothing reads. If bck8_sample and the frame boundary land on the same
    // sysclk the clear below wins and one sample of 256 is dropped; that is
    // a 0.4 % error on a number whose whole job is zero-versus-not-zero.
    wire cdc_frame_end = (frame_pos == 10'd1023);

    always @(posedge sysclk) begin
        if (bck8_sample) begin
            cdc_o_q <= cdc_o;
            if (cdc_o)             cdc_ones_c <= cdc_ones_c + 9'd1;
            if (cdc_o != cdc_o_q) cdc_tog_c  <= cdc_tog_c  + 9'd1;
        end
        if (cdc_frame_end) begin
            cdc_ones_l   <= cdc_ones_c;
            cdc_tog_l    <= cdc_tog_c;
            if (cdc_ones_c > cdc_ones_max) cdc_ones_max <= cdc_ones_c;
            cdc_ones_c   <= 9'd0;
            cdc_tog_c    <= 9'd0;
            cdc_frames   <= cdc_frames + 16'd1;
        end
    end

    // The two words the knock hands back. cdc_frames[15:9] advances every
    // 10.7 ms, so any two knocks more than that apart MUST differ -- a fast
    // bit would alias and prove nothing.
    wire [31:0] cdc_wit_l = {7'd0, cdc_ones_l, 7'd0, cdc_ones_max};
    wire [31:0] cdc_wit_r = {CDC_MAGIC, cdc_tog_l, cdc_frames[15:9]};

    // ---- ad[0..2] WITNESS (S84, DSP4_AD_WITNESS) ----
    //
    // The same instrument as the cdc_o witness above, pointed at the OTHER
    // converter return: the three AK5558 TDM8 lanes. S83 and S84 read every
    // `_buf_C1_IN_*` lane on all three bitstreams this bench has ever
    // carried -- the two current ones and `s41_mhrx_pullup_off`, which the
    // flash log says it lived on from 2026-09-13 to 2026-09-19 including the
    // day S54-S58 measured real preamp noise -- and got EXACT DIGITAL ZERO on
    // all 32 mic lanes every time, rails up, 595 chain unmuted at gain 63,
    // while the four codec lanes carried their own dithered floor in the same
    // pass. Everything a desk or the SPI link can ask has been asked. This is
    // the one question left that needs no scope: are the AK5558 output pins
    // moving AT ALL?
    //
    // ad[0..2] arrive at this part and pass through it as a plain wire
    // (`i_dspa[n] = net_sel[n] ? ni[n] : ad[n]`), so the CPLD can see them and
    // nothing else on the card can. A MAX V has no readback and the TEST pins
    // land on a DNP header, so the witness rides the one path off this part
    // that needs no hands -- the CM4 PCM knock, a third word pair.
    //
    // ONE LANE PER KNOCK, AND FROM S85 ONE EDGE PER KNOCK. Three lanes x
    // (ones, toggles, max) plus the frame counter does not fit in 64 bits at
    // a precision worth having, and the cdc witness's numbers are the right
    // ones. So the knock's low bits SELECT what is answered about -- bits
    // 1:0 the lane, bit 2 the sampling edge (S85) -- and the reply is the cdc
    // reply's exact shape, with both selectors echoed back in the spare bits
    // of the left word as a transcription guard. Six knocks, six readings,
    // same resolution as cdc_o, all six banks counting the same pass.
    //
    // WHAT THE NUMBERS SEPARATE, exactly as for cdc_o:
    //   ones 0,   toggles 0    the lane is at exact digital zero
    //   ones 256, toggles 0    the lane is stuck HIGH -- a different fault
    //   ones >0,  toggles >0   the lane is carrying data, i.e. the ADC is
    //                          clocked, out of reset, and converting
    //
    // WHAT IT CANNOT WITNESS, said here rather than discovered later. The
    // frame counter below counts fs8 -- and `conv_fs = fs8`, an OUTPUT of
    // this part. It therefore witnesses that this CPLD's clock generator is
    // running and framing, NOT that the bit clock and frame sync arrive at
    // the AK5558 pins; U3.142/U3.141 are the only drivers on those nets and
    // nothing in a MAX V can see the far end of a net it drives. That is the
    // same limit the cdc_o witness carries and it is why the probe list in
    // the report names U3 pins 141/142 whatever this answers.
    //
    // What makes the counter worth its bits is the OTHER direction: it is the
    // instrument's own negative control. S80's lesson (finding S80-19) is
    // that an instrument answering static zero on a build where it cannot
    // work is worse than no instrument. Two knocks more than ~11 ms apart
    // MUST return different counter values, and the reader refuses to report
    // the zeros as a measurement if they do not.
    localparam [15:0] AD_MAGIC = 16'hAD07;

    // BUILT IN EVERY CONFIGURATION, SHIPPING INCLUDED (hub ruling S84-N1).
    // The argument is the cdc_o witness's: an instrument that only exists in a
    // special build is an instrument nobody has when they need it, and every
    // session from S71 to S85 has had to flash something before it could ask
    // the one question that mattered. The knock costs nothing at runtime -- it
    // is a specific 64-bit word pair on the CM4 link that cannot occur in
    // audio, and the counters are read-only.
    //
    // IT IS NOT FREE IN AREA, AND THE NUMBER IS THE POINT OF SAYING SO:
    // measured on this part, shipping without it fits in 521 of 1,270 LEs
    // (41 %) at Fmax 68.56 MHz and with it in 882 (69 %) at 67.44 MHz. That is
    // +361 LEs, 28 points of the device, for six banks of counters. The S84
    // form -- three lanes, one edge -- was +174. Both clear the 49.152 MHz
    // sysclk by a wide margin, so this is an area decision and not a timing
    // one, and it is recorded in the S85 report as a 🟡 for the hub rather
    // than taken quietly here.
    //
    // TWO EDGES, NOT ONE (S85). S84 counted ad[0..2] on `bck8_sample` alone,
    // on the argument that this is the edge the DSP samples the lane on and
    // that the two witnesses are comparable only if they count the same
    // thing. Both halves of that are still true and the sample-edge bank
    // below is unchanged. What S84-6 then found is that the argument has a
    // hole in it: `driveall` proves pin -> SPORT -> RX DMA -> slot map ->
    // buffer good, but under `driveall` the lane is LAUNCHED by this part's
    // own `bck8_launch` and is a register output half a bit period wide of
    // the DSP's sampling edge by construction. The AK5558 lanes are not.
    // They are launched by three converters off `conv_bck`, which leaves
    // U3.142, crosses a net with five 33R taps, clocks the converter, and
    // comes back on `ad[n]` -- and then crosses THIS part combinationally
    // (`i_dspa[n] = ad[n]`, no register anywhere in it) to the DSP's pin.
    // Every nanosecond of that round trip eats the DSP's setup window, and
    // nothing in this design has ever measured it.
    //
    // So the witness now runs TWO banks of the same counters on the same
    // three lanes, one strobed on `bck8_sample` (cnt[1:0] == 2'b00, the
    // sysclk tick at which bck8 rises) and one on `bck8_launch` (cnt[1:0]
    // == 2'b10, the tick at which it falls). They are half a bit period --
    // 40.69 ns at 12.288 MHz -- apart, and they are both running at once on
    // the same data, so the comparison is between two readings of ONE pass
    // and not between two runs.
    //
    // WHAT THE PAIR SEPARATES, which is the whole reason for the second bank:
    //   both banks agree, both carry data   the lane is stable across at
    //                                       least half a bit period and the
    //                                       CPLD is sampling it correctly;
    //                                       the loss is further downstream
    //   the banks DISAGREE                  the data transitions between the
    //                                       two edges, so one of them is
    //                                       inside the converter's launch
    //                                       shadow: the phase is the fault
    //                                       and the fix is in this file
    //   one bank static, the other moving   the same thing, at its extreme
    //
    // A disagreement is not proof on its own that `bck8_sample` is the WRONG
    // edge -- two edges 40.69 ns apart on a 81.38 ns bit period will always
    // straddle one transition per bit period somewhere -- but the SIZE of
    // the disagreement locates the transition, and `ones` differing by ~half
    // the toggle count is what a transition sitting on one of the two edges
    // looks like.
    //
    // ONE KNOCK STILL ANSWERS ABOUT ONE THING. The knock's low three bits
    // now select {edge, lane}: bit 2 chooses the bank (0 = bck8_sample,
    // 1 = bck8_launch) and bits 1:0 the lane, exactly as before. S84's three
    // knock words have bit 2 clear, so they still ask what they asked then
    // and the S84 readings remain comparable to these without a correction.
    // Both selectors are echoed in the reply and checked by the reader --
    // S84-9 is the reason: the lane echo caught a real transcription error
    // on its first run, and an edge echo costs one bit of a word that has
    // four to spare.
    //
    // Bank index is {edge, lane}: 0..2 = sample edge, 3..5 = launch edge.
    localparam AD_BANKS = 6;

    reg [5:0]  ad_q;                              // last sample, per bank
    reg [8:0]  ad_ones_c  [0:AD_BANKS-1];
    reg [8:0]  ad_tog_c   [0:AD_BANKS-1];
    reg [8:0]  ad_ones_l  [0:AD_BANKS-1];
    reg [8:0]  ad_tog_l   [0:AD_BANKS-1];
    reg [8:0]  ad_ones_max[0:AD_BANKS-1];
    reg [15:0] ad_frames;                  // free-running, fs8 (= conv_fs)

    // THE CLOCK-GENERATOR RATIO CHECK (S85). The dispatch asks for the
    // conv_bck/conv_fs edges "as the CPLD sees them", and the honest answer
    // is still S84's: this part DRIVES both pins and no MAX V can see the far
    // end of a net it drives, so nothing here witnesses arrival at U6/U7/U8.
    // What it can witness, and what it costs about a dozen LEs to witness, is
    // that its own generator holds the ratio: exactly 256 bck8 periods in
    // every conv_fs frame. A divider that had lost a count, or a frame
    // boundary landing on a bck8 edge, would show here and nowhere else, and
    // it is the one failure that would make every `ones` number below a lie
    // about a different-length frame. Sticky, so a single bad frame since
    // power-up is still visible at the next knock.
    reg [8:0] ad_bck_c;
    reg       ad_bck_bad;

    integer i;
    // Power-up state stated rather than inherited -- the same argument as
    // cdc_count in dsp4_pcm_reframe.v. MAX V macrocells come up cleared;
    // saying so keeps simulation and silicon in agreement and keeps an
    // unwritten counter from propagating X into the capture word.
    initial begin
        ad_q = 6'd0;
        ad_frames = 16'd0;
        ad_bck_c = 9'd0;
        ad_bck_bad = 1'b0;
        for (i = 0; i < AD_BANKS; i = i + 1) begin
            ad_ones_c[i]   = 9'd0; ad_tog_c[i]    = 9'd0;
            ad_ones_l[i]   = 9'd0; ad_tog_l[i]    = 9'd0;
            ad_ones_max[i] = 9'd0;
        end
    end

    // `bck8_sample` (cnt[1:0] == 2'b00) and `bck8_launch` (cnt[1:0] == 2'b10)
    // are mutually exclusive by construction, and `cdc_frame_end`
    // (frame_pos == 1023, so cnt[1:0] == 2'b11) coincides with neither -- so
    // unlike the cdc bank above, no count is ever lost to the frame clear
    // here and `ones` is out of a true 256.
    always @(posedge sysclk) begin
        if (bck8_sample) begin
            for (i = 0; i < 3; i = i + 1) begin
                ad_q[i] <= ad[i];
                if (ad[i])            ad_ones_c[i] <= ad_ones_c[i] + 9'd1;
                if (ad[i] != ad_q[i]) ad_tog_c[i]  <= ad_tog_c[i]  + 9'd1;
            end
            ad_bck_c <= ad_bck_c + 9'd1;
        end
        if (bck8_launch) begin
            for (i = 0; i < 3; i = i + 1) begin
                ad_q[3+i] <= ad[i];
                if (ad[i])              ad_ones_c[3+i] <= ad_ones_c[3+i] + 9'd1;
                if (ad[i] != ad_q[3+i]) ad_tog_c[3+i]  <= ad_tog_c[3+i]  + 9'd1;
            end
        end
        if (cdc_frame_end) begin
            for (i = 0; i < AD_BANKS; i = i + 1) begin
                ad_ones_l[i] <= ad_ones_c[i];
                ad_tog_l[i]  <= ad_tog_c[i];
                if (ad_ones_c[i] > ad_ones_max[i])
                    ad_ones_max[i] <= ad_ones_c[i];
                ad_ones_c[i] <= 9'd0;
                ad_tog_c[i]  <= 9'd0;
            end
            ad_frames <= ad_frames + 16'd1;
            if (ad_bck_c != 9'd256) ad_bck_bad <= 1'b1;
            ad_bck_c <= 9'd0;
        end
    end

    wire [1:0] ad_sel;                     // lane, driven by the knock
    wire       ad_edge;                    // bank,  driven by the knock
    wire [2:0] ad_bank = ad_edge ? (3'd3 + {1'b0, ad_sel}) : {1'b0, ad_sel};

    //   L = {3'b0, bck_ratio_ok, edge, lane[1:0], ones_last[8:0],
    //        7'b0, ones_max[8:0]}
    // The lane still sits at [26:25] and ones/max still sit where S84 put
    // them, so an S84-era reader decodes an S85 reply correctly for the
    // sample-edge banks it knows how to ask for.
    wire [31:0] ad_wit_l = {3'd0, ~ad_bck_bad, ad_edge, ad_sel,
                            ad_ones_l[ad_bank], 7'd0, ad_ones_max[ad_bank]};
    wire [31:0] ad_wit_r = {AD_MAGIC, ad_tog_l[ad_bank], ad_frames[15:9]};

    // ---- Pi PCM re-framer -> DSPA I6 ----
    wire pcm_tdm;
    // The broadcast copy of the Pi stream (all eight TDM8 slots), used
    // only by the DRIVE_ALL capacity-stimulus build below.
    wire pcm_drive;
    // DSP4_PI_TDM8 runs the CM4 link at 4x rate so it carries eight
    // channels each way instead of two -- see dsp4_pcm_reframe.v. It is a
    // build-time evaluation switch, not a shipping default, until the
    // eight-channel path is proven on hardware.
    // The two evaluation switches are independent: PI_TDM8 sets the 4x
    // frame rate, PI_SELFTEST loops the Pi's playback back to its capture
    // inside LOGIC. Stereo self-test (no TDM8) is what the differential
    // latency measurement needs, so they must combine freely.
`ifdef DSP4_PI_SELFTEST
 `ifdef DSP4_PI_TDM8
    dsp4_pcm_reframe #(.PI_TDM8(1), .PI_SELFTEST(1)) u_pcm (
 `else
    dsp4_pcm_reframe #(.PI_SELFTEST(1), .CAP_SLOT_L(0), .CAP_SLOT_R(1)) u_pcm (
 `endif
`elsif DSP4_PI_MAINCAP
    // Latency measurement through the DSP: capture B_O3 slot 0, which is
    // C2_MAIN_ST_OUT and the only slot the node graph drives today. The
    // product allocation stays slots 2/3.
    dsp4_pcm_reframe #(.CAP_SLOT_L(0), .CAP_SLOT_R(1)) u_pcm (
`elsif DSP4_PI_TDM8
    dsp4_pcm_reframe #(.PI_TDM8(1)) u_pcm (
`else
    dsp4_pcm_reframe u_pcm (
`endif
        .sysclk      (sysclk),
        .frame_pos   (frame_pos),
        .pcm_clk     (pcm_clk),
        .pcm_fs      (pcm_fs),
        .pcm_dout    (pcm_dout),
        .pcm_din     (pcm_din),
        .bck8_launch (bck8_launch),
        .bck8_sample (bck8_sample),
        // Capture source for the Pi. In the loopback bring-up build this
        // is a DSPB output lane, so the Pi can record what DSPB actually
        // transmits; the shipping build ties pcm_din off inside the
        // reframer and this input is unused.
        // Capture the MAIN stereo output lane. C2_MAIN_ST_OUT writes
        // SPORT3 slot 0 on chip 2, which is o_dspb[3] (the CPLD's
        // dac_main). That is where a Pi -> DSP -> Pi pass-through lands:
        // XIN_PI -> XS_XFER -> inter-chip -> C2_XR_PI -> C2_PI_IN ->
        // MIX_MAIN -> MAIN_FDR -> MAIN_DLY -> MAIN_ST_OUT. Lane 0 slots
        // 0/1 are AUX_OUT_01/02 and carry nothing in a pass-through.
`ifdef DSP4_PI_TDM8
        // EVALUATION: lane 0 is the only DSPB output the DSP4_PATTERN
        // firmware drives on ALL EIGHT slots (c2_tx cs_mask 0x00FF), so
        // it is the one that can prove eight distinct channels arriving.
        // The product capture stays on o_dspb[3] below.
        .tdm_in      (o_dspb[0]),
`else
        .tdm_in      (o_dspb[3]),
`endif
        .tdm_out     (pcm_tdm),
        .tdm_drive   (pcm_drive),
        .cdc_wit_l   (cdc_wit_l),
        .cdc_wit_r   (cdc_wit_r),
        .ad_wit_l    (ad_wit_l),
        .ad_wit_r    (ad_wit_r),
        .ad_sel      (ad_sel),
        .ad_edge     (ad_edge)
    );

    // ---- Input-lane sources (fixed per product) ----
    // D24: lanes 0-2 = ADC8s, lane 3 = NET (no AD3 converter).
    // D32: personality TBD with the D32 board work.
    wire [3:0] net_sel = strap_d32 ? 4'b1000 : 4'b1000;

`ifdef DSP4_DRIVE_ALL
    // ---- NON-SHIPPING MEASUREMENT BUILD: the driven-capacity stimulus ----
    //
    // Every DSPA input lane carries the Pi's playback, broadcast across
    // all eight TDM8 slots, so a single stereo stream played by the CM4
    // puts full-scale signal on all 46 of chip 1's input kernels at once.
    //
    // WHY IT IS IN THE CPLD AND NOT IN THE FIRMWARE. Until S19 the only
    // way to measure the graph with its dynamics engaged was
    // DSP4_PROFILE_SIGNAL, which synthesises a square INSIDE the 46 input
    // kernels. The part then pays for its own stimulus, so every driven
    // figure has to be netted against a cost nobody could measure
    // independently -- and S18 mis-attributed chip 1's whole 113 % to that
    // synthesis on exactly that reasoning. Driven from here the DSP
    // executes not one instruction for the stimulus, and the 113 % turned
    // out to be the product. What is left is measured per session on a
    // graph with the dynamics switched off and stated beside the number
    // (S19: 0.28 points on chip 1, 0.53 on chip 2).
    //
    // It is also RUNTIME-SWITCHED, which is the point of using the Pi's
    // stream rather than a counter in the CPLD: the silent row and the
    // driven row are taken on ONE bitstream and one boot, and the only
    // difference between them is whether `aplay` is running.
    //
    // NOTHING else changes: same clkgen, same reframer, same DSPB output
    // routing, same pinout. Never set for a shipping build; build.sh
    // labels the artifact dsp4_logic_driveall.<hash>.
    //
    // LANE 6 IS NOT DRIVEN FROM THE BROADCAST COPY, AND THAT IS S78-4.
    // chip 1's RX halves carry two different frame delays (lane_config.c:
    // c1_rx_lanes_mfd = { 2,2,2,2,2,2,1,2 }), so ONE framing cannot be
    // bit-exact on all eight. `pcm_drive` is framed for the seven MFD 2
    // halves; lane 6 is the MFD 1 one and already has a correctly framed
    // stream of its own in `pcm_tdm`, which is what the shipping build
    // gives it. Its cs_mask is 0x0003 -- only slots 0/1 are received, and
    // they are exactly what `pcm_tdm` carries -- so the stimulus still
    // reaches C1_XIN_PI_L/R and nothing is lost by not broadcasting there.
    //
    // Before this, lane 6 took the broadcast copy like the rest and read
    // bit-exact while the other seven read (word << 1): S77-3, located by
    // measurement in S78-3.
    assign i_dspa[5:0] = {6{pcm_drive}};
    assign i_dspa[6]   = pcm_tdm;
    assign i_dspa[7]   = pcm_drive;
`elsif DSP4_LOOPBACK
    // ---- NON-SHIPPING BRING-UP BUILD: fabric feedback loop ----
    //
    // Every DSPA input lane is fed from the matching DSPB output lane,
    // so DSPB can emit a known per-lane pattern and DSPA can check it
    // without a single converter, analog board or scope. That closes
    // BCKI/FSI pair order, sample edge / MFD, within-TDM8 slot order and
    // the NET crossed-index question by measurement instead of by
    // assumption.
    //
    // NOTHING else changes: same clkgen, same reframer, same DA/NO
    // output routing, same pinout. This define is never set for a
    // shipping build, and build.sh labels the artifact
    // dsp4_logic_loopback.<hash> so the two can never be confused.
    // Lane 6 is the EXCEPTION and it has to be: it carries the Pi's
    // playback (pcm_tdm, from the reframer). Feeding it from o_dspb too
    // would tie off the only path the Pi has INTO the DSP, and rung 2 is
    // a Pi -> DSPA -> fabric -> DSPB -> Pi round trip. Everything else
    // still comes from the matching DSPB output lane.
    assign i_dspa[5:0] = o_dspb[5:0];
    assign i_dspa[6]   = pcm_tdm;
    assign i_dspa[7]   = o_dspb[7];
`else
`ifdef DSP4_LANE_ID
    // ---- NON-SHIPPING DIAGNOSTIC: EVERY DSPA INPUT LANE NAMES ITSELF (S85) ----
    //
    // The successor to `driveall`, built because `driveall` answers a
    // different question than four sessions have been reading it as. It puts
    // ONE signal on six pins, so every chip-1 input buffer carries it and the
    // run says "the lanes are good" -- but a receiver reading any of those six
    // pins sees the same bits, so the test cannot tell a correct lane mapping
    // from a permuted one, and cannot tell either from a receiver reading a
    // pin this design believes is elsewhere. S85 put live converter data on
    // i_dspa[0..2] three different ways -- as a wire, as a registered copy,
    // and as the codec lane the DSP reads correctly in the same pass -- and
    // all thirty-two mic buffers read exact digital zero every time. So the
    // question is no longer "do the pins carry data" but "WHICH PIN does each
    // buffer read", and nothing in the record answers it.
    //
    // Here every lane carries a DIFFERENT stream, and each stream names its
    // own pin and its own slot in its top sixteen bits:
    //
    //     word[31:16] = {8'hA5, lane[3:0], tick, slot[2:0]}    word[15:0] = 0
    //
    // so a buffer fed from pin 3 slot 5 reads 0xA53500000 / 0xA53D0000 and
    // says so. `tick` flips every 48 kHz frame for one reason: a constant
    // reads as `distinct 1` in the lane scan, which is the scan's word for
    // DEAD, and an instrument that reports itself dead when it is working is
    // the S80-19 mistake. With the tick the lane both MOVES and names itself.
    //
    // FRAMED FOR MFD 2, which is what seven of chip 1's eight RX halves use
    // (lane_config.c c1_rx_lanes_mfd = {2,2,2,2,2,2,1,2}); the +2-MFD form is
    // the reframer's `drive_period`, and at MFD 2 that is the frame position
    // itself. Lane 6 is the MFD 1 half and will read its own code shifted one
    // bit -- 0x4A6...  rather than 0xA56... -- which is still unmistakable,
    // and the shift is itself the S78-3 signature confirming the framing.
    //
    // It drives NOTHING but the eight DSPA input pins. No DAC lane, no NET
    // lane, no codec, no panel; the converters keep their clock pair and are
    // simply not listened to for the duration.
    wire [7:0] lid_period = frame_pos[9:2];      // MFD 2 framing
    wire [2:0] lid_slot   = lid_period[7:5];
    wire [4:0] lid_bix    = 5'd31 - lid_period[4:0];

    reg lid_tick;
    initial lid_tick = 1'b0;
    always @(posedge sysclk)
        if (cdc_frame_end)
            lid_tick <= ~lid_tick;

    function lid_bit;
        input [3:0] lane;
        input       tick;
        input [2:0] slot;
        input [4:0] bix;
        reg [15:0] w;
        begin
            w = {8'hA5, lane, tick, slot};
            lid_bit = (bix >= 5'd16) ? w[bix - 5'd16] : 1'b0;
        end
    endfunction

    reg [7:0] lid_q;
    integer L;
    initial lid_q = 8'd0;
    always @(posedge sysclk)
        if (bck8_launch)
            for (L = 0; L < 8; L = L + 1)
                lid_q[L] <= lid_bit(L[3:0], lid_tick, lid_slot, lid_bix);

    assign i_dspa = lid_q;
`elsif DSP4_AD_FROM_CDC
    // ---- NON-SHIPPING DIAGNOSTIC: THE MIC LANES FED FROM THE CODEC (S85) ----
    //
    // THE HOLE IN driveall's PROOF, which four sessions have leaned on.
    // `driveall` sets `i_dspa[5:0] = {6{pcm_drive}}` -- six lanes, ONE signal.
    // Every chip-1 input buffer then carries the stimulus, and that has been
    // read ever since as "pin -> SPORT -> RX DMA -> slot map -> buffer is
    // good for lanes 0..5". It is not that. With all six pins carrying
    // identical bits, a receiver reading ANY of them sees the same stream, so
    // the test cannot tell a correct lane mapping from a permuted one, and it
    // cannot tell either from a receiver that is reading a pin this design
    // believes is somewhere else entirely. It proves the pins reach the DSP.
    // It does not prove WHICH pin reaches which SPORT half.
    //
    // That hole is now the only place left for the fault to be. S84 and S85
    // between them have taken everything else off the table: the converters
    // are converting (ad[0..2] carry data at U3's pins, both rail states),
    // the launch phase is not it (S85-1: the two bck8 edges return identical
    // counts), the combinational crossing is not it (S85-5: the lanes read
    // exact zero with a retiming register holding live data), the mux is not
    // it (net_sel is 4'b1000 in both arms), and the slot map is byte-identical
    // across every bitstream this bench has carried.
    //
    // So substitute a KNOWN-GOOD SOURCE instead of a known-good sink. cdc_o is
    // a converter lane on the same Analog board, off the same conv_bck/conv_fs
    // pair, crossing this part the same combinational way -- and the DSP reads
    // it correctly today, four of four codec buffers moving in the same pass
    // in which all thirty-two mic buffers read zero. Feed it to the three mic
    // lanes and the answer is binary:
    //
    //   the mic buffers CARRY the codec's data   the pins, the SPORT halves,
    //                                            the DMA and the slot map for
    //                                            lanes 0-2 are all good, and
    //                                            the difference is at the
    //                                            ad[] pins of this part
    //   the mic buffers stay at EXACT ZERO       nothing the CPLD drives onto
    //                                            i_dspa[0..2] reaches those
    //                                            buffers, driveall's proof was
    //                                            the artifact above, and the
    //                                            fault is the lane mapping on
    //                                            the DSP side
    //
    // All three are fed from the same source deliberately: three lanes reading
    // one identical stream is the reading that cannot be explained by any
    // per-lane accident.
    assign i_dspa[0] = cdc_o;
    assign i_dspa[1] = cdc_o;
    assign i_dspa[2] = cdc_o;
`elsif DSP4_AD_RETIME
    // ---- THE CONVERTER LANES, RE-TIMED (S85) ----
    //
    // The three AK5558 lanes stop being a wire through this part and become a
    // register in it. What that changes, and why it is the one thing left to
    // change, needs the whole path said out loud:
    //
    //   the DAC/NET lanes         launched by THIS part on bck8_launch, a
    //   and everything driveall   register output, half a bit period of
    //   drives                    setup to the receiver's sampling edge by
    //                             construction. This is the arrangement the
    //                             slot map's own convention describes, and
    //                             the one that works.
    //
    //   ad[0..2] (shipping)       launched by three AK5558s off conv_bck,
    //                             which leaves U3.142, crosses a five-33R-tap
    //                             star, is re-buffered on the Analog board
    //                             (U97/U98) and clocks the converter; the
    //                             data comes back over the FPC to ad[n] and
    //                             then crosses U3 COMBINATIONALLY to the
    //                             DSP's pin. Every nanosecond of that round
    //                             trip, plus this part's own pin-to-pin
    //                             delay, is subtracted from the DSP's 40.69
    //                             ns setup window, and nothing in this design
    //                             has ever constrained or measured it -- the
    //                             sdc has no set_input_delay on ad[] at all.
    //
    // The register closes that gap by making the converter lanes exactly the
    // arrangement the DAC lanes already use: capture the pin on bck8_launch,
    // where the S85 witness measured the data sitting stable on BOTH edges
    // (so this capture has most of a bit period of margin on each side), and
    // hand the DSP a register output with the full half period of setup.
    //
    // IT COSTS EXACTLY ONE BCK PERIOD OF LATENCY AND THAT IS NOT FREE.
    // The DSP samples this register at the bck8 rising edge that follows the
    // bck8_launch which loaded it, so it reads the bit the converter launched
    // ONE period earlier than the un-retimed wire would have delivered. There
    // is no sysclk edge between the converter's data becoming valid and the
    // DSP's sampling edge with margin worth having on both sides -- that is
    // the whole problem -- so a retime here cannot be free, and pretending
    // otherwise would just move the off-by-one somewhere it is harder to see.
    // It is compensated on the DSP side by the per-lane frame delay these
    // lanes already carry (lane_config.c `c1_rx_lanes_mfd`, which S78-3 shows
    // is already non-uniform across chip 1's eight RX halves), NOT here:
    // conv_fs is shared with the codec and the DACs and moving it to fix
    // three lanes would break five.
    reg [2:0] ad_rt;
    initial   ad_rt = 3'd0;
    always @(posedge sysclk)
        if (bck8_launch)
            ad_rt <= ad[2:0];

    assign i_dspa[0] = net_sel[0] ? ni[0] : ad_rt[0];
    assign i_dspa[1] = net_sel[1] ? ni[1] : ad_rt[1];
    assign i_dspa[2] = net_sel[2] ? ni[2] : ad_rt[2];
`else
    assign i_dspa[0] = net_sel[0] ? ni[0] : ad[0];
    assign i_dspa[1] = net_sel[1] ? ni[1] : ad[1];
    assign i_dspa[2] = net_sel[2] ? ni[2] : ad[2];
`endif
`ifndef DSP4_LANE_ID
    // The five lanes none of the S85 diagnostics touch. LANE_ID is the
    // exception and drives the whole bus itself, which is the point of it.
    // AD3 carries no converter on the D24 -- net_sel routes it from the NET
    // lane -- so it is not retimed and stays as it was.
    assign i_dspa[3] = net_sel[3] ? ni[3] : ad[3];
    assign i_dspa[4] = cdc_o;
    assign i_dspa[5] = strap_d32 ? snake_in : 1'b0;
    assign i_dspa[6] = pcm_tdm;
    assign i_dspa[7] = mems;
`endif
`endif

    // ---- DSPB output routing (slot map B_O0..B_O7) ----
    assign da[0] = o_dspb[0];                       // DAC 1-8
    assign da[1] = 1'b0;                            // spare (Digital J18)
    assign da[2] = 1'b0;                            // D32_COMPAT only
    assign da[3] = o_dspb[1];                       // DAC 9-16 (DA_LANE_B_O1)
    assign cdc_i = strap_d32 ? 1'b0 : o_dspb[2];    // D24 codec DAC

    // ---- X-logic parking: DRIVEN ON D32, HIGH-Z ON D24 (S36) ----
    //
    // snake_out (pin 110) and dac_main (pin 111) are not spare pads. Each
    // is a three-board net: U3.110 = LOGIC_PLL5_1 = G2667 reaches
    // `opt2: SLOT.A13` as well as `digital: J18.74 / J2.A13 [NO7]`, and
    // U3.111 = LOGIC_PLL5_2 = G2668 reaches `opt2: SLOT.A10` as well as
    // `digital: J18.71 / J2.A10 [NO4]`. On a D24 both had a CONSTANT
    // driver here -- snake_out a hard 1'b0, dac_main the live B_O3 TDM8
    // lane -- so the day an option card is fitted to slot 2 and drives its
    // own A-row, two CMOS outputs meet with no series resistance. That is
    // a fight, not a contention the 33R taps can absorb, and it is on
    // COPPER THAT ALREADY EXISTS: nothing has to be added to the board for
    // it to happen, only a card fitted.
    //
    // The fix is to drive them only on the product that uses them. On D32
    // (strap_d32 = 1) they are the snake send and the main DAC lane and
    // must drive; on D24 they carry nothing this design needs -- the Pi
    // capture reads o_dspb[3] INTERNALLY as `tdm_in`, never through the
    // pin -- so high-Z costs the D24 nothing and hands slot 2 its own
    // lanes back.
    //
    // WHY NOT MOVE THE PINS. Pins 81/85/87 (L1/C2/C0) really are dead:
    // the hub's fan-out table gives all three `(nothing - single-pin net)`
    // on the dsp board alone, so parking a driven output there would reach
    // nobody. But ONE bitstream serves D24 and D32 (strap_d32 is a runtime
    // strap, not a build switch -- dsp4-architecture-decisions.md), so
    // moving snake_out/dac_main to dead pads would forfeit the D32 role
    // that these pins exist for. Tri-stating keeps both products correct
    // in one image.
    assign snake_out = strap_d32 ? o_dspb[2] : 1'bz;
    assign dac_main  = strap_d32 ? o_dspb[3] : 1'bz;
    assign no[0] = o_dspb[4];                       // NET 1-8
    assign no[1] = o_dspb[5];
    assign no[2] = o_dspb[6];
    assign no[3] = o_dspb[7];

    // ---- Converter / option-slot clock pair ----
    // The same bck8/fs8 the DSPA input halves and the DSPB output halves
    // run on (bcki[0]/fsi[0], bcki[5]/fsi[5]), so the converter frame,
    // the option-slot frame and the DSP frame are one frame by
    // construction -- which is what the wire-through lanes require and
    // what the slot map's sample-rising/launch-falling convention means
    // on the analog side too.
    //
    // ONE pair serves the converters AND all three option slots; there
    // is no per-slot clock on this board, only 33R copies of this pin.
    // So an option lane cannot be moved to TDM16 without moving the
    // converters with it -- see the S34 write-up.
    assign conv_bck = bck8;
    assign conv_fs  = fs8;

    // ---- Bring-up test points ----
    // Existing clkgen nets only, so LE count is unchanged (156); the
    // cost is 4 pins plus the extra output loading on these nets, which
    // moved 1270Z Fmax 68.24 -> 67.06 MHz. Keep it that way: D8's STA
    // gate is the guard, and on the rev-D 570Z part the margin is both
    // thinner and noisy (50.67 MHz measured 2026-08-07, 55.88 MHz on
    // 2026-08-11 with these pins added — that spread is fitter placement
    // variance, not a real improvement, so trust the gate, not a
    // remembered percentage).
    // Together these prove clock generation and frame alignment on a
    // scope without a DSP image loaded.
    assign test[0] = fs8;             // TEST1: 48 kHz frame sync, TDM8
    assign test[1] = bck8;            // TEST2: 12.288 MHz bit clock
    assign test[2] = fs16;            // TEST3: 48 kHz frame sync, TDM16
    assign test[3] = frame_pos[9];    // TEST4: 24 kHz square, frame phase

    // ---- Heartbeat (~1.4 Hz from a 25-bit divider) ----
    reg [24:0] hb;
    always @(posedge sysclk)
        hb <= hb + 25'd1;
    assign blink_led = hb[24];

    // Sanity: generated slot map says B_O1 drives DA lane 3
    initial begin
        if (DA_LANE_B_O1 != 3)
            $display("slot-map mismatch: DA_LANE_B_O1");
    end

    // Straps/strobes currently unused; keep referenced.
    wire _unused = ^{bck8_sample,
                     bck16_sample, bck16_launch, fs16, bck16};

endmodule

`default_nettype wire
