provenance: AI-drafted 2026-09-16 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# Contract proposal S56 — `CaptureArm` / `CaptureReady` in the `Test[1-1]*` family, +2 cells per product

**Status: PROPOSED, not landed.** The addresses below are proposed, not typed:
no def, master or `_matrix.csv` row is written by this repo. The DSP side
already dispatches the two words without cells, the same way the window
serial (`0x136E`) has been dispatched since S49, so the bench can use them
before the contract does. Evidence: `findings.md` S56-1.

## 1. What is asked for

Two cells in the `Test` family, next to the thirteen S49 landed
(`defs-v2026.09.16`):

| proposed cell | access | range / law | chip | SPI addr | hex | dispatch symbol |
|---|---|---|---|---|---|---|
| `Test[1-1]CaptureArm[1-1]` | rw | samples wanted, 0 = idle; clamped to 16384 by the DSP; the DSP writes it back to 0 when the run completes | 1 | 4981 | `0x1375` | `_meas_cap_arm_C1_TEST_MEAS` |
| `Test[1-1]CaptureReady[1-1]` | ro | samples captured, 0 = none / run in progress | 1 | 4982 | `0x1376` | `_meas_cap_ready_C1_TEST_MEAS` |

Suggested master rows, in the shape of the S49 rows (description text is the
hub's call):

```
Test[1-1]CaptureArm[1-1],1,,,true,false,Capture MeasChan post-fader samples (count),,,255,...,-
Test[1-1]CaptureReady[1-1],1,,,true,false,Read-back: samples captured,,,255,...,-
```

## 2. Why these addresses

They are the two **reserved** words at the end of `C1_TEST_OSC`'s eight-word
block (`0x1375`, `0x1376`). They were already inside chip 1's dispatch table
(4,984 entries) and nothing mapped them. Using them:

- moves **no** existing address on any chip or product;
- does not grow the dispatch table;
- keeps the whole Test family in one contiguous range, `4967..4982`.

The cost is that two TEST_MEAS words sit inside TEST_OSC's block. The block
is a generator bookkeeping unit and the host never sees it, so this was
judged better than moving TEST_OSC or growing the table. If the hub wants
them inside TEST_MEAS's own block, the alternative is growing chip 1's table
by two (`4983`, `4984`), which also moves nothing.

## 3. Semantics (what the DSP does)

The tap runs on the MeasChan strip only, after `C1_FDR_nn`, the same pool
slot TEST_MEAS's RMS/THD+N fit reads on that pass:

1. Host writes `CaptureReady = 0`, then `CaptureArm = N`.
2. At the next block boundary the tap sets `CaptureReady = 0` and starts
   copying whole 16-sample blocks, contiguous, into
   `_meas_cap_buf_C1_TEST_MEAS` (L2, 16384 words, Q4.28, 1.0 = converter FS).
3. When `N` samples (rounded up to a whole block) or the buffer are full,
   it writes the count to `CaptureReady` and 0 to `CaptureArm`.
4. The host reads the buffer by diag peek. `tools/pi/dsp4_meascap.py`
   does this; `dsp4_fft.py --capture N` analyses it directly.

Chip 2 does nothing. The buffer is not a contract object: it is read by
symbol, like every other bench peek, and has no cell.

## 4. Cost (measured, S56-1)

- Code: 29 instructions in `_test_meas_tap`, `DSP4_TEST_NODES=1` builds only.
- Data: 3 words in L1 DM (arm, ready, run index), 16,384 words in L2.
- Cycles: idle, 3 instructions per block on the MeasChan strip (not
  resolvable on the part). Copying, **+72 cycles median per block pass**
  (1,398 armed vs 4,545 idle exact TCOUNT samples, interleaved), 0.02 % of
  the 327,680-cycle budget.
- Overruns: +0 on both chips over 30 s of 84 back-to-back 16k captures.
- Shipping (`DSP4_TEST_NODES=0`): the two `.var` words and the two dispatch
  entries only; chip 1 `.ldr` size unchanged at 451,892 B.
