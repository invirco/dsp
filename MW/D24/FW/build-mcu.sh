#!/usr/bin/env bash
# Headless build of one panel/hub MCU image from its folder here.
#   ./build-mcu.sh <H1S1|H1S3|H1S4|MH1> <path-to-ST-Drivers-dir> [out-dir]
# Builds in a scratch copy (this tree is never touched), strips the one
# CubeIDE-only flag (-fcyclomatic-complexity) that plain arm-none-eabi-gcc
# rejects, and writes <MCU>.elf/.hex/.bin (+ .shex for the three panel MCUs).
# Drivers/ (ST HAL + CMSIS) is not stored in git; see each README for the pack.
set -euo pipefail
mcu=${1:?mcu}; drv=${2:?Drivers dir}; here=$(cd "$(dirname "$0")" && pwd)
out=${3:-$here/build-out/$mcu}; w=$(mktemp -d)
trap 'rm -rf "$w"' EXIT
rsync -a --exclude=Debug/Core --exclude=Debug/Drivers "$here/$mcu/" "$w/"
rsync -a "$here/$mcu/Debug/" "$w/Debug/"
ln -s "$(cd "$drv" && pwd)" "$w/Drivers"
cd "$w/Debug"
find . -name '*.mk' -exec sed -i 's/-fcyclomatic-complexity//g' {} +
make -f makefile.linux all -j"$(nproc)" >build.log 2>&1 || { tail -20 build.log; exit 1; }
mkdir -p "$out"; cp "$mcu".elf "$mcu".hex "$out"/
arm-none-eabi-objcopy -O binary "$mcu".elf "$out/$mcu.bin"
case $mcu in
  H1S1) id=H1S1 ;;   # shex header id: see README (H1S3/H1S4 ids are crossed)
  H1S3) id=H1S4 ;;
  H1S4) id=H1S3 ;;
  *) id= ;;
esac
[ -n "$id" ] && python3 "$here/hex2shex.py" "$mcu".hex "$id" "$out/$mcu.shex"
arm-none-eabi-gcc --version | head -1
md5sum "$out"/*
