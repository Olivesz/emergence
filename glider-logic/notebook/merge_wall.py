#!/usr/bin/env python3
"""The mutex OR-merge — the primitive the compiled XOR (sum) and carry-OR both need:
route two NEVER-simultaneous SE gliders onto ONE output lane so 'a glider on L_out'
reads their OR.

The make-or-break physics question (settled here in the bare rule, not argued):
when leg-B is shifted onto leg-A's lane by a 2-Snark shifter whose exit Snark Sb
sits ON that lane, can leg-A's own glider fly PAST Sb to reach the output port —
or does Sb obstruct it? If it flies past cleanly, we have a physical single-lane OR.
If not, that's the second wall (after parity), and dual-rail is the way.

BOUNDED single-glider sims; prints a decisive PASS/FAIL. Run: python3 -u merge.py
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from life import run, bbox
from gadgets import split_gliders, glider_dir, glider_lane, glider_phase
from routed import build_variants, bbox_gap
import gates
from lane_shift import build_shift  # SE lane L_in -> SE lane L_out, parity-conserving

t0 = time.time()
V = build_variants()

L1 = -1       # leg-A native output lane (proven shifter target)
L2 = -47      # leg-B native lane (same parity as L1; shifter reaches -47 -> -1)
LOUT = L1     # merge target: leg-A's lane


def all_shifters(L_in, L_out):
    """Every clean 2-Snark SE->SW->SE shifter L_in->L_out (its exit Snark sits on
    L_out). Yields (mcats, exit_Snark_cells, dx1)."""
    for dx1 in range(-40, 300):
        b = build_shift(L_in, L_out, dx1)
        if not b:
            continue
        cats, p1, p2 = b
        gin = V['snark_m0r1'].input_glider(*p1, back=6)
        if set(gin) & cats:
            continue
        gs, rest = split_gliders(run(cats | set(gin), 1400))
        if rest == cats and len(gs) == 1 and glider_dir(gs[0]) == (1, 1) \
                and glider_lane(gs[0]) == L_out:
            yield cats, V['snark_m1r0'].place(*p2), dx1


def flyby(mcats, exitcat):
    """Fire leg-A on LOUT from upstream of the exit Snark; does it pass cleanly?"""
    sbx0, sby0, _, _ = bbox(exitcat)
    xA = sbx0 - 60
    gA = gates.glider('SE', xA, xA + LOUT)          # SE on lane LOUT, upstream of Sb
    assert glider_lane(gA) == LOUT
    if (set(gA) & mcats) or bbox_gap(gA, mcats) < 4:
        return None
    gs, rest = split_gliders(run(set(gA) | mcats, 2200))
    return (rest == mcats and len(gs) == 1
            and glider_dir(gs[0]) == (1, 1) and glider_lane(gs[0]) == LOUT)


print(f"mutex-merge: leg-B lane {L2} -> shifter -> lane {LOUT}; leg-A native on {LOUT}.",
      flush=True)
print("sweeping EVERY clean shifter placement; does leg-A ever fly past Sb?", flush=True)
tested = clean = 0
for mcats, exitcat, dx1 in all_shifters(L2, LOUT):
    r = flyby(mcats, exitcat)
    if r is None:
        continue
    tested += 1
    clean += 1 if r else 0
    if tested <= 6 or r:
        print(f"  dx1={dx1:4d}  Sb bbox {bbox(exitcat)}  leg-A: "
              f"{'CLEAN' if r else 'OBSTRUCTED'}", flush=True)

print(f"\nDECISIVE  shifter placements tested: {tested}; "
      f"leg-A flew past Sb cleanly in {clean}.", flush=True)
print(f"[{round(time.time()-t0,1)}s]  "
      + ("=> single-lane physical OR is viable; build the XOR merge on it."
         if clean else
         "=> WALL: a reflector that emits onto a lane also OBSTRUCTS that lane, so two "
         "single gliders can't be merged onto one wire by reflectors. Fan-in (OR) needs "
         "a dedicated gadget — the next hard rung, exactly as real Life computers use."),
      flush=True)
