#!/usr/bin/env python3
"""
Signal CROSSING for physically-routed glider logic — a TIMED WEAVE,
verified in raw B3/S23.  ** This is NOT an any-phase crossover. **

A multi-bit ripple adder needs carry lanes to cross data lanes.  Two ways
that could work:

  A) a STABLE crossover gadget — a still life that lets two glider paths
     cross at any relative timing, like the Snark lets one path turn.
     FINDING: no such small gadget exists to fetch.  The pattern mirrors we
     can reach were searched:
       - github.com/thomasdunn/cellular-automata-patterns (2398 files, the
         mirror our Snark/duplicator came from): the only "cross*" entries
         are cross.rle / cross2.rle / crosssurface.rle — the period-3
         "cross" OSCILLATOR family, not a signal crossover; linecrosser.rle
         is a spaceship stunt, not a signal gadget.
       - conwaylife.com (wiki/Crossover, patterns/) answers HTTP 403 to
         non-browser fetches, as expected.
     This matches the literature: in STABLE Life circuitry, two signal
     paths are crossed either with three XOR gates (a whole gate-level
     construction) or with Herschel-conduit plumbing — hundreds of cells of
     machinery, not a Snark-sized catalyst.  At the single-still-life scale
     a true any-phase glider crossover is not a thing one fetches.

  B) what Life circuitry actually exploits every day: a glider lane is
     TRANSPARENT.  Two perpendicular corridors may share a crossing point,
     and as long as the two gliders never occupy the crossing REGION at the
     same ticks, each sails through as if the other's corridor were not
     there.  The price is a TIMING DISCIPLINE — the circuit must schedule
     the two signals apart.  In our routed gates timing is fixed by
     placement, so the discipline is enforceable; this file measures
     exactly how much clearance is required.

This file delivers (B), honestly labeled, and verifies it three ways:

  1. each glider's solo trajectory (direction, lane, per-tick cell sets,
     and its arrival ticks at the crossing cell) is MEASURED by simulation;
  2. with a chosen safe offset the combined run is compared to the union of
     the solo runs AT EVERY TICK — the strongest possible statement: the
     two signals provably never influence one another, so direction, lane
     and the entire tick schedule of each are preserved bit-exact;
  3. the relative offset is scanned across a full window and every offset
     is classified, so the UNSAFE window (where the gliders really do
     collide) is exhibited rather than assumed — the hazard is real, and
     the timing discipline is what makes the crossing work.

Then the same weave is verified IN CIRCUIT: a Snark reflects a carry-style
signal 90 degrees and its output corridor crosses a data-style corridor —
catalyst restored exactly, both signals bit-exact.  That is the actual
adder use-case: routing a carry over a data line.

On PASS the initial cells of the working crossing are written to
crossover.rle.

Run:  python3 crossover.py
"""
from life import step, run, translate, normalize, bbox, GLIDER
from gadgets import (components, is_glider, glider_dir, glider_lane,
                     split_gliders, DIRNAME, place_snark, snark_input_glider,
                     SNARK, SNARK_BBOX)


# ------------------------------------------------------------- gliders
#: SE glider (+1,+1) at the origin, and its mirror, a NE glider (+1,-1).
G_SE = frozenset(GLIDER)
G_NE = frozenset(normalize({(x, -y) for (x, y) in GLIDER}))


def delay_glider(g, d, dv):
    """The same glider, its whole schedule shifted d ticks LATER (d may be <0).

    Sliding a glider k cells backwards along its own lane delays it 4k ticks;
    running it j ticks forward advances it j.  Pick k,j with 4k - d in [0,3].
    """
    k = (d + 3) // 4
    j = 4 * k - d
    return run(translate(g, -k * dv[0], -k * dv[1]), j)


def trajectory(cells, ticks):
    """[state at t=0, t=1, ... t=ticks] — the full measured history."""
    traj, s = [set(cells)], set(cells)
    for _ in range(ticks):
        s = step(s)
        traj.append(s)
    return traj


def zone(cell, r=2):
    """The (2r+1)x(2r+1) block centred on `cell` — the crossing ZONE.

    A glider's live cells ride a 3-wide band that is offset a little from
    the 1-cell lane LINE named by glider_lane (the phase-0 bbox corner), so
    presence at the crossing is measured against this small zone, not the
    single line cell.
    """
    cx, cy = cell
    return {(cx + dx, cy + dy) for dx in range(-r, r + 1)
            for dy in range(-r, r + 1)}


def occupancy(traj, cells):
    """Sorted ticks at which any of `cells` is alive — measured, not derived."""
    cells = set(cells)
    return [t for t, s in enumerate(traj) if s & cells]


def never_interact(combined_traj, tA, tB):
    """True iff combined == soloA UNION soloB at EVERY tick (zero influence)."""
    return all(c == a | b for c, a, b in zip(combined_traj, tA, tB))


def classify(tA, solo_b0, d, dv, ticks):
    """Run A against B-delayed-by-d and classify the crossing.

    Returns (verdict, B_initial) with verdict one of
      'SAFE'    combined equals union of solos at every tick — no influence;
      'HEALED'  they touched but both exit bit-exact on schedule (would still
                be usable; in practice this never happens and we don't rely
                on it);
      'UNSAFE'  the signals damage each other.
    """
    b0 = delay_glider(solo_b0, d, dv)
    tB = trajectory(b0, ticks)
    tC = trajectory(tA[0] | tB[0], ticks)
    if never_interact(tC, tA, tB):
        return "SAFE", b0
    if tC[-1] == tA[-1] | tB[-1]:
        return "HEALED", b0
    return "UNSAFE", b0


def unsafe_ranges(ds):
    """Contiguous ranges in a sorted list of ints, as (lo, hi) pairs."""
    if not ds:
        return []
    out, lo, prev = [], ds[0], ds[0]
    for d in ds[1:]:
        if d != prev + 1:
            out.append((lo, prev))
            lo = d
        prev = d
    out.append((lo, prev))
    return out


# ------------------------------------------------------------- RLE out
def to_rle(cells, comments=()):
    """Golly RLE (B3/S23) of `cells`, translated to its bbox origin."""
    x0, y0, x1, y1 = bbox(cells)
    toks = []
    empty_rows = 0
    for y in range(y0, y1 + 1):
        row = [1 if (x, y) in cells else 0 for x in range(x0, x1 + 1)]
        while row and row[-1] == 0:
            row.pop()
        if not row:
            empty_rows += 1
            continue
        if toks:
            n = 1 + empty_rows
            toks.append(("%d$" % n) if n > 1 else "$")
        empty_rows = 0
        i = 0
        while i < len(row):
            j = i
            while j < len(row) and row[j] == row[i]:
                j += 1
            n, ch = j - i, "o" if row[i] else "b"
            toks.append(("%d%s" % (n, ch)) if n > 1 else ch)
            i = j
    toks.append("!")
    body, line, lines = "".join(toks), "", []
    for i in range(0, len(body), 70):
        lines.append(body[i:i + 70])
    head = ["#C %s" % c for c in comments]
    head.append("x = %d, y = %d, rule = B3/S23" % (x1 - x0 + 1, y1 - y0 + 1))
    return "\n".join(head + lines) + "\n"


# ======================================================================
# 1) the bare weave: SE corridor x NE corridor, one crossing cell
# ======================================================================
def build_weave():
    """Geometry: A rides SE on lane y-x==la; B rides NE on lane x+y==lb.
    The two lane lines meet in exactly one cell, the crossing."""
    A0 = set(G_SE)                                   # SE, near the origin
    la = glider_lane(A0)                             # measured, not assumed
    lb = la + 40                                     # same parity => 1 cell
    cross = ((lb - la) // 2, (lb + la) // 2)

    b = translate(G_NE, 0, lb - glider_lane(G_NE))   # onto lane x+y == lb
    assert glider_lane(b) == lb
    s = (cross[0] - 22) - bbox(b)[0]                 # slide SW along the lane
    B0 = translate(b, s, -s)
    assert glider_lane(B0) == lb
    return A0, B0, la, lb, cross


def verify_weave(ticks=220, scan=range(-40, 41)):
    ok, notes = True, []
    A0, B0, la, lb, cross = build_weave()
    tA = trajectory(A0, ticks)

    # --- solo trajectories, measured -----------------------------------
    Z = zone(cross)
    occA = occupancy(tA, Z)
    tB0 = trajectory(B0, ticks)
    occB0 = occupancy(tB0, Z)
    c1 = ok_ = bool(occA) and bool(occB0)
    span = lambda o: f"{o[0]}..{o[-1]}" if o else "never"
    notes.append("both solo gliders really sweep the 5x5 crossing zone at "
                 f"{cross} (A t={span(occA)}, B_base t={span(occB0)}): {ok_}")
    if not c1:
        return False, notes, None, None
    dirA, dirB = glider_dir(tA[-1]), glider_dir(tB0[-1])
    ok_ = (dirA == (1, 1) and dirB == (1, -1)
           and glider_lane(tA[-1]) == la and glider_lane(tB0[-1]) == lb)
    notes.append(f"solo: A={DIRNAME[dirA]} lane y-x=={la}, "
                 f"B={DIRNAME[dirB]} lane x+y=={lb}, perpendicular: {ok_}")
    ok = ok and c1 and ok_

    # the two corridors' centre lines share exactly one cell by construction
    notes.append(f"lane lines cross in exactly one cell {cross} "
                 f"(parity la={la}, lb={lb}): True")

    # --- offset scan: delta = arrival(B) - arrival(A) at the crossing --
    d0 = occB0[0] - occA[0]                          # base offset, measured
    verdicts = {}
    for delta in scan:
        v, b = classify(tA, B0, delta - d0, (1, -1), ticks)
        # sanity: the constructed delay really moved the arrival schedule
        if v == "SAFE":
            got = occupancy(trajectory(b, ticks), Z)
            assert got and got[0] - occA[0] == delta, (delta, got)
        verdicts[delta] = (v, b)
    unsafe = sorted(d for d, (v, _) in verdicts.items() if v == "UNSAFE")
    healed = sorted(d for d, (v, _) in verdicts.items() if v == "HEALED")
    safe = sorted(d for d, (v, _) in verdicts.items() if v == "SAFE")
    ok_ = bool(unsafe) and bool(safe)
    notes.append(f"offset scan delta in [{scan.start},{scan.stop-1}]: "
                 f"{len(safe)} safe, {len(unsafe)} unsafe, {len(healed)} healed")
    notes.append(f"UNSAFE window (the hazard is real): "
                 f"{unsafe_ranges(unsafe)}" + (f", healed={healed}" if healed else ""))
    ok = ok and ok_

    # --- the chosen safe offset, verified in full ----------------------
    # prefer a safe offset past the unsafe window whose crossing-zone
    # schedule is fully disjoint from A's (neighbourhood-level clearance)
    after = [d for d in safe if d > (unsafe[-1] if unsafe else 0)]
    delta_star = Bs = tB = None
    for d in after + list(reversed(safe)):
        tb = trajectory(verdicts[d][1], ticks)
        if not set(occA) & set(occupancy(tb, Z)):
            delta_star, Bs, tB = d, verdicts[d][1], tb
            break
    if delta_star is None:
        notes.append("no safe offset with disjoint zone schedule — weave FAILS")
        return False, notes, None, None
    tC = trajectory(A0 | Bs, ticks)

    ok_ = never_interact(tC, tA, tB)
    notes.append(f"chosen delta={delta_star:+d}: combined == soloA UNION soloB "
                 f"at EVERY tick 0..{ticks} (zero mutual influence): {ok_}")
    ok = ok and ok_

    gs, rest = split_gliders(tC[-1])
    ok_ = (len(gs) == 2 and rest == set())
    notes.append(f"t={ticks}: exactly 2 gliders, residue == catalyst set "
                 f"(empty — the weave needs no catalyst): {ok_}")
    ok = ok and ok_
    outs = sorted((glider_dir(g), glider_lane(g)) for g in gs)
    ok_ = outs == sorted([((1, 1), la), ((1, -1), lb)])
    notes.append(f"outputs unchanged: SE on y-x=={la} and NE on x+y=={lb}: {ok_}")
    ok = ok and ok_

    occB = occupancy(tB, Z)
    ok_ = not (set(occA) & set(occB))
    notes.append(f"crossing-zone schedules disjoint (A t={span(occA)}, "
                 f"B t={span(occB)} — B trails A by {occB[0]-occA[-1]} clear "
                 f"ticks): {ok_}")
    ok = ok and ok_

    hazard = set().union(*tA) & set().union(*tB)
    notes.append(f"swept-corridor overlap (the physical hazard zone): "
                 f"{len(hazard)} cells, bbox {bbox(hazard)}")

    ext = run(set(tC[-1]), 60)                       # they stay clean forever
    gs2, rest2 = split_gliders(ext)
    ok_ = len(gs2) == 2 and rest2 == set()
    notes.append(f"still exactly 2 clean gliders 60 ticks later: {ok_}")
    ok = ok and ok_

    return ok, notes, (A0 | Bs), (delta_star, unsafe_ranges(unsafe), la, lb, cross)


# ======================================================================
# 2) the weave in circuit: a Snark-turned carry crosses a data corridor
# ======================================================================
def verify_snark_crossing(ticks=300, scan=range(-30, 31)):
    """Carry enters NE, the Snark turns it SE, and the SE output corridor
    crosses a NE data corridor.  Union-equality against the verified solo
    Snark run proves the data glider never perturbs the reflection."""
    ok, notes = True, []
    cat = set(place_snark(0, 0))
    t1 = trajectory(cat | set(snark_input_glider()), ticks)

    gs, rest = split_gliders(t1[-1])
    lo = glider_lane(gs[0]) if len(gs) == 1 else None
    ok_ = (len(gs) == 1 and rest == cat and glider_dir(gs[0]) == (1, 1))
    notes.append(f"solo: Snark turns carry NE->SE onto lane y-x=={lo}, "
                 f"catalyst restored: {ok_}")
    ok = ok and ok_

    cx = 30                                          # crossing, clear of the
    cross = (cx, cx + lo)                            # catalyst's bbox
    lb = cross[0] + cross[1]
    assert cross[0] > SNARK_BBOX[2] + 10
    Z = zone(cross)
    occ1 = occupancy(t1, Z)
    ok_ = bool(occ1)
    notes.append(f"carry output really sweeps the crossing zone at {cross} "
                 f"(t={occ1[0] if occ1 else '-'}..{occ1[-1] if occ1 else '-'}):"
                 f" {ok_}")
    ok = ok and ok_
    if not occ1:
        return False, notes, None

    b = translate(G_NE, 0, lb - glider_lane(G_NE))
    s = (cross[0] - 22) - bbox(b)[0]
    B0 = translate(b, s, -s)
    assert glider_lane(B0) == lb
    d0 = occupancy(trajectory(B0, ticks), Z)[0] - occ1[0]

    verdicts = {}
    for delta in scan:
        verdicts[delta] = classify(t1, B0, delta - d0, (1, -1), ticks)
    unsafe = sorted(d for d, (v, _) in verdicts.items() if v == "UNSAFE")
    safe = sorted(d for d, (v, _) in verdicts.items() if v == "SAFE")
    ok_ = bool(unsafe) and bool(safe)
    notes.append(f"offset scan delta in [{scan.start},{scan.stop-1}]: "
                 f"{len(safe)} safe, {len(unsafe)} unsafe; UNSAFE window "
                 f"{unsafe_ranges(unsafe)}")
    ok = ok and ok_

    delta_star = next((d for d in safe if d > (unsafe[-1] if unsafe else 0)),
                      safe[-1] if safe else None)
    if delta_star is None:
        notes.append("no safe offset — snark crossing FAILS")
        return False, notes, None
    _, Bs = verdicts[delta_star]
    tB = trajectory(Bs, ticks)
    tC = trajectory(t1[0] | Bs, ticks)

    ok_ = never_interact(tC, t1, tB)
    notes.append(f"chosen delta={delta_star:+d}: combined == solo(Snark+carry) "
                 f"UNION solo(data) at EVERY tick (reflection untouched): {ok_}")
    ok = ok and ok_

    gs, rest = split_gliders(tC[-1])
    ok_ = (len(gs) == 2 and rest == cat)
    notes.append(f"t={ticks}: 2 gliders out, residue == Snark still life "
                 f"EXACTLY: {ok_}")
    ok = ok and ok_
    outs = sorted((glider_dir(g), glider_lane(g)) for g in gs)
    ok_ = outs == sorted([((1, 1), lo), ((1, -1), lb)])
    notes.append(f"carry exits SE on y-x=={lo}, data exits NE on x+y=={lb}, "
                 f"both unchanged: {ok_}")
    ok = ok and ok_

    return ok, notes, (delta_star, unsafe_ranges(unsafe), lo, lb, cross)


# ======================================================================
def main():
    print("=" * 68)
    print("Glider signal crossing — TIMED WEAVE, not an any-phase crossover")
    print("verified in raw B3/S23 against life.py")
    print("=" * 68)
    print("""
Approach A (fetch a stable crossover still life): NOT AVAILABLE.
  Searched github.com/thomasdunn/cellular-automata-patterns (2398 files):
  every 'cross*' entry is the period-3 cross OSCILLATOR family, no signal
  crossover; conwaylife.com is 403 to fetches.  Stable crossings in Life
  are triple-XOR or Herschel-conduit constructions — machinery, not a
  Snark-sized catalyst.  So the deliverable is the honest approach B:
  a timed weave — corridors are transparent, timing is the discipline.""")
    failed = []

    ok, notes, cells, info = verify_weave()
    if not ok:
        failed.append("WEAVE")
    print(f"\n[1] bare weave — SE corridor x NE corridor: "
          f"{'PASS' if ok else 'FAIL'}")
    for n in notes:
        print(f"    - {n}")

    ok2, notes2, info2 = verify_snark_crossing()
    if not ok2:
        failed.append("SNARK-CROSSING")
    print(f"\n[2] in circuit — Snark-turned carry crosses a data corridor: "
          f"{'PASS' if ok2 else 'FAIL'}")
    for n in notes2:
        print(f"    - {n}")

    print()
    if failed:
        print("FAILED: " + ", ".join(failed))
        return 1

    delta, unsafe, la, lb, cross = info
    fn = "crossover.rle"
    with open(fn, "w") as f:
        f.write(to_rle(cells, comments=[
            "glider signal crossing — TIMED WEAVE, not an any-phase crossover",
            "SE glider on lane y-x==%d crosses NE glider on lane x+y==%d "
            "at cell (%d, %d)" % (la, lb, cross[0], cross[1]),
            "relative offset delta=%+d ticks (B after A at the crossing); "
            "UNSAFE window delta in %s" % (delta, unsafe),
            "verified: combined run == union of solo runs at every tick",
            "generated by crossover.py (emergence/glider-logic)",
        ]))
    print(f"saved {fn} (initial cells of the verified weave, delta={delta:+d})")
    print("\nALL PASS — timed weave verified, bare and in circuit.")
    print("Label: TIMED WEAVE — needs the scheduled clearance above; it is")
    print("not an any-phase stable crossover (none exists at gadget scale).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
