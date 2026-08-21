# dsp4_logic.sdc — timing constraints
# 49.152 MHz XO (Y1, CB3LV) on SYSCLK
create_clock -name sysclk -period 20.345 [get_ports sysclk]

# DSP_CLK (pin 140) is sysclk/2 = 24.576 MHz — the ADSP-2156x CLKIN range
# is fCKIN = 20-30 MHz (datasheet Rev. A Table 23), so the raw XO must not
# reach SYS_CLKIN0. Registered toggle flop straight to the output pin.
create_generated_clock -name dsp_clk -source [get_ports sysclk] \
    -divide_by 2 [get_ports dsp_clk]
# Quartus emits "Warning (332088): No paths exist between clock target
# dsp_clk and its clock source" for this: the flop's Q-to-pin hop is a data
# path, not a clock path, so it will not trace target->source. Benign here —
# nothing inside the CPLD is clocked by dsp_clk, so the zero source latency
# it falls back to is used by no analysed path. Sourcing from
# [get_pins dsp_clk_q|clk] instead does not silence it and breaks the
# constraint outright if the flop is ever renamed or un-preserved.

# after all clocks
derive_clock_uncertainty
