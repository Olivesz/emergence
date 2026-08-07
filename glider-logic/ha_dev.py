#!/usr/bin/env python3
"""Scratch: design the XOR leg-2 reroute for the half-adder. BOUNDED sims only."""
import time
from life import run, translate, bbox
from gadgets import (split_gliders, glider_dir, glider_lane, DIRNAME,
                     place_duplicator, dup_input_glider)
import gates
from routed import (build_variants, traj_params, se_ident, backcast,
                    delay_glider, bbox_gap, DEL7, _causal_outcome)

t_start = time.time()
V = build_variants()

# ---- side A: duplicator at origin -> a_data (SE -23), a_del (NW -47) ----
dupA = set(place_duplicator(0, 0))
a_in = set(dup_input_glider(0, 0, back=0))
T1 = 800
gsA, restA = split_gliders(run(dupA | a_in, T1))
a_data = [g for g in gsA if glider_dir(g) == (1, 1)][0]
a_del  = [g for g in gsA if glider_dir(g) == (-1, -1)][0]
Xa, Ya, t0a = se_ident(a_data, T1)
print("a_data lane", glider_lane(a_data), "a_del lane", glider_lane(a_del))
d_ad, L_ad, tau_ad = traj_params(a_del, T1)
print("a_del traj:", DIRNAME[d_ad], "lane", L_ad, "tau", tau_ad)

# ---- pick causal delta=+7 annihilation ----
ann = None
for (ox, oy, ph) in DEL7:
    a = gates.glider('SE', 0, 0)
    b = gates.glider('NW', ox, oy, ph)
    if _causal_outcome(a, b, 120) == []:
        ann = (ox, oy, ph); break
ox, oy, ph = ann
print("ann", ann, "oy-ox", oy-ox)

# ---- side B geometry (mirror of build_rung4) ----
collide_x, dxB = 130, 150
w = collide_x - Xa
tgt = gates.glider('NW', Xa + w + ox, Ya + w + oy, ph)
t_tgt = t0a + 4 * w
d_t, L_del, tau_t = traj_params(tgt, t_tgt)
dyB = dxB + (L_del + 47)
dupB = set(place_duplicator(dxB, dyB))
L_bd = (dyB - dxB) - 23
b_in = set(dup_input_glider(dxB, dyB, back=4))
# measure B deleter tau to time b_in (as rung4 does)
def measureB(binp):
    s = dupB | set(binp)
    for t in range(0, 1600, 25):
        s = run(s, 25)
        gs2, rest2 = split_gliders(s)
        nw = [g for g in gs2 if glider_dir(g) == (-1, -1)]
        if rest2 == dupB and len(gs2) == 2 and nw:
            return traj_params(nw[0], t + 25)
    return None
got = measureB(b_in)
delta = tau_t - got[2]
if delta < 0:
    dw = (-delta + 7)//8 + 1; w += dw
    tgt = gates.glider('NW', Xa+w+ox, Ya+w+oy, ph); t_tgt = t0a+4*w
    _,_,tau_t = traj_params(tgt, t_tgt); delta = tau_t - got[2]
b_in = delay_glider(b_in, delta)

# b_data: the SE survivor of dupB (leg-2 data carrier)
gsB, restB = split_gliders(run(dupB | set(b_in), 1200))
b_data = [g for g in gsB if glider_dir(g) == (1, 1)][0]
print("b_data lane", glider_lane(b_data), "L_bd", L_bd)
d_bd, L_bd2, tau_bd = traj_params(b_data, 1200)
print("b_data traj:", DIRNAME[d_bd], "lane", L_bd2, "tau", tau_bd)

# target for A's deleter to annihilate b_data (ANN head-on): NW deleter must
# ride lane L_bd + (oy-ox), meeting b_data ph0 at offset (ox,oy).
L_target = L_bd + (oy - ox)
print("L_target (A_del reroute must land NW here):", L_target)

# ---- get a clean standalone a_del glider near the origin ----
s = dupA | a_in
for t in range(0, 400, 20):
    s2 = run(s, 20)
    gs, rest = split_gliders(s2); s = s2
    nw = [g for g in gs if glider_dir(g) == (-1, -1)]
    if rest == dupA and len(gs) == 2 and nw and bbox_gap(nw[0], dupA) >= 6:
        gd = set(nw[0]); Tgd = t + 20; break
print("clean a_del at t", Tgd, "lane", glider_lane(gd), "bbox", bbox(gd))

def lane_place_ymx(v, L, dx):   # incoming ymx beam lane L; returns (dx,dy)
    return dx, dx + (L - v.lin)
def lane_place_xpy(v, L, dx):   # incoming xpy beam lane L
    return dx, (L - v.lin) - dx

def try_reroute(dx1, dx2, dx3, Tmax=4000):
    S1, S2, S3, S4 = V['snark_m0r3'], V['snark_m0r0'], V['snark_m0r1'], V['snark_m0r2']
    p1 = lane_place_ymx(S1, -47, dx1)
    O1 = S1.lout + (p1[0] + p1[1])
    p2 = lane_place_xpy(S2, O1, dx2)
    O2 = S2.lout + (p2[1] - p2[0])
    p3 = lane_place_ymx(S3, O2, dx3)
    O3 = S3.lout + (p3[0] + p3[1])
    num = S4.lout + O3 - S4.lin - 15
    if num % 2:
        return None, f"dx4 parity fail (num={num})"
    dx4 = num // 2
    p4 = lane_place_xpy(S4, O3, dx4)
    O4 = S4.lout + (p4[1] - p4[0])
    cats = [S1.place(*p1), S2.place(*p2), S3.place(*p3), S4.place(*p4)]
    # clearance among catalysts
    for i in range(4):
        for j in range(i+1, 4):
            if bbox_gap(cats[i], cats[j]) < 4:
                return None, f"snarks {i},{j} overlap gap={bbox_gap(cats[i],cats[j])}"
    field = set(gd)
    for c in cats: field |= c
    catU = set().union(*cats)
    res = run(field, Tmax)
    gs, rest = split_gliders(res)
    info = dict(O1=O1, O2=O2, O3=O3, O4=O4, p=(p1,p2,p3,p4))
    if len(gs) == 1 and rest == catU:
        d,l,tau = traj_params(gs[0], Tgd + Tmax)
        info.update(out=(DIRNAME[d], l, tau), bbox=bbox(gs[0]), clean=True)
    else:
        info.update(out=None, clean=False, ngs=len(gs),
                    residue_extra=len(rest - catU))
    return info, "ok"

info, msg = try_reroute(-40, 40, 150)
print("reroute:", msg, "out", info.get('out'), "bbox", info.get('bbox'))

# ---- required deleter tau to annihilate b_data via ANN ----
Xb, Yb, t0b = se_ident(b_data, 1200)
tgtdel = gates.glider('NW', Xb + ox, Yb + oy, ph)
d_nd, L_nd, tau_need = traj_params(tgtdel, t0b)
print("b_data ident X,Y,t0", Xb, Yb, t0b, "| deleter need lane", L_nd, "tau_need", tau_need)

# ---- full reroute builder returning field pieces (delay-tunable) ----
def build_reroute(dx1, dx2, dx3, delay):
    S1,S2,S3,S4 = V['snark_m0r3'],V['snark_m0r0'],V['snark_m0r1'],V['snark_m0r2']
    p1 = lane_place_ymx(S1,-47,dx1); O1 = S1.lout+(p1[0]+p1[1])
    p2 = lane_place_xpy(S2,O1,dx2);  O2 = S2.lout+(p2[1]-p2[0])
    p3 = lane_place_ymx(S3,O2,dx3);  O3 = S3.lout+(p3[0]+p3[1])
    num = S4.lout+O3-S4.lin-15
    if num % 2: return None
    dx4 = num//2; p4 = lane_place_xpy(S4,O3,dx4)
    cats = [S1.place(*p1),S2.place(*p2),S3.place(*p3),S4.place(*p4)]
    catU = set().union(*cats)
    gdd = delay_glider(gd, delay)
    return catU, gdd, (p1,p2,p3,p4)

# baseline output tau with delay=0 was info['out'][2]; delaying input by d -> tau+d
base_tau = info['out'][2]
delay = tau_need - base_tau
print("delay to match tau:", delay)
def gx(g): return bbox(g)[0]
# where does the physical deleter's loop turn around (max x = S4 emission)?
for dx3 in (150, 400):
    inf,_ = try_reroute(-40,40,dx3, Tmax=1)   # just to get S4 pos analytically
    S4 = V['snark_m0r2']; p4 = inf['p'][3]
    print(f"dx3={dx3}: S4(last snark) at x~{p4[0]}, y~{p4[1]} "
          f"-> deleter max-x (turnaround) ~ {p4[0]}")

# race arithmetic: can the deleter reach x* ahead of b_data?
xstar = Xb + ox   # ANN deleter x at collision ~ b_data.x + 3
tstar = t0b       # b_data is at Xb at t0b
# a_del born near origin:
print(f"\nRACE: b_data ANN point x*~{xstar} at t*~{tstar}")
print(f"  a_del born x~{gx(gd)} at t~{Tgd}")
straight = Tgd + 4*(xstar - gx(gd))
print(f"  earliest a_del could reach x={xstar} going STRAIGHT SE: t~{straight}"
      f"  (b_data passes x={xstar} at t~{tstar})")
print(f"  deficit: a_del arrives {straight - tstar} ticks AFTER b_data is gone;"
      f" head-on needs it there EARLIER -> unreachable")

# min-distance witness with the tau-matched small loop
catU, gdd, ps = build_reroute(-40,40,150, delay)
field = set(catU) | set(gdd) | set(b_data)
mind = 1e9; s = set(field)
for _ in range(0, 3600, 30):
    s = run(s, 30)
    gsr, rest = split_gliders(s)
    dd = [g for g in gsr if glider_dir(g)==(-1,-1)]
    bb = [g for g in gsr if glider_dir(g)==(1,1)]
    if dd and bb:
        mind = min(mind, bbox_gap(dd[0], bb[0]))
gsr,rest = split_gliders(run(field, 3600))
print(f"\nmin bbox-gap deleter<->b_data over flight: {mind} "
      f"(annihilation would need ~0); survivors="
      f"{[(DIRNAME[glider_dir(g)],glider_lane(g)) for g in gsr]}")
print("elapsed", round(time.time()-t_start,1), "s")
