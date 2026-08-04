#!/usr/bin/env python3
"""Tiny assembler for the SAP-1+ machine. One instruction per line:
     MNEMONIC [operand]        operand is a 4-bit number or a label
   Labels:  name:   at start of a line.  Data:  DB value  (raw byte).
   Produces a 16-byte memory image (opcode<<4 | operand)."""
from sap1 import (NOP, LDA, ADD, SUB, STA, LDI, JMP, JZ, JC, OUT, HLT)

OPS = dict(NOP=NOP, LDA=LDA, ADD=ADD, SUB=SUB, STA=STA, LDI=LDI,
           JMP=JMP, JZ=JZ, JC=JC, OUT=OUT, HLT=HLT)
NO_OPERAND = {NOP, OUT, HLT}


def assemble(src):
    # pass 1: collect labels and a linear list of (op, operand_token)
    items = []          # (kind, ...)
    labels = {}
    addr = 0
    lines = []
    for raw in src.strip("\n").splitlines():
        line = raw.split(";")[0].strip()
        if not line:
            continue
        if line.endswith(":"):
            labels[line[:-1].strip()] = addr
            continue
        if ":" in line and line.split(":")[0].replace("_", "").isalnum() and " " not in line.split(":")[0]:
            lbl, rest = line.split(":", 1)
            labels[lbl.strip()] = addr
            line = rest.strip()
            if not line:
                continue
        lines.append((addr, line))
        addr += 1
    # pass 2: encode
    image = [0] * 16
    for addr, line in lines:
        parts = line.split()
        mn = parts[0].upper()
        if mn == "DB":
            image[addr] = int(parts[1], 0) & 0xFF
            continue
        if mn not in OPS:
            raise ValueError(f"unknown mnemonic {mn!r} at {addr}")
        op = OPS[mn]
        operand = 0
        if op not in NO_OPERAND:
            tok = parts[1]
            operand = labels[tok] if tok in labels else int(tok, 0)
        image[addr] = ((op & 0xF) << 4) | (operand & 0xF)
    return image, labels
