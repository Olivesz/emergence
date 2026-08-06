#!/usr/bin/env python3
"""Export the routed XOR (half-adder SUM) as RLE snapshots for the whole-circuit
viewer, so you can watch the physical gliders fire through it.  BOUNDED build."""
import time
from life import bbox
from routed import build_variants, to_rle
from ha_xor import build_routed_xor

t0 = time.time()
def lap(m): print(f"[{time.time()-t0:6.1f}s] {m}", flush=True)
V = build_variants(); lap("built variants")
x = build_routed_xor(V, lap)
cats, a_in, a2_in, b_in = x['cats'], x['a_in'], x['a2_in'], x['b_in']

def field(A, B):
    f = set(cats)
    if A: f |= set(a_in) | set(a2_in)
    if B: f |= set(b_in)
    return f

# A=1,B=0 -> sum=1: a_data escapes on lane -23 (you see the SUM glider fly out),
#                   B's deleter is swallowed by leg-1's guard eater.
# A=1,B=1 -> sum=0: both deleters fire, both data gliders annihilate (the full
#                   machinery active), carry would be produced by the AND stage.
for tag, (A, B) in [("10", (1, 0)), ("11", (1, 1)), ("01", (0, 1))]:
    f = field(A, B)
    fn = f"routed_xor_{tag}.rle"
    open(fn, "w").write(to_rle(f))
    lap(f"wrote {fn}: A={A} B={B}, {len(f)} cells, bbox {bbox(f)}")
print("done", flush=True)
