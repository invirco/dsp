# smoke checklist

Status: active
Date: 2026-07-15
Scope: D24 and D32 contract bump verification after regeneration.

## Run commands

1. ./regenerate-dsp-contract.sh
2. ./check-contract-drift.sh

## Checklist

- [ ] Contract sync completed with lock verification
- [ ] D24 MxAdd contiguous check passed
- [ ] D32 MxAdd contiguous check passed
- [ ] D32 family allowlist compatibility passed
- [ ] DSP regeneration completed without fatal errors
- [ ] Generated files present:
  - MW/D32/DSP/ghost_cells.h
  - MW/D32/DSP/SHARC/src/chip1/dsp_params.asm
  - MW/D32/DSP/SHARC/src/chip2/dsp_params.asm
  - MW/D32/DSP/dsp_address_map.md
  - MW/D32/FW/H1S1/Core/Inc/mx_dsp_map.h
- [ ] Regenerate summary captured in release notes or PR
- [ ] Informational mapping gaps reviewed:
  - DSP cells not in matrix
  - matrix cells without DSP mapping
- [ ] Contract note fields added per release-notes-contract-convention.md

## Standing acceptance bars (every session's requal)

Run these alongside the smokes. Each has its own instrument and its own
negative control; the absence of output is not a result.

| bar | invocation | pass |
|---|---|---|
| **contract conformance** | `cd MW/D32/DSP/SHARC && NEGCTL=1 ./conform.sh` | the scorer prints `VERDICT: PASS` — every address agrees with the dispatch table, every declared unit checks out apart from the named `KNOWN_MISMATCH` findings, **and both negative controls fired**. See `docs/contract/conformance-harness.md`. |
| bus golden | `./busgold.sh` | 0 of 256 words differ |
| biquad vs model | `./bqst.sh` | 0 of 16 both arms, negative control fires |
| dynamics | `./dynst.sh` | 0 of 32 on all three arms |
| numerics | `./numverify.sh` | 57/57 |
| cell semantics | `./dcapar.sh` | `VERDICT: PASS` — a write to the reserved DCA address 0x0053 raises `SPI_ERR_COUNT` while its mapped neighbour does not, and moves 0 of 32 bus words; and the compressor's threshold moves the bus **with CompPar untouched at its default**. Two defaults that were both wrong on 2026-08-30 (D57, D59) and that nothing else in this table would notice going wrong again: every other bar writes the cells it depends on. |
| meter | `./mtrverify.sh` | ms64 and both pk64 words exact, **and both negative controls fire** — the BLOCK-32 coefficients and the retired narrow (rounded-store) meter form. The wide-word control moves the gain off unity on purpose: at unity the two forms carry the same value and the primary comparison cannot separate them. |

**Read a bar's SILENCE as a bar failure, not as a result.** On
2026-08-30 two of these were found to have been failing on their own
instruments rather than on the kernel: `bqst.sh` reported "this is NOT
diag firmware" against a part that answered the paced reader perfectly,
and `numverify.sh` reported an arithmetic mismatch on ten words that a
dead link had settled on zero (review finding D60). Both are fixed. When
a bar fails, the first question is whether the instrument could have
succeeded — build the previous HEAD in a worktree and see whether it
fails the same way, which is what settled that one in ten minutes.

**The conformance run is the only bar that measures the kernel against
the MASTERS rather than against itself**, so a session that skips it can
still pass every other bar with a cell wired to the wrong variable. It
costs about ten minutes for both chips.

## Bench hand-back (any session that booted the DSPs)

The bench is a 24/7 unit and must not be left on a frozen splash or on a
work image. Every one of these has its own instrument; do not substitute
another and read the absence of output as a result.

| check | instrument | pass |
|---|---|---|
| shipping DSP firmware restored | `md5sum /home/app/dspboot/chip{1,2}.ldr` | matches the md5 recorded at the start of the session |
| DSPs running on it | `bash run1.sh /home/app/dspboot` (boot+config+verdict) | `BOOT_STAGE 7`, `FRAME_COUNT ~6000/s` (48 kHz / block 8), `DMA0_STAT 0x00006200`, `SPORT0_ERR_A 0x00000000` |
| shipping CPLD bitstream | `openocd -f cpld-jtag.cfg -c "init; scan_chain; shutdown"` | IDCODE `0x020a30dd` |
| GPIOs released | `pinctrl set 6,7,8,9,10,11,12,22,23,24,25 a0` | mandatory after any openocd or dsp4_boot run — a claimed line looks exactly like a bricked card |
| matrix-app up | `systemctl is-active matrix-app` | `active` |
| **all three MCUs verified** | **`grep -aE "MCU (boot )?verified" /home/app/logs/log \| tail -6`** | H1S1, H1S3 and H1S4 all present, timestamped after the restart |

**The MCU check reads `/home/app/logs/log`, not the systemd journal.**
matrix-app has never logged `H1S*` to the journal — `journalctl -u matrix-app`
returns nothing for it over the whole retention window, and the binary carries
no such strings. A session that greps the journal will find silence and can
mistake that for an app regression; that happened on 2026-08-27 and cost a
wrong entry in the outcome, corrected the same day.

Expect the documented **second-restart pattern**: the first `systemctl restart
matrix-app` after a DSP reflash often announces only some of the MCUs, and a
second restart brings all three.

## Pass criteria

All checks above are complete with no hash mismatch, no unexpected family additions, and no unreconciled drift for intended merge scope.
