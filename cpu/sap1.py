#!/usr/bin/env python3
"""
SAP-1+ : a complete, working CPU expressed as ONE flat netlist of the two
verified Wireworld cells (NAND + DFF). "SAP-1" (Simple-As-Possible) is the
canonical textbook minimal computer; this is a lightly-extended variant with
memory-store and branches so it can run real looping programs.

Architecture (8-bit data, 4-bit address, 16-word von-Neumann memory):
  W-bus (8)  — shared bus, driven by exactly one source per micro-step
  PC   (4)   — program counter (count / jump)
  MAR  (4)   — memory address register
  RAM  16x8  — gate-level (DFF rows + address decode + read mux)
  IR   (8)   — instruction register (high nibble opcode, low nibble operand)
  A    (8)   — accumulator            B (8) — ALU operand latch
  ALU  (8)   — add / subtract (two's-complement), carry flag
  OUT  (8)   — output register
  Control    — 6-state ring counter + a hardwired control matrix

Instruction set (opcode = high nibble of the byte, operand = low nibble):
  0x0 NOP            0x4 STA a  M[a]=A       0x8 JC  a  if carry PC=a
  0x1 LDA a  A=M[a]  0x5 LDI i  A=i (imm)    0xE OUT    OUT=A
  0x2 ADD a  A+=M[a] 0x6 JMP a  PC=a         0xF HLT    halt
  0x3 SUB a  A-=M[a] 0x7 JZ  a  if zero PC=a

Micro-program (T1-T3 fetch is common to every instruction):
  T1: PC->MAR    T2: PC++    T3: M[MAR]->IR    then T4-T6 per opcode (below).
"""
from wwlogic import Circuit
from modules import full_adder, add_sub, decoder, mux_onehot

# opcode numbers
NOP, LDA, ADD, SUB, STA, LDI, JMP, JZ, JC = 0, 1, 2, 3, 4, 5, 6, 7, 8
OUT, HLT = 0xE, 0xF
MNEM = {NOP:"NOP",LDA:"LDA",ADD:"ADD",SUB:"SUB",STA:"STA",LDI:"LDI",
        JMP:"JMP",JZ:"JZ",JC:"JC",OUT:"OUT",HLT:"HLT"}


class SAP1:
    def __init__(self, program=None):
        c = self.c = Circuit()
        W = 8            # data width
        AW = 4           # address width
        self.W, self.AW = W, AW
        prog = list(program or [])
        prog += [0] * (16 - len(prog))
        self.prog = prog

        # ---- allocate all state (flops) up front with placeholder inputs ----
        raw = lambda init=0: c.dff(c.GND, en=c.GND, init=init)  # rebind later
        self.PC  = [raw() for _ in range(AW)]
        self.MAR = [raw() for _ in range(AW)]
        self.IR  = [raw() for _ in range(W)]
        self.A   = [raw() for _ in range(W)]
        self.B   = [raw() for _ in range(W)]
        self.O   = [raw() for _ in range(W)]
        self.carry = raw()
        # RAM rows, preloaded with the program image
        self.RAM = [[raw((prog[w] >> b) & 1) for b in range(W)] for w in range(16)]
        # control ring counter T1..T6, one-hot, starts at T1
        self.T = [raw(1 if i == 0 else 0) for i in range(6)]

        # ---- combinational: opcode decode, flags, ring outputs -------------
        t1, t2, t3, t4, t5, t6 = self.T
        op = decoder(c, self.IR[4:8])           # 16 one-hot opcode lines

        Z = c.not_(c.or_list(self.A))           # accumulator == 0
        Cf = self.carry                          # carry flag (flop Q)

        def anyof(*ops):  return c.or_list([op[o] for o in ops])
        usesAddr = anyof(LDA, ADD, SUB, STA)
        addsub   = anyof(ADD, SUB)
        # branch-taken lines
        jz_taken = c.and_(op[JZ], Z)
        jc_taken = c.and_(op[JC], Cf)

        A_ = c.and_; O_ = c.or_list
        # ---- control matrix : signal = OR of product terms -----------------
        Ep  = t1
        Cp  = t2
        Li  = t3
        Lm  = O_([t1, A_(t4, usesAddr)])
        CE  = O_([t3, A_(t5, addsub), A_(t5, op[LDA])])
        Ei  = O_([A_(t4, usesAddr), A_(t4, op[LDI]),
                  A_(t4, op[JMP]), A_(t4, jz_taken), A_(t4, jc_taken)])
        La  = O_([A_(t5, op[LDA]), A_(t6, addsub), A_(t4, op[LDI])])
        Lb  = A_(t5, addsub)
        Eu  = A_(t6, addsub)
        Su  = A_(t6, op[SUB])
        Ea  = O_([A_(t5, op[STA]), A_(t4, op[OUT])])
        Wr  = A_(t5, op[STA])
        Lo  = A_(t4, op[OUT])
        Jl  = O_([A_(t4, op[JMP]), A_(t4, jz_taken), A_(t4, jc_taken)])
        Hlt = A_(t4, op[HLT])
        self.Hlt = Hlt
        self.sig = dict(Ep=Ep,Cp=Cp,Lm=Lm,CE=CE,Li=Li,Ei=Ei,La=La,Lb=Lb,
                        Eu=Eu,Su=Su,Ea=Ea,Wr=Wr,Lo=Lo,Jl=Jl,Hlt=Hlt)

        # ---- datapath combinational ---------------------------------------
        sel = decoder(c, self.MAR)                       # RAM word select
        ram_rd = mux_onehot(c, sel, self.RAM)            # async read
        alu, alu_c = add_sub(c, self.A, self.B, Su)      # ALU
        pc_ext = self.PC + [c.GND] * (W - AW)            # zero-extend PC
        iraddr = self.IR[0:AW] + [c.GND] * (W - AW)      # IR operand -> bus
        # the shared W-bus: exactly one enable is high per micro-step
        bus = mux_onehot(c, [Ep, CE, Ei, Ea, Eu],
                            [pc_ext, ram_rd, iraddr, self.A, alu])
        self.bus = bus
        inc, _ = add_sub(c, self.PC, [c.VCC] + [c.GND]*(AW-1), c.GND)  # PC+1

        # ---- rebind every flop's D and enable ------------------------------
        def wire(q, d, en):
            ff = c.dffs_by_q(q); ff['d'] = d; ff['en'] = en

        for k in range(AW):
            wire(self.MAR[k], bus[k], Lm)
            # PC: jump loads bus, else increment on Cp, else hold
            nxt = c.mux2(Jl, inc[k], bus[k])
            wire(self.PC[k], c.mux2(c.or_(Cp, Jl), self.PC[k], nxt), c.VCC)
        for k in range(W):
            wire(self.IR[k], bus[k], Li)
            wire(self.A[k],  bus[k], La)
            wire(self.B[k],  bus[k], Lb)
            wire(self.O[k],  bus[k], Lo)
        wire(self.carry, alu_c, Eu)
        # RAM write: only the addressed row, only when Wr
        for w in range(16):
            wen = c.and_(Wr, sel[w])
            for b in range(W):
                wire(self.RAM[w][b], bus[b], wen)
        # ring counter: rotate the one-hot token T1->T2->...->T6->T1
        for i in range(6):
            wire(self.T[i], self.T[(i - 1) % 6], c.VCC)

        c.settle()

    # ---- run control -----------------------------------------------------
    def tstate(self):
        return next(i + 1 for i, t in enumerate(self.T) if self.c.get(t))
    def opcode(self):
        return self.c.getbus(self.IR[4:8])
    def snapshot(self):
        g = self.c
        return dict(T=self.tstate(), PC=g.getbus(self.PC), MAR=g.getbus(self.MAR),
                    IR=g.getbus(self.IR), op=self.opcode(), A=g.getbus(self.A),
                    B=g.getbus(self.B), OUT=g.getbus(self.O),
                    C=g.get(self.carry), bus=g.getbus(self.bus),
                    halt=g.get(self.Hlt))

    def run(self, max_cycles=400, trace=False, on_out=None):
        c = self.c
        outs = []
        for cyc in range(max_cycles):
            snap = self.snapshot()
            if trace:
                sig_on = "".join(k for k in ["Ep","Cp","Lm","CE","Li","Ei","La",
                        "Lb","Eu","Su","Ea","Wr","Lo","Jl"] if c.get(self.sig[k]))
                print(f"  cyc{cyc:3d} T{snap['T']} PC={snap['PC']:2d} "
                      f"IR={snap['IR']:02x}({MNEM.get(snap['op'],'?'):3}) "
                      f"A={snap['A']:3d} B={snap['B']:3d} bus={snap['bus']:3d} "
                      f"C={snap['C']} OUT={snap['OUT']:3d} [{sig_on}]")
            if c.get(self.Hlt):
                return outs
            loading_out = c.get(self.sig['Lo'])   # an OUT is committing this edge
            self.c.tick()
            if loading_out:
                v = c.getbus(self.O)
                outs.append(v)
                if on_out: on_out(v)
        return outs
