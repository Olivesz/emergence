#!/usr/bin/env python3
"""
gun_routing — a live glider gun firing a continuous stream that gets ROUTED:
turned 90 degrees through the Snark reflector, in raw Conway's Life (B3/S23).

The crux
--------
Our workhorse source, the Gosper gun, fires every 30 ticks — but the Snark
needs ~55 ticks to rebuild its catalyst after each reflection.  Feed it a raw
Gosper stream and the second glider arrives mid-repair and wrecks it.  The fix
here is approach (A) from the design notes: use a TRUE PERIOD-60 GLIDER GUN,
so the stream arrives pre-spaced at exactly the Snark's verified reusable rate
(gadgets.py proves two gliders 60 ticks apart give two clean reflections).

The gun is Bill Gosper's first true period-60 glider gun (two queen-bee-shuttle
mechanisms geared together), taken verbatim from the conwaylife.com pattern
collection via its GitHub mirror:

    https://raw.githubusercontent.com/thomasdunn/cellular-automata-patterns/
        master/patterns/conwaylife/period60glidergun.rle
    http://conwaylife.com/wiki/Period-60_glider_gun

Geometry (y grows DOWN, so NE = (+1,-1), SE = (+1,+1)):

    - The RLE fires SE; we rotate it three quarter-turns so it fires NE, and
      strip the one in-flight glider it ships with (machinery = 108 cells).
    - The rotated gun emits on lane x0+y0 == 19; translating by (-44,+47)
      shifts the lane by dx+dy = +3, landing it exactly on the Snark's input
      lane x0+y0 == 22 with the gun sitting to the SOUTH-WEST of the Snark.
    - Snark catalyst at the origin (bbox (0,0)-(16,22)).  Every NE glider is
      reflected into one SE glider on the output lane y0-x0 == -2, which then
      flies off to the SE forever — a continuously growing routed stream.

`python3 gun_routing.py` re-verifies the whole thing from scratch and
(re)writes gun_routing.rle, the paste-into-a-viewer snapshot of tick 0.

One subtlety the checks must survive: the gun's internal shuttle reaction
passes through 5-cell phases that are momentarily IDENTICAL to a glider (a
Gosper-style gun literally assembles its glider inside itself).  Those live
inside the gun's bounding box and never escape, so "stray glider" detection
only applies to gliders found OUTSIDE the gun's footprint.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from life import step, run, translate, normalize, bbox
from gadgets import (rle_parse, split_gliders, glider_dir, glider_lane, DIRNAME,
                     SNARK, SNARK_IN_LANE, SNARK_OUT_LANE, SNARK_RECOVERY,
                     place_snark)

HERE = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------- the gun
# Verbatim: conwaylife.com pattern collection (GitHub mirror, see module doc).
P60_GUN_RLE = """#N Period-60 glider gun
#O Bill Gosper
#C The first true period 60 glider gun, found by Bill Gosper.
#C http://conwaylife.com/wiki/Period-60_glider_gun
x = 39, y = 27, rule = B3/S23
27bo$27b4o$11bo16b4o$10bobo5b2o8bo2bo5b2o$3b2o3b2o3bo14b4o5b2o$3b2o3b
2o3bo4bobob2o3b4o$8b2o3bo5b2o3bo2bo$10bobo10bo$11bo8bo2bo2$26bobo$28bo
$24bo$26bo$25bo2$11b2o$11b2o4bo$2o6b2o6b5ob2o$2o5b3o5bo2b2o4bo$8b2o5b
2o8bo12bo$11b2o4bo7bo10bobo$11b2o12bo11b2o$24bo8b2o$22b2o9bobo$35bo$
35b2o!"""

GUN_PERIOD = 60

def rot90(cells):
    """Quarter turn (x,y) -> (-y,x), re-normalized to bbox corner (0,0)."""
    return set(normalize({(-y, x) for (x, y) in cells}))


def build_gun():
    """The p60 gun machinery, rotated to fire NE, at its normalized origin."""
    gun = rle_parse(P60_GUN_RLE)
    for _ in range(3):                     # SE -> SW -> NW -> NE
        gun = rot90(gun)
    gliders, machinery = split_gliders(gun)   # drop the shipped in-flight glider
    return set(machinery)


# ------------------------------------------------------------- placement
# Rotated gun emits NE on lane x0+y0 == 19; translation shifts a NE lane by
# dx+dy, so dx+dy == 3 puts the stream on the Snark's input lane (22).  The
# specific split (-44,+47) parks the gun SW of the Snark, clear of everything.
GUN_DX, GUN_DY = -44, 47
SNARK_AT = (0, 0)                          # Snark catalyst at the origin


def build_world():
    """(world, gun_machinery, snark) — the demo pattern at tick 0."""
    gun = translate(build_gun(), GUN_DX, GUN_DY)
    snark = place_snark(*SNARK_AT)
    assert not (gun & snark)
    return gun | snark, gun, snark


# ------------------------------------------------------------- RLE writer
def to_rle(cells, comments=()):
    """Golly RLE for a cell set (translated so the bbox corner is (0,0))."""
    x0, y0, x1, y1 = bbox(cells)
    w, h = x1 - x0 + 1, y1 - y0 + 1
    grid = {(x - x0, y - y0) for (x, y) in cells}
    lines = [f"#C {c}" for c in comments]
    lines.append(f"x = {w}, y = {h}, rule = B3/S23")

    tokens = []
    blank_rows = 0
    for y in range(h):
        row = sorted(x for x in range(w) if (x, y) in grid)
        if not row:
            blank_rows += 1
            continue
        if y > 0:
            n = 1 + blank_rows
            tokens.append(("$" if n == 1 else f"{n}$"))
        blank_rows = 0
        x = 0
        i = 0
        while i < len(row):
            if row[i] > x:                              # run of dead cells
                n = row[i] - x
                tokens.append("b" if n == 1 else f"{n}b")
                x = row[i]
            j = i
            while j + 1 < len(row) and row[j + 1] == row[j] + 1:
                j += 1
            n = j - i + 1                               # run of live cells
            tokens.append("o" if n == 1 else f"{n}o")
            x += n
            i = j + 1
    tokens.append("!")

    body, cur = [], ""
    for tok in tokens:
        if len(cur) + len(tok) > 69:
            body.append(cur)
            cur = ""
        cur += tok
    body.append(cur)
    return "\n".join(lines + body) + "\n"


# ------------------------------------------------------------ verification
def check(name, cond, results):
    results.append((name, bool(cond)))
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
    return bool(cond)


def free_gliders(gliders, gun_box):
    """Glider components clear of the gun's footprint (see module doc)."""
    gx0, gy0, gx1, gy1 = gun_box
    out = []
    for g in gliders:
        x0, y0, x1, y1 = bbox(g)
        if x1 < gx0 - 2 or x0 > gx1 + 2 or y1 < gy0 - 2 or y0 > gy1 + 2:
            out.append(g)
    return out


def main():
    results = []
    world, gun, snark = build_world()
    gun_box = bbox(gun)

    print("=" * 68)
    print("gun_routing — a p60 gun stream turned 90 degrees by a Snark")
    print("=" * 68)

    # ---- 1) the gun, alone: a true period-60 NE gun on the Snark's lane
    print("\n[1] the gun (Gosper's true p60 gun, rotated to fire NE)")
    check(f"gun machinery is {len(gun)} cells (108 expected)",
          len(gun) == 108, results)
    r0 = split_gliders(gun)[1]
    r60 = split_gliders(run(set(gun), GUN_PERIOD))[1]
    check(f"machinery is periodic with period {GUN_PERIOD}", r0 == r60, results)

    t_first = None
    for t in range(0, 200):
        if free_gliders(split_gliders(run(set(gun), t))[0], gun_box):
            t_first = t
            break
    check(f"gun emits its first free glider at t={t_first}",
          t_first is not None, results)

    T_ALONE = 600
    gs = free_gliders(split_gliders(run(set(gun), T_ALONE))[0], gun_box)
    kinds = {(DIRNAME[glider_dir(g)], glider_lane(g)) for g in gs}
    expected_emitted = (T_ALONE - t_first) // GUN_PERIOD + 1
    check(f"every emitted glider travels NE on lane x0+y0=={SNARK_IN_LANE} "
          f"(got {sorted(kinds)})",
          kinds == {("NE", SNARK_IN_LANE)}, results)
    check(f"one glider per {GUN_PERIOD} ticks: {len(gs)} free gliders by "
          f"t={T_ALONE} ({expected_emitted} expected)",
          len(gs) == expected_emitted, results)

    # ---- 2) rate vs recovery
    print("\n[2] rate vs Snark recovery")
    check(f"gun period {GUN_PERIOD} >= Snark recovery {SNARK_RECOVERY} "
          f"(a raw p30 Gosper stream would NOT fit)",
          GUN_PERIOD >= SNARK_RECOVERY, results)

    # ---- 3) the combined system, long run
    print("\n[3] combined system: gun + Snark, sustained routing")
    T = 26 * GUN_PERIOD                       # 1560 ticks
    # gun-alone machinery cycle, for exact debris comparison at matching phase
    cycle, ga = {}, set(gun)
    for t in range(GUN_PERIOD):
        cycle[t] = split_gliders(ga)[1]
        ga = step(ga)

    n_out_hist, clean, strays, slipped = [], [], [], []
    w = set(world)
    for t in range(T + 1):
        gsw, restw = split_gliders(w)
        n_out = 0
        for g in free_gliders(gsw, gun_box):
            d, lane = glider_dir(g), glider_lane(g)
            if d == (1, 1) and lane == SNARK_OUT_LANE:
                n_out += 1                     # a routed output glider
            elif d == (1, -1) and lane == SNARK_IN_LANE:
                if bbox(g)[0] > 20:            # past the Snark: not consumed?!
                    slipped.append(t)
            else:
                strays.append((t, DIRNAME[d], lane))
        n_out_hist.append(n_out)
        if restw == (cycle[t % GUN_PERIOD] | snark):
            clean.append(t)                    # Snark restored, zero debris
        w = step(w)

    n_out = n_out_hist[-1]
    t_first_out = next((t for t, n in enumerate(n_out_hist) if n), None)
    check(f"a reflected SE glider appears (first at t={t_first_out})",
          t_first_out is not None, results)
    check(f"{n_out} gliders routed through the corner in {T} ticks "
          f"(>= 20 required)", n_out >= 20, results)

    deltas = [n_out_hist[t + GUN_PERIOD] - n_out_hist[t]
              for t in range(t_first_out, T - GUN_PERIOD, GUN_PERIOD)]
    check(f"exactly one new routed glider per {GUN_PERIOD}-tick period, "
          f"every period after the first ({len(deltas)} periods checked)",
          all(d == 1 for d in deltas), results)

    expected_arrivals = (T - t_first_out) // GUN_PERIOD + 1
    check(f"1:1 in/out — {n_out} out vs {expected_arrivals} arrivals",
          n_out == expected_arrivals, results)
    check("no glider ever slips past the Snark unconsumed",
          not slipped, results)
    check(f"no stray gliders on any other lane/direction "
          f"({len(strays)} seen)", not strays, results)

    per_period_clean = [any(p * GUN_PERIOD <= t < (p + 1) * GUN_PERIOD
                            for t in clean) for p in range(T // GUN_PERIOD)]
    check("Snark catalyst + gun machinery restored EXACTLY (zero debris) "
          "at least once in every period", all(per_period_clean), results)
    check(f"still clean at the final tick t={T}", T in clean, results)
    last_clean = clean[-1] if clean else None
    if last_clean is not None:
        wc = run(set(world), last_clean)
        sx0, sy0, sx1, sy1 = bbox(snark)
        in_snark = {(x, y) for (x, y) in wc
                    if sx0 <= x <= sx1 and sy0 <= y <= sy1} - set().union(
                        *(free_gliders(split_gliders(wc)[0], gun_box) or [set()]))
        check(f"cells in the Snark's box at t={last_clean} are exactly the "
              "52-cell Snark still life", in_snark == set(snark), results)

    # ---- 4) write the demo RLE and round-trip it
    print("\n[4] gun_routing.rle")
    rle = to_rle(world, comments=[
        "gun_routing: Gosper's true p60 glider gun (conwaylife.com pattern",
        "collection) rotated to fire NE, feeding Mike Playle's Snark, which",
        "routes the stream 90 degrees onto a SE lane.  Raw B3/S23.",
        "Gun period 60 >= Snark recovery 55 -- a raw p30 Gosper stream would",
        "destroy the reflector.  Generated by gun_routing.py.",
    ])
    path = os.path.join(HERE, "gun_routing.rle")
    with open(path, "w") as f:
        f.write(rle)
    check("gun_routing.rle round-trips through the RLE parser",
          rle_parse(rle) == set(normalize(world)), results)
    print(f"      wrote {path} ({len(world)} cells, bbox {bbox(world)})")

    # ---- summary
    failed = [n for n, ok in results if not ok]
    print("\n" + "-" * 68)
    print(f"gun:    true p60 glider gun (Bill Gosper), 108-cell machinery,")
    print(f"        rotated to fire NE, placed at ({GUN_DX},{GUN_DY}), "
          f"bbox {gun_box}")
    print(f"snark:  at {SNARK_AT}, bbox {bbox(snark)}, recovery "
          f"{SNARK_RECOVERY} ticks")
    print(f"route:  NE stream on lane x0+y0=={SNARK_IN_LANE}  ->  90-degree "
          f"turn  ->  SE stream on lane y0-x0=={SNARK_OUT_LANE}")
    print(f"run:    {T} ticks, {n_out} gliders in -> {n_out} routed out, "
          f"catalyst restored every period")
    print("-" * 68)
    print("ALL PASS" if not failed else "FAILED: " + ", ".join(failed))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
