#!/usr/bin/env python3
"""The compiled D flip-flop with enable, checked exhaustively in raw Wireworld.

The netlist's flip-flop (wwlogic.Circuit.dff with an enable) compiles to:
  * a NAND multiplexer computing the next value, (en AND d) OR (NOT en AND q)
  * a register point on each of the two rails, closing a loop exactly one
    clock long, so the value that arrives at the end of clock k is the
    flip-flop's output for all of clock k+1 (Q(k+1) = D(k), edge-triggered).

d and en are driven from outside, one electron per input per clock. The
sequence visits every (q, d, en) combination, holds for three clocks running
with en=0 at both q=0 and q=1, and loads the same value twice in a row. After
every clock the register point must carry exactly one electron, on the rail
that wwlogic says.
"""
from wwlogic import Circuit
from wwlower import lower
from wwplace import Layout, emit
from wwtiles import simulate, T

# (d, en) per clock. With q starting at 0 this covers all 8 (q, d, en) rows.
SEQ = [(0, 0), (1, 0), (1, 1), (1, 1), (0, 0), (0, 0), (1, 0), (0, 0),
       (0, 1), (0, 1), (1, 0), (0, 0), (0, 0), (1, 1), (1, 0), (0, 1)]


def main():
    c = Circuit()
    d, en = c.net(), c.net()
    q = c.dff(d, en=en, init=0)
    nl, info = lower(c, inputs=(d, en))
    L = Layout(nl, info)
    L.place(colgap=6, rowgap=6)
    L.route_all()
    E = emit(L)
    period = T * L.period
    launch = []
    for k, (dv, ev) in enumerate(SEQ):
        for net, v in ((d, dv), (en, ev)):
            t, f = info["inputs"][net]
            head, tail = E["launch"][t if v else f]
            launch.append((k * period, head, tail))
    t_rail, f_rail = info["regs"][q]
    pt, pf = E["probes"][t_rail], E["probes"][f_rail]
    hits, _ = simulate(E["cells"], launch + [(0, *E["launch"][f_rail])], [pt, pf],
                       period * (len(SEQ) + 1) + 1)
    ht, hf = set(hits[pt]), set(hits[pf])

    ok, seen = True, set()
    print("  clock  q  d en | next q (Wireworld)  next q (wwlogic)")
    for k, (dv, ev) in enumerate(SEQ):
        c.set(d, dv)
        c.set(en, ev)
        qv = c.get(q)
        c.tick()
        want = c.get(q)
        tick = (k + 1) * period
        on_t, on_f = tick in ht, tick in hf
        got = 1 if on_t and not on_f else 0 if on_f and not on_t else None
        good = got == want
        ok &= good
        seen.add((qv, dv, ev))
        print(f"  {k:5d}  {qv}  {dv}  {ev} | {str(got):>18}  {want:>16}  "
              f"[{'PASS' if good else 'FAIL'}]")
    full = len(seen) == 8
    ok &= full
    print(f"  [{'PASS' if full else 'FAIL'}] all 8 (q, d, en) rows exercised")
    print(f"  {L.W}x{L.H} tiles, clock period {period} ticks")
    print("ALL PASS" if ok else "SOME FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
