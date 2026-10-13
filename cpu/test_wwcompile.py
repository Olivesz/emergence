#!/usr/bin/env python3
"""Netlists compiled to raw Wireworld, run in the rule itself.

  full adder   every one of the 8 input rows: each output pair carries exactly
               one electron, on the right wire, on the tick the schedule says
  4-bit PC     the program counter from modules.py, counting with no inputs:
               after every clock the four register points hold the same bits
               as the wwlogic netlist, 0..15 and round again

Inputs are launched as electrons on the input rails; the rest is the
reference Wireworld rule (wwtiles.simulate) over the emitted cells.
"""
import time

from wwlogic import Circuit
from modules import full_adder, program_counter
from wwlower import lower
from wwplace import Layout, emit
from wwtiles import simulate, T


def compile_circuit(c, inputs=(), outputs=(), gap=6):
    nl, info = lower(c, inputs=inputs, outputs=outputs)
    L = Layout(nl, info)
    L.place(colgap=gap, rowgap=gap)
    L.route_all()
    return nl, info, L, emit(L)


def full_adder_test():
    c = Circuit()
    a, b, ci = c.net(), c.net(), c.net()
    s, co = full_adder(c, a, b, ci)
    nl, info, L, E = compile_circuit(c, (a, b, ci), (s, co))
    end = T * (max(L.tau.values()) + 4)
    ok = True
    for A in (0, 1):
        for B in (0, 1):
            for C in (0, 1):
                launch = []
                for n, v in ((a, A), (b, B), (ci, C)):
                    t, f = info["inputs"][n]
                    head, tail = E["launch"][t if v else f]
                    launch.append((0, head, tail))
                probes = {g: E["probes"][g] for n in (s, co) for g in info["outputs"][n]}
                hits, left = simulate(E["cells"], launch, list(probes.values()), end)
                row = []
                for n, want in ((s, A ^ B ^ C), (co, int(A + B + C >= 2))):
                    t, f = info["outputs"][n]
                    on, off = (t, f) if want else (f, t)
                    good = hits[probes[on]] == [T * L.tau[on]] and hits[probes[off]] == []
                    ok &= good
                    row.append(f"{want}@{hits[probes[on]]}")
                ok &= left == 0
                print(f"    {A}+{B}+{C}: sum {row[0]}  carry {row[1]}  electrons left {left}")
    print(f"  [{'PASS' if ok else 'FAIL'}] full adder in raw Wireworld: {L.W}x{L.H} tiles, "
          f"{len(E['cells'])} cells, outputs at ticks {T * L.tau[info['outputs'][s][0]]} "
          f"and {T * L.tau[info['outputs'][co][0]]}")
    return ok


def counter_test(cycles=18):
    c = Circuit()
    pc = program_counter(c, c.VCC, c.GND, [c.GND] * 4, 4)
    nl, info, L, E = compile_circuit(c)
    launch = []
    for q, (t, f) in info["regs"].items():
        head, tail = E["launch"][t if info["init"][q] else f]
        launch.append((0, head, tail))
    period = T * L.period
    probe = {g: E["probes"][g] for rails in info["regs"].values() for g in rails}
    hits, left = simulate(E["cells"], launch, list(probe.values()), period * cycles + 1)
    hits = {p: set(v) for p, v in hits.items()}
    ok, seen, want = True, [], []
    for k in range(cycles):
        if k:
            c.tick()
        val = 0
        for i, q in enumerate(pc):
            t, f = info["regs"][q]
            on_t = (period * k in hits[probe[t]]) or (k == 0 and info["init"][q] == 1)
            on_f = (period * k in hits[probe[f]]) or (k == 0 and info["init"][q] == 0)
            ok &= on_t != on_f                    # exactly one rail per bit
            val |= int(on_t) << i
        seen.append(val)
        want.append(c.getbus(pc))
    ok &= seen == want and left == 2 * len(pc)   # one electron (head + tail) per bit
    print(f"    Wireworld: {seen}\n    wwlogic:   {want}")
    print(f"  [{'PASS' if ok else 'FAIL'}] 4-bit counter in raw Wireworld, lockstep for "
          f"{cycles} clocks: {L.W}x{L.H} tiles, {len(E['cells'])} cells, "
          f"clock period {period} ticks")
    return ok


if __name__ == "__main__":
    t0 = time.time()
    ok = full_adder_test()
    ok &= counter_test()
    print(f"{'ALL PASS' if ok else 'SOME FAILED'}  ({time.time() - t0:.0f}s)")
    raise SystemExit(0 if ok else 1)
