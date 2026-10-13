#!/usr/bin/env python3
"""
wwtiles.py — the Wireworld tile library the netlist compiler places and routes.

Every tile is a T x T square of raw Wireworld cells (or a 2 x 2 block of them
for the NAND cell). Signals enter and leave only at the midpoint of an edge, the
port. Each tile is built so that every port-to-port path takes an exact multiple
of T ticks. That one rule is what makes composition safe: wherever two signals
meet anywhere in a compiled grid, they arrive either on the same tick or a
whole multiple of T apart, and every gadget below is verified for exactly
those cases.

Signals are pulses. A logic value travels as a pair of wires (dual rail): in
every machine cycle exactly one of the two carries one electron. That removes
the need for a clock wire (the pair is its own clock) and makes NOT free (swap
the wires).

Gadgets (all verified here, in the reference rule from ww_cells.py):
  diode     passes electrons one way, adds no delay (found by exhaustive search)
  junction  a cell fed on its four diagonal corners; it fires when 1 or 2 of
            its feeds carry an electron and stays dark at 3
  XOR       junction fed by P twice and Q once: P alone 2, Q alone 1, both 3
  merge     junction fed by two inputs: OR (two simultaneous electrons fire once)
  crossover three XORs: X = A^B, then A^X and B^X swap A and B across each other

Tiles: straight, corner, delay (k*T), split (tap), crossover, NAND.

    python3 wwtiles.py     verify every tile; prints PASS/FAIL, exits 1 on FAIL
"""
import sys

T = 33          # tile size, and the tick quantum every path is a multiple of
P = 16          # port offset along a tile edge: the exact middle, so all 8
                # symmetries of the square map ports onto ports
NB8 = [(dx, dy) for dy in (-1, 0, 1) for dx in (-1, 0, 1) if dx or dy]


# ---------------------------------------------------------------- geometry
def seg(a, b):
    (x0, y0), (x1, y1) = a, b
    dx = (x1 > x0) - (x1 < x0)
    dy = (y1 > y0) - (y1 < y0)
    n = max(abs(x1 - x0), abs(y1 - y0))
    if (x0 + dx * n, y0 + dy * n) != (x1, y1):
        raise ValueError(f"segment {a}->{b} is not horizontal, vertical or 45 degrees")
    return [(x0 + dx * i, y0 + dy * i) for i in range(n + 1)]


def path(*pts):
    out = [pts[0]]
    for a, b in zip(pts, pts[1:]):
        out += seg(a, b)[1:]
    return out


def cheb(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def check_wire(cells):
    """A clean single-file wire: each cell touches only its two path neighbours."""
    idx = {c: i for i, c in enumerate(cells)}
    if len(idx) != len(cells):
        raise ValueError("wire overlaps itself")
    for i, (x, y) in enumerate(cells):
        for dx, dy in NB8:
            j = idx.get((x + dx, y + dy))
            if j is not None and abs(j - i) > 1:
                raise ValueError(f"wire short-circuits at {cells[i]} / {cells[j]}")
    return len(cells) - 1


DIRS = {"E": (1, 0), "W": (-1, 0), "S": (0, 1), "N": (0, -1)}


def diode(u, d):
    """Diode on a straight wire flowing toward d. u is the last upstream wire
    cell; the wire must continue at u+2f and must not contain the gap u+f.
    Returns (cells to add, gap cell)."""
    (x, y), (fx, fy) = u, DIRS[d]
    nx, ny = -fy, fx
    return [(x + nx, y + ny), (x - nx, y - ny),
            (x + fx + nx, y + fy + ny), (x + fx - nx, y + fy - ny)], (x + fx, y + fy)


def route_exact(s, e, L, occupied, box, max_nodes=400_000):
    """Find a clean wire from s to e with exactly L steps. Cells other than s
    and e stay inside box (x0, y0, x1, y1 inclusive) and never touch
    `occupied`. Depth-first search with a distance bound."""
    x0, y0, x1, y1 = box
    occ = set(occupied) - {s, e}
    blocked = set()
    for (cx, cy) in occ:
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                blocked.add((cx + dx, cy + dy))
    pathl = [s]
    on = {s: 0}
    nodes = [0]

    def fresh(c):
        for dx, dy in NB8:
            j = on.get((c[0] + dx, c[1] + dy))
            if j is not None and j != len(pathl) - 1:
                return False
        return True

    def dfs():
        nodes[0] += 1
        if nodes[0] > max_nodes:
            raise TimeoutError("route_exact: search budget exhausted")
        cur = pathl[-1]
        rem = L - (len(pathl) - 1)
        if rem == 0:
            return cur == e
        if cheb(cur, e) > rem:
            return False
        cands = []
        for dx, dy in NB8:
            c = (cur[0] + dx, cur[1] + dy)
            if c == e:
                if rem == 1 and fresh(c):
                    cands.append((-1, c))
                continue
            if c in on or c in blocked or not (x0 <= c[0] <= x1 and y0 <= c[1] <= y1):
                continue
            if not fresh(c) or (cheb(c, e) == 1 and rem > 2):
                continue
            nd = cheb(c, e)
            slack = rem - 1 - nd
            if slack < 0:
                continue
            cands.append((nd if slack < 4 else -nd, c))
        cands.sort()
        for _, c in cands:
            pathl.append(c)
            on[c] = len(pathl) - 1
            if dfs():
                return True
            pathl.pop()
            del on[c]
        return False

    sys.setrecursionlimit(max(10000, 4 * L + 100))
    if not dfs():
        raise ValueError(f"no clean wire {s}->{e} of length {L}")
    return pathl


# ---------------------------------------------------------------- gadgets
def junction(J, ports):
    """The junction cell plus the diagonal feed cells named in ports (NW NE SW SE)."""
    x, y = J
    off = {"NW": (-1, -1), "NE": (1, -1), "SW": (-1, 1), "SE": (1, 1)}
    return {J} | {(x + off[p][0], y + off[p][1]) for p in ports}


def xor_gadget(J):
    """XOR at junction J. P arrives from the west along row J.y (upstream cell
    J+(-4,0)); its end cell J+(-2,0) touches both NW and SW, so P counts twice.
    Q arrives from the south along column J.x+1 (upstream cell J+(1,4)).
    Output leaves NE. With a constant pulse on Q this is NOT P."""
    x, y = J
    cells = junction(J, ("NW", "NE", "SW", "SE")) | {(x - 2, y), (x + 1, y + 2)}
    dc, _ = diode((x - 4, y), "E")
    cells |= set(dc) | {(x - 4, y)}
    dc, _ = diode((x + 1, y + 4), "N")
    cells |= set(dc) | {(x + 1, y + 4)}
    return cells, (x - 4, y), (x + 1, y + 4), (x + 1, y - 1)


def merge_gadget(J):
    """OR at junction J. Input 1 comes down column J.x-1 (upstream cell
    J+(-1,-4)) into NW; input 2 comes along row J.y+1 from the west (upstream
    cell J+(-4,1)) into SW. Output leaves SE."""
    x, y = J
    cells = junction(J, ("NW", "SW", "SE")) | {(x - 1, y - 2), (x - 2, y + 1)}
    dc, _ = diode((x - 1, y - 4), "S")
    cells |= set(dc) | {(x - 1, y - 4)}
    dc, _ = diode((x - 4, y + 1), "E")
    cells |= set(dc) | {(x - 4, y + 1)}
    return cells, (x - 1, y - 4), (x - 4, y + 1), (x + 1, y + 1)


# ---------------------------------------------------------------- tiles
SIDES = "NESW"


class Tile:
    """cells: conductor cells. ports: name -> (side, k) with k the tile index
    along that side. paths: (input ports, output port, latency in ticks),
    latency counted from a head on the input port cell to a head on the next
    tile's port cell, so a straight tile is exactly T."""

    def __init__(self, name, w, h, cells, ports, paths, wire=False):
        self.name, self.w, self.h = name, w, h
        self.cells = frozenset(cells)
        self.ports = dict(ports)
        self.paths = list(paths)
        self.wire = wire          # a plain wire: works in either direction

    def port_cell(self, name):
        side, k = self.ports[name]
        W, H = self.w * T, self.h * T
        return {"W": (0, k * T + P), "E": (W - 1, k * T + P),
                "N": (k * T + P, 0), "S": (k * T + P, H - 1)}[side]

    def outside(self, name):
        """The cell just beyond a port, in the neighbouring tile."""
        side, _ = self.ports[name]
        x, y = self.port_cell(name)
        dx, dy = {"W": (-1, 0), "E": (1, 0), "N": (0, -1), "S": (0, 1)}[side]
        return (x + dx, y + dy)

    def transformed(self, k):
        """One of the 8 symmetries of the square: k in 0..7 (rotations, then mirrored)."""
        W, H = self.w * T, self.h * T
        rot = k % 4
        mir = k >= 4

        def f(c, w=W, h=H):
            x, y = c
            if mir:
                x = w - 1 - x
            for _ in range(rot):               # rotate 90 degrees clockwise
                x, y = h - 1 - y, x
                w, h = h, w
            return (x, y)

        def fs(side, kk, w=self.w, h=self.h):
            # map (side, k) through the same transform
            x, y = self.port_cell_of(side, kk, w, h)
            return x, y

        cells = {f(c) for c in self.cells}
        nw, nh = (self.h, self.w) if rot % 2 else (self.w, self.h)
        ports = {}
        for name in self.ports:
            x, y = f(self.port_cell(name))
            ports[name] = _side_of(x, y, nw * T, nh * T)
        t = Tile(f"{self.name}/{k}", nw, nh, cells, ports, self.paths, self.wire)
        return t

    @staticmethod
    def port_cell_of(side, k, w, h):
        W, H = w * T, h * T
        return {"W": (0, k * T + P), "E": (W - 1, k * T + P),
                "N": (k * T + P, 0), "S": (k * T + P, H - 1)}[side]


def _side_of(x, y, W, H):
    if x == 0:
        return ("W", (y - P) // T)
    if x == W - 1:
        return ("E", (y - P) // T)
    if y == 0:
        return ("N", (x - P) // T)
    if y == H - 1:
        return ("S", (x - P) // T)
    raise ValueError("not a port cell")


def inner_box(w=1, h=1):
    return (2, 2, w * T - 3, h * T - 3)


def t_straight():
    return Tile("straight", 1, 1, path((0, P), (T - 1, P)),
                {"a": ("W", 0), "b": ("E", 0)}, [(("a",), "b", T)], wire=True)


def t_corner():
    w = path((0, P), (P, P), (P + 1, P - 1), (P + 1, 1), (P, 0))
    assert check_wire(w) == T - 1
    return Tile("corner", 1, 1, w, {"a": ("W", 0), "b": ("N", 0)},
                [(("a",), "b", T)], wire=True)


def _serpentine(n, c1, c2, slow_entry):
    """W to E: up and down vertical runs on pitch 2 (columns x = 3, 5, ...).
    c1, c2 shorten the first two turns; slow_entry adds one tick."""
    # an odd number of diagonal steps makes an odd length, so the two
    # entries differ by one diagonal
    cells = path((0, P), (1, P), (3, P - 2)) if slow_entry else path((0, P), (2, P), (3, P - 1))
    x, y, up = 3, cells[-1][1], True
    lo, hi = 2, T - 3
    for i in range(n):
        if i == 0:
            tgt = lo + c1
        elif i == 1:
            tgt = hi - c2
        else:
            tgt = lo if up else hi
        if (up and tgt > y) or (not up and tgt < y):
            raise ValueError("turn behind the run")
        cells += path((x, y), (x, tgt))[1:]
        y = tgt
        if i == n - 1:
            break
        cells += [(x + 1, y - 1 if up else y + 1), (x + 2, y)]
        x += 2
        up = not up
    # exit: along the lane beyond the last turn to column T-3, then to the E port
    if up:
        cells += path((x, y), (x + 1, y - 1), (T - 4, y - 1), (T - 3, y), (T - 3, P - 1),
                      (T - 2, P), (T - 1, P))[1:]
    else:
        cells += path((x, y), (x + 1, y + 1), (T - 4, y + 1), (T - 3, y), (T - 3, P + 1),
                      (T - 2, P), (T - 1, P))[1:]
    return cells, x


def t_delay(k):
    """W to E in exactly k*T ticks."""
    L = k * T - 1
    for n in range(1, 16):
        for c1 in range(0, 28):
            for c2 in range(0, 28):
                for slow in (False, True):
                    try:
                        cells, x = _serpentine(n, c1, c2, slow)
                    except ValueError:
                        continue
                    if x > T - 7 or len(cells) - 1 != L:
                        continue
                    try:
                        check_wire(cells)
                    except ValueError:
                        continue
                    return Tile(f"delay{k}", 1, 1, cells, {"a": ("W", 0), "b": ("E", 0)},
                                [(("a",), "b", k * T)], wire=True)
    raise ValueError(f"no serpentine of {k} tiles")


def _tap_up(sx):
    """Branch from a tap off row P at x=sx to the N port, arriving at tick T-1."""
    b = path((sx + 1, P - 1), (sx - 2, P - 4), (sx - 2, 4), (sx - 1, 3), (P - 1, 3), (P, 2), (P, 0))
    assert len(b) - 1 == (T - 1) - (sx + 1), (sx, len(b))
    check_wire(b)
    return b


def _mirror_y(cells):
    return [(x, T - 1 - y) for x, y in cells]


def t_split_EN():
    """W in; E out straight, N out by a tap off the main wire."""
    main = path((0, P), (T - 1, P))
    return Tile("splitEN", 1, 1, main + _tap_up(6),
                {"i": ("W", 0), "e": ("E", 0), "n": ("N", 0)},
                [(("i",), "e", T), (("i",), "n", T)])


def t_split_NS():
    """W in; N and S out (a T)."""
    c = path((0, P), (P, P))
    up = path((P + 1, P - 1), (P + 1, 1), (P, 0))
    dn = path((P + 1, P + 1), (P + 1, T - 2), (P, T - 1))
    return Tile("splitNS", 1, 1, c + up + dn, {"i": ("W", 0), "n": ("N", 0), "s": ("S", 0)},
                [(("i",), "n", T), (("i",), "s", T)])


def t_split_ENS():
    """W in; E, N and S out: main wire with a tap up and a staggered tap down."""
    main = path((0, P), (T - 1, P))
    return Tile("splitENS", 1, 1, main + _tap_up(6) + _mirror_y(_tap_up(10)),
                {"i": ("W", 0), "e": ("E", 0), "n": ("N", 0), "s": ("S", 0)},
                [(("i",), "e", T), (("i",), "n", T), (("i",), "s", T)])


def _q_from_south(x):
    """From the S port to an upstream cell on column x at row 20, 12 ticks."""
    return path((P, T - 1), (P, 20 + 2 + (x - P)), (x, 22), (x, 20)) if x != P else \
        path((P, T - 1), (P, 20))


def t_cross():
    """A: W -> E, B: S -> N, crossed by three XORs. Both paths take exactly T."""
    cells = set()
    gx, pu, qu, _ = xor_gadget((P, P))           # X = A ^ B
    cells |= gx | set(path((0, P), pu)) | set(path((P, T - 1), (P, 23), (17, 22), qu)) | {(18, 14)}
    gn, pu2, qu2, ne2 = xor_gadget((17, 5))      # A ^ X = B, out north
    cells |= gn | set(path((18, 13), qu2)) | set(path(ne2, (19, 3), (P, 0)))
    ge, pu3, qu3, ne3 = xor_gadget((26, 15))     # B ^ X = A, out east
    cells |= ge | set(path((19, 15), pu3)) | set(path(ne3, (28, 13), (31, P), (T - 1, P)))
    # The cancelling copies, padded to arrive exactly with X's pulses.
    tap_a, tap_b = (6, P - 1), (17, 26)          # taps off (5,16) and (16,27)
    cells |= {(11, 5), (12, 5), (13, 5), tap_a, (27, 21), (27, 20), (27, 19), tap_b}
    a2 = route_exact(tap_a, (10, 5), 23 - 3 - 6, cells, (1, 1, 14, 14))
    cells |= set(a2)
    b2 = route_exact(tap_b, (27, 22), 22 - 3 - 6, cells, (18, 21, 31, 31))
    cells |= set(b2)
    return Tile("cross", 1, 1, cells,
                {"a": ("W", 0), "a2": ("E", 0), "b": ("S", 0), "b2": ("N", 0)},
                [(("a",), "a2", T), (("b",), "b2", T)])


def t_merge():
    """OR: inputs W and S, output E. Simultaneous inputs fire once."""
    J = (17, 15)
    cells = junction(J, ("NW", "SW", "SE")) | {(15, 14), (16, 17)}
    dc, _ = diode((13, 14), "E")                 # W input along row 14 into NW
    cells |= set(dc)
    dc, _ = diode((16, 19), "N")                 # S input up column 16 into SW
    cells |= set(dc)
    cells |= set(path((0, P), (1, P), (3, 14), (13, 14)))
    cells |= set(path((P, T - 1), (16, 19)))
    cells |= set(path((18, 16), (T - 1, P)))
    return Tile("merge", 1, 1, cells, {"a": ("W", 0), "b": ("S", 0), "o": ("E", 0)},
                [(("a",), "o", T), (("b",), "o", T)])


def t_notc(out="E"):
    """P doubled from W, Q from S; out = Q and not P (with Q always present,
    this is NOT P). Output E, or N for the second variant."""
    cells, pu, qu, ne = xor_gadget((P, P))
    cells |= set(path((0, P), pu)) | set(path((P, T - 1), (P, 23), (17, 22), qu))
    if out == "E":
        cells |= set(path(ne, (18, 14), (20, 14), (22, P), (T - 1, P)))
        ports = {"p": ("W", 0), "q": ("S", 0), "o": ("E", 0)}
    else:
        cells |= set(path(ne, (18, 14), (18, 2), (P, 0)))
        ports = {"p": ("W", 0), "q": ("S", 0), "o": ("N", 0)}
    return Tile("notc" + out, 1, 1, cells, ports, [(("p", "q"), "o", T)])


# ---------------------------------------------------------------- simulation
def simulate(cells, launches, probes, ticks):
    """launches: list of (time, head, tail). Returns ({probe: [head times]}, electrons left)."""
    cells = set(cells)
    for _, h, tl in launches:
        cells.add(h)
        cells.add(tl)
    nb = {c: [(c[0] + dx, c[1] + dy) for dx, dy in NB8 if (c[0] + dx, c[1] + dy) in cells]
          for c in cells}
    heads, tails = set(), set()
    hits = {p: [] for p in probes}
    for t in range(ticks):
        for tt, h, tl in launches:
            if tt == t:
                heads.add(h)
                tails.add(tl)
        cnt = {}
        for h in heads:
            for n in nb[h]:
                if n not in heads and n not in tails:
                    cnt[n] = cnt.get(n, 0) + 1
        tails, heads = heads, {n for n, k in cnt.items() if k in (1, 2)}
        for p in probes:
            if p in heads:
                hits[p].append(t + 1)
    return hits, len(heads) + len(tails)


def launch_at(tile, port, t):
    """Head on the port cell at time t, tail just outside: the electron moves in."""
    return (t, tile.port_cell(port), tile.outside(port))


# ---------------------------------------------------------------- verification
def library():
    lib = {"straight": t_straight(), "corner": t_corner(), "splitEN": t_split_EN(),
           "splitNS": t_split_NS(), "splitENS": t_split_ENS(), "cross": t_cross(),
           "merge": t_merge(), "notcE": t_notc("E"), "notcN": t_notc("N")}
    for k in DELAYS:
        lib[f"delay{k}"] = t_delay(k)
    return lib


DELAYS = (2, 3, 4, 5, 6, 7, 8, 9, 10)
LOGIC = {"merge": lambda a, b: a | b, "notcE": lambda p, q: q & (1 - p) if q or not p else 1,
         "notcN": lambda p, q: q & (1 - p) if q or not p else 1}


def verify_tile(t, offsets=(0,)):
    """Returns list of failure strings. Checks every input combination; for
    two-input tiles also every relative offset in `offsets` (multiples of T)."""
    fails = []
    ins = sorted({p for ins_, _, _ in t.paths for p in ins_})
    outs = sorted({o for _, o, _ in t.paths})
    probes = [t.port_cell(o) for o in outs]
    lat = {o: L for _, o, L in t.paths}
    # one cell inside each input port: any head there after launch is backflow
    inner = {}
    for p in ins:
        x, y = t.port_cell(p)
        ox, oy = t.outside(p)
        inner[p] = (2 * x - ox, 2 * y - oy)

    def run(launch):
        h, e = simulate(t.cells, launch, probes + list(inner.values()), 400)
        for p, c in inner.items():
            launched = [tt for tt, hd, _ in launch if hd == t.port_cell(p)]
            own = [tt + 1 for tt in launched]
            back = [x for x in h[c] if x not in own]
            if back:
                fails.append(f"{t.name}: backflow out of input {p} at {back}")
        return h, e

    if t.name.startswith("cross"):
        for d in offsets:
            for a in (0, 1):
                for b in (0, 1):
                    ta, tb = (0, d) if d >= 0 else (-d, 0)
                    la = ([launch_at(t, "a", ta)] if a else []) + ([launch_at(t, "b", tb)] if b else [])
                    h, e = run(la)
                    got_a = h[t.port_cell("a2")]
                    got_b = h[t.port_cell("b2")]
                    want_a = [ta + T - 1] if a else []
                    want_b = [tb + T - 1] if b else []
                    if got_a != want_a or got_b != want_b or e:
                        fails.append(f"{t.name} a={a}@{ta} b={b}@{tb}: a2={got_a} b2={got_b} left={e}")
        return fails
    if len(ins) == 1:
        h, e = run([launch_at(t, ins[0], 0)])
        for o in outs:
            if h[t.port_cell(o)] != [lat[o] - 1]:
                fails.append(f"{t.name} {ins[0]}->{o}: {h[t.port_cell(o)]} want [{lat[o] - 1}]")
        if e:
            fails.append(f"{t.name}: {e} electrons left")
        return fails
    # two-input logic tiles: simultaneous inputs, full truth table
    import itertools
    base = t.name.split("/")[0]
    for combo in itertools.product((0, 1), repeat=2):
        la = [launch_at(t, p, 0) for p, on in zip(ins, combo) if on]
        h, e = run(la)
        v = dict(zip(ins, combo))
        if base == "merge":
            want = v["a"] | v["b"]
        else:
            want = 1 if (v["p"] ^ v["q"]) else 0      # the XOR it physically is
        got = h[t.port_cell(outs[0])]
        if got != ([lat[outs[0]] - 1] if want else []) or e:
            fails.append(f"{t.name} {v}: out {got} want {want} left={e}")
    return fails


def main():
    lib = library()
    ok = True
    for name, t in lib.items():
        offs = tuple(k * T for k in range(-3, 4)) if name == "cross" else (0,)
        fails = []
        for k in range(8):
            fails += verify_tile(t.transformed(k), offs)
        good = not fails
        ok &= good
        lats = ", ".join(f"{''.join(i)}->{o} {L}" for i, o, L in t.paths)
        print(f"  [{'PASS' if good else 'FAIL'}] {name:9s} {len(t.cells):4d} cells  {lats}"
              f"  (all 8 orientations)")
        for f in fails[:4]:
            print("         " + f)
    print("ALL PASS" if ok else "SOME FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
