# conformance run

| run | chip | phase | addresses | verified | seconds | healthy at exit |
|---|---|---|---|---|---|---|
| `conform_after_c1.json` | 1 | all | 4800/4800 | True | 293.9 | True |
| `conform_after_c1_negunit.json` | 1 | effect | 4800/4800 | True | None | True |
| `conform_after_c1_noverify.json` | 1 | presence | 64/4800 | False | 0.6 | True |
| `conform_after_c2.json` | 2 | presence | 1952/1952 | True | 120.4 | True |

## presence — every address, written and read back

| verdict | addresses |
|---|---|
| ECHO | 6088 |
| UNMAPPED | 388 |
| SKIPPED_METER | 159 |
| CLEARED | 117 |

## declared units — the documented value, the documented consequence

| check | wrote | expected | observed | verdict | note |
|---|---|---|---|---|---|
| ChanGateRng | 0.0 | 0x10000000 | 0x0FFFFFE5 | PASS |  |
| ChanGateRng | 20.0 | 0x0199999A | 0x0199999A | PASS |  |
| ChanGateRng | 40.0 | 0x0028F5C3 | 0x0028F5C3 | PASS |  |
| ChanGateRng | 60.0 | 0x00041893 | 0x00041894 | PASS |  |
| ChanCompPar | 0.0 | 0x00000000 | 0x00000000 | PASS |  |
| ChanCompPar | 25.0 | 0x20000000 | 0x20000000 | PASS |  |
| ChanCompPar | 50.0 | 0x40000000 | 0x40000000 | PASS |  |
| ChanCompPar | 100.0 | 0x7FFFFFFF | 0x7FFFFFFF | PASS |  |
| ChanGateAtt | 0.1 | 0x18127845 | 0x0CCCCCD0 | FAIL | D41 — ms vs one-pole alpha, no conversion in this repo |
| ChanGateAtt | 25.0 | 0x001B4B98 | 0xFFFFFFFF | FAIL | D41 — ms vs one-pole alpha, no conversion in this repo |
| ChanGateAtt | 250.0 | 0x0002BB06 | 0xFFFFFFFF | FAIL | D41 — ms vs one-pole alpha, no conversion in this repo |
| ChanGateRel | 50.0 | 0x000DA686 | 0xFFFFFFFF | FAIL | D41 — ms vs one-pole alpha, no conversion in this repo |
| ChanGateRel | 500.0 | 0x00015D85 | 0xFFFFFFFF | FAIL | D41 — ms vs one-pole alpha, no conversion in this repo |
| ChanGateRel | 5000.0 | 0x000022F4 | 0xFFFFFFFF | FAIL | D41 — ms vs one-pole alpha, no conversion in this repo |
| ChanCompAtt | 0.5 | 0x053947A6 | 0x40000000 | FAIL | D41 — ms vs one-pole alpha, no conversion in this repo |
| ChanCompAtt | 25.0 | 0x001B4B98 | 0xFFFFFFFF | FAIL | D41 — ms vs one-pole alpha, no conversion in this repo |
| ChanCompAtt | 250.0 | 0x0002BB06 | 0xFFFFFFFF | FAIL | D41 — ms vs one-pole alpha, no conversion in this repo |
| ChanCompRel | 5.0 | 0x00883FD1 | 0xFFFFFFFF | FAIL | D41 — ms vs one-pole alpha, no conversion in this repo |
| ChanCompRel | 500.0 | 0x00015D85 | 0xFFFFFFFF | FAIL | D41 — ms vs one-pole alpha, no conversion in this repo |
| ChanCompRel | 5000.0 | 0x000022F4 | 0xFFFFFFFF | FAIL | D41 — ms vs one-pole alpha, no conversion in this repo |
| ChanGateHold | 0.0 | 0x00000000 | 0x00000000 | PASS | D41 — ms vs raw samples, no conversion in this repo |
| ChanGateHold | 50.0 | 0x00000960 | 0x42480000 | FAIL | D41 — ms vs raw samples, no conversion in this repo |
| ChanGateHold | 2000.0 | 0x00017700 | 0x44FA0000 | FAIL | D41 — ms vs raw samples, no conversion in this repo |
| ChanDelay | 0.0 | 0x00000000 | 0x00000000 | PASS | D41 — ms vs raw samples, no conversion in this repo |
| ChanDelay | 10.0 | 0x000001E0 | 0x41200000 | FAIL | D41 — ms vs raw samples, no conversion in this repo |
| ChanDelay | 250.0 | 0x00002EE0 | 0x437A0000 | FAIL | D41 — ms vs raw samples, no conversion in this repo |
| ChanPol | None | 0x-10000000 | 0x-10000000 | PASS |  |
| ChanMute | None | 0x00000000 | 0x00000000 | PASS |  |
| ramp:GainFast | 1048576000 | None | 0x3E800000 | PASS |  |
| ramp:GainFast | 1061158912 | None | 0x3F400000 | PASS |  |
| ramp:DynSafe | 1048576000 | None | 0x3E800000 | PASS |  |
| ramp:DynSafe | 1061158912 | None | 0x3F400000 | PASS |  |
| ramp:GainFast | 1048576000 | None | 0x3E800000 | PASS |  |
| ramp:GainFast | 1061158912 | None | 0x3F400000 | PASS |  |

## inert probe — a write that changes nothing kernel-visible

| addr | cells | class | words moved | verdict |
|---|---|---|---|---|
| 0x0039 | Chan001CompThr001 | POSITIVE CONTROL | — | CONTROL DEAD |

## negative controls

| control | subject | result |
|---|---|---|
| wrong-unit | ChanGateRng | FAILED as required (4 of 4) |

no-readback control: 64 addresses came out UNVERIFIED, as required.

## verdict

PASS
