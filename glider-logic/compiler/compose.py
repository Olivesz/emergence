#!/usr/bin/env python3
"""The make-or-break compiler test: chain two gates by ROUTING gate1's output into
gate2's input. If a gate's output can be routed and re-consumed, every multi-gate
circuit is 'just more of this'. Build a routed 3-input AND: AND(AND(a,b),c)=a&b&c.
BOUNDED sims."""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from life import run, bbox
from gadgets import split_gliders, glider_dir, glider_lane, glider_phase, DIRNAME
from routed import backcast, traj_params, se_ident, bbox_gap
import gates
from router import V, place_snark, route_from

t0 = time.time()
r = gates.AND_REACTION
bx, by, bph = r['offset'][0], r['offset'][1], r['phase']

def and_inputs(ox, oy, A, B):
    """AND gate at (ox,oy): a=SE(ox,oy), b=SW(ox+bx,oy+by,bph). Returns the input set."""
    s = set()
    if A: s |= set(gates.glider('SE', ox, oy))
    if B: s |= set(gates.glider('SW', ox + bx, oy + by, bph))
    return s

# ---- gate1 = AND(a,b) at origin; grab its NW output x (case a=b=1) ----
g1 = and_inputs(0, 0, 1, 1)
gs, rest = split_gliders(run(g1, 260))
xs = [g for g in gs if glider_dir(g) == (-1, -1)]
assert len(xs) == 1 and not rest, f"gate1 AND(1,1) didn't give a clean NW output: {[(DIRNAME[glider_dir(g)],glider_lane(g)) for g in gs]}"
x = xs[0]
print(f"gate1 AND(1,1) -> x: NW lane {glider_lane(x)} phase {glider_phase(x)} bbox {bbox(x)}", flush=True)

# ---- route x with 2 right turns (NW->NE->SE), place c, read the output RIGHT AFTER
# the merge (before the output travels onward — a downstream wire the compiler routes
# later; here we only need to prove the AND fires on the routed signal). ----
rr = route_from(x, [('R', 30), ('R', 30)])
assert rr, "route failed"
rcats, xr, wp = rr
base = and_inputs(0, 0, 1, 1) | rcats
xr_full = T_xr = None
s = set(base); T = 0
while T < 2600:
    s = run(s, 30); T += 30
    gs, rst = split_gliders(s)
    se = [g for g in gs if glider_dir(g) == (1, 1) and glider_lane(g) == glider_lane(xr)]
    if se and rst == rcats and bbox_gap(se[0], rcats) >= 18:
        xr_full, T_xr = se[0], T; break
assert xr_full, "x_routed not found"
X, Y, tref = se_ident(xr_full, T_xr)                 # canonical SE identity (proven to fire)
c_launch = set(backcast(gates.glider('SW', X + bx, Y + by, bph), tref))

# trace the read window: when is the gate2 NW output present AND the Snarks still intact?
full = and_inputs(0, 0, 1, 1) | rcats | c_launch
T_read = None
sc = run(set(full), max(0, tref - 40)); tt = tref - 40      # fast-forward to near the merge
while tt < tref + 240:
    sc = run(sc, 8); tt += 8
    gs, rest = split_gliders(sc)
    nw = [g for g in gs if glider_dir(g) == (-1, -1)]
    if nw and rest == rcats:
        T_read = tt; break
print(f"gate2: merge ~({X},{Y}) t~{tref}; clean read window t={T_read}", flush=True)
assert T_read, "no clean read window (output collides too fast)"

print("\nRouted 3-input AND  out = a & b & c  (read at the gate2 merge):", flush=True)
allok = True
for (A, B, C) in [(1, 1, 1), (1, 1, 0), (1, 0, 1), (0, 1, 1), (0, 0, 0)]:
    s = and_inputs(0, 0, A, B) | rcats
    if C: s |= c_launch
    gs, rest = split_gliders(run(s, T_read))
    nw = [g for g in gs if glider_dir(g) == (-1, -1)]     # gate2 output = the only NW glider
    got = 1 if nw else 0
    ok = (got == (A & B & C)) and (rest == rcats)
    allok &= ok
    print(f"  a={A} b={B} c={C} -> out={got} want {A&B&C}  snarks_ok={rest==rcats}  "
          f"{'OK' if ok else 'FAIL'}", flush=True)
print("\nGATE COMPOSITION (routed a&b&c):", "PASS" if allok else "PARTIAL",
      f"({round(time.time()-t0,1)}s)", flush=True)

# ---- EMIT the compiled circuit (a=b=c=1) as a standalone field to watch it run ----
from routed import to_rle
field = and_inputs(0, 0, 1, 1) | rcats | c_launch
here = os.path.dirname(os.path.abspath(__file__))
open(os.path.join(here, "compiled_and.rle"), "w").write(to_rle(field))
print(f"emitted compiled_and.rle: {len(field)} cells, bbox {bbox(field)}  "
      f"(gate1 AND @origin -> routed -> gate2 AND -> a&b&c)", flush=True)

