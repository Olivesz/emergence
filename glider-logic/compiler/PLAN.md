# Glider Logic Compiler — netlist → a real B3/S23 circuit of gliders

**Goal:** compile a logic netlist (full adder → ripple adder → `5+6`) into ONE raw
Conway's-Life field that computes it with actual gliders. Our own gates, our own
compiler, our own output — the honest, feasible path to multi-bit (hand-building
hit a lane-parity wall at the first HA→HA chain).

**Why a compiler works where hands don't:** it imposes a regular grid and only ever
connects grid-aligned ports, so the parity/timing conflicts that kill ad-hoc
placement can't arise. Same reason Carlini (and every Life-computer builder) wrote one.

**Simplifying target — one-shot combinational circuits:** inject inputs once, run,
read outputs. Every wire carries ≤1 glider, so Snark 55-tick recovery is irrelevant.
Routing = single-glider geometry + timing only.

## Substrate (all physics already verified in ../)
- signal = one glider (present = 1). travels a diagonal lane at c/4.
- wire = a Snark-routed glider path. turn = one Snark (90°). 8 orientations verified.
- fan-out = duplicator (1→2). cross = timed-weave crossover. delay = longer wire.
- gate = a glider-collision reaction: AND (merge), NOT/INHIBIT (annihilate), => NAND.

## Pipeline / stages (build + verify one at a time)
1. **router** — place Snarks to route a single glider along an arbitrary path; clean,
   catalysts restored, tracked (dir/lane/phase/time) at every waypoint. ← FOUNDATION
2. **tiles** — WIRE / TURN / FANOUT / CROSS / DELAY / GATE as grid-aligned cells with
   typed I/O ports (lane, phase, arrival-time), so tiles compose by construction.
3. **netlist** — gates + nets (a full adder, then a ripple adder).
4. **place** — assign gates to grid cells.
5. **route** — connect nets with tiles (maze route on the grid).
6. **time** — pad wire length so each gate's inputs arrive simultaneously (timing closure).
7. **emit** — stamp all tiles → one Life field; run it; verify the truth table in the raw rule.
8. **scale** — compile the ripple adder; watch `5+6` compute in real gliders.

## Honesty
Every stage is verified in the bare rule (catalysts restored, exact survivors). We
report the wall the moment we hit one. "See how far we can get."
