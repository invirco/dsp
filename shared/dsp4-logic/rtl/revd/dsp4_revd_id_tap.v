// dsp4_revd_id_tap.v — the rev D board strap, answered inside the existing
// design-ID knock reply (S173).
//
// WHY THIS IS A TAP ON THE CM4 PCM LINE AND NOT A PORT ON THE CORE.
// The rev C bitstream must stay byte-identical (S173), and its artifact
// hash covers rtl/*.v. Any edit to the shared core -- even one behind an
// `ifdef -- renames and re-stamps the rev C image. So the rev D revision
// is the SAME core, untouched, plus this file (rtl/revd/, outside the
// rev C hash glob), instantiated by dsp4_logic_revd_top.
//
// WHAT IT DOES. The core answers the ID knock with
//     L = DESIGN_ID,  R = {16'hD594, CFG_BITS[15:0]}
// for 128 Pi frames. This tap watches the bits the core launches on
// pcm_din, and when the last 48 launched bits are exactly
// {DESIGN_ID, 16'hD594} it replaces the 5th bit that follows -- CFG_BITS
// bit 11 -- with the LIVE board strap:
//
//     CFG_BITS[11] = 1  <=>  BOARD_REV0 (U3.81) reads LOW = rev D copper
//
// CFG_BITS[10] is the STATIC "built from the rev D pin set" bit, set by
// build.sh for BOARD_REV=D. So the reply's low word reads:
//
//     rev C image, any board ............ 0x0010   (bits 11:10 = 00)
//     rev D image on rev D copper ....... 0x0C10   (bits 11:10 = 11)
//     rev D image on rev C copper ....... 0x0410   (bits 11:10 = 01) -- WRONG IMAGE
//
// On rev C, U3.81 is the single-pin net L1 (it reaches nothing), so the
// weak pull-up the rev D qsf puts on it reads 1 there; on rev D it is tied
// to GND (DSPC stage 2b, kept by L11 Q2).
//
// SAFETY. Nothing but the CM4's own return stream is touched, and only
// inside an ID reply: a false 48-bit match in audio would cost bit 11 of
// one 32-bit word (~ -120 dBFS) once. Every other bit is the core's bit,
// retimed by ONE sysclk (20.3 ns) on rev D. The Pi samples on the PCM BCK
// rising edge 8 sysclk after the launch, so the retimed bit still has
// 7 sysclk (~142 ns) of setup -- the margin the core's own comment cites.
//
// Power-up: MAX V registers come up cleared, and cnt == 0 is IDLE, so
// nothing is spliced until a real match.

`default_nettype none

`ifndef DSP4_DESIGN_ID
 `define DSP4_DESIGN_ID 32'h0000_0000
`endif

module dsp4_revd_id_tap #(
    parameter [31:0] DESIGN_ID = `DSP4_DESIGN_ID
) (
    input  wire sysclk,
    input  wire pcm_clk,      // the core's PCM BCK (a sysclk register)
    input  wire din_core,     // the core's pcm_din
    input  wire board_rev0,   // U3.81: 1 = open (rev C), 0 = GND (rev D)
    output wire din_pin       // to the pcm_din pin
);
    localparam [15:0] ID_MAGIC = 16'hD594;   // as dsp4_pcm_reframe

    // The strap is static, but it is a pin: synchronise it.
    reg [1:0] rev_sync;
    initial   rev_sync = 2'b00;
    always @(posedge sysclk) rev_sync <= {rev_sync[0], board_rev0};
    wire board_is_revd = ~rev_sync[1];

    // The core launches pcm_din on the SAME sysclk edge that takes pcm_clk
    // low, so in the cycle after that edge pcm_clk reads 0, its delayed
    // copy reads 1, and din_core already holds the new bit.
    reg pclk_q;
    initial pclk_q = 1'b0;
    always @(posedge sysclk) pclk_q <= pcm_clk;
    wire launched = pclk_q & ~pcm_clk;

    reg  [47:0] hist;
    initial     hist = 48'd0;
    wire [47:0] hist_next = {hist[46:0], din_core};
    wire        hit = (hist_next == {DESIGN_ID, ID_MAGIC});

    // cnt: 0 idle; 1 = magic just finished; on the launch that sees cnt==5
    // the bit being launched is CFG_BITS[11] (15,14,13,12 came before it).
    reg [2:0] cnt;
    initial   cnt = 3'd0;
    always @(posedge sysclk) begin
        if (launched) begin
            if (hit)                cnt <= 3'd1;
            else if (cnt == 3'd7)   cnt <= 3'd0;
            else if (cnt != 3'd0)   cnt <= cnt + 3'd1;
        end
        if (launched)
            hist <= hist_next;
    end

    wire splice = launched ? (cnt == 3'd5) : (cnt == 3'd6);

    reg din_q;
    initial din_q = 1'b0;
    always @(posedge sysclk)
        din_q <= splice ? board_is_revd : din_core;
    assign din_pin = din_q;

endmodule

`default_nettype wire
