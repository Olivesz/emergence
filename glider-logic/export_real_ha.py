#!/usr/bin/env python3
"""Export the ACTUAL verified half-adder glider field (raw B3/S23) for each of the
4 input combos, so the viewer can run the REAL gliders -- not a schematic. Each
file = the real catalysts + the real input gliders for that (A,B). BOUNDED build."""
import time
from life import run, bbox, translate
from gadgets import split_gliders, glider_dir, glider_lane
from routed import build_variants, to_rle
from ha_full import build_half_adder

t0 = time.time()
def lap(m): print(f"[{time.time()-t0:6.1f}s] {m}", flush=True)
V = build_variants(); lap("built variants")
h = build_half_adder(V, lap)
cats = h['cats']; SUM = h['sum_lanes']; CL = h['carry_lane']
T = h['t_tgt'] + 1800

# common frame: shift every state by the union-bbox min so coords are >=0 and the
# 4 files share one coordinate system (so the same lanes mean the same thing).
states = {}
for A in (0, 1):
    for B in (0, 1):
        s = set(cats)
        if A: s |= set(h['a_in']) | set(h['a2_in']) | set(h['a3_in'])
        if B: s |= set(h['b_in']) | set(h['b2_in'])
        states[(A, B)] = s
allc = set().union(*states.values())
x0, y0, x1, y1 = bbox(allc)
dx, dy = -x0, -y0

for (A, B), s in states.items():
    st = translate(s, dx, dy)
    # confirm the REAL field computes the expected sum/carry (raw rule)
    gs, rest = split_gliders(run(set(s), T))
    sm = 1 if [l for (d, l) in ((glider_dir(g), glider_lane(g)) for g in gs)
               if d == (1, 1) and l in SUM] else 0
    cy = 1 if any(glider_dir(g) == (-1, -1) and glider_lane(g) == CL for g in gs) else 0
    ok = (sm == (A ^ B)) and (cy == (A & B)) and (rest == cats)
    fn = f"real_ha_{A}{B}.rle"
    open(fn, "w").write(to_rle(st))
    lap(f"{fn}: A={A} B={B} -> sum={sm} carry={cy} verified={ok}  {len(st)} cells")

# also emit the common-frame geometry so the page can label the output lanes
print(f"FRAME shift=({dx},{dy}) unionbbox=({x0},{y0},{x1},{y1})", flush=True)
print(f"SUM_LANES(orig)={sorted(SUM)} CARRY_LANE(orig)={CL} settleT={T}", flush=True)
