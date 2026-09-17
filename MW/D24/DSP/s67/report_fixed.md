
## fader, analog (dB re fader 0 dB; ideal = 20 log10 Level)
| fader | ideal | strip 5 post-fdr | MAIN L | MAIN R | worst err |
| 0 dB |   0.000 |    0.000 |    0.000 |    0.000 | 0.0000 |
| -6 dB |  -6.000 |   -6.000 |   -6.000 |   -6.000 | 0.0000 |
| -20 dB | -20.000 |  -20.000 |  -20.000 |  -20.000 | 0.0000 |
| -inf (Off) |    -inf |     -inf |     -inf |     -inf | exact 0 (H = 0) |
| 0 dB again |   0.000 |    0.000 |    0.000 |   -0.000 | 0.0000 |
absolute at 0 dB: {5: 5.5768, 33: -0.4438, 34: -0.4438}

## fader, osc (dB re fader 0 dB; ideal = 20 log10 Level)
| fader | ideal | strip 5 post-fdr | MAIN L | MAIN R | AUX 1 | worst err |
| 0 dB |   0.000 |    0.000 |    0.000 |    0.000 |    0.000 | 0.0000 |
| -6 dB |  -6.000 |   -6.000 |   -6.000 |   -6.000 |   -6.000 | 0.0000 |
| -20 dB | -20.000 |  -20.000 |  -20.000 |  -20.000 |  -20.000 | 0.0000 |
| -inf (Off) |    -inf |     -inf |     -inf |     -inf |     -inf | exact 0 (H = 0) |
| 0 dB again |   0.000 |    0.000 |    0.000 |    0.000 |    0.000 | 0.0000 |
absolute at 0 dB: {5: 0.0, 33: -6.0206, 34: -6.0206, 35: 0.0}

## pan (analog): MAIN L/R re strip 5 post-fader, dB
| law | idx | L meas | L pred | R meas | R pred | worst err |
| 0 | 0 |   -0.000 |    0.000 |     -inf |     -inf | 0.0000 |
| 0 | 63 |   -6.021 |   -6.021 |   -6.021 |   -6.021 | 0.0000 |
| 0 | 126 |     -inf |     -inf |    0.000 |    0.000 | 0.0000 |
| 1 | 0 |   -0.000 |    0.000 |     -inf |     -inf | 0.0000 |
| 1 | 63 |   -6.021 |   -6.021 |   -6.021 |   -6.021 | 0.0000 |
| 1 | 126 |     -inf |     -inf |   -0.000 |    0.000 | 0.0000 |

## assign, analog (coherent H dB; nonzero words of 16 in the bus block)
| Main on | 33:  -0.444 | 34:  -0.444 | 5:   5.577 | {'_buf_C1_BUS_MAIN_L': 16, '_buf_C1_BUS_MAIN_R': 16, '_buf_C1_BUS_AUX_01': 16} |
| Main off | 33:    -inf | 34:    -inf | 5:   5.577 | {'_buf_C1_BUS_MAIN_L': 0, '_buf_C1_BUS_MAIN_R': 0, '_buf_C1_BUS_AUX_01': 16} |
| Main on again | 33:  -0.444 | 34:  -0.444 | 5:   5.577 | {'_buf_C1_BUS_MAIN_L': 16, '_buf_C1_BUS_MAIN_R': 16, '_buf_C1_BUS_AUX_01': 16} |

## assign, osc (coherent H dB; nonzero words of 16 in the bus block)
| Main on | 33:  -6.021 | 34:  -6.021 | 35:    -inf | 5:   0.000 | {'_buf_C1_BUS_MAIN_L': 16, '_buf_C1_BUS_MAIN_R': 16, '_buf_C1_BUS_AUX_01': 0} |
| Main off | 33:    -inf | 34:    -inf | 35:    -inf | 5:   0.000 | {'_buf_C1_BUS_MAIN_L': 0, '_buf_C1_BUS_MAIN_R': 0, '_buf_C1_BUS_AUX_01': 0} |
| Main on again | 33:  -6.021 | 34:  -6.021 | 35:    -inf | 5:   0.000 | {'_buf_C1_BUS_MAIN_L': 16, '_buf_C1_BUS_MAIN_R': 16, '_buf_C1_BUS_AUX_01': 0} |
| Aux1 on | 33:  -6.021 | 34:  -6.021 | 35:   0.000 | 5:   0.000 | {'_buf_C1_BUS_MAIN_L': 16, '_buf_C1_BUS_MAIN_R': 16, '_buf_C1_BUS_AUX_01': 16} |
| Aux1 off | 33:  -6.021 | 34:  -6.021 | 35:    -inf | 5:   0.000 | {'_buf_C1_BUS_MAIN_L': 16, '_buf_C1_BUS_MAIN_R': 16, '_buf_C1_BUS_AUX_01': 0} |
| Aux1 on again | 33:  -6.021 | 34:  -6.021 | 35:   0.000 | 5:   0.000 | {'_buf_C1_BUS_MAIN_L': 16, '_buf_C1_BUS_MAIN_R': 16, '_buf_C1_BUS_AUX_01': 16} |

## sum (osc, OscChan 99), coherent H dB re the oscillator
| strip 5 alone | 33:  -6.021 (pred   -6.021) | 34:  -6.021 (pred   -6.021) | 35:   0.000 (pred    0.000) |
| strip 6 alone | 33:  -6.021 (pred   -6.021) | 34:  -6.021 (pred   -6.021) | 35:   0.000 (pred    0.000) |
| 5 + 6 equal | 33:   0.000 (pred    0.000) | 34:   0.000 (pred    0.000) | 35:   6.021 (pred    6.021) |
| 5 + 6(-6 dB) | 33:  -2.492 (pred   -2.492) | 34:  -2.492 (pred   -2.492) | 35:   3.529 (pred    3.529) |

## EQ/dyn, analog
| EQ 1000 Hz | pred +6.000 | strip +6.0000 | MAIN L +6.0000 |
| EQ 2000 Hz | pred +1.866 | strip +1.8660 | MAIN L +1.8660 |
| EQ 250 Hz | pred +0.423 | strip +0.4230 | MAIN L +0.4230 |
| COMP in -10.46 dBFS pk, ratio 4 | pred(peak) -7.152 | pred(envelope -11.56) -6.331 | gain word -6.331 | strip -6.281 | MAIN L -6.253 |
| COMP in -10.46 dBFS pk, ratio 2 | pred(peak) -4.768 | pred(envelope -11.55) -4.223 | gain word -4.223 | strip -4.174 | MAIN L -4.146 |
| COMP in -15.42 dBFS pk, ratio 4 | pred(peak) -3.433 | pred(envelope -16.60) -2.549 | gain word -2.549 | strip -2.572 | MAIN L -2.572 |
| COMP in -15.42 dBFS pk, ratio 2 | pred(peak) -2.288 | pred(envelope -16.55) -1.723 | gain word -1.723 | strip -1.715 | MAIN L -1.715 |

## EQ/dyn, osc
| EQ 1000 Hz | pred +6.000 | strip +6.0000 | MAIN L +6.0000 |
| EQ 2000 Hz | pred +1.866 | strip +1.8660 | MAIN L +1.8660 |
| EQ 250 Hz | pred +0.423 | strip +0.4229 | MAIN L +0.4229 |
| COMP in -10.00 dBFS pk, ratio 4 | pred(peak) -7.500 | pred(envelope -11.19) -6.608 | gain word -6.608 | strip -6.634 | MAIN L -6.634 |
| COMP in -10.00 dBFS pk, ratio 2 | pred(peak) -5.000 | pred(envelope -11.16) -4.419 | gain word -4.419 | strip -4.422 | MAIN L -4.422 |
| COMP in -16.00 dBFS pk, ratio 4 | pred(peak) -3.000 | pred(envelope -17.16) -2.128 | gain word -2.128 | strip -2.134 | MAIN L -2.134 |
| COMP in -16.00 dBFS pk, ratio 2 | pred(peak) -2.000 | pred(envelope -17.19) -1.405 | gain word -1.405 | strip -1.422 | MAIN L -1.422 |
