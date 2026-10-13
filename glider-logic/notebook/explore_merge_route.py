#!/usr/bin/env python3
"""Decisive parity test: can EITHER 2-Snark SE->SE pair route lane 8 -> lane -23
(the two XOR sum rails)? SW pair conserves lane parity; NE pair may flip it."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from routed import build_variants, bbox_gap
from gadgets import split_gliders, glider_dir, glider_lane
from life import run
V = build_variants()

def shifter(pair, L_in, L_out, dx1):
    v1, v2 = pair
    dy1 = dx1 + (L_in - v1.lin)              # v1 SE in-lane (ymx) == L_in
    cat1 = v1.place(dx1, dy1)
    Lmid = v1.out_lane(dx1, dy1)             # v1 out lane (xpy: SW or NE)
    S = Lmid - v2.lin                        # dx2+dy2  (v2 in, xpy)
    D = L_out - v2.lout                      # dy2-dx2  (v2 out SE, ymx)
    if (S - D) % 2:
        return None
    dx2, dy2 = (S - D) // 2, (S + D) // 2
    cat2 = v2.place(dx2, dy2)
    if bbox_gap(cat1, cat2) < 5:
        return None
    return cat1 | cat2, (dx1, dy1), (dx2, dy2)

sw = (V['snark_m0r1'], V['snark_m1r0'])       # SE->SW->SE
ne = (V['snark_m1r3'], V['snark_m0r0'])       # SE->NE->SE
for name, pair in [('SW', sw), ('NE', ne)]:
    parity_ok = built = clean = 0
    hit = None
    for dx1 in range(-80, 340, 1):
        b = shifter(pair, 8, -23, dx1)
        if b is None:
            continue
        parity_ok += 1
        cats, p1, p2 = b
        gin = set(pair[0].input_glider(*p1, back=6))
        if gin & cats:
            continue
        built += 1
        gs, rest = split_gliders(run(cats | gin, 1400))
        if rest == cats and len(gs) == 1 and glider_dir(gs[0]) == (1, 1) and glider_lane(gs[0]) == -23:
            clean += 1
            if hit is None:
                hit = dx1
    print(f"{name} pair  8->-23:  parity-valid={parity_ok}  placed={built}  clean-routes={clean}"
          + (f"  (e.g. dx1={hit})" if hit is not None else ""))
