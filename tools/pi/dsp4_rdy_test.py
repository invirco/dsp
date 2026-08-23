"""Decisive SPI2_RDY test.

The DSP drains its RFIFO by polling BETWEEN transactions, so it cannot
drain during one. Clock a long single transfer with CS held asserted: 64
bytes = 16 words into a 2-deep FIFO. By the end the RFIFO must be full,
and with FCEN=1/FCCH=0(RX)/FCPL=1 the slave must have deasserted RDY.
Sample it the instant the transfer returns.
"""
import sys; sys.argv=['r']
import dsp4_diag as D
link = D.SpiLink('0.0', 1000000, 6, rdy_gpio=8)
print('idle RDY =', link.rdy.get_value(), '(1 = ready, FCPL=1)')
low = 0
for i in range(40):
    link.realign(64)                 # 64 bytes, CS asserted throughout
    if link.rdy.get_value() == 0:
        low += 1
print(f'RDY read LOW immediately after a 16-word burst: {low}/40')
print('RDY TRACKS THE RFIFO — usable as flow control' if low
      else 'RDY stayed asserted through a guaranteed FIFO overfill')
