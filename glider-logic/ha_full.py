#!/usr/bin/env python3
"""A complete routed HALF-ADDER in one raw-B3/S23 Life field:
     SUM   = the physically-routed XOR  (ha_xor.build_routed_xor)
     CARRY = the physically-routed AND  (routed.build_rung3, Rung 3)
both driven by the same logical inputs A,B.  The AND stage is translated into a
clear region so the two gates share the field without colliding.  Fan-out of A/B
into the two gates is by the project's disclosed multi-input convention (each bit
fires all of its input gliders); every gate's INTERNAL fan-out is a real duplicator.

Verified per row: SUM = A^B, CARRY = A&B, every catalyst restored, exact survivor
multiset (raw rule).  BOUNDED sims only.  `build_half_adder(V)` returns the cell
(reused by the full adder)."""
import time
from life import run, translate
from gadgets import split_gliders, glider_dir, glider_lane, DIRNAME
from routed import build_variants, build_rung3, verify_and_reaction
from ha_xor import build_routed_xor

OFF = (0, 1400)                                 # translate the AND stage clear of the XOR


def _surv(state):
    gs, rest = split_gliders(state)
    return sorted((DIRNAME[glider_dir(g)], glider_lane(g)) for g in gs), rest


def build_half_adder(V, lap=lambda m: None):
    xor = build_routed_xor(V, lap)
    lap("XOR (sum) built")
    and_ok, tau_and = verify_and_reaction()
    assert and_ok, "AND reaction failed to verify"
    a3 = build_rung3(V, tau_and)
    lap("AND (carry) built")

    dx, dy = OFF
    and_cats = translate(set(a3['cats']), dx, dy)
    a3_in = translate(set(a3['a_in']), dx, dy)
    b2_in = translate(set(a3['b_in']), dx, dy)
    assert not (and_cats & xor['cats']), "AND catalysts overlap the XOR"
    cats = xor['cats'] | and_cats
    Tand = a3['tA'] + 900

    # per-row survivors of the translated AND alone (robust: no lane-shift algebra)
    and_exp = {}
    for A, B in [(1, 1), (1, 0), (0, 1), (0, 0)]:
        init = set(and_cats)
        if A: init |= a3_in
        if B: init |= b2_in
        surv, rest = _surv(run(init, Tand))
        assert rest == and_cats, f"AND catalysts not restored, row {A}{B}"
        and_exp[(A, B)] = surv
    lap("AND per-row survivors captured")

    # combined expected survivor multiset = XOR's + AND's
    exp = {k: sorted(xor['exp'][k] + and_exp[k]) for k in xor['exp']}
    carry_lane = None
    for (d, l) in and_exp[(1, 1)]:
        if d == 'NW':
            carry_lane = l                      # the merged AND output rides here
    assert carry_lane is not None
    return dict(cats=cats, a_in=xor['a_in'], a2_in=xor['a2_in'], a3_in=a3_in,
                b_in=xor['b_in'], b2_in=b2_in, sum_lanes=xor['sum_lanes'],
                carry_lane=carry_lane, exp=exp, t_tgt=xor['t_tgt'])


def main():
    t0 = time.time()
    def lap(m): print(f"[{time.time()-t0:6.1f}s] {m}", flush=True)
    V = build_variants(); lap("built variants")
    h = build_half_adder(V, lap)
    cats, SUM, CL, exp = h['cats'], h['sum_lanes'], h['carry_lane'], h['exp']
    T = h['t_tgt'] + 1800
    allok = True
    for A, B in [(1, 1), (1, 0), (0, 1), (0, 0)]:
        init = set(cats)
        if A: init |= set(h['a_in']) | set(h['a2_in']) | set(h['a3_in'])
        if B: init |= set(h['b_in']) | set(h['b2_in'])
        surv, rest = _surv(run(init, T))
        sm = 1 if [l for (d, l) in surv if d == 'SE' and l in SUM] else 0
        cy = 1 if ('NW', CL) in surv else 0
        clean = (rest == cats); exact = (surv == exp[(A, B)])
        ok = (sm == (A ^ B)) and (cy == (A & B)) and clean and exact; allok &= ok
        print(f"[{time.time()-t0:6.1f}s]  A={A} B={B}: SUM={sm}(want {A^B}) "
              f"CARRY={cy}(want {A&B}) cats={clean} exact={exact} {'OK' if ok else 'FAIL'}",
              flush=True)
        if not exact:
            print(f"      got {surv}\n      exp {exp[(A,B)]}", flush=True)
    print("\nROUTED HALF-ADDER (SUM=XOR, CARRY=AND) — raw-rule, catalysts restored:",
          "PASS" if allok else "FAIL")
    return allok


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
