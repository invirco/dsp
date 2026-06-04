#!/bin/bash
# build.sh — Wine-wrapped CCES CLI build script for ADSP-21564
#
# Prerequisites:
#   1. Install CCES on Windows, copy CLI tools to Wine prefix:
#      ~/.wine/drive_c/CCES/
#   2. Ensure Wine is installed: apt install wine
#   3. Verify: wine ~/.wine/drive_c/CCES/cc21k.exe --version
#
# Usage:
#   ./build.sh [clean|build|all]
#   Default: build

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SRC_DIR="$SCRIPT_DIR/src"
BUILD_DIR="$SCRIPT_DIR/build"

# CCES tool paths (adjust to match your Wine prefix)
CCES_DIR="$HOME/.wine/drive_c/CCES"
CC21K="wine $CCES_DIR/cc21k.exe"
ASM21K="wine $CCES_DIR/asm21k.exe"
LD21K="wine $CCES_DIR/ld21k.exe"

# Processor target
PROC="-proc ADSP-21564"

# Compiler flags
CFLAGS="$PROC -O2 -DNDEBUG"
ASMFLAGS="$PROC"
LDFLAGS="$PROC"

# LDF (Linker Description File) — use CCES default or custom
# LDF="$SCRIPT_DIR/ADSP-21564.ldf"

clean() {
    echo "=== Clean ==="
    rm -rf "$BUILD_DIR"
    echo "Cleaned."
}

build() {
    echo "=== Build ==="
    mkdir -p "$BUILD_DIR/chip1" "$BUILD_DIR/chip2"

    local errors=0

    # Assemble Chip 1 ASM files
    echo "--- Chip 1: Assembling ---"
    for asm in "$SRC_DIR"/chip1/nodes/*.asm "$SRC_DIR"/chip1/*.asm; do
        [ -f "$asm" ] || continue
        base=$(basename "$asm" .asm)
        echo "  ASM: $base.asm"
        $ASM21K $ASMFLAGS -o "$BUILD_DIR/chip1/$base.doj" "$asm" || errors=$((errors+1))
    done

    # Compile Chip 1 C files
    for csrc in "$SRC_DIR"/chip1/*.c; do
        [ -f "$csrc" ] || continue
        base=$(basename "$csrc" .c)
        echo "  CC:  $base.c"
        $CC21K $CFLAGS -c -o "$BUILD_DIR/chip1/$base.doj" "$csrc" || errors=$((errors+1))
    done

    # Assemble Chip 2 ASM files
    echo "--- Chip 2: Assembling ---"
    for asm in "$SRC_DIR"/chip2/nodes/*.asm "$SRC_DIR"/chip2/*.asm; do
        [ -f "$asm" ] || continue
        base=$(basename "$asm" .asm)
        echo "  ASM: $base.asm"
        $ASM21K $ASMFLAGS -o "$BUILD_DIR/chip2/$base.doj" "$asm" || errors=$((errors+1))
    done

    # Compile Chip 2 C files
    for csrc in "$SRC_DIR"/chip2/*.c; do
        [ -f "$csrc" ] || continue
        base=$(basename "$csrc" .c)
        echo "  CC:  $base.c"
        $CC21K $CFLAGS -c -o "$BUILD_DIR/chip2/$base.doj" "$csrc" || errors=$((errors+1))
    done

    # Link Chip 1
    echo "--- Chip 1: Linking ---"
    chip1_objs=$(find "$BUILD_DIR/chip1" -name '*.doj' 2>/dev/null)
    if [ -n "$chip1_objs" ]; then
        $LD21K $LDFLAGS -o "$BUILD_DIR/chip1.dxe" $chip1_objs || errors=$((errors+1))
    fi

    # Link Chip 2
    echo "--- Chip 2: Linking ---"
    chip2_objs=$(find "$BUILD_DIR/chip2" -name '*.doj' 2>/dev/null)
    if [ -n "$chip2_objs" ]; then
        $LD21K $LDFLAGS -o "$BUILD_DIR/chip2.dxe" $chip2_objs || errors=$((errors+1))
    fi

    if [ $errors -gt 0 ]; then
        echo "=== Build FAILED ($errors errors) ==="
        return 1
    fi

    echo "=== Build OK ==="
    echo "  Chip 1: $BUILD_DIR/chip1.dxe"
    echo "  Chip 2: $BUILD_DIR/chip2.dxe"
}

case "${1:-build}" in
    clean) clean ;;
    build) build ;;
    all)   clean && build ;;
    *)     echo "Usage: $0 [clean|build|all]"; exit 1 ;;
esac
