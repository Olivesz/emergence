#!/usr/bin/env python3
"""
Logic gates with NOTHING but gliders and Conway's rule.

A signal is a *stream of gliders*: a glider present in a period-30 time-slot on a
diagonal "lane" means 1, absent means 0. A Gosper gun is a constant source of 1s.
Gates are literally *collisions* — where two gliders meet, the Life rule decides
what survives. This file finds the reactions by brute-force simulation (so nothing
is taken on faith) and assembles them into gates whose truth tables are then
checked by running the raw automaton.
"""
from life import step, run, translate, normalize, bbox, GLIDER, GOSPER, EATER

# ---- gliders in all four diagonal directions, each verified by simulation ----
def _mirror(cells, mx=False, my=False, w=3, h=3):
    return {((w-1-x) if mx else x, (h-1-y) if my else y) for (x, y) in cells}

def _velocity(cells, ticks=4):
    b0 = bbox(cells); c1 = run(set(cells), ticks); b1 = bbox(c1)
    return (b1[0]-b0[0], b1[1]-b0[1])

# build the four gliders and confirm each moves the way its name says
_SE = set(GLIDER)                                   # +x,+y
_SW = _mirror(GLIDER, mx=True)                      # -x,+y
_NE = _mirror(GLIDER, my=True)                      # +x,-y
_NW = _mirror(GLIDER, mx=True, my=True)             # -x,-y
DIRV = {"SE": (1, 1), "SW": (-1, 1), "NE": (1, -1), "NW": (-1, -1)}
GLIDERS = {"SE": _SE, "SW": _SW, "NE": _NE, "NW": _NW}

def glider(dir, x=0, y=0, phase=0):
    g = run(set(GLIDERS[dir]), phase % 4)
    return translate(g, x, y)

def glider_phases(dir):
    return {normalize(run(set(GLIDERS[dir]), k)) for k in range(4)}

ALL_PHASES = set()
for d in GLIDERS: ALL_PHASES |= glider_phases(d)

def components(cells):
    cells = set(cells); seen = set(); comps = []
    for c in cells:
        if c in seen: continue
        stack = [c]; comp = set()
        while stack:
            p = stack.pop()
            if p in seen or p not in cells: continue
            seen.add(p); comp.add(p); x, y = p
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    if dx or dy: stack.append((x+dx, y+dy))
        comps.append(comp)
    return comps

def is_glider(c):
    return len(c) == 5 and normalize(c) in ALL_PHASES


# ---- find a clean two-glider ANNIHILATION (the heart of a NOT gate) ----------
def find_annihilation():
    """An SE glider and an NW glider meeting head-on. Search offset & phase for a
       collision that leaves the plane EMPTY — total mutual annihilation."""
    a = glider("SE", 0, 0)
    for phase in range(4):
        for ox in range(4, 16):
            for oy in range(-6, 7):
                b = glider("NW", ox, oy, phase)
                if a & b: continue
                field = a | b
                # run long enough for the collision to resolve and any escapees to leave
                res = run(field, 60)
                if len(res) == 0:
                    return dict(offset=(ox, oy), phase=phase)
    return None


# ---- the INHIBIT gate:  out = A AND NOT B  (B's glider deletes A's) ----------
# A is an SE glider on the "data" lane; B is an NW glider aimed to annihilate it.
# The output lane is A's path continued past the collision point.

ANN = find_annihilation()      # the annihilation geometry, computed once at import

def _output_region(T):
    # where A's SE glider sits at time T if nothing hit it (the output window)
    aT = run(glider("SE", 0, 0), T)
    x0, y0, x1, y1 = bbox(aT)
    return (x0-1, y0-1, x1+1, y1+1)

def inhibit(A_bit, B_bit, T=48):
    field = set()
    if A_bit: field |= glider("SE", 0, 0)
    if B_bit: field |= glider("NW", ANN["offset"][0], ANN["offset"][1], ANN["phase"])
    res = run(field, T)
    rx0, ry0, rx1, ry1 = _output_region(T)
    out = {(x, y) for (x, y) in res if rx0 <= x <= rx1 and ry0 <= y <= ry1}
    return 1 if any(is_glider(c) for c in components(out)) else 0

def NOT(B_bit, T=48):          # NOT B  =  1 AND NOT B  =  inhibit(1, B)
    return inhibit(1, B_bit, T)

# ---- the AND gate:  two gliders MERGE into one only when both are present -----
# A is an SE glider; B is an SW glider. Where they meet they fuse into a single
# output glider heading NW — a lane neither input reaches on its own, so a lone A
# or lone B produces nothing there. (reaction found by search, hard-coded here.)
AND_REACTION = dict(bdir="SW", phase=1, offset=(2, 4), T=64)

def _and_output_region(T, pad=2):
    r = AND_REACTION
    both = run(glider("SE", 0, 0) | glider(r["bdir"], r["offset"][0], r["offset"][1], r["phase"]), T)
    oc = components(both)[0]
    x0, y0, x1, y1 = bbox(oc)
    return (x0-pad, y0-pad, x1+pad, y1+pad)

def AND(A_bit, B_bit):
    r = AND_REACTION; T = r["T"]
    field = set()
    if A_bit: field |= glider("SE", 0, 0)
    if B_bit: field |= glider(r["bdir"], r["offset"][0], r["offset"][1], r["phase"])
    res = run(field, T)
    x0, y0, x1, y1 = _and_output_region(T)
    out = {(x, y) for (x, y) in res if x0 <= x <= x1 and y0 <= y <= y1}
    return 1 if any(is_glider(c) for c in components(out)) else 0

# NAND = NOT(AND) — the single universal gate. {NAND} alone builds any circuit,
# exactly as the Wireworld CPU reduces to NAND. So the *same* logic that runs the
# SAP-1/SAP-2 could in principle stand on these glider gates — computation, all
# the way down to "3 to be born, 2 to survive."


if __name__ == "__main__":
    ok = True
    def check(name, cond):
        global ok; ok = ok and cond
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")

    print("gliders in four directions (velocity verified):")
    for d in ["SE", "SW", "NE", "NW"]:
        check(f"{d} glider moves {DIRV[d]}", _velocity(GLIDERS[d]) == DIRV[d])

    print("\nsearching for a two-glider annihilation reaction…")
    ANN = find_annihilation()
    check("found a clean SE+NW annihilation (plane left empty)", ANN is not None)
    if ANN: print("   reaction:", ANN)

    print("\nINHIBIT gate  (out = A AND NOT B), truth table in raw Life:")
    for a in (0, 1):
        for b in (0, 1):
            got = inhibit(a, b); want = a & (1 - b)
            check(f"  A={a} B={b} -> {got}  (want {want})", got == want)

    print("\nNOT gate  (out = NOT B):")
    check("  NOT 0 -> 1", NOT(0) == 1)
    check("  NOT 1 -> 0", NOT(1) == 0)

    print("\nAND gate  (two gliders merge only when both present):")
    for a in (0, 1):
        for b in (0, 1):
            got = AND(a, b); want = a & b
            check(f"  A={a} B={b} -> {got}  (want {want})", got == want)

    print("\nNAND (universal) = NOT(AND):")
    check("  NAND 1,1 -> 0", (1 - AND(1, 1)) == 0)
    check("  NAND 1,0 -> 1", (1 - AND(1, 0)) == 1)

    print("\nALL PASS" if ok else "\nSOME FAILED")
