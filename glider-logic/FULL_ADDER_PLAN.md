# Routed full adder → multi-bit — assembly plan

Design spec for the next rung, ready to build the moment the routed **half-adder**
(`routed.py` Rung 5) lands. A full adder from two half-adders, then a ripple chain.

## Full adder = two half-adders + a carry merge

```
FA(A, B, Cin) -> (sum, cout):
    (s1, c1) = HA(A,  B)      # half-adder 1
    (sum, c2) = HA(s1, Cin)   # half-adder 2
    cout      = c1 OR c2
```

## Physical routing (real gliders)

- **HA1** consumes A, B (our half-adder already fans each input 3× internally).
  Outputs: `s1` on HA1's sum lane(s); `c1` on HA1's carry (AND) output lane.
- **s1 → HA2**: `s1` must be **rerouted with Snarks** onto HA2's A-input lane at the
  phase/tick HA2 expects — same reroute technique as leg-2 in the half-adder.
  `Cin` enters directly on HA2's B-input lane.
- **HA2** outputs: `sum` on its sum lane(s); `c2` on its carry lane.
- **cout = c1 OR c2 needs NO physical OR gadget.** c1 and c2 are provably
  **mutually exclusive**: if HA1 carries (c1=1) then s1=0, so s1+Cin ≤ 1 and c2=0;
  if c1=0 then c2 = s1·Cin. So at most one of c1,c2 is ever 1 → read *"a glider on
  either carry lane"* (2-region readout, honest), or route both onto one shared
  output lane where — being mutually exclusive — they never collide.
- **Crossovers**: in a 2D layout the carry lines (c1, c2, cout) cross the data path
  (s1 → HA2 and the operand feeds). Each crossing uses the **verified timed-weave
  crossover** (`crossover.py`) — with its scheduled clearance window respected.

## Verification (same rigorous standard)

8-row truth table `(A,B,Cin) -> (sum, cout)` by raw B3/S23, using the *final-only*
`settle()` (exact catalyst restoration + survivor dir/lane match + forever-escape).
During iteration use **bounded** sims (fixed tick count), never open-ended loops —
see [[agent-slow-verify-credit-bomb]].

## Multi-bit (toward 11-bit)

Chain N full adders; `cout[i] → cin[i+1]` is a physical carry glider rerouted into
the next stage (a crossover per bit position where it crosses data lines). Operand
bits enter from input assemblies (a gun assembly per active bit, silenced per 0
bit) — exactly Carlini's layout. This is the Carlini-scale build; our verified kit
(reflector, duplicator, gates, routed AND, crossover, gun-driven source) is
precisely the standard cell library it composes from.

## Status of the standard-cell library (all verified in raw Life)

| Cell | State |
|---|---|
| glider / gun / eater | ✅ |
| Snark reflector (turn 90°) | ✅ |
| duplicator (fan-out) | ✅ |
| INHIBIT / AND / XOR gates | ✅ |
| routed AND gate | ✅ |
| crossover (timed weave) | ✅ |
| gun-driven routed source | ✅ |
| **routed half-adder** | ⏳ in progress (Rung 5) |
| routed full adder | ▢ next (this plan) |
