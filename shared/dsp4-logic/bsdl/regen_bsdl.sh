#!/bin/bash
# regen_bsdl.sh -- regenerate the 5M1270ZT144 pre-configuration BSDL with the
# local Quartus and check it carries the five facts dspcard_id.py source J
# uses (S175). The .bsd is Intel tool output under the Quartus licence and is
# NOT committed (.gitignore); this script is how to get it back.
#
#   ./regen_bsdl.sh            writes ./5M1270ZT144C4_pre.bsd, verifies it
set -eu
HERE="$(cd "$(dirname "$0")" && pwd)"
QUARTUS="${QUARTUS:-/opt/intelFPGA_lite/21.1/quartus}"
WANT_SHA=7bdd8e3effc89fa939e954423a00bc5e0b6e68ab2b860535256b49cc59f4bb70
F="$HERE/5M1270ZT144C4_pre.bsd"

# The option parser in bsdl_cmd.tcl strips one leading dash and splits on
# '=': it takes `--output_directory=<dir>`, not `-output_directory <dir>`.
"$QUARTUS/bin/quartus_eda" --bsdl 5M1270ZT144C4 --output_directory="$HERE" >/dev/null
SHA=$(sha256sum "$F" | cut -d' ' -f1)
echo "sha256 $SHA"
[ "$SHA" = "$WANT_SHA" ] || echo "!! sha256 differs from the S175 file (another Quartus build?) -- checking the facts anyway"

fail=0
chk() { grep -q -- "$2" "$F" && echo "ok   $1" || { echo "FAIL $1"; fail=1; }; }
chk "IR length 10"            'INSTRUCTION_LENGTH of MAX_V_5M1270ZT144 : entity is 10;'
chk "SAMPLE = 0000000101"     '"SAMPLE            (0000000101)'
chk "IDCODE 0x020A30DD"       '"0010000010100011"&'
chk "boundary length 636"     'BOUNDARY_LENGTH of MAX_V_5M1270ZT144 : entity is 636;'
chk "cell 522 = IO81 input"   '"522   (BC_4, IO81, input, X)'
exit $fail
