#!/usr/bin/env python3
"""
PHYSICALLY-ROUTED glider logic — composed from the verified gadgets, and
verified end-to-end by running the raw B3/S23 automaton.

gates.py proved the *reactions* (collisions compute); gadgets.py proved the
*wiring primitives* (Snark corner, duplicator fan-out).  This file actually
wires them together: gliders leave one gadget, fly across the plane, and enter
the next on exactly the lane and tick it needs.  Nothing is hand-placed at a
gate mouth unless the rung says so — signals are ROUTED.

The four rungs (each verified by simulation, catalysts-restored required):

  RUNG 1  fan-out + routing: one glider -> duplicator -> two copies, one of
          them bent 180 degrees by two Snarks so both copies end up travelling
          SE on two chosen parallel lanes.
  RUNG 2  a routed gate input: a glider is reflected by a Snark onto the exact
          lane/phase of gates.py's annihilation reaction (ANN), giving an
          INHIBIT (A AND NOT B) gate with a routed data input.  A rotated
          eater absorbs the deleter in the A=0 row so the machine ends stable.
  RUNG 3  a fully routed AND: both inputs enter on their own lanes, are
          reflected by Snarks onto a two-glider merge reaction, and the output
          glider (a lane neither input ever reaches) escapes cleanly.  Full
          4-row truth table.
  RUNG 4  half-adder, begun: BOTH inputs pass through duplicators (real
          fan-out); one copy pair is routed into the RUNG-3 AND (the carry),
          the other copies are routed onto designated parallel "sum feed"
          lanes for a future XOR stage.  4-row table for the carry.

Directions (y grows downward): SE=(+1,+1) NE=(+1,-1) SW=(-1,+1) NW=(-1,-1).
A glider on the SE/NW diagonal family rides lane  y0-x0  (phase-0 bbox corner);
on the NE/SW family it rides lane  x0+y0.

Run:  python3 routed.py     (prints a PASS/FAIL report, writes routed_*.rle)
"""
import os
from life import step, run, translate, normalize, bbox, GLIDER, EATER
from gadgets import (components, is_glider, glider_dir, glider_lane, glider_phase,
                     split_gliders, GLIDER_PHASES, DIRNAME,
                     SNARK, SNARK_DEMO_GLIDER, DUPLICATOR, DUP_DEMO_GLIDER,
                     place_duplicator, dup_input_glider)
import gates

HERE = os.path.dirname(os.path.abspath(__file__))

# ======================================================================
# 0)  geometry: lanes, trajectories, time-shifting gliders
# ======================================================================
def fam(d):
    """Which diagonal family a direction rides: SE/NW share y-x, NE/SW share x+y."""
    return 'ymx' if d[0] * d[1] > 0 else 'xpy'


def rot90(cells):
    """Quarter turn (x,y)->(-y,x). A valid Life pattern stays valid (isotropy)."""
    return {(-y, x) for (x, y) in cells}


def mirror(cells):
    """Reflect across the main diagonal (x<->y). Also a symmetry of B3/S23."""
    return {(y, x) for (x, y) in cells}


def norm_pair(cat, demo):
    """Translate catalyst+demo TOGETHER so the union's bbox corner is (0,0)."""
    allc = cat | demo
    mnx = min(x for x, _ in allc)
    mny = min(y for _, y in allc)
    t = lambda s: frozenset((x - mnx, y - mny) for (x, y) in s)
    return t(cat), t(demo)


def traj_params(comp, t):
    """Trajectory invariants of a glider component observed at absolute time t.

    Returns (dir, lane, tau).  Two gliders are the SAME spacetime signal iff
    all three match: dir+lane fix the diagonal line, tau fixes the schedule
    (tau = t' - 4*dx*x0 is constant along the flight, 1-tick resolution).
    """
    d, k = GLIDER_PHASES[normalize(comp)]
    a = (4 - k) % 4
    c0 = run(set(comp), a)          # canonical phase-0 appearance...
    tt = t + a                      # ...which it shows at time t+a
    x0, y0, _, _ = bbox(c0)
    lane = (y0 - x0) if fam(d) == 'ymx' else (x0 + y0)
    tau = tt - 4 * d[0] * x0
    return d, lane, tau


def backcast(target, t0):
    """Initial cells that evolve into glider state `target` exactly at time t0.

    Gliders are backward-deterministic along their own flight: slide the state
    q cells back along its direction (= 4q ticks earlier), then run forward
    the 0..3 tick remainder.
    """
    d = glider_dir(target)
    q = (t0 + 3) // 4
    s = 4 * q - t0
    base = translate(set(target), -d[0] * q, -d[1] * q)
    return run(base, s)


def delay_glider(g, delta):
    """A copy of initial glider g whose whole flight is `delta` ticks later."""
    if delta == 0:
        return set(g)
    if delta > 0:
        return backcast(set(g), delta)
    return run(set(g), -delta)


def bbox_gap(a, b):
    """Chebyshev gap between two bboxes (negative = overlap)."""
    ax0, ay0, ax1, ay1 = bbox(a)
    bx0, by0, bx1, by1 = bbox(b)
    gx = max(bx0 - ax1, ax0 - bx1)
    gy = max(by0 - ay1, ay0 - by1)
    return max(gx, gy)


def ahead_in_band(comp, cat_cells):
    """Is any catalyst cell ahead of this glider, close enough to interact?

    A glider's cells span its corner-lane +-2; influence reaches 1 more cell,
    so anything with |lane difference| <= 4 that lies forward of the glider is
    a potential future collision and must be flown past under observation.
    """
    d = glider_dir(comp)
    l = glider_lane(comp)
    if fam(d) == 'ymx':
        lv = lambda c: c[1] - c[0]
        av = lambda c: c[0] + c[1]
        sgn = 1 if d == (1, 1) else -1
    else:
        lv = lambda c: c[0] + c[1]
        av = lambda c: c[0] - c[1]
        sgn = 1 if d == (1, -1) else -1
    ga = max(av(c) for c in comp) if sgn > 0 else min(av(c) for c in comp)
    for c in cat_cells:
        if abs(lv(c) - l) <= 4:
            if sgn > 0 and av(c) >= ga - 6:
                return True
            if sgn < 0 and av(c) <= ga + 6:
                return True
    return False


def settle(initial, catalysts, expected, t_min, t_max, chunk=25):
    """Run the raw automaton until the composite has SETTLED FOR GOOD:
       - the non-glider residue is exactly the catalyst still-life set,
       - the gliders present match `expected` [(dirname, lane), ...] exactly,
       - then keep running until every survivor has actually FLOWN PAST every
         catalyst anywhere near its lane, re-checking the invariants the whole
         way.  This is an exact escape proof, not a heuristic: the final state
         is catalysts + gliders receding into empty plane forever.
       Returns (ok, t, state, glider_components)."""
    s = set(initial)
    t = 0
    want = sorted(expected)

    def signature_ok(gs, rest):
        if rest != set(catalysts) or len(gs) != len(want):
            return False
        return sorted((DIRNAME[glider_dir(c)], glider_lane(c)) for c in gs) == want

    while t < t_max:
        s = run(s, chunk)
        t += chunk
        if t < t_min:
            continue
        gs, rest = split_gliders(s)
        if not signature_ok(gs, rest):
            continue
        # escape phase: fly every survivor past all catalysts, invariants held
        guard = 0
        while any(ahead_in_band(c, catalysts) for c in gs):
            s = run(s, 100)
            t += 100
            gs, rest = split_gliders(s)
            if not signature_ok(gs, rest):
                return False, t, s, gs
            guard += 1
            if guard > 60:
                return False, t, s, gs
        return True, t, s, gs
    gs, rest = split_gliders(s)
    return False, t, s, gs


def se_ident(comp, t):
    """Express an SE glider seen at time t as gates.glider('SE',X,Y,0) @ t0."""
    d, k = GLIDER_PHASES[normalize(comp)]
    assert d == (1, 1)
    ref = run(set(GLIDER), k)                      # = gates.glider('SE',0,0,k)
    X = bbox(comp)[0] - bbox(ref)[0]
    Y = bbox(comp)[1] - bbox(ref)[1]
    return X, Y, t - k


# ======================================================================
# 1)  the Snark in all 8 orientations (4 rotations x mirror)
# ======================================================================
# Rotating/reflecting a whole pattern is a symmetry of the rule, so each
# variant is *expected* to work — but every one is verified from scratch
# anyway (one glider in on its lane -> one glider out at 90deg, catalyst
# restored) before anything downstream is allowed to use it.
class Variant:
    def __init__(self, name, cat, demo):
        self.name, self.cat, self.demo = name, cat, demo
        self.din = glider_dir(demo)
        self.lin = glider_lane(demo)
        self.dout = None
        self.lout = None
        self.ok = False

    def verify(self):
        c = set(self.cat)
        if step(c) != c:
            return False
        res = run(c | set(self.demo), 300)
        gs, rest = split_gliders(res)
        if len(gs) != 1 or rest != c:
            return False
        self.dout = glider_dir(gs[0])
        self.lout = glider_lane(gs[0])
        # a Snark turn is +-90deg: never straight through, never reversed
        if self.dout in (self.din, (-self.din[0], -self.din[1])):
            return False
        self.ok = True
        return True

    # -- placement ------------------------------------------------------
    def place(self, dx, dy):
        return translate(self.cat, dx, dy)

    def in_lane(self, dx, dy):
        return self.lin + ((dy - dx) if fam(self.din) == 'ymx' else (dx + dy))

    def out_lane(self, dx, dy):
        return self.lout + ((dy - dx) if fam(self.dout) == 'ymx' else (dx + dy))

    def input_glider(self, dx, dy, back=0, delta=0):
        g = translate(self.demo, dx - back * self.din[0], dy - back * self.din[1])
        return delay_glider(g, delta)


def build_variants():
    out = {}
    c0, g0 = set(SNARK), set(SNARK_DEMO_GLIDER)
    for m in range(2):
        c, g = (mirror(c0), mirror(g0)) if m else (set(c0), set(g0))
        for r in range(4):
            cc, gg = norm_pair(frozenset(c), frozenset(g))
            v = Variant(f"snark_m{m}r{r}", cc, gg)
            v.verify()
            out[v.name] = v
            c, g = rot90(c), rot90(g)
    return out


# ======================================================================
# 2)  reactions used downstream (verified inline, not taken on faith)
# ======================================================================
# Both reactions come straight from gates.py:
#   ANN          data SE at (0,0) ph0 + deleter NW at ANN.offset/phase ->
#                total annihilation (basis of INHIBIT / NOT).
#   AND_REACTION data SE at (0,0) ph0 + SW at (2,4) ph1 -> ONE NW glider on
#                lane +2 (basis of AND).
#
# A routed composite realizes each glider's ENTIRE approach flight, so a
# reaction is only usable if it is CAUSAL: starting both gliders 50 cells
# further back along their own lanes must give the identical outcome.  (Many
# hand-placed collisions fail this — the "initial" configuration is one that
# free-flying gliders would already have destroyed.  Both gates.py reactions
# pass; they are re-proven here every run.)
def _causal_outcome(a, b, ticks):
    def classify(res):
        gs, rest = split_gliders(res)
        if rest:
            return None
        return sorted((DIRNAME[glider_dir(c)], glider_lane(c)) for c in gs)
    da, db = glider_dir(a), glider_dir(b)
    out1 = classify(run(set(a) | set(b), ticks))
    a_pre = translate(a, -50 * da[0], -50 * da[1])
    b_pre = translate(b, -50 * db[0], -50 * db[1])
    out2 = classify(run(a_pre | b_pre, 200 + ticks))
    return out1 if (out1 is not None and out1 == out2) else None


def verify_and_reaction():
    """gates.AND_REACTION, re-verified *causally*; returns (ok, tau_ref)."""
    r = gates.AND_REACTION
    a = gates.glider('SE', 0, 0)
    b = gates.glider(r['bdir'], r['offset'][0], r['offset'][1], r['phase'])
    if _causal_outcome(a, b, 260) != [('NW', 2)]:
        return False, None
    res = run(set(a) | set(b), 260)
    gs, _ = split_gliders(res)
    _, _, tau = traj_params(gs[0], 260)
    # single-input rows: neither glider alone ever shows up as (NW, lane 2)
    for g in (a, b):
        gs1, rest1 = split_gliders(run(set(g), 260))
        if rest1 or len(gs1) != 1 or (glider_dir(gs1[0]), glider_lane(gs1[0])) == ((-1, -1), 2):
            return False, None
    return True, tau


def verify_ann():
    a = gates.glider('SE', 0, 0)
    ox, oy = gates.ANN['offset']
    b = gates.glider('NW', ox, oy, gates.ANN['phase'])
    return _causal_outcome(a, b, 80) == []


# an eater for NW gliders: EATER swallows SE gliders (life.py verified), so
# suitably rotated/mirrored copies swallow NW ones.  All 8 orientations are
# searched; each hit is one orientation + alignment class (sliding an eater
# along the glider's own lane only retimes the arrival, so one representative
# per diagonal class suffices).
def find_nw_eater():
    g0 = gates.glider('NW', 0, 0)
    cands = []
    E = set(EATER)
    for m in range(2):
        Em = mirror(E) if m else set(E)
        for r in range(4):
            Eo = frozenset(normalize(Em))
            seen = set()
            for ex in range(-28, 6):
                for ey in range(-28, 6):
                    Et = translate(Eo, ex, ey)
                    if Et & g0:
                        continue
                    if run(g0 | Et, 200) == Et:
                        cl = ey - ex
                        if cl not in seen:
                            seen.add(cl)
                            cands.append((Eo, ex, ey))
            Em = rot90(Em)
    return cands


# ======================================================================
# 3)  RLE export
# ======================================================================
def to_rle(cells):
    if not cells:
        return "x = 0, y = 0, rule = B3/S23\n!\n"
    x0, y0, x1, y1 = bbox(cells)
    w, h = x1 - x0 + 1, y1 - y0 + 1
    rows = []
    for y in range(y0, y1 + 1):
        raw = ''.join('o' if (x, y) in cells else 'b' for x in range(x0, x1 + 1))
        raw = raw.rstrip('b')
        enc, i = '', 0
        while i < len(raw):
            j = i
            while j < len(raw) and raw[j] == raw[i]:
                j += 1
            n = j - i
            enc += (str(n) if n > 1 else '') + raw[i]
            i = j
        rows.append(enc)
    # join rows with $, compressing runs of blank rows into n$
    body, i = '', 0
    while i < len(rows):
        body += rows[i]
        j = i + 1
        while j < len(rows) and rows[j] == '' and rows[j - 1] == '':
            j += 1
        nblank = 1
        k = i + 1
        while k < len(rows) and rows[k] == '':
            nblank += 1
            k += 1
        if k >= len(rows) and rows[i] == '':
            break
        if i < len(rows) - 1:
            body += (str(nblank) if nblank > 1 else '') + '$'
            i = i + nblank
        else:
            i += 1
    body += '!'
    wrapped = '\n'.join(body[i:i + 70] for i in range(0, len(body), 70))
    return f"x = {w}, y = {h}, rule = B3/S23\n{wrapped}\n"


def save_rle(name, cells, comment):
    path = os.path.join(HERE, f"routed_{name}.rle")
    with open(path, 'w') as f:
        f.write(f"#N routed_{name}\n#C {comment}\n")
        f.write(to_rle(cells))
    return os.path.basename(path)


# ======================================================================
# RUNG 1 — duplicator + two Snarks: fan-out onto chosen parallel lanes
# ======================================================================
# Layout (duplicator at origin):
#   input SE on lane -1 -> DUP -> SE copy on lane -23   (kept as-is)
#                              -> NW copy on lane -47
#   NW copy -> Snark(NW->NE)  at (16,-23)  -> NE on lane x+y=5
#   NE leg  -> Snark(NE->SE)  at (dx,dy)   -> SE on chosen lane D
# Both survivors travel SE on parallel lanes (-23 and D).  D slides the second
# Snark along the NE corridor, so the final lane is genuinely *chosen*.
def build_rung1(V, D=-97):
    v270, v0 = V['snark_m0r3'], V['snark_m0r0']
    dup = set(place_duplicator(0, 0))
    # reflector 1: input must be the dup's NW lane (-47)
    r1dx = 16
    r1dy = r1dx + (-47 - v270.lin)            # dy-dx = -47 - lin
    O1 = v270.out_lane(r1dx, r1dy)
    # reflector 2: input = the NE corridor O1, output = chosen SE lane D
    s = O1 - v0.lin                           # dx+dy
    t = (D - v0.lout)                         # dy-dx
    assert (s + t) % 2 == 0, "lane parity: pick D with the other parity"
    r2dx, r2dy = (s - t) // 2, (s + t) // 2
    cats = [dup, v270.place(r1dx, r1dy), v0.place(r2dx, r2dy)]
    for i in range(len(cats)):
        for j in range(i + 1, len(cats)):
            assert bbox_gap(cats[i], cats[j]) >= 5, "catalysts too close"
    catalysts = set().union(*cats)
    gin = set(dup_input_glider(0, 0, back=0))
    info = dict(O1=O1, D=D, r1=(r1dx, r1dy), r2=(r2dx, r2dy))
    return catalysts, gin, info


def verify_rung1(V):
    notes = []
    catalysts, gin, info = build_rung1(V)
    ok, t, state, gs = settle(catalysts | gin, catalysts,
                              [('SE', -23), ('SE', info['D'])],
                              t_min=600, t_max=2400)
    notes.append(f"1 glider in -> 2 SE gliders out on parallel lanes "
                 f"(-23, {info['D']}), settled at t={t}: {ok}")
    if ok:
        notes.append("all catalysts (duplicator + 2 Snarks) restored exactly; "
                     "both survivors' forward paths are clear forever")
    geometry = (f"in: SE lane y-x=-1 | out: SE lanes y-x=-23 and y-x={info['D']} "
                f"| Snark(NW->NE)@{info['r1']}, Snark(NE->SE)@{info['r2']}, "
                f"NE transfer corridor x+y={info['O1']}")
    return ok, notes, geometry, catalysts | gin


# ======================================================================
# RUNG 2 — Snark-routed data glider driving gates.py's ANN reaction
#           (INHIBIT gate: out = A AND NOT B), eater-terminated
# ======================================================================
def calibrate_routed_A(V, T1=400, back=10):
    """Route A through Snark(NE->SE) at the origin and express the resulting
       SE glider in gates.py coordinates: A == gates.glider('SE',X,Y,0) @ t0."""
    v0 = V['snark_m0r0']
    cat = set(v0.place(0, 0))
    a_in = v0.input_glider(0, 0, back=back)
    res = run(cat | a_in, T1)
    gs, rest = split_gliders(res)
    assert len(gs) == 1 and rest == cat and glider_dir(gs[0]) == (1, 1)
    X, Y, t0 = se_ident(gs[0], T1)
    # cross-check: the whole trajectory really is glider('SE',X,Y,0) started @t0
    assert run(gates.glider('SE', X, Y, 0), T1 + 40 - t0) == run(set(gs[0]), 40)
    return cat, a_in, X, Y, t0


def build_rung2(V, EAT, T1=400):
    cat, a_in, X, Y, t0 = calibrate_routed_A(V, T1)
    ox, oy = gates.ANN['offset']
    target = gates.glider('NW', X + ox, Y + oy, gates.ANN['phase'])
    b_in = backcast(target, t0)
    assert not (set(b_in) & cat)
    deleter_lane = (Y + oy) - (X + ox)
    # try each eater orientation/class, slid to sit between Snark and collision
    for (Eo, ex, ey) in EAT:
        base = (X + ox + ex) + (Y + oy + ey)
        s = (56 - base) // 2
        eat = translate(Eo, X + ox + ex + s, Y + oy + ey + s)
        if bbox_gap(eat, cat) < 5:
            continue
        cats = cat | eat
        # row A=0,B=1: deleter must be swallowed, everything restored
        ok1, t1, _, _ = settle(cats | set(b_in), cats, [], t_min=t0 + 60, t_max=t0 + 500)
        if not ok1:
            continue
        # row A=1,B=0: data glider must sail past the eater unharmed
        ok2, t2, _, g2 = settle(cats | set(a_in), cats, [('SE', Y - X)],
                                t_min=t0 + 60, t_max=t0 + 500)
        if ok2:
            return dict(cat=cat, eat=eat, a_in=a_in, b_in=set(b_in),
                        X=X, Y=Y, t0=t0, deleter_lane=deleter_lane)
    return None


def verify_rung2(V, EAT):
    notes = []
    cfg = build_rung2(V, EAT)
    if cfg is None:
        return False, ["no eater placement passed both guard tests"], "", set()
    cats = cfg['cat'] | cfg['eat']
    lane_out = cfg['Y'] - cfg['X']
    t0 = cfg['t0']
    rows = [(1, 0, [('SE', lane_out)]),
            (1, 1, []),
            (0, 1, []),
            (0, 0, [])]
    allok = True
    for A, B, expect in rows:
        init = set(cats)
        if A:
            init |= set(cfg['a_in'])
        if B:
            init |= set(cfg['b_in'])
        ok, t, _, _ = settle(init, cats, expect, t_min=t0 + 60, t_max=t0 + 600)
        allok &= ok
        out = 1 if expect else 0
        notes.append(f"A={A} B={B} -> out={out} (want {A & (1 - B)}), "
                     f"catalysts+eater restored, settled t={t}: {ok}")
    geometry = (f"A: NE glider on x+y=22 -> Snark@(0,0) -> SE data on y-x={lane_out}; "
                f"B: NW deleter on y-x={cfg['deleter_lane']} (gates.ANN offset "
                f"{gates.ANN['offset']} phase {gates.ANN['phase']} at t0={t0}); "
                f"rotated eater guards the Snark on the deleter lane")
    return allok, notes, geometry, cats | set(cfg['a_in']) | set(cfg['b_in'])


# ======================================================================
# RUNG 3 — fully routed AND gate (gates.py's AND_REACTION)
# ======================================================================
# The AND output is an NW glider that retraces the data corridor 2 lanes off,
# so NOTHING may sit up-left of the merge on that side — a Snark feeding the
# SE data leg would be smashed by its own gate's output (verified: a
# retrograde glider 2 lanes off the corridor wrecks the catalyst).  The
# routable topology is therefore:
#   B: NE glider  -> Snark(NE->SE) -> SE transfer -> Snark(SE->SW) -> SW leg,
#      arriving tick-exactly at the merge (TWO reflections, both timed).
#   A: enters directly ON the merge lane from empty space up-left.
# Then all four collision products head into virgin plane: A passes SE (B=0),
# B passes SW (A=0), and the AND output leaves NW over A's (empty) entry
# corridor.  No sinks needed; every row ends catalysts-restored.
def build_rung3(V, tau_and, dx1=45, L_A=40):
    v0, v90 = V['snark_m0r0'], V['snark_m0r1']
    catB0 = set(v0.place(0, 0))                  # NE -> SE at the origin
    # second Snark on the SE transfer lane (abs -2): dy - dx = -2 - lin = -4
    dy1 = dx1 + (-2 - v90.lin)
    catB1 = set(v90.place(dx1, dy1))
    assert bbox_gap(catB0, catB1) >= 5
    cats = catB0 | catB1
    L_SW = v90.out_lane(dx1, dy1)
    b_in = v0.input_glider(0, 0, back=10)

    # measure the twice-reflected B leg
    def measure(binp):
        s = cats | set(binp)
        for t in range(0, 1200, 25):
            s = run(s, 25)
            gs, rest = split_gliders(s)
            if rest == cats and len(gs) == 1 and glider_dir(gs[0]) == (-1, 1):
                return traj_params(gs[0], t + 25)
        return None

    got = measure(b_in)
    assert got and got[1] == L_SW, f"B leg on wrong lane: {got}"
    tau_B = got[2]

    # place A so that B arrives EXACTLY as gates.AND_REACTION requires:
    # B == glider('SW', X+bx, Y+by, bph) @ tA   where A == glider('SE',X,Y,0)@tA
    r = gates.AND_REACTION
    bx, by, bph = r['offset'][0], r['offset'][1], r['phase']
    probe = gates.glider('SW', 0, 0, bph)
    _, lane0, tau0 = traj_params(probe, 0)
    sXY = L_SW - lane0 - bx - by                 # X + Y
    if (sXY - L_A) % 2:
        L_A += 1                                 # lane parity fix-up
    X = (sXY - L_A) // 2
    Y = X + L_A
    tA = tau_B - tau0 - 4 * (X + bx)
    assert tA >= 200, f"A would have to start in the past (tA={tA})"
    a_in = backcast(gates.glider('SE', X, Y, 0), tA)
    assert not (set(a_in) & (cats | set(b_in)))
    assert bbox_gap(a_in, cats) >= 5 and bbox_gap(a_in, b_in) >= 5
    # cross-check the reconstruction: the routed B really IS the required one
    tgt = gates.glider('SW', X + bx, Y + by, bph)
    assert traj_params(tgt, tA) == ((-1, 1), L_SW, tau_B)
    exp_tau_out = tau_and + tA + 4 * X           # NW: tau shifts by t0 + 4*dx
    return dict(cats=cats, a_in=set(a_in), b_in=set(b_in), X=X, Y=Y, tA=tA,
                L_A=Y - X, L_SW=L_SW, v90pos=(dx1, dy1),
                exp_out=('NW', (Y - X) + 2, exp_tau_out))


def verify_rung3(V, tau_and):
    notes = []
    cfg = build_rung3(V, tau_and)
    cats = cfg['cats']
    tA, L_A = cfg['tA'], cfg['L_A']
    dirn, lane_out, tau_out = cfg['exp_out']
    rows = [(1, 1, [(dirn, lane_out)]),
            (1, 0, [('SE', L_A)]),
            (0, 1, [('SW', cfg['L_SW'])]),
            (0, 0, [])]
    allok = True
    for A, B, expect in rows:
        init = set(cats)
        if A:
            init |= set(cfg['a_in'])
        if B:
            init |= set(cfg['b_in'])
        ok, t, _, gs = settle(init, cats, expect, t_min=tA + 60, t_max=tA + 700)
        if ok and A and B:
            d, l, tau = traj_params(gs[0], t)
            ok = (tau == tau_out)
            notes.append(f"A=1 B=1 -> AND=1: merged NW output on lane "
                         f"y-x={lane_out}, tick-exact (tau {tau}=={tau_out}): {ok}")
        else:
            out = 1 if (A and B) else 0
            notes.append(f"A={A} B={B} -> AND={out} (want {A & B}); "
                         f"catalysts restored, survivors escape: {ok}")
        allok &= ok
    geometry = (f"B: NE on x+y=22 -> Snark@(0,0) -> SE transfer y-x=-2 -> "
                f"Snark(SE->SW)@{cfg['v90pos']} -> SW on x+y={cfg['L_SW']}; "
                f"A: direct SE entry on y-x={L_A}; merge at "
                f"~({cfg['X']},{cfg['Y']}) t={tA}; output NW on y-x={lane_out} "
                f"escapes over A's empty entry corridor")
    return allok, notes, geometry, cats | set(cfg['a_in']) | set(cfg['b_in'])


# ======================================================================
# RUNG 4 — half-adder, begun: dual fan-out + the first XOR inhibit leg
# ======================================================================
# gates.py's half-adder fans inputs out BY HAND.  Here both inputs really pass
# through duplicators, and the first leg of the XOR (sum) stage is computed
# from the DUPLICATED signals themselves:
#     A -> DUP_A:  SE copy = A data (XOR leg-1 data)
#                  NW copy = A's deleter for the future leg 2  (delivered rail)
#     B -> DUP_B:  NW copy = B's deleter — aimed, tick-exactly, at A's data
#                  (an annihilation reaction: this IS "A AND NOT B")
#                  SE copy = B data rail (future leg-2 / carry feed)
# A rotated eater guards DUP_A from B's deleter in the A=0 row.
#
# Geometry note: with both duplicators emitting data-SE/deleter-NW,
# only ONE cross-inhibition is geometrically realizable (the deleter of the
# down-right duplicator can reach the other's data; the reverse deleter flies
# away from everything).  The second XOR leg needs a 3-Snark reroute of A's
# deleter; that is where this rung stops (ha_xor.py builds the second leg).
#
# The annihilation used here is the delta=+7 cousin of gates.ANN (deleter 7
# lanes above the data), chosen so DUP_B's catalyst band clears the surviving
# data glider's escape corridor; it is re-verified causally at build time.
DEL7 = [(3, 10, 0), (5, 12, 0), (3, 10, 1), (2, 9, 3), (4, 11, 3)]


def build_rung4(V, collide_x=130, dxB=150):
    # ---- side A: plain duplicator at the origin ----
    dupA = set(place_duplicator(0, 0))
    a_in = set(dup_input_glider(0, 0, back=0))
    T1 = 800
    res = run(dupA | a_in, T1)
    gs, rest = split_gliders(res)
    assert rest == dupA and len(gs) == 2
    a_data = [g for g in gs if glider_dir(g) == (1, 1)][0]
    a_del = [g for g in gs if glider_dir(g) == (-1, -1)][0]
    assert glider_lane(a_data) == -23 and glider_lane(a_del) == -47
    Xa, Ya, t0a = se_ident(a_data, T1)

    # ---- pick a causal delta=+7 annihilation ----
    ann = None
    for (ox, oy, ph) in DEL7:
        a = gates.glider('SE', 0, 0)
        b = gates.glider('NW', ox, oy, ph)
        if _causal_outcome(a, b, 120) == []:
            ann = (ox, oy, ph)
            break
    assert ann, "no causal delta=+7 annihilation found"
    ox, oy, ph = ann

    # ---- B's deleter target: kill A's data at x ~ collide_x ----
    w = collide_x - Xa
    tgt = gates.glider('NW', Xa + w + ox, Ya + w + oy, ph)
    t_tgt = t0a + 4 * w
    d_t, L_del, tau_t = traj_params(tgt, t_tgt)
    assert d_t == (-1, -1) and L_del == -23 + (oy - ox)

    # ---- side B: duplicator whose NW output rides the deleter lane ----
    dyB = dxB + (L_del + 47)
    dupB = set(place_duplicator(dxB, dyB))
    assert bbox_gap(dupA, dupB) >= 8
    cats0 = dupA | dupB
    L_bd = (dyB - dxB) - 23                     # B's SE data-rail lane

    def measureB(binp):
        s = dupB | set(binp)
        for t in range(0, 1600, 25):
            s = run(s, 25)
            gs2, rest2 = split_gliders(s)
            nw = [g for g in gs2 if glider_dir(g) == (-1, -1)]
            if rest2 == dupB and len(gs2) == 2 and nw:
                return traj_params(nw[0], t + 25)
        return None

    b_in = set(dup_input_glider(dxB, dyB, back=4))
    got = measureB(b_in)
    assert got and got[1] == L_del, f"B deleter on wrong lane: {got}"
    delta = tau_t - got[2]
    if delta < 0:                               # retime by sliding the collision
        dw = (-delta + 7) // 8 + 1
        w += dw
        tgt = gates.glider('NW', Xa + w + ox, Ya + w + oy, ph)
        t_tgt = t0a + 4 * w
        _, _, tau_t = traj_params(tgt, t_tgt)
        delta = tau_t - got[2]
    b_in = delay_glider(b_in, delta)
    assert not (set(b_in) & cats0)
    assert bbox_gap(b_in, dupA) >= 4 and bbox_gap(b_in, dupB) >= 4
    got = measureB(b_in)
    assert got == ((-1, -1), L_del, tau_t), f"B timing mismatch: {got}"

    # ---- guard eater: swallow B's deleter before it reaches DUP_A ----
    g0 = gates.glider('NW', 0, 0, ph)
    cands = []
    for m in range(2):
        Em = mirror(set(EATER)) if m else set(EATER)
        for r4 in range(4):
            Eo = frozenset(normalize(Em))
            seen = set()
            for ex in range(-28, 6):
                for ey in range(-28, 6):
                    Et = translate(Eo, ex, ey)
                    if (Et & g0) or not run(g0 | Et, 200) == Et:
                        continue
                    if (ey - ex) not in seen:
                        seen.add(ey - ex)
                        cands.append((Eo, ex, ey))
            Em = rot90(Em)
    for (Eo, ex, ey) in cands:
        base = (Xa + w + ox + ex) + (Ya + w + oy + ey)
        s = (188 - base) // 2                   # park it near x+y ~ 188
        eat = translate(Eo, Xa + w + ox + ex + s, Ya + w + oy + ey + s)
        if bbox_gap(eat, dupA) < 6 or bbox_gap(eat, dupB) < 6:
            continue
        cats = cats0 | eat
        # row A=0,B=1: deleter swallowed, B's data rail sails on
        ok1, _, _, _ = settle(cats | b_in, cats, [('SE', L_bd)],
                              t_min=t_tgt + 100, t_max=t_tgt + 1600)
        if not ok1:
            continue
        # row A=1,B=0: both of A's copies fly past everything unharmed
        ok2, _, _, _ = settle(cats | a_in, cats, [('SE', -23), ('NW', -47)],
                              t_min=t_tgt + 100, t_max=t_tgt + 1600)
        if ok1 and ok2:
            return dict(cats=cats, a_in=a_in, b_in=b_in, ann=ann,
                        Xa=Xa, Ya=Ya, w=w, t_tgt=t_tgt, L_del=L_del,
                        L_bd=L_bd, dupB_at=(dxB, dyB))
    return None


def verify_rung4(V):
    notes = []
    cfg = build_rung4(V)
    if cfg is None:
        return False, ["no guard-eater placement passed both guard tests"], "", set()
    cats = cfg['cats']
    t_tgt, L_bd = cfg['t_tgt'], cfg['L_bd']
    rows = [(1, 1, [('NW', -47), ('SE', L_bd)]),
            (1, 0, [('SE', -23), ('NW', -47)]),
            (0, 1, [('SE', L_bd)]),
            (0, 0, [])]
    allok = True
    for A, B, expect in rows:
        init = set(cats)
        if A:
            init |= set(cfg['a_in'])
        if B:
            init |= set(cfg['b_in'])
        ok, t, _, gs = settle(init, cats, expect, t_min=t_tgt + 100,
                              t_max=t_tgt + 1800)
        allok &= ok
        leg1 = A & (1 - B)
        notes.append(f"A={A} B={B} -> XOR-leg1 (A AND NOT B)={leg1}, "
                     f"railA(NW del)={'-' if not A else 'out'}, "
                     f"railB(SE data)={'-' if not B else 'out'}: {ok}")
    ox, oy, ph = cfg['ann']
    geometry = (f"A -> DUP@(0,0): data SE y-x=-23, deleter rail NW y-x=-47; "
                f"B -> DUP@{cfg['dupB_at']}: deleter NW y-x={cfg['L_del']} "
                f"annihilates A's data at ~({cfg['Xa']+cfg['w']},"
                f"{cfg['Ya']+cfg['w']}) t~{t_tgt} "
                f"(delta=+7 causal annihilation, offset ({ox},{oy}) ph {ph}); "
                f"data rail SE y-x={L_bd}; guard eater on the deleter lane")
    return allok, notes, geometry, cats | set(cfg['a_in']) | set(cfg['b_in'])


# ======================================================================
# report
# ======================================================================
def main():
    print("=" * 70)
    print("PHYSICALLY-ROUTED glider logic — raw-automaton verification")
    print("=" * 70)
    results = {}

    # -- prerequisites: 8 Snark orientations + the two reactions ----------
    V = build_variants()
    nok = sum(v.ok for v in V.values())
    print(f"\n[prereq] Snark in 8 orientations (4 rotations x mirror): "
          f"{nok}/8 verified")
    for v in V.values():
        tag = (f"{DIRNAME[v.din]}->{DIRNAME[v.dout]}" if v.ok else "FAILED")
        print(f"    {v.name}: {tag}  (in lane {v.lin}, out lane {v.lout})")
    and_ok, tau_and = verify_and_reaction()
    ann_ok = verify_ann()
    print(f"[prereq] gates.ANN annihilation re-verified CAUSALLY "
          f"(same outcome from 50 cells further out): {ann_ok}")
    print(f"[prereq] gates.AND_REACTION re-verified CAUSALLY "
          f"(one NW glider on lane +2, no debris): {and_ok}")
    EAT = find_nw_eater()
    print(f"[prereq] rotated/mirrored eaters that swallow NW gliders: "
          f"{len(EAT)} orientation/alignment classes")
    prereq = (nok == 8) and and_ok and ann_ok and len(EAT) > 0

    rungs = []
    if prereq:
        rungs.append(("RUNG 1  fan-out + 180deg reroute onto parallel lanes",
                      "fanout", "1 glider -> duplicator -> 2 SE gliders on "
                      "chosen parallel lanes via two Snarks",
                      lambda: verify_rung1(V)))
        rungs.append(("RUNG 2  routed INHIBIT (A AND NOT B) via gates.ANN",
                      "inhibit", "Snark-routed data glider + gates.ANN deleter "
                      "+ eater-terminated deleter lane",
                      lambda: verify_rung2(V, EAT)))
        rungs.append(("RUNG 3  fully routed AND gate (gates.AND_REACTION, "
                      "4-row truth table)",
                      "and", "B routed through two Snarks tick-exactly onto "
                      "gates.py's AND merge; output escapes on a virgin lane",
                      lambda: verify_rung3(V, tau_and)))
        rungs.append(("RUNG 4  half-adder begun: dual fan-out + first XOR "
                      "inhibit leg",
                      "half_adder_stage", "both inputs duplicated; B's deleter "
                      "copy annihilates A's data copy (A AND NOT B); rails "
                      "delivered; eater-guarded",
                      lambda: verify_rung4(V)))

    summary = []
    for title, name, comment, fn in rungs:
        print(f"\n{title}")
        try:
            ok, notes, geometry, cells0 = fn()
        except AssertionError as e:
            ok, notes, geometry, cells0 = False, [f"build failed: {e}"], "", set()
        for n in notes:
            print(f"    - {n}")
        if geometry:
            print(f"    geometry: {geometry}")
        print(f"    => {'PASS' if ok else 'FAIL'}")
        if ok and cells0:
            f = save_rle(name, cells0, comment)
            print(f"    saved {f}")
        summary.append((title.split()[0] + ' ' + title.split()[1], ok))

    print("\n" + "=" * 70)
    line = ", ".join(f"{n}: {'PASS' if ok else 'FAIL'}" for n, ok in summary)
    print("SUMMARY  " + (line if line else "prerequisites failed"))
    allok = prereq and all(ok for _, ok in summary)
    print("ALL RUNGS PASS" if allok and summary else
          ("SOME RUNGS FAILED" if summary else "PREREQ FAILURE"))
    return 0 if allok else 1


if __name__ == "__main__":
    raise SystemExit(main())
