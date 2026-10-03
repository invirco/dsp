# S167 H1S4 pedal relay

Flashed on MW-D24-2 2026-10-03 14:05Z (`app cli loadfw H1S4`, after `sreset.py`).

- `H1S4.shex` md5 `ff79052ef96b09976173bb842a11382a`, header id `H1S3` (the crossed socket id, per S135).
- Baseline: `f54848b0` (S139) = unit `/home/app/fwbuild/H1S4` + `s139/gen/H1S4/matrix.cs` + `s139/gen/matrix.h`.
  `Debug/makefile` needs its `.ld` path changed to `../STM32F030R8TX_FLASH.ld`. With gcc 14.2.1 that rebuild is byte-identical to `f54848b0`.
- Change: the new `Core/Inc/pedal_relay.cs`, plus the hooks in `diff-vs-f54848b0.patch`.
  The wire protocol is in the header of `pedal_relay.cs`.
- Rollback: `/home/app/firmware/H1S4.shex.bak-s167-pre` (= `f54848b0`), then `sreset.py` + `app cli loadfw H1S4`.
