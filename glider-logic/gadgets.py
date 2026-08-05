#!/usr/bin/env python3
"""
Routing gadgets for physically-routed glider logic — verified in *our* engine.

life.py gives us a signal (the glider), a signal source (the gun) and a signal
sink (the eater).  To actually *wire* anything you need two more things, and
neither of them is optional:

    1. a WIRE CORNER   — bend a glider stream 90 degrees without consuming it,
       so a signal can be routed to wherever the next gate happens to sit.
    2. a FAN-OUT       — copy one glider stream into two, so one signal can
       drive two gates.  Without it, every gate is single-use and you cannot
       build an adder (a carry has to go two places at once).

Both gadgets here are STABLE: the catalyst is a still life, it is restored
exactly after each signal passes, and it therefore works at any timing.  That
is what makes them usable as circuit components rather than as stunts.

    A) SNARK        Mike Playle, 25 Apr 2013.  52-cell stable still life;
                    the smallest/fastest stable 90-degree glider reflector.
                    In: NE-travelling glider.  Out: SE-travelling glider.

    B) DUPLICATOR   conwaylife.com/patterns/gliderduplicator.rle.  84-cell
                    stable still life.  In: one SE glider.  Out: two gliders
                    (one SE, one NW).  Catalyst restored exactly.

Compass convention: y increases DOWNWARD (screen coordinates), so SE = (+1,+1)
and NE = (+1,-1).  A glider's "lane" is the diagonal it can never leave.

Run this file to re-verify both from scratch:  python3 gadgets.py
"""
from life import step, run, translate, normalize, bbox, parse, GLIDER


# ------------------------------------------------------------------ RLE
def rle_parse(text, ox=0, oy=0):
    """Decode Golly RLE ('x = w, y = h, rule = ...' + run-length body) -> cells.

    'b' dead, 'o' alive, '$' end-of-row (with run count = row skip), '!' end.
    '#'-comment lines and the header line are ignored; body lines may wrap
    anywhere, including mid-token, so we join them before decoding.
    """
    body = []
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if s.lower().startswith("x"):           # header
            continue
        body.append(s)
    data = "".join(body)

    cells, x, y, num = set(), 0, 0, ""
    for ch in data:
        if ch.isdigit():
            num += ch
            continue
        n = int(num) if num else 1
        num = ""
        if ch == "b":
            x += n
        elif ch == "o":
            for i in range(n):
                cells.add((x + i + ox, y + oy))
            x += n
        elif ch == "$":
            y += n
            x = 0
        elif ch == "!":
            break
    return cells


# ------------------------------------------------- connectivity & gliders
def components(cells):
    """8-connected components, as a list of sets."""
    cells = set(cells)
    seen, comps = set(), []
    for c in cells:
        if c in seen:
            continue
        stack, comp = [c], set()
        while stack:
            p = stack.pop()
            if p in seen or p not in cells:
                continue
            seen.add(p)
            comp.add(p)
            x, y = p
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    if dx or dy:
                        stack.append((x + dx, y + dy))
        comps.append(comp)
    return comps


def _rot90(cells):
    """Rotate a quarter turn: (x,y) -> (-y,x), then normalize."""
    return normalize({(-y, x) for (x, y) in cells})


def _glider_phase_table():
    """All 16 glider appearances (4 directions x 4 phases) -> (direction, phase).

    GLIDER travels (+1,+1).  Rotating cells by (x,y)->(-y,x) rotates the
    travel direction the same way: (dx,dy) -> (-dy,dx).
    """
    table, cur, d = {}, set(GLIDER), (1, 1)
    for _ in range(4):
        for k in range(4):
            table[normalize(run(set(cur), k))] = (d, k)
        cur = _rot90(cur)
        d = (-d[1], d[0])
    return table


GLIDER_PHASES = _glider_phase_table()


def is_glider(comp):
    return len(comp) == 5 and normalize(comp) in GLIDER_PHASES


def glider_dir(comp):
    """Travel direction of a 5-cell glider component, as (dx,dy)."""
    return GLIDER_PHASES[normalize(comp)][0]


def glider_phase(comp):
    """Which of the 4 glider phases this component is showing (0..3)."""
    return GLIDER_PHASES[normalize(comp)][1]


def glider_lane(comp):
    """The diagonal lane a glider rides — invariant for its whole flight.

    The bounding box of a glider wobbles within its period, so we first run
    the glider forward to its canonical phase 0 (which only slides it along
    the same lane), then read the lane off the top-left corner:
    y0-x0 on the (+1,+1)/(-1,-1) diagonal, y0+x0 on the other.
    """
    d, k = GLIDER_PHASES[normalize(comp)]
    x0, y0, _, _ = bbox(run(set(comp), (4 - k) % 4))
    return (y0 - x0) if d[0] * d[1] > 0 else (y0 + x0)


def split_gliders(cells):
    """(list of glider components, everything else) — 'else' is the catalyst."""
    gs = [c for c in components(cells) if is_glider(c)]
    rest = set(cells) - (set().union(*gs) if gs else set())
    return gs, rest


# ======================================================================
# A) THE SNARK — stable 90-degree glider reflector
# ======================================================================
# Verbatim from conwaylife.com/patterns/snark.rle, mirrored at
#   https://raw.githubusercontent.com/thomasdunn/cellular-automata-patterns/
#       master/patterns/conwaylife/snark.rle
# (byte-identical copy also at Tw1ddle/game-of-life/src/embed/snark.rle).
# The file ships the reflector *plus* one demonstration input glider.
SNARK_RLE = """#N Snark
#O Mike Playle
#C The fastest and smallest 90-degree stable glider reflector (as of
#C June 2013).
#C www.conwaylife.com/wiki/Snark
x = 17, y = 23, rule = B3/S23
6b2o3b2o$6b2o2bob3o$10bo4bo$6b4ob2o2bo$6bo2bobobob2o$9bobobobo$10b2obo
bo$14bo2$2o$bo7b2o$bobo5b2o$2b2o7$12b2o$3b2o7bo$2bobo8b3o$4bo10bo!"""

_snark_full = rle_parse(SNARK_RLE)
_snark_gliders, _snark_cat = split_gliders(_snark_full)

#: the reflector itself: a 52-cell still life — two eater 1s, two blocks and
#: the "31.4" catalyst that is the heart of it.  Origin = RLE cell (0,0).
SNARK = frozenset(_snark_cat)

#: the demonstration input glider that ships with the RLE.
SNARK_DEMO_GLIDER = frozenset(_snark_gliders[0])

SNARK_IN_DIR = (1, -1)     # input glider travels NE  (+x, -y)
SNARK_OUT_DIR = (1, 1)     # output glider travels SE  (+x, +y)
SNARK_IN_LANE = 22         # input lane:  x0 + y0 == 22  (phase-0 bbox corner)
SNARK_OUT_LANE = -2        # output lane: y0 - x0 == -2
SNARK_RECOVERY = 55        # catalyst is back to the still life by t = 55
SNARK_BBOX = bbox(SNARK)   # (0, 0, 16, 22)


def place_snark(dx=0, dy=0):
    """The Snark catalyst, translated so its RLE origin lands on (dx,dy)."""
    return translate(SNARK, dx, dy)


def snark_input_glider(dx=0, dy=0, back=0):
    """A glider on the Snark's input lane, `back` cells further out along it.

    `back` slides the glider backwards along its own NE lane (-1,+1 per unit),
    which only delays arrival by 4*back ticks — the lane is unchanged, and the
    Snark is stable, so any `back` works.
    """
    return translate(SNARK_DEMO_GLIDER, dx - back, dy + back)


# ======================================================================
# B) THE DUPLICATOR — stable 1-glider-in / 2-gliders-out fan-out
# ======================================================================
# Verbatim from conwaylife.com/patterns/gliderduplicator.rle, mirrored at
#   https://raw.githubusercontent.com/thomasdunn/cellular-automata-patterns/
#       master/patterns/conwaylife/gliderduplicator.rle
# The stored snapshot is mid-operation: it carries two in-flight gliders and a
# 6-cell spark that has not settled yet.  Strip the gliders and let it relax
# for 8 ticks and what remains is an 84-cell still life — the actual gadget.
DUPLICATOR_RLE = """#N gliderduplicator.rle
#C http://conwaylife.com/wiki/Glider_duplicator
#C http://conwaylife.com/patterns/gliderduplicator.rle
x = 76, y = 53, rule = B3/S23
obo$b2o$bo17$20bo$21b2o$20b2o5$51b2o$52bo$52bobo$42bo10b2o$40b3o$39bo$
39b2o$24b2o48b2o$25bo48b2o$25bob2o$26bo2bo23bo$27b2o24bo$42b2o9b3o$42b
2o11bo4$51bo3b2o$50bobo3bo$49bobo3bo$45b2obobo3bo$45b2obo2b4obo5b2o$
49bobo3bobo5bo$45b2ob2o2bo2bobo2b3o$46bobo2b2o3bo3bo$34b2o10bobo$34b2o
11bo!"""

_dup_full = rle_parse(DUPLICATOR_RLE)
_dup_gliders, _dup_raw = split_gliders(_dup_full)

#: the fan-out catalyst: 84-cell still life, origin = RLE cell (0,0).
DUPLICATOR = frozenset(run(set(_dup_raw), 8))

#: the input glider of the shipped snapshot (the one on lane y-x == 0).
DUP_DEMO_GLIDER = frozenset(min(_dup_gliders, key=lambda c: bbox(c)[0]))

DUP_IN_DIR = (1, 1)        # input glider travels SE, entering from the NW
DUP_IN_LANE = -1           # input lane:  y0 - x0 == -1  (phase-0 bbox corner)
DUP_OUT_DIRS = ((1, 1), (-1, -1))   # one SE copy, one NW copy
DUP_OUT_LANES = (-23, -47)          # y0 - x0 for the SE / NW output
DUP_RECOVERY = 350         # catalyst is back to the still life by t = 350
DUP_BBOX = bbox(DUPLICATOR)  # (24, 26, 75, 52)


def place_duplicator(dx=0, dy=0):
    """The duplicator catalyst, translated so its RLE origin lands on (dx,dy)."""
    return translate(DUPLICATOR, dx, dy)


def dup_input_glider(dx=0, dy=0, back=0):
    """A glider on the duplicator's input lane, `back` cells further out."""
    return translate(DUP_DEMO_GLIDER, dx - back, dy - back)


# ======================================================================
# verification
# ======================================================================
DIRNAME = {(1, 1): "SE", (-1, 1): "SW", (-1, -1): "NW", (1, -1): "NE"}


def _fire(catalyst, gliders, ticks):
    """Run catalyst + gliders for `ticks`, return (glider comps, leftover)."""
    s = set(catalyst)
    for g in gliders:
        s |= set(g)
    s = run(s, ticks)
    return split_gliders(s)


def verify_snark():
    """One NE glider in -> exactly one SE glider out, catalyst restored."""
    notes = []
    cat = set(SNARK)
    ok = (step(cat) == cat)
    notes.append(f"catalyst is a {len(cat)}-cell still life: {ok}")

    gin = set(SNARK_DEMO_GLIDER)
    in_dir = glider_dir(gin)
    in_lane = glider_lane(gin)

    gs, rest = _fire(cat, [gin], 300)
    one_out = (len(gs) == 1)
    restored = (rest == cat)
    out_dir = glider_dir(gs[0]) if one_out else None
    out_lane = glider_lane(gs[0]) if one_out else None
    turned = one_out and out_dir == (-in_dir[1], in_dir[0])   # 90-deg turn
    notes.append(f"t=300: {len(gs)} glider(s) out, catalyst restored: {restored}")
    lanes_ok = (in_lane == SNARK_IN_LANE and out_lane == SNARK_OUT_LANE)
    notes.append(f"lanes match the documented geometry: {lanes_ok}")
    ok = ok and one_out and restored and turned and lanes_ok

    # timing independence: any of the 4 glider phases / any arrival time works
    phases_ok = True
    for j in range(8):
        g = run(set(gin), j)                      # same lane, j ticks later
        gs2, rest2 = _fire(cat, [g], 300)
        phases_ok &= (len(gs2) == 1 and rest2 == cat
                      and glider_dir(gs2[0]) == out_dir)
    notes.append(f"works at all 4 input phases / arbitrary timing: {phases_ok}")
    ok = ok and phases_ok

    # the lane is unique: nudging the input off it breaks the reflection
    neighbours = []
    for k in (-2, -1, 1, 2):
        g = translate(gin, k, k)                  # perpendicular shift
        gs3, rest3 = _fire(cat, [g], 250)
        neighbours.append(len(gs3) == 1 and rest3 == cat)
    lane_unique = not any(neighbours)
    notes.append(f"adjacent lanes (+-1, +-2) do NOT reflect: {lane_unique}")
    ok = ok and lane_unique

    # it is reusable: two gliders 60 ticks apart give two reflections
    g2 = snark_input_glider(back=15)              # 15 cells back = 60 ticks
    gs4, rest4 = _fire(cat, [gin, g2], 400)
    reusable = (len(gs4) == 2 and rest4 == cat
                and all(glider_dir(c) == out_dir for c in gs4))
    notes.append(f"reusable — 2 gliders 60t apart -> 2 reflections: {reusable}")
    ok = ok and reusable

    return ok, {
        "in_dir": DIRNAME[in_dir], "in_lane": f"x0+y0=={in_lane}",
        "out_dir": DIRNAME[out_dir] if out_dir else "?",
        "out_lane": f"y0-x0=={out_lane}",
        "notes": notes,
    }


def verify_duplicator():
    """One SE glider in -> exactly two gliders out, catalyst restored."""
    notes = []
    cat = set(DUPLICATOR)
    ok = (step(cat) == cat)
    notes.append(f"catalyst is an {len(cat)}-cell still life: {ok}")

    gin = set(DUP_DEMO_GLIDER)
    in_dir, in_lane = glider_dir(gin), glider_lane(gin)

    gs, rest = _fire(cat, [gin], 450)
    two_out = (len(gs) == 2)
    restored = (rest == cat)
    outs = sorted(((glider_dir(c), glider_lane(c)) for c in gs),
                  key=lambda t: t[0]) if two_out else []
    notes.append(f"t=450: {len(gs)} glider(s) out, catalyst restored: {restored}")
    dirs_ok = two_out and {d for d, _ in outs} == set(DUP_OUT_DIRS)
    lanes_ok = (in_lane == DUP_IN_LANE
                and {l for _, l in outs} == set(DUP_OUT_LANES))
    notes.append(f"two distinct output directions {DUP_OUT_DIRS}: {dirs_ok}")
    notes.append(f"lanes match the documented geometry: {lanes_ok}")
    ok = ok and two_out and restored and dirs_ok and lanes_ok

    # timing independence — hold the input further back along its lane
    timing_ok = True
    for back in (4, 20, 41):
        g = dup_input_glider(back=back)
        gs2, rest2 = _fire(cat, [g], 450 + 4 * back)
        timing_ok &= (len(gs2) == 2 and rest2 == cat)
    notes.append(f"works at arbitrary input timing: {timing_ok}")
    ok = ok and timing_ok

    return ok, {
        "in_dir": DIRNAME[in_dir], "in_lane": f"y0-x0=={in_lane}",
        "out": [f"{DIRNAME[d]} on y0-x0=={l}" for d, l in outs],
        "notes": notes,
    }


def main():
    print("=" * 68)
    print("Life routing gadgets — verified against life.py (B3/S23)")
    print("=" * 68)
    failed = []

    ok, info = verify_snark()
    if not ok:
        failed.append("SNARK")
    print(f"\nSNARK reflects glider 90deg + restores: {'PASS' if ok else 'FAIL'} "
          f"(in={info['in_dir']} lane {info['in_lane']}, out={info['out_dir']} "
          f"lane {info['out_lane']})")
    for n in info["notes"]:
        print(f"    - {n}")
    print(f"    - geometry: catalyst bbox {SNARK_BBOX}, "
          f"recovery time {SNARK_RECOVERY} ticks")

    ok, info = verify_duplicator()
    if not ok:
        failed.append("DUPLICATOR")
    print(f"\nDUPLICATOR 1->2 + restores: {'PASS' if ok else 'FAIL'} "
          f"(in={info['in_dir']} lane {info['in_lane']}, "
          f"out={' + '.join(info['out']) if info['out'] else '?'})")
    for n in info["notes"]:
        print(f"    - {n}")
    print(f"    - geometry: catalyst bbox {DUP_BBOX}, "
          f"recovery time ~{DUP_RECOVERY} ticks")

    print()
    if failed:
        print("FAILED: " + ", ".join(failed))
    else:
        print("ALL PASS")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
