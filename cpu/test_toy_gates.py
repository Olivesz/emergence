#!/usr/bin/env python3
"""Act VIII's Wireworld gates in index.html, run in the reference rule.

The gate layouts are read out of index.html itself (WW_GATES), not retyped, so
this test checks exactly what a visitor runs. Each gate is placed on the toy's
112x56 board at the toy's offset and driven the toy's way: for every input
row, electrons are cleared, an electron is launched rightward at each active
input cell, and the output cell is watched for one gate period.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from ww_cells import step

PAGE = os.path.join(HERE, "..", "index.html")
WW_W, WW_H = 112, 56
WANT = {
    "or":  {"O": [0, 1, 1, 1]},
    "xor": {"O": [0, 1, 1, 0]},
    "and": {"O": [0, 0, 0, 1]},
    "ha":  {"O": [0, 0, 0, 1], "S": [0, 1, 1, 0]},
}
ROWS = [(0, 0), (1, 0), (0, 1), (1, 1)]          # (A, B), index = A + 2B as in the toy


def load_gates(path=PAGE):
    src = open(path).read()
    m = re.search(r"var WW_GATES = \{(.*?)\n  \};", src, re.S)
    if not m:
        raise ValueError("WW_GATES not found in index.html")
    body = re.sub(r"//[^\n]*", "", m.group(1))
    body = re.sub(r"(\b[a-z]+)\s*:", r'"\1":', body)
    body = re.sub(r",\s*([\]}])", r"\1", body)
    return json.loads("{" + body + "}")


def place(art):
    ox, oy = (WW_W - len(art[0])) // 2, (WW_H - len(art)) // 2
    g = [0] * (WW_W * WW_H)
    marks = {}
    for r, row in enumerate(art):
        for c, ch in enumerate(row):
            x, y = ox + c, oy + r
            if not (0 <= x < WW_W and 0 <= y < WW_H) or ch == " ":
                continue
            g[y * WW_W + x] = {"@": 1, "~": 2}.get(ch, 3)
            if ch in "ABOS":
                marks[ch] = (x, y)
    return g, marks


def run_row(g0, marks, a, b, period):
    g = g0[:]
    for name, on in (("A", a), ("B", b)):
        if on:
            x, y = marks[name]
            g[y * WW_W + x] = 1
            if x > 0:
                g[y * WW_W + x - 1] = 2
    seen = {k: 0 for k in "OS" if k in marks}
    for _ in range(period):
        g = step(WW_W, WW_H, g)
        for k in seen:
            x, y = marks[k]
            if g[y * WW_W + x] == 1:
                seen[k] = 1
    return seen


def main():
    gates = load_gates()
    ok = True
    if sorted(gates) != sorted(WANT):
        print(f"  [FAIL] index.html gates {sorted(gates)} != tested {sorted(WANT)}")
        ok = False
    for name, want in WANT.items():
        gate = gates.get(name)
        if gate is None:
            continue
        g0, marks = place(gate["art"])
        got = {k: [] for k in want}
        for a, b in ROWS:
            seen = run_row(g0, marks, a, b, gate["period"])
            for k in want:
                got[k].append(seen[k])
        for k in want:
            good = got[k] == want[k]
            ok &= good
            label = {"O": "out", "S": "sum"}[k]
            print(f"  [{'PASS' if good else 'FAIL'}] {name:3} {label}: "
                  f"00,10,01,11 -> {got[k]} (want {want[k]})")
    print("ALL PASS" if ok else "SOME FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
