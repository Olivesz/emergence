# A CPU built from Wireworld

A complete, working **SAP-1+** processor (the canonical "Simple-As-Possible"
teaching CPU, lightly extended with memory-store and branches) expressed as a
single flat netlist of just **two primitives** — a NAND gate and a D flip-flop —
each of which is a verified [Wireworld](../README.md) gadget.

This is the payoff of Act VIII: the same 4-state cellular automaton that gave us
a clock, a wire, and logic gates is *universal*, and here it runs actual programs.

## Why two primitives is the whole trick

Hand-composing asynchronous Wireworld gates hits a wall: a long lead on one gate
input corrupts the other, and inter-gate wires are bidirectional, so signals flow
backward and oscillate. Real silicon beats the identical hazard the same way we
do here — a **synchronous discipline**: every signal is latched in a D flip-flop
once per clock, and combinational NAND clouds settle in between. So a netlist of
`{NAND, DFF}` on one clock computes exactly what the physical Wireworld circuit
computes, cycle for cycle. NAND is functionally complete; the flip-flop supplies
memory. That's a universal computer.

```
wwlogic.py   the simulator: NAND + DFF primitives, AND/OR/XOR/MUX derived from NAND
modules.py   datapath cells: register, full-adder, adder/subtractor, PC, decoder, RAM
sap1.py      the CPU: bus, PC, MAR, RAM, IR, A/B, ALU, OUT, ring-counter control
asm.py       a tiny assembler (labels, DB data)
run_cpu.py   five real programs, self-checking
ww_cells.py  the physical Wireworld NAND & flip-flop, verified in the raw CA rule
```

The assembled machine is **1446 NAND gates + 175 flip-flops** — every one of them
one of the two verified cells.

## The instruction set

8-bit data, 4-bit addresses, 16 words of shared (von-Neumann) memory.

| Op | Mnemonic | Effect | | Op | Mnemonic | Effect |
|----|----------|--------|-|----|----------|--------|
| 0x0 | `NOP` | — | | 0x5 | `LDI i` | A = i (immediate) |
| 0x1 | `LDA a` | A = M[a] | | 0x6 | `JMP a` | PC = a |
| 0x2 | `ADD a` | A = A + M[a] | | 0x7 | `JZ a` | if A==0, PC = a |
| 0x3 | `SUB a` | A = A − M[a] | | 0x8 | `JC a` | if carry, PC = a |
| 0x4 | `STA a` | M[a] = A | | 0xE / 0xF | `OUT` / `HLT` | display A / halt |

Each instruction runs in up to 6 clocked micro-steps (T1–T3 fetch, T4–T6
execute), sequenced by a one-hot ring counter and a hardwired control matrix.

## Programs it runs (all self-checked in `run_cpu.py`)

- **5 + 3 → 8** and **9 − 4 → 5** — arithmetic on memory operands
- **countdown 3,2,1,0** — a loop with a data-dependent `JZ` branch
- **sum 4+3+2+1 → 10** — accumulate in memory across a counted loop
- **Fibonacci → 1,1,2,3,5,8,13,21,34,55,89,144** — loops until 8-bit overflow
  trips the carry flag and `JC` halts it

```bash
python3 wwlogic.py   # primitives + derived gates
python3 modules.py   # datapath modules
python3 run_cpu.py   # the CPU running real programs
```
