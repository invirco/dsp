// dsp4_logic_revd_top.v — top level of the REV D revision of the LOGIC
// CPLD (U3, 5M1270ZT144C4N on both revisions; S173).
//
// The rev D board moves eleven U3 pins (DSPC-L8d/L8e/L8k) and adds the
// BOARD_REV0 strap on U3.81. The pin moves are a qsf matter only
// (quartus/dsp4_logic_revd.qsf, generated from the rev C qsf by
// gen_revd_qsf.py). The ONE logic difference is the strap, which this
// wrapper reads and reports through dsp4_revd_id_tap -- see that file for
// why it is a tap and not a change to the shared core.
//
// Everything else is dsp4_logic_top, instantiated unchanged.

`default_nettype none

module dsp4_logic_revd_top (
    input  wire        sysclk,
    output wire        conv_bck,
    output wire        conv_fs,
    output wire        dsp_clk,
    output wire [7:0]  bcki,
    output wire [7:0]  fsi,
    output wire [7:0]  i_dspa,
    input  wire [7:0]  o_dspb,
    input  wire [3:0]  ad,
    output wire [3:0]  da,
    input  wire [3:0]  ni,
    output wire [3:0]  no,
    input  wire        cdc_o,
    output wire        cdc_i,
    output wire        mems_bck,
    output wire        mems_fs,
    input  wire        mems_i2s,
    output wire        pcm_clk,
    output wire        pcm_fs,
    input  wire        pcm_dout,
    output wire        pcm_din,
    output wire        blink_led,
    output wire [3:0]  test,
    input  wire        board_rev0    // U3.81 BOARD_REV0: GND on rev D
);

    wire pcm_din_core;

    dsp4_logic_top u_core (
        .sysclk(sysclk), .conv_bck(conv_bck), .conv_fs(conv_fs),
        .dsp_clk(dsp_clk),
        .bcki(bcki), .fsi(fsi), .i_dspa(i_dspa), .o_dspb(o_dspb),
        .ad(ad), .da(da), .ni(ni), .no(no),
        .cdc_o(cdc_o), .cdc_i(cdc_i),
        .mems_bck(mems_bck), .mems_fs(mems_fs), .mems_i2s(mems_i2s),
        .pcm_clk(pcm_clk), .pcm_fs(pcm_fs), .pcm_dout(pcm_dout),
        .pcm_din(pcm_din_core), .blink_led(blink_led), .test(test)
    );

    dsp4_revd_id_tap u_rev (
        .sysclk(sysclk), .pcm_clk(pcm_clk), .din_core(pcm_din_core),
        .board_rev0(board_rev0), .din_pin(pcm_din)
    );

endmodule

`default_nettype wire
