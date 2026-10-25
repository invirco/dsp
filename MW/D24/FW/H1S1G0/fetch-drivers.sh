#!/usr/bin/env bash
# Assemble the ST driver set for the H1S1 rev D (STM32G0B1) build, in the
# CubeMX Drivers/ layout, from ST's own GitHub repos at pinned tags.
#   ./fetch-drivers.sh <out-dir>      -> <out-dir>/Drivers
# Drivers/ is not stored in git (same rule as every MCU here). The rev C
# trees name a CubeMX pack instead; this port has no .ioc, so the pack is
# replaced by the three component repos the STM32CubeG0 pack itself carries.
set -euo pipefail
out=${1:?out-dir}; mkdir -p "$out"; out=$(cd "$out" && pwd)
src=$out/src; d=$out/Drivers
mkdir -p "$src"
get() {   # repo tag commit
  [ -d "$src/$1" ] || git -c advice.detachedHead=false clone -q --depth 1 \
      --branch "$2" "https://github.com/STMicroelectronics/$1.git" "$src/$1"
  have=$(git -C "$src/$1" rev-parse HEAD)
  [ "$have" = "$3" ] || { echo "$1 $2 is $have, want $3" >&2; exit 1; }
}
get stm32g0xx_hal_driver v1.4.7          a0cf8a8b96183fdcc2e3b1cf0bcf0825f27bd0c9
get cmsis_device_g0      v1.4.5          f576c24e123edf3332988ecd49512c0f35f85186
get cmsis_core           v5.9.0_20250520 b7487de1303e2eb77c402432e368691e9dcfb5f0
rm -rf "$d"; mkdir -p "$d/CMSIS/Device/ST"
cp -r "$src/stm32g0xx_hal_driver" "$d/STM32G0xx_HAL_Driver"
cp -r "$src/cmsis_device_g0" "$d/CMSIS/Device/ST/STM32G0xx"
cp -r "$src/cmsis_core/Include" "$d/CMSIS/Include"     # CMSIS 5 pack layout
rm -rf "$d"/STM32G0xx_HAL_Driver/.git "$d"/CMSIS/Device/ST/STM32G0xx/.git
echo "$d"
