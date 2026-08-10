// model_pi_i2s_tx.v — behavioural model of the Raspberry Pi PCM block
// transmitting I2S as a CLOCK SLAVE (LOGIC masters BCK and LRCLK).
//
// Philips I2S (DATA_DELAY = 1, the default and what the bcm2835 driver
// programs as CH1POS=1 for I2S mode):
//
//   - the transmitter changes data on the BCK FALLING edge;
//   - WS changes on a falling edge, and the MSB of the new word is
//     driven DATA_DELAY falling edges later — so with DATA_DELAY=1 the
//     MSB is sampled by the receiver on the SECOND rising edge after
//     the WS transition.
//
// DATA_DELAY=0 gives the left-justified variant (MSB driven on the same
// falling edge as the WS change). The parameter exists because the Pi's
// CH1POS/CH2POS are programmable: if bring-up shows the Pi framed
// differently, this model and the RTL constant move together.
//
// WS low = left, WS high = right (I2S convention).
// Simulation only — never in the Quartus project.

`default_nettype none

module model_pi_i2s_tx #(
    parameter integer DATA_DELAY = 1
) (
    input  wire        bck,        // pcm_clk from LOGIC
    input  wire        ws,         // pcm_fs  from LOGIC
    input  wire [31:0] left,       // sample presented on the left slot
    input  wire [31:0] right,      // sample presented on the right slot
    output reg         sd          // pcm_dout -> LOGIC
);
    reg [31:0] sr;
    reg [31:0] word;
    reg        ws_d;
    reg        chan;               // channel latched at the WS transition
    integer    since_ws;           // falling edges since the WS transition

    initial begin
        sr       = 32'd0;
        word     = 32'd0;
        ws_d     = 1'bx;
        chan     = 1'b0;
        since_ws = 1000;
        sd       = 1'b0;
    end

    always @(negedge bck) begin
        if (ws !== ws_d) begin
            since_ws = 0;
            chan     = ws;
        end else begin
            since_ws = since_ws + 1;
        end
        ws_d = ws;

        if (since_ws == DATA_DELAY)
            sr = chan ? right : left;

        sd = sr[31];
        sr = {sr[30:0], 1'b0};
    end
endmodule

`default_nettype wire
