provenance: AI-drafted 2026-10-26 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# 5M1270ZT144 BSDL (S175)

`tools/pi/dspcard_id.py` source J reads U3.81 (BOARD_REV0) with a JTAG
SAMPLE/PRELOAD. These five facts are all it takes from the BSDL:

| fact | value | BSDL line |
|---|---|---|
| IR length | 10 | `INSTRUCTION_LENGTH ... is 10` |
| SAMPLE/PRELOAD | `0000000101` = 0x005 | `INSTRUCTION_OPCODE` |
| IDCODE | 0x020A30DD (the bench reads this, `shared/dsp4-logic/README.md`) | `IDCODE_REGISTER` |
| boundary length | 636 | `BOUNDARY_LENGTH` |
| U3.81 input cell | 522, `(BC_4, IO81, input, X)` (BSC group 174; 523 control, 524 output3) | `BOUNDARY_REGISTER` |

Cell 0 is the cell nearest TDO, so cell *n* is the *n*-th bit out of a DR
scan (openocd shifts LSB first).

## Where the file comes from

**Not committed.** It is Intel tool output under the Quartus licence
("for the sole purpose of programming logic devices manufactured by Intel"),
so it stays out of git (`.gitignore`) and is regenerated:

```
shared/dsp4-logic/bsdl/regen_bsdl.sh
```

That runs `quartus_eda --bsdl 5M1270ZT144C4 --output_directory=<dir>` (Quartus
Prime Lite 21.1.1 Build 850, `/opt/intelFPGA_lite/21.1`; the generator is
`quartus/common/tcl/internal/eda_bsd/bsdl_cmd.tcl`), writes
`5M1270ZT144C4_pre.bsd` (pre-configuration BSDL, 40,484 bytes), and checks
the five facts. Regeneration is byte-identical:

    sha256 7bdd8e3effc89fa939e954423a00bc5e0b6e68ab2b860535256b49cc59f4bb70

**The vendor web copy could not be fetched from this machine (2026-10-26):**
every intel.com and altera.com BSDL URL tried returns 403 "Access Denied" to
curl (the same block as analog.com and docs.amd.com), and bsdl.info lists
`MAX_V_5M1270ZT144` (48,594 bytes, submitted 2018-09-29, IDCODE
`0000 0010000010100011 00001101110 1`, the same IDCODE as here) but needs a
login to download. The Quartus file is the same device database the web file
is generated from. A byte comparison against the web file was not possible.

**Pre-configuration vs post-configuration.** A pre-configuration BSDL is enough
for SAMPLE: in user mode a MAX V's boundary cells still capture the pads, and
an input cell captures whatever the pad reads. A post-configuration BSDL only
changes which cells are marked input/output/bidir for EXTEST, which this tool
never issues.
