# ADSP-21564 reference documents

Analog downloads were blocked here, so the PDFs were collected locally and renamed for quick lookup.

Source links:
- Datasheet: https://www.analog.com/media/en/technical-documentation/data-sheets/adsp-21560-21561-21564-21568.pdf
- HRM: https://www.analog.com/media/en/dsp-documentation/processor-manuals/adsp-21560-21561-21564-21568-hrm.pdf

## Local inventory

| File | Use |
|---|---|
| `adsp-2156x-datasheet.pdf` | Main silicon datasheet |
| `adsp-2156x-hrm.pdf` | Hardware reference manual |
| `adsp-2156x-anomaly.pdf` | Silicon anomaly list |
| `ee-400-cache-on-adsp-sc5xx-215xx.pdf` / `.zip` | Cache app note + example |
| `ee-408-adsp-2156x-fir-iir-accelerators.pdf` / `.zip` | FIR/IIR accelerator note + example |
| `ee-412-adsp-2156x-system-optimization-techniques.pdf` / `.zip` | System optimization note + example |
| `ee-418-adsp-2156x-dmc-board-design-guidelines.pdf` | DMC board guidelines |
| `ee-447-adsp-sc59x-2159x-2156x-boot-rom-tips-and-tricks.pdf` | Boot ROM, boot stream, secure boot tips |
| `ee-384-sc58x-2158x-boot-rom-tips-and-tricks.pdf` | Boot ROM tips for SC58x/2158x family |
| `ee-470-adsp-2156x-power-sequencing-requirements.pdf` | Power sequencing note |
| `ee-377-mcapi-mdma-dual-sharc-audio-talkthrough.pdf` | MDMA dual-SHARC audio pipeline example |
| `ee-383-mdma-dual-sharc-parallel-pipeline-audio-talkthrough.pdf` | Parallel audio talkthrough with MDMA |
| `ee-379-adsp214xx-vs-sc58x-2158x-peripheral-considerations.pdf` | Peripheral behavior notes across SHARC families |
| `ee-375-migrating-legacy-sharc-to-sc58x-2158x.pdf` | Legacy SHARC migration guidance |
| `ee-399-linux-runtime-sharc-loader-sc57x-sc58x.pdf` | Runtime SHARC loader notes for SC5xx Linux systems |
| `ee-177-sharc-spi-slave-booting-application-note.pdf` | SPI slave booting reference (legacy SHARC families) |
| `ee-189-link-port-tips-and-tricks-adsp2106x-2116x.pdf` | Link port tips/tricks reference (legacy SHARC families) |
| `ee-199-link-port-booting-adsp21161.pdf` | Link port booting reference (legacy SHARC families) |
| `ev-21568-som-manual.pdf` | SOM user manual |
| `ev-21568-som-schematic.pdf` | SOM schematic |
| `ev-21568-som-bom.csv.zip` | SOM BOM archive |
| `adsp-sc589-ezboard-manual.pdf` | EZ-Board user guide (adjacent eval platform) |
| `adsp-sc589-ezboard-schematic-rel-2-0b.pdf` | EZ-Board schematic collateral |
| `sc58x-2158x-prm.pdf` | SHARC+ programming reference (includes SRU/pinmux context) |
| `sc58x-2158x-hrm.pdf` | SC58x/2158x hardware reference (CGU/SRU/pinmux details) |
| `cces-3.0.3-release-notes.pdf` | CCES release notes |
| `cces-3.0.3-installation-guide.pdf` | CCES installation guide |
| `ee-68-jtag-emulation-technical-reference.pdf` | JTAG/emulator reference |
| `cces-sharc-compiler-manual.pdf` | SHARC C/C++ compiler manual |
| `cces-assembler-preprocessor-manual.pdf` | Assembler/preprocessor manual |
| `cces-linker-utilities-manual.pdf` | Linker/utilities manual |

## Toolchain note

The active CCES Wine prefix is `~/.wine-cces` and it includes `license.dat` plus the expected tools: `cc21k.exe`, `easm21k.exe`, and `linker.exe`.

## Linux/Wine CLI quick use

Use the active prefix explicitly when invoking CCES CLI tools:

```bash
export WINEPREFIX="$HOME/.wine-cces"
wine "$WINEPREFIX/drive_c/CCES/cc21k.exe" -version
wine "$WINEPREFIX/drive_c/CCES/easm21k.exe" -version
wine "$WINEPREFIX/drive_c/CCES/linker.exe" -version
```

For reproducible scripts, keep all three calls behind the same `WINEPREFIX` and log output to a build artifact.

## Bring-up coverage note

- Boot ROM and SPI boot stream guidance is covered by `ee-447-adsp-sc59x-2159x-2156x-boot-rom-tips-and-tricks.pdf`.
- Power-up/reset sequencing guidance is covered by `ee-470-adsp-2156x-power-sequencing-requirements.pdf`.
- Clock/PLL setup guidance is covered in the existing `adsp-2156x-datasheet.pdf` and `adsp-2156x-hrm.pdf`.
- SPORT/TDM and DMA pipeline examples are covered by `ee-377-mcapi-mdma-dual-sharc-audio-talkthrough.pdf` and `ee-383-mdma-dual-sharc-parallel-pipeline-audio-talkthrough.pdf` (SC58x/2158x collateral, architecture-adjacent to 2156x).
- SPI slave and link-port examples are covered with legacy SHARC app notes (`ee-177`, `ee-189`, `ee-199`) as supplemental references; no 2156x-specific standalone app note was surfaced in this sweep.

## Audio implementation coverage

- SHARC optimization references are covered by `ee-400-cache-on-adsp-sc5xx-215xx.pdf` and `ee-412-adsp-2156x-system-optimization-techniques.pdf`.
- FIR/IIR accelerator usage is covered by `ee-408-adsp-2156x-fir-iir-accelerators.pdf` plus its companion archive.
- Audio framework/example projects are covered by `ee-377-mcapi-mdma-dual-sharc-audio-talkthrough.pdf`, `ee-383-mdma-dual-sharc-parallel-pipeline-audio-talkthrough.pdf`, and the example archives already collected in this folder.

## Optional coverage note

- Eval-platform collateral is available via `adsp-sc589-ezboard-manual.pdf` and `adsp-sc589-ezboard-schematic-rel-2-0b.pdf`.
- Pinmux/CGU/SRU quick-reference material is covered by `sc58x-2158x-hrm.pdf` and `sc58x-2158x-prm.pdf`.
- Known-issues/FAQ tracking sources:
	- ADSP-2156x FAQs: https://ez.analog.com/dsp/sharc-processors/adsp-2156x/w/documents/17620/adsp-2156x-faqs
	- CCES forum hub: https://ez.analog.com/dsp/software-and-development-tools/cces/
