#!/usr/bin/env python3
"""The browser engines (wwcpu.js, wwcpu2.js) must match the Python netlists.

Each SAP-1 and SAP-2 program is run on both sides and compared clock by clock:
every register, the flags, the bus and the halt line at every cycle, plus the
assembled memory image. Runs under Node, or under macOS's JavaScriptCore shell
when Node is absent. With no JavaScript runtime at all it FAILS rather than
skipping.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from asm import assemble
from asm2 import assemble as assemble2
import run_cpu
import run_sap2
from sap1 import SAP1
from sap2 import SAP2

JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc"
SAP1_PROGS = [("5+3", run_cpu.P1), ("9-4", run_cpu.P2), ("countdown", run_cpu.P3),
              ("sum", run_cpu.P4), ("fibonacci", run_cpu.P5)]
SAP2_PROGS = [("multiply", run_sap2.MUL), ("divide", run_sap2.DIV), ("gcd", run_sap2.GCD),
              ("fibonacci", run_sap2.FIB), ("primes", run_sap2.PRIMES), ("sort", run_sap2.SORT)]
K1 = ["T", "PC", "MAR", "IR", "A", "B", "OUT", "C", "bus", "halt"]
K2 = ["T", "PC", "MAR", "IR", "A", "B", "MDR", "SP", "OUT", "Z", "C", "S", "bus", "halt"]


def py_trace(cpu, keys, max_cycles):
    rows = []
    for _ in range(max_cycles):
        s = cpu.snapshot()
        rows.append([s[k] for k in keys])
        if s["halt"]:
            break
        if hasattr(cpu, "step"):
            cpu.step()
        else:
            cpu.c.tick()
    return rows


def expected():
    out = {"sap1": [], "sap2": []}
    for name, src in SAP1_PROGS:
        img, _ = assemble(src)
        out["sap1"].append(dict(name=name, src=src, image=img,
                                trace=py_trace(SAP1(img), K1, 3000)))
    for name, src in SAP2_PROGS:
        img, _ = assemble2(src)
        out["sap2"].append(dict(name=name, src=src, image=img,
                                trace=py_trace(SAP2(img), K2, 200000)))
    return out


HARNESS = r"""
var say = (typeof console !== "undefined" && console.log) ? function (s) { console.log(s); } : print;
function trace(cpu, keys, max) {
  var rows = [];
  for (var i = 0; i < max; i++) {
    var s = cpu.snapshot();
    rows.push(keys.map(function (k) { return s[k]; }));
    if (s.halt) break;
    cpu.step();
  }
  return rows;
}
var result = { sap1: [], sap2: [] };
INPUT.sap1.forEach(function (p) {
  var img = E1.assemble(p.src).image;
  result.sap1.push({ name: p.name, image: img, trace: trace(new E1.SAP1(img), K1, 3000) });
});
INPUT.sap2.forEach(function (p) {
  var img = E2.assemble2(p.src).image;
  result.sap2.push({ name: p.name, image: img, trace: trace(new E2.SAP2(img), K2, 200000) });
});
say(JSON.stringify(result));
"""


def wrap(engine_src, names):
    # Each engine is a script that defines globals; scope it so the two can coexist.
    body = "\n".join(l for l in engine_src.split("\n") if "module.exports" not in l)
    return "(function () {\n" + body + "\nreturn {" + ", ".join(f"{n}: {n}" for n in names) + "};\n})()"


def runtime():
    node = shutil.which("node")
    if node:
        return [node]
    if os.path.exists(JSC):
        return [JSC]
    return None


def main():
    rt = runtime()
    if rt is None:
        print("  [FAIL] no JavaScript runtime (need node, or macOS jsc)")
        return 1
    want = expected()
    src = ("var INPUT = " + json.dumps({k: [dict(name=p["name"], src=p["src"]) for p in v]
                                        for k, v in want.items()}) + ";\n"
           + f"var K1 = {json.dumps(K1)}; var K2 = {json.dumps(K2)};\n"
           + "var E1 = " + wrap(open(os.path.join(HERE, "wwcpu.js")).read(), ["SAP1", "assemble"]) + ";\n"
           + "var E2 = " + wrap(open(os.path.join(HERE, "wwcpu2.js")).read(), ["SAP2", "assemble2"]) + ";\n"
           + HARNESS)
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
        f.write(src)
        path = f.name
    try:
        proc = subprocess.run(rt + [path], capture_output=True, text=True)
    finally:
        os.unlink(path)
    if proc.returncode != 0:
        print(proc.stderr[-2000:])
        print("  [FAIL] JavaScript harness crashed")
        return 1
    got = json.loads(proc.stdout.strip().splitlines()[-1])
    ok = True
    for machine in ("sap1", "sap2"):
        for w, g in zip(want[machine], got[machine]):
            # booleans/ints differ in representation only
            gt = [[int(x) for x in row] for row in g["trace"]]
            wt = [[int(x) for x in row] for row in w["trace"]]
            same_img = list(g["image"])[:len(w["image"])] == list(w["image"]) and \
                not any(list(g["image"])[len(w["image"]):])
            same = same_img and gt == wt
            first = next((i for i, (a, b) in enumerate(zip(wt, gt)) if a != b), None)
            note = "" if same else (f" (image differs)" if not same_img else
                                    f" (first divergence at cycle {first if first is not None else min(len(wt), len(gt))})")
            print(f"  [{'PASS' if same else 'FAIL'}] {machine} {w['name']}: "
                  f"{len(wt)} cycles identical{note}")
            ok &= same
    print("ALL PASS" if ok else "SOME FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
