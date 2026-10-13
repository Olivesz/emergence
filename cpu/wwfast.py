#!/usr/bin/env python3
"""
wwfast.py — the C stepper (wwfast.c), built on first use with the system C
compiler and loaded with ctypes, plus a check that it matches the reference.

    python3 wwfast.py     cross-check against ww_cells.step; exits 1 on any
                          difference
"""
import ctypes
import hashlib
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "wwfast.c")
_lib = None


def lib():
    global _lib
    if _lib is not None:
        return _lib
    code = open(SRC, "rb").read()
    tag = hashlib.sha256(code).hexdigest()[:16]
    ext = ".dylib" if sys.platform == "darwin" else ".so"
    # Build inside the checkout (gitignored), never in a shared temp directory:
    # a library someone else could write there would be loaded and run.
    cache = os.path.join(HERE, "__wwfast__")
    os.makedirs(cache, mode=0o700, exist_ok=True)
    out = os.path.join(cache, f"wwfast-{tag}{ext}")
    if not os.path.exists(out):
        fd, tmp = tempfile.mkstemp(suffix=ext, dir=cache)
        os.close(fd)
        subprocess.run(["cc", "-O2", "-shared", "-fPIC", "-o", tmp, SRC], check=True)
        os.replace(tmp, out)
    L = ctypes.CDLL(out)
    i64, p = ctypes.c_int64, ctypes.c_void_p
    L.ww_new.restype = p
    L.ww_new.argtypes = [i64, i64, ctypes.c_char_p]
    L.ww_free.argtypes = [p]
    L.ww_run.restype = i64
    L.ww_run.argtypes = [p, i64, ctypes.POINTER(i64), i64, ctypes.c_char_p,
                         ctypes.POINTER(i64), i64, i64]
    L.ww_electrons.restype = i64
    L.ww_electrons.argtypes = [p]
    L.ww_state.argtypes = [p, ctypes.c_char_p]
    _lib = L
    return L


class Grid:
    """A Wireworld grid over the bounding box of `cells` (with a border)."""

    def __init__(self, cells, heads=(), tails=(), border=2):
        xs = [c[0] for c in cells]
        ys = [c[1] for c in cells]
        self.x0, self.y0 = min(xs) - border, min(ys) - border
        self.w = max(xs) - self.x0 + 1 + border
        self.h = max(ys) - self.y0 + 1 + border
        buf = bytearray(self.w * self.h)
        for c in cells:
            buf[self.idx(c)] = 3
        for c in tails:
            buf[self.idx(c)] = 2
        for c in heads:
            buf[self.idx(c)] = 1
        self.s = lib().ww_new(self.w, self.h, bytes(buf))
        if not self.s:
            raise MemoryError("ww_new failed")
        self.t = 0

    @classmethod
    def from_bytes(cls, raw, w, h):
        """A grid from a dense state array (0 empty, 1 head, 2 tail, 3 conductor)."""
        self = cls.__new__(cls)
        self.x0, self.y0, self.w, self.h, self.t = 0, 0, w, h, 0
        self.s = lib().ww_new(w, h, bytes(raw))
        if not self.s:
            raise MemoryError("ww_new failed")
        return self

    def idx(self, c):
        return (c[1] - self.y0) * self.w + (c[0] - self.x0)

    def run(self, n, probes=()):
        """Advance n ticks; returns {probe cell: [ticks it held a head]}."""
        probes = list(probes)
        L = lib()
        pidx = (ctypes.c_int64 * max(1, len(probes)))(*[self.idx(c) for c in probes])
        pmap = bytearray(self.w * self.h) if probes else bytearray(1)
        for c in probes:
            pmap[self.idx(c)] = 1
        cap = 1 << 16
        hits = {c: [] for c in probes}
        done = 0
        while done < n:
            chunk = min(n - done, 1 << 20)
            while True:
                out = (ctypes.c_int64 * cap)()
                # run on a copy-free basis: if the buffer overflows, grow and redo
                # this chunk from a saved state
                saved = self.state() if probes else None
                k = L.ww_run(self.s, chunk, pidx, len(probes), bytes(pmap), out, cap, self.t)
                if k >= 0:
                    break
                if k == -2:
                    raise MemoryError("ww_run out of memory")
                self._load(saved)
                cap *= 4
            for j in range(k):
                hits[probes[out[2 * j + 1]]].append(out[2 * j])
            self.t += chunk
            done += chunk
        return hits

    def state(self):
        buf = ctypes.create_string_buffer(self.w * self.h)
        lib().ww_state(self.s, buf)
        return buf.raw

    def _load(self, raw):
        lib().ww_free(self.s)
        self.s = lib().ww_new(self.w, self.h, raw)

    def electrons(self):
        return lib().ww_electrons(self.s)

    def __del__(self):
        if getattr(self, "s", None):
            lib().ww_free(self.s)
            self.s = None


def crosscheck(cells, heads, tails, ticks):
    """Step the C engine and the reference rule side by side; True if every
    cell matches after every tick."""
    from ww_cells import step
    g = Grid(cells, heads, tails)
    ref = bytearray(g.state())
    for t in range(ticks):
        ref = step(g.w, g.h, list(ref))
        g.run(1)
        if bytes(ref) != g.state():
            return False, t + 1
    return True, ticks


if __name__ == "__main__":
    import random
    from wwtiles import library, T
    ok = True
    lib_ = library()
    # 1) a crossover fed from both sides, plus a merge and a NOT-with-clock
    rnd = random.Random(7)
    for name in ("cross", "merge", "notcE", "splitENS", "delay5"):
        t = lib_[name]
        heads, tails = [], []
        for p in [p for p in t.ports if p in ("a", "b", "i", "p", "q")]:
            if rnd.random() < 0.8:
                heads.append(t.port_cell(p))
                tails.append(t.outside(p))
        cells = set(t.cells) | set(tails)
        good, n = crosscheck(cells, heads, tails, 3 * T)
        ok &= good
        print(f"  [{'PASS' if good else 'FAIL'}] {name}: C engine == reference rule for {n} ticks")
    # 2) a random soup with many electrons
    cells = {(x, y) for x in range(60) for y in range(40) if rnd.random() < 0.45}
    heads = [c for c in cells if rnd.random() < 0.1]
    tails = [c for c in cells if c not in heads and rnd.random() < 0.1]
    good, n = crosscheck(cells, heads, tails, 200)
    ok &= good
    print(f"  [{'PASS' if good else 'FAIL'}] random soup: C engine == reference rule for {n} ticks")
    print("ALL PASS" if ok else "SOME FAILED")
    raise SystemExit(0 if ok else 1)
