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
# DSP_SRC_DIR/DSP_BUILD_DIR overrides support out-of-tree builds
# (e.g. the D5 fixed-point tree during conversion).
SRC_DIR="${DSP_SRC_DIR:-$SCRIPT_DIR/src}"
BUILD_DIR="${DSP_BUILD_DIR:-$SCRIPT_DIR/build}"
LDF="$SCRIPT_DIR/ADSP-21564.ldf"

# Native Linux CCES tool paths
CCES_DIR="/opt/analog/cces/3.0.3"
export ANALOGD_LICENSE_FILE="$HOME/.analog/cces/license.dat"
CC21K="$CCES_DIR/cc21k"
ASM21K="$CCES_DIR/easm21k"
LD21K="$CCES_DIR/linker"
LDR21K="$CCES_DIR/elfloader"

# Processor target
# Default target is ADSP-21564. Set PROC_TARGET=ADSP-21568 only when using
# a 21568-only license for a fit-proxy build.
PROC_TARGET="${PROC_TARGET:-ADSP-21564}"
PROC="-proc $PROC_TARGET"

# Assembler flags. -I <src> so shared asm headers (src/diag.h) resolve the
# same way from src/, src/chipN/ and src/lib/.
ASMFLAGS="$PROC -I $SRC_DIR"

# Compiler flags (for any C files)
CFLAGS="$PROC -O -DNDEBUG"

# P2.2 bisect variant selector (TEMPORARY — goes with the scaffolding when
# tasks.md NOW item 3 lands). See the DSP4_BISECT block at the top of
# src/dma_config.c for what each value parks on:
#   0 = production, 1 = round 1 (default, park after arm_region(A)),
#   2 = variant B (park after arm_region(B)), 3 = variant C (EN last),
#   4 = park on entry to dma_cfg_init, 5 = park on the first instruction
#   of _start (does the image execute at all?).
# The define goes to the ASSEMBLER too: with a bisect variant selected,
# diag.asm mirrors the status LED onto PB_05 (SPI2_RDY -> Pi GPIO8/GPIO12)
# so the bisect can be read over ssh instead of needing eyes on LD3/LD2.
# Always passed explicitly (defaulting to the same 1 that dma_config.c
# falls back to) so the C and asm halves can never disagree about which
# variant is being built.
DSP4_BISECT="${DSP4_BISECT:-1}"
CFLAGS="$CFLAGS -DDSP4_BISECT=$DSP4_BISECT"
ASMFLAGS="$ASMFLAGS -DDSP4_BISECT=$DSP4_BISECT"
echo "  (P2.2 bisect variant: DSP4_BISECT=$DSP4_BISECT)"

# Linker flags — LDF resolved in build(): the repo LDF hardcodes
# ARCHITECTURE(ADSP-21564); for a fit-proxy build under a different
# PROC_TARGET a matching temp LDF is generated in the build dir (same
# memory map — 21568 = same core/L1/L2). Never commit a non-21564 LDF.
resolve_ldf() {
    if [ "$PROC_TARGET" != "ADSP-21564" ]; then
        mkdir -p "$BUILD_DIR"
        local proxy_ldf="$BUILD_DIR/${PROC_TARGET}.ldf"
        sed "s/ARCHITECTURE(ADSP-21564)/ARCHITECTURE($PROC_TARGET)/" "$LDF" > "$proxy_ldf"
        LDF="$proxy_ldf"
        echo "  (fit-proxy: using generated $proxy_ldf)"
    fi
    LDFLAGS="$PROC -T $LDF"
}

# A non-21564 build is a temporary compatibility (fit-proxy) image only —
# same core/L1/L2, different part number. Banner it and drop a marker beside
# the DXEs so the output can never be mistaken for a production card image.
compat_banner() {
    [ "$PROC_TARGET" = "ADSP-21564" ] && return 0
    echo "*********************************************************************"
    echo "*  TEMPORARY COMPATIBILITY BUILD — target $PROC_TARGET, NOT 21564"
    echo "*  Fit proxy only (21564 constraints + memory map). Do NOT flash or"
    echo "*  release as a production D32/DSP4 image."
    echo "*********************************************************************"
}

compat_marker() {
    [ "$PROC_TARGET" = "ADSP-21564" ] && return 0
    cat > "$BUILD_DIR/COMPAT-BUILD.txt" <<EOF
TEMPORARY COMPATIBILITY BUILD — NOT A PRODUCTION IMAGE

Target:      $PROC_TARGET (fit proxy for ADSP-21564)
LDF:         $LDF (generated; ARCHITECTURE rewritten, memory map unchanged)
Built:       $(date -u '+%Y-%m-%dT%H:%M:%SZ')
Reason:      full CCES licence (AD-CCES-NODE-1) pending; this host is
             entitled to ADSP-21568 only, so -proc ADSP-21564 fails.
Validity:    proves toolchain, codegen, link and memory fit. Says nothing
             about 21564 part-specific behaviour. Do not flash to hardware
             or publish as a release artifact. This applies to the .ldr
             boot streams beside the DXEs too — they are bootable, and a
             fit-proxy image booted into a real 21564 is not a test, it
             is an unknown.
EOF
    echo "  Marker: $BUILD_DIR/COMPAT-BUILD.txt"
}
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
    compat_banner
    resolve_ldf
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

    # ---- Compile C files ----
    # Shared (root src/) C is compiled TWICE with -DCHIP_ID, like the
    # shared asm infra; chipN/ C compiles once with its chip define.
    for csrc in "$SRC_DIR"/*.c; do
        [ -f "$csrc" ] || continue
        base=$(basename "$csrc" .c)
        for chip in 1 2; do
            echo "  CC: $base.c (CHIP_ID=$chip)"
            $CC21K $CFLAGS -DCHIP_ID=$chip -c \
                -o "$BUILD_DIR/chip$chip/$base.doj" "$csrc" || total_errors=$((total_errors+1))
        done
    done
    for chip in 1 2; do
        for csrc in "$SRC_DIR"/chip$chip/*.c; do
            [ -f "$csrc" ] || continue
            base=$(basename "$csrc" .c)
            echo "  CC: chip$chip/$base.c"
            $CC21K $CFLAGS -DCHIP_ID=$chip -c \
                -o "$BUILD_DIR/chip$chip/$base.doj" "$csrc" || total_errors=$((total_errors+1))
        done
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
    loader || total_errors=$((total_errors+1))
    compat_marker
    compat_banner
    echo ""
    count
}

# ---- Boot streams (.ldr) ------------------------------------------------
# A .dxe is not bootable. The card has no boot flash: SYS_BMODE[2:0] is
# strapped 0b010 = SPI slave boot through the SPI2 peripheral, and the
# CM4 pushes the stream (CS1 -> chip 1, CS2 -> chip 2). See
# tools/pi/dsp4_boot.py for the host side.
#
#   -b SPIHOST  "SPI Host boot" = the slave-boot case, where a host
#               pushes the stream in. -b SPI is the master case (the part
#               reads a flash itself) and is the wrong intent here.
#               elfloader 6.4.2.1 emits byte-identical output for both
#               (checked 2026-08-20), so this is a statement of intent
#               rather than a change of image — but state the intent, so
#               a toolchain that starts distinguishing them gets it right.
#   -bcode 1    single-bit SPI (HRM Table 40-19, SPIS_BCODE 00xx). The
#               BCODE nibble sits in the low byte of every block header,
#               and the boot kernel reads the first byte of the stream as
#               its SPICMD auto-detect (HRM Table 40-18), so this is also
#               what tells the kernel to stay in single-bit mode.
#   -f BINARY   raw bytes for spidev, not ASCII hex
#   -width 8    byte-wide stream
#   -MaxBlockSize 0x1000
#               HARD REQUIREMENT on this part in SPI target boot, found
#               2026-08-21. The default is 0x7FFFFFF0, i.e. one block per
#               contiguous section, and the boot kernel does not survive a
#               large one: bisected with src/blink/bulkprobe.asm (rdyprobe
#               plus a slab of dead code, so size is the only variable),
#               chip 1, ten boots per rung —
#                   180 B stream, 68 B block     10/10 boot
#                 8364 B stream, 8252 B block     0/10 boot
#               and then the SAME 8364-byte DXE re-run through elfloader
#               with -MaxBlockSize 0x400 or 0x1000 boots 4/4. Nothing else
#               changed: not the clock (100 kHz behaves the same as 1 MHz),
#               not the host transfer size (--chunk 1024 / 2048 / 4096 all
#               behave the same), not the zero-fill blocks (removing the
#               506 KB L2 fill changed nothing). It is the byte count in a
#               single block header that the kernel cannot take.
#               This is why the full firmware — one 8 KB+ block per
#               section — was accepted by the host end to end and then
#               never executed a single instruction, while the 1 KB
#               blink/rdyprobe images always ran. 0x1000 is used rather
#               than 0x400 because both boot and the larger block costs
#               fewer headers.
#               NECESSARY BUT NOT YET SUFFICIENT: with this in place the
#               full 208 KB chip1 image still does not run (DSP4_BISECT=5
#               park stayed silent, 2026-08-21 15:0xZ), so there is a
#               SECOND limit above ~8 KB — total image size, block count,
#               or the fill blocks. The bulkprobe ladder rebuilt with this
#               flag is the instrument for that; see tasks.md P2.2.
LDRFLAGS="-b SPIHOST -bcode 1 -f BINARY -width 8 -MaxBlockSize 0x1000"
#
# The entry address is NOT passed on the command line: the ELF header
# carries no entry point, so elfloader defaults to 0x90004 — which IS the
# right answer here (IVT base 0x00090000 + RSTI at offset 0x004). The
# check below asserts that, because if the IVT layout ever moves, a
# silently wrong entry address produces a board that boots into garbage.
loader() {
    local rc=0 f
    echo "--- Boot streams ---"
    for f in chip1 chip2; do
        [ -f "$BUILD_DIR/$f.dxe" ] || continue
        if ! "$LDR21K" $PROC $LDRFLAGS \
                -o "$BUILD_DIR/$f.ldr" "$BUILD_DIR/$f.dxe" \
                > "$BUILD_DIR/$f.ldr.log" 2>&1; then
            echo "  ERROR: elfloader failed for $f (see $BUILD_DIR/$f.ldr.log)"
            rc=1
            continue
        fi
        if ! grep -q "Defaulting to 0x90004" "$BUILD_DIR/$f.ldr.log"; then
            echo "  ERROR: $f.ldr entry address is not the RSTI vector 0x90004."
            echo "         Check seg_rth placement in the LDF and src/ivt.asm."
            rc=1
            continue
        fi
        echo "  $f.ldr: $(stat -c %s "$BUILD_DIR/$f.ldr") bytes"
    done
    return $rc
}

# ---- Bring-up images ("is this board alive?") ----------------------------
# Standalone minimal images: one pin toggling and nothing else — no SRU,
# no SPORT, no DMA, no SEC, no SPI. They separate "the boot stream never
# landed" from "it landed but the plumbing hangs", and they are the only
# instrument that can tell those apart, so they are permanent tools, not
# scaffolding. Both link against the same LDF; the unused regions simply
# stay empty.
#
#   blink     — toggles PA_12 (LD3 on DSPA / LD2 on DSPB). Needs eyes at
#               the bench, but needs nothing else to be working.
#   rdyprobe  — toggles PB_05 (the SPI2_RDY net, which reaches the Pi as
#               GPIO8 / GPIO12). Same answer, readable over ssh.
#
# $1 = image base name, $2 = source file under src/blink/, $3 = pin note.
tiny_image() {
    local img="$1" src="$2" note="$3"
    echo "=== Build $img image ==="
    compat_banner
    resolve_ldf
    mkdir -p "$BUILD_DIR/blink"
    local rc=0 c
    for c in 1 2; do
        $ASM21K $ASMFLAGS -DCHIP_ID=$c \
            -o "$BUILD_DIR/blink/$img$c.doj" "$SRC_DIR/blink/$src" \
            || { rc=1; continue; }
        $ASM21K $ASMFLAGS -DCHIP_ID=$c -nwc \
            -o "$BUILD_DIR/blink/${img}_ivt$c.doj" "$SRC_DIR/blink/blink_ivt.asm" \
            || { rc=1; continue; }
        $LD21K $LDFLAGS -Map "$BUILD_DIR/$img$c.map.xml" \
            -o "$BUILD_DIR/$img$c.dxe" \
            "$BUILD_DIR/blink/${img}_ivt$c.doj" "$BUILD_DIR/blink/$img$c.doj" \
            || { rc=1; continue; }
        "$LDR21K" $PROC $LDRFLAGS \
            -o "$BUILD_DIR/$img$c.ldr" "$BUILD_DIR/$img$c.dxe" \
            > "$BUILD_DIR/$img$c.ldr.log" 2>&1 || { rc=1; continue; }
        if ! grep -q "Defaulting to 0x90004" "$BUILD_DIR/$img$c.ldr.log"; then
            echo "  ERROR: $img$c.ldr entry address is not the RSTI vector"
            rc=1; continue
        fi
        echo "  $img$c.ldr: $(stat -c %s "$BUILD_DIR/$img$c.ldr") bytes" \
             "(chip $c, ~$([ $c = 1 ] && echo 1 || echo 2) Hz on $note)"
    done
    compat_marker
    [ $rc -eq 0 ] && echo "=== ${img} OK ===" || echo "=== ${img} FAILED ==="
    return $rc
}

blink()    { tiny_image blink    blink.asm    PA_12; }
rdyprobe() { tiny_image rdyprobe rdyprobe.asm "PB_05 = Pi GPIO8/GPIO12"; }

# ---- Boot-size probe (see src/blink/bulkprobe.asm) -----------------------
# rdyprobe plus a slab of never-executed code, at five sizes, chip 1 only.
# Built as a ladder because the question is where slave boot stops
# working, not whether one particular size does.
bulkprobe() {
    echo "=== Build bulkprobe ladder (chip 1) ==="
    resolve_ldf
    mkdir -p "$BUILD_DIR/blink"
    local rc=0 b
    for b in ${BULK_LEVELS:-0 1 2 3 4}; do
        $ASM21K $ASMFLAGS -DCHIP_ID=1 -DBULK=$b \
            -o "$BUILD_DIR/blink/bulkprobe$b.doj" "$SRC_DIR/blink/bulkprobe.asm" \
            || { rc=1; continue; }
        $ASM21K $ASMFLAGS -DCHIP_ID=1 -nwc \
            -o "$BUILD_DIR/blink/bulkprobe_ivt.doj" "$SRC_DIR/blink/blink_ivt.asm" \
            || { rc=1; continue; }
        $LD21K $LDFLAGS -Map "$BUILD_DIR/bulkprobe$b.map.xml" \
            -o "$BUILD_DIR/bulkprobe$b.dxe" \
            "$BUILD_DIR/blink/bulkprobe_ivt.doj" "$BUILD_DIR/blink/bulkprobe$b.doj" \
            || { rc=1; continue; }
        "$LDR21K" $PROC $LDRFLAGS \
            -o "$BUILD_DIR/bulkprobe$b.ldr" "$BUILD_DIR/bulkprobe$b.dxe" \
            > "$BUILD_DIR/bulkprobe$b.ldr.log" 2>&1 || { rc=1; continue; }
        echo "  bulkprobe$b.ldr: $(stat -c %s "$BUILD_DIR/bulkprobe$b.ldr") bytes"
    done
    [ $rc -eq 0 ] && echo "=== bulkprobe OK ===" || echo "=== bulkprobe FAILED ==="
    return $rc
}

case "${1:-build}" in
    clean) clean ;;
    build) build ;;
    all)   clean && build ;;
    blink) blink ;;
    rdyprobe) rdyprobe ;;
    bulkprobe) bulkprobe ;;
    count) count ;;
    single) single "$2" ;;
    *)     echo "Usage: $0 [clean|build|all|blink|rdyprobe|bulkprobe|count|single <asm-file>]"
           exit 1 ;;
esac
