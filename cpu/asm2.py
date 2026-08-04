#!/usr/bin/env python3
"""Two-pass assembler for SAP-2. Instructions are 1 byte (no operand) or 2 bytes
(opcode + operand). Supports labels, `DB value`, `ORG addr`, and `name = value`
equates. Operands may be numbers, labels, or equates."""
from sap2 import OPS, HAS_OPERAND

def assemble(src):
    # pass 1: measure sizes, collect labels/equates
    labels, equ = {}, {}
    items = []          # (addr, kind, ...)
    addr = 0
    for raw in src.replace("\r","").split("\n"):
        line = raw.split(";")[0].strip()
        if not line: continue
        # label:
        while ":" in line:
            head, rest = line.split(":", 1)
            head = head.strip()
            if " " in head or head.upper() in OPS:  # not a label
                break
            labels[head] = addr; line = rest.strip()
            if not line: break
        if not line: continue
        parts = line.split()
        mn = parts[0].upper()
        if mn == "ORG":
            addr = _num(parts[1], labels, equ); continue
        if len(parts) >= 3 and parts[1] == "=":     # equate:  NAME = value
            equ[parts[0]] = _num(parts[2], labels, equ); continue
        if mn == "DB":
            items.append((addr, "DB", parts[1:])); addr += len(parts[1:]); continue
        if mn not in OPS:
            raise ValueError(f"unknown mnemonic {mn!r}")
        size = 2 if mn in HAS_OPERAND else 1
        items.append((addr, mn, parts[1:])); addr += size
    # pass 2: emit
    image = [0]*256
    for addr, mn, args in items:
        if mn == "DB":
            for i, a in enumerate(args): image[addr+i] = _num(a, labels, equ) & 0xFF
            continue
        image[addr] = OPS[mn]
        if mn in HAS_OPERAND:
            image[addr+1] = _num(args[0], labels, equ) & 0xFF
    return image, labels

def _num(tok, labels, equ):
    if tok in labels: return labels[tok]
    if tok in equ:    return equ[tok]
    return int(tok, 0)
