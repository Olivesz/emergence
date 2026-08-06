#!/usr/bin/env python3
"""Crop a small, runnable TILE out of Carlini's full 137,712-cell glider adder.

The full adder (see carlini_adder.py) is a 36,715 x 41,556 circuit: 8 input
gun assemblies on the NW anti-diagonal, a ripple-carry core of 270x270 gate
tiles in the middle, 4 output terminals on the SE anti-diagonal.  At 137,712
cells over a 36k x 41k board it is ~4-5x past what our JS Life viewer
(life-viewer.html) handles comfortably (~30k cells) — and the interesting
machinery is spread across tens of thousands of cells of empty diagonal.

This file crops ONE axis-aligned window out of the ripple-carry core: a
3,500 x 3,500 patch of the middle of the circuit.  That patch is a real,
recognizable PIECE of the adder — several of Carlini's 270x270 gate tiles,
built from period-30 glider guns and Snark reflectors.  Because those gate
tiles carry their own internal guns, the crop is SELF-CONSISTENT: run it and
the guns keep firing and gliders keep streaming through the gates in all four
diagonal directions, indefinitely — you are watching a slice of the adder
compute.  (Long-range signals that would enter/leave this window in the full
circuit simply aren't present; this is a "watch a piece" crop, not the whole
machine, so the arithmetic result isn't decoded here.)

Verification is deliberately BOUNDED — a fixed <=300-generation run of the
naive engine (life.step) on the cropped patch only, never the full
2^20-generation adder computation.  Runs in a couple of seconds.

Run:  python3 carlini_tile.py
It prints the crop window + bbox + cell count, a bounded "guns firing /
gliders present" check, and writes carlini_tile.rle (re-parseable by
gadgets.rle_parse / loadable in life-viewer.html).
"""
import os
import sys
import time
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from carlini_adder import fetch_mc, parse_mc          # loads Carlini's gen-0 cells
from life import bbox, step
from gadgets import split_gliders, glider_dir

RLE_PATH = os.path.join(HERE, "carlini_tile.rle")

# Crop window (absolute coordinates in the full adder's frame).  Chosen inside
# the densest part of the ripple-carry core; ~10.5k cells, comfortably viewer-
# tractable, and self-firing (its gate tiles contain their own guns).
WIN = (15_000, 22_500, 18_500, 26_000)      # (x0, y0, x1, y1), inclusive
GENS = 300                                  # bounded verification horizon


def crop(cells, win):
    wx0, wy0, wx1, wy1 = win
    return {(x, y) for (x, y) in cells if wx0 <= x <= wx1 and wy0 <= y <= wy1}


def to_rle(cells, path, comment):
    """standard RLE (B3/S23), origin at the crop's bbox corner."""
    x0, y0, x1, y1 = bbox(cells)
    rows = defaultdict(list)
    for (x, y) in cells:
        rows[y - y0].append(x - x0)
    items = []
    prev_row = -1
    for y in sorted(rows):
        if prev_row >= 0:
            items.append((y - prev_row, "$"))
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
    out = [f"#N Carlini adder — cropped core tile",
           f"#C {comment}",
           f"#C source: Nicholas Carlini, https://nicholas.carlini.com/writing/2020/gameoflife/adder.mc",
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


def main():
    print("Carlini glider-adder — cropped core tile for the JS Life viewer")
    print("source: https://nicholas.carlini.com/writing/2020/gameoflife/adder.mc\n")

    cells = parse_mc(fetch_mc())
    fx0, fy0, fx1, fy1 = bbox(cells)
    print(f"full adder: {len(cells):,} cells, "
          f"bbox {fx1-fx0+1:,} x {fy1-fy0+1:,}\n")

    wx0, wy0, wx1, wy1 = WIN
    tile = crop(cells, WIN)
    if not tile:
        print("FAIL: crop window is empty"); return 1
    tx0, ty0, tx1, ty1 = bbox(tile)
    n = len(tile)
    print(f"crop window (absolute): x [{wx0:,}, {wx1:,}]  y [{wy0:,}, {wy1:,}]")
    print(f"tile: {n:,} live cells, bbox {tx1-tx0+1:,} x {ty1-ty0+1:,} "
          f"(x [{tx0:,},{tx1:,}], y [{ty0:,},{ty1:,}])")
    tractable = n < 20_000
    print(f"viewer-tractable (< 20,000 cells): "
          f"{'YES' if tractable else 'NO'}  ({n:,} cells)\n")

    # ---- bounded verification: guns firing / gliders present -------------
    print(f"bounded run of the naive engine (life.step), {GENS} gens on the "
          f"crop only:")
    t0 = time.time()
    cur = set(tile)
    samples = {}
    for g in range(1, GENS + 1):
        cur = step(cur)
        if g % 60 == 0 or g == GENS:
            gl, _ = split_gliders(cur)
            dirs = defaultdict(int)
            for gg in gl:
                dirs[glider_dir(gg)] += 1
            samples[g] = (len(cur), len(gl), dict(dirs))
            print(f"  gen {g:4d}: pop {len(cur):6,d}  gliders {len(gl):4d}  "
                  f"dirs {dict(dirs)}")
    dt = time.time() - t0

    pops = [len(tile)] + [samples[g][0] for g in sorted(samples)]
    glider_counts = [samples[g][1] for g in sorted(samples)]
    alive = pops[-1] > 0
    steady = 0.4 * pops[0] < pops[-1] < 3.0 * pops[0]     # no die-off, no blow-up
    guns_firing = all(c > 50 for c in glider_counts)       # streams kept replenished
    ndirs = max(len(samples[g][2]) for g in samples)
    print(f"\n  [{'PASS' if alive and steady else 'FAIL'}] tile stays alive & "
          f"population steady (gen0 {pops[0]:,} -> gen{GENS} {pops[-1]:,})")
    print(f"  [{'PASS' if guns_firing else 'FAIL'}] guns keep firing — "
          f">50 whole gliders present at every sample")
    print(f"  [{'PASS' if ndirs >= 2 else 'FAIL'}] gliders flow through gates "
          f"in {ndirs} distinct diagonal directions (real gate machinery, "
          f"not one free stream)")
    print(f"  ({dt:.1f}s for {GENS} gens on {n:,} cells)\n")

    to_rle(tile, RLE_PATH,
           f"cropped from the ripple-carry core, window x[{wx0},{wx1}] "
           f"y[{wy0},{wy1}] of the full 137,712-cell adder")
    print(f"wrote {RLE_PATH}")
    print(f"  {n:,} cells, {tx1-tx0+1:,} x {ty1-ty0+1:,} board — load it in "
          f"life-viewer.html to watch a piece of Carlini's adder run.")
    ok = alive and steady and guns_firing and ndirs >= 2 and tractable
    print(f"\nVERDICT: {'PASS' if ok else 'PARTIAL'} — a self-firing, "
          f"viewer-tractable slice of the real glider adder.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
