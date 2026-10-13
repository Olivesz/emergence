#!/usr/bin/env python3
"""Routing primitive for a fully-physical adder: a 2-Snark SE->SW->SE lane-shifter
that takes an SE glider on lane L_in and re-emits it as SE on a chosen lane L_out
(so a fanned copy can be delivered onto a gate's exact input lane). This SE->SW->SE
pair reaches duplicator-input lanes (the fan-out's consumers) cleanly; far output
lanes need the complementary SE->NE->SE pair (m1r3,m0r0) not built here. BOUNDED."""
import time
from life import run
from gadgets import split_gliders, glider_dir, glider_lane
from routed import build_variants, bbox_gap

V = build_variants()
v1 = V['snark_m0r1']   # SE -> SW
v2 = V['snark_m1r0']   # SW -> SE


def build_shift(L_in, L_out, dx1=0):
    dy1 = dx1 + (L_in - v1.lin)            # v1 in_lane (SE ymx) == L_in
    cat1 = v1.place(dx1, dy1)
    Lsw = v1.out_lane(dx1, dy1)            # v1 SW output lane (xpy)
    S = Lsw - v2.lin                       # dx2+dy2  (v2 SW in, xpy)
    D = L_out - v2.lout                    # dy2-dx2  (v2 SE out, ymx)
    if (S - D) % 2:
        return None
    dx2, dy2 = (S - D) // 2, (S + D) // 2
    cat2 = v2.place(dx2, dy2)
    if bbox_gap(cat1, cat2) < 5:
        return None
    return cat1 | cat2, (dx1, dy1), (dx2, dy2)


def verify(L_in, L_out):
    for dx1 in range(-80, 240, 1):        # slide until the two Snarks clear
        built = build_shift(L_in, L_out, dx1)
        if not built:
            continue
        cats, p1, p2 = built
        gin = v1.input_glider(*p1, back=6)
        if set(gin) & cats:
            continue
        gs, rest = split_gliders(run(cats | set(gin), 1200))
        if rest == cats and len(gs) == 1 and glider_dir(gs[0]) == (1, 1) \
                and glider_lane(gs[0]) == L_out:
            return True, dx1, p1, p2
    return False, None, None, None


if __name__ == "__main__":
    t0 = time.time()
    print(f"v1 {v1.din}->{v1.dout} (lin {v1.lin} lout {v1.lout}); "
          f"v2 {v2.din}->{v2.dout} (lin {v2.lin} lout {v2.lout})")
    # route a fanned copy (SE on lane -47) onto a duplicator's input lane (-1),
    # and onto the routed-AND's A entry lane (40), as concrete targets.
    # A Snark pair preserves lane parity, so an odd lane cannot reach an even
    # one: that case must find nothing.
    allok = True
    for (L_in, L_out, label) in [(-47, -1, "dup input"), (-47, 40, "AND A-entry"),
                                 (-45, -1, "dup input (other copy)")]:
        ok, dx1, p1, p2 = verify(L_in, L_out)
        expect = (L_in - L_out) % 2 == 0
        allok &= bool(ok) == expect
        print(f"SE lane {L_in} -> SE lane {L_out} [{label}]: "
              + (f"OK (Snarks @ {p1},{p2})" if ok else "no clean placement found")
              + ("" if expect else "  (expected: parity differs)"))
    print("elapsed", round(time.time() - t0, 1), "s")
    raise SystemExit(0 if allok else 1)
