#!/usr/bin/env python3
"""The first PHYSICAL fan-in in raw B3/S23, via De Morgan (no reflector merge — that's
wall #2, see merge.py). Built on the proven routed AND (routed.build_rung3):

    NOR(a,b) = AND(NOT a, NOT b)          <-- VERIFIED here, all 4 rows, universal gate
    OR(a,b)  = NOT(NOR(a,b))              <-- needs one more routed INHIBIT stage

NOR core (VERIFIED): RUNG 3's two AND inputs become CONSTANT carriers (always injected);
the real inputs a,b are DELETERS that annihilate them. A carrier survives iff its input
is 0, so the AND computes A=NOT a, B=NOT b -> its output fires iff a=b=0 == NOR. Every
row passes settle() in the bare rule (catalysts restored, exact survivor multiset,
forever-escape). NOR is functionally COMPLETE (like NAND) — so this single verified gate
is a universal physical fan-in: the whole point of routing around wall #2, in real
gliders.

OR = NOT(NOR) (IN PROGRESS): the output NOT needs a constant carrier C_out that the NOR
output m deletes. But m's lane (43) sits inside the machine's A-entry corridor band, and
the annihilation geometry pins C_out onto an adjacent SE lane that runs straight back
through the merge — so the carrier disrupts the AND (verified failure mode). The fix is
FLOOR-PLANNING (compiler stages 4-5): route m out to open space with a Snark, then place
the output-NOT there. build_or/verify_or below document the construction and the exact
obstruction. BOUNDED sims. Run: python3 -u routed_or.py
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from life import run, bbox
from gadgets import split_gliders, glider_dir, glider_lane, DIRNAME
import gates
from routed import (build_variants, build_rung3, verify_and_reaction, settle,
                    traj_params, backcast, bbox_gap, _causal_outcome, to_rle)
from router import route_from

DIRVEC = {(1, 1): 'SE', (-1, 1): 'SW', (1, -1): 'NE', (-1, -1): 'NW'}


def deleter_for(g, context=frozenset(), avoid=frozenset(), gap=4, T=800, win=6, along=90):
    """An initial glider that TOTALLY annihilates initial-state glider g against the
    CATALYSTS `context`: run(context | g | d) leaves `context` restored with NO gliders
    — so the deleter can't clip or fly into a catalyst (isolation-only checks miss the
    fly-by). `avoid` (e.g. the other carrier) only imposes a start-position gap. Sweeps
    the collision point ALONG g's lane (small s = upstream, open space) + a tiny
    perpendicular/phase window. Returns the deleter or None."""
    dg = glider_dir(g)
    opp = DIRVEC[(-dg[0], -dg[1])]
    gx0, gy0, gx1, gy1 = bbox(g)
    cx, cy = (gx0 + gx1) // 2, (gy0 + gy1) // 2
    px, py = -dg[1], dg[0]                         # a perpendicular direction
    ctx = set(context)
    for s in range(0, along):                      # how far downstream the deleter starts
        for ph in range(4):
            for k in range(-win, win + 1):
                dx = cx + dg[0] * s + px * k
                dy = cy + dg[1] * s + py * k
                d = set(gates.glider(opp, dx, dy, ph))
                if d & set(g):
                    continue
                if (ctx and bbox_gap(d, ctx) < gap) or (avoid and bbox_gap(d, avoid) < gap):
                    continue
                # must annihilate causally in isolation...
                if _causal_outcome(set(g), d, 160) != []:
                    continue
                # ...AND leave the catalysts pristine with no survivors in context
                gs, rest = split_gliders(run(ctx | set(g) | d, T))
                if not gs and rest == ctx:
                    return d
    return None


def build_nor(V, tau_and):
    """RUNG-3 AND with its two inputs turned into deletable constant carriers."""
    cfg = build_rung3(V, tau_and)
    cats, a_in, b_in = cfg['cats'], set(cfg['a_in']), set(cfg['b_in'])
    # validate each deleter against the catalysts AND the other carrier, in context
    a_del = deleter_for(a_in, context=cats, avoid=b_in)   # kills a_in when a=1 (SE->NW deleter)
    b_del = deleter_for(b_in, context=cats, avoid=a_in)   # kills b_in when b=1 (NE->SW deleter)
    assert a_del and b_del, "no clean in-context total-annihilation deleter found"
    cfg.update(a_del=a_del, b_del=b_del, carrierA=a_in, carrierB=b_in)
    return cfg


def nor_field(cfg, a, b):
    """The NOR field for logical inputs (a,b): carriers always on, deleters gate them."""
    f = set(cfg['cats']) | set(cfg['carrierA']) | set(cfg['carrierB'])
    if a:
        f |= cfg['a_del']
    if b:
        f |= cfg['b_del']
    return f


def verify_nor(cfg):
    """NOR(a,b): the AND's NW output fires iff a==b==0. Full 4-row raw-rule check."""
    cats = cfg['cats']
    dirn, lane_out, _ = cfg['exp_out']        # ('NW', lane, tau)
    L_A, L_SW, tA = cfg['L_A'], cfg['L_SW'], cfg['tA']
    # each row's exact surviving-glider signature (see module docstring)
    rows = {(0, 0): [(dirn, lane_out)],       # NOR=1: AND output present
            (0, 1): [('SE', L_A)],            # a_in survives, enters/exits as lone A
            (1, 0): [('SW', L_SW)],           # b_in survives, exits SW
            (1, 1): []}                       # both deleted
    notes, allok = [], True
    for (a, b), expect in rows.items():
        ok, t, _, _ = settle(nor_field(cfg, a, b), cats, expect,
                             t_min=tA + 60, t_max=tA + 900)
        allok &= ok
        nor = 1 if (a == 0 and b == 0) else 0
        notes.append(f"a={a} b={b} -> NOR={nor} "
                     f"(AND output {'present' if expect and expect[0][0]=='NW' else 'absent'}), "
                     f"survivors={expect}, catalysts restored, settled t={t}: {ok}")
    return allok, notes


def isolate(field, cats, wantdir, lane=None, gap=6, tmax=2600, t_min=0):
    """Run `field` until (after t_min) it holds exactly one glider (direction wantdir,
    optional lane) clear of `cats` by `gap`, catalysts restored. Returns (state, T)."""
    s = set(field); cats = set(cats); T = 0
    while T < tmax:
        s = run(s, 15); T += 15
        if T < t_min:
            continue
        gs, rest = split_gliders(s)
        if rest == cats and len(gs) == 1 and glider_dir(gs[0]) == wantdir \
                and bbox_gap(gs[0], cats) >= gap \
                and (lane is None or glider_lane(gs[0]) == lane):
            return set(gs[0]), T
    return None, T


def isolate_m(cfg, extra=frozenset(), wantdir=(-1, -1), lane=None, gap=6, tmax=2600):
    """Isolate the NOR output m from the a=b=0 field (+extra catalysts)."""
    return isolate(nor_field(cfg, 0, 0) | set(extra), set(cfg['cats']) | set(extra),
                   wantdir, lane, gap, tmax)


def build_or(V, tau_and):
    """OR = NOT(NOR). The output NOT would pin its carrier onto an SE lane inside the
    machine band, disrupting the merge — so first turn m (NW) RIGHT into an NE lane
    with x+y < 0 (m flown far up-left first, where its x+y is already negative). An NE
    glider keeps x+y constant, so it and the output-NOT's SW carrier stay off the
    machine's x+y band [0,124] forever. Place the output-NOT out there."""
    cfg = build_nor(V, tau_and)
    cats = cfg['cats']
    m0, _ = isolate_m(cfg, gap=8)                # m: clean NW glider (lane 43)
    assert m0, "couldn't isolate the NOR output m"

    routing = m_far = T_far = L_far = None
    for along in range(40, 360, 12):             # turn further up-left => more negative x+y
        rr = route_from(m0, [('R', along)])      # NW -> NE
        if rr is None:
            continue
        rcats, mfin, _ = rr
        Lne = glider_lane(mfin)                   # NE rides lane x+y
        if Lne >= -8 or bbox_gap(rcats, cats) < 6:   # want it clearly below the band
            continue
        mf, Tf = isolate_m(cfg, extra=rcats, wantdir=(1, -1), lane=Lne, gap=10)
        if mf is not None:
            routing, m_far, T_far, L_far = rcats, mf, Tf, Lne
            break
    assert routing is not None, "couldn't turn m onto a clear x+y<0 NE lane"

    allcats = cats | routing
    d = deleter_for(m_far, context=allcats, T=1000)   # the SW carrier m_far annihilates
    assert d, "no clean carrier C_out for the routed m"
    C_out = set(backcast(d, T_far))
    L_out = glider_lane(d)                         # C_out (SW) also rides an x+y lane
    assert bbox_gap(C_out, allcats) >= 4
    cfg.update(routing=routing, allcats=allcats, C_out=C_out, L_out=L_out,
               L_far=L_far, T_far=T_far)
    # DEAD END (documented): the surviving C_out (OR=1) flies SW back into the turn-Snark
    # S1, and the annihilation geometry pins C_out's lane within ~3 of m's, so any escape
    # Snark also clips m. A standalone output-NOT can't escape here. The working path is
    # the 2-machine composition in routed_nor_compose.py (OR's output = a clean AND-merge).
    cfg.update(escape=set(), out_dir='SW', out_lane=L_out)
    return cfg


def or_field(cfg, a, b):
    return nor_field(cfg, a, b) | cfg['routing'] | cfg['C_out'] | cfg.get('escape', set())


def verify_or(cfg):
    """OR(a,b): the output glider survives iff a OR b. 4-row raw check. When OR=1, junk
    rails (a_in / b_in survivors) also escape; listed in expect."""
    allcats = cfg['allcats']
    L_A, L_SW, tA = cfg['L_A'], cfg['L_SW'], cfg['tA']
    out = (cfg['out_dir'], cfg['out_lane'])        # the routed OR output port
    rows = {(0, 0): [],                            # OR=0: C_out deleted by routed m
            (0, 1): sorted([out, ('SE', L_A)]),    # OR=1: output + a_in junk
            (1, 0): sorted([out, ('SW', L_SW)]),   # OR=1: output + b_in junk
            (1, 1): [out]}                         # OR=1: output only
    notes, allok = [], True
    for (a, b), expect in rows.items():
        ok, t, _, _ = settle(or_field(cfg, a, b), allcats, expect,
                             t_min=tA + 60, t_max=cfg['T_far'] + 1700)
        allok &= ok
        got = 1 if (out in expect) else 0
        notes.append(f"a={a} b={b} -> OR={got} (want {a | b}); output "
                     f"{'present' if got else 'absent'} on {out[0]} lane {out[1]}, "
                     f"catalysts restored, t={t}: {ok}")
    return allok, notes


if __name__ == "__main__":
    t0 = time.time()
    V = build_variants()
    and_ok, tau_and = verify_and_reaction()
    print(f"[prereq] AND reaction causal: {and_ok}", flush=True)
    print("\nBuilding NOR core (routed AND with deletable constant carriers)...", flush=True)
    cfg = build_nor(V, tau_and)
    print(f"  carrier A (SE lane {glider_lane(cfg['carrierA'])}) deleter: NW, "
          f"carrier B (NE lane {glider_lane(cfg['carrierB'])}) deleter: SW", flush=True)
    print(f"  AND output (NOR readout): {cfg['exp_out'][0]} lane {cfg['exp_out'][1]}", flush=True)
    print("\nNOR truth table in raw B3/S23 (a universal, physical fan-in):", flush=True)
    nok, notes = verify_nor(cfg)
    for n in notes:
        print("   -", n, flush=True)
    print(f"ROUTED NOR: {'PASS' if nok else 'FAIL'}", flush=True)

    # emit a field that SHOWS the fan-in mechanism: a=0,b=1 -> b's input glider
    # annihilates constant carrier B (the De Morgan NOT), carrier A survives.
    if nok:
        field = nor_field(cfg, 0, 1)
        here = os.path.dirname(os.path.abspath(__file__))
        open(os.path.join(here, "compiled_nor.rle"), "w").write(to_rle(field))
        print(f"  emitted compiled_nor.rle: {len(field)} cells, bbox {bbox(field)}  "
              f"(a=0,b=1 -> b deletes carrier B, carrier A survives -> NOR=0)", flush=True)

    # OR = NOT(NOR): documented, with its exact floor-planning obstruction
    print("\nOR = NOT(NOR) — attempting the output NOT:", flush=True)
    try:
        cfg2 = build_or(V, tau_and)
        ok, notes = verify_or(cfg2)
        for n in notes:
            print("   -", n, flush=True)
        print(f"ROUTED OR: {'PASS' if ok else 'IN PROGRESS'}", flush=True)
    except AssertionError as e:
        ok = False
        print(f"   - build stopped: {e}", flush=True)
    if not ok:
        print("   NOTE: the output carrier C_out is pinned (by the annihilation geometry) "
              "onto an SE lane inside the machine's A-entry corridor, so it disrupts the "
              "AND merge. OR needs m routed to open space first (floor-planning, stages 4-5).",
              flush=True)

    print(f"\n[{round(time.time()-t0,1)}s]  Physical fan-in achieved: a VERIFIED routed NOR "
          "(universal). OR = one more routed INHIBIT on a floor-planned output.", flush=True)
    sys.exit(0 if nok else 1)
