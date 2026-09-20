// model_tdm_rx.v — behavioural model of a DSP-side TDM receiver.
//
// Encodes the LOCKED timing convention (generated/dsp4_slot_map.vh:
// TDM_SAMPLE_EDGE_RISING=1) exactly as a SPORT configured CKRE=1 sees
// the wire:
//
//   - data and FS are sampled on the BCK RISING edge;
//   - with MFD = 1, FS is asserted one BCK period BEFORE slot 0 — so the
//     rising edge at which FS reads high does NOT carry slot-0 data; the
//     NEXT rising edge carries slot 0 bit 31 (MSB first).
//
// MFD IS A PARAMETER BECAUSE THE PART DOES NOT HAVE ONE VALUE OF IT, and
// this model having exactly one is how S77-3 got past the sim suite.
// `MW/D32/DSP/SHARC/src/chip1/lane_config.c` has
//     c1_rx_lanes_mfd[8] = { 2, 2, 2, 2, 2, 2, 1, 2 };
// -- the halves LOGIC frames are MFD 1, the halves a pin-strapped AKM
// converter frames are MFD 2 (src/sport_config.c, S42-1). Every
// testbench in this suite instantiated the MFD 1 receiver, so a
// transmitter aimed at MFD 1 and received by an MFD 2 half -- which is
// what DRIVE_ALL did on seven lanes out of eight -- read PASS here and
// arrived on the part as (word << 1). Model the receiver the lane
// actually has.
//
// This model is the arbiter for every framing question in the sim
// suite: if the RTL and this model disagree, the RTL is wrong (or the
// convention in the slot map has to change, deliberately).
//
// Simulation only — never in the Quartus project.

`default_nettype none

module model_tdm_rx #(
    parameter integer SLOTS = 8,
    // SPORT_MCTL.MFD of the half being modelled: BCK periods between the
    // edge that reads FS high and the edge that carries slot 0 bit 31.
    parameter integer MFD   = 1
) (
    input wire bck,
    input wire fs,
    input wire d
);
    localparam integer BITS = SLOTS * 32;

    reg [31:0] mem   [0:SLOTS-1];   // last COMPLETE frame, by slot
    reg [31:0] shift;
    integer    bitidx;              // bit index this edge carries, 0..BITS-1
    reg        synced;              // FS has been seen at least once
    integer    frames;              // complete frames received
    integer    misframes;           // FS arrived out of position

    // The bit index the edge AFTER an FS-high edge carries. MFD = 1 puts
    // slot 0 bit 31 there; MFD = 2 puts it one edge later, so that edge
    // still carries the PREVIOUS frame's last bit. A TDM8 frame is 8 x 32
    // = 256 BCK long and the wire is continuous, so a frame delay does not
    // shorten the frame -- it rotates where FS falls inside the stream.
    // Resetting the bit counter at every FS (which this model did until
    // S78) is only correct at MFD = 1 and silently truncates every frame
    // at MFD = 2.
    localparam integer FIRST_IDX = ((1 - MFD) % BITS + BITS) % BITS;

    integer i;
    initial begin
        bitidx    = 0;
        synced    = 1'b0;
        frames    = 0;
        misframes = 0;
        shift     = 32'd0;
        for (i = 0; i < SLOTS; i = i + 1) mem[i] = 32'hxxxxxxxx;
    end

    always @(posedge bck) begin
        // 1. Sample the bit this edge carries, once FS has located us.
        if (synced) begin
            shift = {shift[30:0], d};
            if (bitidx % 32 == 31) mem[bitidx / 32] = shift;
            if (bitidx == BITS - 1) begin
                frames = frames + 1;
                bitidx = 0;
            end else begin
                bitidx = bitidx + 1;
            end
        end

        // 2. FS sampled high here => the NEXT edge carries FIRST_IDX. A
        //    receiver already in step stays in step; one that is not says so.
        if (fs === 1'b1) begin
            if (!synced) begin
                bitidx = FIRST_IDX;
                synced = 1'b1;
            end else if (bitidx != FIRST_IDX) begin
                misframes = misframes + 1;
                bitidx    = FIRST_IDX;
            end
        end
    end
endmodule

`default_nettype wire
