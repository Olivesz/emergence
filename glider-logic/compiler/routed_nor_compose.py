#!/usr/bin/env python3
"""OR as a 2-stage composition whose output ESCAPES FORWARD (a fresh AND-merge glider),
so it never flies back into its own hardware — the dead end the standalone output-NOT
hit (see routed_or.py).

    OR(a,b) = AND( NOT(NOR(a,b)), 1 )

Stage 1 (routed_or.build_or): NOR(a,b) -> m, m turned onto a clean x+y<0 NE lane.
Stage 2 (here): a constant SW carrier p is INHIBITED by m (present iff a=b=0), then
merged with a constant SE partner q via the AND reaction. When m is absent (a OR b),
p survives and p+q fuse into an NW output that flies off into empty space = OR=1. When
m is present, m kills p first, q sails on alone, no output = OR=0.

STATUS (honest): the forward-escape idea WORKS for the three OR=1 rows — p survives, p+q
fuse into a clean NW output that flies off into empty space (verified, catalysts restored).
The (0,0) row is the wall: m must kill p UPSTREAM of the p+q merge, but routing m out put
the turn-Snark right at the m-collision, leaving p no clean stretch to merge in. Pushing
the collision far up-lane to make room balloons the sim length (>300s per verify) — the
slow-verify credit-bomb pattern. This is the practical wall for HAND floor-planning: each
composed gate needs a deliberate, roomy floor-plan, which is exactly the compiler's
automated place/route/time (Tier 3), not something to hand-tune per gate. Run: python3 -u
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from life import run, bbox
from gadgets import split_gliders, glider_dir, glider_lane, DIRNAME
import gates
from routed import (build_variants, verify_and_reaction, settle, backcast,
                    bbox_gap, to_rle)
import routed_or as RO

DIRVEC = {(1, 1): 'SE', (-1, 1): 'SW', (1, -1): 'NE', (-1, -1): 'NW'}


def merge_partner(p, context, T=700, win=8, along=80):
    """Find a constant SE partner q that AND-merges with SW carrier p into ONE clean NW
    output, catalysts restored. Sweeps the merge point along p's lane + a small window."""
    dp = glider_dir(p)                              # p is SW = (-1, 1)
    px0, py0, px1, py1 = bbox(p)
    cx, cy = (px0 + px1) // 2, (py0 + py1) // 2
    perp = (-dp[1], dp[0])
    ctx = set(context)
    for s in range(0, along):                       # slide the meeting point down p's lane
        for ph in range(4):
            for k in range(-win, win + 1):
                qx = cx + dp[0] * s + perp[0] * k
                qy = cy + dp[1] * s + perp[1] * k
                q = set(gates.glider('SE', qx, qy, ph))
                if (q & set(p)) or (ctx and bbox_gap(q, ctx) < 5):
                    continue
                gs, rest = split_gliders(run(ctx | set(p) | q, T))
                if rest == ctx and len(gs) == 1 and glider_dir(gs[0]) == (-1, -1):
                    return q, (DIRNAME[(-1, -1)], glider_lane(gs[0]))
    return None, None


def build_or(V, tau_and):
    cfg = RO.build_or(V, tau_and)                   # NOR + m turned onto NE lane; C_out=p
    allcats, p = cfg['allcats'], cfg['C_out']       # p: constant SW carrier (annihilated by m)
    # In the m-absent field, p survives — grab it DOWNSTREAM of the m-collision (t_min >
    # T_far) so that when m IS present it kills p before the merge point, still clear of
    # the turn-Snark, then find q that fuses with it into an NW output.
    pf, Tp = RO.isolate(RO.nor_field(cfg, 1, 1) | cfg['routing'] | p, allcats,
                        wantdir=(-1, 1), lane=cfg['L_out'], gap=8,
                        t_min=cfg['T_far'] + 20, tmax=cfg['T_far'] + 500)
    assert pf is not None, "couldn't isolate the surviving carrier p downstream of m"
    q, outport = merge_partner(pf, allcats)
    assert q is not None, "no AND-merge partner q for the surviving carrier"
    cfg.update(q=set(backcast(set(q), Tp)), out=outport)   # constant q, present from t=0
    return cfg


def or_field(cfg, a, b):
    return RO.or_field(cfg, a, b) | cfg['q']


def verify_or(cfg):
    allcats = cfg['allcats']
    L_A, L_SW, tA = cfg['L_A'], cfg['L_SW'], cfg['tA']
    out = cfg['out']                                 # ('NW', lane) the AND-merge OR output
    q_sw = ('SW', glider_lane(cfg['C_out']))          # when OR=0, q sails on alone (SW)
    rows = {(0, 0): [q_sw],                          # m kills p; q alone; no OR output
            (0, 1): sorted([out, ('SE', L_A)]),      # OR=1: merge output + a_in junk
            (1, 0): sorted([out, ('SW', L_SW)]),     # OR=1: merge output + b_in junk
            (1, 1): [out]}                           # OR=1: merge output only
    notes, allok = [], True
    for (a, b), expect in rows.items():
        ok, t, _, _ = settle(or_field(cfg, a, b), allcats, expect,
                             t_min=tA + 60, t_max=cfg['T_far'] + 1800)
        allok &= ok
        got = 1 if (out in expect) else 0
        notes.append(f"a={a} b={b} -> OR={got} (want {a | b}); output "
                     f"{'present' if got else 'absent'} on {out[0]} lane {out[1]}, "
                     f"catalysts restored, t={t}: {ok}")
    return allok, notes


if __name__ == "__main__":
    t0 = time.time()
    V = build_variants()
    _, tau = verify_and_reaction()
    print("Building composed OR = AND(NOT(NOR(a,b)), 1) ...", flush=True)
    cfg = build_or(V, tau)
    print(f"  NOR output m -> NE lane {cfg['L_far']}; surviving carrier p (SW lane "
          f"{cfg['L_out']}) merged with q -> OR output {cfg['out']}", flush=True)
    print("\nOR truth table in raw B3/S23:", flush=True)
    ok, notes = verify_or(cfg)
    for n in notes:
        print("   -", n, flush=True)
    print(f"\nROUTED OR (first physical fan-in gate, forward-escaping output): "
          f"{'PASS' if ok else 'FAIL'}  ({round(time.time()-t0,1)}s)", flush=True)
    if ok:
        field = or_field(cfg, 1, 0)
        here = os.path.dirname(os.path.abspath(__file__))
        open(os.path.join(here, "compiled_or.rle"), "w").write(to_rle(field))
        print(f"  emitted compiled_or.rle: {len(field)} cells, bbox {bbox(field)}", flush=True)
    sys.exit(0 if ok else 1)
