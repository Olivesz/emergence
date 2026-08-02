# How a brainless slime mold moves and "thinks"

Deep-dive research notes on *Physarum polycephalum* — the organism behind Act VI —
focused on the question that matters for the simulation: **what makes it move one way
and not another, deterministically, with no brain?**

---

## 0. What it actually is

*Physarum polycephalum* in its plasmodial stage is a **single cell** — one continuous
bag of cytoplasm containing **millions of nuclei** (a syncytium), with no membranes
dividing it and no nervous system of any kind. It can span from microns to, in the
lab, square *meters*. Everything below is done by one cell with no neurons, no
central controller, and no global plan. The "computation" is physics and chemistry
distributed across the whole body.

---

## 1. The motor: how it physically moves

The body is a network of **tubes (veins)** whose walls are lined with a gel of
**actin and myosin** — the same contractile proteins as our muscles.

- **Shuttle streaming.** The cytoplasm (endoplasm) doesn't flow one way; it sloshes
  **back and forth** through the tubes with a rhythmic period of roughly **1–3 minutes**,
  reversing direction each half-cycle. This is *shuttle streaming*, and it's the
  fastest cytoplasmic streaming known in any organism.
- **Peristalsis, not a pump.** Contraction is a **wave of cross-sectional squeezing**
  travelling along a tube (peristalsis), driven by actomyosin contraction–relaxation
  cycles of the tube walls. There is no heart; the whole network peristalses.
- **The calcium oscillator.** The rhythm is set by a **Ca²⁺ oscillator**: a
  phosphorylation/dephosphorylation cycle of myosin light-chain kinase, made bistable
  and pushed into relaxation oscillations by calcium exchange with internal vacuoles.
  A crucial twist: in Physarum, **calcium *inhibits* contraction**, so the calcium
  wave runs about **180° out of phase** with the mechanical tension. Chemistry
  oscillates; tension oscillates half a beat behind it.
- **How that becomes locomotion.** A local biochemical cue **softens the actin cortex**
  at one spot. Softer wall → lower resistance → the oscillating cytoplasm preferentially
  **flows *into* that region** on each stroke → net forward advance of the front there.
  Movement is the organism biasing where its own sloshing dumps mass. Top speed is
  only about **1 cm/hour**, but it never stops rearranging.
- **Tubes thicken with use.** A tube carrying more flow **grows wider**; a tube
  carrying little flow **shrinks and is reabsorbed**. This single physical fact —
  *flux widens the pipe* — is the seed of all its problem-solving (§3).

> **The one-line motor:** rhythmic actomyosin contraction sloshes cytoplasm through
> tubes; wherever the wall softens, cytoplasm piles in and the body advances there;
> tubes that carry flow fatten, tubes that don't wither.

---

## 2. The decision rule: what makes it go one way vs. another

This is the deep part. The direction it "chooses" is governed by its **oscillators**,
not by any sensor reading a map.

- **It climbs a gradient of its own oscillation frequency.** The plasmodium migrates
  **toward regions that make it oscillate faster, and away from regions that slow it
  down.** Attractants (food, warmth, moderate humidity) speed the local rhythm;
  repellents (light, salt, quinine) slow it. The organism is, in effect, a field of
  clocks that flows toward wherever the clocks tick fastest.
- **Attraction vs. repulsion is a matter of *phase*, and can be inverted.** In a
  striking experiment, an *attractant* (warmth) applied so that it oscillated *slower*
  than the body's own rhythm caused the mold to **flee** it; a *repellent* (cold)
  oscillated *faster* **attracted** it. Whether a stimulus pulls or pushes depends on
  the **phase relationship** between the stimulus and the internal clock — not on the
  stimulus's identity. The "meaning" of a signal is relational.
- **Coupled oscillators = a distributed computer.** Neighbouring contractile regions
  **entrain** one another (like metronomes on a shared table syncing up). Information
  — "food is that way" — propagates as **phase shifts** rippling across the coupled
  oscillator field. There is no signal wire and no address; the body integrates all
  local votes into one coherent direction of advance through physics alone. This is
  how a cell with no neurons does something that *looks* like deliberation.
- **Chemotaxis on top.** Overlaid on the oscillator dynamics is straightforward
  chemotaxis: it senses attractant/repellent concentrations at its advancing fronts
  and biases growth accordingly. Both stories are the same mechanism viewed at
  different scales — chemicals set local oscillation frequency; frequency sets flow.

> **The one-line decision rule:** flow toward wherever you tick fastest — and because
> that "fastest" is computed by millions of coupled local clocks entraining each other,
> the whole body agrees on a direction without anyone deciding it.

---

## 3. The deterministic mathematics — two models

There are two famous, very different formalisations. Emergence uses one for the free
foraging modes and a deterministic stand-in for the maze; the real organism is best
captured by the first.

### 3a. The Tero flow-conductivity model — the *real* "Physarum solver"

Tero, Kobayashi & Nakagaki modelled the body as a **network of tubes carrying
Poiseuille (laminar pipe) flow**, borrowing the language of electrical circuits.

- Each edge *(i, j)* has a **conductivity** `D_ij = π·r_ij⁴ / (8ξ)` — thickness to the
  **fourth power** (Hagen–Poiseuille), so fat tubes conduct hugely better than thin ones.
- Flow through it: `Q_ij = (D_ij / L_ij)·(p_i − p_j)` (flux = conductivity × pressure
  drop / length) — i.e. **Ohm's law**.
- Pressures come from **Kirchhoff's current law** (flow in = flow out at every node),
  with a **source** (start food) injecting `+I₀` and a **sink** (end food) drawing
  `−I₀`. Solving that linear system = a Poisson equation on the graph.
- **The one adaptive rule:** `dD_ij/dt = f(|Q_ij|) − μ·D_ij`. Tubes carrying big flux
  **thicken**; a constant decay `μ` **starves** the rest. Positive feedback on flow.

From that single feedback loop, two behaviours **provably** emerge:

1. **Dead-end cutting** — tubes off the main route carry ~no flow, so they decay away.
2. **Shortest-path selection** — when several tubes connect start to end, the flux
   concentrates on the shortest (least resistance), which thickens; the longer
   competitors starve and vanish.

It has been **proven mathematically** (Bonifaci, Mehlhorn, Varma; Becchetti et al.)
that the discretised model converges to the true shortest path, with explicit
complexity bounds — a rare case of a *biological* dynamic that's a provably-correct
optimisation algorithm. This is why people say the slime mold "computes."

### 3b. The Jones multi-agent model — what Emergence Act VI actually runs

Jeff Jones (2010) showed you don't need the tube equations to get the *look* and much
of the behaviour — it emerges bottom-up from a swarm of trivial agents:

- The plasmodium = a population of **particle-agents**, each on a lattice cell with a
  position and a heading.
- A shared lattice holds a **chemoattractant/trail field** that **diffuses** and
  **evaporates** (a multiplicative decay each step).
- Each agent, each step: **sense** the trail at three points ahead (left / centre /
  right, offset by a *sensor angle*); **rotate** toward the strongest by a *rotation
  angle*; **move** forward one step; and **deposit** trail **only on a successful move**.
- Food sources emit strong attractant.

Reinforced routes attract more agents → more deposition → more attraction; unused
routes evaporate. The macroscopic transport network — including near-optimal,
self-pruning veins — is a pure **emergent** consequence of those microscopic rules.
**This is exactly the model behind Act VI's "Connect the cities" and "Free veins"**:
sensor angle, rotation angle, deposit-on-move, and trail decay are all present.

### 3c. Why the maze uses a deterministic solver instead

In Act VI's **"Solve a maze"**, we do *not* use the agent swarm — a swarm flood
evaporates and never guarantees the start reaches the end. Instead we grow a front
**breadth-first from the start** and, the instant it reaches the end, read the
**shortest path** straight off the distance field. It's a deterministic stand-in that
is *guaranteed* to solve, and it mirrors the organism's real outcome (explore all
corridors, then keep only the connecting tube) even though the mechanism is BFS rather
than tube-flow. Honest labelling: the agent model *simulates the organism*; the maze
mode *reproduces its result*.

---

## 4. The higher tricks — memory, anticipation, learning (all brainless)

- **Externalised spatial memory.** Physarum lays down a translucent **extracellular
  slime** wherever it has been, and it **avoids its own slime**. That trail is an
  *external* memory: it doesn't remember internally where it's been — it *reads the
  environment* it has marked, and so avoids re-exploring dead ends. Deprived of the
  ability to sense its own trail, it gets dramatically worse at navigating U-shaped
  traps. Cognition, offloaded into the world.
- **Anticipation.** Exposed to a stressor on a **regular time interval**, it begins to
  **slow down in anticipation** of the next hit *before it arrives* — and resumes when
  the pattern stops. Timing, with no clock organ beyond its own oscillators.
- **Habituation.** Made to cross a bridge laced with a harmless irritant (quinine,
  caffeine), it is initially repelled, then **learns to ignore it** — the textbook
  definition of habituation, the simplest form of learning — and this learned state
  can even be **transferred by fusing** a habituated mold with a naïve one.
- **Network design that rivals engineers.** Given oat flakes placed like the cities
  around Tokyo, it grew a tube network **comparable to the real Tokyo rail system** in
  efficiency, fault-tolerance, and cost (Tero et al., *Science*, 2010) — balancing
  total length against robustness the way a human transit planner does.
- **Balanced diet & irrational-seeming choices.** It navigates nutrient trade-offs to
  reach an optimal protein-to-carbohydrate blend, and shows decision effects
  (context-dependent preferences) once thought to require a brain.

---

## 5. The through-line for *Emergence*

Physarum is the project's thesis in its purest form: **intelligence with no
intelligence inside.** No neuron, no plan, no map held anywhere — just

> local rule (soften where you tick faster) → physical consequence (cytoplasm flows
> in, tubes carrying flow thicken, the rest starve) → global outcome (shortest paths,
> Steiner-like networks, maze solutions, the Tokyo subway).

The same three-line skeleton — *sense locally, reinforce what's used, decay the rest* —
is Langton's ant, ant-colony pheromone trails, and neural pruning, wearing a costume
of yellow goo. That's why it belongs beside the ant, the cells, and the sandpile.

---

## Sources

- [Model of the Ca²⁺ oscillator for shuttle streaming in Physarum (PubMed)](https://pubmed.ncbi.nlm.nih.gov/1532135/)
- [Random network peristalsis in Physarum organizes fluid flows across an individual (PNAS)](https://www.pnas.org/doi/10.1073/pnas.1305049110)
- [A lumped-parameter model of endoplasm flow explains migration and polarization (PLOS ONE / PMC)](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6478327/)
- [Periodic traction in migrating large amoeba of Physarum (J. R. Soc. Interface)](https://royalsocietypublishing.org/rsif/article/12/106/20150099/35597/Periodic-traction-in-migrating-large-amoeba-of)
- [Brainless but Multi-Headed: Decision Making by the Acellular Slime Mould (J. Mol. Biol.)](https://www.sciencedirect.com/science/article/abs/pii/S0022283615003873)
- [Thermotaxis in a slime mold, Physarum polycephalum (oscillation-frequency gradient)](https://www.sciencedirect.com/science/article/abs/pii/S0091677375906720)
- [Physarum solver: a biologically inspired method of road-network navigation (Tero et al.)](https://www.sciencedirect.com/science/article/abs/pii/S0378437106000963)
- [Physarum Can Compute Shortest Paths — convergence proofs (Bonifaci & Mehlhorn)](https://www.iasi.cnr.it/~vbonifaci/pub/physarum-jtb.pdf)
- [Convergence Properties for the Physarum Solver (arXiv)](https://arxiv.org/pdf/1101.5249)
- [Emergence of Self-Organized Amoeboid Movement in a Multi-Agent Approximation of Physarum (Jones, arXiv)](https://arxiv.org/pdf/1212.0023)
- [Physarum-inspired Network Optimization: A Review (arXiv)](https://arxiv.org/pdf/1712.02910)
- [Slime mold uses an externalized spatial "memory" to navigate complex environments (PNAS)](https://www.pnas.org/doi/10.1073/pnas.1215037109)
- [Thoughts from the forest floor: a review of cognition in the slime mould Physarum (Animal Cognition)](https://link.springer.com/article/10.1007/s10071-023-01782-1)
