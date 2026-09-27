provenance: AI-drafted 2026-09-27 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# H1S3 / H1S4 panel firmware: build reproduction from bench-unit source

Unit: app@192.168.1.219. All work done in copies under `/home/app/s129fw/`,
created by `rsync -a` from `/home/app/fwbuild/{H1S3,H1S4}/`. Nothing under
`/home/app/fwbuild/` or `/home/app/firmware/` was modified. No flashing, no
SWD/openocd, no GPIO, no service start/stop, no `d24_*`/`dsp4_*` tool was run.

## 1. Copies made

```
rsync -a /home/app/fwbuild/H1S3/ /home/app/s129fw/H1S3/
rsync -a /home/app/fwbuild/H1S4/ /home/app/s129fw/H1S4/
```

- `/home/app/s129fw/H1S3`: 22M, 311 files
- `/home/app/s129fw/H1S4`: 18M, 281 files

## 2. Toolchain

```
$ arm-none-eabi-gcc --version
arm-none-eabi-gcc (15:14.2.rel1-1) 14.2.1 20241119
```
`which arm-none-eabi-gcc` → `/usr/bin/arm-none-eabi-gcc` (Debian package
`15:14.2.rel1-1`, i.e. gcc 14.2.1).

`-print-multi-lib` ran instantly and lists the full multilib set; the one
relevant to these targets (`-mcpu=cortex-m0 -mthumb -mfloat-abi=soft`) is:
```
thumb/v6-m/nofp;@mthumb@march=armv6s-m@mfloat-abi=soft
```

**Recorded toolchain version mismatch.** Every CubeIDE-generated makefile
fragment (`Debug/makefile`, `Debug/objects.mk`, `Debug/sources.mk`, and each
`subdir.mk`) for both boards carries the header:
```
# Toolchain: GNU Tools for STM32 (13.3.rel1)
```
The box has gcc 14.2.1 (a later STM32-community/Debian ARM GNU toolchain
build), not the exact 13.3.rel1 STM32CubeIDE bundled compiler the project
was recorded against. Despite that, the rebuild below is byte-identical —
this pairing of source and 14.2.1 happens to still reproduce the flashed
image, but the recorded toolchain version does not match what's installed.

**Windows path in the Debug makefile — confirmed in Debug, not just
Release.** `Debug/makefile` line 66/67 for both boards linked against an
absolute Windows path that does not resolve on Linux:
```
H1S3: -T"C:\dropbox\_mx\MW\D24\FW\H1S3\STM32F030R8TX_FLASH.ld"
H1S4: -T"C:\dropbox\_mx\MW\D24\FW\H1S4\STM32F030R8TX_FLASH.ld"
```
The actual linker script sits one level above `Debug/` in each project
(`/home/app/s129fw/H1S3/STM32F030R8TX_FLASH.ld`,
`/home/app/s129fw/H1S4/STM32F030R8TX_FLASH.ld`) — same file, wrong recorded
path. This is the only Windows-specific breakage found; no
`-fcyclomatic-complexity` or other CubeIDE-IDE-only flag is present in the
*current* `Debug/*.mk` files for either board (see note below on a stale
artifact that did have it).

**Pre-existing but stale Linux-build artifacts, not created by this
session.** Both `Debug/` trees already contained, copied over by `rsync`
from `/home/app/fwbuild/`: `makefile.linux` (linker path already fixed to
`../STM32F030R8TX_FLASH.ld`), `fw.sh`/`fw.bat` (a wrapper that `sed`s out
`-fcyclomatic-complexity` before building), `build_linux_H1S3(4).log`, and
`fwReport.txt`. Their timestamps place them on **2025-12-30**, well before
the current flashed image. `stm32f0xx_it.c` was touched 2025-12-30 16:11
and **`matrix.h` in both trees was rewritten 2026-08-19 15:55:38–39, one to
two seconds before the currently-flashed `.elf`/`.map` (15:55:40 / 15:55:41)
were written** — i.e. `matrix.h` is regenerated immediately before the
official build that produced the currently-flashed image, and the Dec-30
`fw.sh`/`fwReport.txt` artifacts predate that regeneration by nearly eight
months. That's why `fwReport.txt`'s own recorded size (`text=21028`) does
not match the flashed image's `text=20572` for H1S3 — it's a stale build
against older source, not evidence against reproducibility. It was left
alone; this session's rebuild uses the standard `Debug/makefile` path, not
`makefile.linux`/`fw.sh`.

## 3. Build invocation

Worked from `Debug/makefile` / `objects.mk` / `sources.mk` /
`Core/Src/subdir.mk` / `Core/Startup/subdir.mk` /
`Drivers/STM32F0xx_HAL_Driver/Src/subdir.mk` directly (not the stale
`makefile.linux`/`fw.sh`). The exact command, run from inside each
`Debug/` copy:

```
make -f makefile all
```

(`all` → `main-build` → the `.elf`/`.map` rule → `secondary-outputs`
producing `.list`, `.hex`, and the size report — all defined in the
makefile already; no extra flags needed.)

**Fix applied, in the copy only:** in `/home/app/s129fw/H1S3/Debug/makefile`
and `/home/app/s129fw/H1S4/Debug/makefile`, replaced the Windows linker
path with the correct relative path (one line changed per file, two
occurrences on the same line — the prerequisite and the `-T` flag):

```
sed -i 's#C:\\dropbox\\_mx\\MW\\D24\\FW\\H1S3\\STM32F030R8TX_FLASH.ld#../STM32F030R8TX_FLASH.ld#g' H1S3/Debug/makefile
sed -i 's#C:\\dropbox\\_mx\\MW\\D24\\FW\\H1S4\\STM32F030R8TX_FLASH.ld#../STM32F030R8TX_FLASH.ld#g' H1S4/Debug/makefile
```
No other file needed editing — `subdir.mk`/`objects.mk`/`sources.mk`
contained no Windows paths and no unsupported flags.

**Before building**, the original artifacts were preserved:
```
H1S3.elf  md5 = 73d0937d150e0cf7f747619c411c8ce4
          size: text=20572 data=1212 bss=2068 dec=23852 (0x5d2c)
H1S4.elf  md5 = 09a5e54e39b7da05a8d092996495c3b5
          size: text=13868 data=876  bss=1916 dec=16660 (0x4114)
```
then `H1S3.elf`→`H1S3.elf.orig`, `H1S4.elf`→`H1S4.elf.orig`, and every
`*.o` under each `Debug/` tree (26 for H1S3, 24 for H1S4 — the other `.o`
files found in the initial tree-wide count live under `Release/`, untouched
and irrelevant to this Debug rebuild) renamed to `*.o.orig`.

`make -f makefile all` then ran clean (no stale `.o`/`.elf` present),
recompiling every source, and finished with exit code 0 for both boards.

## 4. Fresh build vs. original — comparison

`arm-none-eabi-size`, fresh build:
```
H1S3.elf   text=20572 data=1212 bss=2068 dec=23852 (0x5d2c)
H1S4.elf   text=13868 data=876  bss=1916 dec=16660 (0x4114)
```
Identical to the recorded originals in every field, for both boards.

ELF file md5 (fresh vs. `.orig`) **differs**:
```
H1S3.elf      83b892be4c541b8a7ae393b8ca51d34a
H1S3.elf.orig 73d0937d150e0cf7f747619c411c8ce4
H1S4.elf      ce4aabc1feea68657472135c1e6ec199
H1S4.elf.orig 09a5e54e39b7da05a8d092996495c3b5
```
This is expected and immaterial — the `.elf` carries DWARF debug info with
embedded absolute source/build-directory paths (`/home/app/s129fw/...`
here vs. whatever directory the original build ran from), which changes the
ELF bytes without touching the flashable content.

What matters is the flash image. `arm-none-eabi-objcopy -O binary` on each
pair, then md5:
```
H1S3: fresh f06639b6ceab7f854bdaa2b8d9bd7cdb (21784 bytes)
      orig  f06639b6ceab7f854bdaa2b8d9bd7cdb (21784 bytes)
H1S4: fresh 97c4dfea4c1f2a298625dcbfa3376890 (14744 bytes)
      orig  97c4dfea4c1f2a298625dcbfa3376890 (14744 bytes)
```
**Byte-identical**, and the sizes match the task's stated flashed-image
sizes exactly (21784 / 14744 bytes). `cmp -l` between fresh and orig binary
confirms **0 bytes differ** for both boards (`cmp` exit code 0 on both).
Since the raw binaries are 100% identical, there is by construction no
disassembly difference to report — not even in absolute addresses or
build-id constants, because there is no byte difference at all.

**Is the flashed image byte-reproducible from this source with this
toolchain: YES**, for both H1S3 and H1S4. The rebuilt `.bin` (what actually
gets flashed) is bit-for-bit identical to what's on the unit today, using
the source currently on the box, gcc 14.2.1 in place of the recorded
13.3.rel1, and one makefile line fixed per board (the Windows linker-script
path) — no source changes.

## 5. Source facts

### H1S4/Core/Inc/matrix.cs

`MATRIX[]` array and the cell-pointer `enum` (lines 11–27):
```c
11  const unsigned int MATRIX[] = // local matrix cells
12  {
13     0x0, // reserved and unused
14     Sys001Enc001,
15     Sys001Skin001,
16     Sys001Test001,
17     Sys001Test002,
18  };
19  enum // MATRIX cell pointers
20  {
21     p0, // reserved and unused
22     pSys001Enc001,
23     pSys001Skin001,
24     pSys001Test001,
25     pSys001Test002,
26     MATRIX_X,
27  };
```

`rsw[]` (radio switch properties), full (lines 29–37):
```c
struct rSw rsw[] = // radio switch properties
{
    { GPIOC, PC8_Pin, pSys001Skin001, 1 },
    { GPIOA, PA11_Pin, pSys001Skin001, 2 },
    { GPIOF, PF6_Pin, pSys001Skin001, 3 },
    { GPIOA, PA15_Pin, pSys001Skin001, 4 },
    { GPIOB, PB0_Pin, pSys001Skin001, 5 },
    { GPIOB, PB10_Pin, pSys001Skin001, 6 },
};
```

`wled[]` (radio led properties), full (lines 39–50):
```c
struct wLed wled[] = // radio led properties
{
    { GPIOC, PC7_Pin | PC9_Pin, pSys001Skin001, 1 },
    { GPIOA, PA8_Pin | PA12_Pin, pSys001Skin001, 2 },
    { GPIOA, PA13_Pin, pSys001Skin001, 3 },
    { GPIOF, PF7_Pin, pSys001Skin001, 3 },
    { GPIOA, PA14_Pin, pSys001Skin001, 4 },
    { GPIOC, PC10_Pin, pSys001Skin001, 4 },
    { GPIOB, PB1_Pin, pSys001Skin001, 5 },
    { GPIOC, PC5_Pin, pSys001Skin001, 5 },
    { GPIOB, PB2_Pin | PB11_Pin, pSys001Skin001, 6 },
};
```
(All six `rsw[]` entries and all nine `wled[]` entries key off
`pSys001Skin001` — this board has only one cell used as a switch/LED
address in the matrix; the `radioData` field, not `matrixAdd`, is what
distinguishes the individual switches/LEDs.)

### H1S4/Core/Inc/matrix.h — the four defines
```
5163:#define Sys001Enc001 5232
5342:#define Sys001Skin001 5412
5343:#define Sys001Test001 5414
5344:#define Sys001Test002 5415
```

### H1S3/Core/Inc/matrix.h — the same four defines
```
5163:#define Sys001Enc001 5232
5342:#define Sys001Skin001 5412
5343:#define Sys001Test001 5414
5344:#define Sys001Test002 5415
```
Identical line numbers and identical numeric values on both boards (H1S3
right panel, H1S4 left panel) — `matrix.h` is evidently the same generated
file (or generated from the same global matrix definition) dropped into
both project trees; the two boards differentiate cell usage in `matrix.cs`
(here, both only reference `pSys001Skin001`, but H1S3's own `matrix.cs` — not
requested in full — would use the same defines for its own radio
switch/LED set).

### Is matrix.h generated?

Yes, explicitly. First 15 lines (identical in both H1S3 and H1S4 copies):
```c
1  // matrix.h - GENERATED on-unit from config/_matrix.mxc (app build 260714102659)
2  // 2026-08-19: aligns panel fw addresses with the RUNNING app generation.
3  // Do not confuse with the Dropbox MX/matrix.h (newer generation, drifted).
4  #define AaAux001Mtr001 1
5  #define AaAux002Mtr001 2
6  #define AaAux003Mtr001 3
7  #define AaAux004Mtr001 4
8  #define AaAux005Mtr001 5
9  #define AaAux006Mtr001 6
10 #define AaAux007Mtr001 7
11 #define AaAux008Mtr001 8
12 #define AaChan001Mtr001 9
13 #define AaChan001Mtr002 10
14 #define AaChan002Mtr001 11
15 #define AaChan002Mtr002 12
```
The header names its generator input (`config/_matrix.mxc`), the app build
that generated it (`260714102659`), and explicitly warns that the Dropbox
copy under `MX/matrix.h` is a newer, drifted generation — i.e. there are
now two divergent lineages of this header and the on-unit one used for this
build is the older/pinned one. Its rewrite timestamp (2026-08-19 15:55:38)
lands 1–2 seconds before the currently-flashed `.elf` was linked, confirming
it was regenerated as an immediate precursor to that official build.

`matrix.h` is 5415 lines long in total.

### MATRIX_X and hardcoded indices

`MATRIX_X` = **5** (the enum in `matrix.cs`: `p0`=0, `pSys001Enc001`=1,
`pSys001Skin001`=2, `pSys001Test001`=3, `pSys001Test002`=4,
`MATRIX_X`=5 — five slots, index 0 reserved/unused).

No code in `matrix.cs` indexes `matrix[][]` with a bare numeric literal.
Every access uses either the named enum constants (`p0`,
`pSys001Skin001`, …), a loop bound by `MATRIX_X` (`for (int i = 1; i <
MATRIX_X; i++)` in `Eol()`), or a runtime pointer (`TXptr`, `s.matrixAdd`)
wrapped modulo `MATRIX_X` in `Poll()`. `unsigned char
matrix[MATRIX_X][MATRIX_Y]` is itself sized off the enum, so appending a
fifth cell to `MATRIX[]` does **not** require hunting down a hardcoded
array-size constant elsewhere — as long as the same new symbol is appended
to *both* the `MATRIX[]` initializer list and the parallel `enum` in
lock-step. That parallelism is the fragile part: the two lists are
independent C constructs with no compiler-enforced link between them, so
adding to one and forgetting the other silently misaligns every index
after the insertion point without a compile error.
