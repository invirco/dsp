provenance: AI-drafted 2026-09-27 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# Unit configuration this session changed on MW-D24-2

Three files, all of them `/etc` on the unit and none of them a build input.
Kept here because a unit's configuration that exists only on the unit is a
configuration nobody can review.

| file | what it does | why |
|---|---|---|
| `s128-cores.conf` → `/etc/systemd/system/d24-testui.service.d/` | `LimitCORE=infinity` on the display service | the two SIGSEGVs left no managed trace; a core is the only thing left to read |
| `90-d24-cores.conf` → `/etc/sysctl.d/` | `kernel.core_pattern`, `fs.suid_dumpable` | the kernel's default writes a file called `core` into a working directory, or nothing |
| `s105-capture.conf` → **REMOVED** from `/etc/systemd/system/d24-testui.service.d/` | it set `MX_DRM_CAPTURE_PATH` and `MX_DRM_CAPTURE_MS=1000` | measured: it costs ~43 % of a core continuously and stalls the UI thread ~180 ms every 3 s, which is the whole of NW3's 3-6 % packet loss. It is an S105 diagnostic, not a factory setting. Kept at `/home/app/s128/s105-capture.conf.removed` on the unit for a session that wants screenshots again. |

`s123-latency.conf` (`MX_FACTORY_LATENCY_LOG`) is LEFT IN PLACE: it appends one
CSV line per screen change and costs nothing measurable.
