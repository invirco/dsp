#!/usr/bin/env python3
"""Emit a name -> word-address table from a CCES .map.xml.

The scope harness needs the address of any .var it wants to poke or read,
and those move on every build. Reading them out of the map keeps the host
tool honest instead of carrying hand-copied constants that go stale.
"""
import json, re, sys

def syms(path):
    s = open(path, errors='ignore').read()
    out = {}
    for m in re.finditer(r"name='(_[A-Za-z0-9_]+)'[^>]*address='(0x[0-9a-fA-F]+)'", s):
        out.setdefault(m.group(1), int(m.group(2), 16))
    for m in re.finditer(r"address='(0x[0-9a-fA-F]+)'[^>]*name='(_[A-Za-z0-9_]+)'", s):
        out.setdefault(m.group(2), int(m.group(1), 16))
    return out

if __name__ == '__main__':
    print(json.dumps(syms(sys.argv[1]), indent=0, sort_keys=True))
