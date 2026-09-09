"""build_config.py — read MW/D32/DSP/SHARC/shipping.config.

The shipping build parameters live in ONE file. This is the Python half of
reading it; build.sh sources the same file directly. See shipping.config's own
header for why it exists.

An environment variable of the same name always wins, so a control arm is
still one command -- but the override is then explicit and lands in the
image's DIAG_BUILD_CFG word.
"""
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.normpath(
    os.path.join(_HERE, '..', '..', 'MW', 'D32', 'DSP', 'SHARC',
                 'shipping.config'))


def load(path=None):
    """Return {KEY: int} from shipping.config. Missing file -> {}."""
    path = path or os.environ.get('DSP4_SHIPPING_CONFIG', CONFIG_PATH)
    out = {}
    try:
        fh = open(path)
    except OSError:
        return out
    with fh:
        for n, line in enumerate(fh, 1):
            line = line.split('#', 1)[0].strip()
            if not line:
                continue
            if '=' not in line:
                raise ValueError('%s:%d: not KEY=VALUE: %r' % (path, n, line))
            k, v = line.split('=', 1)
            try:
                out[k.strip()] = int(v.strip(), 0)
            except ValueError:
                raise ValueError('%s:%d: %s is not an integer: %r'
                                 % (path, n, k.strip(), v.strip()))
    return out


def get(key, default=None):
    """Environment first, then shipping.config, then `default`."""
    if key in os.environ and os.environ[key] != '':
        return int(os.environ[key], 0)
    v = load().get(key)
    return default if v is None else v


if __name__ == '__main__':
    import sys
    cfg = load()
    if len(sys.argv) > 1:
        for k in sys.argv[1:]:
            print(get(k, ''))
    else:
        for k, v in cfg.items():
            print('%s=%s' % (k, v))
