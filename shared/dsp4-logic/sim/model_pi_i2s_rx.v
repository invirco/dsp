// model_pi_i2s_rx.v — behavioural model of the Raspberry Pi PCM block
// RECEIVING I2S as a clock slave: what the CM4 writes into the ALSA
// capture buffer when LOGIC drives pcm_din.
//
// Mirror of model_pi_i2s_tx. LOGIC launches WS and data on the BCK
// FALLING edge, so the receiver first SEES a WS change on the rising
// edge that follows it, and the MSB of that word arrives DATA_DELAY
// rising edges later (DATA_DELAY = 1 is Philips I2S = the Pi's
// CH1POS = 1). A word therefore runs across the WS boundary — its last
// bit lands on the edge where WS changes again — which is exactly the
// case a naive "reset the counter on WS" model gets wrong.
//
// `left`/`right` hold the last COMPLETE word of each channel and
// `pairs` counts complete L/R pairs, so a testbench can wait for
// settled frames instead of guessing a delay.
//
// Simulation only — never in the Quartus project.

`default_nettype none

module model_pi_i2s_rx #(
    parameter integer DATA_DELAY = 1
) (
    input  wire        bck,        // pcm_clk from LOGIC
    input  wire        ws,         // pcm_fs  from LOGIC
    input  wire        sd,         // pcm_din from LOGIC
    output reg  [31:0] left,
    output reg  [31:0] right,
    output reg  [31:0] pairs
);
    reg [31:0] sr;
    reg        ws_d;
    reg        arm;
    integer    arm_cnt;
    reg        arm_chan;
    reg        cur_chan;
    integer    cnt;                // bits still to shift in this word

    initial begin
        sr       = 32'd0;
        ws_d     = 1'bx;
        arm      = 1'b0;
        arm_cnt  = 0;
        arm_chan = 1'b0;
        cur_chan = 1'b0;
        cnt      = 0;
        left     = 32'd0;
        right    = 32'd0;
        pairs    = 32'd0;
    end

    always @(posedge bck) begin
        // 1. A WS change seen here starts a word DATA_DELAY edges later.
        if (ws !== ws_d) begin
            arm      = 1'b1;
            arm_cnt  = DATA_DELAY;
            arm_chan = ws;
        end

        // 2. Fire the pending word start.
        if (arm) begin
            if (arm_cnt == 0) begin
                cnt      = 32;
                cur_chan = arm_chan;
                arm      = 1'b0;
            end else begin
                arm_cnt = arm_cnt - 1;
            end
        end

        // 3. Shift the word in progress; it may run past a WS change.
        if (cnt != 0) begin
            sr  = {sr[30:0], sd};
            cnt = cnt - 1;
            if (cnt == 0) begin
                if (cur_chan) begin
                    right = sr;
                    pairs = pairs + 32'd1;
                end else begin
                    left = sr;
                end
            end
        end

        ws_d = ws;
    end
endmodule

`default_nettype wire
