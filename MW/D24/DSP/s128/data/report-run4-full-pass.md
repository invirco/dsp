# D24 factory test report

Unit 10000000830b03af  ·  2026-09-27T15:43:23Z  ·  pass 1  ·  test image factory-test-v2

| result | rows |
|---|---|
| pass | 22 |
| fail | 1 |
| no data | 58 |
| ignored | 0 |
| skipped | 0 |
| not tested | 88 |
| no verdict | 33 |
| **all rows** | **202** |

Wall time this pass 790 s.  Automatic part 661 s, operator part 77 s.

The unit checked itself WHILE the operator worked: the bench setup and the panel checks (637 s) ran under the first half of the automatic set, and the network checks ran under the analog paths. That is why the two parts above add up to more than the wall time.

## Every check that is not a pass

| check | what it is | result | reading | limit | judged by | pass | what to do |
|---|---|---|---|---|---|---|---|
| 128 | network socket | fail | bench host 192.168.1.211: worst 4.0% loss over 3 passes [3.0, 4.0, 4.0], max RTT 1.202 ms… | 0% loss, max RTT < 5 ms | the unit | 1 | look at this part before the unit goes on |
| 43 | MONO AUX button | no data | no key code arrived within 30 s |  | the operator | 1 | the check ran but could not read an answer |
| 44 | MONO AUX button LEDs (white pair) | no data | not reached: the button sent nothing |  | the operator | 1 | the check ran but could not read an answer |
| 45 | STEREO AUX button | no data | no key code arrived within 30 s |  | the operator | 1 | the check ran but could not read an answer |
| 46 | STEREO AUX button LEDs (white pair) | no data | not reached: the button sent nothing |  | the operator | 1 | the check ran but could not read an answer |
| 47 | FX button | no data | no key code arrived within 30 s |  | the operator | 1 | the check ran but could not read an answer |
| 48 | FX button LEDs (white pair) | no data | not reached: the button sent nothing |  | the operator | 1 | the check ran but could not read an answer |
| 49 | EQ button | no data | no key code arrived within 30 s |  | the operator | 1 | the check ran but could not read an answer |
| 50 | EQ button LEDs (white pair) | no data | not reached: the button sent nothing |  | the operator | 1 | the check ran but could not read an answer |
| 51 | AUX ON FADERS button | no data | no key code arrived within 30 s |  | the operator | 1 | the check ran but could not read an answer |
| 52 | AUX ON FADERS button LEDs (white pair) | no data | not reached: the button sent nothing |  | the operator | 1 | the check ran but could not read an answer |
| 53 | OVERVIEW button | no data | no key code arrived within 30 s |  | the operator | 1 | the check ran but could not read an answer |
| 54 | OVERVIEW button LEDs (white pair) | no data | not reached: the button sent nothing |  | the operator | 1 | the check ran but could not read an answer |
| 56 | panel microphone and speaker | no data | no settled window for: base, tone, back | a tone in the window (THD+N <= -6 dB, or SNR >= 13.7 dB ove… | the unit | 1 | the check ran but could not read an answer |
| 59 | FX MUTE button | no data | no key code arrived within 30 s |  | the operator | 1 | the check ran but could not read an answer |
| 60 | FX MUTE button LEDs (white pair) | no data | The always-lit rings: not checked, because this screen cannot ask a yes or no question ye… |  | the unit | 1 | the check ran but could not read an answer |
| 61 | FX MUTE red LEDs | no data | not reached: the button sent nothing |  | the operator | 1 | the check ran but could not read an answer |
| 62 | HOME button | no data | no key code arrived within 30 s |  | the operator | 1 | the check ran but could not read an answer |
| 63 | HOME button LEDs (white pair) | no data | not reached: the button sent nothing |  | the operator | 1 | the check ran but could not read an answer |
| 64 | MENU button | no data | no key code arrived within 30 s |  | the operator | 1 | the check ran but could not read an answer |
| 65 | MENU button LEDs (white pair) | no data | not reached: the button sent nothing |  | the operator | 1 | the check ran but could not read an answer |
| 66 | +48 button | no data | no key code arrived within 30 s |  | the operator | 1 | the check ran but could not read an answer |
| 67 | +48 button LEDs (white pair) | no data | not reached: the button sent nothing |  | the operator | 1 | the check ran but could not read an answer |
| 68 | FEEDBACK button | no data | no key code arrived within 30 s |  | the operator | 1 | the check ran but could not read an answer |
| 69 | FEEDBACK button LEDs (white pair) | no data | not reached: the button sent nothing |  | the operator | 1 | the check ran but could not read an answer |
| 70 | MUTE button | no data | no key code arrived within 30 s |  | the operator | 1 | the check ran but could not read an answer |
| 71 | MUTE button LEDs (white pair) | no data | not reached: the button sent nothing |  | the operator | 1 | the check ran but could not read an answer |
| 72 | SCENE button | no data | no key code arrived within 30 s |  | the operator | 1 | the check ran but could not read an answer |
| 73 | SCENE button LEDs (white pair) | no data | not reached: the button sent nothing |  | the operator | 1 | the check ran but could not read an answer |
| 74 | L button | no data | no key code arrived within 30 s |  | the operator | 1 | the check ran but could not read an answer |
| 75 | L button LEDs (white pair) | no data | not reached: the button sent nothing |  | the operator | 1 | the check ran but could not read an answer |
| 76 | C button | no data | no key code arrived within 30 s |  | the operator | 1 | the check ran but could not read an answer |
| 77 | C button LEDs (white pair) | no data | not reached: the button sent nothing |  | the operator | 1 | the check ran but could not read an answer |
| 79 | CH ASSIGN button | no data | no key code arrived within 30 s |  | the operator | 1 | the check ran but could not read an answer |
| 80 | CH ASSIGN button LEDs (white pair) | no data | not reached: the button sent nothing |  | the operator | 1 | the check ran but could not read an answer |
| 81 | R button | no data | no key code arrived within 30 s |  | the operator | 1 | the check ran but could not read an answer |
| 82 | R button LEDs (white pair) | no data | not reached: the button sent nothing |  | the operator | 1 | the check ran but could not read an answer |
| 83 | MONITOR button | no data | no key code arrived within 30 s |  | the operator | 1 | the check ran but could not read an answer |
| 84 | MONITOR button LEDs (white pair) | no data | not reached: the button sent nothing |  | the operator | 1 | the check ran but could not read an answer |
| 85 | REC/PLY button | no data | no key code arrived within 30 s |  | the operator | 1 | the check ran but could not read an answer |
| 86 | REC/PLY button LEDs (white pair) | no data | The always-lit rings: not checked, because this screen cannot ask a yes or no question ye… |  | the unit | 1 | the check ran but could not read an answer |
| 87 | REC/PLY red LEDs | no data | not reached: the button sent nothing |  | the operator | 1 | the check ran but could not read an answer |
| 88 | STUDIO CTL button | no data | no key code arrived within 30 s |  | the operator | 1 | the check ran but could not read an answer |
| 89 | STUDIO CTL button LEDs (white pair) | no data | not reached: the button sent nothing |  | the operator | 1 | the check ran but could not read an answer |
| 90 | Encoder ring | no data | the encoder sent no ring position within 30 s |  | the operator | 1 | the check ran but could not read an answer |
| 91 | Encoder ring LEDs | no data | The ring around the encoder: not checked, because this screen cannot ask a yes or no ques… |  | the unit | 1 | the check ran but could not read an answer |
| 102 | main control processor link | no data | no H1S1 version cell; host side H1S1.shex 272868c889fc87ead0a3b4bb277f55e2 | non-zero version equal to the H1S1.shex manifest | the unit | 1 | the check ran but could not read an answer |
| 107 | audio processor select line 6 | no data | CS6 reaches no fitted part | no part behind the select, and no read path to the net | the unit | 1 | the check ran but could not read an answer |
| 108 | audio processor select line 7 | no data | CS7 is not a DSP chip select: it is SWD_EN1, CM4-owned | n/a -- assert-one-read-one does not apply to this net | the unit | 1 | the check ran but could not read an answer |
| 109 | audio processor select line 8 | no data | CS8 is not a DSP chip select: it is SWD_EN3, CM4-owned | n/a -- assert-one-read-one does not apply to this net | the unit | 1 | the check ran but could not read an answer |
| 125 | right panel processor link | no data | no BOOT0/NRST drive on H1S1 | ROM ACK 0x79 and re-enumeration | the unit | 1 | the check ran but could not read an answer |
| 126 | left panel processor link | no data | no BOOT0/NRST drive on H1S1 | ROM ACK 0x79 and re-enumeration | the unit | 1 | the check ran but could not read an answer |
| 130 | top-panel USB socket (hub port 3) | no data | nothing on port 3 | a device enumerates on that socket | the unit | 1 | the check ran but could not read an answer |
| 131 | top-panel USB socket (hub port 4) | no data | nothing on port 4 | a device enumerates on that socket | the unit | 1 | the check ran but could not read an answer |
| 142 | output converter link | no data | retired: a TX slot read cannot prove a converter -- the outputs are proved by the patch p… | the DAC outputs carry the signal written to them | the unit | 1 | the check ran but could not read an answer |
| 196 | clock master | no data | design id unreadable under dsp4-pcm-slave; BLK_OVERRUN delta over 13 s: chip1 0 chip2 0 | id = d02d83b3cc22 and zero overrun delta | the unit | 1 | the check ran but could not read an answer |
| 197 | output converters | no data | retired: a TX slot read cannot prove a converter -- the outputs are proved by the patch p… | the DAC outputs carry the signal written to them | the unit | 1 | the check ran but could not read an answer |
| 200 | power processor | no data | no reader for the power MCU's published words; AN_EN (GPIO26) = 26: op -- pd / hi | state running, PWR_FAIL clear, AN_EN as expected | the unit | 1 | the check ran but could not read an answer |
| 202 | main control processor | no data | no H1S1 version cell; host side H1S1.shex 272868c889fc87ead0a3b4bb277f55e2 | non-zero version equal to the H1S1.shex manifest | the unit | 1 | the check ran but could not read an answer |
| 11 | MIC 9 | no verdict |  |  | - | - | not run in this pass |
| 12 | MIC 10 | no verdict |  |  | - | - | not run in this pass |
| 13 | MIC 11 | no verdict |  |  | - | - | not run in this pass |
| 14 | MIC 12 | no verdict |  |  | - | - | not run in this pass |
| 15 | MIC 17 | no verdict |  |  | - | - | not run in this pass |
| 16 | MIC 18 | no verdict |  |  | - | - | not run in this pass |
| 17 | MIC 19 | no verdict |  |  | - | - | not run in this pass |
| 18 | MIC 21 | no verdict |  |  | - | - | not run in this pass |
| 19 | MIC 22 | no verdict |  |  | - | - | not run in this pass |
| 20 | MIC 23 | no verdict |  |  | - | - | not run in this pass |
| 21 | MIC 24 | no verdict |  |  | - | - | not run in this pass |
| 22 | MIC 7 | no verdict |  |  | - | - | not run in this pass |
| 23 | MIC 8 | no verdict |  |  | - | - | not run in this pass |
| 24 | MIC 20 | no verdict |  |  | - | - | not run in this pass |
| 25 | Aux Out A1 (doubles as Monitor 1) | no verdict |  |  | - | - | not run in this pass |
| 26 | Aux Out A2 | no verdict |  |  | - | - | not run in this pass |
| 27 | Aux Out A3 | no verdict |  |  | - | - | not run in this pass |
| 28 | Aux Out A4 | no verdict |  |  | - | - | not run in this pass |
| 29 | Aux Out A5 | no verdict |  |  | - | - | not run in this pass |
| 30 | Aux Out A6 | no verdict |  |  | - | - | not run in this pass |
| 31 | Aux Out A7 | no verdict |  |  | - | - | not run in this pass |
| 32 | Aux Out A8 | no verdict |  |  | - | - | not run in this pass |
| 33 | Main Out L | no verdict |  |  | - | - | not run in this pass |
| 34 | Main Out R | no verdict |  |  | - | - | not run in this pass |
| 36 | Monitor Out L (TRS, unbalanced) | no verdict |  |  | - | - | not run in this pass |
| 37 | Monitor Out R (TRS, unbalanced) | no verdict |  |  | - | - | not run in this pass |
| 38 | Talkback TB (XLR) | no verdict |  |  | - | - | not run in this pass |
| 39 | Aux Out A 1-2 (TRS, Phone Jack sub-assembly) | no verdict |  |  | - | - | not run in this pass |
| 40 | Aux Out A 3-4 (TRS, Phone Jack sub-assembly) | no verdict |  |  | - | - | not run in this pass |
| 41 | Aux Out A 5-6 (TRS, Phone Jack sub-assembly) | no verdict |  |  | - | - | not run in this pass |
| 42 | Aux Out A 7-8 (TRS, Phone Jack sub-assembly) | no verdict |  |  | - | - | not run in this pass |
| 146 | headphone link | no verdict |  |  | - | - | not run in this pass |
| 147 | small jack link | no verdict |  |  | - | - | not run in this pass |
| 1 | MIC 1 | not tested |  |  | - | 1 | no signal path in the patch list reaches this row |
| 2 | MIC 2 | not tested |  |  | - | 1 | no signal path in the patch list reaches this row |
| 3 | MIC 3 | not tested |  |  | - | 1 | no signal path in the patch list reaches this row |
| 4 | MIC 4 | not tested |  |  | - | 1 | no signal path in the patch list reaches this row |
| 5 | MIC 13 | not tested |  |  | - | 1 | no signal path in the patch list reaches this row |
| 6 | MIC 14 | not tested |  |  | - | 1 | no signal path in the patch list reaches this row |
| 7 | MIC 15 | not tested |  |  | - | 1 | no signal path in the patch list reaches this row |
| 8 | MIC 16 | not tested |  |  | - | 1 | no signal path in the patch list reaches this row |
| 9 | MIC 5 | not tested |  |  | - | 1 | no signal path in the patch list reaches this row |
| 10 | MIC 6 | not tested |  |  | - | 1 | no signal path in the patch list reaches this row |
| 35 | Center/LF Out | not tested |  |  | - | 1 | the Centre/LF socket is on a converter lane this product has no cell for: nothing the host can write puts a signal on it |
| 55 | BOOT0 indicator LED | not tested |  |  | - | 1 | the red indicator is driven by the processor boot pin, not by the processor, so nothing the host writes can light it |
| 58 | Pedal UART through-path | not tested |  |  | - | 1 | the pedal path through this panel needs the pedal and its lead, which is the foot pedal station |
| 78 | C red LED | not tested |  |  | - | 1 | no indicator is declared for this designator: the firmware table gives the C button one indicator pair and the loop grades it on row 77 |
| 92 | Talkback switch + LEDs (pass-through) | not tested |  |  | - | 1 | the talkback switch and its two indicators pass through the panel processor with no matrix cell bound, so the host can neither read the swi… |
| 93 | Mini-jack insertion sense (pass-through) | not tested |  |  | - | 1 | the mini-jack sense passes through the panel processor with no matrix cell bound, so the host cannot read it |
| 94 | TEMP / BLOWER / FAN sense (pass-through) | not tested |  |  | - | 1 | the temperature, blower and fan lines pass through the panel processor with no matrix cell bound, so the host cannot read them |
| 95 | Mini-jack 1 (3.5 mm, Mini Jack sub-assembly) | not tested |  |  | - | 1 | no signal path in the patch list reaches this row |
| 96 | Mini-jack 2 (3.5 mm, Mini Jack sub-assembly) | not tested |  |  | - | 1 | no signal path in the patch list reaches this row |
| 97 | Phones 1 (headphone jack) | not tested |  |  | - | 1 | the headphone socket is on two converter lanes this product has no cells for: nothing the host can write puts a signal on it |
| 98 | Footswitch 1 | not tested |  |  | - | 1 | the host cannot see this control or sense line change: this unit has no per-control read through the panel processors |
| 99 | Footswitch 2 | not tested |  |  | - | 1 | the host cannot see this control or sense line change: this unit has no per-control read through the panel processors |
| 100 | 7-segment display + LEDs | not tested |  |  | - | 1 | the host cannot light one indicator at a time: this unit has no indicator drive for the panel processors |
| 101 | Pedal link + 9 V | not tested |  |  | - | 1 | the foot pedal and its lead are not at the bench |
| 113 | PSU monitor ADC PAD0 | not tested |  |  | - | 1 | no test is declared for this row: it is out of scope for the factory test or its method has not been written |
| 114 | PSU monitor ADC PAD1 | not tested |  |  | - | 1 | no test is declared for this row: it is out of scope for the factory test or its method has not been written |
| 115 | PSU monitor ADC PAD2 | not tested |  |  | - | 1 | no test is declared for this row: it is out of scope for the factory test or its method has not been written |
| 116 | PSU monitor ADC PAD3 | not tested |  |  | - | 1 | no test is declared for this row: it is out of scope for the factory test or its method has not been written |
| 117 | PSU monitor ADC PAD4 | not tested |  |  | - | 1 | no test is declared for this row: it is out of scope for the factory test or its method has not been written |
| 118 | PSU monitor ADC PAD5 | not tested |  |  | - | 1 | no test is declared for this row: it is out of scope for the factory test or its method has not been written |
| 119 | PSU monitor ADC PAD6 | not tested |  |  | - | 1 | no test is declared for this row: it is out of scope for the factory test or its method has not been written |
| 120 | PSU monitor ADC PAD7 | not tested |  |  | - | 1 | no test is declared for this row: it is out of scope for the factory test or its method has not been written |
| 121 | PSU monitor ADC PAD8 | not tested |  |  | - | 1 | no test is declared for this row: it is out of scope for the factory test or its method has not been written |
| 122 | PSU monitor ADC PAD9 | not tested |  |  | - | 1 | no test is declared for this row: it is out of scope for the factory test or its method has not been written |
| 123 | PSU monitor ADC PAD10 | not tested |  |  | - | 1 | no test is declared for this row: it is out of scope for the factory test or its method has not been written |
| 124 | PSU monitor ADC PAD11 | not tested |  |  | - | 1 | no test is declared for this row: it is out of scope for the factory test or its method has not been written |
| 129 | foot pedal socket | not tested |  |  | - | 1 | the foot pedal and its lead are not at the bench |
| 132 | second screen socket (not fitted) | not tested |  |  | - | 1 | the second screen socket is a placeholder on this revision and is not fitted |
| 134 | Power Switch | not tested |  |  | - | 1 | working the power switch shuts the unit down; it is checked when the session ends, not inside a pass |
| 135 | expansion card USB-C socket | not tested |  |  | - | 1 | the expansion card this row belongs to does not exist yet |
| 136 | expansion link 1 | not tested |  |  | - | 1 | the expansion card this row belongs to does not exist yet |
| 137 | expansion link 2 | not tested |  |  | - | 1 | the expansion card this row belongs to does not exist yet |
| 138 | expansion link 3 | not tested |  |  | - | 1 | the expansion card this row belongs to does not exist yet |
| 145 | foot pedal link | not tested |  |  | - | 1 | the foot pedal and its lead are not at the bench |
| 148 | screen ribbon link | not tested |  |  | - | 1 | this row is a screen link, not an audio path: it does not belong to this station |
| 149 | expansion compatibility link | not tested |  |  | - | 1 | the expansion card this row belongs to does not exist yet |
| 150 | analog board supply link | not tested |  |  | - | 1 | no test is declared for this row: it is out of scope for the factory test or its method has not been written |
| 152 | fan link | not tested |  |  | - | 1 | the expansion card this row belongs to does not exist yet |
| 153 | J11 (power link / header) | not tested |  |  | - | 1 | board-level test at the assembler |
| 154 | J12 (power link / header) | not tested |  |  | - | 1 | no test is declared for this row: it is out of scope for the factory test or its method has not been written |
| 155 | J13 (power link / header) | not tested |  |  | - | 1 | no test is declared for this row: it is out of scope for the factory test or its method has not been written |
| 156 | J14 (power link / header) | not tested |  |  | - | 1 | no test is declared for this row: it is out of scope for the factory test or its method has not been written |
| 157 | J23 (power link / header) | not tested |  |  | - | 1 | no test is declared for this row: it is out of scope for the factory test or its method has not been written |
| 158 | J24 (power link / header) | not tested |  |  | - | 1 | no test is declared for this row: it is out of scope for the factory test or its method has not been written |
| 159 | J33 (power link / header) | not tested |  |  | - | 1 | no test is declared for this row: it is out of scope for the factory test or its method has not been written |
| 160 | J34 (power link / header) | not tested |  |  | - | 1 | no test is declared for this row: it is out of scope for the factory test or its method has not been written |
| 161 | J43 (power link / header) | not tested |  |  | - | 1 | no test is declared for this row: it is out of scope for the factory test or its method has not been written |
| 162 | J44 (power link / header) | not tested |  |  | - | 1 | no test is declared for this row: it is out of scope for the factory test or its method has not been written |
| 163 | J56 (board header) | not tested |  |  | - | 1 | board-level test at the assembler |
| 164 | J1 (power link / header) | not tested |  |  | - | 1 | covered by the clock master test: it already needs this header’s clock and logic-bus lines |
| 165 | J2 (power link / header) | not tested |  |  | - | 1 | covered by the clock master test: it already needs this header’s clock and logic-bus lines |
| 166 | J3 (power link / header) | not tested |  |  | - | 1 | covered by the converter-select, microphone-gain-latch and audio-processor select/ready tests: every net on this header already has its own… |
| 167 | J4 (power link / header) | not tested |  |  | - | 1 | covered by the converter-select, microphone-gain-latch and audio-processor select/ready tests: every net on this header already has its own… |
| 168 | J6 (power link / header) | not tested |  |  | - | 1 | covered by the audio-processor select and ready tests: both processors’ select and ready lines on this header already have their own automa… |
| 169 | J4 (power link / header) | not tested |  |  | - | 1 | board-level test at the assembler |
| 170 | J5 (board header) | not tested |  |  | - | 1 | board-level test at the assembler |
| 171 | J6 (board header) | not tested |  |  | - | 1 | board-level test at the assembler |
| 172 | J7 (power link / header) | not tested |  |  | - | 1 | covered by the network link, error-counter, packet-loss and throughput tests: they already exercise this magjack |
| 173 | J10 (power link / header) | not tested |  |  | - | 1 | board-level test at the assembler |
| 174 | J14 (debug / test header) | not tested |  |  | - | 1 | board-level test at the assembler |
| 175 | J15 (debug / test header) | not tested |  |  | - | 1 | board-level test at the assembler |
| 176 | J19 (power link / header) | not tested |  |  | - | 1 | no test is declared for this row: it is out of scope for the factory test or its method has not been written |
| 177 | J20 (board header) | not tested |  |  | - | 1 | board-level test at the assembler |
| 178 | J21 (board header) | not tested |  |  | - | 1 | board-level test at the assembler |
| 179 | J22 (power link / header) | not tested |  |  | - | 1 | board-level test at the assembler |
| 180 | J23 (debug / test header) | not tested |  |  | - | 1 | board-level test at the assembler |
| 181 | J24 (power link / header) | not tested |  |  | - | 1 | covered by the compute-module test: the unit being up and reachable already proves this connector |
| 182 | J25 (power link / header) | not tested |  |  | - | 1 | covered by the compute-module test: the unit being up and reachable already proves this connector |
| 183 | J26 (board header) | not tested |  |  | - | 1 | board-level test at the assembler |
| 184 | J27 (power link / header) | not tested |  |  | - | 1 | board-level test at the assembler |
| 185 | J30 (power link / header) | not tested |  |  | - | 1 | no test is declared for this row: it is out of scope for the factory test or its method has not been written |
| 186 | J31 (power link / header) | not tested |  |  | - | 1 | board-level test at the assembler |
| 187 | J32 (debug / test header) | not tested |  |  | - | 1 | board-level test at the assembler |
| 188 | J35 (power link / header) | not tested |  |  | - | 1 | no test is declared for this row: it is out of scope for the factory test or its method has not been written |
| 189 | J36 (power link / header) | not tested |  |  | - | 1 | no test is declared for this row: it is out of scope for the factory test or its method has not been written |
| 190 | J37 (power link / header) | not tested |  |  | - | 1 | no test is declared for this row: it is out of scope for the factory test or its method has not been written |
| 191 | J38 (power link / header) | not tested |  |  | - | 1 | no test is declared for this row: it is out of scope for the factory test or its method has not been written |
| 192 | J39 (power link / header) | not tested |  |  | - | 1 | no test is declared for this row: it is out of scope for the factory test or its method has not been written |

## Every check that passed

| check | what it is | reading | judged by | pass |
|---|---|---|---|---|
| 103 | audio processor select line 1 | CS1 asserted (GPIO6): CHIP_ID 1 BUILD_ID 0x20260812 | the unit | 1 |
| 104 | audio processor select line 2 | CS2 asserted (GPIO24): CHIP_ID 2 BUILD_ID 0x20260812 | the unit | 1 |
| 105 | audio processor select line 3 | CS3/GPIO8 SPI_RDY: running hi, in reset lo, after boot hi (BOOT_STAGE 7) | the unit | 1 |
| 106 | audio processor select line 4 | CS4/GPIO12 SPI_RDY: running hi, in reset lo, after boot hi (BOOT_STAGE 7) | the unit | 1 |
| 110 | audio processor reset line | FRAME_COUNT 8506 -> 11593 advancing; after !RST_D (GPIO16) low 200 ms: None -> None | the unit | 1 |
| 111 | microphone gain chain latch | wrote 05 09 0D 11 15 19 1D 21 25 29 2D 31 35 39 3D 41 45 49 4D 51 55 59 5D 61 00, read ba… | the unit | 1 |
| 112 | talkback converter select line | 05H = 0xBB | the unit | 1 |
| 127 | screen link | HDMI-A-1 connected; EDID RTK 10811, native 1920x1080, active=True (informational, not gat… | the unit | 1 |
| 133 | IEC Power Inlet | the unit has been running from its mains inlet for 6.4 hours | the unit | 1 |
| 139 | audio processor A link | CHIP_ID 1 BUILD_ID 0x20260812 BOOT_STAGE 7, FRAME_COUNT 20355->24444 (3005 blocks/s), 28/… | the unit | 1 |
| 140 | audio processor B link | CHIP_ID 2 BUILD_ID 0x20260812 BOOT_STAGE 7, FRAME_COUNT 20825->31216 (3008 blocks/s) | the unit | 1 |
| 141 | input converter link | lane 0 (U15): 8/8 CARRYING, rms -117.5..-115.1 dBFS; lane 1 (U39): 8/8 CARRYING, rms -113… | the unit | 1 |
| 143 | right panel link | H1S3 S_TEST = '// H1S3 SW Right'; app log: | the unit | 1 |
| 144 | left panel link | H1S4 S_TEST = '// H1S4 SW Left'; app log: | the unit | 1 |
| 151 | screen power link | inferred from screen link PASS | the unit | 1 |
| 193 | compute module | throttled=0x0 temp=50.1 C core=0.9100V app=d24-testui | the unit | 1 |
| 194 | audio processor A | CHIP_ID 1 BUILD_ID 0x20260812 BOOT_STAGE 7, FRAME_COUNT 20355->24444 (3005 blocks/s), 28/… | the unit | 1 |
| 195 | audio processor B | CHIP_ID 2 BUILD_ID 0x20260812 BOOT_STAGE 7, FRAME_COUNT 20825->31216 (3008 blocks/s) | the unit | 1 |
| 198 | input converters | lane 0 (U15): 8/8 CARRYING, rms -117.5..-115.1 dBFS; lane 1 (U39): 8/8 CARRYING, rms -113… | the unit | 1 |
| 199 | talkback converter | 05H = 0xBB | the unit | 1 |
| 201 | dispatch processor | main control processor link=PASS; S_TEST identities: {'H1S1': '// H1S1 DSP', 'H1S4': '// … | the unit | 1 |
| 203 | screen | HDMI-A-1 connected; EDID RTK 10811, native 1920x1080, active=True (informational, not gat… | the unit | 1 |

1 earlier set-aside expired because the check list moved and now count as owed: 1.

## History

Nothing has changed verdict on this unit yet.

