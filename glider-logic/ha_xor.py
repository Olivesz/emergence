#!/usr/bin/env python3
"""Physically-routed XOR = the half-adder SUM, in raw Conway's Life.

leg-1 (Rung 4, untouched) + a DECOUPLED leg-2: a second A-duplicator on the RIGHT
whose NW deleter is born next to b_data and closes on it (kills the spatial race),
tuned to the exact clean DEL7 offset (no still-life debris), with its own guard
eater for the B=0 case.  The two legs ride SEPARATE A-copies, so leg-1 is untouched.

SUM = an SE glider on lane -23 (a_data survives, A only) or lane L_bd (b_data
survives, B only).  Verified raw B3/S23: every catalyst restored, exact survivors.

`build_routed_xor(V)` returns the circuit (reused by the full half-adder / adder);
running this file verifies the 4-row truth table.  BOUNDED sims only."""
import time
from life import run, translate, normalize, bbox, EATER
from gadgets import (split_gliders, glider_dir, glider_lane, DIRNAME,
                     place_duplicator, dup_input_glider)
import gates
from routed import (build_variants, build_rung4, traj_params, se_ident,
                    delay_glider, bbox_gap, mirror, rot90)


def build_routed_xor(V, lap=lambda m: None):
    cfg = build_rung4(V)                        # leg-1: dupA, dupB, guard-eater, a_in, b_in
    assert cfg, "rung4 failed"
    lap(f"rung4 done (t_tgt={cfg['t_tgt']})")
    cats1 = cfg['cats']; a_in = cfg['a_in']; b_in = cfg['b_in']; L_bd = cfg['L_bd']
    ox, oy, ph = cfg['ann']

    # ---- decoupled leg-2: a second A-duplicator on the RIGHT.  Its NW deleter
    # rides the lane exactly (oy-ox) above b_data, so any crossing already sits at
    # the DEL7 offset; only the crossing PHASE need be tuned, via a small delay.
    L_a2 = L_bd + (oy - ox)
    pxA2 = 444; pyA2 = pxA2 + (L_a2 + 47)
    dupA2 = set(place_duplicator(pxA2, pyA2))
    assert bbox_gap(dupA2, cats1) >= 6, f"dupA2 collides with leg-1 (gap {bbox_gap(dupA2, cats1)})"
    a2_base = set(dup_input_glider(pxA2, pyA2, back=0))
    dupB = set(place_duplicator(*cfg['dupB_at']))
    Tiso = cfg['t_tgt'] + 1200

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

    def kill_x():                               # where the kill lands (to park the eater)
        s = dupA2 | dupB | set(a2_in) | b_in; last = None; seen = False
        for _ in range(0, Tiso, 40):
            s = run(s, 40); gs, _ = split_gliders(s)
            bd = [g for g in gs if glider_dir(g) == (1, 1) and glider_lane(g) == L_bd]
            if bd:
                seen = True; last = bbox(bd[0])[0]
            elif seen:
                break
        return last if last is not None else pxA2
    PARK = 2 * (kill_x() - 60) + L_a2

    # ---- guard eater for a_del2 (B=0 case), tested IN CONTEXT ----
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
        for ss in range(-16, 16):
            E = translate(Eo, rx0 + ss + ex, ry0 + ss + ey)
            if E & (cats1 | dupA2 | set(a2_in)):
                continue
            gs2, rest2 = split_gliders(run(dupA2 | set(a2_in) | E, Tiso))
            nw15 = any(glider_dir(g) == (-1, -1) and glider_lane(g) == L_a2 for g in gs2)
            if rest2 == (dupA2 | E) and not nw15:
                eater2 = E; break
        if eater2:
            break
    assert eater2, "no guard eater for a_del2"
    lap("guard eater placed")

    cats = cats1 | dupA2 | eater2
    L_a2data = (pyA2 - pxA2) - 23               # 39, the spare that flies off
    exp = {                                     # full survivor multiset per row
        (1, 1): [('NW', -47), ('SE', L_a2data)],
        (1, 0): [('NW', -47), ('SE', -23), ('SE', L_a2data)],
        (0, 1): [('SE', L_bd)],
        (0, 0): [],
    }
    return dict(cats=cats, a_in=a_in, a2_in=a2_in, b_in=b_in, L_bd=L_bd,
                sum_lanes={-23, L_bd}, t_tgt=cfg['t_tgt'], exp=exp)


def main():
    t0 = time.time()
    def lap(m): print(f"[{time.time()-t0:6.1f}s] {m}", flush=True)
    V = build_variants(); lap("built variants")
    x = build_routed_xor(V, lap)
    cats, a_in, a2_in, b_in = x['cats'], x['a_in'], x['a2_in'], x['b_in']
    SUM, exp = x['sum_lanes'], x['exp']; T = x['t_tgt'] + 1800
    def survivors(state):
        gs, rest = split_gliders(state)
        return sorted((DIRNAME[glider_dir(g)], glider_lane(g)) for g in gs), rest
    allok = True
    for A, B, want in [(1, 1, 0), (1, 0, 1), (0, 1, 1), (0, 0, 0)]:
        init = set(cats)
        if A: init |= set(a_in) | set(a2_in)
        if B: init |= set(b_in)
        surv, rest = survivors(run(init, T))
        got = 1 if [l for (d, l) in surv if d == 'SE' and l in SUM] else 0
        clean = (rest == cats); exact = (surv == sorted(exp[(A, B)]))
        ok = (got == want) and clean and exact; allok &= ok
        print(f"[{time.time()-t0:6.1f}s]  A={A} B={B}: sum={got}(want {want}) "
              f"cats_restored={clean} exact={exact} survivors={surv} {'OK' if ok else 'FAIL'}",
              flush=True)
    print("\nROUTED XOR (half-adder SUM) — raw-rule, catalysts restored:",
          "PASS" if allok else "FAIL")
    return allok


if __name__ == "__main__":
    main()
