# attic

Retired material kept for reference. Nothing here is part of the active build.

- `d24-adau1466/` — the original D24 DSP era: ADAU1466 SigmaStudio project
  (`DSP.ssprj`, `single DSP*`, exported `DSP_Export/` headers) plus the
  Raspberry Pi `dsp_boot` loader (ARM cross-compiler binaries, bcm2835 lib).
  Superseded by the SHARC implementation at `MW/D24/DSP/SHARC/`.
- `sync-from-app.sh` — pre-contract sync script that pulled
  `shared/mx_master.csv` from the mx-app repo. Superseded by
  `sync-from-mx26.sh` and the defs.lock contract flow.
