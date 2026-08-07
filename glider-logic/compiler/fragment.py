#!/usr/bin/env python3
"""Route AROUND wall #2. Fan-in (OR) can't be a reflector-merge (merge.py) — but it
doesn't have to be. Build EVERYTHING from just the two proven reactions:

    gates.inhibit(A,B) = A AND NOT B      (annihilation; ../routed.py RUNG 2)
    gates.AND(A,B)     = A AND B          (both-present merge; ../routed.py RUNG 3)

plus a constant '1' carrier (an injected glider — free in a one-shot circuit) and
fan-out (../physical_fanout.py). No two mutually-exclusive gliders are ever merged
onto one lane, so wall #2 never bites. If the truth tables below all pass, the full
adder is IN the achievable fragment: what remains is routing/timing at scale, not a
new wall.

Every gate is evaluated through gates.py's RAW-LIFE reaction functions, so these are
real collisions, not Python booleans. BOUNDED. Run: python3 -u fragment.py
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import gates

t0 = time.time()

# ---- the whole basis: two reactions + a constant carrier -------------------
def INH(a, b):  return gates.inhibit(a, b)   # A AND NOT B   (raw Life)
def AND(a, b):  return gates.AND(a, b)       # A AND B       (raw Life)
def NOT(a):     return INH(1, a)             # constant-1 carrier, deleted by a
def OR(a, b):   return NOT(AND(NOT(a), NOT(b)))          # De Morgan — no fan-in
def NAND(a, b): return NOT(AND(a, b))
def XOR(a, b):  return AND(OR(a, b), NAND(a, b))         # a!=b  == (a|b) & !(a&b)

def half_add(a, b):
    return XOR(a, b), AND(a, b)                          # (sum, carry)

def full_add(a, b, cin):
    s1, c1 = half_add(a, b)
    s2, c2 = half_add(s1, cin)
    return s2, OR(c1, c2)                                # carry-OR, also De Morgan

def ripple_add(x, y, nbits):
    r = cin = 0
    for i in range(nbits):
        s, cin = full_add((x >> i) & 1, (y >> i) & 1, cin)
        r |= s << i
    return r | (cin << nbits)


def check(name, cond, fails):
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}", flush=True)
    if not cond:
        fails.append(name)


if __name__ == "__main__":
    fails = []
    print("basis reactions (raw Life): INHIBIT, AND, and NOT = INHIBIT(1, x)", flush=True)
    for a in (0, 1):
        for b in (0, 1):
            check(f"INHIBIT {a},{b} = {a&(1-b)}", INH(a, b) == a & (1 - b), fails)
    check("NOT 0 = 1", NOT(0) == 1, fails)
    check("NOT 1 = 0", NOT(1) == 0, fails)

    print("\nOR = NOT(AND(NOT a, NOT b))  — De Morgan, no reflector fan-in:", flush=True)
    for a in (0, 1):
        for b in (0, 1):
            check(f"{a} OR {b} = {a | b}", OR(a, b) == (a | b), fails)

    print("\nXOR = AND(OR(a,b), NAND(a,b)):", flush=True)
    for a in (0, 1):
        for b in (0, 1):
            check(f"{a} XOR {b} = {a ^ b}", XOR(a, b) == (a ^ b), fails)

    print("\nHALF-ADDER (sum=XOR, carry=AND), all in-fragment:", flush=True)
    for a in (0, 1):
        for b in (0, 1):
            s, c = half_add(a, b)
            check(f"{a}+{b} -> sum {s} carry {c}", (s, c) == (a ^ b, a & b), fails)

    print("\nFULL-ADDER (two half-adders + carry-OR), all in-fragment:", flush=True)
    for a in (0, 1):
        for b in (0, 1):
            for cin in (0, 1):
                s, co = full_add(a, b, cin); tot = a + b + cin
                check(f"{a}+{b}+{cin} -> sum {s} cout {co}",
                      (s, co) == (tot & 1, tot >> 1), fails)

    print("\nRIPPLE ADD — every bit through the in-fragment full adder:", flush=True)
    for x, y, n in [(6, 5, 4), (3, 2, 3), (15, 1, 4), (170, 85, 8), (511, 1, 9)]:
        check(f"{x} + {y} = {x + y}", ripple_add(x, y, n) == x + y, fails)

    dt = round(time.time() - t0, 1)
    if not fails:
        print(f"\nALL PASS ({dt}s) — the full adder is built from ONLY the two proven "
              "reactions + a constant carrier. Wall #2 blocks the naive merge; De Morgan "
              "routes around it. What's left is routing/timing at scale, not a new wall.")
    else:
        print(f"\n{len(fails)} FAILED ({dt}s): {fails}")
    sys.exit(1 if fails else 0)
