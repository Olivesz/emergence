#!/usr/bin/env python3
"""Every count the repo's pages quote must equal the count computed from the
netlists (verify.py --stats). A page that drifts from the code fails here."""
import os
import re
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)
from verify import stats

# (file, regex with one group per stat, stat keys)
QUOTES = [
    ("cpu/README.md", r"\*\*([\d,]+) NAND gates \+ ([\d,]+) flip-flops\*\*", ["sap1_nand", "sap1_dff"]),
    ("cpu/README.md", r"NAND\+DFF \(([\d,]+) gates\)", ["sap2_nand"]),
    ("cpu/cpu.html", r"A CPU with ([\d,]+) NAND gates &amp; ([\d,]+) flip-flops", ["sap1_nand", "sap1_dff"]),
    ("cpu/cpu.html", r"it is ([\d,]+) NAND gates and ([\d,]+) D flip-flops", ["sap1_nand", "sap1_dff"]),
    ("cpu/cpu2.html", r"from ([\d,]+) NAND gates &amp; ([\d,]+) flip-flops", ["sap2_nand", "sap2_dff"]),
    ("cpu/cpu_shell.html", r"A CPU with ([\d,]+) NAND gates &amp; ([\d,]+) flip-flops", ["sap1_nand", "sap1_dff"]),
    ("cpu/cpu2_shell.html", r"from ([\d,]+) NAND gates &amp; ([\d,]+) flip-flops", ["sap2_nand", "sap2_dff"]),
    ("machine-explorer.html", r"The whole machine is ([\d,]+) NAND gates \+ ([\d,]+) flip-flops", ["sap1_nand", "sap1_dff"]),
    ("README.md", r"a \*\*D flip-flop\*\* — ([\d,]+) and ([\d,]+) of them", ["sap1_nand", "sap1_dff"]),
]


def main():
    st = stats()
    ok = True
    for path, rx, keys in QUOTES:
        text = open(os.path.join(ROOT, path)).read()
        m = re.search(rx, text)
        if not m:
            print(f"  [FAIL] {path}: quote not found: {rx}")
            ok = False
            continue
        for k, g in zip(keys, m.groups()):
            got = int(g.replace(",", ""))
            good = got == st[k]
            ok &= good
            print(f"  [{'PASS' if good else 'FAIL'}] {path}: {k} quoted {got}, computed {st[k]}")
    print("ALL PASS" if ok else "SOME FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
