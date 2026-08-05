#!/usr/bin/env python3
"""Nicholas Carlini's complete 4-bit ripple-carry adder, running in our engine.

Provenance
----------
    https://nicholas.carlini.com/writing/2020/digital-logic-game-of-life.html
    pattern:  https://nicholas.carlini.com/writing/2020/gameoflife/adder.mc

Carlini built digital logic out of period-30 glider streams: gates are laid on
270x270-cell tiles (270 = 9 x 30, a multiple of the gun period so stream
phases stay aligned across tiles), each full adder is thirteen gates, and four
full adders are chained into a standard ripple-carry adder.  His demo adds
six (0110) and five (0101) to get eleven (1011).

The pattern is a 137,712-cell circuit spanning 36,715 x 41,556 cells:

  * 8 input sites on the NW anti-diagonal — two mirrored groups of four,
    one lane per bit of each operand.  An active bit is a gun assembly that
    emits a period-30 glider stream; an inactive bit is a larger, silenced
    assembly that emits nothing.
  * the adder itself in the middle,
  * 4 output terminals on the SE anti-diagonal, one lane per sum bit.  A sum
    bit is 1 iff a glider stream arrives on its lane (every stream ends on a
    terminal gadget, so nothing escapes to infinity).

Signals travel diagonally (gliders!), so a "lane" is a diagonal x - y = const,
and bit significance runs along the anti-diagonal (MSB on the south-west lane
— the convention is fixed below by the inputs themselves).

How this file verifies it
-------------------------
The naive sparse engine in life.py steps this pattern at ~0.3 s/generation,
and the computation takes on the order of 10^5 generations (signals cross an
~80,000-cell diagonal at glider speed c/4) — days of CPU.  So this file embeds
a small pure-python HASHLIFE (Gosper's memoized-quadtree algorithm), which is

  1. cross-validated cell-for-cell against life.step on the actual adder
     pattern (and on a Gosper gun) before it is trusted with anything,
  2. then used to run the adder 2^20 = 1,048,576 generations to steady state,
  3. after which the input and output lanes are probed and decoded.

Run:  python3 carlini_adder.py          (~1-2 min, ~1 GB RAM at peak)

It prints the parsed size, every lane's state, the decoded arithmetic, and a
PASS / PARTIAL / FAIL verdict.  It also (re)writes carlini_adder.rle — the
generation-0 pattern in standard RLE, re-parseable by gadgets.rle_parse.
"""
import os
import sys
import time
import urllib.request
from collections import Counter, defaultdict

sys.setrecursionlimit(1_000_000)
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from life import step, run, bbox, GOSPER    # the naive engine (ground truth)
from gadgets import split_gliders, glider_dir

URL = "https://nicholas.carlini.com/writing/2020/gameoflife/adder.mc"
MC_PATH = os.path.join(HERE, "carlini_adder.mc")
RLE_PATH = os.path.join(HERE, "carlini_adder.rle")


# ======================================================================
# 1) fetch + parse the macrocell file
# ======================================================================
def fetch_mc():
    if os.path.exists(MC_PATH):
        text = open(MC_PATH).read()
    else:
        print(f"downloading {URL} ...")
        text = urllib.request.urlopen(URL, timeout=60).read().decode()
        open(MC_PATH, "w").write(text)
    if not text.startswith("[M2]"):
        raise ValueError("not a Golly macrocell file (missing [M2] header)")
    return text


def parse_mc(text):
    """Golly macrocell (numeric flavour) -> set of (x, y) live cells.

    Every non-comment line defines node #k (k = 1, 2, ... in file order) as
    `level nw ne sw se`.  At level 1 the four children are cell states; at
    higher levels they are node numbers, 0 meaning an all-dead subtree.  The
    root is the last node.  This file uses the numeric flavour throughout
    (no `$.*` leaf lines), which is what this parser handles.
    """
    nodes = {}
    nid = 0
    for ln in text.splitlines():
        ln = ln.strip()
        if not ln or ln[0] in "#[":
            continue
        if not ln[0].isdigit():
            raise ValueError(f"unsupported macrocell leaf line: {ln[:40]!r}")
        nid += 1
        nodes[nid] = tuple(map(int, ln.split()))
    cells = set()

    def emit(n, lv, x, y):
        if n == 0:
            return
        _, a, b, c, d = nodes[n]
        if lv == 1:
            if a: cells.add((x, y))
            if b: cells.add((x + 1, y))
            if c: cells.add((x, y + 1))
            if d: cells.add((x + 1, y + 1))
            return
        h = 1 << (lv - 1)
        emit(a, lv - 1, x, y)
        emit(b, lv - 1, x + h, y)
        emit(c, lv - 1, x, y + h)
        emit(d, lv - 1, x + h, y + h)

    emit(nid, nodes[nid][0], 0, 0)
    return cells


# ======================================================================
# 2) embedded hashlife (Gosper's algorithm, pure python, no deps)
# ======================================================================
# Nodes are interned integers: id 0 = dead cell, id 1 = live cell (level 0).
# LEVEL/CH/POP hold per-node data.  expand() and successor() are *centered*,
# so the universe center never moves and absolute coordinates survive.
LEVEL = [0, 0]
CH = [None, None]
POP = [0, 1]
_JOIN = {}
_EMPTY = {0: 0}
_SUCC = {}


def _join(a, b, c, d):
    key = (a, b, c, d)
    n = _JOIN.get(key)
    if n is None:
        n = len(LEVEL)
        _JOIN[key] = n
        LEVEL.append(LEVEL[a] + 1)
        CH.append(key)
        POP.append(POP[a] + POP[b] + POP[c] + POP[d])
    return n


def _empty(k):
    n = _EMPTY.get(k)
    if n is None:
        e = _empty(k - 1)
        n = _EMPTY[k] = _join(e, e, e, e)
    return n


def _expand(m):
    """level k -> k+1, pattern kept centered."""
    a, b, c, d = CH[m]
    e = _empty(LEVEL[m] - 1)
    return _join(_join(e, e, e, a), _join(e, e, b, e),
                 _join(e, c, e, e), _join(d, e, e, e))


def _centre(m):
    a, b, c, d = CH[m]
    return _join(CH[a][3], CH[b][2], CH[c][1], CH[d][0])


def _succ_4x4(m):
    """level-2 node (4x4) -> its 2x2 center advanced ONE generation."""
    g = [[0] * 4 for _ in range(4)]
    for q, ox, oy in zip(CH[m], (0, 2, 0, 2), (0, 0, 2, 2)):
        qa, qb, qc, qd = CH[q]
        g[oy][ox], g[oy][ox + 1] = qa, qb
        g[oy + 1][ox], g[oy + 1][ox + 1] = qc, qd

    def nxt(cx, cy):
        n = sum(g[cy + dy][cx + dx]
                for dy in (-1, 0, 1) for dx in (-1, 0, 1) if dx or dy)
        return 1 if n == 3 or (n == 2 and g[cy][cx]) else 0

    return _join(nxt(1, 1), nxt(2, 1), nxt(1, 2), nxt(2, 2))


def _successor(m, j):
    """center (level k-1) of m, advanced 2^min(j, k-2) generations."""
    k = LEVEL[m]
    j = min(j, k - 2)
    if POP[m] == 0:
        return _empty(k - 1)
    key = (m, j)
    r = _SUCC.get(key)
    if r is not None:
        return r
    if k == 2:
        r = _succ_4x4(m)
    else:
        A, B, C, D = CH[m]
        Aa, Ab, Ac, Ad = CH[A]
        Ba, Bb, Bc, Bd = CH[B]
        Ca, Cb, Cc, Cd = CH[C]
        Da, Db, Dc, Dd = CH[D]
        c1 = _successor(A, j)
        c2 = _successor(_join(Ab, Ba, Ad, Bc), j)
        c3 = _successor(B, j)
        c4 = _successor(_join(Ac, Ad, Ca, Cb), j)
        c5 = _successor(_join(Ad, Bc, Cb, Da), j)
        c6 = _successor(_join(Bc, Bd, Da, Db), j)
        c7 = _successor(C, j)
        c8 = _successor(_join(Cb, Da, Cd, Dc), j)
        c9 = _successor(D, j)
        if j == k - 2:      # full Gosper superspeed: two half-depth stages
            r = _join(_successor(_join(c1, c2, c4, c5), j),
                      _successor(_join(c2, c3, c5, c6), j),
                      _successor(_join(c4, c5, c7, c8), j),
                      _successor(_join(c5, c6, c8, c9), j))
        else:               # slower than superspeed: second stage adds 0 gens
            r = _join(_centre(_join(c1, c2, c4, c5)),
                      _centre(_join(c2, c3, c5, c6)),
                      _centre(_join(c4, c5, c7, c8)),
                      _centre(_join(c5, c6, c8, c9)))
    _SUCC[key] = r
    return r


def _is_padded(m):
    if LEVEL[m] < 3:
        return False
    A, B, C, D = CH[m]
    return (POP[A] == POP[CH[CH[A][3]][3]] and
            POP[B] == POP[CH[CH[B][2]][2]] and
            POP[C] == POP[CH[CH[C][1]][1]] and
            POP[D] == POP[CH[CH[D][0]][0]])


def hl_advance(m, g):
    """advance node m by exactly g generations (centered frame)."""
    for j in range(g.bit_length() - 1, -1, -1):
        if (g >> j) & 1:
            while LEVEL[m] < max(j + 2, 3) or not _is_padded(m):
                m = _expand(m)
            m = _successor(m, j)
    return m


def hl_from_cells(cells):
    """-> (node, cx, cy): node whose center is at absolute (cx, cy)."""
    xs = [x for x, _ in cells]
    ys = [y for _, y in cells]
    x0, y0 = min(xs), min(ys)
    k = max(max(xs) - x0 + 1, max(ys) - y0 + 1).bit_length()

    def build(kk, ox, oy, pts):
        if not pts:
            return _empty(kk)
        if kk == 0:
            return 1
        h = 1 << (kk - 1)
        q = [[], [], [], []]
        for (x, y) in pts:
            q[2 * ((y - oy) >= h) + ((x - ox) >= h)].append((x, y))
        return _join(build(kk - 1, ox, oy, q[0]),
                     build(kk - 1, ox + h, oy, q[1]),
                     build(kk - 1, ox, oy + h, q[2]),
                     build(kk - 1, ox + h, oy + h, q[3]))

    half = 1 << (k - 1)
    return build(k, x0, y0, list(cells)), x0 + half, y0 + half


def hl_to_cells(m, cx, cy, window=None):
    """extract live cells (optionally only inside window=(x0,y0,x1,y1))."""
    out = []

    def rec(n, x, y, k):
        if POP[n] == 0:
            return
        s = 1 << k
        if window is not None:
            wx0, wy0, wx1, wy1 = window
            if x > wx1 or y > wy1 or x + s <= wx0 or y + s <= wy0:
                return
        if k == 0:
            out.append((x, y))
            return
        h = s >> 1
        a, b, c, d = CH[n]
        rec(a, x, y, k - 1)
        rec(b, x + h, y, k - 1)
        rec(c, x, y + h, k - 1)
        rec(d, x + h, y + h, k - 1)

    half = 1 << (LEVEL[m] - 1)
    rec(m, cx - half, cy - half, LEVEL[m])
    return set(out)


# ======================================================================
# 3) locating the I/O sites (generation 0 geometry)
# ======================================================================
def coarse_clusters(pts, grid=100):
    """agglomerate points into clusters of adjacent occupied grid squares."""
    occ = defaultdict(list)
    for (x, y) in pts:
        occ[(x // grid, y // grid)].append((x, y))
    seen, clusters = set(), []
    for key in list(occ):
        if key in seen:
            continue
        stack, members = [key], []
        seen.add(key)
        while stack:
            k = stack.pop()
            members.extend(occ[k])
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    nk = (k[0] + dx, k[1] + dy)
                    if nk in occ and nk not in seen:
                        seen.add(nk)
                        stack.append(nk)
        clusters.append(members)
    return clusters


def lane_center(cluster):
    lanes = [x - y for x, y in cluster]
    return (min(lanes) + max(lanes)) // 2


def find_io_lanes(cells):
    """-> (A lanes, B lanes, sum lanes), each sorted ascending by x - y.

    The 8 input assemblies sit on the NW anti-diagonal (x+y ~ 7100-7400),
    the 4 output terminals on the SE one (x+y ~ 67600-67900).  Operand A is
    the positive-lane group, operand B the mirrored negative-lane group.
    """
    nw = [(x, y) for (x, y) in cells if x + y < 12_000]
    se = [(x, y) for (x, y) in cells if x + y > 64_000]
    nw_cl = coarse_clusters(nw)
    se_cl = coarse_clusters(se)
    if len(nw_cl) != 8 or len(se_cl) != 4:
        raise ValueError(f"expected 8 input + 4 output sites, "
                         f"found {len(nw_cl)} + {len(se_cl)}")
    in_lanes = sorted(lane_center(c) for c in nw_cl)
    a_lanes = [l for l in in_lanes if l > 0]
    b_lanes = [l for l in in_lanes if l < 0]
    return a_lanes, b_lanes, sorted(lane_center(c) for c in se_cl)


# ======================================================================
# 4) probing lanes at steady state
# ======================================================================
def probe(node, cx, cy, lane, ad_lo, ad_hi, halfw=350):
    """live cells on diagonal lane x-y in [lane±halfw], x+y in [ad_lo,ad_hi]."""
    x_lo = (ad_lo + lane - halfw) // 2 - 5
    x_hi = (ad_hi + lane + halfw) // 2 + 5
    y_lo = (ad_lo - lane - halfw) // 2 - 5
    y_hi = (ad_hi - lane + halfw) // 2 + 5
    w = hl_to_cells(node, cx, cy, window=(x_lo, y_lo, x_hi, y_hi))
    return {(x, y) for (x, y) in w
            if abs((x - y) - lane) <= halfw and ad_lo <= x + y <= ad_hi}


def bits_to_int(bits):        # bits[0] is the MSB
    v = 0
    for b in bits:
        v = 2 * v + b
    return v


# ======================================================================
# main
# ======================================================================
def main():
    verdict_checks = []

    def check(name, ok):
        verdict_checks.append(ok)
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
        return ok

    print("Carlini 4-bit ripple-carry glider adder")
    print(f"source: {URL}\n")

    # ---- fetch + parse -------------------------------------------------
    text = fetch_mc()
    cells = parse_mc(text)
    x0, y0, x1, y1 = bbox(cells)
    print(f"parsed {os.path.basename(MC_PATH)} (macrocell, "
          f"{len(text.splitlines())} lines):")
    print(f"  {len(cells):,} live cells, bbox {x1-x0+1:,} x {y1-y0+1:,} "
          f"(x [{x0},{x1}], y [{y0},{y1}])\n")

    # ---- naive-engine sanity + hashlife cross-validation ---------------
    print("cross-validating embedded hashlife against life.step ...")
    gun = set(GOSPER)
    gnode, gcx, gcy = hl_from_cells(gun)
    ok = all(hl_to_cells(hl_advance(gnode, g), gcx, gcy) == run(set(gun), g)
             for g in (1, 7, 30, 100, 200))
    check("hashlife == life.step on Gosper gun (1,7,30,100,200 gens)", ok)

    node, cx, cy = hl_from_cells(cells)
    t0 = time.time()
    naive32 = run(set(cells), 32)
    t_naive = time.time() - t0
    hl32 = hl_to_cells(hl_advance(node, 32), cx, cy)
    check(f"hashlife == life.step on the ADDER itself, 32 gens "
          f"(pop {len(cells):,} -> {len(naive32):,})", hl32 == naive32)
    print(f"  (naive engine: {t_naive/32:.2f} s/generation on this pattern — "
          f"the full ~10^5-gen computation is why hashlife is embedded)\n")

    # ---- deep run ------------------------------------------------------
    T = 1 << 20
    print(f"running {T:,} generations with hashlife ...")
    t0 = time.time()
    end = hl_advance(node, T)
    print(f"  done in {time.time() - t0:.0f} s; population "
          f"{POP[node]:,} -> {POP[end]:,}")
    n_nodes = len(LEVEL)
    end2 = hl_advance(node, T * 2)
    check(f"steady state: 2^20 -> 2^21 gens creates almost no new spacetime "
          f"({len(LEVEL) - n_nodes:,} new nodes)", len(LEVEL) - n_nodes < 50_000)
    del end2

    # streams run on the period-30 gun clock.  Raw input streams are p30;
    # gate outputs are thinned to every other slot (p60) — presence, not
    # density, encodes the bit.  Verify the output stream is exactly
    # periodic with a period that is a multiple of 30.
    a_lanes, b_lanes, s_lanes = find_io_lanes(cells)
    band = lambda n: probe(n, cx, cy, s_lanes[-1], 60_000, 66_000)
    b_T = band(end)
    period = next((dt for dt in (30, 60, 90, 120)
                   if band(hl_advance(node, T + dt)) == b_T), None)
    check(f"output stream is locked to the p30 gun clock "
          f"(exact period {period}, T vs T+15 differs)",
          period is not None and period % 30 == 0
          and b_T != band(hl_advance(node, T + 15)))

    # the probe patch really is a stream of SE-bound gliders
    gs, rest = split_gliders(b_T)
    interior = [g for g in gs
                if all(60_500 < x + y < 65_500 for x, y in g)]  # not clipped
    check(f"probe patch decomposes into gliders, all flying SE "
          f"({len(interior)} whole gliders, {len(rest)} leftover cells "
          f"from patch-boundary clipping)",
          len(interior) > 100 and
          all(glider_dir(g) == (1, 1) for g in interior))
    print()

    # ---- decode --------------------------------------------------------
    # Bit convention: within each operand, MSB on the south-west-most lane
    # (smallest x - y).  This is fixed by the inputs: it is the only uniform
    # convention under which the operands read 6 and 5 — and then the SAME
    # convention must make the outputs read 11 for the adder to be right.
    print("lane probes at steady state (stream = glider stream on the "
          "p30 gun clock):")

    def read(lanes, ad_lo, ad_hi, label):
        bits = []
        for lane in lanes:                       # ascending = MSB..LSB
            n = len(probe(end, cx, cy, lane, ad_lo, ad_hi))
            bits.append(1 if n > 50 else 0)
            print(f"  {label} lane x-y~{lane:7,d}: {n:5,d} cells -> "
                  f"{'STREAM (1)' if bits[-1] else 'silent (0)'}")
        return bits

    A = read(a_lanes, 8_000, 14_000, "in A ")
    B = read(b_lanes, 8_000, 14_000, "in B ")
    S = read(s_lanes, 60_000, 66_000, "out  ")
    a_v, b_v, s_v = bits_to_int(A), bits_to_int(B), bits_to_int(S)
    a_s, b_s, s_s = ("".join(map(str, x)) for x in (A, B, S))
    print(f"\n  operand A = {a_s} = {a_v}")
    print(f"  operand B = {b_s} = {b_v}")
    print(f"  sum       = {s_s} = {s_v}")
    check(f"inputs are the advertised demo values 6 and 5",
          sorted((a_v, b_v)) == [5, 6])
    check(f"THE ADDER COMPUTES: {a_v} + {b_v} = {s_v}", a_v + b_v == s_v)
    print()

    # ---- export RLE ----------------------------------------------------
    write_rle(cells, RLE_PATH)
    print(f"wrote {RLE_PATH}")
    print(f"  viewer note: at {len(cells):,} cells over a "
          f"{x1-x0+1:,} x {y1-y0+1:,} board this is ~4.6x past what "
          f"life-viewer.html handles comfortably (~30k cells) — watch it in "
          f"Golly, or crop a single 270x270 gate tile for the viewer.\n")

    # ---- verdict -------------------------------------------------------
    if all(verdict_checks):
        print("VERDICT: PASS — the real Carlini ripple-carry adder runs in "
              "our engine and computes 6 + 5 = 11 entirely in gliders.")
    elif verdict_checks[:2] == [True, True]:
        print("VERDICT: PARTIAL — pattern parses and evolves correctly in "
              "our engine, but full arithmetic verification failed; see "
              "FAIL lines above.")
    else:
        print("VERDICT: FAIL — see FAIL lines above.")
    return 0 if all(verdict_checks) else 1


def write_rle(cells, path):
    """standard RLE (B3/S23), origin at the pattern's bbox corner."""
    x0, y0, x1, y1 = bbox(cells)
    rows = defaultdict(list)
    for (x, y) in cells:
        rows[y - y0].append(x - x0)
    items = []                                   # (count, tag) run list
    prev_row = -1
    for y in sorted(rows):
        gap = y - prev_row
        if prev_row >= 0:
            items.append((gap, "$"))
        prev_row = y
        xs = sorted(rows[y])
        cursor = 0
        i = 0
        while i < len(xs):
            j = i
            while j + 1 < len(xs) and xs[j + 1] == xs[j] + 1:
                j += 1
            if xs[i] > cursor:
                items.append((xs[i] - cursor, "b"))
            items.append((j - i + 1, "o"))
            cursor = xs[j] + 1
            i = j + 1
    out = [f"#N Carlini 4-bit ripple-carry adder (6 + 5 = 11)",
           f"#O Nicholas Carlini",
           f"#C {URL}",
           f"x = {x1 - x0 + 1}, y = {y1 - y0 + 1}, rule = B3/S23"]
    line = ""
    for cnt, tag in items:
        tok = (str(cnt) if cnt > 1 else "") + tag
        if len(line) + len(tok) > 69:
            out.append(line)
            line = ""
        line += tok
    out.append(line + "!")
    open(path, "w").write("\n".join(out) + "\n")


if __name__ == "__main__":
    sys.exit(main())
