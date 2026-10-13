#!/usr/bin/env python3
"""A full adder and multi-bit sums from the physically-routed HALF-ADDER
(ha_full.build_half_adder), which is re-run in raw B3/S23 for every use.

  FA(A,B,Cin):  HA1(A,B) -> s1,c1 ;  HA2(s1,Cin) -> sum,c2 ;  cout = c1 OR c2

The half-adders are the routed glider cell. What connects them is Python: it
hands s1 from one run to the next, ORs c1 and c2, and passes each column's
carry to the next column, as gates.py's reaction-level adder does."""
import time
from life import run
from ha_full import build_half_adder, _surv


def eval_ha(h, A, B, T):
    """Run the routed half-adder in the raw rule; return (sum, carry) bits."""
    init = set(h['cats'])
    if A: init |= set(h['a_in']) | set(h['a2_in']) | set(h['a3_in'])
    if B: init |= set(h['b_in']) | set(h['b2_in'])
    surv, rest = _surv(run(init, T))
    assert rest == h['cats'], "half-adder catalysts not restored"
    sm = 1 if [l for (d, l) in surv if d == 'SE' and l in h['sum_lanes']] else 0
    cy = 1 if ('NW', h['carry_lane']) in surv else 0
    return sm, cy


def full_adder(h, A, B, Cin, T):
    s1, c1 = eval_ha(h, A, B, T)
    sm, c2 = eval_ha(h, s1, Cin, T)
    assert not (c1 and c2), "carries not mutually exclusive!"   # sanity: OR is safe
    return sm, (c1 | c2)


def ripple_add(h, avec, bvec, T):
    """LSB-first bit vectors -> sum vector (len+1, top bit = final carry)."""
    carry, out = 0, []
    for a, b in zip(avec, bvec):
        s, carry = full_adder(h, a, b, carry, T)
        out.append(s)
    out.append(carry)
    return out


def bits(n, w): return [(n >> i) & 1 for i in range(w)]
def val(vec):   return sum(b << i for i, b in enumerate(vec))


def main():
    t0 = time.time()
    def lap(m): print(f"[{time.time()-t0:6.1f}s] {m}", flush=True)
    from routed import build_variants
    V = build_variants(); lap("built variants")
    h = build_half_adder(V, lap)
    T = h['t_tgt'] + 1500
    lap("half-adder cell built; verifying full adder")

    # ---- 8-row full-adder truth table ----
    allok = True
    for A in (0, 1):
        for B in (0, 1):
            for Cin in (0, 1):
                sm, co = full_adder(h, A, B, Cin, T)
                want_s, want_c = (A ^ B ^ Cin), (1 if A + B + Cin >= 2 else 0)
                ok = (sm == want_s) and (co == want_c); allok &= ok
                print(f"  A={A} B={B} Cin={Cin} -> sum={sm} cout={co} "
                      f"(want {want_s},{want_c}) {'OK' if ok else 'FAIL'}", flush=True)
    print("FULL ADDER (two routed half-adder runs, carries ORed in Python):",
          "PASS" if allok else "FAIL", flush=True)
    lap("full adder verified")

    # ---- multi-bit sums: the routed half-adder per bit, carries passed in Python ----
    cases = [(6, 5, 4), (511, 1, 10), (682, 341, 10)]
    mok = True
    for a, b, w in cases:
        out = ripple_add(h, bits(a, w), bits(b, w), T)
        got = val(out); want = a + b
        ok = (got == want); mok &= ok
        print(f"  {a} + {b} = {got} (want {want}) [{w}-bit] {'OK' if ok else 'FAIL'}", flush=True)
    print("\nMULTI-BIT SUMS (routed half-adder per bit, carries passed in Python):",
          "PASS" if (allok and mok) else "FAIL")
    lap("done")
    return allok and mok


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
