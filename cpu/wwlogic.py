#!/usr/bin/env python3
"""
wwlogic — a synchronous gate-level logic simulator whose ONLY primitives are the
two things we verify physically in Wireworld: a NAND gate and a D flip-flop.

Why this is a faithful model of a Wireworld machine
---------------------------------------------------
Wireworld's async-composition wall (a long lead on one gate input corrupts the
other; inter-gate wires are bidirectional and oscillate) is dissolved by a
*synchronous* discipline: every signal is latched in a D flip-flop once per
clock, and combinational NAND clouds are allowed to settle in between. That is
exactly how real silicon defeats the same hazards (setup/hold + a global clock).
So a netlist of {NAND, DFF} with a single clock computes what the physical
Wireworld circuit computes, cycle for cycle — provided each NAND and each DFF is
a verified Wireworld gadget (see ww_cells.py).

Evaluation model
----------------
A `Circuit` holds nets (wires carrying a 0/1 for the current cycle), combinational
NAND gates, and DFFs. Each clock cycle:
  1. settle(): recompute every NAND to a fixpoint (combinational logic is acyclic
     except through DFFs, so this converges).
  2. tick(): sample each DFF's D (post-settle), then commit all Q's simultaneously
     (edge-triggered semantics — no race between flops).
NAND is functionally complete, so AND/OR/NOT/XOR/MUX below are all built from it,
mirroring a real standard-cell library.
"""

class Circuit:
    def __init__(self):
        self.vals = {}          # net id -> 0/1
        self.nands = []         # (out, a, b)
        self.dffs = []          # dict: q, d, en, clr, init
        self._n = 0
        self.GND = self.net(0)  # constant 0
        self.VCC = self.net(1)  # constant 1
        self._const = {self.GND, self.VCC}

    # --- net creation -----------------------------------------------------
    def net(self, init=0):
        i = self._n; self._n += 1
        self.vals[i] = init
        return i

    def bus(self, width, init=0):
        return [self.net((init >> k) & 1) for k in range(width)]

    # --- primitive: NAND --------------------------------------------------
    def nand(self, a, b):
        o = self.net()
        self.nands.append((o, a, b))
        return o

    # --- primitive: D flip-flop (rising edge), optional load-enable & clear
    def dff(self, d, en=None, clr=None, init=0):
        q = self.net(init)
        self.dffs.append(dict(q=q, d=d, en=en, clr=clr, init=init))
        return q

    # --- derived combinational gates (all from NAND) ----------------------
    def not_(self, a):        return self.nand(a, a)
    def and_(self, a, b):     return self.not_(self.nand(a, b))
    def or_(self, a, b):      return self.nand(self.not_(a), self.not_(b))
    def nor_(self, a, b):     return self.not_(self.or_(a, b))
    def xor_(self, a, b):
        n = self.nand(a, b)
        return self.nand(self.nand(a, n), self.nand(n, b))
    def xnor_(self, a, b):    return self.not_(self.xor_(a, b))

    def and3(self, a, b, c):  return self.and_(self.and_(a, b), c)
    def and4(self, a, b, c, d): return self.and_(self.and_(a, b), self.and_(c, d))
    def or3(self, a, b, c):   return self.or_(self.or_(a, b), c)
    def or4(self, a, b, c, d): return self.or_(self.or_(a, b), self.or_(c, d))

    def and_list(self, xs):
        xs = list(xs)
        if not xs: return self.VCC
        acc = xs[0]
        for x in xs[1:]: acc = self.and_(acc, x)
        return acc

    def or_list(self, xs):
        xs = list(xs)
        if not xs: return self.GND
        acc = xs[0]
        for x in xs[1:]: acc = self.or_(acc, x)
        return acc

    # 2:1 mux — sel ? b : a
    def mux2(self, sel, a, b):
        ns = self.not_(sel)
        return self.or_(self.and_(ns, a), self.and_(sel, b))

    def mux2_bus(self, sel, A, B):
        return [self.mux2(sel, a, b) for a, b in zip(A, B)]

    # --- evaluation -------------------------------------------------------
    def settle(self, max_iter=None):
        v = self.vals
        # keep constants pinned
        v[self.GND] = 0; v[self.VCC] = 1
        n = len(self.nands)
        cap = max_iter if max_iter is not None else (n + 5)
        for _ in range(cap):
            changed = False
            for (o, a, b) in self.nands:
                nv = 0 if (v[a] and v[b]) else 1
                if v[o] != nv:
                    v[o] = nv; changed = True
            if not changed:
                return
        # If we get here the combinational logic didn't converge (a real
        # combinational loop) — that's a design bug we want to hear about.
        raise RuntimeError("combinational logic failed to settle (cycle?)")

    def tick(self):
        self.settle()
        v = self.vals
        nxt = []
        for ff in self.dffs:
            if ff['clr'] is not None and v[ff['clr']]:
                nv = 0
            elif ff['en'] is not None and not v[ff['en']]:
                nv = v[ff['q']]                 # hold
            else:
                nv = v[ff['d']]
            nxt.append((ff['q'], nv))
        for q, nv in nxt:
            v[q] = nv
        self.settle()

    # --- convenience ------------------------------------------------------
    def set(self, net, bit):   self.vals[net] = bit & 1
    def get(self, net):        return self.vals[net]
    def getbus(self, bus):     return sum((self.vals[n] & 1) << k for k, n in enumerate(bus))
    def setbus(self, bus, val):
        for k, n in enumerate(bus):
            self.vals[n] = (val >> k) & 1


# ============================ self-tests ==============================
if __name__ == "__main__":
    ok = True
    def check(name, cond):
        global ok
        ok = ok and cond
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")

    # 1) NAND-derived gate truth tables
    c = Circuit()
    a = c.net(); b = c.net()
    g_and = c.and_(a, b); g_or = c.or_(a, b); g_xor = c.xor_(a, b); g_not = c.not_(a)
    print("Truth tables (built from NAND only):")
    for A in (0, 1):
        for B in (0, 1):
            c.set(a, A); c.set(b, B); c.settle()
            check(f"AND {A}{B}", c.get(g_and) == (A & B))
            check(f"OR  {A}{B}", c.get(g_or) == (A | B))
            check(f"XOR {A}{B}", c.get(g_xor) == (A ^ B))
    c.set(a, 0); c.settle(); check("NOT 0", c.get(g_not) == 1)
    c.set(a, 1); c.settle(); check("NOT 1", c.get(g_not) == 0)

    # 2) DFF as a toggle (÷2 counter): D = NOT Q
    c = Circuit()
    q_ref = [None]
    # need Q before we can wire D=NOT Q — create the flop with a placeholder,
    # then patch. Simpler: build a feedback net.
    c2 = Circuit()
    # make a dff whose d is not(q): allocate q first via dff with d set later.
    # We'll just construct: q = dff(d); d = not(q). Circuit stores d by net id,
    # so create the not gate AFTER we know q, and rebind the dff's d.
    q = c2.dff(c2.GND, init=0)          # temp d
    d = c2.not_(q)
    c2.dffs[-1]['d'] = d                 # rebind D = NOT Q
    seq = []
    for _ in range(6):
        seq.append(c2.get(q)); c2.tick()
    check("DFF toggles 010101", seq == [0, 1, 0, 1, 0, 1])

    # 3) DFF load-enable holds when en=0
    c3 = Circuit()
    d_in = c3.net(); en = c3.net()
    q3 = c3.dff(d_in, en=en, init=0)
    c3.set(d_in, 1); c3.set(en, 0); c3.tick()
    check("DFF holds when en=0", c3.get(q3) == 0)
    c3.set(en, 1); c3.tick()
    check("DFF loads when en=1", c3.get(q3) == 1)
    c3.set(d_in, 0); c3.set(en, 0); c3.tick()
    check("DFF holds new val when en=0", c3.get(q3) == 1)

    print("\nALL PASS" if ok else "\nSOME FAILED")
