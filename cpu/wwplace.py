#!/usr/bin/env python3
"""
wwplace.py — place and route a lowered gadget netlist (wwlower.py) on a grid of
Wireworld tiles (wwtiles.py), then emit the raw cells.

Time is counted in tile units (one unit = T ticks). Every tile on a route adds
exactly its latency in units, so a route's arrival time is its length. Each
gadget's inputs must arrive on the same unit; the router finds a shortest
path for every input and then pads the early ones with delay tiles until they
all arrive together. Register points close each flip-flop's loop: the value
that arrives at a register at unit P (the machine period) is the value it
sends out at unit 0 of the next cycle.

Routes may cross each other (a crossover tile) wherever both are straight and
perpendicular. A route branches (fan-out) at any of its own plain tiles by
turning it into a split tile.
"""
import heapq
from collections import defaultdict

from wwtiles import T, P, library, DELAYS

DIRV = {"N": (0, -1), "E": (1, 0), "S": (0, 1), "W": (-1, 0)}
OPP = {"N": "S", "S": "N", "E": "W", "W": "E"}
MAXD = max(DELAYS)


class Seg:
    """One net's use of a wire tile: entered from side `src` at unit `t`,
    leaving on `outs`. `delay` > 1 makes it a delay tile."""
    __slots__ = ("net", "src", "outs", "t", "delay")

    def __init__(self, net, src, outs, t, delay=1):
        self.net, self.src, self.outs, self.t, self.delay = net, src, list(outs), t, delay


class Layout:
    margin = 2
    schedule = "asap"

    def __init__(self, nl, info):
        self.nl, self.info = nl, info
        self.gpos = {}          # gadget -> tile
        self.gside = {}         # gadget -> {port: side}, plus 'o' for its output
        self.tau = {}           # gadget -> unit its inputs arrive (registers: 0)
        self.tiles = {}         # tile -> ('g', gadget) or [Seg, ...]
        self.tree = defaultdict(dict)   # net -> {tile: Seg}
        self.period = None
        self.stats = defaultdict(int)

    # ------------------------------------------------------------ placement
    def place(self, colgap=3, rowgap=3):
        nl = self.nl
        src_kinds = ("reg", "in")
        level = {}
        order = []
        from wwlower import topo_order
        for g in topo_order(nl):
            if nl.kind[g] in src_kinds:
                level[g] = 0
            else:
                level[g] = 1 + max(level[s] for s in nl.ins[g].values())
            order.append(g)
        self.level = level
        cols = defaultdict(list)
        for g in order:
            cols[level[g]].append(g)
        y = {}
        # initial order: sources by index, others by barycentre of their sources
        for g in cols[0]:
            y[g] = len([h for h in cols[0] if h < g])
        sinks = nl.sinks()
        for sweep in range(4):
            for lv in sorted(cols):
                if lv == 0 and sweep == 0:
                    continue
                def key(g):
                    if lv == 0:
                        ys = [y[s] for s, _ in sinks.get(g, []) if s in y]
                    else:
                        ys = [y[s] for s in nl.ins[g].values() if s in y]
                    return sum(ys) / len(ys) if ys else 0
                cols[lv].sort(key=key)
                n = len(cols[lv])
                for i, g in enumerate(cols[lv]):
                    y[g] = i - n / 2
        height = max(len(v) for v in cols.values())
        self.rowgap, self.colgap = rowgap, colgap
        top = 4
        for lv, gs in cols.items():
            n = len(gs)
            off = (height - n) // 2
            for i, g in enumerate(gs):
                tx = 4 + lv * (colgap + 1)
                ty = top + (off + i) * (rowgap + 1)
                self.gpos[g] = (tx, ty)
                self.tiles[(tx, ty)] = ("g", g)
        self.W = 4 + (max(cols) + 1) * (colgap + 1) + 8
        self.H = top + height * (rowgap + 1) + 8
        # orientations: output east; the second input faces its source
        for g, (tx, ty) in self.gpos.items():
            k = nl.kind[g]
            if k in src_kinds:
                self.gside[g] = {"o": "E"}          # input side chosen by the router
            elif k == "out":
                self.gside[g] = {"d": "W"}
            else:
                ins = nl.ins[g]
                names = ("a", "b") if k == "merge" else ("p", "q")
                ya = self.gpos[ins[names[0]]][1] if ins[names[0]] in self.gpos else ty
                yb = self.gpos[ins[names[1]]][1] if ins[names[1]] in self.gpos else ty
                # whichever source is further off the gadget's row comes in on N/S
                if abs(yb - ty) >= abs(ya - ty):
                    w, v = names
                else:
                    v, w = names
                vy = self.gpos[ins[v]][1]
                self.gside[g] = {w: "W", v: ("N" if vy < ty else "S"), "o": "E"}
        # Each port's neighbouring tile is kept for the one net that uses it.
        self.reserved = {}
        for g, (tx, ty) in self.gpos.items():
            k = nl.kind[g]
            for port, side in self.gside[g].items():
                dx, dy = DIRV[side]
                t = (tx + dx, ty + dy)
                if port == "o":
                    self.reserved[t] = (g, None)          # first tile of g's own net
                else:
                    self.reserved[t] = (nl.ins[g][port], t)   # only as that route's last tile
            if k == "reg":
                self.gside[g]["d"] = "W"
                self.reserved[(tx - 1, ty)] = (nl.ins[g]["d"], (tx - 1, ty))

    # ------------------------------------------------------------ routing
    def free_for(self, tile, net, s_in, s_out, goal=None):
        """Can `net` pass through `tile` entering at s_in and leaving at s_out?
        Returns 'free', 'cross' or None."""
        x, y = tile
        if not (0 <= x < self.W and 0 <= y < self.H):
            return None
        r = self.reserved.get(tile)
        if r is not None and (r[0] != net or (r[1] is not None and r[1] != goal)):
            return None
        u = self.tiles.get(tile)
        if u is None:
            return "free"
        if isinstance(u, tuple):
            return None
        if len(u) != 1:
            return None
        s = u[0]
        if s.net == net or s.delay != 1 or len(s.outs) != 1:
            return None
        if OPP[s.src] != s.outs[0] or OPP[s_in] != s_out:
            return None                       # both must be straight
        if s.src in (s_in, s_out):
            return None                       # and perpendicular
        return "cross"

    def starts(self, net):
        """Places a new branch of `net` can begin: (first tile, side entered, unit)."""
        out = []
        g = net
        if not self.tree[net]:
            tx, ty = self.gpos[g]
            so = self.gside[g]["o"]
            dx, dy = DIRV[so]
            out.append(((tx + dx, ty + dy), OPP[so], self.tau[g] + 1, None))
            return out
        for tile, s in self.tree[net].items():
            u = self.tiles[tile]
            if len(u) != 1 or s.delay != 1 or len(s.outs) >= 3 or isinstance(u, tuple):
                continue
            for side in "NESW":
                if side == s.src or side in s.outs:
                    continue
                dx, dy = DIRV[side]
                out.append(((tile[0] + dx, tile[1] + dy), OPP[side], s.t + 1, (tile, side)))
        return out

    def goal_of(self, sink, port):
        side = self.gside[sink][port]
        sx, sy = self.gpos[sink]
        dx, dy = DIRV[side]
        return (sx + dx, sy + dy), OPP[side], (sx, sy), side

    def astar(self, net, starts, goal, goal_out, sink_tile, blocked=frozenset(),
              max_expand=60000):
        """starts: [(first tile, side entered, tag)]. Finds the fewest-tile path
        whose last tile is `goal`, leaving it on `goal_out`. Returns (path, tag)
        with path = [(tile, s_in, s_out)], or None."""
        heap, best, prev, tagof = [], {}, {}, {}
        cnt = 0
        for (tile, s_in, tag) in starts:
            if tile in blocked or tile == sink_tile:
                continue
            key = (tile, s_in)
            if key not in best:
                best[key] = 0.0
                tagof[key] = tag
                h = abs(tile[0] - goal[0]) + abs(tile[1] - goal[1])
                heapq.heappush(heap, (h, cnt, 0.0, tile, s_in))
                cnt += 1
        expanded = 0
        while heap:
            f, _, gcost, tile, s_in = heapq.heappop(heap)
            key = (tile, s_in)
            if best[key] < gcost:
                continue
            expanded += 1
            if expanded > max_expand:
                return None
            for s_out in "NESW":
                if s_out == s_in:
                    continue
                kind = self.free_for(tile, net, s_in, s_out, goal)
                if kind is None:
                    continue
                if tile == goal and s_out == goal_out:
                    path = [(tile, s_in, s_out)]
                    k = key
                    while k in prev:
                        k2, so = prev[k]
                        path.append((k2[0], k2[1], so))
                        k = k2
                    path.reverse()
                    return path, tagof[k]
                dx, dy = DIRV[s_out]
                nxt = (tile[0] + dx, tile[1] + dy)
                if nxt == sink_tile or nxt in blocked:
                    continue
                step = 1.0 + (0.3 if kind == "cross" else 0.0) + \
                    (0.05 if OPP[s_in] != s_out else 0.0)
                ng = gcost + step
                nkey = (nxt, OPP[s_out])
                if nkey not in best or best[nkey] > ng:
                    best[nkey] = ng
                    prev[nkey] = (key, s_out)
                    h = abs(nxt[0] - goal[0]) + abs(nxt[1] - goal[1])
                    heapq.heappush(heap, (ng + h, cnt, ng, nxt, OPP[s_out]))
                    cnt += 1
        return None

    def route(self, net, sink, port, blocked=frozenset()):
        """Shortest route from the net's tree into sink's port:
        (path, first-tile unit t0, branch point) — arrival is t0 + len(path)."""
        goal, goal_out, sink_tile, side = self.goal_of(sink, port)
        sts = self.starts(net)
        for (tile, s_in, t0, bp) in sts:
            if tile == sink_tile and s_in == side:
                return [], t0, bp
        r = self.astar(net, [(tile, s_in, (t0, bp)) for tile, s_in, t0, bp in sts],
                       goal, goal_out, sink_tile, blocked)
        if r is None:
            return None
        path, (t0, bp) = r
        return path, t0, bp

    def capacity(self, path):
        """Most units a fresh branch can absorb: a free straight tile can hold a
        delay tile; anything else (a turn, a crossing) is exactly one unit."""
        return sum(MAXD if (OPP[si] == so and tile not in self.tiles) else 1
                   for tile, si, so in path)

    def route_timed(self, net, sink, port, tau, window=16, max_expand=200000):
        """A route that arrives exactly at unit tau once its free straight tiles
        become delay tiles: n tiles with total room c work when n <= tau-t0 <= c.
        Uniform-cost search on (tile, side entered, room still missing); the
        first route to reach the sink missing nothing is the shortest that fits."""
        r = self.route(net, sink, port)
        if r is None:
            return None
        path, t0, bp = r
        if len(path) <= tau - t0 <= self.capacity(path):
            return path, t0, bp
        goal, goal_out, sink_tile, side = self.goal_of(sink, port)
        starts = [st for st in self.starts(net) if st[0] != sink_tile and tau - st[2] >= 1]
        if not starts:
            return None
        xs = [goal[0]] + [st[0][0] for st in starts]
        ys = [goal[1]] + [st[0][1] for st in starts]
        x0, y0 = min(xs) - window, min(ys) - window
        x1, y1 = max(xs) + window, max(ys) + window

        def h(t):
            return abs(t[0] - goal[0]) + abs(t[1] - goal[1])

        heap, seen, cnt = [], set(), 0
        for (tile, s_in, ts, bps) in starts:
            # node: (tile, s_in, missing room, tiles so far, parent, start)
            node = (tile, s_in, tau - ts, 0, None, (ts, bps))
            heapq.heappush(heap, (h(tile), cnt, node))
            cnt += 1
        expanded = 0
        while heap:
            _, _, node = heapq.heappop(heap)
            tile, s_in, miss, n, par, start = node
            key = (tile, s_in, miss)
            if key in seen:
                continue
            seen.add(key)
            expanded += 1
            if expanded > max_expand:
                return None
            onpath, p = set(), par
            while p is not None:
                onpath.add(p[0][0])
                p = p[1]
            for s_out in "NESW":
                if s_out == s_in:
                    continue
                kind = self.free_for(tile, net, s_in, s_out, goal)
                if kind is None:
                    continue
                room = MAXD if (kind == "free" and OPP[s_in] == s_out) else 1
                nmiss = max(0, miss - room)
                step = (tile, s_in, s_out)
                if tile == goal and s_out == goal_out:
                    if nmiss == 0 and start[0] + n + 1 <= tau:
                        out, p = [step], par
                        while p is not None:
                            out.append(p[0])
                            p = p[1]
                        out.reverse()
                        return out, start[0], start[1]
                    continue
                dx, dy = DIRV[s_out]
                nxt = (tile[0] + dx, tile[1] + dy)
                if nxt == sink_tile or nxt in onpath:
                    continue
                if not (x0 <= nxt[0] <= x1 and y0 <= nxt[1] <= y1):
                    continue
                if start[0] + n + 1 + h(nxt) + 1 > tau:
                    continue
                child = (nxt, OPP[s_out], nmiss, n + 1, (step, par), start)
                heapq.heappush(heap, (n + 1 + h(nxt), cnt, child))
                cnt += 1
        return None

    def commit(self, net, path, t0, bp):
        """Write a found route into the grid; returns its Seg list."""
        segs = []
        if bp is not None:
            tile, side = bp
            self.tree[net][tile].outs.append(side)
        t = t0
        for tile, s_in, s_out in path:
            s = Seg(net, s_in, [s_out], t)
            u = self.tiles.get(tile)
            if u is None:
                self.tiles[tile] = [s]
            else:
                u.append(s)
                self.stats["crossings"] += 1
            self.tree[net][tile] = s
            segs.append(s)
            t += 1
        return segs

    def pad(self, segs, need, arrival_end):
        """Add `need` units along segs (a fresh branch) with delay tiles.
        Returns the units it could not place."""
        if need <= 0:
            return 0
        cands = [s for s in segs if OPP[s.src] == s.outs[0] and
                 len(self._tile_of(s)) == 1]
        for s in cands:
            if need <= 0:
                break
            add = min(MAXD - 1, need)
            if add + 1 not in DELAYS:
                add -= 1
            if add <= 0:
                continue
            s.delay = add + 1
            need -= add
        # re-time the branch
        if segs:
            t = segs[0].t
            for s in segs:
                s.t = t
                t += s.delay
        return need

    def _tile_of(self, seg):
        for tile, s in self.tree[seg.net].items():
            if s is seg:
                return self.tiles[tile]
        raise KeyError

    def route_all(self, log=None):
        nl = self.nl
        from wwlower import topo_order
        order = topo_order(nl)
        for g in order:
            if nl.kind[g] in ("reg", "in"):
                self.tau[g] = 0
        done = 0
        for g in order:
            if nl.kind[g] in ("reg", "in"):
                continue
            self._route_inputs(g, list(nl.ins[g].items()))
            done += 1
            if log and done % 500 == 0:
                log(f"  routed {done} gadgets")
        # registers: the period is the latest D arrival; every loop is padded to it
        regs = [g for g in order if nl.kind[g] == "reg"]
        best = {}
        for g in regs:
            src = nl.ins[g]["d"]
            cands = []
            for side in self._reg_in_sides(g):
                self.gside[g]["d"] = side
                r = self.route(src, g, "d")
                if r is not None:
                    cands.append((r[1] + len(r[0]), side))
            if not cands:
                raise RuntimeError(f"cannot route register {g}")
            best[g] = min(cands)
        if not regs:
            return
        self.period = max(a for a, _ in best.values())
        for g in sorted(regs, key=lambda g: -best[g][0]):
            src = nl.ins[g]["d"]
            placed = False
            for side in [best[g][1]] + [s for s in self._reg_in_sides(g) if s != best[g][1]]:
                self.gside[g]["d"] = side
                r = self.route_timed(src, g, "d", self.period)
                if r is not None:
                    path, t0, bp = r
                    segs = self.commit(src, path, t0, bp)
                    if self.pad(segs, self.period - (t0 + len(path)), self.period):
                        raise RuntimeError("padding accounting error")
                    placed = True
                    break
            if not placed:
                raise RuntimeError(f"register {g}: no route reaches the period {self.period}")

    def _t0(self, net, bp):
        if bp is None:
            return self.tau[net] + 1
        return self.tree[net][bp[0]].t + 1

    def _reg_in_sides(self, g):
        tx, ty = self.gpos[g]
        return [side for side in ("W", "N", "S")
                if (tx + DIRV[side][0], ty + DIRV[side][1]) not in self.tiles]

    def _route_inputs(self, g, ins):
        """Schedule g at the latest earliest-arrival over its inputs (or, with
        schedule='estimate', source time + distance + margin), then route every
        input to arrive exactly then. If congestion defeats that, try later."""
        est = 0
        for port, src in ins:
            if self.schedule == "asap":
                r = self.route(src, g, port)
                if r is None:
                    raise RuntimeError(f"gadget {g}: no route for input {port}")
                est = max(est, r[1] + len(r[0]))
            else:
                goal = self.goal_of(g, port)[0]
                first = self.first_tile(src)
                d = abs(first[0] - goal[0]) + abs(first[1] - goal[1])
                est = max(est, self.tau[src] + 1 + d + 1 + self.margin + d // 4)
        for attempt in range(10):
            tau = est + attempt * (2 + attempt)
            committed, failed = [], None
            for port, src in sorted(ins, key=lambda ps: self.tau[ps[1]], reverse=True):
                r = self.route_timed(src, g, port, tau)
                if r is None:
                    failed = (port, src)
                    break
                path, t0, bp = r
                segs = self.commit(src, path, t0, bp)
                committed.append((src, segs, bp))
                if self.pad(segs, tau - (t0 + len(path)), tau):
                    raise RuntimeError("padding accounting error")
            if failed is None:
                self.tau[g] = tau
                self.stats["late"] += attempt
                return
            for src, segs, bp in reversed(committed):
                self.uncommit(src, segs, bp)
        port, src = failed
        self.last_fail = (g, port, src, {}, tau, self.route(src, g, port))
        raise RuntimeError(f"gadget {g}: input {port} cannot be routed on time")

    def first_tile(self, g):
        tx, ty = self.gpos[g]
        dx, dy = DIRV[self.gside[g]["o"]]
        return (tx + dx, ty + dy)

    def uncommit(self, net, segs, bp):
        for s in segs:
            tile = next(t for t, v in self.tree[net].items() if v is s)
            u = self.tiles[tile]
            u.remove(s)
            if not u:
                del self.tiles[tile]
            del self.tree[net][tile]
        if bp is not None:
            tile, side = bp
            self.tree[net][tile].outs.remove(side)


# ---------------------------------------------------------------- emission
_LIB = None
_XF = {}


def lib():
    global _LIB
    if _LIB is None:
        _LIB = library()
    return _LIB


def oriented(name, want):
    """The transform of library tile `name` whose ports sit on the sides in
    `want` ({port: side}); None if no symmetry fits."""
    key = (name, tuple(sorted(want.items())))
    if key not in _XF:
        base = lib()[name]
        _XF[key] = None
        for k in range(8):
            t = base.transformed(k)
            if all(t.ports[p][0] == s for p, s in want.items()):
                _XF[key] = t
                break
    return _XF[key]


def wire_tile(src, outs, delay=1):
    outs = list(outs)
    if delay > 1:
        return oriented(f"delay{delay}", {"a": src, "b": outs[0]})
    if len(outs) == 1:
        if OPP[src] == outs[0]:
            return oriented("straight", {"a": src, "b": outs[0]})
        return oriented("corner", {"a": src, "b": outs[0]})
    if len(outs) == 3:
        o = set(outs)
        for name in ("splitENS",):
            for k in range(8):
                t = lib()[name].transformed(k)
                if t.ports["i"][0] == src and {t.ports[p][0] for p in ("e", "n", "s")} == o:
                    return t
    o = set(outs)
    for name, ps in (("splitEN", ("e", "n")), ("splitNS", ("n", "s"))):
        for k in range(8):
            t = lib()[name].transformed(k)
            if t.ports["i"][0] == src and {t.ports[p][0] for p in ps} == o:
                return t
    raise ValueError(f"no split tile for {src} -> {outs}")


def cross_tile(s1, s2):
    for a, b in ((s1, s2), (s2, s1)):
        t = oriented("cross", {"a": a.src, "a2": a.outs[0], "b": b.src, "b2": b.outs[0]})
        if t is not None:
            return t
    raise ValueError("no crossover orientation")


def gadget_tile(kind, sides):
    if kind == "merge":
        for a, b in (("a", "b"), ("b", "a")):
            t = oriented("merge", {"a": sides[a], "b": sides[b], "o": sides["o"]})
            if t is not None:
                return t
    if kind == "notc":
        for name in ("notcE", "notcN"):
            t = oriented(name, {"p": sides["p"], "q": sides["q"], "o": sides["o"]})
            if t is not None:
                return t
    raise ValueError(f"no {kind} orientation for {sides}")


def emit(L):
    """Raw cells of the whole layout, plus where to start and watch it.
    Returns dict(cells=set, heads=set, tails=set, probes={gadget: cell})."""
    cells, heads, tails, probes, launch = set(), set(), set(), {}, {}
    nl = L.nl
    for tile, u in L.tiles.items():
        ox, oy = tile[0] * T, tile[1] * T
        if isinstance(u, tuple):
            g = u[1]
            k = nl.kind[g]
            if k in ("merge", "notc"):
                t = gadget_tile(k, L.gside[g])
            elif k in ("reg", "in"):
                t = wire_tile(L.gside[g].get("d", "W"), [L.gside[g]["o"]])
                pc = t.port_cell("a")
                entry = (ox + pc[0], oy + pc[1])
                dx, dy = DIRV[t.ports["a"][0]]
                probes[g] = entry
                launch[g] = (entry, (entry[0] + dx, entry[1] + dy))
            else:                                     # out: a plain stub
                t = wire_tile(L.gside[g]["d"], [OPP[L.gside[g]["d"]]])
                pc = t.port_cell("a")
                probes[g] = (ox + pc[0], oy + pc[1])
        elif len(u) == 1:
            s = u[0]
            t = wire_tile(s.src, s.outs, s.delay)
        else:
            t = cross_tile(u[0], u[1])
        if t is None:
            raise ValueError(f"tile {tile}: no orientation")
        for (x, y) in t.cells:
            cells.add((ox + x, oy + y))
    return dict(cells=cells, probes=probes, launch=launch)
