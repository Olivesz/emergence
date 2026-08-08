# Master plan — all the way to a rudimentary glider CPU (raw B3/S23)

One field, real gliders, every rung verified by running the automaton. No forks, no
stopping to ask — grind each rung until it verifies or is proven impossible; on a dead
end, backtrack and try another direction. This is the complete path; we need all of it
for the CPU anyway.

Legend: [x] done+verified · [~] in progress · [ ] todo

## Tier 0 — substrate & primitives  (DONE)
- [x] sparse Life engine, glider/gun/eater (`life.py`)
- [x] reactions: INHIBIT (annihilate), AND (merge) — brute-found, truth-checked (`gates.py`)
- [x] Snark reflector (8 orientations), duplicator fan-out (`gadgets.py`)
- [x] single-glider router (`compiler/router.py`), gate→gate composition (`compose.py`)
- [x] physical fan-out (chained dups), lane-shift (`physical_fanout.py`, `lane_shift.py`)
- [x] routed INHIBIT + routed AND, 4-row tables (`routed.py` RUNG 2–3)
- [x] **routed NOR** — universal physical fan-in, De Morgan carriers (`routed_or.py`)
- [x] wall #1 parity, wall #2 reflector-merge — both characterized + routed around

## Tier 1 — a complete combinational gate set  (single-output, composable)
- [~] **OR** = NOT(NOR): route NOR's output m to a FAR lane (out of the machine band),
      place the output-NOT there so the surviving carrier misses the machine. Verify 4 rows.
- [ ] **NOT** (standalone) = INHIBIT with a constant carrier — extract from the OR build.
- [ ] **NAND** = NOT(AND) — same output-NOT trick on the routed AND.
- [ ] **XOR** (single-output) = AND(OR(a,b), NAND(a,b)) — compose three gates + fan-out a,b.
      This is the sum bit and the first true multi-gate composed circuit with real fan-in.
- Backtrack option if the output-NOT floor-plan is too tight: build gates on a common GRID
  with fixed cell pitch so every gate's I/O port lands on a free lane by construction.

## Tier 2 — arithmetic
- [ ] **half-adder** (single field): SUM = XOR, CARRY = AND, shared fanned inputs.
- [ ] **full adder** = 2 half-adders + carry-OR (all in-fragment, `fragment.py` proved the logic).
- [ ] **crossover** for carry-crosses-data (`crossover.py` timed weave — already verified) wired in.
- [ ] **N-bit ripple adder**: chain full adders, route carry bit i → bit i+1. Watch 5+6.

## Tier 3 — compiler automation (so Tier 2+ is generated, not hand-placed)
- [ ] **netlist** IR: gates + nets (a full adder as data).
- [ ] **place**: assign gates to grid cells with clearance.
- [ ] **route**: maze-route each net with Snark turns / lane-shifts, obstacle-avoiding.
- [ ] **time**: pad wire lengths so every gate's inputs arrive on the same tick (timing closure).
- [ ] emit + verify the compiled adder truth table in the raw rule.

## Tier 4 — sequential (state)
- [x] 1-bit memory: glider circulating a 4-Snark loop forever (`latch_dev.py`)
- [ ] **non-destructive read** hardened (tap via duplicator, byte-stationary).
- [ ] **write / clear**: inject or annihilate the loop glider on a control signal (SR latch).
- [ ] **clock**: a gun-driven periodic enable (guns already verified, `gun_routing.py`).
- [ ] **register** = N SR-latches loaded together on a clock edge.

## Tier 5 — datapath → rudimentary CPU
- [ ] a 1-address datapath: PC (register) → instruction latch → decode (gate net) →
      ALU (the ripple adder + logic gates) → accumulator (register) → back to memory.
- [ ] control: a few instructions (LDA, ADD, STA, JMP) decoded by a gate net + clock.
- [ ] the honest wall: GLOBAL timing-closure + feedback loops at scale is the genuine
      person-years mountain (Tier 5 may only reach a single self-clocked datapath slice).
      We climb until a rung is proven infeasible in this substrate, then document it as the
      real terminus — "as far as the physics + effort let us," not a guess.

## Rules of the grind
- Every claim verified in the bare rule (catalysts restored, exact survivors, escape).
- Bounded sims only; main-thread; `python3 -u` + laps; background+poll anything long.
- On a dead end: record why, backtrack, try another construction. Commit+push each rung.
