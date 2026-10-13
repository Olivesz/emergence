#!/usr/bin/env python3
"""Physical fan-out, no routing hardware: a duplicator's SE output (lane -23) sits
exactly on the INPUT lane of a second duplicator placed at offset dy-dx=-22, so
duplicators CHAIN directly.  N chained duplicators fan one glider into N+1 physical
copies on distinct lanes — the fan-out tree a fully-physical adder needs, built from
duplicators alone.  Verified raw B3/S23: every catalyst restored.  BOUNDED sims."""
import time
from life import run
from gadgets import (split_gliders, glider_dir, glider_lane, place_duplicator,
                     dup_input_glider)

t0 = time.time()


def chain(n, dxs):
    """Chain n duplicators: each new one has input lane = previous SE-out lane.
    dxs = list of downstream dx offsets. Returns (field, cats)."""
    cats = set(place_duplicator(0, 0))
    a_in = set(dup_input_glider(0, 0, back=0))
    in_lane = -23                                # dup1's SE-output lane
    for k in range(1, n):
        dx = dxs[k - 1]
        dy = dx + (in_lane + 1)                  # input lane == in_lane (DUP_IN_LANE=-1)
        cats |= set(place_duplicator(dx, dy))
        in_lane = in_lane - 22                   # this dup's SE output lane
    return cats | a_in, set(c for c in cats)


def verify(n, dxs, ticks=1600):
    field, cats = chain(n, dxs)
    gs, rest = split_gliders(run(field, ticks))
    ok = (rest == cats) and (len(gs) == n + 1)   # n+1 copies from one input
    lanes = sorted((glider_dir(g), glider_lane(g)) for g in gs)
    return ok, len(gs), lanes


# 1 -> 3 (two duplicators): confirm across a band of placements
good = [dx for dx in range(40, 60) if verify(2, [dx])[0]]
print(f"1->3 fan-out (dup+dup): {len(good)}/20 placements clean; e.g. dx={good[:3]}")
ok3, n3, lanes3 = verify(2, [good[0]])
print(f"   dx={good[0]}: {n3} copies, lanes {lanes3}, catalysts restored={ok3}")

# 1 -> 4 (three duplicators): chain a third off the second's SE output
good4 = [dx3 for dx3 in range(good[0] + 30, good[0] + 90)
         if verify(3, [good[0], dx3])[0]]
if good4:
    ok4, n4, lanes4 = verify(3, [good[0], good4[0]])
    print(f"1->4 fan-out (dup+dup+dup): dx3={good4[0]}: {n4} copies, "
          f"lanes {lanes4}, catalysts restored={ok4}")
else:
    ok4 = False
    print("1->4: no clean third-level placement in the swept band")
print("elapsed", round(time.time() - t0, 1), "s")
raise SystemExit(0 if (good and good4 and ok3 and ok4) else 1)
