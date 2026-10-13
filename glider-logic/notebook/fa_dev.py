#!/usr/bin/env python3
"""Full-adder step 2: SUM-MERGE (OR the XOR's two sum rails onto ONE lane).
Route b_data (SE lane 8) through a 2-Snark shifter onto lane -23 (a_data's lane) so
"sum=1" is always a glider on lane -23, whichever input produced it. Verify all 4
rows in the raw rule (catalysts restored). This is the foundation of HA1->HA2.
Bounded simulations only."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import time
from life import run, translate
from gadgets import split_gliders, glider_dir, glider_lane
from routed import build_variants, bbox_gap
from ha_xor import build_routed_xor
from lane_shift import build_shift   # SE lane L_in -> SE lane L_out via 2 Snarks

t0 = time.time()
def lap(m): print(f"[{time.time()-t0:6.1f}s] {m}", flush=True)
V = build_variants(); lap("variants")
x = build_routed_xor(V, lap)
cats, a_in, a2_in, b_in = x['cats'], x['a_in'], x['a2_in'], x['b_in']
L_bd = x['L_bd']; T = x['t_tgt'] + 1800
lap("XOR built")

def field(A, B, extra=frozenset()):
    s = set(cats) | set(extra)
    if A: s |= set(a_in) | set(a2_in)
    if B: s |= set(b_in)
    return s

def on_lane(state, d, lane):
    gs, rest = split_gliders(state)
    return [g for g in gs if glider_dir(g) == d and glider_lane(g) == lane], rest

# a 2-Snark shifter that turns SE-lane-8 (b_data) into SE-lane-(-23). Slide it along
# b_data's flight (lane 8) until it (a) cleanly reroutes b_data to -23, (b) leaves the
# XOR catalysts + a_data untouched.
cand = None
n_built = n_clear = n_clean = 0
for dx1 in range(-60, 720, 2):
    built = build_shift(8, -23, dx1)
    if not built:
        continue
    n_built += 1
    sh_cats, p1, p2 = built
    if sh_cats & cats or bbox_gap(sh_cats, cats) < 5:
        continue
    n_clear += 1
    # A=0,B=1: b_data must become a clean SE glider on -23, all catalysts restored
    allc = cats | sh_cats
    st = run(field(0, 1, sh_cats), T)
    g23, rest = on_lane(st, (1, 1), -23)
    g8, _ = on_lane(st, (1, 1), 8)
    if len(g23) == 1 and not g8:
        n_clean += 1
        if rest == allc:
            cand = (dx1, sh_cats, p1, p2); break
lap(f"search: built={n_built} collision-free={n_clear} routed-b_data-to-(-23)={n_clean}")
if cand is None:
    lap("NO clean shifter placement routes b_data(8) -> -23 with catalysts restored.")
    raise SystemExit
dx1, sh_cats, p1, p2 = cand
allc = cats | sh_cats
lap(f"shifter placed dx1={dx1} Snarks@{p1},{p2}: b_data(8)->(-23) clean")

# now the full 4-row SUM-MERGE truth table: sum=A^B must appear as a glider on -23
print("\nSUM-MERGE truth table (sum on the single lane -23):", flush=True)
allok = True
for A, B in [(1, 1), (1, 0), (0, 1), (0, 0)]:
    st = run(field(A, B, sh_cats), T)
    g23, rest = on_lane(st, (1, 1), -23)
    sm = 1 if g23 else 0
    clean = (rest == allc)
    ok = (sm == (A ^ B)) and clean; allok &= ok
    print(f"  A={A} B={B}: sum(on -23)={sm} want {A^B}  cats_restored={clean}  "
          f"{'OK' if ok else 'FAIL'}", flush=True)
print("\nSUM-MERGE:", "PASS" if allok else "FAIL", flush=True)
lap("done")
