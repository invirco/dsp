# ADSP-21564 ADI site checklist

Keep this short: collect the docs needed to bring up and debug the ADSP-21564 DSP path.

## Core silicon docs
- [x] ADSP-21560/61/64/68 datasheet
- [x] ADSP-21560/61/64/68 hardware reference manual (HRM)
- [x] ADSP-2156x silicon errata (latest revision)

## Boot and system bring-up
- [x] Booting / Boot ROM application note(s) for ADSP-2156x
- [x] SPI flash boot image/loader format notes
- [x] Clock/PLL configuration guidance
- [x] Power-up/reset sequencing guidance

## Peripherals and interfaces (for this project)
- [x] SPORT/TDM usage notes and examples
- [x] DMA ping-pong / linked descriptor examples
- [x] SPI slave communication examples
- [x] Link Port usage notes/examples (if used for inter-chip control)

## Toolchain and debug
- [x] CCES release notes for the installed version
- [x] CCES CLI tools present in the active prefix
- [x] CCES install/quick-start PDF
- [x] SHARC compiler/assembler/linker manuals, if separate
- [x] Emulator/JTAG debug guide for the hardware you will use
- [x] Linux/Wine notes for CCES CLI, if needed

## Minimum required for this folder
- CCES CLI binaries and matching release notes
- SHARC compiler/assembler/linker reference material
- JTAG/emulator debug guide for the hardware you will actually use

## Audio/DSP implementation references
- [x] SHARC optimization app notes (ISR, memory placement, SIMD)
- [x] FIR/IIR accelerator usage notes
- [x] Audio framework/example projects relevant to ADSP-2156x

## Optional but useful
- [x] EZ-KIT board user guide/schematics (if eval board is in use)
- [x] Pin mux/CGU/SRU quick reference docs
- [x] Any known-issues KB pages for ADSP-2156x + CCES

## Local naming convention (recommended)
Save files into this folder using stable names, e.g.:
- `adsp-2156x_errata.pdf`
- `adsp-2156x_booting_appnote.pdf`
- `cces_release_notes_<version>.pdf`
- `adsp-2156x_sport_dma_examples.pdf`
