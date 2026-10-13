#!/usr/bin/env python3
"""Run every check in the repo and exit non-zero if any of them fails.

    python3 verify.py --fast      the push gate (about a minute)
    python3 verify.py --nightly   --fast plus the slow raw-rule runs
    python3 verify.py --stats     print the counts the READMEs quote
    python3 verify.py --falsify   break each fast check on purpose; each must fail
                                  (add --nightly to include the slow ones)

Every check is a script that prints its own PASS/FAIL lines and exits 0 only
when everything it checks holds.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.abspath(__file__))

# (name, working dir, argv, tier)
CHECKS = [
    ("netlist primitives",     "cpu", ["wwlogic.py"], "fast"),
    ("datapath modules",       "cpu", ["modules.py"], "fast"),
    ("SAP-1 programs",         "cpu", ["run_cpu.py"], "fast"),
    ("SAP-2 programs",         "cpu", ["run_sap2.py"], "fast"),
    ("Wireworld cells",        "cpu", ["ww_cells.py"], "fast"),
    ("Wireworld tile library", "cpu", ["wwtiles.py"], "fast"),
    ("dual-rail lowering",     "cpu", ["wwlower.py"], "fast"),
    ("compiled to Wireworld",  "cpu", ["test_wwcompile.py"], "fast"),
    ("Act VIII toy gates",     "cpu", ["test_toy_gates.py"], "fast"),
    ("page build reproducible", "cpu", ["build_pages.py", "--check"], "fast"),
    ("JS engines == Python",   "cpu", ["test_js_parity.py"], "fast"),
    ("quoted numbers",         "tests", ["test_numbers.py"], "fast"),
    ("Life engine",            "glider-logic", ["life.py"], "fast"),
    ("glider gates",           "glider-logic", ["gates.py"], "fast"),
    ("Snark + duplicator",     "glider-logic", ["gadgets.py"], "fast"),
    ("glider crossing",        "glider-logic", ["crossover.py"], "fast"),
    ("routed glider rungs",    "glider-logic", ["routed.py"], "nightly"),
    ("routed half-adder",      "glider-logic", ["ha_full.py"], "nightly"),
    ("half-adder per bit",     "glider-logic", ["ha_adder.py"], "nightly"),
    ("Carlini adder 6+5",      "glider-logic", ["carlini_adder.py"], "nightly"),
]

# Each check must FAIL when the thing it checks is broken: (check, file, old, new).
MUTATIONS = [
    ("netlist primitives", "cpu/wwlogic.py",
     "v[o] = 0 if (v[a] and v[b]) else 1", "v[o] = 0 if (v[a] or v[b]) else 1"),
    ("datapath modules", "cpu/modules.py",
     "    cout = c.or_(c.and_(a, b), c.and_(s1, cin))", "    cout = c.and_(c.and_(a, b), c.and_(s1, cin))"),
    ("SAP-1 programs", "cpu/run_cpu.py",
     'ok &= check("5 + 3", img, [8])', 'ok &= check("5 + 3", img, [9])'),
    ("SAP-2 programs", "cpu/run_sap2.py",
     'ok &= check("multiply 6*7", MUL, [42])', 'ok &= check("multiply 6*7", MUL, [43])'),
    ("Wireworld cells", "cpu/ww_cells.py",
     "n[i] = 1 if h in (1, 2) else 3", "n[i] = 1 if h in (1, 2, 3) else 3"),
    ("Wireworld tile library", "cpu/wwtiles.py",
     "cells |= set(path((P, T - 1), (16, 19)))", "cells |= set(path((P, T - 1), (16, 20)))"),
    ("dual-rail lowering", "cpu/wwlower.py",
     "rails[base] = (m, n)", "rails[base] = (n, m)"),
    ("compiled to Wireworld", "cpu/wwlower.py",
     "rails[base] = (m, n)", "rails[base] = (n, m)"),
    ("Act VIII toy gates", "index.html",
     '" A######     #    "', '" A## ###     #    "'),
    ("page build reproducible", "cpu/wwcpu.js",
     "and_(a, b) { return this.not_(this.nand(a, b)); }", "and_(a, b) { return this.nand(a, b); }"),
    ("JS engines == Python", "cpu/wwcpu.js",
     "and_(a, b) { return this.not_(this.nand(a, b)); }", "and_(a, b) { return this.nand(a, b); }"),
    ("quoted numbers", "cpu/README.md",
     "**1446 NAND gates + 175 flip-flops**", "**1447 NAND gates + 175 flip-flops**"),
    ("Life engine", "glider-logic/life.py",
     "if n == 3 or (n == 2 and c in cells)", "if n == 3 or (n == 1 and c in cells)"),
    ("glider gates", "glider-logic/life.py",
     "if n == 3 or (n == 2 and c in cells)", "if n == 3 or (n == 1 and c in cells)"),
    ("Snark + duplicator", "glider-logic/life.py",
     "if n == 3 or (n == 2 and c in cells)", "if n == 3 or (n == 1 and c in cells)"),
    ("glider crossing", "glider-logic/life.py",
     "if n == 3 or (n == 2 and c in cells)", "if n == 3 or (n == 1 and c in cells)"),
    ("routed glider rungs", "glider-logic/routed.py",
     "ok = (tau == tau_out)", "ok = (tau == tau_out + 1)"),
    ("routed half-adder", "glider-logic/ha_full.py",
     "ok = (sm == (A ^ B))", "ok = (sm == (A | B))"),
    ("half-adder per bit", "glider-logic/ha_adder.py",
     "got = val(out); want = a + b", "got = val(out); want = a + b + 1"),
    ("Carlini adder 6+5", "glider-logic/carlini_adder.py",
     "a_v + b_v == s_v)", "a_v + b_v == s_v + 1)"),
]
# Fetched data the nightly checks need, copied into the falsification sandbox if present.
DATA = ["glider-logic/carlini_adder.mc"]


def stats():
    sys.path.insert(0, os.path.join(ROOT, "cpu"))
    from asm import assemble
    import run_cpu
    from sap1 import SAP1
    from sap2 import SAP2
    s1 = SAP1(assemble(run_cpu.P1)[0]).c
    s2 = SAP2([0]).c
    return {
        "sap1_nand": len(s1.nands), "sap1_dff": len(s1.dffs),
        "sap2_nand": len(s2.nands), "sap2_dff": len(s2.dffs),
    }


def run_check(name, cwd, argv, root=ROOT, quiet=False):
    t0 = time.time()
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    p = subprocess.run([sys.executable, "-u"] + argv, cwd=os.path.join(root, cwd),
                       capture_output=True, text=True, env=env)
    dt = time.time() - t0
    if not quiet:
        tag = "PASS" if p.returncode == 0 else "FAIL"
        print(f"[{tag}] {name:26s} {dt:6.1f}s   ({cwd}/{' '.join(argv)})", flush=True)
        if p.returncode != 0:
            print("       " + "\n       ".join((p.stdout + p.stderr).strip().splitlines()[-15:]))
    return p.returncode, dt


def falsify(tiers):
    """Copy the repo, break one thing, and require the matching check to fail."""
    by_name = {c[0]: c for c in CHECKS}
    files = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"],
                           cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
    files += [f for f in DATA if os.path.exists(os.path.join(ROOT, f))]
    ok = True
    for name, path, old, new in MUTATIONS:
        if by_name[name][3] not in tiers:
            continue
        with tempfile.TemporaryDirectory() as tmp:
            for f in files:
                os.makedirs(os.path.dirname(os.path.join(tmp, f)), exist_ok=True)
                shutil.copy2(os.path.join(ROOT, f), os.path.join(tmp, f))
            src = open(os.path.join(tmp, path)).read()
            if src.count(old) != 1:
                print(f"[FAIL] {name}: mutation target not found exactly once in {path}")
                ok = False
                continue
            open(os.path.join(tmp, path), "w").write(src.replace(old, new))
            _, cwd, argv, _ = by_name[name]
            rc, dt = run_check(name, cwd, argv, root=tmp, quiet=True)
            caught = rc != 0
            ok &= caught
            print(f"[{'PASS' if caught else 'FAIL'}] {name:26s} broken {path}: exit {rc} "
                  f"({'caught' if caught else 'NOT CAUGHT'}, {dt:.1f}s)", flush=True)
    return ok


def main(argv):
    if "--stats" in argv:
        for k, v in stats().items():
            print(f"{k} {v}")
        return 0
    tiers = {"fast"} | ({"nightly"} if "--nightly" in argv else set())
    if "--falsify" in argv:
        ok = falsify(tiers)
        print("ALL MUTATIONS CAUGHT" if ok else "SOME MUTATIONS NOT CAUGHT")
        return 0 if ok else 1
    if not ({"--fast", "--nightly"} & set(argv)):
        print(__doc__)
        return 2
    fails = []
    t0 = time.time()
    for name, cwd, args, tier in CHECKS:
        if tier in tiers:
            rc, _ = run_check(name, cwd, args)
            if rc != 0:
                fails.append(name)
    print(f"\n{'ALL PASS' if not fails else 'FAILED: ' + ', '.join(fails)}"
          f"  ({time.time() - t0:.0f}s)")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
