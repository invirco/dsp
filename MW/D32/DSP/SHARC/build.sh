#!/bin/bash
# build.sh — Native Linux CCES CLI build script for ADSP-21564 (D32)
#
# Prerequisites:
#   1. Install CCES for Linux: sudo dpkg -i adi-cces-linux-amd64-3.0.3.deb
#   2. Install SHARC Linux Command-Line Tools via Help > Install New Software
#      (or manually: extract sharc_linux.jar and sudo tar xf support_files.tar.gz -C /opt/analog/cces/3.0.3)
#   3. Activate license via Help > Manage Licenses in the CCES IDE
#
# Usage:
#   ./build.sh [clean|build|all|count]
#   Default: build

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SRC_DIR="$SCRIPT_DIR/src"
BUILD_DIR="$SCRIPT_DIR/build"
LDF="$SCRIPT_DIR/ADSP-21564.ldf"

# Native Linux CCES tool paths
CCES_DIR="/opt/analog/cces/3.0.3"
export ANALOGD_LICENSE_FILE="$HOME/.analog/cces/license.dat"
CC21K="$CCES_DIR/cc21k"
ASM21K="$CCES_DIR/easm21k"
LD21K="$CCES_DIR/linker"

# Processor target
# Default target is ADSP-21564. Set PROC_TARGET=ADSP-21568 only when using
# a 21568-only license for a fit-proxy build.
PROC_TARGET="${PROC_TARGET:-ADSP-21564}"
PROC="-proc $PROC_TARGET"

# Assembler flags
ASMFLAGS="$PROC"

# Compiler flags (for any C files)
CFLAGS="$PROC -O2 -DNDEBUG"

# Linker flags
LDFLAGS="$PROC -T $LDF"

clean() {
    echo "=== Clean ==="
    rm -rf "$BUILD_DIR"
    echo "Cleaned."
}

count() {
    echo "=== Source file count ==="
    echo "Chip 1 node ASM:  $(find "$SRC_DIR/chip1/nodes" -name '*.asm' 2>/dev/null | wc -l)"
    echo "Chip 2 node ASM:  $(find "$SRC_DIR/chip2/nodes" -name '*.asm' 2>/dev/null | wc -l)"
    echo "Chip 1 infra ASM: $(find "$SRC_DIR/chip1" -maxdepth 1 -name '*.asm' 2>/dev/null | wc -l)"
    echo "Chip 2 infra ASM: $(find "$SRC_DIR/chip2" -maxdepth 1 -name '*.asm' 2>/dev/null | wc -l)"
    echo "Shared ASM:       $(find "$SRC_DIR" -maxdepth 1 -name '*.asm' 2>/dev/null | wc -l)"
    echo "Library ASM:      $(find "$SRC_DIR/lib" -name '*.asm' 2>/dev/null | wc -l)"
    echo "Total ASM:        $(find "$SRC_DIR" -name '*.asm' 2>/dev/null | wc -l)"
}

single() {
    local asm_path="$1"
    if [ -z "$asm_path" ]; then
        echo "Usage: $0 single <asm-file>"
        exit 1
    fi

    if [[ "$asm_path" != /* ]]; then
        asm_path="$SCRIPT_DIR/$asm_path"
    fi

    if [ ! -f "$asm_path" ]; then
        echo "ERROR: file not found: $asm_path"
        exit 1
    fi

    mkdir -p "$BUILD_DIR"
    local base
    base=$(basename "$asm_path" .asm)
    local out_path="$BUILD_DIR/$base.doj"

    echo "=== Single-file assemble ==="
    echo "ASM: $asm_path"
    $ASM21K $ASMFLAGS -o "$out_path" "$asm_path"
    echo "Wrote: $out_path"
}

assemble_dir() {
    local src_dir="$1"
    local out_dir="$2"
    local label="$3"
    local extra_flags="${4:-}"

    local count=0
    local errors=0

    for asm in "$src_dir"/*.asm; do
        [ -f "$asm" ] || continue
        base=$(basename "$asm" .asm)
        echo "  ASM: $base"
        $ASM21K $ASMFLAGS $extra_flags -o "$out_dir/$base.doj" "$asm" || errors=$((errors+1))
        count=$((count+1))
    done

    echo "  ($label: $count files, $errors errors)"
    return $errors
}

build() {
    echo "=== Build D32 DSP ==="
    mkdir -p "$BUILD_DIR/chip1" "$BUILD_DIR/chip2" "$BUILD_DIR/lib"

    local total_errors=0

    # ---- Shared library (chip-agnostic: biquad, dynamics, delay, ramp) ----
    echo "--- Library: Assembling ---"
    assemble_dir "$SRC_DIR/lib" "$BUILD_DIR/lib" "lib" || total_errors=$((total_errors+$?))

    # ---- Shared infrastructure — assembled TWICE with CHIP_ID define ----
    # Files like main.asm, ivt.asm, sport_init.asm use #if CHIP_ID == N
    # to conditionally include chip-specific externs and code paths.
    echo "--- Shared (Chip 1): Assembling ---"
    assemble_dir "$SRC_DIR" "$BUILD_DIR/chip1" "shared-c1" "-DCHIP_ID=1" || total_errors=$((total_errors+$?))

    echo "--- Shared (Chip 2): Assembling ---"
    assemble_dir "$SRC_DIR" "$BUILD_DIR/chip2" "shared-c2" "-DCHIP_ID=2" || total_errors=$((total_errors+$?))

    # IVT must use -nwc (Normal Word Code) for fixed vector table alignment.
    # The default VISA mode produces SW sections that don't match the PM
    # qualifier required for the NW IVT memory region.
    echo "  Re-assembling IVT with -nwc (NW mode for vector table)"
    $ASM21K $ASMFLAGS -DCHIP_ID=1 -nwc -o "$BUILD_DIR/chip1/ivt.doj" "$SRC_DIR/ivt.asm" || total_errors=$((total_errors+1))
    $ASM21K $ASMFLAGS -DCHIP_ID=2 -nwc -o "$BUILD_DIR/chip2/ivt.doj" "$SRC_DIR/ivt.asm" || total_errors=$((total_errors+1))

    # ---- Chip 1: Infrastructure + dsp_params ----
    echo "--- Chip 1: Infrastructure ---"
    assemble_dir "$SRC_DIR/chip1" "$BUILD_DIR/chip1" "chip1-infra" "-DCHIP_ID=1" || total_errors=$((total_errors+$?))

    # ---- Chip 1: Node skeletons ----
    echo "--- Chip 1: Nodes ---"
    assemble_dir "$SRC_DIR/chip1/nodes" "$BUILD_DIR/chip1" "chip1-nodes" || total_errors=$((total_errors+$?))

    # ---- Chip 2: Infrastructure + dsp_params ----
    echo "--- Chip 2: Infrastructure ---"
    assemble_dir "$SRC_DIR/chip2" "$BUILD_DIR/chip2" "chip2-infra" "-DCHIP_ID=2" || total_errors=$((total_errors+$?))

    # ---- Chip 2: Node skeletons ----
    echo "--- Chip 2: Nodes ---"
    assemble_dir "$SRC_DIR/chip2/nodes" "$BUILD_DIR/chip2" "chip2-nodes" || total_errors=$((total_errors+$?))

    # ---- Compile any C files ----
    for csrc in "$SRC_DIR"/chip1/*.c "$SRC_DIR"/chip2/*.c "$SRC_DIR"/*.c; do
        [ -f "$csrc" ] || continue
        base=$(basename "$csrc" .c)
        dir=$(dirname "$csrc")
        rel=${dir#$SRC_DIR/}
        echo "  CC: $rel/$base.c"
        $CC21K $CFLAGS -c -o "$BUILD_DIR/$rel/$base.doj" "$csrc" || total_errors=$((total_errors+1))
    done

    # ---- Link Chip 1 ----
    # chip1/ has: shared infra (CHIP_ID=1), chip1 infra, chip1 nodes, dsp_params
    # lib/ has: chip-agnostic library
    echo "--- Chip 1: Linking ---"
    chip1_objs=$(find "$BUILD_DIR/chip1" "$BUILD_DIR/lib" -name '*.doj' 2>/dev/null | sort)
    if [ -n "$chip1_objs" ]; then
        echo "  Objects: $(echo "$chip1_objs" | wc -l) files"
        $LD21K $LDFLAGS -Map "$BUILD_DIR/chip1.map.xml" -o "$BUILD_DIR/chip1.dxe" $chip1_objs || total_errors=$((total_errors+1))
    else
        echo "  WARNING: No object files for Chip 1"
    fi

    # ---- Link Chip 2 ----
    echo "--- Chip 2: Linking ---"
    chip2_objs=$(find "$BUILD_DIR/chip2" "$BUILD_DIR/lib" -name '*.doj' 2>/dev/null | sort)
    if [ -n "$chip2_objs" ]; then
        echo "  Objects: $(echo "$chip2_objs" | wc -l) files"
        $LD21K $LDFLAGS -Map "$BUILD_DIR/chip2.map.xml" -o "$BUILD_DIR/chip2.dxe" $chip2_objs || total_errors=$((total_errors+1))
    else
        echo "  WARNING: No object files for Chip 2"
    fi

    if [ $total_errors -gt 0 ]; then
        echo "=== Build FAILED ($total_errors errors) ==="
        return 1
    fi

    echo "=== Build OK ==="
    echo "  Chip 1: $BUILD_DIR/chip1.dxe"
    echo "  Chip 2: $BUILD_DIR/chip2.dxe"
    echo ""
    count
}

case "${1:-build}" in
    clean) clean ;;
    build) build ;;
    all)   clean && build ;;
    count) count ;;
    single) single "$2" ;;
    *)     echo "Usage: $0 [clean|build|all|count|single <asm-file>]"; exit 1 ;;
esac
