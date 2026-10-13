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
ww_cells.py  a hand-built Wireworld NAND and loop register, verified in the raw CA rule
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

Interactive front panel: **[`cpu.html`](cpu.html)** — pick a program, hit Run, and
watch one register drive the bus (green) while another latches it (cyan).

---

# SAP-2 — a much more capable machine

`sap2.py` is a far bigger CPU on the same NAND+DFF substrate: **256 bytes of
memory, ~35 instructions, and a stack**. Where SAP-1 is hardwired and 16 words,
SAP-2 is **microcoded** — a resettable step counter drives a gate-level control
store (a PLA generated from a microcode table), so a rich instruction set fits.

- **8-bit addresses → 256 bytes**, multi-byte instructions
- **multi-function ALU**: add/sub/and/or/xor/not/shl/shr/inc/dec, with **Z/C/S flags**
- **indirect addressing** (B as a pointer, `LDX`/`STX`), immediate arithmetic, `CMP`
- **a stack** (`SP`) with **`CALL`/`RET`/`PUSH`/`POP`** → subroutines & recursion
- **I/O**: a live `IN` register and a **memory-mapped display** at `0xF0–0xFF`

The CPU logic stays gate-level NAND+DFF (4,575 gates); the 256-byte main store is a
memory array spliced in at the clock edge (SAP-1 already proved RAM is buildable
cell-for-cell — replicating it 256× just slows the sim).

Real algorithms, all self-checked in `run_sap2.py`:

- **multiply** 6×7 → 42, **divide** 47÷5 → 9 r 2, **gcd**(48,36) → 12
- **primes < 20** → 2,3,5,7,11,13,17,19 (nested loops + modulo)
- **bubble sort** of an in-memory array via indirect addressing

```bash
python3 run_sap2.py   # six real algorithms on the SAP-2
```

Interactive debugger panel: **[`cpu2.html`](cpu2.html)** — a code editor with an
assembler, single-step / breakpoints (click a memory cell), editable memory
(double-click), an input dial, and the memory-mapped screen.
`wwcpu2.js` is the JS port (verified identical to the Python); `cpu2.html` is
built from `cpu2_shell.html` with the engine injected.
