# conformance run

| run | chip | phase | addresses | verified | seconds | healthy at exit |
|---|---|---|---|---|---|---|
| `conform_s6i_c1.json` | 1 | inert | 4800/4800 | True | None | True |

## presence — every address, written and read back

| verdict | addresses |
|---|---|

## declared units — the documented value, the documented consequence

| check | wrote | expected | observed | verdict | note |
|---|---|---|---|---|---|

## inert probe — a write that changes nothing kernel-visible

| addr | cells | class | words moved | verdict |
|---|---|---|---|---|
| — |  | WINDOW | — | INFO |
| 0x0000 | Chan001Gain001 | POSITIVE CONTROL | 32 | CONTROL OK |
| 0x0039 | Chan001CompThr001 | POSITIVE CONTROL | 32 | CONTROL OK |
| 0x002E | Chan001GateKey001 | 0x002E: C1_GATE_01 GateKey | 0 | INERT CONFIRMED |
| 0x002F | Chan001GateDetSrc001 | 0x002F: C1_GATE_01 GateDetSrc | 0 | INERT CONFIRMED |
| 0x0040 | Chan001CompType001 | 0x0040: C1_COMP_01 CompType | 0 | INERT CONFIRMED |
| 0x0041 | Chan001CompKey001 | 0x0041: C1_COMP_01 CompKey | 0 | INERT CONFIRMED |
| 0x0042 | Chan001CompDetSrc001 | 0x0042: C1_COMP_01 CompDetSrc | 0 | INERT CONFIRMED |
| 0x0043 | Chan001CompLimMode001 | 0x0043: C1_COMP_01 CompLimMode | 0 | INERT CONFIRMED |
| 0x0044 | Chan001CompEqPos001 | 0x0044: C1_COMP_01 CompEqPos | 0 | INERT CONFIRMED |
| 0x0045 | Chan001CompFilterOn001 | 0x0045: C1_COMP_01 CompFilterOn | 0 | INERT CONFIRMED |
| 0x0046 | Chan001CompFilterHpf001, Chan001CompFilterLpf001, Chan001CompFilterQ001 | 0x0046: C1_COMP_01 CompFilter HPF[0] | 0 | INERT CONFIRMED |
| 0x0053 | Chan001RtgDca001 | 0x0053: C1_FDR_01 DCA assignment | 0 | INERT CONFIRMED |
| 0x00BE | Chan002GateKey001 | 0x00BE: C1_GATE_02 GateKey | 0 | INERT CONFIRMED |
| 0x00BF | Chan002GateDetSrc001 | 0x00BF: C1_GATE_02 GateDetSrc | 0 | INERT CONFIRMED |

## negative controls

NONE RUN — this run could not have failed.

## verdict

PASS
