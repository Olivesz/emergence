#!/usr/bin/env python3
"""
ww_cells.py — Wireworld standard-cell verification for the Emergence CPU (Act VIII).

Self-contained: run `python3 ww_cells.py`. No imports beyond the stdlib.

Two clocked logic cells are built and verified by direct simulation of the
exact Wireworld rule (engine copied verbatim from cpu.py):

  CELL 1 — NAND.
    A 5-cell corner-fed junction (same family as the finalAND.py F-junction):
    center J with four diagonal ports. A real clock loop (circulating
    electron, period P) drives a tap wire into the NW port; inputs A and B
    are pulses injected in phase with the clock into the NE and SW ports;
    output leaves via the SE port. The center fires on 1 or 2 adjacent
    heads and is suppressed by 3 — so the clock pulse passes (output=1)
    unless BOTH A and B arrive with it (3 heads -> suppressed, output=0).
    This IS the "clock-fed suppression junction": NAND in a single stage.

  CELL 2 — 1-bit register / D-latch cell (loop storage).
    The verified writable register from cpu.py reg_test (loop + SET wire
    + left-edge vertical diode + non-destructive read tap), extended with
    a CLEAR junction: the right edge of the loop makes a 1-cell "V-jog"
    through a junction cell J (in -> J -> out, diagonal jog). All of J's
    east neighbours are exterior, and the two cells (W+2,K-1),(W+2,K) are
    adjacent to J and to NOTHING else on the loop — so a 2-wide clear wire
    delivering two simultaneous heads there, synchronized with the stored
    electron's arrival at `in`, gives J three adjacent heads: the
    circulating electron is annihilated with zero residue. Mistimed clear
    pulses do NOT clear (synchronization is load-bearing, as in any
    clocked design).

Every claim below is verified by simulation and printed as PASS/FAIL.
"""

# ----------------------------------------------------------------------
# Wireworld engine — reference implementation copied verbatim from cpu.py
# ----------------------------------------------------------------------
def step(W, H, g):
    n = [0] * (W * H)
    for y in range(H):
        yb = y * W
        for x in range(W):
            i = yb + x; s = g[i]
            if s == 1: n[i] = 2
            elif s == 2: n[i] = 3
            elif s == 0: n[i] = 0
            else:
                h = 0
                for dy in (-1, 0, 1):
                    ny = y + dy
                    if 0 <= ny < H:
                        b = ny * W
                        for dx in (-1, 0, 1):
                            if (dx or dy):
                                nx = x + dx
                                if 0 <= nx < W and g[b + nx] == 1: h += 1
                n[i] = 1 if h in (1, 2) else 3
    return n


# Fast sparse engine (identical semantics; cross-checked against `step`
# below before any result is trusted).
class Sim:
    def __init__(self, W, H, base):
        self.W, self.H = W, H
        self.g = base[:]
        self.nbr = []
        for i in range(W * H):
            x, y = i % W, i // W
            ns = []
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    if dx or dy:
                        nx, ny = x + dx, y + dy
                        if 0 <= nx < W and 0 <= ny < H:
                            ns.append(ny * W + nx)
            self.nbr.append(ns)
        self.heads = [i for i, s in enumerate(base) if s == 1]
        self.tails = [i for i, s in enumerate(base) if s == 2]

    def inject(self, x, y):
        """Place a lone electron head on a conductor cell (dead-end launch,
        exactly as cpu.py set_test/reg_test do)."""
        i = y * self.W + x
        if self.g[i] == 3:
            self.g[i] = 1
            self.heads.append(i)

    def tick(self):
        g = self.g
        cnt = {}
        for h in self.heads:
            for j in self.nbr[h]:
                if g[j] == 3:
                    cnt[j] = cnt.get(j, 0) + 1
        new_heads = [j for j, c in cnt.items() if c == 1 or c == 2]
        for i in self.tails: g[i] = 3
        for i in self.heads: g[i] = 2
        for j in new_heads: g[j] = 1
        self.tails = self.heads
        self.heads = new_heads

    def is_head(self, x, y):
        return self.g[y * self.W + x] == 1

    def electrons(self):
        return len(self.heads) + len(self.tails)


# ----------------------------------------------------------------------
# Grid construction helpers (copied from cpu.py)
# ----------------------------------------------------------------------
class G:
    def __init__(s): s.c = set()
    def put(s, x, y): s.c.add((x, y))
    def hl(s, x0, x1, y):
        for x in range(min(x0, x1), max(x0, x1) + 1): s.put(x, y)
    def vl(s, y0, y1, x):
        for y in range(min(y0, y1), max(y0, y1) + 1): s.put(x, y)

DIODE_H = [(0,0),(1,0),(2,0),(3,0),(4,0),(5,-1),(5,0),(5,1),(6,-1),(6,1),
           (7,-1),(7,0),(8,-1),(9,-1),(10,0),(11,0),(12,0),(13,0),(14,0)]
DIODE_UP = [(dy, -dx) for (dx, dy) in DIODE_H]

def stamp_diode_up(g, x, y):        # entry (x,y) bottom, exit (x,y-14) top
    for dx, dy in DIODE_UP: g.put(x + dx, y + dy)
    return (x, y - 14)

def pack(g, ports):
    xs = [p[0] for p in g.c] + [p[0] for p in ports]
    ys = [p[1] for p in g.c] + [p[1] for p in ports]
    mnx = min(xs) - 1; mny = min(ys) - 1
    W = max(xs) - mnx + 2; H = max(ys) - mny + 2
    base = [0] * (W * H)
    for (x, y) in g.c: base[(y - mny) * W + (x - mnx)] = 3
    return W, H, base, [(p[0] - mnx, p[1] - mny) for p in ports]


# ----------------------------------------------------------------------
# Engine cross-check: fast sparse engine vs reference step()
# ----------------------------------------------------------------------
def crosscheck(W, H, base, injections, S):
    """Run both engines with the same injection schedule; compare grids."""
    sim = Sim(W, H, base)
    ref = base[:]
    for t in range(S):
        for (tt, x, y) in injections:
            if tt == t:
                sim.inject(x, y)
                i = y * W + x
                if ref[i] == 3: ref[i] = 1
        sim.tick()
        ref = step(W, H, ref)
        if sim.g != ref:
            return False
    return True


# ======================================================================
# CELL 1 — clocked NAND
# ======================================================================
CW, CHT = 10, 6          # clock loop rectangle
TAPX = 5                 # tap column on the clock loop's bottom edge
JX, JY = 24, 12          # junction center
LW = 10                  # A/B input wire length

def build_nand():
    g = G()
    # clock loop
    g.hl(0, CW, 0); g.hl(0, CW, CHT); g.vl(0, CHT, 0); g.vl(0, CHT, CW)
    # tap branch: down off the bottom edge, then east into the NW port
    g.vl(CHT + 1, JY - 1, TAPX)
    g.hl(TAPX, JX - 1, JY - 1)                    # ends at Fnw=(JX-1,JY-1)
    # 5-cell junction: center + four diagonal ports
    for p in ((JX, JY), (JX-1, JY-1), (JX+1, JY-1), (JX-1, JY+1), (JX+1, JY+1)):
        g.put(*p)
    g.hl(JX + 2, JX + 1 + LW, JY - 1)             # A wire (east, into Fne)
    g.hl(JX - 1 - LW, JX - 2, JY + 1)             # B wire (west, into Fsw)
    g.hl(JX + 2, JX + 8, JY + 1)                  # OUT wire (east from Fse)
    ports = [(2, 0), (1, 0),                      # clock seed: head, tail
             (JX - 1, JY - 1),                    # Fnw probe (clock arrival)
             (JX + 1 + LW, JY - 1),               # A injection cell
             (JX - 1 - LW, JY + 1),               # B injection cell
             (JX + 6, JY + 1)]                    # output probe
    return pack(g, ports)

def nand_run(W, H, base, pk, a_at, b_at, S):
    seedH, seedT, fnw, ain, bin_, out = pk
    sim = Sim(W, H, base)
    sim.g[seedH[1] * W + seedH[0]] = 1; sim.heads = [seedH[1] * W + seedH[0]]
    sim.g[seedT[1] * W + seedT[0]] = 2; sim.tails = [seedT[1] * W + seedT[0]]
    fnwh, outh = [], []
    for t in range(S):
        if a_at == t: sim.inject(*ain)
        if b_at == t: sim.inject(*bin_)
        sim.tick()
        if sim.is_head(*fnw): fnwh.append(t + 1)
        if sim.is_head(*out): outh.append(t + 1)
    return fnwh, outh

def verify_nand(results):
    W, H, base, pk = build_nand()

    # engine cross-check on this circuit (clock seed + worst-case injections)
    seedH, seedT = pk[0], pk[1]
    cbase = base[:]
    cbase[seedH[1] * W + seedH[0]] = 1
    cbase[seedT[1] * W + seedT[0]] = 2
    okx = crosscheck(W, H, cbase, [(28, pk[3][0], pk[3][1]),
                                   (28, pk[4][0], pk[4][1])], 120)
    results.append(("NAND engine cross-check (fast == reference)", okx))

    # calibration: run the clock alone, find its arrivals at the NW port
    fnwh, outh = nand_run(W, H, base, pk, None, None, 400)
    P = fnwh[2] - fnwh[1]
    cstar = next(c for c in fnwh if c > 2 * LW + 10)   # a comfortable edge
    tinj = cstar - LW          # lone head travels LW cells to reach its port
    print(f"  clock loop period P={P}, clock edges at Fnw: {fnwh[:4]}...")
    print(f"  target clock window t*={cstar}; inputs injected at t={tinj} "
          f"(in phase: arrival == t*)")

    table = []
    for (A, B) in ((0, 0), (0, 1), (1, 0), (1, 1)):
        fh, oh = nand_run(W, H, base, pk,
                          tinj if A else None, tinj if B else None,
                          cstar + 2 * P)
        win = [t for t in oh if cstar <= t < cstar + P]
        nxt = [t for t in oh if cstar + P <= t < cstar + 2 * P]
        got = 1 if win else 0
        want = 0 if (A and B) else 1
        ok = got == want
        table.append((A, B, got, want, ok, win, nxt))
        results.append((f"NAND row A={A} B={B}: out={got} (want {want})", ok))

    print("  A B | out | want |  fires in output window")
    for (A, B, got, want, ok, win, nxt) in table:
        print(f"  {A} {B} |  {got}  |  {want}   |  {win if win else '-'}   "
              f"[{'PASS' if ok else 'FAIL'}]")
    # clock stream survives a suppression: next window fires again after 1,1
    rec = table[3][6]
    okr = bool(rec)
    results.append(("NAND clock recovers after 1,1 suppression "
                    f"(next window fires at {rec})", okr))


# ======================================================================
# CELL 2 — 1-bit register (loop storage) with SET and synchronized CLEAR
# ======================================================================
RW, RH = 20, 14          # register loop rectangle (h=14 matches diode span)
K = 7                    # V-jog row on the right edge
CLW = 8                  # clear wire length
SETIN = (-8, 0)
READOUT = (6, RH + 4)

def build_reg():
    g = G()
    g.hl(-8, RW, 0)                       # top edge + SET wire
    g.hl(0, RW, RH)                       # bottom edge
    g.vl(0, K - 1, RW)                    # right edge, upper part
    g.put(RW + 1, K)                      # J: the V-jog junction cell
    g.vl(K + 1, RH, RW)                   # right edge, lower part
    stamp_diode_up(g, 0, RH)              # left edge = upward diode
    g.vl(RH + 1, RH + 4, 6)               # read tap (non-destructive)
    g.hl(RW + 2, RW + 2 + CLW, K - 1)     # clear wire, upper lane (tip T1)
    g.hl(RW + 2, RW + 2 + CLW, K)         # clear wire, lower lane (tip T2)
    ports = [SETIN, READOUT,
             (RW, K - 1),                 # 'in' probe: cell before J
             (RW + 2 + CLW, K - 1),       # clear injection, upper lane
             (RW + 2 + CLW, K),           # clear injection, lower lane
             (RW + 2, K - 1), (RW + 2, K)]  # clear tips (calibration probes)
    return pack(g, ports)

def reg_run(W, H, base, pk, sets=(), clears=(), S=700):
    pset, pread, pin, injA, injB, tipA, tipB = pk
    sim = Sim(W, H, base)
    reads, inhits, tipboth = [], [], []
    for t in range(S):
        if t in sets: sim.inject(*pset)
        if t in clears:
            sim.inject(*injA); sim.inject(*injB)
        sim.tick()
        if sim.is_head(*pread): reads.append(t + 1)
        if sim.is_head(*pin): inhits.append(t + 1)
        if sim.is_head(*tipA) and sim.is_head(*tipB): tipboth.append(t + 1)
    return reads, inhits, tipboth, sim.electrons()

def gapset(seq):
    return sorted({seq[i + 1] - seq[i] for i in range(len(seq) - 1)})

def verify_reg(results):
    W, H, base, pk = build_reg()

    # engine cross-check on this circuit (SET at 0, clear pulse mid-run)
    okx = crosscheck(W, H, base,
                     [(0, pk[0][0], pk[0][1]),
                      (150, pk[3][0], pk[3][1]), (150, pk[4][0], pk[4][1])],
                     260)
    results.append(("DFF engine cross-check (fast == reference)", okx))

    # --- HOLD: write a 1, watch the read tap for 8 periods -------------
    reads, inhits, _, el = reg_run(W, H, base, pk, sets=(0,), S=560)
    gaps = gapset(reads)
    P = gaps[0] if len(gaps) == 1 else None
    ok_hold = (len(reads) >= 7 and len(gaps) == 1 and reads[-1] > 560 - P - 4)
    print(f"  HOLD:  SET at t=0 -> reads at {reads[:5]}... "
          f"gap set {gaps} (stable period), last read t={reads[-1]}")
    results.append((f"DFF HOLD: stored 1 re-read every {P} ticks, "
                    f"{len(reads)} non-destructive reads, bit alive at end", ok_hold))

    # --- WRITE: Q follows D --------------------------------------------
    ok_w1 = len(reads) > 0                       # D=1: SET pulse -> Q=1
    r0, _, _, el0 = reg_run(W, H, base, pk, sets=(), S=300)
    ok_w0 = (not r0) and el0 == 0                # D=0: no pulse -> Q=0
    results.append(("DFF WRITE D=1: SET pulse through diode -> Q=1 "
                    "(read tap fires)", ok_w1))
    results.append(("DFF WRITE D=0: no pulse -> Q=0 "
                    "(read tap silent, loop empty)", ok_w0))

    # --- CLEAR calibration ---------------------------------------------
    # (1) travel time: inject on the quiescent structure, see when both
    #     clear tips carry heads.
    _, _, tipboth, _ = reg_run(W, H, base, pk, clears=(200,), S=240)
    off = tipboth[0] - 200
    # (2) stored-bit phase: 'in' probe head times from the HOLD run.
    t_star = next(t for t in inhits if t > 250)
    t_inj = t_star - off
    print(f"  CLEAR: tips reached {off} ticks after injection; stored head at "
          f"'in' at t={t_star} -> synchronized injection at t={t_inj}")

    # --- CLEAR: synchronized suppression pulse -------------------------
    rc, _, _, elc = reg_run(W, H, base, pk, sets=(0,), clears=(t_inj,),
                            S=t_star + 300)
    pre = [t for t in rc if t < t_inj]
    post = [t for t in rc if t > t_star + P]
    ok_clear = (len(pre) >= 3) and (not post) and elc == 0
    print(f"  CLEAR: read tap before clear: {pre[:4]}...  after clear: "
          f"{post if post else 'SILENT'}; electrons left in grid: {elc}")
    results.append(("DFF CLEAR: synchronized suppression pulse kills the "
                    "circulating electron (reads stop, 0 electrons remain)", ok_clear))

    # --- CLEAR synchronization requirement (mistimed pulse != clear) ---
    rm, _, _, elm = reg_run(W, H, base, pk, sets=(0,), clears=(t_inj + 2,),
                            S=t_star + 300)
    ok_sync = bool([t for t in rm if t > t_star + P])
    results.append(("DFF CLEAR is genuinely synchronized: a pulse 2 ticks "
                    "late does NOT clear (bit still read afterwards)", ok_sync))

    # --- WRITE after CLEAR: full 1 -> 0 -> 1 cycle ---------------------
    t_re = t_inj + 80
    S_rw = t_inj + 400
    sim_reads, _, _, elw = reg_run(W, H, base, pk, sets=(0, t_re),
                                   clears=(t_inj,), S=S_rw)
    mid = [t for t in sim_reads if t_inj < t <= t_re]
    post2 = [t for t in sim_reads if t > t_re]
    g2 = gapset(post2)
    ok_rw = (not mid) and len(post2) >= 3 and g2 == [P] \
            and post2[-1] > S_rw - P - 4 and elw >= 2
    print(f"  WRITE-CLEAR-WRITE: reads between clear and re-set: "
          f"{mid if mid else 'none'}; after re-SET: {post2[:3]}... gaps {g2}")
    results.append(("DFF full cycle: write 1, clear to 0, write 1 again "
                    "(reads silent while 0, periodic again after re-set)", ok_rw))

    print("  note: CLEAR is defined for Q=1 (it is the synchronized "
          "suppression of a present electron); issuing CLEAR on an empty "
          "loop is a protocol violation — J then sees only 2 heads and "
          "fires, injecting a spurious bit. Gate CLEAR with Q (one NAND) "
          "when composing.")


# ======================================================================
if __name__ == "__main__":
    print("=" * 70)
    print("Wireworld standard-cell verification (engine: exact cpu.py rule)")
    print("=" * 70)
    results = []

    print("\nCELL 1 — clocked NAND (clock loop -> suppression junction)")
    verify_nand(results)

    print("\nCELL 2 — 1-bit register: loop + diode SET + read tap + "
          "synchronized CLEAR")
    verify_reg(results)

    print("\n" + "=" * 70)
    print("VERIFICATION REPORT")
    print("=" * 70)
    fails = []
    for (name, ok) in results:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
        if not ok: fails.append(name)
    print("-" * 70)
    if fails:
        print(f"{len(fails)} FAILURE(S):")
        for f in fails: print("  -", f)
    else:
        print("ALL PASS")
