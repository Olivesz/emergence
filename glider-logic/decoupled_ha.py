#!/usr/bin/env python3
"""Decoupled leg-2: a SECOND A-duplicator placed RIGHT, whose NW output (a_del2)
is born next to b_data and closes on it head-on. BOUNDED sims only (<=1600t)."""
import time
from life import run, bbox
from gadgets import (split_gliders, glider_dir, glider_lane, DIRNAME,
                     place_duplicator, dup_input_glider)
import gates
from routed import (build_variants, traj_params, se_ident,
                    delay_glider, bbox_gap, DEL7, _causal_outcome)

t0 = time.time()

# ---------- rebuild b_data exactly as ha_dev / build_rung4 does ----------
dupA = set(place_duplicator(0, 0)); a_in = set(dup_input_glider(0, 0, back=0))
gsA, _ = split_gliders(run(dupA | a_in, 800))
a_data = [g for g in gsA if glider_dir(g) == (1, 1)][0]
Xa, Ya, t0a = se_ident(a_data, 800)

ann = None
for (ox, oy, ph) in DEL7:
    if _causal_outcome(gates.glider('SE', 0, 0), gates.glider('NW', ox, oy, ph), 120) == []:
        ann = (ox, oy, ph); break
ox, oy, ph = ann

collide_x, dxB = 130, 150
w = collide_x - Xa
tgt = gates.glider('NW', Xa + w + ox, Ya + w + oy, ph); t_tgt = t0a + 4 * w
_, L_del, tau_t = traj_params(tgt, t_tgt)
dyB = dxB + (L_del + 47)
dupB = set(place_duplicator(dxB, dyB)); L_bd = (dyB - dxB) - 23
b_in = set(dup_input_glider(dxB, dyB, back=4))
def measureB(binp):
    s = dupB | set(binp)
    for t in range(0, 1600, 25):
        s = run(s, 25); gs2, rest2 = split_gliders(s)
        nw = [g for g in gs2 if glider_dir(g) == (-1, -1)]
        if rest2 == dupB and len(gs2) == 2 and nw:
            return traj_params(nw[0], t + 25)
    return None
got = measureB(b_in); delta = tau_t - got[2]
if delta < 0:
    dw = (-delta + 7) // 8 + 1; w += dw
    tgt = gates.glider('NW', Xa+w+ox, Ya+w+oy, ph); t_tgt = t0a+4*w
    _, _, tau_t = traj_params(tgt, t_tgt); delta = tau_t - got[2]
b_in = delay_glider(b_in, delta)
gsB, _ = split_gliders(run(dupB | set(b_in), 1200))
b_data = [g for g in gsB if glider_dir(g) == (1, 1)][0]
Xb, Yb, t0b = se_ident(b_data, 1200)

# what a NW deleter must satisfy to annihilate b_data head-on:
tgtdel = gates.glider('NW', Xb + ox, Yb + oy, ph)
_, L_nd, tau_need = traj_params(tgtdel, t0b)
print(f"b_data: lane {L_bd}, ident X={Xb} Y={Yb} t0={t0b}")
print(f"deleter needs: lane {L_nd}, tau {tau_need}  (born down-right of x={Xb})")

# ---------- decoupled leg-2: place dupA2 on the RIGHT ----------
# NW output lane of a duplicator at (px,py) is (py-px) - 47.  Set == L_nd.
#   px chosen so a_del2 is BORN right of b_data's meeting point (x ~ Xb).
def measure_del2(px, py, back=0, delay=0):
    d2 = set(place_duplicator(px, py))
    inp = set(dup_input_glider(px, py, back=back))
    if delay: inp = delay_glider(inp, delay)
    s = d2 | inp
    for t in range(0, 1600, 25):
        s = run(s, 25); gs, rest = split_gliders(s)
        nw = [g for g in gs if glider_dir(g) == (-1, -1)]
        if rest == d2 and len(gs) == 2 and nw:
            return d2, inp, traj_params(nw[0], t + 25)
    return d2, inp, None

# lock lane: py - px = L_nd + 47.  sweep px (birth x) on the right side.
best = None
for px in range(Xb + 10, Xb + 120, 8):
    py = px + (L_nd + 47)
    d2, inp, tr = measure_del2(px, py, back=0)
    if tr is None: continue
    d_, lane_, tau_ = tr
    if lane_ != L_nd:      # placement parity: nudge py by the lane error
        py += (L_nd - lane_); d2, inp, tr = measure_del2(px, py, back=0)
        if tr is None: continue
        d_, lane_, tau_ = tr
    if lane_ == L_nd:
        best = (px, py, tau_); break
if best is None:
    print("no right placement produced lane", L_nd); raise SystemExit
px, py, tau_have = best
print(f"dupA2 @ ({px},{py}) -> a_del2 lane {L_nd}, tau {tau_have}")

# tune input delay so tau matches tau_need (delaying input by d adds d to tau)
delay = tau_need - tau_have
print(f"input delay to match tau_need: {delay}")
d2 = set(place_duplicator(px, py))
inp = set(dup_input_glider(px, py, back=0))
if delay >= 0:
    inp = delay_glider(inp, delay)
else:
    print("NEGATIVE delay -> move dupA2 further right (later birth). retrying...")
    # push px right until tau_have <= tau_need
    while delay < 0:
        px += 8; py += 8
        _, _, tr = measure_del2(px, py, back=0)
        if tr is None: continue
        _, lane_, tau_have = tr
        if lane_ != L_nd:
            py += (L_nd - lane_); _, _, tr = measure_del2(px, py, back=0)
            if tr is None: continue
            _, lane_, tau_have = tr
        delay = tau_need - tau_have
    print(f"  -> dupA2 @ ({px},{py}), tau_have {tau_have}, delay {delay}")
    d2 = set(place_duplicator(px, py))
    inp = delay_glider(set(dup_input_glider(px, py, back=0)), delay)

# ---------- SWEEP input delay: does ANY timing annihilate b_data? ----------
d2 = set(place_duplicator(px, py))
base_inp = set(dup_input_glider(px, py, back=0))
hits = []
for dly in range(-600, 1400, 4):     # phase-4 glider; step 4 keeps phase, scan window
    inp = delay_glider(base_inp, dly) if dly >= 0 else base_inp  # (neg handled below)
    if dly < 0:
        # advance b_data instead (equivalent to launching A earlier)
        field = d2 | base_inp | set(delay_glider(set(b_data), -dly))
    else:
        field = d2 | inp | set(b_data)
    gs, rest = split_gliders(run(field, 1700))
    nw_surv = [g for g in gs if glider_dir(g) == (-1, -1)]
    se8 = [g for g in gs if glider_dir(g) == (1, 1) and glider_lane(g) == L_bd]
    if rest == d2 and not nw_surv and not se8:
        hits.append(dly)
print(f"\nannihilation delays (dupA2 input lead/lag) that PASS: {hits[:12]}"
      + (" ..." if len(hits) > 12 else ""))
print("LEG-2 DECOUPLED ACHIEVABLE:", "YES" if hits else "NO")
if hits:
    print(f"  -> works with input delay in a window around {hits[len(hits)//2]};"
          f" integration = give A that launch lead over B")
print("elapsed", round(time.time() - t0, 1), "s")
