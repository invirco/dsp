#!/usr/bin/env bash
# dryrun_d24.sh -- S66 gate 3: the generated fixtures run against the recorded D24 data, both modes, then the report,
# the comparison with the hand tables and the time projection. Desk only; no unit.
set -euo pipefail
cd "$(dirname "$0")/../.."
python3 tools/accept/gen_accept_fixtures.py --product d24 >/dev/null
python3 tools/accept/replay_d24_recorded.py >/dev/null
OUT=MW/D24/DSP/s66
rm -rf "$OUT/results"
for mode in factory full; do
  for map in "$OUT"/replay/*.json; do
    fx=MW/D24/DSP/accept/fixtures/$(basename "$map")
    python3 tools/pi/dsp4_accept.py run --fixture "$fx" --mode "$mode" --unit MW-D24-2 \
      --source "replay:$map" --out "$OUT/results/$mode"
  done
done > "$OUT/run.out"
python3 tools/pi/dsp4_accept.py report "$OUT/results/factory" "$OUT/results/full" --md "$OUT/report.md" >/dev/null
python3 tools/accept/dryrun_compare.py > "$OUT/compare.md" || echo "compare: DIFFs, see $OUT/compare.md"
{ python3 tools/pi/dsp4_accept.py plan --manifest MW/D24/DSP/accept/manifest.json --mode factory
  python3 tools/pi/dsp4_accept.py plan --manifest MW/D24/DSP/accept/manifest.json --mode full; } > "$OUT/plan.out"
echo "done: $OUT/{run.out,report.md,compare.md,plan.out}"
