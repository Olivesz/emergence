#!/usr/bin/env python3
"""
Conway's Game of Life — the substrate, one rule below Wireworld.

Wireworld cheats a little: it *builds in* the idea of a wire and a directional
electron. Life does not. Its entire law is:

    a cell is alive next tick iff it has exactly 3 live neighbours,
    or it is alive now and has exactly 2.

That's it — no wires, no signals, no clock. And yet a small arrangement of live
cells (a *glider*) crawls diagonally across the empty plane forever, a *glider
gun* spits one out every 30 ticks, and where two gliders meet they can annihilate.
From nothing but "3 to be born, 2 to survive" we will make a moving signal, a
signal source, a signal sink, and — from their collisions — logic gates.

Cells are stored sparsely as a set of (x,y), so patterns can travel forever.
"""
from collections import Counter

def step(cells):
    nb = Counter()
    for (x, y) in cells:
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx or dy:
                    nb[(x + dx, y + dy)] += 1
    return {c for c, n in nb.items() if n == 3 or (n == 2 and c in cells)}

def run(cells, n):
    for _ in range(n):
        cells = step(cells)
    return cells

def translate(cells, dx, dy):
    return {(x + dx, y + dy) for (x, y) in cells}

def bbox(cells):
    xs = [x for x, _ in cells]; ys = [y for _, y in cells]
    return (min(xs), min(ys), max(xs), max(ys)) if cells else (0, 0, -1, -1)

def normalize(cells):
    if not cells: return frozenset()
    mnx = min(x for x, _ in cells); mny = min(y for _, y in cells)
    return frozenset((x - mnx, y - mny) for (x, y) in cells)

# ------------------------------------------------------------------ patterns
def parse(rle_rows, ox=0, oy=0):
    """Tiny ASCII-pattern parser: 'O'/'*' = alive, anything else dead."""
    cells = set()
    for y, row in enumerate(rle_rows):
        for x, ch in enumerate(row):
            if ch in "O*#":
                cells.add((x + ox, y + oy))
    return cells

# a glider, travelling SE (+x,+y), period 4, displacement (1,1) per period
GLIDER = parse([".O.",
                "..O",
                "OOO"])

# Gosper glider gun — emits one SE glider every 30 ticks (LifeWiki canonical)
GOSPER = parse([
  "........................O...........",
  "......................O.O...........",
  "............OO......OO............OO",
  "...........O...O....OO............OO",
  "OO........O.....O...OO..............",
  "OO........O...O.OO....O.O...........",
  "..........O.....O.......O...........",
  "...........O...O....................",
  "............OO......................",
])

# Eater 1 (fishhook) — a still life that swallows a glider that hits its notch
EATER = parse(["OO.",
               "O.O",
               "..O",
               "..OO"])


# ============================ self-tests ==============================
if __name__ == "__main__":
    ok = True
    def check(name, cond):
        global ok; ok = ok and cond
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")

    # 1) a glider translates by (1,1) every 4 ticks, shape preserved
    g0 = set(GLIDER)
    g4 = run(g0, 4)
    check("glider is period-4 and moves (+1,+1)", normalize(g4) == normalize(g0)
          and translate(g0, 1, 1) == g4)
    g16 = run(g0, 16)
    check("glider after 16 ticks moved (+4,+4)", g16 == translate(g0, 4, 4))

    # 2) the Gosper gun emits exactly one glider every 30 ticks (a real stream)
    gun = set(GOSPER)
    pops = [len(run(set(GOSPER), t)) for t in (60, 90, 120, 150)]
    deltas = [pops[i+1] - pops[i] for i in range(len(pops)-1)]
    check("gun population grows by +5 every 30 ticks (one glider/period)",
          all(d == 5 for d in deltas))
    # isolate emitted objects as 8-connected components and confirm they're gliders
    def components(cells):
        cells = set(cells); seen = set(); comps = []
        for c in cells:
            if c in seen: continue
            stack = [c]; comp = set()
            while stack:
                p = stack.pop()
                if p in seen or p not in cells: continue
                seen.add(p); comp.add(p)
                x, y = p
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        if dx or dy: stack.append((x + dx, y + dy))
            comps.append(comp)
        return comps
    glider_phases = {normalize(run(set(GLIDER), k)) for k in range(4)}   # a glider has 4 phases
    def is_glider(c): return len(c) == 5 and normalize(c) in glider_phases
    comps = components(run(set(GOSPER), 200))
    gliders = [c for c in comps if is_glider(c)]
    downstream = [c for c in comps if min(x for x, _ in c) > 36]   # clear of the machinery
    check("gun has emitted a stream of real gliders",
          len(gliders) >= 5 and all(is_glider(c) for c in downstream))

    # 3) EATER is a still life, and it swallows a glider (placement found by search)
    check("eater is a still life", step(set(EATER)) == set(EATER))
    def eats(glider0, eater0, steps=60):
        after = run(glider0 | eater0, steps)
        return normalize(after) == normalize(eater0)      # only the eater remains
    found = None
    base_g = set(GLIDER)                                   # glider heading SE from origin
    for ex in range(2, 14):
        for ey in range(2, 14):
            e = translate(EATER, ex, ey)
            if not (base_g & e) and eats(base_g, e):
                found = (ex, ey); break
        if found: break
    check("eater cleanly swallows a glider (found placement %s)" % (found,), found is not None)
    globals()['EATER_OFFSET'] = found

    print("\nALL PASS" if ok else "\nSOME FAILED")
