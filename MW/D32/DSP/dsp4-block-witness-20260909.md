provenance: AI-drafted 2026-09-09 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# Block kernels are not an audio defect — the witness and the stimulus were

famverify's audio arm read **17 of 20 families LIVE** on a block-8
per-sample build and **9 of 20** with block kernels, block 8 or block 16
alike. That gap was the whole reason the shipping pair was not yet proven
to pass audio correctly (S9-5). It is now settled, and the verdict is
unambiguous:

> **BLOCK KERNELS ARE NOT AN AUDIO DEFECT.** With a witness that reads
> where a block kernel actually leaves its output, and a stimulus that is
> written where a block kernel actually reads it, the shipping
> configuration — block 16, block kernels, 983.04 MHz — reads **17 of 20
> LIVE, and agrees with the per-sample control on all twenty families,
> verdict for verdict.** The contract arm is identical on every family and
> the numeric arm is BIT_EXACT on COMPRESSOR, FADER_PAN and TUBE_SAT.

Two independent defects, both in the bench instrument, both on chip 1
only, and both invisible to every other bar because nothing else reads a
node buffer.

## 1. Defect one: the witness read a variable the kernel never writes

Under `DSP4_BLOCK_KERNELS` a chip-1 strip node does **not** publish its
output to `_buf_<node>`. It writes a **shared pool slot** (`blk_pool.h`:
eight `BLOCK`-word slots reused by all 32 strips, which is what keeps DM
from overflowing), and `_buf_<node>` survives as a **one-word `.var` that
nothing writes at all**:

```
    .global _buf_C1_EQ_01;
    .var _buf_C1_EQ_01;          /* one word — the block kernel writes BLK_CHAIN_B */
```

`_scope_record` — which the family walk points at `_buf_<node>` — has a
`#if DSP4_BLOCK_KERNELS` arm that reads `_scope_src + _sample_idx`,
because it assumes node buffers became `BLOCK`-word arrays. On chip 2
they did (`_blk_<node>[DSP4_BLOCK_SIZE]`). On chip 1 they did not. So the
witness **walked off a one-word variable into the next node's parameter
storage**, sixteen words at a time.

That is not a hypothesis. It is visible three ways at once:

**The values it read back were parameters, not audio.** In the
block-kernel arm the peaks are IEEE-754 floats and integers with obvious
meanings, where the per-sample control reads Q4.28 audio:

| family | per-sample control (Q4.28 audio) | block-kernel arm | what the block-kernel value is |
|---|---|---|---|
| GAIN | `536870912` = 2.0 | `1065353216` | `0x3F800000` = **1.0f** |
| EQ_BIQUAD | `134217728` = 0.5 | `1082130432` | `0x40800000` = **4.0f** |
| HPF_LPF | `134217728` = 0.5 | `1082130432` | **4.0f** |
| COMPRESSOR | `113086372` | `1120403456` | `0x42C80000` = **100.0f** |
| DELAY | `9679736` | `12000` | **12000 samples** = 250 ms delay line |
| TALKBACK | `536870912` | `1082130432` | **4.0f** |

**The map says exactly which parameters.** From the chip-1 link map, the
words the witness reached at `_buf_<node> + k`, `k = 0..15`:

```
_buf_C1_GAIN_01 @ 0x92A40   +1 _mtr_wide_C1_GAIN_01   +4 _gain_coeff_C1_GAIN_02
_buf_C1_EQ_01   @ 0x912A9   +3 _eq_coeffs_A_C1_EQ_02
_buf_C1_DLY_01  @ 0x9113E   +2 _dly_write_ptr_C1_DLY_02 … +6 _dly_max_C1_DLY_02
_buf_C1_TALK_01 @ 0x951DD   +4 _talk_gain_C1_TALK_02
```

`_dly_max_C1_DLY_02` is 12000. `_gain_coeff_C1_GAIN_02` is 1.0f.
`_eq_coeffs_A_C1_EQ_02` is 4.0f. Every anomalous peak in the table above
is named in the map.

**The arithmetic of `moved` gives it away.** For the nodes whose `_buf_`
*is* written once per block, the number of samples that moved in a
64-sample capture was **exactly 4 = 64/16 = N/BLOCK** — one real sample
per block, fifteen neighbours. GAIN, GATE and TALKBACK all read `moved=4`.

So in the block-kernel arm, **GAIN and TALKBACK read "LIVE" because the
witness was watching the very parameter class the test was stepping.**
The two families that appeared to survive were the two that failed
hardest.

## 2. Defect two: the stimulus was driven into a slot with no reader

Fixing the witness alone changes nothing, and that is itself the proof.
Arm **C** below is the tap with the stimulus still as it was: the peaks
become honest — `0`, `1`, `4`, real Q4.28 magnitudes instead of float
parameters — and the verdict is **SILENT**. The witness was now telling
the truth, and the truth was that the chip-1 chain had no input.

`_scope_inject_blk` fills `DSP4_BLOCK_SIZE` words at whatever address the
host poked into `_scope_inj`. The host names the injection point by its
RX slot symbol. On chip 2 that is right — an `INTERCHIP_RECV` declares
`_rx_ic_slot_<node>[DSP4_BLOCK_SIZE]` and the chain reads it, which is
why every chip-2 family was unaffected throughout. On chip 1 it is wrong
twice:

* `INPUT_TDM`'s block kernel reads the DMA buffer **straight into a pool
  slot**; `_rx_slot_C1_IN_01` is "kept as a scalar purely so
  `block_io.asm`'s tables still resolve" and **nothing reads it**. The
  stimulus went nowhere.
* It is **one word**, and the routine wrote **sixteen** — fifteen of them
  into whatever DM follows it.

The second point is a latent memory overrun in the shipping image, not
only in the instrument. It is inert in the field (`_scope_inj` is 0 until
a host arms the scope, which nothing in the product does) but it is a
real defect and it is recorded as **S10-3** rather than fixed here,
because fixing it changes `ac65ad38`/`e5dce9e4` and that is a window
decision for PW.

## 3. The instrument: `DSP4_SCOPE_BLK_TAP`

A witness for a pooled buffer cannot live after the block. The pool is
**reused** — strip N's `BLK_CHAIN_B` is strip N+1's the moment strip N+1's
GAIN runs, and by the end of a block every slot holds the last strip that
touched it. There is no later point at which a given node's block still
exists. The only correct place to read a node's block is where the node
just left it.

So the generated chain calls `_scope_tap` immediately after every node,
with two arguments:

```
#if DSP4_BLOCK_KERNELS && DSP4_SCOPE_BLK_TAP
    r0 = _buf_C1_EQ_01;       /* identity — already what the host pokes into _scope_src */
    r1 = BLK_CHAIN_B_P1;      /* where this node's block IS, right now */
    call _scope_tap;
#endif
```

`_scope_tap` returns immediately unless `r0 == _scope_src`, and otherwise
copies the whole block into `_scope_buf`. **The host side of the family
walk did not change at all** — it still names the node by `_buf_<node>`.

Where the node owns a block array (`_blk_<node>` on chip 2, `_buf_<node>`
for MIX_BUS) the tap is handed that array instead. Two families —
TALKBACK and NOISE_GEN — have **no block kernel at all**: under block
kernels the chain calls them once per block and one word per block is
their entire output, so they get `_scope_tap1`, which records that one
word and advances by one. Decimated, but real.

Where the node's output block is a pool slot, the slot comes from
`_STRIP_BLK_OUT` in `tools/dsp/dsp_codegen.py` — the same kind of table as
`_METER_SRC_BLOCK` and under the same rule: it is a fact about the
generated kernel, and `_blk_out_of()` **checks it against the body it just
generated**, so a kernel rewritten onto a different slot fails the run
rather than quietly mis-witnessing.

The stimulus takes the same treatment: the chain hands
`_scope_inject_blk` the slot symbol the host names and the address that
node's block actually lives at. `r0 = 0` means "no redirect", which is
chip 2, byte for byte as it was.

**Cost to the shipping image: none, and it is checked rather than
asserted.** `DSP4_SCOPE_BLK_TAP` defaults to 0, the taps are inside the
guard, and a default `./build.sh` after every change in this session
reproduced `chip1.ldr ac65ad38…` / `chip2.ldr e5dce9e4…` — the staged
shipping pair, byte for byte. In the tap build the taps cost about eight
cycles per node per block, ~3.4k cycles on chip 1's ~430 positions, near
1 % of the 327,680-cycle budget; that is why it is an instrument and never
ships.

## 4. The arms

One bench, one day (2026-09-09), one contract (`defs-v2026.09.08.4`,
cross-check sha `4aa3c343…`, 0 disagreements in all four), one variable at
a time.

| | A | B | C | D |
|---|---|---|---|---|
| block | 8 | 8/16 | 16 | **16** |
| kernels | per-sample | block | block | **block** |
| witness | `_scope_record` | `_scope_record` | **`_scope_tap`** | **`_scope_tap`** |
| stimulus | RX slot | RX slot | RX slot | **redirected to the pool** |
| **audio LIVE** | **17/20** | **9/20** | **9/20** | **17/20** |

```
family       ch | A blk8 per-sample  | B kernels old-witness | C tap, old stimulus | D tap + stimulus
ANTI_FB       2 | LIVE               | LIVE                  | LIVE                | LIVE
AUX_INPUT     2 | NO_STIMULUS_PATH   | NO_STIMULUS_PATH      | NO_STIMULUS_PATH    | NO_STIMULUS_PATH
COMPRESSOR    1 | LIVE               | INERT                 | SILENT              | LIVE
CROSSOVER     2 | LIVE               | LIVE                  | LIVE                | LIVE
DCA           2 | NO_PROBE           | NO_PROBE              | NO_PROBE            | NO_PROBE
DELAY         1 | LIVE               | INERT                 | SILENT              | LIVE
EQ_BIQUAD     1 | LIVE               | INERT                 | INERT               | LIVE
FADER_PAN     1 | LIVE               | INERT                 | SILENT              | LIVE
FX_ENGINE     2 | LIVE               | LIVE                  | LIVE                | LIVE
GAIN          1 | LIVE               | LIVE*                 | LIVE                | LIVE
GATE          1 | LIVE               | INERT                 | SILENT              | LIVE
GEQ           2 | LIVE               | LIVE                  | LIVE                | LIVE
HPF_LPF       1 | LIVE               | INERT                 | INERT               | LIVE
LIMITER       2 | LIVE               | LIVE                  | LIVE                | LIVE
METER         1 | NO_PROBE           | NO_PROBE              | NO_PROBE            | NO_PROBE
MONITOR       2 | LIVE               | LIVE                  | LIVE                | LIVE
NOISE_GEN     1 | LIVE               | LIVE                  | LIVE                | LIVE
ROUTING       1 | LIVE               | SILENT                | SILENT              | LIVE
TALKBACK      1 | LIVE               | LIVE*                 | LIVE                | LIVE
TUBE_SAT      1 | LIVE               | SILENT                | SILENT              | LIVE
                                                                    A vs D agree: 20/20
```

`*` — GAIN and TALKBACK's arm-B "LIVE" is the witness reading the
parameter the test stepped (§1), not the node's output.

**The witness proved itself before the arms were believed.** NOISE_GEN
needs no stimulus: it generates its own. In arm C — the tap with the
stimulus still broken — NOISE_GEN read **peak 268,365,104** against the
per-sample control's **267,776,416**, i.e. the tap was capturing genuine
full-rate audio out of the block kernel at a moment when every
stimulus-driven family correctly read silence. That is the control the
tap needed, and it was taken on a chip-1 strip-adjacent node.

**Contract arm: identical on all twenty families**, A against D —
GEQ 31/31, CROSSOVER 8/8, ROUTING 42/42, COMPRESSOR 17/17, ANTI_FB 20/20,
0 FAILED. **Numeric arm: BIT_EXACT in both** for COMPRESSOR, FADER_PAN,
TUBE_SAT.

**One line did not reproduce and it is stated, not hidden.** GATE's
NUMERIC arm reads `NO_STIMULUS` in arm D where arm A reads `BIT_EXACT` —
`dsp4_node_verify`'s own stimulus search found no usable point in a block
build. GATE's **audio** arm is LIVE and its contract arm is 12/12, so this
is a property of the second instrument, not of the family. Open as
**S10-4**.

## 5. What this means for the shipping pair

`blk_chip1.ldr` `ac65ad386fb910b7bed7736872abae43` /
`blk_chip2.ldr` `e5dce9e43c2c72290c115726ca31976c` — the shipping pair —
is now **proven to pass audio correctly by the family walk**, at the block
size, the kernels and the clock it actually runs. The 8-of-20 line that
blocked it was never about the audio.

Three things carry forward:

1. **Every block-kernel famverify run since 2026-09-01 was measuring its
   own instrument on chip 1**, and no chip-1 audio conclusion from those
   runs should be quoted.
2. **The shipping image's `_scope_inject_blk` still overruns
   `_rx_slot_C1_IN_01` by fifteen words when a host arms the scope**
   (S10-3). Inert in the field; a new pair to fix.
3. **`DIAG_BUILD_CFG` has no spare bit for `DSP4_SCOPE_BLK_TAP`** — bits
   8..23 are all allocated and 31..24 is the signature — so the tap build
   is identified by its build banner and by `_scope_tap` in its map, not
   by the part. That is a gap in "the image says what it is" and it is
   recorded as **S10-5**. The report now records `build_cfg` per chip, so
   a famverify JSON at least says which of five same-day configurations it
   was taken on.
