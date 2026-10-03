provenance: AI-drafted 2026-10-03 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# MH1 — panel hub / flash router

STM32G031C4T6 on the main board. The CM4's UART `/dev/serial0` ends here; MH1 broadcasts to the panel MCUs (H1S1/H1S3/H1S4) on the slave bus, relays `.shex` loads, and drives the PANEL_DIM PWM (TIM16 CH1, PB8). It is NOT flashed by `loadfw` — it is the router. Reflash only over SWD.

- Source: this folder = the Dropbox/unit `fwbuild/MH1` tree (last edited 2026-08-19) **plus `mh1-dimset.diff`** (S131-era PANEL_DIM fix: 32-step duty table, `'>'`+2 hex digits, boot duty 8 %). `Core/Src/main.c` is the patched file; `main.c.unpatched` is the 08-19 original and `patch main.c.unpatched < mh1-dimset.diff` gives `main.c`.
- Needs **STM32Cube FW_G0 V1.5.0** (CubeMX 6.14.1) for `Drivers/`.
- Build: `../build-mcu.sh <MCU> <path-to-Drivers>` (arm-none-eabi-gcc 14.2.1 20241119, Debian `15:14.2.rel1-1`; CubeIDE used 13.3.rel1 — the image is identical). Drivers/ is not stored here.
- **What is on MW-D24-2 is the dimset build, NOT the `MH1.elf 0fe9717a` on the unit** (that elf is the unpatched 08-19 build; `fwbuild/MH1/Debug/MH1.hex` `369371ec…`, bin `300fc323…` = `MH1-0819`). Flashed (S131 runbook `mx26 docs/runbook-mh1-dimset-swd.md`): `image/MH1.hex` md5 `1110c60aaffae800affdbcaf3649982f`, `image/MH1.bin` `bf21f762cdb418c360046e1649f0e983` (27 440 B). **Reproduces byte-for-byte** with `build-mcu.sh MH1` (hex and bin). The unpatched tree also reproduces `369371ec…`/`300fc323…`. Not re-read from the chip in S168 (unit untouchable); flashed image identity rests on the S131 runbook's `verify_image` and the unit's `/home/app/s131fw/MH1-dimset.bin` (md5 matches).
- **How flashed:** SWD through the unit's openocd (`/home/app/mh1-swd.cfg`, SWD mux channel 3: `pinctrl set 5 op dl; pinctrl set 13 op dh`), `flash write_image erase MH1.hex; verify_image`, then `mww 0xE000ED0C 0x05FA0004` (never `program`/`reset run`); release pins with `pinctrl set 5,13 ip`. Full steps and rollback (`/home/app/s131fw/mh1-pre-dimset.bin`): mx26 `docs/runbook-mh1-dimset-swd.md`.
