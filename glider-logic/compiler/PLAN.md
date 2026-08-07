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

## Where we are (verified) and the two walls we've characterized
**Proven in the bare rule:** the router (stage 1), the reactions (AND, INHIBIT/ANN),
fully-routed INHIBIT + AND gates (`../routed.py` RUNGs 2–3), **gate→gate composition**
(`compose.py`: route one gate's output into another's input — a routed 3-input AND),
plus fan-out (`../physical_fanout.py`), lane-shift (`../lane_shift.py`), and 1-bit
glider memory (`../latch_dev.py`). Emit works (`compiled_and.rle`).

**Wall #1 — parity (hand-building).** Reaction geometry fixes a gate's two output
rails to *opposite* lane parity; reflectors conserve parity, so hand-routing can't
align them. *Escaped by the compiler:* it places each gate freely, so it can put both
data inputs on same-parity lanes. (`../test_merge_route.py`.)

**Wall #2 — fan-in by reflector is impossible.** A reflector that emits onto a lane
also *obstructs* that lane: to merge two mutually-exclusive gliders onto one wire, the
upstream leg's glider must fly past the downstream leg's exit-Snark — and it is
destroyed every time (`compiler/merge.py`: **340/340** placements obstructed).
Direction doesn't help; whichever reflector is upstream gets traversed. Merging onto a
*virgin* lane works only for AND (needs BOTH inputs); OR needs EITHER alone, so there's
no partner glider to react with. A reflector merge is therefore impossible.

**The route around wall #2 — De Morgan + a constant carrier (`compiler/fragment.py`).**
Fan-in doesn't need a bespoke OR-gadget. `OR(a,b) = NOT(AND(NOT a, NOT b))`, where
`NOT x = INHIBIT(1, x)` uses a constant '1' carrier (an injected glider — free in a
one-shot circuit). The inner `AND(¬a,¬b)` is the **both-present** merge onto a virgin
lane (RUNG 3) — never a merge of two mutually-exclusive signals — so wall #2 never
bites. `fragment.py` builds NOT/OR/XOR/half-add/full-add/ripple-add from ONLY the two
proven reactions (each evaluated through gates.py's raw-Life functions) and passes
every truth table (incl. 170+85=255, 511+1=512). **So the full adder is in the
achievable fragment**: every primitive it needs (INHIBIT, AND-merge, fan-out, constant
carrier) is already verified as real routed gliders, and `compose.py` proved a chaining
step. What remains between here and a compiled adder is **routing + timing-closure at
scale (stages 4–6), not a new wall.**

**First physical fan-in built — a routed NOR (`compiler/routed_or.py`).** The route-around
is now realized in actual gliders: RUNG 3's two AND inputs become CONSTANT carriers, and
the real inputs `a,b` are DELETERS that annihilate them (carrier survives iff input=0), so
the AND computes `AND(NOT a, NOT b)` = **NOR** — all 4 rows verified in the bare rule
(catalysts restored, exact survivors). NOR is functionally complete, so this one verified
gate is a **universal** physical fan-in. Emitted `compiled_nor.rle`, shipped as the
life-viewer default. `OR = NOT(NOR)` is one more routed INHIBIT, but its output carrier is
pinned (by annihilation geometry) onto an SE lane inside the machine's A-entry corridor, so
it disrupts the merge — OR needs `m` routed to open space first (**floor-planning**, stage
4–5). That's the concrete next build; the logic and every reaction are already proven.

## Honesty
Every stage is verified in the bare rule (catalysts restored, exact survivors). We
report the wall the moment we hit one. "See how far we can get."
