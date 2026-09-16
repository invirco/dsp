"""s52_setup.py — strip 20 transparent for MeasChan."""
import s52lib as X
c1 = X.Chip(1)
X.strip_unity(c1, 20)
print('strip 20 unity/unmuted/dyn off: Mute', c1.r('Chan020Mute001'), 'CompOn', c1.r('Chan020CompOn001'),
      'GateOn', c1.r('Chan020GateOn001'), 'EqOn', c1.r('Chan020EqOn001'), 'TubeOn', c1.r('Chan020TubeOn001'),
      'Gain %.4f' % X.from_f32(c1.r('Chan020Gain001')), 'Level %.4f' % X.from_f32(c1.r('Chan020Level001')))
