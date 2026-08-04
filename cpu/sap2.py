#!/usr/bin/env python3
"""
SAP-2 : a much more capable CPU, still one synchronous netlist of NAND + DFF for
all of its logic. Extends SAP-1 with:
  * 8-bit addresses -> 256 bytes of memory, multi-byte instructions
  * a microcoded control unit: a resettable step counter + a gate-level control
    store (a PLA generated from a microcode table), so ~35 instructions fit
  * a multi-function ALU (add/sub/and/or/xor/not/shl/shr/inc/dec) with Z/C/S flags
  * indirect addressing (via B as a pointer), immediate arithmetic, compare
  * a stack (SP) with CALL/RET/PUSH/POP  -> subroutines & recursion
  * I/O: an INPUT register you set live, plus a memory-mapped display region

Modeling note (honest): the CPU proper — registers, ALU, flags, the whole
control unit — is gate-level NAND+DFF exactly like SAP-1. The 256-byte *main
store* is kept as a memory array spliced in at the clock edge (read = combinational
from MAR, write = on the edge). SAP-1 already proved RAM can be built cell-for-cell
from DFF rows; replicating that 256x is mechanical and only slows the sim, so here
the interesting part stays gate-level and memory stays fast.
"""
from wwlogic import Circuit
from modules import (reg, alu, decoder, mux_onehot, add_sub, match_const, ALU_OPS)

# ---------------- instruction set -----------------
OPS = {
    "NOP":0x00, "HLT":0x01,
    "LDA":0x10, "STA":0x11, "LDI":0x12, "MAB":0x13, "MBA":0x14,
    "LDB":0x15, "LBI":0x16, "LDX":0x17, "STX":0x18,
    "ADD":0x20, "SUB":0x21, "ANA":0x22, "ORA":0x23, "XRA":0x24, "CMA":0x25,
    "INR":0x26, "DCR":0x27, "SHL":0x28, "SHR":0x29,
    "ADI":0x2A, "SUI":0x2B, "ANI":0x2C, "ORI":0x2D, "XRI":0x2E,
    "CMP":0x30, "CPI":0x31,
    "JMP":0x40, "JZ":0x41, "JNZ":0x42, "JC":0x43, "JNC":0x44,
    "CALL":0x50, "RET":0x51, "PUSH":0x52, "POP":0x53,
    "IN":0x60, "OUT":0x61,
}
MNEM = {v:k for k,v in OPS.items()}
HAS_OPERAND = {"LDA","STA","LDI","LDB","LBI","ADI","SUI","ANI","ORI","XRI",
               "CPI","JMP","JZ","JNZ","JC","JNC","CALL"}   # 2-byte instructions

# ---------------- microcode -----------------
# Each entry: the control tokens for T2, T3, ... (fetch T0/T1 are implicit & common).
# Tokens: plain signal names; ("alu",OP) sets the ALU function; ("PCi",cond)
# is a conditional PC-load (cond in Z/nZ/C/nC); "PCi" alone is unconditional.
FETCH_OPERAND = [["PCo","MARi"], ["RAMo","MDRi","PCc"]]     # MDR <- next byte, PC++
def M(*steps): return list(steps)

MICRO = {
  "NOP":  M(["NI"]),
  "HLT":  M(["HALT","NI"]),
  "LDA":  M(*FETCH_OPERAND, ["MDRo","MARi"], ["RAMo","Ai","NI"]),
  "STA":  M(*FETCH_OPERAND, ["MDRo","MARi"], ["Ao","RAMw","NI"]),
  "LDI":  M(["PCo","MARi"], ["RAMo","Ai","PCc","NI"]),
  "MAB":  M(["Ao","Bi","NI"]),
  "MBA":  M(["Bo","Ai","NI"]),
  "LDB":  M(*FETCH_OPERAND, ["MDRo","MARi"], ["RAMo","Bi","NI"]),
  "LBI":  M(["PCo","MARi"], ["RAMo","Bi","PCc","NI"]),
  "LDX":  M(["Bo","MARi"], ["RAMo","Ai","NI"]),
  "STX":  M(["Bo","MARi"], ["Ao","RAMw","NI"]),
  "ADD":  M([("alu","ADD"),"ALUo","Ai","FL","NI"]),
  "SUB":  M([("alu","SUB"),"ALUo","Ai","FL","NI"]),
  "ANA":  M([("alu","AND"),"ALUo","Ai","FL","NI"]),
  "ORA":  M([("alu","OR"), "ALUo","Ai","FL","NI"]),
  "XRA":  M([("alu","XOR"),"ALUo","Ai","FL","NI"]),
  "CMA":  M([("alu","NOT"),"ALUo","Ai","FL","NI"]),
  "INR":  M([("alu","INC"),"ALUo","Ai","FL","NI"]),
  "DCR":  M([("alu","DEC"),"ALUo","Ai","FL","NI"]),
  "SHL":  M([("alu","SHL"),"ALUo","Ai","FL","NI"]),
  "SHR":  M([("alu","SHR"),"ALUo","Ai","FL","NI"]),
  "ADI":  M(*FETCH_OPERAND, [("alu","ADD"),"ALUbMDR","ALUo","Ai","FL","NI"]),
  "SUI":  M(*FETCH_OPERAND, [("alu","SUB"),"ALUbMDR","ALUo","Ai","FL","NI"]),
  "ANI":  M(*FETCH_OPERAND, [("alu","AND"),"ALUbMDR","ALUo","Ai","FL","NI"]),
  "ORI":  M(*FETCH_OPERAND, [("alu","OR"), "ALUbMDR","ALUo","Ai","FL","NI"]),
  "XRI":  M(*FETCH_OPERAND, [("alu","XOR"),"ALUbMDR","ALUo","Ai","FL","NI"]),
  "CMP":  M([("alu","SUB"),"FL","NI"]),
  "CPI":  M(*FETCH_OPERAND, [("alu","SUB"),"ALUbMDR","FL","NI"]),
  "JMP":  M(*FETCH_OPERAND, ["MDRo","PCi","NI"]),
  "JZ":   M(*FETCH_OPERAND, ["MDRo",("PCi","Z"),"NI"]),
  "JNZ":  M(*FETCH_OPERAND, ["MDRo",("PCi","nZ"),"NI"]),
  "JC":   M(*FETCH_OPERAND, ["MDRo",("PCi","C"),"NI"]),
  "JNC":  M(*FETCH_OPERAND, ["MDRo",("PCi","nC"),"NI"]),
  "CALL": M(*FETCH_OPERAND, ["SPo","MARi"], ["PCo","RAMw","SPdec"], ["MDRo","PCi","NI"]),
  "RET":  M(["SPinc"], ["SPo","MARi"], ["RAMo","PCi","NI"]),
  "PUSH": M(["SPo","MARi"], ["Ao","RAMw","SPdec","NI"]),
  "POP":  M(["SPinc"], ["SPo","MARi"], ["RAMo","Ai","NI"]),
  "IN":   M(["INo","Ai","NI"]),
  "OUT":  M(["Ao","OUTi","NI"]),
}

# all plain (non-alu, non-conditional) control signals
SIGNALS = ["PCo","MDRo","Ao","Bo","ALUo","RAMo","SPo","INo",
           "MARi","PCi","IRi","MDRi","Ai","Bi","OUTi","RAMw",
           "PCc","SPinc","SPdec","FL","HALT","NI","ALUbMDR"]
DRIVERS = ["PCo","MDRo","Ao","Bo","ALUo","RAMo","SPo","INo"]   # bus output-enables


class SAP2:
    STACK_TOP = 0xFF
    DISPLAY_BASE = 0xF0                     # M[0xF0..0xFF] mirrored to the panel

    def __init__(self, program=None, inval=0):
        c = self.c = Circuit()
        self.RAM = list(program or [])
        self.RAM += [0] * (256 - len(self.RAM))
        self.in_val = inval & 0xFF

        raw = lambda init=0: c.dff(c.GND, en=c.GND, init=init)
        b8  = lambda init=0: [raw((init >> k) & 1) for k in range(8)]
        self.A=b8(); self.B=b8(); self.MAR=b8(); self.PC=b8(); self.IR=b8()
        self.MDR=b8(); self.SP=b8(self.STACK_TOP)
        self.Zf=raw(); self.Cf=raw(); self.Sf=raw()
        self.T = [raw(1 if i==0 else 0) for i in range(8)]     # step counter 0..7 (one-hot seed T0)
        self.Tbits = None
        # behavioral-memory interface nets (inputs to the netlist)
        self.ram_out = c.bus(8)
        self.in_nets = c.bus(8)

        # ---- step counter value (encode one-hot? no — keep a 3-bit counter) ----
        # simpler & cheaper: a 3-bit binary step register with a one-hot decode.
        self.Tc = [raw(0), raw(0), raw(0)]                     # 3-bit step counter, starts 0
        stepline = decoder(c, self.Tc)                         # 8 lines T0..T7

        # ---- opcode decode ----
        opmatch = {name: match_const(c, self.IR, code) for name,code in OPS.items()}

        # ---- flags & branch conditions ----
        condnet = {"Z":self.Zf, "nZ":c.not_(self.Zf), "C":self.Cf, "nC":c.not_(self.Cf)}

        # ---- build the control PLA from the microcode table ----
        # collect minterms per signal: list of (op, tstep, cond_or_None)
        mint = {s:[] for s in SIGNALS}
        alu_mint = []          # (op, tstep, aluopname)
        # fetch (common to every opcode): T0 PCo,MARi ; T1 RAMo,IRi,PCc
        fetch_terms = {"PCo":[0], "MARi":[0], "RAMo":[1], "IRi":[1], "PCc":[1]}
        for name, steps in MICRO.items():
            for j, toks in enumerate(steps):
                tstep = j + 2                                  # execute starts at T2
                for tok in toks:
                    if isinstance(tok, tuple) and tok[0]=="alu":
                        alu_mint.append((name, tstep, tok[1]))
                    elif isinstance(tok, tuple) and tok[0]=="PCi":
                        mint["PCi"].append((name, tstep, tok[1]))
                    else:
                        mint[tok].append((name, tstep, None))

        def term(name, tstep, cond):
            base = c.and_(opmatch[name], stepline[tstep])
            return base if cond is None else c.and_(base, condnet[cond])

        sig = {}
        for s in SIGNALS:
            terms = [c.and_(c.VCC, stepline[t]) for t in fetch_terms.get(s, [])]
            terms += [term(nm, ts, cd) for (nm, ts, cd) in mint[s]]
            sig[s] = c.or_list(terms) if terms else c.GND
        # ALU function-select (4 bits), one-hot-ish encoded op index
        selbits = []
        for b in range(4):
            terms = [c.and_(opmatch[nm], stepline[ts])
                     for (nm, ts, op) in alu_mint if (ALU_OPS[op] >> b) & 1]
            selbits.append(c.or_list(terms) if terms else c.GND)
        self.sig = sig
        self.HALT = sig["HALT"]

        # ---- ALU ----
        alu_b = [c.mux2(sig["ALUbMDR"], self.B[k], self.MDR[k]) for k in range(8)]
        aluR, aluC, aluZ, aluS = alu(c, self.A, alu_b, selbits)

        # ---- shared bus ----
        srcs = [self.PC, self.MDR, self.A, self.B, aluR, self.ram_out, self.SP, self.in_nets]
        bus = mux_onehot(c, [sig[d] for d in DRIVERS], srcs)
        self.bus = bus
        self.RAMw = sig["RAMw"]

        # ---- increments for PC and SP ----
        pc_inc,_ = add_sub(c, self.PC, [c.VCC]+[c.GND]*7, c.GND)
        sp_inc,_ = add_sub(c, self.SP, [c.VCC]+[c.GND]*7, c.GND)
        sp_dec,_ = add_sub(c, self.SP, [c.VCC]+[c.GND]*7, c.VCC)
        # step counter next: NI -> 0 else +1
        t_inc,_  = add_sub(c, self.Tc, [c.VCC]+[c.GND]*2, c.GND)

        # ---- rebind all flop D/enables ----
        def wire(q, d, en): ff=c.dffs_by_q(q); ff['d']=d; ff['en']=en
        for k in range(8):
            wire(self.MAR[k], bus[k], sig["MARi"])
            wire(self.IR[k],  bus[k], sig["IRi"])
            wire(self.MDR[k], bus[k], sig["MDRi"])
            wire(self.A[k],   bus[k], sig["Ai"])
            wire(self.B[k],   bus[k], sig["Bi"])
            # PC: jump-load bus, else increment on PCc, else hold
            pc_nxt = c.mux2(sig["PCi"], pc_inc[k], bus[k])
            wire(self.PC[k], c.mux2(c.or_(sig["PCc"], sig["PCi"]), self.PC[k], pc_nxt), c.VCC)
            # SP: inc / dec / hold
            sp_id  = c.mux2(sig["SPinc"], sp_dec[k], sp_inc[k])   # if inc use inc, elif dec use dec
            wire(self.SP[k], c.mux2(c.or_(sig["SPinc"], sig["SPdec"]), self.SP[k], sp_id), c.VCC)
        wire(self.Zf, aluZ, sig["FL"]); wire(self.Cf, aluC, sig["FL"]); wire(self.Sf, aluS, sig["FL"])
        for b in range(3):
            wire(self.Tc[b], c.mux2(sig["NI"], t_inc[b], c.GND), c.VCC)

        # OUT register (a real gate-level register) — output-enable never drives bus
        self.O = [c.dff(bus[k], en=sig["OUTi"], init=0) for k in range(8)]

        self.stepline = stepline
        c.settle()

    # ---------- behavioral memory splice ----------
    def _refresh(self):
        addr = self.c.getbus(self.MAR)
        self.c.setbus(self.ram_out, self.RAM[addr])
        self.c.setbus(self.in_nets, self.in_val)

    def step(self):
        c = self.c
        self._refresh(); c.settle()
        we  = c.get(self.RAMw); addr = c.getbus(self.MAR); data = c.getbus(self.bus)
        c.commit_dffs()
        if we: self.RAM[addr] = data & 0xFF
        self._refresh(); c.settle()

    # ---------- introspection ----------
    def tstate(self): return self.c.getbus(self.Tc)
    def opcode(self):  return self.c.getbus(self.IR)
    def active_signals(self):
        return [s for s in SIGNALS if self.c.get(self.sig[s])]
    def snapshot(self):
        g=self.c
        return dict(T=self.tstate(), PC=g.getbus(self.PC), MAR=g.getbus(self.MAR),
                    IR=g.getbus(self.IR), op=self.opcode(), A=g.getbus(self.A),
                    B=g.getbus(self.B), MDR=g.getbus(self.MDR), SP=g.getbus(self.SP),
                    OUT=g.getbus(self.O), Z=g.get(self.Zf), C=g.get(self.Cf),
                    S=g.get(self.Sf), bus=g.getbus(self.bus), halt=g.get(self.HALT),
                    sigs=self.active_signals())

    def run(self, max_cycles=20000, trace=False, on_out=None):
        c=self.c; outs=[]
        for _ in range(max_cycles):
            if c.get(self.HALT): break
            s=self.snapshot()
            if trace:
                print(f"  T{s['T']} PC={s['PC']:3d} IR={s['IR']:02x}"
                      f"({MNEM.get(s['op'],'?'):4}) A={s['A']:3d} B={s['B']:3d} "
                      f"SP={s['SP']:3d} Z={s['Z']} C={s['C']} bus={s['bus']:3d} "
                      f"[{' '.join(s['sigs'])}]")
            lo = c.get(self.sig["OUTi"])
            self.step()
            if lo:
                v=c.getbus(self.O); outs.append(v)
                if on_out: on_out(v)
        return outs
