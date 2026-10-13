#!/usr/bin/env python3
"""Record docs/acts.gif: each of index.html's eight acts, running, in headless
Chromium. Frames are screenshots of the real page; ffmpeg assembles the GIF.

    python3 tools/record_acts.py    (needs playwright + chromium, and ffmpeg)
"""
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "acts.gif"
W, H = 960, 540
WARM = {"1": 6000, "2": 2500, "3": 3000, "4": 6000, "5": 6000, "6": 5000, "7": 4000, "8": 3000}
FRAMES, STEP_MS = 18, 110


def main():
    tmp = pathlib.Path(tempfile.mkdtemp())
    n = 0
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
        page.goto((ROOT / "index.html").as_uri())
        page.wait_for_timeout(1500)
        page.click("#skipBtn")
        page.wait_for_timeout(800)
        assert page.evaluate("window.innerWidth") == W
        for key in "12345678":
            page.keyboard.press(key)
            if key == "8":
                page.click('#wireSeeds .seed[data-wire="ha"]')
            page.wait_for_timeout(WARM[key])
            sizes = []
            for _ in range(FRAMES):
                f = tmp / f"f{n:04d}.png"
                page.screenshot(path=str(f))
                sizes.append(f.stat().st_size)
                n += 1
                page.wait_for_timeout(STEP_MS)
            if min(sizes) < 20_000:
                sys.exit(f"act {key}: a frame is {min(sizes)} bytes — blank capture, not recording it")
        b.close()
    OUT.parent.mkdir(exist_ok=True)
    pal = tmp / "pal.png"
    vf = "fps=8,scale=640:-1:flags=lanczos"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-framerate", "8", "-i", str(tmp / "f%04d.png"),
                    "-vf", vf + ",palettegen=max_colors=96", str(pal)], check=True)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-framerate", "8", "-i", str(tmp / "f%04d.png"),
                    "-i", str(pal), "-lavfi", vf + " [x]; [x][1:v] paletteuse=dither=bayer:bayer_scale=4",
                    str(OUT)], check=True)
    shutil.rmtree(tmp)
    print(f"wrote {OUT.relative_to(ROOT)}: {n} frames, {OUT.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
