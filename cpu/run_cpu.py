#!/usr/bin/env python3
"""Run real programs on the SAP-1+ CPU and check the results."""
from sap1 import SAP1
from asm import assemble

def banner(t): print("\n" + "=" * 62 + f"\n{t}\n" + "=" * 62)

# ---- Program 1: 5 + 3 = 8 (memory operands, output) --------------------
P1 = """
        LDA  x        ; A = M[x] = 5
        ADD  y        ; A = A + M[y] = 8
        OUT           ; display
        HLT
x:      DB 5
y:      DB 3
"""

# ---- Program 2: 9 - 4 = 5 (subtract) -----------------------------------
P2 = """
        LDA  x
        SUB  y
        OUT
        HLT
x:      DB 9
y:      DB 4
"""

# ---- Program 3: countdown 3,2,1,0  (loop + JZ branch + JMP) -------------
P3 = """
        LDI  3        ; A = 3
loop:   OUT           ; display A
        JZ   done     ; if A == 0 -> stop
        SUB  one      ; A = A - 1
        JMP  loop
done:   HLT
one:    DB 1
"""

# ---- Program 4: sum 4+3+2+1 = 10  (accumulate in memory, loop) ---------
#  Packed to exactly 16 bytes: sum/n data cells are preloaded, no init stores.
P4 = """
        LDI  4        ; n = 4
        STA  n
loop:   LDA  n
        JZ   done     ; n==0 -> finish
        ADD  sum
        STA  sum      ; sum += n
        LDA  n
        SUB  one
        STA  n        ; n -= 1
        JMP  loop
done:   LDA  sum
        OUT
        HLT
one:    DB 1
n:      DB 0
sum:    DB 0
"""

# ---- Program 5: Fibonacci until 8-bit overflow (JC carry branch) --------
P5 = """
top:    LDA  a
        OUT           ; print a
        ADD  b        ; A = a + b  (sets carry on >255)
        JC   done     ; overflow -> stop
        STA  t
        LDA  b
        STA  a        ; a = b
        LDA  t
        STA  b        ; b = a+b
        JMP  top
done:   HLT
a:      DB 1
b:      DB 1
t:      DB 0
"""

def check(name, image, want_outs, trace=False, maxc=2000):
    cpu = SAP1(image)
    outs = cpu.run(max_cycles=maxc, trace=trace)
    ok = outs == want_outs
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: outputs={outs} (want {want_outs})")
    return ok

if __name__ == "__main__":
    ok = True
    banner("SAP-1+ : running real programs on the NAND+DFF CPU")

    img, lbl = assemble(P1)
    print("Program 1 image:", [f"{b:02x}" for b in img])
    ok &= check("5 + 3", img, [8])

    img, _ = assemble(P2)
    ok &= check("9 - 4", img, [5])

    img, _ = assemble(P3)
    ok &= check("countdown 3..0", img, [3, 2, 1, 0])

    img, _ = assemble(P4)
    ok &= check("sum 1..4", img, [10])

    img, _ = assemble(P5)
    ok &= check("Fibonacci", img, [1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144])

    print("\n" + ("ALL PROGRAMS PASS" if ok else "SOME PROGRAMS FAILED"))
    raise SystemExit(0 if ok else 1)
