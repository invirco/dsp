#!/usr/bin/env bash
set -euo pipefail

# Resilient ADSP-2156x documentation fetcher.
# - Does not hard-exit on analog.com precheck failure.
# - Tries curated manual/datasheet URLs first.
# - Crawls ADSP-2156x product pages for additional PDF links.
# - Logs diagnostics and download outcomes.
#
# Usage:
#   ./fetch-adsp2156x-docs-resilient.sh
#   ./fetch-adsp2156x-docs-resilient.sh --out "/path/to/output"

OUT_DIR="/home/peter/dsp/docs/adsp-2156x"
USER_AGENT="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --out)
      [[ $# -ge 2 ]] || { echo "ERROR: --out requires a directory" >&2; exit 2; }
      OUT_DIR="$2"
      shift 2
      ;;
    -h|--help)
      sed -n '1,60p' "$0"
      exit 0
      ;;
    *)
      echo "ERROR: unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

mkdir -p "$OUT_DIR"
LOG="$OUT_DIR/download-log.tsv"
DIAG="$OUT_DIR/network-diagnostics.txt"
: > "$LOG"
: > "$DIAG"

echo "Saving docs to: $OUT_DIR"

diag() {
  printf "%s\n" "$*" | tee -a "$DIAG" >/dev/null
}

diag "=== Network diagnostics ==="
diag "Date: $(date -Iseconds)"
diag "Host: $(hostname || true)"
diag ""

if command -v getent >/dev/null 2>&1; then
  diag "getent hosts analog.com:"
  getent hosts analog.com >> "$DIAG" 2>&1 || diag "(failed)"
else
  diag "getent not available"
fi

diag ""
diag "curl --http1.1 -I https://www.analog.com:"
curl --http1.1 -I --connect-timeout 8 --max-time 20 -A "$USER_AGENT" https://www.analog.com >> "$DIAG" 2>&1 || diag "(failed)"

diag ""
diag "curl -I https://example.com:"
curl -I --connect-timeout 8 --max-time 20 https://example.com >> "$DIAG" 2>&1 || diag "(failed)"
diag ""

if ! curl -4 --http1.1 -fsSI --connect-timeout 5 --max-time 12 -A "$USER_AGENT" \
  "https://www.analog.com/" >/dev/null 2>&1; then
  echo "ERROR: DNS works, but Analog's www CDN is not returning HTTP responses." >&2
  echo "This network is timing out at the Akamai edge used by www.analog.com." >&2
  echo "Switch network (for example, a phone hotspot) or enable a working VPN, then run this task again." >&2
  echo "Diagnostics: $DIAG" >&2
  exit 3
fi

CURL_OPTS=(
  -fL
  -4
  --http1.1
  --retry 1
  --retry-delay 1
  --retry-all-errors
  --connect-timeout 12
  --max-time 180
  -A "$USER_AGENT"
)

download_pdf() {
  local url="$1"
  local source="$2"

  local base
  base="$(basename "${url%%\?*}")"
  [[ -n "$base" && "$base" != "/" ]] || base="download-$(date +%s%N).pdf"
  [[ "${base,,}" == *.pdf ]] || base="${base}.pdf"

  local dst="$OUT_DIR/$base"
  if [[ -s "$dst" ]]; then
    printf "SKIP\t%s\t%s\t%s\n" "$source" "$url" "$dst" | tee -a "$LOG" >/dev/null
    return 0
  fi

  local tmp
  tmp="$(mktemp "$OUT_DIR/.tmp.XXXXXX")"

  if curl "${CURL_OPTS[@]}" -o "$tmp" "$url" >/dev/null 2>&1; then
    if head -c 4 "$tmp" | grep -q "%PDF"; then
      mv "$tmp" "$dst"
      printf "OK\t%s\t%s\t%s\n" "$source" "$url" "$dst" | tee -a "$LOG" >/dev/null
      return 0
    fi
    rm -f "$tmp"
    printf "NOT_PDF\t%s\t%s\n" "$source" "$url" | tee -a "$LOG" >/dev/null
    return 1
  fi

  rm -f "$tmp"
  printf "FAIL\t%s\t%s\n" "$source" "$url" | tee -a "$LOG" >/dev/null
  return 1
}

CURATED_URLS=(
  "https://www.analog.com/media/en/dsp-documentation/hardware-reference-manuals/adsp-2156x_hwr_rev1.1.pdf"
  "https://www.analog.com/media/en/dsp-documentation/hardware-reference-manuals/adsp-2156x_hwr_rev1.0.pdf"
  "https://www.analog.com/media/en/technical-documentation/data-sheets/adsp-2156x.pdf"
  "https://www.analog.com/media/en/technical-documentation/data-sheets/adsp-21560.pdf"
  "https://www.analog.com/media/en/technical-documentation/data-sheets/adsp-21561.pdf"
  "https://www.analog.com/media/en/technical-documentation/data-sheets/adsp-21562.pdf"
  "https://www.analog.com/media/en/technical-documentation/data-sheets/adsp-21563.pdf"
  "https://www.analog.com/media/en/technical-documentation/data-sheets/adsp-21564.pdf"
  "https://www.analog.com/media/en/technical-documentation/data-sheets/adsp-21565.pdf"
  "https://www.analog.com/media/en/technical-documentation/data-sheets/adsp-21566.pdf"
  "https://www.analog.com/media/en/technical-documentation/data-sheets/adsp-21567.pdf"
  "https://www.analog.com/media/en/technical-documentation/data-sheets/adsp-21568.pdf"
  "https://www.analog.com/media/en/technical-documentation/data-sheets/adsp-21569.pdf"
)

SEED_PAGES=(
  "https://www.analog.com/en/products/adsp-21560.html"
  "https://www.analog.com/en/products/adsp-21561.html"
  "https://www.analog.com/en/products/adsp-21562.html"
  "https://www.analog.com/en/products/adsp-21563.html"
  "https://www.analog.com/en/products/adsp-21564.html"
  "https://www.analog.com/en/products/adsp-21565.html"
  "https://www.analog.com/en/products/adsp-21566.html"
  "https://www.analog.com/en/products/adsp-21567.html"
  "https://www.analog.com/en/products/adsp-21568.html"
  "https://www.analog.com/en/products/adsp-21569.html"
)

echo "Step 1/2: Trying curated URLs"
for u in "${CURATED_URLS[@]}"; do
  download_pdf "$u" "curated" || true
done

echo "Step 2/2: Crawling product pages for additional docs"
URL_POOL="$(mktemp)"
for page in "${SEED_PAGES[@]}"; do
  html="$(mktemp)"
  if curl "${CURL_OPTS[@]}" -o "$html" "$page" >/dev/null 2>&1; then
    grep -Eoi 'https://[^"\047 >]+\.pdf([^"\047 >]*)?' "$html" >> "$URL_POOL" || true
    grep -Eoi '/media/[^"\047 >]+\.pdf([^"\047 >]*)?' "$html" | sed 's#^#https://www.analog.com#' >> "$URL_POOL" || true
  else
    printf "PAGE_FAIL\t%s\n" "$page" >> "$LOG"
  fi
  rm -f "$html"
done

sort -u "$URL_POOL" \
  | grep -Eiv '(cookie|privacy|declaration)' \
  | grep -Ei '(adsp[-_]?215|adsp[-_]?2156|sharc|dsp-documentation|technical-documentation)' \
  | grep -Ei '(pdf|data[-_ ]?sheet|manual|hardware|reference|ee-|an-|application)' \
  > "$URL_POOL.filtered" || true

while IFS= read -r u; do
  [[ -z "$u" ]] && continue
  download_pdf "$u" "crawl" || true
done < "$URL_POOL.filtered"

rm -f "$URL_POOL" "$URL_POOL.filtered"

TOTAL_OK="$(awk -F '\t' '$1=="OK"{c++} END{print c+0}' "$LOG")"
TOTAL_SKIP="$(awk -F '\t' '$1=="SKIP"{c++} END{print c+0}' "$LOG")"
TOTAL_FAIL="$(awk -F '\t' '$1=="FAIL"{c++} END{print c+0}' "$LOG")"
TOTAL_NOTPDF="$(awk -F '\t' '$1=="NOT_PDF"{c++} END{print c+0}' "$LOG")"
TOTAL_PAGEFAIL="$(awk -F '\t' '$1=="PAGE_FAIL"{c++} END{print c+0}' "$LOG")"

echo
echo "Done"
echo "Downloaded: $TOTAL_OK"
echo "Skipped existing: $TOTAL_SKIP"
echo "Failed downloads: $TOTAL_FAIL"
echo "Non-PDF responses: $TOTAL_NOTPDF"
echo "Failed product pages: $TOTAL_PAGEFAIL"
echo "Download log: $LOG"
echo "Network diagnostics: $DIAG"

if [[ "$TOTAL_OK" -eq 0 ]]; then
  echo
  echo "No documents downloaded. Check the diagnostics file and your network/proxy settings."
  echo "If needed, set proxy vars before running:"
  echo "  export https_proxy=http://proxy-host:proxy-port"
  echo "  export http_proxy=http://proxy-host:proxy-port"
fi
