#!/usr/bin/env python3
"""Record SAP-1 running Fibonacci, clock by clock, from the gate-level netlist.

    python3 record_trace.py           rewrite traces/sap1_fib.json
    python3 record_trace.py --check   exit 1 unless the committed file is
                                      reproduced byte for byte

Each row is one clock: the ring-counter step T, PC, MAR, IR, A, B, OUT, the
carry flag, the bus, the control lines that are on, and whether OUT was loaded.
The header names the program image and the netlist's size, so the trace says
which machine produced it.
"""
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from asm import assemble
import run_cpu
from sap1 import SAP1

OUT = os.path.join(HERE, "traces", "sap1_fib.json")
SIGS = ["Ep", "Cp", "Lm", "CE", "Li", "Ei", "La", "Lb", "Eu", "Su", "Ea", "Wr", "Lo", "Jl"]


def record():
    img, _ = assemble(run_cpu.P5)
    cpu = SAP1(img)
    c = cpu.c
    rows, outs = [], []
    for _ in range(3000):
        s = cpu.snapshot()
        lo = c.get(cpu.sig["Lo"])
        rows.append([s["T"], s["PC"], s["MAR"], s["IR"], s["A"], s["B"], s["OUT"], s["C"],
                     s["bus"], [k for k in SIGS if c.get(cpu.sig[k])], int(bool(lo))])
        if s["halt"]:
            break
        c.tick()
        if lo:
            outs.append(c.getbus(cpu.O))
    head = dict(machine="SAP-1", program="fibonacci", source="cpu/run_cpu.py P5",
                image=img, image_sha256=hashlib.sha256(bytes(img)).hexdigest(),
                netlist=dict(nand=len(c.nands), dff=len(c.dffs)),
                columns=["T", "PC", "MAR", "IR", "A", "B", "OUT", "C", "bus", "on", "out_load"],
                clocks=len(rows), out_tape=outs)
    text = json.dumps(dict(header=head, rows=rows), separators=(",", ":")) + "\n"
    return text, outs


def main(argv):
    text, outs = record()
    want = [1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144]
    ok = outs == want
    print(f"  [{'PASS' if ok else 'FAIL'}] netlist run prints {outs}")
    if "--check" in argv:
        same = os.path.exists(OUT) and open(OUT).read() == text
        print(f"  [{'PASS' if same else 'FAIL'}] traces/sap1_fib.json reproduced byte for byte")
        ok &= same
    else:
        open(OUT, "w").write(text)
        print(f"wrote {os.path.relpath(OUT, HERE)} ({len(text)} bytes)")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
