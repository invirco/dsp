// model_tdm_rx.v — behavioural model of a DSP-side TDM receiver.
//
// Encodes the LOCKED timing conventions (generated/dsp4_slot_map.vh:
// TDM_SAMPLE_EDGE_RISING=1, TDM_MFD=1) exactly as a SPORT configured
// CKRE=1 / MFD=1 sees the wire:
//
//   - data and FS are sampled on the BCK RISING edge;
//   - FS is asserted one BCK period BEFORE slot 0 — so the rising edge
//     at which FS reads high does NOT carry slot-0 data; the NEXT
//     rising edge carries slot 0 bit 31 (MSB first).
//
// This model is the arbiter for every framing question in the sim
// suite: if the RTL and this model disagree, the RTL is wrong (or the
// convention in the slot map has to change, deliberately).
//
// Simulation only — never in the Quartus project.

`default_nettype none

module model_tdm_rx #(
    parameter integer SLOTS = 8
) (
    input wire bck,
    input wire fs,
    input wire d
);
    localparam integer BITS = SLOTS * 32;

    reg [31:0] mem   [0:SLOTS-1];   // last COMPLETE frame, by slot
    reg [31:0] shift;
    integer    bitpos;              // -1 = between frames, else 0..BITS-1
    integer    frames;              // complete frames received
    integer    misframes;           // FS arrived mid-frame

    integer i;
    initial begin
        bitpos    = -1;
        frames    = 0;
        misframes = 0;
        shift     = 32'd0;
        for (i = 0; i < SLOTS; i = i + 1) mem[i] = 32'hxxxxxxxx;
    end

    always @(posedge bck) begin
        // 1. Sample the data bit due at this edge (if we are inside a frame).
        if (bitpos >= 0) begin
            shift = {shift[30:0], d};
            if (bitpos % 32 == 31) mem[bitpos / 32] = shift;
            if (bitpos == BITS - 1) begin
                bitpos = -1;
                frames = frames + 1;
            end else begin
                bitpos = bitpos + 1;
            end
        end

        // 2. FS sampled high here => slot 0 bit 31 arrives at the NEXT edge.
        if (fs === 1'b1) begin
            if (bitpos != -1) misframes = misframes + 1;
            bitpos = 0;
        end
    end
endmodule

`default_nettype wire
