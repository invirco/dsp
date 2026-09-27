# Panel firmware recon — D24 bench unit (192.168.1.219)

READ-ONLY recon. Nothing was built, flashed, or run. All paths below are on
the bench unit, not this repo.

## 1. Indicator-output init (commented-out block) + PB11/PF1 drive

Both `H1S3/Core/Src/main.c` and `H1S4/Core/Src/main.c` `#include "matrix.cs"`
(`H1S3/Core/Src/main.c:23`, `H1S4/Core/Src/main.c:23`), and it is
**`matrix.cs`**, not `main.c`, that actually defines `MainInit()`. (`main.c`'s
own `MX_GPIO_Init()` never touches the wled pins at all — see below.)

### H1S3 — `/home/app/fwbuild/H1S3/Core/Inc/matrix.cs`, `MainInit()` (lines 192–227)

Commented-out LED-output block, lines 202–216:
```
202	                                                           // init LEDs
203		/*
204	    GPIO_InitStruct.Pin = PA7_Pin | PA11_Pin;
205	    GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
206	    HAL_GPIO_Init(GPIOA, &GPIO_InitStruct);
207	    GPIO_InitStruct.Pin = PB0_Pin | PB1_Pin | PB2_Pin | PB3_Pin | PB5_Pin | PB10_Pin | PB11_Pin | PB13_Pin | PB14_Pin | PB15_Pin;
208	    GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
209	    HAL_GPIO_Init(GPIOB, &GPIO_InitStruct);
210	    GPIO_InitStruct.Pin = PC0_Pin | PC2_Pin | PC3_Pin | PC4_Pin | PC5_Pin | PC6_Pin | PC7_Pin | PC8_Pin | PC12_Pin | PC13_Pin | PC15_Pin;
211	    GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
212	    HAL_GPIO_Init(GPIOC, &GPIO_InitStruct);
213	    GPIO_InitStruct.Pin = PF1_Pin;
214	    GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
215	    HAL_GPIO_Init(GPIOF, &GPIO_InitStruct);
216	    */
```

PB11 / PF1 forced high, lines 218–225 (immediately after the commented-out block):
```
218		GPIO_InitStruct.Pin = PB11_Pin;
219		GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
220		HAL_GPIO_Init(GPIOB, &GPIO_InitStruct);
221		HAL_GPIO_WritePin(GPIOB, PB11_Pin, GPIO_PIN_SET); // always on white led next to red led
222		GPIO_InitStruct.Pin = PF1_Pin;
223		GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
224		HAL_GPIO_Init(GPIOF, &GPIO_InitStruct);
225		HAL_GPIO_WritePin(GPIOF, PF1_Pin, GPIO_PIN_SET); // always on white led next to red led
```
Both comments read verbatim `// always on white led next to red led`.

Note: `wled[]` (line 54 and 62, see §2) independently comments out PB10|PB11
and PF1 as *addressable* LED table entries, consistent with those two pins
instead being hard-wired on in `MainInit()`.

### H1S4 — `/home/app/fwbuild/H1S4/Core/Inc/matrix.cs`, `MainInit()` (lines 131–156)

Commented-out LED-output block, lines 141–155 (the whole body of `MainInit()`
in H1S4 is this one comment block — nothing is left active):
```
131	void MainInit()
132	{
133	    // init matrix bus
134	    GPIO_InitStruct.Pin = S2_Pin;
135	    GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
136	    HAL_GPIO_Init(S2_GPIO_Port, &GPIO_InitStruct);
137	    HAL_GPIO_WritePin(S2_GPIO_Port, S2_Pin, GPIO_PIN_SET); // data ready handshake pin
138	    // init uart interrupt busy pin
139	    GPIO_BusyStruct.Pin = BUSY_Pin;
140	
141	    // init LEDs
142	    /*
143	        GPIO_InitStruct.Pin = PA8_Pin | PA12_Pin | PA13_Pin | PA14_Pin;
144	        GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
145	        HAL_GPIO_Init(GPIOA, &GPIO_InitStruct);
146	        GPIO_InitStruct.Pin = PB1_Pin | PB2_Pin | PB11_Pin;
147	        GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
148	        HAL_GPIO_Init(GPIOB, &GPIO_InitStruct);
149	        GPIO_InitStruct.Pin = PC5_Pin | PC7_Pin | PC9_Pin | PC10_Pin;
150	        GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
151	        HAL_GPIO_Init(GPIOC, &GPIO_InitStruct);
152	        GPIO_InitStruct.Pin = PF7_Pin;
153	        GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
154	        HAL_GPIO_Init(GPIOF, &GPIO_InitStruct);
155	    */
156	}
```
H1S4 has **no** PB11/PF1-style "always on" override — `MainInit()` ends at
line 156 with nothing active beyond the S2 handshake pin. There is no H1S4
equivalent of H1S3's "always on white led next to red led" pins.

### `MX_GPIO_Init()` — the STM32CubeMX-generated function in `main.c` (both boards)

This function only ever configures pins as **input with pull-up**, or a
single dedicated output (`S2_Pin`, the TX-ready handshake line to MH1). It
never touches the wled/rsw pins as outputs — that reconfiguration happens
later, per-pin, at runtime inside `WrRadioLed()`/`WrEncLed()` (see §2).

**H1S3** — `main.c:450–521`:
```
457	  /* GPIO Ports Clock Enable */
458	  __HAL_RCC_GPIOC_CLK_ENABLE();
459	  __HAL_RCC_GPIOF_CLK_ENABLE();
460	  __HAL_RCC_GPIOA_CLK_ENABLE();
461	  __HAL_RCC_GPIOB_CLK_ENABLE();
462	  __HAL_RCC_GPIOD_CLK_ENABLE();
463	
464	  /*Configure GPIO pin Output Level */
465	  HAL_GPIO_WritePin(S2_GPIO_Port, S2_Pin, GPIO_PIN_SET);
466	
467	  /*Configure GPIO pins : PC13_Pin PC14_Pin PC15_Pin PC0_Pin
468	                           PC1_Pin PC2_Pin PC3_Pin PC4_Pin
469	                           PC5_Pin PC6_Pin PC7_Pin PC8_Pin
470	                           PC10_Pin PC11_Pin PC12_Pin */
471	  GPIO_InitStruct.Pin = PC13_Pin|PC14_Pin|PC15_Pin|PC0_Pin
472	                          |PC1_Pin|PC2_Pin|PC3_Pin|PC4_Pin
473	                          |PC5_Pin|PC6_Pin|PC7_Pin|PC8_Pin
474	                          |PC10_Pin|PC11_Pin|PC12_Pin;
475	  GPIO_InitStruct.Mode = GPIO_MODE_INPUT;
476	  GPIO_InitStruct.Pull = GPIO_PULLUP;
477	  HAL_GPIO_Init(GPIOC, &GPIO_InitStruct);
478	
479	  /*Configure GPIO pins : PF0_Pin PF1_Pin PF4_Pin PF5_Pin
480	                           PF6_Pin PF7_Pin */
481	  GPIO_InitStruct.Pin = PF0_Pin|PF1_Pin|PF4_Pin|PF5_Pin
482	                          |PF6_Pin|PF7_Pin;
483	  GPIO_InitStruct.Mode = GPIO_MODE_INPUT;
484	  GPIO_InitStruct.Pull = GPIO_PULLUP;
485	  HAL_GPIO_Init(GPIOF, &GPIO_InitStruct);
486	
487	  /*Configure GPIO pins : PA0_Pin PA3_Pin PA4_Pin PA5_Pin
488	                           PA6_Pin PA7_Pin PA11_Pin PA12_Pin
489	                           PA13_Pin PA14_Pin PA15_Pin */
490	  GPIO_InitStruct.Pin = PA0_Pin|PA3_Pin|PA4_Pin|PA5_Pin
491	                          |PA6_Pin|PA7_Pin|PA11_Pin|PA12_Pin
492	                          |PA13_Pin|PA14_Pin|PA15_Pin;
493	  GPIO_InitStruct.Mode = GPIO_MODE_INPUT;
494	  GPIO_InitStruct.Pull = GPIO_PULLUP;
495	  HAL_GPIO_Init(GPIOA, &GPIO_InitStruct);
496	
497	  /*Configure GPIO pins : PB0_Pin PB1_Pin PB2_Pin PB10_Pin
498	                           PB11_Pin PB12_Pin PB13_Pin PB14_Pin
499	                           PB15_Pin PB3_Pin PB4_Pin PB5_Pin
500	                           PB6_Pin BUSY_Pin S3_Pin */
501	  GPIO_InitStruct.Pin = PB0_Pin|PB1_Pin|PB2_Pin|PB10_Pin
502	                          |PB11_Pin|PB12_Pin|PB13_Pin|PB14_Pin
503	                          |PB15_Pin|PB3_Pin|PB4_Pin|PB5_Pin
504	                          |PB6_Pin|BUSY_Pin|S3_Pin;
505	  GPIO_InitStruct.Mode = GPIO_MODE_INPUT;
506	  GPIO_InitStruct.Pull = GPIO_PULLUP;
507	  HAL_GPIO_Init(GPIOB, &GPIO_InitStruct);
508	
509	  /*Configure GPIO pin : PD2_Pin */
510	  GPIO_InitStruct.Pin = PD2_Pin;
511	  GPIO_InitStruct.Mode = GPIO_MODE_INPUT;
512	  GPIO_InitStruct.Pull = GPIO_PULLUP;
513	  HAL_GPIO_Init(PD2_GPIO_Port, &GPIO_InitStruct);
514	
515	  /*Configure GPIO pin : S2_Pin */
516	  GPIO_InitStruct.Pin = S2_Pin;
517	  GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
518	  GPIO_InitStruct.Pull = GPIO_NOPULL;
519	  GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;
520	  HAL_GPIO_Init(S2_GPIO_Port, &GPIO_InitStruct);
```
Note this input+pull-up sweep for GPIOB **includes PB11** and for GPIOF
**includes PF1** — i.e. `MX_GPIO_Init()` first configures PB11/PF1 as
pulled-up inputs, and `MainInit()` (in `matrix.cs`, called right after) then
re-inits those two specific pins as push-pull outputs and drives them high.

**H1S4** — `main.c:236–311` is byte-for-byte the same pattern (same port
sweeps, same pin sets: GPIOC 13/14/15/0-8/9-12, GPIOF 0/1/4/5/6/7, GPIOA
0/1/4-8/11-15, GPIOB 0-6/10-15/BUSY/S3, PD2, and `S2_Pin` as the sole
output). Pin lists differ only in a couple of board-specific pins (H1S4 adds
PC9, PA1, PA8; drops PC11/PA12/PA13 from the input sweep since those become
outputs). Same conclusion: everything is input+pull-up except `S2_Pin`.

## 2. `WrRadioLed` / `RdRadioSwitch` and the `wled[]` / `rsw[]` tables

Both functions live in `matrix.cs` (not a header), immediately after
`MainInit()`/`MainLoop()`.

### H1S3 — `/home/app/fwbuild/H1S3/Core/Inc/matrix.cs`

`RdRadioSwitch()`, lines 269–276:
```
269	void RdRadioSwitch(struct rSw s)
270	{
271	    if (!HAL_GPIO_ReadPin(s.port, s.pin) && matrix[s.matrixAdd][TXD] != s.radioData)
272	    {
273	        ledFollowSw = 1; matrix[s.matrixAdd][TXD] = s.radioData;
274	        if (matrix[s.matrixAdd][TXF] < 2) matrix[s.matrixAdd][TXF]++;
275	    }
276	}
```
`WrRadioLed()`, lines 325–344:
```
325	void WrRadioLed(struct wLed s)
326	{
327	    if (matrix[s.matrixAdd][RXD] == s.radioData) 
328	    {
329	        //HAL_GPIO_WritePin(s.port, s.pin, GPIO_PIN_SET);
330	        // convert to output for bright led
331	        GPIO_InitStruct.Pin = s.pin;
332	        GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
333	        HAL_GPIO_Init(s.port, &GPIO_InitStruct);
334	        HAL_GPIO_WritePin(s.port, s.pin, GPIO_PIN_SET);
335	    }
336	    else
337	    {
338	        //HAL_GPIO_WritePin(s.port, s.pin, GPIO_PIN_RESET);
339	        // convert to input for dim led
340	        GPIO_InitStruct.Pin = s.pin;
341	        GPIO_InitStruct.Mode = GPIO_MODE_INPUT;
342	        HAL_GPIO_Init(s.port, &GPIO_InitStruct);
343	    }
344	}
```
So an LED is never merely driven low/high — the pin itself is switched
between `OUTPUT_PP` (driven, "bright") and floating `INPUT` (undriven, "dim",
i.e. relies on whatever pull/leakage the LED circuit gives it) every poll
cycle. There's no explicit "off" drive.

`rsw[]`, lines 29–45 (radio switch: port, pin, matrix cell pointer,
radioData code):
```
29	struct rSw rsw[] = // radio switch properties
30	{
31	    { GPIOF, PF5_Pin, pSys001Skin001, 1 },
32	    { GPIOA, PA4_Pin, pSys001Skin001, 2 },
33	    { GPIOF, PF4_Pin, pSys001Skin001, 3 },
34	    { GPIOA, PA5_Pin, pSys001Skin001, 4 },
35	    { GPIOA, PA3_Pin, pSys001Skin001, 5 },
36	    { GPIOA, PA6_Pin, pSys001Skin001, 6 },
37	    { GPIOB, PB6_Pin, pSys001Skin001, 7 },
38	    { GPIOB, PB12_Pin, pSys001Skin001, 8 },
39	    { GPIOB, PB4_Pin, pSys001Skin001, 9 },
40	    { GPIOD, PD2_Pin, pSys001Skin001, 10 },
41	    { GPIOC, PC11_Pin, pSys001Skin001, 11 },
42	    { GPIOC, PC1_Pin, pSys001Skin001, 12 },
43	    { GPIOF, PF0_Pin, pSys001Skin001, 13 },
44	    { GPIOC, PC14_Pin, pSys001Skin001, 14 },
45	};
```
`wled[]`, lines 47–65 (radio LED: port, pin, matrix cell pointer,
radioData code — two entries commented out):
```
47	struct wLed wled[] = // radio led properties
48	{
49	    { GPIOB, PB0_Pin, pSys001Skin001, 1 },
50	    { GPIOB, PB1_Pin, pSys001Skin001, 2 },
51	    { GPIOC, PC5_Pin, pSys001Skin001, 3 },
52	    { GPIOB, PB2_Pin, pSys001Skin001, 4 },
53	    { GPIOC, PC4_Pin, pSys001Skin001, 5 },
54	    //{ GPIOB, PB10_Pin | PB11_Pin, pSys001Test002, 6 },
55	    { GPIOB, PB10_Pin, pSys001Skin001, 6 },
56		{ GPIOA, PA7_Pin, pSys001Skin001, 7 },
57	    { GPIOB, PB13_Pin, pSys001Skin001, 8 },
58	    { GPIOB, PB5_Pin, pSys001Skin001, 9 },
59	    { GPIOB, PB3_Pin, pSys001Skin001, 10 },
60	    { GPIOC, PC12_Pin, pSys001Skin001, 11 },
61	    { GPIOC, PC0_Pin, pSys001Skin001, 12 },
62	    //{ GPIOF, PF1_Pin, pSys001Test002, 13 },
63	    { GPIOC, PC15_Pin, pSys001Skin001, 13 },
64	    { GPIOC, PC13_Pin, pSys001Skin001, 14 },
65	};
```
(There is also a third table, `weled[]`/`WrEncLed()`, lines 66–77 and
286–307, for the encoder LEDs — same pattern, keyed on `pSys001Enc001`.)

### H1S4 — `/home/app/fwbuild/H1S4/Core/Inc/matrix.cs`

`RdRadioSwitch()` (lines 206–213) and `WrRadioLed()` (lines 230–249) are
textually identical to H1S3's versions above (same body).

`rsw[]`, lines 29–37:
```
29	struct rSw rsw[] = // radio switch properties
30	{
31	    { GPIOC, PC8_Pin, pSys001Skin001, 1 },
32	    { GPIOA, PA11_Pin, pSys001Skin001, 2 },
33	    { GPIOF, PF6_Pin, pSys001Skin001, 3 },
34	    { GPIOA, PA15_Pin, pSys001Skin001, 4 },
35	    { GPIOB, PB0_Pin, pSys001Skin001, 5 },
36	    { GPIOB, PB10_Pin, pSys001Skin001, 6 },
37	};
```
`wled[]`, lines 39–50 (note: two entries use OR'd pin pairs, and radioData
value 3 and 4 each appear twice on different physical pins/ports — both
members of the OR'd/duplicated pair light together for that switch position):
```
39	struct wLed wled[] = // radio led properties
40	{
41	    { GPIOC, PC7_Pin | PC9_Pin, pSys001Skin001, 1 },
42	    { GPIOA, PA8_Pin | PA12_Pin, pSys001Skin001, 2 },
43	    { GPIOA, PA13_Pin, pSys001Skin001, 3 },
44	    { GPIOF, PF7_Pin, pSys001Skin001, 3 },
45	    { GPIOA, PA14_Pin, pSys001Skin001, 4 },
46	    { GPIOC, PC10_Pin, pSys001Skin001, 4 },
47	    { GPIOB, PB1_Pin, pSys001Skin001, 5 },
48	    { GPIOC, PC5_Pin, pSys001Skin001, 5 },
49	    { GPIOB, PB2_Pin | PB11_Pin, pSys001Skin001, 6 },
50	};
```
H1S4 has no `weled[]`/encoder-LED table and no `WrEncLed()` — it has no
rotary encoder (matches the "// H1S4 SW Left" identity; H1S3 "SW Right" is
the board with the encoder).

## 3. The `MATRIX[]` address table and cell-address decode

### H1S3 — `/home/app/fwbuild/H1S3/Core/Inc/matrix.cs:11–27`
```
11	const unsigned int MATRIX[] = // local matrix cells
12	{
13	   0x0, // reserved and unused
14	   Sys001Enc001,
15	   Sys001Skin001,
16	   Sys001Test001,
17	   Sys001Test002,
18	};
19	enum // MATRIX cell pointers
20	{
21	   p0, // reserved and unused
22	   pSys001Enc001,
23	   pSys001Skin001,
24	   pSys001Test001,
25	   pSys001Test002,
26	   MATRIX_X,
27	};
```
The symbols resolve (`/home/app/fwbuild/H1S3/Core/Inc/matrix.h:5163,5342-5344`)
to:
```
5163:#define Sys001Enc001 5232
5342:#define Sys001Skin001 5412
5343:#define Sys001Test001 5414
5344:#define Sys001Test002 5415
```
so at runtime `MATRIX[] == { 0, 5232, 5412, 5414, 5415 }` — exactly the array
reported. `MATRIX_X` (= 5, from the parallel enum) sizes the parallel
`matrix[MATRIX_X][MATRIX_Y]` data/flag array; the enum values `pSys001Enc001`
etc. (1..4) are the array *indices* used everywhere else (`rsw[]`, `wled[]`,
`weled[]` `matrixAdd` fields, and `Eol()`).

Address decode, `Eol()`, lines 364–390 (RX path, fires on LF, i.e. end of a
bus message):
```
370	    if ((!s_help) && (!ignor)) 
371	    { 
372	        for (int i = 1; i < MATRIX_X; i++) // find local matrix address
373	        {
374	            if (a == MATRIX[i]) // local matrix address found
375	            {
376	                matrix[i][RXD] = d; // write local matrix data
377	                if (matrix[i][RXF] < 2) matrix[i][RXF]++;
378	                break;
379	            }
380	        }
381	    }
382	    d = 0;                  // reset local data value
```
`a` (the address accumulated by `A_00..A_0F`, hex digits) is linear-searched
against `MATRIX[1..MATRIX_X-1]` (index 0, the `0x0` placeholder, is
deliberately skipped). **If the incoming address matches nothing in
`MATRIX[]`, the `if` body is simply never entered — `d` and `a` are still
reset and the bus handshake (`S2_GPIO_Port`/`S2_Pin` set high at line 386)
still completes as normal.** There is no error, no flag, no distinct
"unknown address" branch — an address for a cell this board doesn't own is
silently dropped on the floor. (Contrast with this repo's own no-fallback
policy for unknown matrix-cell families — this panel firmware has no such
guard at all.)

### H1S4 — `/home/app/fwbuild/H1S4/Core/Inc/matrix.cs:11–27` and `Eol()` (lines 275–301)

Textually identical `MATRIX[]`/enum block and identical `Eol()` loop
(`for (int i = 1; i < MATRIX_X; i++) if (a == MATRIX[i]) ...`), same
silent-drop-on-no-match behavior. H1S4's `matrix.h` (also 5415 lines) defines
the same `Sys001Enc001/Sys001Skin001/Sys001Test001/Sys001Test002` constants
at the same values, so H1S4's runtime `MATRIX[]` is also
`{0, 5232, 5412, 5414, 5415}` — H1S4 just never populates `rsw[]`/`wled[]`
entries against `pSys001Enc001` (no encoder hardware), even though the
address is technically in its `MATRIX[]`.

### MH1 — `/home/app/fwbuild/MH1/Core/Src/main.c`

**MH1 has no `MATRIX[]` array, no `matrixAdd` field, and no `Eol()`-style
address comparison anywhere in its source.** (`grep -n "MATRIX\|matrixAdd\|radioData"` across
`MH1/Core/Src/main.c` and `MH1/Core/Inc/*.h` turns up only one hit,
`MH1/Core/Inc/Project.h:285: #define MATRIX_SIZE 47`, an unrelated legacy
byte-count constant used only by MH1's own matrix-fill-forward loop, not a
cell-address table.)

MH1's per-slave polling loop, `CheckS()` (`MH1/Core/Src/main.c:747–841`,
excerpted — pattern repeats per slave slot, this is the H1S3/H1S4 slot):
```
751	    if (!HAL_GPIO_ReadPin(S2_GPIO_Port, S2_Pin)) {
752		WaitForNotBusy();
753		HAL_GPIO_WritePin(GPIOF, S3_Pin, GPIO_PIN_SET);
754		while (!HAL_GPIO_ReadPin(S2_GPIO_Port, S2_Pin)) {
755	    } // wait for S to finish sending data
756		HAL_GPIO_WritePin(GPIOF, S3_Pin, GPIO_PIN_RESET);
757		WaitForNotBusy();
758	    }
```
and the byte forwarder, lines 922–954:
```
922	void TxSmessage(void) { // send S message to Host
923		myChar = 0;
924		int i = 0;
925		while (myChar != 0x0a) {
926			myChar = sMessage[i];
927			i++;
928			UART1_Write(myChar);
929		}
930		sMessageReady = 0;
931	}
...
944	void TxHostMessage(void) {
945		myChar = 0;
946		int i = 0;
947		if (hostMessage[0] == S_FILL_START)
948			matrixFill = 1; // check for matrixFill message
949		else {
950			while (myChar != 0x0a) { // send Host message to S
951				myChar = hostMessage[i];
952				i++;
953				TxS(myChar);
954			}
955		}
956		hostMessageReady = 0;
957	}
952	void TxS(char myChar) {
953		UART2_Write(myChar); // send char to bus
954		while (!UART2_Tx_Idle()) {
955		}
956	}
```
`CheckS()` only watches each slave's `S2`-style data-ready pin and strobes an
`S3`-style request line; `TxSmessage()`/`TxS()`/`TxHostMessage()` copy the
message **byte-for-byte until the `0x0a` terminator**, with no inspection of
address (`h`..`w`) or data (`0`-`F`) characters — it is a transparent relay,
identical in structure for every one of MH1's ~9 slave slots.

**Answer to the key question:** a new matrix cell address for the left panel
only needs `MATRIX[]`/`rsw[]`/`wled[]` (and whatever symbol table backs
`matrix.h`'s `#define`s) changed in **H1S4**. MH1 never parses a cell
address or cell value — it is a dumb byte pipe between UART1 (host) and
UART2 (each slave's bus) — so it requires no change for a new cell address,
as long as the address still fits the existing 4-hex-nibble / `A_00..A_0F`+
`D_00..D_0F` encoding and the message still terminates on LF. MH1 would only
need to change if the *slot topology* changed (a new physical slave board
added/moved) — that is a `CheckS()`/`StartAllSlaves()` pin-list change, a
completely different axis from adding a cell address on an existing slave.

## 4. Build recipe

### Directory contents

**H1S3/Release** (top level):
```
H1S3.elf   H1S3.list   H1S3.map
H1S4.elf   H1S4.list   H1S4.map   <- stale cross-board leftovers, see below
makefile   objects.list  objects.mk   sources.mk
Core/  Drivers/   (subdir.mk + .o/.d/.su/.cyclo per source)
```
**H1S4/Release** (top level):
```
H1S4.elf   H1S4.list   H1S4.map
makefile   objects.list  objects.mk   sources.mk
Core/  Drivers/
```
Note H1S3's `Release/` directory contains a *second* set of H1S4 build
outputs (`H1S4.elf`/`.list`/`.map`), left over from what looks like a
copy/build mistake — its `H1S4.elf` (5060 B text) does not match the real
`H1S4/Release/H1S4.elf` (7964 B text): different size, different md5. This
stray file should not be treated as authoritative for H1S4.

`H1S3/Release/objects.mk`:
```
USER_OBJS :=
LIBS :=
```
`H1S3/Release/sources.mk` (subdirs only, generated, no edits):
```
SUBDIRS := \
Core/Src \
Core/Startup \
Drivers/STM32F0xx_HAL_Driver/Src \
```
(H1S4's `objects.mk`/`sources.mk` are the same shape, not reproduced.)

### Rebuild invocation

Both makefiles are STM32CubeIDE-generated ("Automatically-generated file. Do
not edit!", header records `Toolchain: GNU Tools for STM32 (13.3.rel1)`).
The rebuild command, run from each `Release/` directory, would be:
```
make -C /home/app/fwbuild/H1S3/Release all
make -C /home/app/fwbuild/H1S4/Release all
```
which resolves to (from `H1S3/Release/makefile`):
```
H1S3.elf H1S3.map: $(OBJS) $(USER_OBJS) C:\dropbox\_mx\MW\D24\FW\H1S3\STM32F030R8TX_FLASH.ld makefile objects.list $(OPTIONAL_TOOL_DEPS)
	arm-none-eabi-gcc -o "H1S3.elf" @"objects.list" $(USER_OBJS) $(LIBS) -mcpu=cortex-m0 -T"C:\dropbox\_mx\MW\D24\FW\H1S3\STM32F030R8TX_FLASH.ld" --specs=nosys.specs -Wl,-Map="H1S3.map" -Wl,--gc-sections -static --specs=nano.specs -mfloat-abi=soft -mthumb -Wl,--start-group -lc -lm -Wl,--end-group
```
Note the linker-script path baked into the makefile is a **Windows path**
(`C:\dropbox\_mx\MW\D24\FW\H1S3\STM32F030R8TX_FLASH.ld`) — this makefile was
generated on a Windows STM32CubeIDE install and was not regenerated for this
Linux bench box, so `make -C Release all` would almost certainly fail here
even if it were run (not run — read-only recon only).

I did **not** run `make`.

### Toolchain on the bench box
```
$ arm-none-eabi-gcc --version
arm-none-eabi-gcc (15:14.2.rel1-1) 14.2.1 20241119
```
This is a **different** toolchain build (Debian's 14.2.1) than the one that
produced the checked-in `Release/` outputs (STM32CubeIDE's bundled
"13.3.rel1" per the makefile header) — a rebuild here would not reproduce
the existing `.elf` bit-for-bit even if the Windows-path linker script
problem were solved.

### Staleness: source vs. Release build

For **both** boards, `Core/Inc/matrix.h` and `Core/Inc/matrix.cs` carry an
mtime of **2026-08-19**, which postdates the existing `Release/*.elf`:

| file | mtime |
|---|---|
| H1S3/Core/Inc/matrix.h | 2026-08-19 15:55:38 |
| H1S3/Core/Inc/matrix.cs | 2026-08-19 12:35:31 |
| H1S3/Core/Src/stm32f0xx_it.c | 2025-12-30 16:11:11 |
| H1S3/Core/Src/main.c | 2025-06-19 18:04:22 |
| **H1S3/Release/H1S3.elf** | **2025-12-30 16:05:26** |
| H1S4/Core/Inc/matrix.h | 2026-08-19 15:55:38 |
| H1S4/Core/Inc/matrix.cs | 2026-08-19 12:35:31 |
| H1S4/Core/Src/stm32f0xx_it.c | 2025-12-30 16:11:11 |
| H1S4/Core/Src/main.c | 2025-06-19 19:11:20 |
| **H1S4/Release/H1S4.elf** | **2025-12-29 19:42:15** |

For both boards the current `matrix.h`/`matrix.cs` (which carry the
2026-08-19 "rev C bring-up fix" comment quoted in `matrix.cs:432–438`, about
the `Uart1_Int()` ORE/blocking-read wedge fix) is **newer than the checked-in
`.elf`** — the Release build on disk predates that source, i.e. it does not
contain the rev-C fix. In addition, for H1S3, `Core/Src/stm32f0xx_it.c`
(2025-12-30 16:11:11) is newer than `Release/H1S3.elf` (2025-12-30 16:05:26,
6 minutes earlier); for H1S4, `stm32f0xx_it.c`'s mtime (2025-12-30 16:11:11)
is nearly a full day newer than `Release/H1S4.elf` (2025-12-29 19:42:15).
Also, `H1S4/Release/Core/Src/main.o` (2025-12-30 16:06:14) is newer than
`H1S4/Release/H1S4.elf` (2025-12-29 19:42:15) — an object file was rebuilt
without the elf being relinked. **By every mtime comparison available, the
checked-in `Release/*.elf` on this bench box is stale relative to its own
sources.**

### md5 / size

```
$ md5sum H1S3/Release/H1S3.elf H1S4/Release/H1S4.elf H1S3/Release/H1S4.elf
10468828a533ee84bb36b9b1575ce1b0  H1S3/Release/H1S3.elf
22d561fafd4ba9c04d3b9233f506c89b  H1S4/Release/H1S4.elf
4fdeb5c32911c793abe0acb9db3233fd  H1S3/Release/H1S4.elf   (stray/stale, see above)

$ arm-none-eabi-size H1S3/Release/H1S3.elf H1S4/Release/H1S4.elf H1S3/Release/H1S4.elf
   text	   data	    bss	    dec	    hex	filename
  11512	   1208	   2064	  14784	   39c0	H1S3/Release/H1S3.elf
   7964	    872	   1920	  10756	   2a04	H1S4/Release/H1S4.elf
   5060	     12	   1844	   6916	   1b04	H1S3/Release/H1S4.elf
```

## 5. The packing tool — `hex2shex.py`

`/home/app/fwbuild/hex2shex.py`, full listing (45 lines):
```python
#!/usr/bin/env python3
# Convert an Intel hex to the Matrix "shex" flash-stream format:
#  - record 1: :02<MCUID>04<ext-addr>CS   (extended-address record, MCU id in place of the 0000 field)
#  - data:     16-byte aligned records, checksum replaced by literal "CS"
#  - EOF:      :00000001CS      (type-05 start-address records dropped)
import sys

def parse_hex(path):
    mem = {}
    ext = 0
    for line in open(path):
        line = line.strip()
        if not line.startswith(":"):
            continue
        n = int(line[1:3], 16)
        addr = int(line[3:7], 16)
        typ = int(line[7:9], 16)
        data = bytes.fromhex(line[9:9 + n * 2])
        if typ == 4:
            ext = int(line[9:13], 16) << 16
        elif typ == 0:
            for i, b in enumerate(data):
                mem[ext + addr + i] = b
    return mem

def emit_shex(mem, mcuid, out):
    base = min(mem) & 0xFFFF0000
    lines = [":02%s04%04XCS" % (mcuid, base >> 16)]
    lo = min(mem) & ~0xF
    hi = max(mem)
    a = lo
    while a <= hi:
        chunk = bytes(mem.get(a + i, 0xFF) for i in range(16))
        if any((a + i) in mem for i in range(16)):
            lines.append(":10%04X00%sCS" % ((a - base) & 0xFFFF, chunk.hex().upper()))
        a += 16
    lines.append(":00000001CS")
    open(out, "w", newline="\n").write("\n".join(lines) + "\n")
    return len(lines)

if __name__ == "__main__":
    hexfile, mcuid, out = sys.argv[1:4]
    mem = parse_hex(hexfile)
    n = emit_shex(mem, mcuid, out)
    print("%s -> %s: %d records, %d bytes image" % (hexfile, out, n, len(mem)))
```
Usage: `hex2shex.py <input.hex> <MCUID> <output.shex>` — three positional
args, no flags. `mcuid` is an arbitrary string (in practice `"H1S3"`/`"H1S4"`)
substituted literally into the first output line's `:02<MCUID>04<ext>CS`
extended-address record — **this is the only place the destination slave
slot/identity is encoded**; the actual data records (`:10<addr>00<16
bytes>CS`) carry no slot information, only a flash offset relative to
`base`. Checksums are not computed — the literal string `CS` is written in
place of a real Intel-hex checksum byte, so the consuming loader (not this
script) must special-case that sentinel rather than checksum-validate.
Because the MCU id lives only in that one header line, swapping it (as seen
in §5 below) silently repoints an otherwise-correct image at the wrong slot
with no structural error.

### md5 / size of the six shex files

```
a0db4f65ed61a99f76c8f6ebd00df893  /home/app/firmware/H1S3.shex                           59956 bytes
1222e007920015d4cdd8ec9426a288d3  /home/app/firmware/H1S4.shex                           40596 bytes
ee72e0148cee75842039196e2f98850d  /home/app/fwbuild/right-slot4-H1S3content.shex         59956 bytes
8b3d2dd45c8acdda3a3ac49c42900869  /home/app/fwbuild/left-slot3-H1S4content.shex          40596 bytes
be2d0a796ab8e573c44b99b41fc96706  /home/app/fwbuild/H1S3.new.shex                        59956 bytes
8ce8be3726528b21486cb8b2fe9b3849  /home/app/fwbuild/H1S4.new.shex                        40596 bytes
```
No two of the six files are fully byte-identical (all six md5s differ). But
diffing shows two near-identical pairs and one important discrepancy:

**Header (MCUID) field, line 1 of each file:**
```
/home/app/firmware/H1S3.shex                     :02H1S4040800CS   <- says H1S4, wrong
/home/app/firmware/H1S4.shex                     :02H1S3040800CS   <- says H1S3, wrong
/home/app/fwbuild/right-slot4-H1S3content.shex   :02H1S4040800CS   <- says H1S4, wrong
/home/app/fwbuild/left-slot3-H1S4content.shex    :02H1S3040800CS   <- says H1S3, wrong
/home/app/fwbuild/H1S3.new.shex                  :02H1S3040800CS   <- correct
/home/app/fwbuild/H1S4.new.shex                  :02H1S4040800CS   <- correct
```
The two currently-deployed images in `/home/app/firmware/` — `H1S3.shex` and
`H1S4.shex` — **carry each other's MCUID header** (H1S3.shex says H1S4,
H1S4.shex says H1S3), and `right-slot4-H1S3content.shex` /
`left-slot3-H1S4content.shex` inherit that same swap. Only `H1S3.new.shex`
and `H1S4.new.shex` have the header matching their own filename/board.

**Data payload:** `right-slot4-H1S3content.shex` and `H1S3.new.shex` are
byte-identical **except for that header line** (confirmed with `diff`, 1
line changed out of 1280+). Likewise `left-slot3-H1S4content.shex` and
`H1S4.new.shex` are identical except the header line. So:
- `right-slot4-H1S3content.shex` ≈ `H1S3.new.shex` (content-identical,
  header differs)
- `left-slot3-H1S4content.shex` ≈ `H1S4.new.shex` (content-identical,
  header differs)

But the **deployed** `/home/app/firmware/H1S3.shex` and
`/home/app/firmware/H1S4.shex` are *not* content-identical to the `.new`
files — they differ at one internal data record each (`H1S3.shex` line 1281,
`H1S4.shex` line 862) where a small function-pointer/jump table (consistent
with the `Rx_Fun[]` table in `matrix.cs`) holds different target addresses:
deployed = `...0000000070140000` / `24150000261500002715...`
(word-decoded ≈ `0x1470`, `0x1524`, `0x1526`, `0x1527`), `.new`/`right-slot4`/
`left-slot3` = `...00000000234B0000` / `1B4C00001D4C00001E4C...` (≈ `0x4B02`,
`0x4C1B`, `0x4C1D`, `0x4C1E`). This is consistent with the deployed images
predating a code-layout change (matches the source staleness in §4 — the
2026-08-19 matrix.cs/matrix.h edits post-date the Release elfs). I'm
reporting the byte facts; I did not attempt to prove which specific source
edit produced that particular address shift.

**Net picture:** the shex files in `/home/app/firmware/` that the unit would
actually load are (a) older than the current source and the `.new`/`slot*`
files, and (b) have their two boards' MCUID headers swapped relative to
their own filenames.

## 6. Version / identity strings

**H1S3** — `/home/app/fwbuild/H1S3/Core/Inc/matrix.cs:93`:
```
93	char testMessage[100] = "// H1S3 SW Right\n";       // test message
```
**H1S4** — `/home/app/fwbuild/H1S4/Core/Inc/matrix.cs:66`:
```
66	char testMessage[100] = "// H1S4 SW Left\n";        // test message
```
Both are sent verbatim over UART1 by `TestMessage()` (H1S3 `matrix.cs:358-362`,
H1S4 `matrix.cs:269-273`) whenever `test` is true (default at boot: `test = 1`,
H1S3 line 92 / H1S4 line 65), i.e. this is the board's self-identification
string on first host poll after reset.

No separate build-stamp constant (`VERSION`/`BUILD_*`/`__DATE__`/`__TIME__`/
`FW_REV`) exists anywhere in either board's `main.c`, `matrix.cs`, or
`matrix.h` — grepping all three files for those patterns on both boards
returns nothing. The only in-line dating is the prose comment at
`matrix.cs:433` ("2026-08-19 rev C bring-up fix ...", quoted in full in §3's
neighborhood / §4) — a code comment, not a runtime-readable constant.

## 7. Version control

`ls -a /home/app/fwbuild/H1S3` and `ls -a /home/app/fwbuild/H1S4`: no `.git`
in either (only STM32CubeIDE's `.cproject`, `.mxproject`, `.project`, plus
`Core/`, `Debug/`, `Release/`, `Drivers/`, the `.ioc`, and the linker script).

`git` is **not installed** on this bench box (`which git` and
`git -C /home/app/fwbuild status` both fail — "command not found"). No `.git`
directory exists anywhere under `/home/app/fwbuild` (checked all the way up
to the top of that tree). **The panel firmware source on this bench unit is
not under version control at all** — `/home/app/fwbuild/` is a flat working
directory of per-board STM32CubeIDE project trees plus a pile of loose
`.hex`/`.shex` snapshots (`H1S1-s69.shex`, `H1S1-s81.shex`,
`H1S1-pre-s109-2026-09-25.shex`, `pack-backup-H1S3.shex`, etc.) that appear
to be hand-named manual backups rather than any kind of managed history.
