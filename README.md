# Emergence

**A living cellular-automata universe — one engine, seven acts, built to inspire awe.**

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
| **VI — The Slime Mold** | Physarum agent model | The brainless yellow slime mold *Physarum polycephalum* — which famously reproduced the Tokyo rail network and solves mazes. Thousands of particle-agents each sniff a chemical trail at three points ahead, steer toward the strongest, move, and deposit; the trail diffuses and evaporates. **Reinforced routes survive, dead ends fade** — the emergent network *is* the solution. "Connect the cities" and "Free veins" run the agent model; **"Solve a maze"** grows the organism outward from a single **start** life-point through a huge world-filling labyrinth and, the instant it reaches the **end**, reveals the shortest connecting path (deterministic breadth-first — always the true shortest route); **"Flow physics"** runs the *actual organism physics* — the **Tero flow-conductivity model** on a braided maze: current is injected at the start and drained at the end (Kirchhoff), flux follows Poiseuille's law through each tube, and every tube adapts `D += δ·(\|Q\|^μ − D)` (μ≈1.8, superlinear) so tubes carrying flux **thicken** and the rest **starve** — the faithful model from [robert-30/physarum-maze](https://github.com/robert-30/physarum-maze): each *maze cell* is a graph node (~200 nodes), the Kirchhoff pressure system is solved with a current source each iteration. It **forages**: the slime starts at the source **only** (no prior knowledge of the maze), grows its frontier outward exploring the corridors, **peels dead-ends as it goes** (a tip that can't advance retracts and is never re-explored), and the instant its frontier reaches the goal it stops exploring and the flux concentrates — `D += δ·(\|Q\|^μ − D)`, μ≈1.8 — onto the shortest connecting tube while the rest starve. Rendered as **thick glowing veins** (width ∝ conductivity) over the maze: a dim network shows where it explored, a bright thick tube is the solution. **"Smart solve"** is the *efficient* counterpart — **bidirectional A\***: two frontiers grow from the two foods, each guided toward the other by `f = cost-so-far + straight-line-distance`, meeting in the middle. On a hard, heavily-braided maze with **random, non-corner endpoints** (so the solution isn't a diagonal) it finds the shortest path exploring only ~10% of the cells — the live **Explored** readout shows the cost. The solvers run in **slow-motion** (speed slider) so you can watch the frontiers explore. Note the theory: **"Smart solve"** assumes you *know* the goal (heuristic → A\*); **"Solve a maze"** does *not* (uninformed) and so must expand its frontier uniformly by distance — the provably-optimal shortest-path search when the goal's location is unknown. The gap in *Explored* between them is exactly the value of knowing where you're going. **"No-map walk"** is the true *stuck-inside-with-no-map* solver — **Trémaux's algorithm**: one agent with only local sensing marks each passage as it walks it, never takes a twice-marked passage, and backtracks from dead-ends; it's guaranteed to escape *any* maze, and the passages walked once trace the solution. "Slime maze" is the pure agent-model companion. |
| **VII — The Sandpile** | Abelian sandpile (BTW) | Drop sand grains; any cell with 4 topples one to each neighbour, which can cascade. Dropping at one point grows the astonishing **self-similar sandpile-identity fractal**; raining grains randomly drives the pile to a critical state where **avalanche sizes follow a power law** — the same signature (self-organized criticality) as earthquakes, extinctions, and market crashes. One integer rule. |

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

The simulation runs on a world **several times wider than the viewport** (a fixed
cell budget caps total work, so the world grows *wider*, not denser), so there's far
more universe off-screen than you can see at once. A camera lets you roam it:

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
