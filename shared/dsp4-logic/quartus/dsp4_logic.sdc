# dsp4_logic.sdc — timing constraints
# 49.152 MHz XO (Y1, CB3LV) on SYSCLK
create_clock -name sysclk -period 20.345 [get_ports sysclk]
derive_clock_uncertainty
