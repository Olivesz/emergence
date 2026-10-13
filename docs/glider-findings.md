# Glider logic: what is built, and what stopped it

Everything here runs in raw Conway's Life (B3/S23) in this repository's own
engine (`glider-logic/life.py`). A result counts only when the script that
checks it restores every catalyst exactly and finds exactly the expected
surviving gliders.

## Built and verified

| Result | Script | In `verify.py` |
|---|---|---|
| glider, Gosper gun, eater | `life.py` | fast |
| INHIBIT (annihilation) and AND (merge) reactions; NOT, XOR, NAND; a reaction-level adder with the carry passed between columns in Python | `gates.py` | fast |
| Snark reflector (8 orientations) and glider duplicator | `gadgets.py` | fast |
| a timed crossing: two lanes cross when scheduled apart | `crossover.py` | fast |
| routed fan-out, routed INHIBIT, routed AND | `routed.py` | nightly |
| routed XOR, then a routed half-adder in one field | `ha_xor.py`, `ha_full.py` | nightly |
| full adder and 10-bit sums from the routed half-adder run once per use, with sums and carries passed between runs in Python | `ha_adder.py` | nightly |
| single-glider router; one gate's output routed into another's input (a routed 3-input AND) | `compiler/router.py`, `compiler/compose.py` | fast |
| fan-in rebuilt from verified reactions: NOR = AND(NOT a, NOT b) with constant carriers, checked at logic level, then built as a routed NOR | `compiler/fragment.py`, `compiler/routed_or.py` | fast |
| 1-to-3 and 1-to-4 fan-out by chained duplicators; a 2-Snark lane shifter | `physical_fanout.py`, `lane_shift.py` | nightly, fast |
| a gun's stream turned by a Snark | `gun_routing.py` | fast |
| 1-bit memory: one glider circulating a 4-Snark loop, exactly periodic; a duplicator tap reads it without destroying it (the read loop drifts a few cells per lap) | `latch.py` | nightly |
| Nicholas Carlini's 137,712-cell ripple-carry adder computes 6+5=11 in this engine's hashlife (pattern pinned by sha256) | `carlini_adder.py` | nightly |

## Walls, measured

**Lane parity.** A gate's two output rails come out on lanes of opposite
parity, and Snark reflectors preserve parity, so no pair of Snarks moves one
rail onto the other's lane. `notebook/explore_merge_route.py` tries every
2-Snark route from lane 8 to lane -23: 0 parity-valid, 0 placed, 0 clean.

**Merging by reflector.** To put two mutually exclusive gliders on one lane,
the upstream glider has to fly past the reflector that emits the downstream
one, and it is destroyed. `notebook/merge_wall.py` tries 340 placements of the
shifter: in 0 does the glider pass cleanly. Fan-in therefore cannot be a
reflector merge; the routed NOR above builds it from reactions instead.

**OR as NOT(NOR).** `notebook/routed_nor_compose.py` lets the NOR's output
escape forward and fuse with a constant carrier. The three rows where OR is 1
work. The (0,0) row does not: the NOR output must cancel the carrier before the
merge, and the turn that routes it out sits on the collision. Making room
pushes each verification run past 300 s; the script stops with an assertion.

**Scale.** Every multi-gate circuit above was placed by hand. A compiled
multi-bit adder needs an automated placer and router with timing closure;
that is not built, so multi-bit sums still pass carries in Python.

## Dead ends kept for the record

`glider-logic/notebook/` holds the exploration scripts behind the walls above
and the experiments that led to `ha_xor.py` (`ha_dev.py`, `decoupled_ha.py`,
`fa_dev.py`). They are not checks and are not run by `verify.py`.
