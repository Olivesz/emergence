#!/usr/bin/env python3
"""Scratch: a 1-bit MEMORY = one glider circulating forever in a CLOSED 4-Snark
loop (bit=1 held). BOUNDED sims only. Reuses verified assets; imports only.

The loop: NW glider -> S1(NW->NE) -> S2(NE->SE) -> S3(SE->SW) -> S4(SW->NW)
-> back onto the SAME NW lane (-47) it started on -> S1 -> forever. This is
ha_dev.py's open 4-Snark reroute CLOSED onto itself: solve dx4 so the exit NW
lane == the entry NW lane. A Snark reflects on any phase from anywhere along
its lane, so lane-closure + S4 lying SE of S1 makes the whole state exactly
periodic: run(state, P) == state is a complete proof the bit is held forever.

Stage A (search_geoms) is the pure-algebra geometry search (run separately).
Stage B below seeds one glider into a curated closing geometry, finds the exact
loop period P by state-repetition, and verifies the catalysts and the single
glider survive many periods. Stage C adds a non-destructive DUPLICATOR read.
"""
import sys, time
from life import run, translate, bbox, normalize
from gadgets import (glider_dir, glider_lane, glider_phase, split_gliders,
                     DIRNAME, place_duplicator)
from routed import build_variants, bbox_gap, traj_params

t0 = time.time()
def log(*a): print(*a, flush=True)

V = build_variants()
S1, S2, S3, S4 = V['snark_m0r3'], V['snark_m0r0'], V['snark_m0r1'], V['snark_m0r2']
IN_LANE = -47   # S1 accepts NW on lane -47; a closed loop must return here

def lane_place_ymx(v, L, dx):   # incoming ymx (SE/NW) beam on lane L
    return dx, dx + (L - v.lin)
def lane_place_xpy(v, L, dx):   # incoming xpy (NE/SW) beam on lane L
    return dx, (L - v.lin) - dx

def geom(dx1, dx2, dx3, target=IN_LANE):
    p1 = lane_place_ymx(S1, IN_LANE, dx1); O1 = S1.lout + (p1[0] + p1[1])
    p2 = lane_place_xpy(S2, O1, dx2);      O2 = S2.lout + (p2[1] - p2[0])
    p3 = lane_place_ymx(S3, O2, dx3);      O3 = S3.lout + (p3[0] + p3[1])
    num = S4.lout + O3 - S4.lin - target
    if num % 2:
        return None
    dx4 = num // 2
    p4 = lane_place_xpy(S4, O3, dx4);      O4 = S4.lout + (p4[1] - p4[0])
    ps = (p1, p2, p3, p4)
    cats = [S1.place(*p1), S2.place(*p2), S3.place(*p3), S4.place(*p4)]
    return ps, (O1, O2, O3, O4), cats

def search_geoms():
    cands = []
    for dx1 in range(-70, 30, 2):
        for dx2 in range(-10, 90, 2):
            for dx3 in range(20, 200, 4):
                g = geom(dx1, dx2, dx3)
                if g is None: continue
                ps, Os, cats = g
                mingap = min(bbox_gap(cats[i], cats[j])
                             for i in range(4) for j in range(i + 1, 4))
                if mingap < 5: continue
                allc = set().union(*cats); bx0, by0, bx1, by1 = bbox(allc)
                cands.append((max(bx1 - bx0, by1 - by0), mingap, dx1, dx2, dx3, Os))
    cands.sort()
    return cands

# Primary: ha_dev's PROVEN-CLEAN reroute dx1,dx2,dx3=(-40,40,150) (legs 1-3
# identical to a verified NW->NE->SE->SW routing; only S4 retargeted to -47),
# then progressively tighter closing geometries from Stage A.
CANDS = [(-40, 40, 150), (-40, 40, 100), (-40, 40, 60), (0, 18, 40), (-20, -2, 20)]

def trace_one(dx1, dx2, dx3, T=4000, step=20):
    ps, Os, cats = geom(dx1, dx2, dx3)
    catU = set().union(*cats)
    log(f"\n-- trace dx=({dx1},{dx2},{dx3}) O1..O4={Os} --")
    for i, c in enumerate(cats):
        log(f"   S{i+1} bbox {bbox(c)}")
    seed = None
    for back in range(4, 80, 4):
        g = set(S1.input_glider(*ps[0], back=back))
        if not (g & catU) and min(bbox_gap(g, c) for c in cats) >= 5:
            seed = g; ub = back; break
    log(f"   seed back={ub} bbox {bbox(seed)} lane {glider_lane(seed)} dir {DIRNAME[glider_dir(seed)]}")
    s = catU | seed; t = 0
    while t < T:
        s = run(s, step); t += step
        gs, rest = split_gliders(s)
        extra = len(rest - catU); missing = len(catU - rest)
        info = [(DIRNAME[glider_dir(g)], glider_lane(g)) for g in gs]
        if extra or missing or len(gs) != 1:
            log(f"   t={t}: nglid={len(gs)} {info} extra={extra} missing={missing}  <-- perturbed")
            if missing:  # a catalyst got hit -> dead end, stop early
                log(f"   catalyst damaged at t={t}; aborting trace")
                return
        elif t % 200 == 0:
            log(f"   t={t}: {info}")
    log(f"   trace end t={t}")

def find_period(S, catU, Tmax=6000, chunk=4):
    """Smallest P>0 with run(S,P)==S; P is a multiple of 4 (glider phase).
    Returns (P, trace) or (None, trace). trace samples health along the way."""
    s = set(S); t = 0; trace = []
    while t < Tmax:
        s = run(s, chunk); t += chunk
        if t % 40 == 0:
            gs, rest = split_gliders(s)
            trace.append((t, len(gs), len(rest - catU), len(catU - rest)))
        if s == S:
            return t, trace
    return None, trace

def try_loop(dx1, dx2, dx3, verbose=True):
    ps, Os, cats = geom(dx1, dx2, dx3)
    catU = set().union(*cats)
    # seed an NW glider on lane -47 into S1, back far enough to clear every cat
    seed = None
    for back in range(0, 60, 4):
        g = set(S1.input_glider(*ps[0], back=back))
        if g & catU:  # overlaps a catalyst
            continue
        if min(bbox_gap(g, c) for c in cats) >= 3:
            seed = g; used_back = back; break
    if seed is None:
        return dict(dx=(dx1, dx2, dx3), ok=False, why="no clear seed placement")
    S = catU | seed
    if len(S) != len(catU) + 5:
        return dict(dx=(dx1, dx2, dx3), ok=False, why="seed overlaps catalyst")
    P, trace = find_period(S, catU)
    res = dict(dx=(dx1, dx2, dx3), Os=Os, back=used_back, ncat=len(catU),
               P=P, trace=trace)
    if P is None:
        # diagnose: did the glider die?
        died = [tr for tr in trace if tr[1] != 1 or tr[2] > 0]
        res.update(ok=False, why="no period found <=6000",
                   first_bad=died[0] if died else None,
                   last=trace[-1] if trace else None)
        return res
    # rigorous checks at period boundaries
    gs, rest = split_gliders(S)
    seed_sig = (DIRNAME[glider_dir(gs[0])], glider_lane(gs[0]))
    reps_ok = True; per_period = []
    st = set(S)
    for k in range(1, 6):
        st = run(st, P)
        exact = (st == S)
        gsk, restk = split_gliders(st)
        sigk = (len(gsk) == 1 and (DIRNAME[glider_dir(gsk[0])], glider_lane(gsk[0])) == seed_sig)
        cat_ok = (restk == catU)
        per_period.append((k, exact, len(gsk), sigk, cat_ok))
        reps_ok = reps_ok and exact and sigk and cat_ok
    res.update(ok=reps_ok, seed_sig=seed_sig, per_period=per_period,
               proof=(run(set(S), P) == S))
    return res

log("=== Stage B: closed 4-Snark glider loop (1-bit memory, bit=1) ===")
log(f"chain S1..S4 lanes: lin/lout = "
    f"{[(s.lin, s.lout) for s in (S1, S2, S3, S4)]}")

if '--trace' in sys.argv:
    trace_one(-40, 40, 150)
    trace_one(-40, 40, 60)
    log(f"\nelapsed {round(time.time()-t0,1)}s")
    sys.exit(0)

if '--traceread' in sys.argv:
    from gadgets import place_duplicator as _pd
    def geom_read_dbg(dx1, dx2, dx3, ddx, target=-47):
        p1 = lane_place_ymx(S1, -47, dx1); O1 = S1.lout + (p1[0] + p1[1])
        p2 = lane_place_xpy(S2, O1, dx2);  O2 = S2.lout + (p2[1] - p2[0])
        dup = set(_pd(ddx, ddx + (O2 + 1))); O2c = O2 - 22; Oread = O2 - 46
        p3 = lane_place_ymx(S3, O2c, dx3); O3 = S3.lout + (p3[0] + p3[1])
        num = S4.lout + O3 - S4.lin - target
        if num % 2: return None
        dx4 = num // 2; p4 = lane_place_xpy(S4, O3, dx4)
        cats = [S1.place(*p1), S2.place(*p2), S3.place(*p3), S4.place(*p4)]
        return dict(ps=(p1,p2,p3,p4), dup=dup, cats=cats, O=(O1,O2,O2c,O3), Oread=Oread)
    dx1, dx2, dx3 = -40, 40, 150
    def clearing(target_ddx):
        best = None
        for ddx in range(-40, 260, 2):
            G = geom_read_dbg(dx1, dx2, dx3, ddx)
            if G is None: continue
            objs = G['cats'] + [G['dup']]
            mg = min(bbox_gap(objs[i], objs[j]) for i in range(len(objs)) for j in range(i+1, len(objs)))
            if mg >= 5 and abs(ddx - target_ddx) < abs((best or 999) - target_ddx):
                best = ddx
        return best
    for tgt in (60, 110, 160):
        ddx = clearing(tgt)
        G = geom_read_dbg(dx1, dx2, dx3, ddx)
        catU = set().union(*G['cats']) | G['dup']
        log(f"\n-- traceread ddx={ddx} O(1,2,2c,3)={G['O']} Oread(NW)={G['Oread']} --")
        for i, c in enumerate(G['cats']): log(f"   S{i+1} bbox {bbox(c)}")
        log(f"   DUP bbox {bbox(G['dup'])}")
        seed = set(S1.input_glider(*G['ps'][0], back=8))
        s = catU | seed; t = 0; hist = []
        while t < 2600:
            s = run(s, 40); t += 40
            gs, rest = split_gliders(s)
            sig = tuple(sorted((DIRNAME[glider_dir(g)], glider_lane(g)) for g in gs))
            hist.append((t, sig, len(rest - catU), len(catU - rest)))
        for (tt, sig, ex, mi) in hist:
            log(f"   t={tt}: {list(sig)} extra={ex} miss={mi}")
    log(f"\nelapsed {round(time.time()-t0,1)}s")
    sys.exit(0)

winner = None
for dx in CANDS:
    r = try_loop(*dx)
    log(f"\ndx={r['dx']}  P={r.get('P')}  ok={r['ok']}")
    if not r['ok']:
        log(f"   why: {r.get('why')}  first_bad={r.get('first_bad')} last={r.get('last')}")
        continue
    log(f"   seed_sig={r['seed_sig']} back={r['back']} ncat={r['ncat']}")
    log(f"   run(S,P)==S proof: {r['proof']}")
    log(f"   per-period [k, exact, nglid, sig_ok, cats_ok]: {r['per_period']}")
    winner = r
    break

if winner:
    log(f"\nLOOP CLOSED: period P={winner['P']} ticks; single glider on lane "
        f"{IN_LANE} NW survives >=5 periods with all 4 Snark catalysts restored "
        f"EXACTLY (run(S,P)==S proves it holds forever).")
else:
    log("\nNo curated geometry closed cleanly (see diagnostics above).")

# ======================================================================
# Stage C: NON-DESTRUCTIVE READ. Splice a DUPLICATOR into the SE leg (the
# loop's only SE beam, S2->S3). Duplicator: SE in -> SE out (continues loop,
# 22 lanes over) + NW out (the READ glider, 46 lanes over, escapes each pass).
# The circulating bit persists; one read is emitted per period.
# Duplicator input lane = -1 + (dy-dx); SE out = in-22; NW out = in-46.
# ======================================================================
from gadgets import DUP_RECOVERY

def geom_read(dx1, dx2, dx3, ddx, target=IN_LANE):
    p1 = lane_place_ymx(S1, IN_LANE, dx1); O1 = S1.lout + (p1[0] + p1[1])
    p2 = lane_place_xpy(S2, O1, dx2);      O2 = S2.lout + (p2[1] - p2[0])  # SE leg
    # duplicator on the SE leg: input SE on lane O2 -> (dy-dx) = O2 + 1
    dup_dx, dup_dy = ddx, ddx + (O2 + 1)
    dup = set(place_duplicator(dup_dx, dup_dy))
    O2c = O2 - 22    # SE continuation lane (loop keeps going)
    Oread = O2 - 46  # NW read-output lane (escapes)
    p3 = lane_place_ymx(S3, O2c, dx3);     O3 = S3.lout + (p3[0] + p3[1])
    num = S4.lout + O3 - S4.lin - target
    if num % 2:
        return None
    dx4 = num // 2
    p4 = lane_place_xpy(S4, O3, dx4);      O4 = S4.lout + (p4[1] - p4[0])
    cats = [S1.place(*p1), S2.place(*p2), S3.place(*p3), S4.place(*p4)]
    return dict(ps=(p1, p2, p3, p4), dup=dup, cats=cats,
                O=(O1, O2, O2c, O3, O4), Oread=Oread,
                dup_at=(dup_dx, dup_dy))

def is_read(g, Oread):
    return glider_dir(g) == (-1, -1) and glider_lane(g) == Oread

def strip_reads(state, Oread):
    """(core = state minus read gliders, reads list, loop gliders list, residue)."""
    gs, rest = split_gliders(state)
    reads = [g for g in gs if is_read(g, Oread)]
    loops = [g for g in gs if not is_read(g, Oread)]
    core = set(state)
    for g in reads:
        core -= set(g)
    return core, reads, loops, rest

def verify_read(dx1, dx2, dx3, ddx):
    """Rigorous read verification. Reference is the STEADY loop core (catalysts +
    circulating glider, reads stripped) -- NOT the one-time seed. Then P is the
    core's self-recurrence, and at each of 5 periods the core must be identical
    while exactly one more read glider has escaped."""
    G = geom_read(dx1, dx2, dx3, ddx)
    if G is None:
        return dict(ddx=ddx, ok=False, why="parity")
    cats, dup, Oread = G['cats'], G['dup'], G['Oread']
    catU = set().union(*cats) | dup
    objs = cats + [dup]
    mg = min(bbox_gap(objs[i], objs[j]) for i in range(len(objs)) for j in range(i + 1, len(objs)))
    if mg < 5:
        return dict(ddx=ddx, ok=False, why=f"clearance {mg}")
    seed = None
    for back in range(4, 80, 4):
        g = set(S1.input_glider(*G['ps'][0], back=back))
        if not (g & catU) and min(bbox_gap(g, c) for c in objs) >= 5:
            seed = g; break
    if seed is None:
        return dict(ddx=ddx, ok=False, why="no clear seed")
    # 1) run past the seed transient to a CLEAN steady loop moment (loop glider
    #    back on lane -47, catalysts restored, no stray sparks)
    s = catU | seed; t = 0; base = None
    while t < 4000:
        s = run(s, 4); t += 4
        core, reads, loops, rest = strip_reads(s, Oread)
        if (t >= 1900 and rest == catU and len(loops) == 1
                and glider_dir(loops[0]) == (-1, -1)
                and glider_lane(loops[0]) == IN_LANE
                and core == catU | set(loops[0])):
            base = frozenset(core); t_ref = t; break
    if base is None:
        return dict(ddx=ddx, ok=False, why="no clean steady reference")
    # 2) near-period P: the loop is NOT byte-stationary (the duplicator emits at
    #    a timing-dependent position, so it does not re-anchor the glider the way
    #    a Snark does -> a small per-lap drift). Find the approximate lap time via
    #    the minimum symmetric-difference of the drifting core to the reference.
    s = set(base); t = 0; best = (10**9, 0)
    while t < 3000:
        s = run(s, 4); t += 4
        core, reads, loops, rest = strip_reads(s, Oread)
        if t >= 400 and len(loops) == 1 and glider_lane(loops[0]) == IN_LANE:
            sd = len(core ^ base)
            if sd < best[0]:
                best = (sd, t)
    P = best[1]
    if P == 0 or P <= DUP_RECOVERY:
        return dict(ddx=ddx, ok=False, why=f"no lap period (best={best})")
    # 3) verify >=5 PASSES. A "pass" k succeeds if, in a small window around
    #    t_ref + k*P, there is a CLEAN moment: all 6 catalysts restored exactly
    #    (rest==catU), exactly one circulating glider on lane -47, and exactly k
    #    read gliders have escaped NW on lane Oread. Tolerates the drift.
    rows = []; allok = True; drift = best[0]
    for k in range(1, 6):
        st = set(base); tt = t_ref
        found = None
        target_lo, target_hi = t_ref + k * P - 80, t_ref + k * P + 80
        while tt < target_hi:
            st = run(st, 4); tt += 4
            if tt < target_lo:
                continue
            core, reads, loops, rest = strip_reads(st, Oread)
            if (rest == catU and len(loops) == 1
                    and glider_dir(loops[0]) == (-1, -1)
                    and glider_lane(loops[0]) == IN_LANE
                    and len(reads) == k and all(is_read(g, Oread) for g in reads)):
                found = (tt, len(reads)); break
        rows.append((k, found))
        allok = allok and (found is not None)
    return dict(ddx=ddx, ok=allok, P=P, t_ref=t_ref, drift=drift, Oread=Oread,
                dup_at=G['dup_at'], O=G['O'], rows=rows, ncat=len(catU))

if winner:
    log("\n=== Stage C: non-destructive READ (duplicator on the SE leg) ===")
    dx1, dx2, dx3 = winner['dx']
    read_win = None
    for ddx in (60, 110, 160, 90, 140, 40):
        r = verify_read(dx1, dx2, dx3, ddx)
        log(f"ddx={ddx}: ok={r['ok']} P={r.get('P')} why={r.get('why')}")
        if r['ok']:
            read_win = r
            log(f"   READ LOOP OK  lap~P={r['P']} t_ref={r['t_ref']} drift/lap={r['drift']} "
                f"Oread(NW)={r['Oread']} dup@{r['dup_at']} ncat={r['ncat']}")
            log(f"   per-pass [k, (clean_t, #reads escaped)]: {r['rows']}")
            break
    if read_win:
        log(f"\nREAD OK: across 5 passes the circulating bit survives (1 glider on "
            f"lane {IN_LANE}, all 6 catalysts restored exactly at a clean moment "
            f"each pass) and exactly ONE new NW read glider on lane "
            f"{read_win['Oread']} has escaped per pass (k reads after k passes). "
            f"NB the read loop is not byte-stationary: the duplicator emits at a "
            f"timing-dependent position, giving a ~{read_win['drift']}-cell/lap drift "
            f"(the pure Snark-only loop, by contrast, is exactly periodic).")
    else:
        log("\nRead-tap did not verify across the tried placements (see notes).")

log(f"\nelapsed {round(time.time()-t0,1)}s")
