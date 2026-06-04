#!/bin/bash
# mac-build.sh — Temporarily swaps ens9 MAC to match CCES FlexLM license HOSTID,
# runs the build, then restores the original MAC.
#
# The license.dat is locked to 001c42a3b69b (Parallels VM NIC).
# Wine enumerates ens9 first, so FlexLM sees the wrong MAC normally.
# Swapping ens9 MAC for the duration of the build fixes this.
#
# Usage: ./mac-build.sh [clean|build|all|count]

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
NIC="ens9"
LICENSE_MAC="00:1c:42:a3:b6:9b"
REAL_MAC="38:f9:d3:0e:fa:11"

restore_mac() {
    echo "=== Restoring MAC on $NIC to $REAL_MAC ==="
    sudo ip link set "$NIC" down
    sudo ip link set "$NIC" address "$REAL_MAC"
    sudo ip link set "$NIC" up
    echo "MAC restored."
}

# Always restore on exit (success or failure)
trap restore_mac EXIT

echo "=== Swapping $NIC MAC to $LICENSE_MAC ==="
sudo ip link set "$NIC" down
sudo ip link set "$NIC" address "$LICENSE_MAC"
sudo ip link set "$NIC" up
echo "MAC swapped."

# Brief pause for NIC to come back up
sleep 1

echo "=== Starting build ==="
"$SCRIPT_DIR/build.sh" "$@"
