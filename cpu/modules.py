#!/usr/bin/env python3
"""
SAP-1 datapath modules, built entirely from wwlogic primitives (NAND + DFF).
Every function takes a Circuit `c` and returns nets/buses, so the whole machine
is one flat netlist of the two verified Wireworld cells.

Convention: buses are little-endian lists of net ids (bit 0 = LSB).
"""
from wwlogic import Circuit


# ---- N-bit register with load-enable and synchronous clear ---------------
def reg(c, D, load, width=None, clr=None, init=0):
    """Q holds; on a clock with load=1, Q<-D; clr=1 zeroes it. Returns Q bus."""
    width = width or len(D)
    Q = []
    for k in range(width):
        d = D[k] if k < len(D) else c.GND
        Q.append(c.dff(d, en=load, clr=clr, init=(init >> k) & 1))
    return Q


# ---- full adder (from NAND) ----------------------------------------------
def full_adder(c, a, b, cin):
    s1 = c.xor_(a, b)
    s = c.xor_(s1, cin)
    cout = c.or_(c.and_(a, b), c.and_(s1, cin))
    return s, cout


# ---- N-bit adder / subtractor -------------------------------------------
def add_sub(c, A, B, sub):
    """If sub=1 compute A-B (two's complement: A + ~B + 1), else A+B.
       Returns (sum_bus, carry_out)."""
    n = max(len(A), len(B))
    carry = sub                          # +1 for subtract
    S = []
    for k in range(n):
        a = A[k] if k < len(A) else c.GND
        b = B[k] if k < len(B) else c.GND
        b = c.xor_(b, sub)               # invert B on subtract
        s, carry = full_adder(c, a, b, carry)
        S.append(s)
    return S, carry


# ---- N-bit program counter: register + increment + jump load -------------
def program_counter(c, count_en, jump_load, jump_addr, width, clr=None):
    """A PC that increments when count_en=1, or loads jump_addr when jump_load=1.
       Built as a register whose D is a mux between (Q+1) and jump_addr.
       Returns the PC output bus. (Two-phase: we allocate Q, then wire D.)"""
    # allocate Q flops with placeholder D, then rebind (needs Q to compute Q+1)
    Q = [c.dff(c.GND, en=c.VCC, clr=clr, init=0) for _ in range(width)]
    inc, _ = add_sub(c, Q, [c.VCC] + [c.GND] * (width - 1), c.GND)  # Q + 1
    load_or_count = c.or_(count_en, jump_load)
    for k in range(width):
        nxt = c.mux2(jump_load, inc[k], jump_addr[k])   # jump wins over increment
        # hold unless counting or jumping:
        c.dffs_by_q(Q[k])['d'] = c.mux2(load_or_count, Q[k], nxt)
    return Q


# ---- 2->4 and 4->16 one-hot address decoders (from NAND) -----------------
def decoder(c, sel_bits):
    """sel_bits little-endian -> list of 2^n one-hot lines."""
    n = len(sel_bits)
    inv = [c.not_(s) for s in sel_bits]
    lines = []
    for i in range(1 << n):
        terms = [sel_bits[k] if (i >> k) & 1 else inv[k] for k in range(n)]
        lines.append(c.and_list(terms))
    return lines


# ---- k-way one-hot mux over buses ---------------------------------------
def mux_onehot(c, selects, buses):
    """selects: one-hot lines; buses: list of same-width buses. Returns OR of
       (sel_i AND bus_i) per bit — a bus-read multiplexer."""
    width = len(buses[0])
    out = []
    for bit in range(width):
        terms = [c.and_(selects[i], buses[i][bit]) for i in range(len(buses))]
        out.append(c.or_list(terms))
    return out


# ---- RAM: 2^A words x W bits, gate-level (DFF cells + decode + mux) -------
def ram(c, addr, data_in, write, width, clr=None, init=None):
    """Synchronous-write, async-read RAM built from real DFF cells.
       addr: A-bit bus; write=1 stores data_in at addr on the clock.
       Returns the read data bus (combinational read of addressed word).
       init: optional list of word values to preload (program/data image)."""
    A = len(addr)
    nwords = 1 << A
    sel = decoder(c, addr)                       # one-hot word select
    rows = []
    for w in range(nwords):
        wr = c.and_(write, sel[w])               # write only the addressed row
        iv = (init[w] if (init and w < len(init)) else 0)
        row = reg(c, data_in, wr, width=width, clr=clr, init=iv)
        rows.append(row)
    read = mux_onehot(c, sel, rows)              # read addressed word
    return read, rows


# small helper on Circuit: find a dff record by its q net (for two-phase wiring)
def _dffs_by_q(self, q):
    for ff in self.dffs:
        if ff['q'] == q:
            return ff
    raise KeyError(q)
Circuit.dffs_by_q = _dffs_by_q


# ============================ self-tests ==============================
if __name__ == "__main__":
    ok = True
    def check(name, cond):
        global ok; ok = ok and cond
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")

    # register load/hold/clear
    c = Circuit()
    D = c.bus(4); load = c.net(); clr = c.net()
    Q = reg(c, D, load, width=4, clr=clr)
    c.setbus(D, 0b1010); c.set(load, 1); c.set(clr, 0); c.tick()
    check("reg loads 1010", c.getbus(Q) == 0b1010)
    c.setbus(D, 0b0101); c.set(load, 0); c.tick()
    check("reg holds when load=0", c.getbus(Q) == 0b1010)
    c.set(clr, 1); c.tick()
    check("reg clears", c.getbus(Q) == 0)

    # adder / subtractor (8-bit)
    c = Circuit()
    A = c.bus(8); B = c.bus(8); sub = c.net()
    S, cout = add_sub(c, A, B, sub)
    import random
    addok = True; subok = True
    for _ in range(200):
        x = random.randint(0, 255); y = random.randint(0, 255)
        c.setbus(A, x); c.setbus(B, y); c.set(sub, 0); c.settle()
        if c.getbus(S) != ((x + y) & 0xFF): addok = False
        c.set(sub, 1); c.settle()
        if c.getbus(S) != ((x - y) & 0xFF): subok = False
    check("8-bit ADD (200 random)", addok)
    check("8-bit SUB (200 random)", subok)

    # program counter: increments, wraps, and jumps
    c = Circuit()
    cen = c.net(); jl = c.net(); ja = c.bus(4); clr = c.net()
    PC = program_counter(c, cen, jl, ja, 4, clr=clr)
    c.set(clr, 1); c.tick(); c.set(clr, 0)
    seq = []
    c.set(cen, 1); c.set(jl, 0)
    for _ in range(6):
        seq.append(c.getbus(PC)); c.tick()
    check("PC counts 0..5", seq == [0, 1, 2, 3, 4, 5])
    c.set(cen, 0); c.set(jl, 1); c.setbus(ja, 12); c.tick()
    check("PC jumps to 12", c.getbus(PC) == 12)
    c.set(jl, 0); c.set(cen, 1); c.tick()
    check("PC counts after jump ->13", c.getbus(PC) == 13)

    # RAM: preload, read, write, read back
    c = Circuit()
    addr = c.bus(4); din = c.bus(8); wr = c.net()
    prog = [i * 3 & 0xFF for i in range(16)]
    rd, rows = ram(c, addr, din, wr, width=8, init=prog)
    readok = True
    for a in range(16):
        c.setbus(addr, a); c.set(wr, 0); c.settle()
        if c.getbus(rd) != prog[a]: readok = False
    check("RAM preload reads back", readok)
    c.setbus(addr, 5); c.setbus(din, 0xAB); c.set(wr, 1); c.tick()
    c.set(wr, 0); c.setbus(addr, 5); c.settle()
    check("RAM write@5 then read =0xAB", c.getbus(rd) == 0xAB)
    c.setbus(addr, 6); c.settle()
    check("RAM neighbour untouched", c.getbus(rd) == prog[6])

    print("\nALL PASS" if ok else "\nSOME FAILED")
