# Emergence

**A living cellular-automata universe — one engine, several acts, built to inspire awe.**

Two rules you could write on a napkin produce unfathomable complexity. This is an
interactive, single-file web toy that makes that *visible* — cinematic, glowing,
and playable in the browser with no build step and no dependencies.

> The whole point: maximize the gap between the **triviality of the rule** and the
> **apparent sophistication of the result** — and make that gap legible. Show the
> rule, then show the miracle.

## The acts

| Act | System | The "wow" |
|-----|--------|-----------|
| **I — The Turmites** | Langton's Ant & generalized turmites | ~10,000 steps of chaos, then a self-built periodic *highway* appears from nowhere. An editable rule string makes it an infinite explorer (`RL`, `RLR`, `LLRR`, …), and **multiple ants** share one grid — their highways collide and interfere. |
| **II — The Living Field** | Conway's Game of Life | Cells that breathe. Age-colored (newborn cyan → ancient magenta). R-pentomino, Gosper glider gun, pulsar, or paint your own. |
| **III — The Grazers** | Hybrid (the novel one) | Ants roaming a *living* Conway field. Each ant reads the **same alive/dead bit** Conway reads and turns on it — the two automata provably reading the same state. |
| **IV — Chemical Garden** | Gray–Scott reaction–diffusion | Two virtual chemicals feed, react, and diffuse. A field of near-uniform noise **self-organizes into coral, cell mitosis, and fingerprints** — Turing's morphogenesis, live. Drag to inject reagent. |
| **V — The Creatures** | Lenia (continuous CA) | Conway's Life made **continuous** — real-valued cells, a smooth ring kernel, a bell-curve growth function. An ecosystem of glowing organisms **self-assembles out of random static** and swims, morphs, and divides. Runs on its own coarse grid (kernel convolution is costly), rendered scaled up. Drag to breathe life into the void. |

## Why the thesis holds in the code

Langton's Ant and Conway's Life look like different species — a moving read/write
head vs. a global field update. But they are both cellular automata, and in **Act
III** the connection is literal: the ant's turn rule is

```js
ant.dir += alive ? 1 : 3;   // turn right on a live cell, left on a dead one
```

…which *is* Langton's "turn right on one color, left on the other" — except the
"color" is Conway's life-state. The moving-head automaton and the field automaton
are reading the same bit.

## Run it

It's a single self-contained HTML file. Any of:

```bash
open index.html
# or serve it
python3 -m http.server 8000   # then visit http://localhost:8000
```

No build, no dependencies, no network — all CSS/JS is inline and the visuals are
pure `<canvas>`.

## A world bigger than the screen

The simulation runs on a world roughly **2× the viewport in each dimension**, so
there's more universe off-screen than you can see at once. A camera lets you roam it:

- **Scroll / pinch** to zoom toward the cursor; **drag** to pan.
- Zoom cluster (bottom-left): `−` / `+`, **⤢ Fit** (`F`) to frame the whole world, and a **✋ Pan / ✎ Paint** toggle.
- Keys: `F` fit, `+` / `−` zoom, arrow keys pan.
- Rendering uses an **offscreen "world" canvas** drawn once per frame at native
  resolution, then blitted to the screen through a single camera transform — so the
  five simulations never need to know the camera exists.

## Controls

- **Acts** — switch live with the tabs, or press `1`–`5`.
- **Transport** — Play/Pause (`space`), Step, Reset, Speed.
- **Act I** — editable turmite `Rule` string; **⏭ to highway** fast-forwards to the brink; up to 8 interacting ants.
- **Act II** — seed presets, or switch to **✎ Paint** and drag to paint life.
- **Act III** — ant count, Life tempo, and `plant` vs `toggle` coupling.
- **Acts IV–V** — presets, or **✎ Paint** to inject reagent / breathe in life.

## Architecture

One engine, shared grid buffers (`state`, `age`, `heat` typed arrays); only the
`step*()` and `seed*()` functions differ per act. Rendering is `<canvas>` with a
cheap **bloom** post-process (downscale → blur → additive composite) that turns
colored squares into glowing energy.

The heart of the hybrid is a single function, `coupling()`, deliberately isolated
so its rule can be redesigned — that one function defines the entire character of
Act III.

## Roadmap

Emergence is *rule-dependent*: change the rule, change the miracle. The aliveness ladder
climbs from mechanical (the ant) → organic (chemistry that grows) → genuinely alive (Lenia).
Next rungs:

- **A named Lenia bestiary** — hand-placed orbium / creatures with known seeds, so you can watch a single organism swim across an empty field.
- **True turmites** — an ant with internal states → spiral and fractal builders far beyond `RL`.
- **Hexagonal / triangular lattices** — the ant on other grids, with new symmetries.
- **Reaction–diffusion parameter sweep** — a continuous (feed, kill) map to roam the whole Pearson zoo.
- **Lenia parameter dials** — live μ / σ / kernel controls to discover new life-forms.

## License

MIT — see [LICENSE](LICENSE).
