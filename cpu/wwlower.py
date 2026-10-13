#!/usr/bin/env python3
"""
wwlower.py — lower a wwlogic Circuit (NAND + DFF) to the gadget netlist the
Wireworld compiler lays out.

Every logic value becomes a pair of rails: in each machine cycle exactly one of
the two carries a pulse. On rails, NOT is free (swap them) and constants fold
away, so the netlist's NOT gates and constant inputs disappear. Each remaining
NAND(a, b) becomes three gadgets:

    m   = MERGE(a.f, b.f)        pulses iff NAND(a,b) = 1   (the result's true rail)
    clk = MERGE(a.t, a.f)        always exactly one pulse   (a local clock)
    n   = NOTC(p=m, q=clk)       pulses iff m does not      (the result's false rail)

A flip-flop with enable becomes NAND logic in front of a one-cycle delay: its
next value is (en AND d) OR (NOT en AND q). The delay itself is a register
point: the rail's wire passes through it once per cycle, and that is where the
initial electron sits.

Identical NANDs (same two inputs) are built once.
"""
from collections import defaultdict


class GadgetNetlist:
    """kinds: 'merge' (ins a, b), 'notc' (ins p, q), 'reg' (in d), 'in', 'out' (in d).
    Every gadget drives at most one rail (its id); rails are gadget ids."""

    def __init__(self):
        self.kind = []
        self.ins = []          # dict port -> driving gadget id
        self.tag = []          # human-readable origin

    def add(self, kind, tag, **ins):
        self.kind.append(kind)
        self.ins.append(dict(ins))
        self.tag.append(tag)
        return len(self.kind) - 1

    def sinks(self):
        s = defaultdict(list)
        for g, ins in enumerate(self.ins):
            for port, src in ins.items():
                s[src].append((g, port))
        return s

    def count(self, kind):
        return sum(1 for k in self.kind if k == kind)


def lower(c, inputs=(), outputs=()):
    """c: wwlogic.Circuit. inputs: nets driven from outside (each gets two 'in'
    gadgets). outputs: nets to expose (each gets two 'out' gadgets).
    Returns (netlist, info) where info maps names to rails."""
    nl = GadgetNetlist()
    prod = {o: (a, b) for o, a, b in c.nands}
    CONST0, CONST1 = ("c", 0), ("c", 1)
    lit = {c.GND: CONST0, c.VCC: CONST1}
    rails = {}                       # base -> (true rail gadget, false rail gadget)

    def neg(l):
        return ("c", 1 - l[1]) if l[0] == "c" else (l[0], not l[1])

    def true_rail(l):
        t, f = rails[l[0]]
        return t if l[1] else f

    def false_rail(l):
        t, f = rails[l[0]]
        return f if l[1] else t

    reg_of = {}
    for i, ff in enumerate(c.dffs):
        base = ("q", ff["q"])
        t = nl.add("reg", f"q{ff['q']}.t", d=None)
        f = nl.add("reg", f"q{ff['q']}.f", d=None)
        rails[base] = (t, f)
        reg_of[ff["q"]] = (t, f, ff)
        lit[ff["q"]] = (base, True)
    for n in inputs:
        base = ("in", n)
        rails[base] = (nl.add("in", f"in{n}.t"), nl.add("in", f"in{n}.f"))
        lit[n] = (base, True)

    memo = {}

    def nand(la, lb):
        if la == CONST0 or lb == CONST0:
            return CONST1
        if la == CONST1:
            return neg(lb)
        if lb == CONST1:
            return neg(la)
        if la == lb:
            return neg(la)
        if la == neg(lb):
            return CONST1
        key = frozenset((la, lb))
        if key in memo:
            return memo[key]
        m = nl.add("merge", "m", a=false_rail(la), b=false_rail(lb))
        clk = nl.add("merge", "clk", a=true_rail(la), b=false_rail(la))
        n = nl.add("notc", "n", p=m, q=clk)
        base = ("g", m)
        rails[base] = (m, n)
        memo[key] = (base, True)
        return memo[key]

    import sys
    sys.setrecursionlimit(max(10000, 4 * len(c.nands)))

    def L(n):
        if n in lit:
            return lit[n]
        a, b = prod[n]
        r = nand(L(a), L(b))
        lit[n] = r
        return r

    for o, _, _ in c.nands:
        L(o)

    def AND(x, y):
        return neg(nand(x, y))

    def OR(x, y):
        return nand(neg(x), neg(y))

    for q, (t, f, ff) in reg_of.items():
        d = L(ff["d"])
        if ff["en"] is not None:
            en = L(ff["en"])
            d = OR(AND(en, d), AND(neg(en), lit[q]))
        if ff["clr"] is not None:
            d = AND(neg(L(ff["clr"])), d)
        if d[0] == "c":
            raise ValueError(f"flip-flop {q} has a constant next state; not supported")
        nl.ins[t]["d"] = true_rail(d)
        nl.ins[f]["d"] = false_rail(d)

    outs = {}
    for n in outputs:
        l = L(n)
        if l[0] == "c":
            raise ValueError(f"output {n} is constant")
        outs[n] = (nl.add("out", f"out{n}.t", d=true_rail(l)),
                   nl.add("out", f"out{n}.f", d=false_rail(l)))
    info = dict(regs={q: (t, f) for q, (t, f, _) in reg_of.items()},
                inputs={n: rails[("in", n)] for n in inputs}, outputs=outs,
                init={q: ff["init"] for q, (_, _, ff) in reg_of.items()})
    return nl, info


def topo_order(nl):
    """Gadgets in dependency order; register points count as sources."""
    order, state = [], {}
    for start in range(len(nl.kind)):
        if start in state:
            continue
        stack = [(start, 0)]
        while stack:
            g, ph = stack.pop()
            if ph == 0:
                if g in state:
                    continue
                state[g] = 1
                stack.append((g, 1))
                if nl.kind[g] != "reg":
                    for src in nl.ins[g].values():
                        if src not in state:
                            stack.append((src, 0))
            elif state[g] != 2:
                state[g] = 2
                order.append(g)
    return order


class PulseSim:
    """Cycle-level model of the lowered netlist: which rails pulse each cycle.
    Checks the dual-rail invariant everywhere."""

    def __init__(self, nl, info):
        self.nl, self.info = nl, info
        self.order = topo_order(nl)
        self.v = [0] * len(nl.kind)
        for q, (t, f) in info["regs"].items():
            self.v[t] = info["init"][q]
            self.v[f] = 1 - info["init"][q]

    def evaluate(self, inputs=None):
        nl, v = self.nl, self.v
        for n, (t, f) in self.info["inputs"].items():
            b = (inputs or {}).get(n, 0)
            v[t], v[f] = b, 1 - b
        for g in self.order:
            k, ins = nl.kind[g], nl.ins[g]
            if k == "merge":
                v[g] = v[ins["a"]] | v[ins["b"]]
            elif k == "notc":
                if v[ins["p"]] and not v[ins["q"]]:
                    raise AssertionError("NOTC fed p without q")
                v[g] = v[ins["q"]] & (1 - v[ins["p"]])
            elif k == "out":
                v[g] = v[ins["d"]]

    def tick(self):
        new = {g: self.v[self.nl.ins[g]["d"]] for g, k in enumerate(self.nl.kind) if k == "reg"}
        for g, b in new.items():
            self.v[g] = b

    def bit(self, rails):
        t, f = rails
        if self.v[t] + self.v[f] != 1:
            raise AssertionError("dual-rail invariant broken")
        return self.v[t]


if __name__ == "__main__":
    import random
    from wwlogic import Circuit
    from modules import full_adder, program_counter
    from sap1 import SAP1
    from asm import assemble
    import run_cpu

    ok = True

    def check(name, cond):
        global ok
        ok &= cond
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")

    # full adder, exhaustive
    c = Circuit()
    a, b, ci = c.net(), c.net(), c.net()
    s, co = full_adder(c, a, b, ci)
    nl, info = lower(c, inputs=(a, b, ci), outputs=(s, co))
    ps = PulseSim(nl, info)
    good = True
    for A in (0, 1):
        for B in (0, 1):
            for C in (0, 1):
                ps.evaluate({a: A, b: B, ci: C})
                good &= ps.bit(info["outputs"][s]) == A ^ B ^ C
                good &= ps.bit(info["outputs"][co]) == (A + B + C >= 2)
    check(f"full adder on rails, 8 rows ({nl.count('merge')} merges, {nl.count('notc')} notc)", good)

    # SAP-1 in lockstep with the NAND/DFF netlist, every register every cycle
    for name, src, want in [("5+3", run_cpu.P1, [8]), ("Fibonacci", run_cpu.P5,
                            [1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144])]:
        img, _ = assemble(src)
        ref = SAP1(img)
        nl, info = lower(ref.c)
        ps = PulseSim(nl, info)
        cyc, same = 0, True
        while not ref.c.get(ref.Hlt) and cyc < 3000:
            ps.evaluate()
            for q, rails in info["regs"].items():
                if ps.bit(rails) != ref.c.get(q):
                    same = False
            ref.c.tick()
            ps.tick()
            cyc += 1
        outs = SAP1(img).run(max_cycles=3000)
        check(f"SAP-1 {name}: {cyc} cycles, all 175 registers equal every cycle, "
              f"OUT {outs}", same and outs == want)
    print(f"  SAP-1 lowered: {nl.count('merge')} merges + {nl.count('notc')} NOT-with-clock "
          f"= {nl.count('notc')} dual-rail NAND cells, {nl.count('reg')} register points")
    print("ALL PASS" if ok else "SOME FAILED")
    raise SystemExit(0 if ok else 1)
