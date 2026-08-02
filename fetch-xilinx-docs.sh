#!/usr/bin/env bash
set -euo pipefail

# Xilinx/AMD documentation fetcher for the D6 FPGA platform (fpga/).
# docs.amd.com serves PDFs only through a JS viewer (curl gets HTML), so
# this pulls from verified direct-PDF sources:
#   - 0x04.net/~mwk/xidocs  — community mirror of Xilinx UG/DS PDFs
#     (versions may lag docs.amd.com; check revision on the title page)
#   - www.xilinx.com/support/documents/sw_manuals — still serves PDFs
#   - mm.digikey.com / farnell.com / amd.com content-dam — per-doc mirrors
# PDFs land in docs/xilinx/ and are NOT committed (see .gitignore);
# the download log is committed as the record of what/where.
#
# Usage: ./fetch-xilinx-docs.sh [--out DIR]

OUT_DIR="/home/peter/dsp/docs/xilinx"
USER_AGENT="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --out) OUT_DIR="$2"; shift 2 ;;
    -h|--help) sed -n '1,20p' "$0"; exit 0 ;;
    *) echo "ERROR: unknown argument: $1" >&2; exit 2 ;;
  esac
done

mkdir -p "$OUT_DIR"
LOG="$OUT_DIR/download-log.tsv"
: > "$LOG"
echo "Saving docs to: $OUT_DIR"

CURL_OPTS=( -fL -4 --retry 2 --retry-delay 2 --retry-all-errors
            --connect-timeout 12 --max-time 300 -A "$USER_AGENT" )

# download <dest-name> <url> [fallback-url...]
download() {
  local name="$1"; shift
  local dst="$OUT_DIR/$name"
  if [[ -s "$dst" ]]; then
    printf "SKIP\t%s\n" "$name" | tee -a "$LOG"; return 0
  fi
  local url tmp
  tmp="$(mktemp "$OUT_DIR/.tmp.XXXXXX")"
  for url in "$@"; do
    if curl "${CURL_OPTS[@]}" -o "$tmp" "$url" >/dev/null 2>&1 \
       && head -c 4 "$tmp" | grep -q "%PDF"; then
      mv "$tmp" "$dst"
      printf "OK\t%s\t%s\n" "$name" "$url" | tee -a "$LOG"
      return 0
    fi
  done
  rm -f "$tmp"
  printf "FAIL\t%s\t%s\n" "$name" "$*" | tee -a "$LOG"
  return 1
}

MIR="https://0x04.net/~mwk/xidocs"

# --- Zynq UltraScale+ (flagship: ZU5EV / Kria K26) ---
download ug1085-zynq-ultrascale-trm.pdf \
  "$MIR/ug/ug1085-zynq-ultrascale-trm.pdf"
download ds891-zynq-ultrascale-plus-overview.pdf \
  "$MIR/ds/ds891-zynq-ultrascale-plus-overview.pdf" \
  "https://www.avnet.com/wcm/connect/4717b36f-c145-4d4c-ada7-3a58518f77c1/ds891-zynq-ultrascale-plus-datasheet.pdf?MOD=AJPERES&attachment=false"
download zynq-ultrascale-plus-packaging-pinouts.pdf \
  "https://mm.digikey.com/Volume0/opasdata/d220001/medias/docus/7152/Zynq%20UltraScale+_Datasheet.pdf"

# --- Kria K26 / KR260 ---
download sm-k26-som-datasheet.pdf \
  "https://mm.digikey.com/Volume0/opasdata/d220001/medias/docus/7161/SM-K26-XCL2GI.pdf"
download ug1092-kr260-starter-kit.pdf \
  "https://uk.farnell.com/site/binaries/content/assets/common/product-family-documents/amd-kria-k24-k26/kria-kr260-robotics-starter-kit-user-guide.pdf" \
  "https://www.mouser.com/pdfDocs/22.pdf"
download kr260-product-brief.pdf \
  "https://www.amd.com/content/dam/amd/en/documents/products/som/kria/k26/kr260-product-brief.pdf"
download k26-product-brief.pdf \
  "https://www.amd.com/content/dam/amd/en/documents/products/som/kria/k26/k26-product-brief.pdf"

# --- Zynq-7000 (32/64-ch tier: XC7Z020) ---
download ug585-zynq-7000-trm.pdf \
  "$MIR/ug/ug585-Zynq-7000-TRM.pdf" \
  "https://download.kamami.pl/p574762-ug585-Zynq-7000-TRM.pdf"
download ds190-zynq-7000-overview.pdf \
  "$MIR/ds/ds190-Zynq-7000-Overview.pdf"
download ds187-xc7z010-xc7z020-datasheet.pdf \
  "$MIR/ds/ds187-XC7Z010-XC7Z020-Data-Sheet.pdf" \
  "https://www.farnell.com/datasheets/2301214.pdf" \
  "https://download.kamami.pl/p574762-ds187-XC7Z010-XC7Z020-Data-Sheet.pdf"

# --- UltraScale architecture (fabric design: BRAM/URAM, DSP48E2, I/O, clocks) ---
download ug573-ultrascale-memory-resources.pdf \
  "$MIR/ug/ug573-ultrascale-memory-resources.pdf"
download ug579-ultrascale-dsp48e2.pdf \
  "$MIR/ug/ug579-ultrascale-dsp.pdf"
download ug571-ultrascale-selectio.pdf \
  "$MIR/ug/ug571-ultrascale-selectio.pdf"
download ug572-ultrascale-clocking.pdf \
  "$MIR/ug/ug572-ultrascale-clocking.pdf"
download ds890-ultrascale-overview.pdf \
  "$MIR/ds/ds890-ultrascale-overview.pdf"
download ds180-7series-overview.pdf \
  "$MIR/ds/ds180_7Series_Overview.pdf"

# --- Vivado methodology ---
download ug949-ultrafast-design-methodology.pdf \
  "https://www.fdi.ucm.es/profesor/mendias/DAS/docs/ug949-vivado-design-methodology-en-us-2023.1.pdf" \
  "https://www.xilinx.com/support/documents/sw_manuals/xilinx2022_2/ug949-vivado-design-methodology.pdf"
download ug1231-ultrafast-quick-reference.pdf \
  "https://www.fdi.ucm.es/profesor/mendias/DAS/docs/ug1231-ultrafast-design-methodology-quick-reference.pdf"

echo
awk -F '\t' '{c[$1]++} END{printf "OK: %d  SKIP: %d  FAIL: %d\n", c["OK"], c["SKIP"], c["FAIL"]}' "$LOG"
echo "Log: $LOG"
echo
echo "NOT fetchable without an AMD account (JS viewer / login only):"
echo "  - DS925 (ZU+ DC/AC characteristics)  -> read at docs.amd.com/r/en-US/ds925-zynq-ultrascale-plus"
echo "  - Vivado installer                    -> see docs/xilinx/README.md"
