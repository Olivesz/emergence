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
| NOT ∘ AND | | **NAND** — the *universal* gate |

Because NAND is universal, the **same logic that runs the SAP-1 / SAP-2** could in
principle stand on these glider gates. It's computation all the way down: a CPU
made of gates, made of gliders, made of nothing but *"3 to be born, 2 to survive."*

```
life.py    the Life engine (sparse) + glider, Gosper gun, eater — all verified
gates.py   four-direction gliders, the annihilation & merge reactions, and the
           NOT / INHIBIT / AND / NAND gates, each truth-table-checked in raw Life
```

Interactive visualizer: **[`glider-logic.html`](glider-logic.html)** — watch a
glider crawl, a gun fire a stream, and gliders collide to compute NOT and AND,
with input toggles and a live output lamp.

## Why Wireworld for the CPU, then?

Both are Turing-complete, so either *could* host a computer. Wireworld makes it
**tractable** — wires and gates fall out of its rules, so you can hand-build a
whole processor. A full CPU in Life is a legendary, years-long undertaking (the
gates here are the first rung of that ladder). Same idea, two depths: Wireworld to
*build* the computer, Life to *show how little the universe needs to know*.
