#!/usr/bin/env python3
"""Compiler foundation: route ONE glider along an arbitrary path by placing Snarks.
Each turn is verified in the raw rule (one clean glider out, catalyst restored). This
is the wire substrate the whole compiler stands on. BOUNDED single-glider sims."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from life import run, bbox
from gadgets import split_gliders, glider_dir, glider_lane, glider_phase, DIRNAME
from routed import build_variants, bbox_gap
import gates

V = build_variants()

# 8 Snark orientations mapped to (incoming dir) -> turn.  Directions as (dx,dy):
# SE=(1,1) SW=(-1,1) NW=(-1,-1) NE=(1,-1).  Right = clockwise, Left = counterclockwise.
RIGHT = {(1, 1): 'snark_m0r1', (-1, 1): 'snark_m0r2', (-1, -1): 'snark_m0r3', (1, -1): 'snark_m0r0'}
LEFT  = {(1, 1): 'snark_m1r3', (1, -1): 'snark_m1r2', (-1, -1): 'snark_m1r1', (-1, 1): 'snark_m1r0'}
OUT_R = {(1, 1): (-1, 1), (-1, 1): (-1, -1), (-1, -1): (1, -1), (1, -1): (1, 1)}
OUT_L = {(1, 1): (1, -1), (1, -1): (-1, -1), (-1, -1): (-1, 1), (-1, 1): (1, 1)}

def fam(d): return 'ymx' if d in ((1, 1), (-1, -1)) else 'xpy'

def place_snark(g, turn, along, span=60):
    """Place a Snark to turn glider g (turn 'L'/'R') ~`along` cells downstream.
    Returns (catalyst, out_glider, dx_used) or None. Verified: 1 clean glider out,
    catalyst restored, direction actually turned."""
    d = glider_dir(g); L = glider_lane(g)
    v = V[(RIGHT if turn == 'R' else LEFT)[d]]
    want = (OUT_R if turn == 'R' else OUT_L)[d]
    gx0, gy0, gx1, gy1 = bbox(g)
    base = gx0 + d[0] * along                     # downstream anchor in x
    for off in range(-span, span):
        dx = base + off
        if fam(d) == 'ymx':
            dy = dx + (L - v.lin)                 # v in_lane (ymx) == L
        else:
            dy = (L - v.lin) - dx                 # v in_lane (xpy) == L
        cat = v.place(dx, dy)
        if cat & g or bbox_gap(cat, g) < 3:
            continue
        gs, rest = split_gliders(run(set(g) | cat, 4 * along + 700))
        if rest == cat and len(gs) == 1 and glider_dir(gs[0]) == want:
            return cat, gs[0], dx
    return None

def route(start_dir, start_pos, segments):
    """start a glider going start_dir at start_pos; segments = [(turn, along), ...].
    Returns (all_catalysts, final_glider, waypoints) or None on failure."""
    x0, y0 = start_pos
    g = set(gates.glider(DIRNAME[start_dir], x0, y0))
    cats = set(); wp = [(DIRNAME[start_dir], glider_lane(g), bbox(g))]
    for i, (turn, along) in enumerate(segments):
        r = place_snark(g, turn, along)
        if r is None:
            print(f"  segment {i} ({turn},{along}) from {DIRNAME[glider_dir(g)]}: NO clean turn")
            return None
        cat, g2, dx = r
        cats |= cat
        wp.append((DIRNAME[glider_dir(g2)], glider_lane(g2), bbox(g2)))
        g = set(g2)
    return cats, g, wp


if __name__ == "__main__":
    import time
    t0 = time.time()
    # 4 right turns from SE: SE->SW->NW->NE->SE (a box). Verify each turn + whole path.
    res = route((1, 1), (0, 0), [('R', 60), ('R', 60), ('R', 60), ('R', 60)])
    if res is None:
        print("route FAILED"); sys.exit(1)
    cats, gfinal, wp = res
    print("waypoints (dir, lane, bbox):")
    for w in wp:
        print("  ", w)
    # whole-path verification: start glider + all Snarks, run, expect 1 clean glider out
    x0, y0 = 0, 0
    g0 = set(gates.glider('SE', x0, y0))
    field = g0 | cats
    gs, rest = split_gliders(run(field, 4000))
    ok = (rest == cats) and len(gs) == 1
    print(f"\nWHOLE PATH: {len(cats)} catalyst cells, final gliders={len(gs)} "
          f"dir={DIRNAME[glider_dir(gs[0])] if gs else '-'}, catalysts restored={rest==cats}")
    print("ROUTER:", "PASS" if ok else "FAIL", f"({round(time.time()-t0,1)}s)")
