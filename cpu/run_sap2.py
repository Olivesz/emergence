#!/usr/bin/env python3
"""Real algorithms running on the SAP-2 CPU — multiply, divide, GCD, Fibonacci,
and an in-memory bubble sort. Every program self-checks its output."""
from sap2 import SAP2
from asm2 import assemble

def check(name, src, want, inval=0, maxc=200000):
    img, _ = assemble(src)
    cpu = SAP2(img, inval=inval)
    outs = cpu.run(max_cycles=maxc)
    ok = outs == want
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {outs}" + ("" if ok else f"  want {want}"))
    return ok

# multiply 6*7 = 42 by repeated addition
MUL = """
        LDI 0
        STA prod
        LDA y
        STA cnt
mloop:  LDA cnt
        JZ   mdone
        LDA  prod
        LDB  x
        ADD
        STA  prod
        LDA  cnt
        DCR
        STA  cnt
        JMP  mloop
mdone:  LDA  prod
        OUT
        HLT
x: DB 6
y: DB 7
prod: DB 0
cnt: DB 0
"""

# divide 47 / 5 -> quotient 9, remainder 2 (repeated subtraction; C = borrow = x<y)
DIV = """
        LDI 0
        STA q
divl:   LDA x
        LDB y
        CMP
        JC   ddone
        LDA  x
        LDB  y
        SUB
        STA  x
        LDA  q
        INR
        STA  q
        JMP  divl
ddone:  LDA  q
        OUT
        LDA  x
        OUT
        HLT
x: DB 47
y: DB 5
q: DB 0
"""

# gcd(48,36) = 12 (Euclid by subtraction)
GCD = """
gloop:  LDA a
        LDB b
        CMP
        JZ   gdone
        JC   blt
        LDA  a
        LDB  b
        SUB
        STA  a
        JMP  gloop
blt:    LDA  b
        LDB  a
        SUB
        STA  b
        JMP  gloop
gdone:  LDA  a
        OUT
        HLT
a: DB 48
b: DB 36
"""

# Fibonacci, now with an 8-bit machine and INR-based loop, till overflow
FIB = """
        LDA a
        OUT
        LDA a
        LDB b
        ADD
        JC   done
        STA  t
        LDA  b
        STA  a
        LDA  t
        STA  b
        JMP  0
done:   HLT
a: DB 1
b: DB 1
t: DB 0
"""

# primes up to 20 by trial division (nested loops + modulo via repeated subtraction)
PRIMES = """
        NP1 = 21
        LDI 2
        STA n
ploop:  LDA n
        CPI NP1
        JNC pend
        LDI 2
        STA d
tloop:  LDA d
        LDB n
        CMP
        JNC prime
        LDA n
        STA r
modl:   LDA r
        LDB d
        CMP
        JC   moddone
        LDA  r
        LDB  d
        SUB
        STA  r
        JMP  modl
moddone: LDA r
        CPI 0
        JZ   notprime
        LDA  d
        INR
        STA  d
        JMP  tloop
prime:  LDA n
        OUT
next:   LDA n
        INR
        STA n
        JMP  ploop
notprime: JMP next
pend:   HLT
n: DB 0
d: DB 0
r: DB 0
"""

# in-memory bubble sort, then print the sorted array (indirect addressing)
SORT = """
        N = 6
        LDI N
        DCR
        STA passes
outer:  LDA passes
        JZ   done
        LDI arr
        STA p
        LDI N
        DCR
        STA icnt
inner:  LDA icnt
        JZ   nextp
        LDA  p
        MAB
        LDX
        STA  ai
        LDA  p
        INR
        MAB
        LDX
        STA  aip
        LDA  ai
        LDB  aip
        CMP
        JC   noswap
        JZ   noswap
        LDA  p
        MAB
        LDA  aip
        STX
        LDA  p
        INR
        MAB
        LDA  ai
        STX
noswap: LDA  p
        INR
        STA  p
        LDA  icnt
        DCR
        STA  icnt
        JMP  inner
nextp:  LDA  passes
        DCR
        STA  passes
        JMP  outer
done:   LDI arr
        STA p
        LDI N
        STA ocnt
oloop:  LDA ocnt
        CPI 0
        JZ   end
        LDA  p
        MAB
        LDX
        OUT
        LDA  p
        INR
        STA  p
        LDA  ocnt
        DCR
        STA  ocnt
        JMP  oloop
end:    HLT
arr: DB 5 2 8 1 9 3
ai: DB 0
aip: DB 0
passes: DB 0
icnt: DB 0
ocnt: DB 0
p: DB 0
"""

if __name__ == "__main__":
    print("=" * 60 + "\nSAP-2 : real algorithms on the NAND+DFF CPU\n" + "=" * 60)
    ok = True
    ok &= check("multiply 6*7", MUL, [42])
    ok &= check("divide 47/5 (q,r)", DIV, [9, 2])
    ok &= check("gcd(48,36)", GCD, [12])
    ok &= check("fibonacci", FIB, [1,1,2,3,5,8,13,21,34,55,89,144])
    ok &= check("primes < 20", PRIMES, [2,3,5,7,11,13,17,19])
    ok &= check("bubble sort", SORT, [1,2,3,5,8,9])
    print("\n" + ("ALL PASS" if ok else "SOME FAILED"))
    raise SystemExit(0 if ok else 1)
