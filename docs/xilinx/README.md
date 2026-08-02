# Xilinx/AMD documentation set (D6 FPGA platform)

Fetched 2026-08-02 by `../../fetch-xilinx-docs.sh` (18 PDFs, ~95 MB).
PDFs are local-only (gitignored); `download-log.tsv` records what came
from where. Re-run the script to restore or refresh the set.

CAVEAT: docs.amd.com serves current PDFs only through a logged-in JS
viewer, so several files come from mirrors and may lag the latest
revision (e.g. UG1085 mirror is v1.8 vs current 2.5). Check the
revision on the title page before trusting register-level detail;
docs.amd.com/r/en-US/<slug> is always current for online reading.

## Contents by purpose

Flagship silicon (ZU5EV / Kria K26):
- `ug1085-zynq-ultrascale-trm.pdf` — Zynq US+ device TRM (THE manual)
- `ds891-zynq-ultrascale-plus-overview.pdf` — family overview/selection
- `zynq-ultrascale-plus-packaging-pinouts.pdf` — packages incl. SFVC784
  pin-compat family (ZU2CG-ZU5EV, per platform-shortlist)
- `sm-k26-som-datasheet.pdf` — K26 SoM datasheet
- `k26-product-brief.pdf`, `kr260-product-brief.pdf`
- `ug1092-kr260-starter-kit.pdf` — KR260 user guide (PL Ethernet ports)

Entry tier (XC7Z020):
- `ug585-zynq-7000-trm.pdf` — Zynq-7000 TRM
- `ds190-zynq-7000-overview.pdf`, `ds187-xc7z010-xc7z020-datasheet.pdf`

UltraScale fabric design (TM engines, MW-Net MAC):
- `ug573-ultrascale-memory-resources.pdf` — BRAM/UltraRAM (reverb tanks)
- `ug579-ultrascale-dsp48e2.pdf` — DSP slice (MAC/biquad/FIR engines)
- `ug571-ultrascale-selectio.pdf` — I/O (TDM lanes, RGMII)
- `ug572-ultrascale-clocking.pdf` — clocking (audio PLL domains)
- `ds890-ultrascale-overview.pdf`, `ds180-7series-overview.pdf`

Vivado:
- `ug949-ultrafast-design-methodology.pdf` (2023.1)
- `ug1231-ultrafast-quick-reference.pdf`

Known gaps (login-only, read online):
- DS925 ZU+ DC/AC characteristics — docs.amd.com/r/en-US/ds925-zynq-ultrascale-plus
- Current-revision UG1085 — docs.amd.com/r/en-US/ug1085-zynq-ultrascale-trm

## Vivado toolchain — requires AMD account (manual step)

The installer is behind login; no unauthenticated download exists.

1. Create/sign in to an AMD account at amd.com (free).
2. Downloads page: <https://www.xilinx.com/support/download.html>
   (redirects to the AMD Vivado download center).
3. Get the **Vivado ML Standard** self-extracting web installer for
   Linux (~300 MB; the full image is ~100+ GB — use the web installer).
4. During install select ONLY: Vivado ML Standard; devices: Zynq-7000
   + Zynq UltraScale+ MPSoC (+ Spartan UltraScale+ if wanted).
   Expect 60-90 GB installed. Root disk had ~159 GB free on
   2026-08-02 — fits, but consider a cleanup first.
5. License: none needed — Standard covers XC7Z020, Kria K26, Artix,
   Spartan US+. VERIFY whether bare XCZU5EV chip-down needs Enterprise
   (K26 SoM route does not).
6. Debian 13 is unofficial but workable (Ubuntu-targeted installer;
   expect minor shims like libtinfo5).
7. NEVER commit the toolchain — same rule as CCES/Quartus
   (see CLAUDE.md / D2).

Kria board software (no Vivado needed to start): AMD-provided Ubuntu
images boot the KV260/KR260 directly — control-plane and UAC2/recording
software development can begin before any bitstream work.
