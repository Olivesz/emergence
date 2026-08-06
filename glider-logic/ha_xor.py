#!/usr/bin/env python3
"""Integrated routed XOR (half-adder SUM): leg-1 (Rung 4, untouched) + decoupled
leg-2 (a second A-duplicator on the right whose NW deleter kills b_data, tuned to
the exact clean DEL7 offset, with its own guard eater). SUM = an SE glider on
lane -23 (a_data survives) or lane L_bd (b_data survives). Raw B3/S23; every
catalyst must be restored exactly. BOUNDED sims only."""
import time
from life import run, translate, normalize, bbox, EATER
from gadgets import (split_gliders, glider_dir, glider_lane, DIRNAME,
                     place_duplicator, dup_input_glider)
import gates
from routed import (build_variants, build_rung4, traj_params, se_ident,
                    delay_glider, bbox_gap, mirror, rot90)

t0 = time.time()
def lap(msg): print(f"[{time.time()-t0:6.1f}s] {msg}", flush=True)
V = build_variants(); lap("built variants")
cfg = build_rung4(V)                       # leg-1: dupA, dupB, guard-eater, a_in, b_in
assert cfg, "rung4 failed"
lap(f"rung4 done (t_tgt={cfg['t_tgt']})")
cats1 = cfg['cats']; a_in = cfg['a_in']; b_in = cfg['b_in']; L_bd = cfg['L_bd']
ox, oy, ph = cfg['ann']
T = cfg['t_tgt'] + 1800
print(f"leg-1 ready: sum rails SE -23 (a_data) & SE {L_bd} (b_data); ann offset ({ox},{oy}) ph {ph}")

# ---- decoupled leg-2: a second A-duplicator on the RIGHT.  Its NW deleter (a_del2)
#      rides the lane exactly (oy-ox) above b_data, so ANY crossing already sits at the
#      DEL7 offset; only the crossing PHASE need be tuned, via a small input delay.
L_a2 = L_bd + (oy - ox)                      # 8 + 7 = 15
pxA2 = 444; pyA2 = pxA2 + (L_a2 + 47)
dupA2 = set(place_duplicator(pxA2, pyA2))
assert bbox_gap(dupA2, cats1) >= 6, f"dupA2 collides with leg-1 (gap {bbox_gap(dupA2, cats1)})"
a2_base = set(dup_input_glider(pxA2, pyA2, back=0))
dupB = set(place_duplicator(*cfg['dupB_at']))
Tiso = cfg['t_tgt'] + 1200

# frame-exact isolated field (both duplicators from t=0) -> the a_del2/b_data timing
# is identical to the full circuit.  Sweep input delay for a CLEAN kill.
def leg2_run(D):
    a2 = delay_glider(a2_base, D)
    if a2 & (dupA2 | dupB): return None
    return split_gliders(run(dupA2 | dupB | a2 | b_in, Tiso))
def is_clean(gsr):
    gs, rest = gsr
    se8 = any(glider_dir(g) == (1, 1) and glider_lane(g) == L_bd for g in gs)
    nw15 = any(glider_dir(g) == (-1, -1) and glider_lane(g) == L_a2 for g in gs)
    return (not se8) and (not nw15) and (rest == dupA2 | dupB)
bestD = next((D for D in range(0, 40, 2) if (r := leg2_run(D)) and is_clean(r)), None)
assert bestD is not None, "no clean leg-2 delay in 0..40"
a2_in = delay_glider(a2_base, bestD)
lap(f"leg-2 clean kill at input delay {bestD}")

# where does the kill land? (for parking the guard eater just left of it)
def kill_x():
    s = dupA2 | dupB | set(a2_in) | b_in; last = None; seen = False
    for _ in range(0, Tiso, 40):
        s = run(s, 40); gs, _ = split_gliders(s)
        bd = [g for g in gs if glider_dir(g) == (1, 1) and glider_lane(g) == L_bd]
        if bd:
            seen = True; last = bbox(bd[0])[0]
        elif seen:
            break                              # b_data appeared, now gone -> died here
    return last if last is not None else pxA2
kx = kill_x()
PARK = 2 * (kx - 60) + L_a2                   # eater on lane L_a2, ~60 left of the kill
lap(f"kill lands at x~{kx}; parking guard eater at x+y~{PARK}")

# ---- guard eater for a_del2 (swallow it when B=0) on lane L_a2 ----
# Tested IN CONTEXT: let dupA2 emit a_del2 naturally, require the eater to swallow it
# and every catalyst restored (only the a_data2 spare on lane 39 flies off).
g0 = gates.glider('NW', 0, 0, ph)
cands = []
for m in range(2):
    Em = mirror(set(EATER)) if m else set(EATER)
    for r in range(4):
        Eo = frozenset(normalize(Em)); seen = set()
        for ex in range(-28, 6):
            for ey in range(-28, 6):
                Et = translate(Eo, ex, ey)
                if (Et & g0) or run(g0 | Et, 200) != Et:
                    continue
                if (ey - ex) not in seen:
                    seen.add(ey - ex); cands.append((Eo, ex, ey))
        Em = rot90(Em)
rx0 = (PARK - L_a2) // 2; ry0 = rx0 + L_a2
eater2 = None
for (Eo, ex, ey) in cands:
    for ss in range(-16, 16):                 # slide along the anti-diagonal
        E = translate(Eo, rx0 + ss + ex, ry0 + ss + ey)
        if E & (cats1 | dupA2 | set(a2_in)):   # no cell overlap with any catalyst/input
            continue
        gs2, rest2 = split_gliders(run(dupA2 | set(a2_in) | E, Tiso))
        nw15 = any(glider_dir(g) == (-1, -1) and glider_lane(g) == L_a2 for g in gs2)
        if rest2 == (dupA2 | E) and not nw15:
            eater2 = E; break
    if eater2:
        break
assert eater2, "no guard eater for a_del2"
cats = cats1 | dupA2 | eater2
lap("guard eater placed")

# ---- 4-row XOR truth table: RIGOROUS (catalysts restored + exact survivors) ----
SUM = {-23, L_bd}
def survivors(state):
    gs, rest = split_gliders(state)
    return sorted((DIRNAME[glider_dir(g)], glider_lane(g)) for g in gs), rest
# a_data SE-23 & a_del NW-47 (dupA); b_data SE L_bd (dupB); a_data2 SE39 (dupA2 spare)
L_a2data = (pyA2 - pxA2) - 23
exp = {
    (1, 1): [('NW', -47), ('SE', L_a2data)],                 # both data killed; two spares
    (1, 0): [('NW', -47), ('SE', -23), ('SE', L_a2data)],    # a_del2 eaten; A's copies sail
    (0, 1): [('SE', L_bd)],                                   # b_data sails; b_del eaten
    (0, 0): [],
}
rows = [(1, 1, 0), (1, 0, 1), (0, 1, 1), (0, 0, 0)]
allok = True
for A, B, want in rows:
    init = set(cats)
    if A: init |= set(a_in) | set(a2_in)
    if B: init |= set(b_in)
    surv, rest = survivors(run(init, T))
    lanes = [l for (d, l) in surv if d == 'SE' and l in SUM]
    got = 1 if lanes else 0
    clean = (rest == cats); exact = (surv == sorted(exp[(A, B)]))
    ok = (got == want) and clean and exact; allok &= ok
    print(f"[{time.time()-t0:6.1f}s]  A={A} B={B}: sum={got}(want {want}) "
          f"cats_restored={clean} exact={exact} survivors={surv} {'OK' if ok else 'FAIL'}",
          flush=True)
    if not clean:
        ext = rest - cats
        print(f"      residue +{len(ext)} bbox={bbox(ext) if ext else None} -{len(cats-rest)}")
print("\nROUTED XOR (half-adder SUM) — raw-rule, catalysts restored:",
      "PASS" if allok else "FAIL")
print("elapsed", round(time.time() - t0, 1), "s")
