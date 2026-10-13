#!/usr/bin/env python3
"""Build cpu.html and cpu2.html: each page is its shell with the engine inlined.

The engines (wwcpu.js, wwcpu2.js) end with a CommonJS export line so Node can
load them for the parity test; the browser pages drop that line.

    python3 build_pages.py          rewrite cpu.html and cpu2.html
    python3 build_pages.py --check  exit 1 if either committed page differs
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PAGES = [("cpu_shell.html", "wwcpu.js", "cpu.html"),
         ("cpu2_shell.html", "wwcpu2.js", "cpu2.html")]
MARK = "/* ENGINE_PLACEHOLDER */"


def build(shell, engine):
    s = open(os.path.join(HERE, shell)).read()
    if s.count(MARK) != 1:
        raise ValueError(f"{shell}: expected exactly one {MARK}")
    lines = open(os.path.join(HERE, engine)).read().split("\n")
    body = "\n".join(l for l in lines if "module.exports" not in l).rstrip() + "\n"
    return s.replace(MARK, body)


def main(argv):
    check = "--check" in argv
    ok = True
    for shell, engine, out in PAGES:
        page = build(shell, engine)
        path = os.path.join(HERE, out)
        if check:
            same = os.path.exists(path) and open(path).read() == page
            print(f"  [{'PASS' if same else 'FAIL'}] {out} == {shell} + {engine}")
            ok &= same
        else:
            open(path, "w").write(page)
            print(f"wrote {out}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
