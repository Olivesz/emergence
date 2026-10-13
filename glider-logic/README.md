# Logic gates from gliders — one level below Wireworld

The [Wireworld CPU](../cpu/) is built from gates. But Wireworld *cheats a little*:
its rules already hand you a **wire** and a **directional electron**. This folder
goes one level deeper — to **Conway's Game of Life**, whose entire law has no
notion of a wire, a signal, or a clock at all:

> A cell is alive next tick iff it has exactly **3** live neighbours,
> or it is alive now and has exactly **2**.

That's the whole universe. And yet:

- a small arrangement of 5 cells — a **glider** — crawls diagonally forever. *That's our signal.*
- a **Gosper glider gun** spits out one glider every 30 ticks. *That's a signal source / clock.*
- an **eater** (a 7-cell still life) swallows a glider whole. *That's a signal sink.*
- where two gliders **collide**, the rule decides what survives — and that is a **logic gate**.

Nothing here is designed-in. Every reaction is *found by brute-force simulation*
and then its truth table is *checked by running the raw automaton* — no trust.

## What's verified (`python3 gates.py` → ALL PASS)

| Built from | Reaction | Gate |
|---|---|---|
| two gliders meeting head-on | **annihilate** (plane left empty) | **INHIBIT** `A AND NOT B`, and **NOT** = `INHIBIT(1, B)` |
| an SE + an SW glider | **merge into one** glider (only when *both* present) | **AND** |
| two INHIBIT gates, mutually-exclusive readout | survive on either lane | **XOR** — the *sum* bit |
| NOT ∘ AND | | **NAND** — the *universal* gate |

And then **arithmetic**: XOR (sum) beside AND (carry) is a **half-adder**; two
half-adders make a **full-adder**; rippling those across bit positions adds whole
numbers. Every bit-column is checked by running the raw automaton:

```
3 + 2  (0b011 + 0b010), each column added by colliding gliders:
  bit0: 1+0+cin0 -> sum 1, carry 0
  bit1: 1+1+cin0 -> sum 0, carry 1
  bit2: 0+0+cin1 -> sum 1, carry 0        => 0b101 = 5
```

In this reaction-level adder, inputs are fanned out by placement and each
column's carry is handed to the next column by the Python harness; every
column's gates run in the raw rule.

NAND is universal, so these gates are a complete basis for logic: gates made of
gliders, made of nothing but *"3 to be born, 2 to survive."*

## Routing the signal — a physically-routed gate

Colliding gliders in place is one thing; a *circuit* needs to **turn** and **fan
out** signals. Both gadgets are real, canonical Life still-lifes, verified
cell-by-cell in our engine (`python3 gadgets.py` → ALL PASS):

- the **Snark** — a 52-cell reflector that turns a glider **90°** and restores itself,
- the **duplicator** — an 84-cell still life that **splits one glider into two**.

With those plus the gate reactions, `routed.py` assembles and verifies **actually
routed** logic in raw B3/S23 — no placement shortcuts:

| Rung | What it is |
|---|---|
| 1 | **fan-out with routing** — duplicator → two Snarks → two copies on chosen parallel lanes |
| 2 | a routed **INHIBIT** (`A AND NOT B`) fed through a Snark, full truth table |
| 3 | a **fully-routed AND gate** — B turned through *two* Snarks onto the merge, A entering directly, output escaping on a virgin lane — 4-row table **tick-exact** |
| 4 | a **fully-routed XOR** (= the half-adder SUM) — leg-2 decoupled onto its own right-side duplicator so the deleter is born beside `b_data`, tuned to the exact clean annihilation offset, with its own guard eater; 4 rows exact (`ha_xor.py`) |
| 5 | a complete **half-adder** — routed XOR (sum) + routed AND (carry) in one field, shared inputs; SUM=A^B, CARRY=A&B, exact (`ha_full.py`) |
| 6 | the routed half-adder **run per bit**: two runs make a full adder (8/8 rows) and one run per bit adds 6+5=11, 511+1=512 and 682+341=1023. Each half-adder runs in the raw rule; the harness passes the sum and carries between runs and ORs the two carries in Python (`ha_adder.py`) |

Every row passes only if the non-glider residue equals the catalyst still-lifes
*exactly*, the surviving gliders match by (direction, lane), and they stay stable
forever as they fly past every catalyst — plus a **causality** back-cast test
(hand-placed reactions can be unphysical; routed ones can't be).

```
life.py         Life engine (sparse) + glider, Gosper gun, eater — all verified
gates.py        four-direction gliders, annihilation & merge reactions, and the
                NOT / INHIBIT / AND / XOR / NAND gates + half/full-adder + 3+2
gadgets.py      the Snark reflector and the glider duplicator, verified in-engine
routed.py       physically-routed fan-out, INHIBIT, and a full AND gate
crossover.py    a verified glider crossover (timed weave) — carry over data
gun_routing.py  a real period-60 gun driving the Snark — a live routed stream
ha_xor.py, ha_full.py, ha_adder.py   routed XOR, routed half-adder, per-bit sums
latch.py        a 1-bit memory: one glider circulating a 4-Snark loop
compiler/       a single-glider router, gate-to-gate composition, a routed NOR
carlini_adder.py  fetch + parse + hashlife-verify Carlini's REAL 6+5=11 adder
notebook/       exploration scripts behind the walls in docs/glider-findings.md
```

What is built, and the walls that stopped the rest, measured:
[docs/glider-findings.md](../docs/glider-findings.md).

## The real thing, verified: a complete multi-bit glider adder

We didn't just build the parts — we checked that the whole machine exists and
runs. `carlini_adder.py` fetches Nicholas Carlini's
[ripple-carry glider adder](https://nicholas.carlini.com/writing/2020/digital-logic-game-of-life.html)
(a `.mc` macrocell file), parses its quadtree from scratch (**137,712 live cells**,
a 36,715 × 41,556 board), and — because the naive engine would take *days* — runs
it on a compact **pure-Python hashlife that is cross-validated cell-for-cell against
`life.step`**, for **2²⁰ generations**, then decodes the output glider streams:

```
operand A = 0110 = 6      operand B = 0101 = 5      sum = 1011 = 11
[PASS] THE ADDER COMPUTES: 6 + 5 = 11 — entirely in gliders
```

So the ladder is real end to end: **our** gates, arithmetic, routing hardware, and
a physically-routed AND gate + crossover + gun-driven signal — and, as the
existence proof at scale, a full multi-bit adder computing 6+5=11, verified in our
own engine. A live gun feeding the Snark and the routed AND run in the
[whole-circuit viewer](life-viewer.html); the 137k-cell adder is best watched in Golly.

Interactive visualizers: **[`glider-logic.html`](glider-logic.html)** — NOT / AND /
XOR and the **"Add a bit"** half-adder (flip both inputs to 1 and watch the sum
lanes go dark as the carry lights: `1+1 = 10`); and **[`life-viewer.html`](life-viewer.html)** —
the whole-circuit viewer, defaulting to the **routed AND gate** running in full.

## Why Wireworld for the CPU, then?

Both are Turing-complete, so either *could* host a computer. Wireworld makes it
**tractable** — wires and gates fall out of its rules, so you can hand-build a
whole processor. A full CPU in Life is a legendary, years-long undertaking (the
gates here are the first rung of that ladder). Same idea, two depths: Wireworld to
*build* the computer, Life to *show how little the universe needs to know*.
