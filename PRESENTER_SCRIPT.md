# HeatGrid – Presenter Script (8 minutes max)

**Plan:** Slides 1–5 → Live demo (slide 6) → Slides 7–10
**Speak slowly. Bold = say it with emphasis. [Brackets] = action, don't read aloud.**

| Part | Slides | Time | Ends by |
|---|---|---|---|
| Intro + problem | 1–3 | 1:45 | 1:45 |
| Design + setup | 4–5 | 1:30 | 3:15 |
| Live demo | 6 | 2:45 | 6:00 |
| Results + conclusion | 7–10 | 2:00 | 8:00 |

---

## Before you start (off camera)

```bash
conda activate heatgrid
cd "heatgrid/MPI Heat Implementation"
python scripts/demo_server.py
```

1. Open **http://localhost:8000** and click the **Live demo** tab.
2. In the top card, change the grid to **1000 × 1000** (rows and cols). Leave the rest: single hotspot, 100 steps, 1 warm-up + 3 trials.
   *Why: at the default 500×500 the runs are so short (~0.07 s) that the numbers jump around. At 1000×1000 the blocking vs non-blocking gap shows up every time.*
3. Click **Run all three** once so everything is warm. Then refresh the page and set 1000 × 1000 again.
4. Open a terminal in `MPI Heat Implementation` next to the browser, with `conda activate heatgrid` already run, for Step 4.

---

## Slide 1 – Title (0:00–0:20)

> Hi, I'm Clarence Ebebe, student number 222086329. This is **HeatGrid**, my Deliverable 2 for Parallel Programming.
>
> It's an MPI heat simulation. I look at two things: **how you split the grid**, and **how the parts talk to each other**, and how both affect runtime on a normal 2-core laptop.

## Slide 2 – Problem and motivation (0:20–1:00)

> The problem is heat spreading across a 2D grid. Every cell updates from its **four neighbours** every step.
>
> When I split the grid across processes, the edges have to be swapped every step. These are called **halo swaps**, and that cost is what this study measures.
>
> It suits parallel computing because every step is the same simple update, with neighbours only talking locally.
>
> For South African relevance, the test scenarios mimic **Johannesburg heat patterns**: a heat island, hotspots and a gradient. These are **synthetic inputs, not real temperatures**, and it all runs on cheap hardware, no cluster. That links to **SDG 9.5**, building research capacity on low-cost hardware.

## Slide 3 – Research gap and questions (1:00–1:45)

> Most studies on this use **big clusters**. Very little looks at **1 to 4 processes on one small laptop**, which is what most students here actually have.
>
> So I ask two questions:
> - **RQ1:** When does a **2D grid split** beat a simple **1D strip split**?
> - **RQ2:** How much time does **non-blocking communication** save over **blocking**?
>
> My contribution is five implementations sharing one kernel, a reproducible benchmark pipeline, a measured answer to RQ2, and a reasoned limit on RQ1.

## Slide 4 – Design (1:45–2:30)

> [Point at the two diagrams] On the left is the **1D slab**: the grid is cut into horizontal strips, and each rank swaps rows above and below. On the right is the **2D Cartesian** split: a 2×2 grid, swapping rows **and** columns.
>
> All five versions use the **same update formula**. The sequential version doesn't use MPI at all, so any MPI overhead is visible.
>
> [Point at the 4 steps] The non-blocking version **starts sending the edges, updates the inside while the data travels**, then waits, then finishes the edges. That overlap is the whole idea.
>
> Timing only covers the step loop, and I take the **slowest rank**.

## Slide 5 – Setup (2:30–3:15)

> The results come from a **2-core Intel i5 laptop** with 8 GB of RAM. Python, NumPy, mpi4py and MPICH.
>
> I tested three grid sizes, at 1, 2 and 4 processes. Each config ran **5 trials plus a warm-up**, in shuffled order. That's **324 runs, zero failures**.
>
> Before every timed run, the result must match the sequential version, otherwise it doesn't count.
>
> One important note: **4 processes on 2 cores is oversubscribed**, so I flag those runs and don't use them as scaling evidence.

## Slide 6 – LIVE DEMO (3:15–6:00)

### What the live demo is (read this once so you understand it)

The **Live demo** tab is a web page in front of my real code. When you press a button, the page asks a small local server (`demo_server.py`) to run the **same commands you would type in a terminal**, like `python src/heat.py ...` or `mpiexec -n 2 python src/heat.py ...`. It then shows the **exact command**, the **raw output**, and a plain-English summary.

So nothing is pre-recorded or faked. Every number on screen comes from a run that just happened on this laptop.

**Run all three** runs the three steps in order and scrolls down the page as it goes:

| Step on screen | What actually runs | What it proves |
|---|---|---|
| **1 Correctness** | `python scripts/validate.py --procs 2 4` | The maths is right, and every MPI version gives the exact same answer as sequential |
| **2 Sequential and MPI execution** | sequential run, then `mpiexec -n 2 ... slab_nonblocking` | MPI works on a real input and checks itself |
| **3 A meaningful comparison** | `slab_blocking` vs `slab_nonblocking`, both on 2 processes | Changing only the communication style changes the runtime (RQ2) |

It takes about **10–15 seconds** in total. **Keep talking while it runs.**

**Step 4** (the pipeline) is not a button. You run it in the terminal.

---

### Running it: click and say

**Open (≈15 s)**
> Now the live demo. Quick note first: **this is an Apple M1, not the i5** from my results. So these numbers show that it works. They are **not** my performance evidence.
>
> This tab runs my actual programs on this laptop. For every step it shows the **exact command** and its **raw output**.

[Point at the input chips in the top card: **1000×1000, single hotspot, seed 2001, 100 steps, 1 warm-up + 3 trials**]

> Every run uses this same input: a 1000 by 1000 grid with one hotspot, 100 time steps, one warm-up and three timed trials.

[Click **Run all three**]

---

**Step 1 – Correctness (≈40 s)**

What you'll see: a green box, **"All correctness checks passed"**, and two tables.

[Point at the first table, "Accuracy against the exact solution"]
> First, is the maths right? I use a test case with a known exact answer. Each time I make the grid twice as fine, the error drops by **4.00**. That's **second-order accuracy**, which is exactly what this method should give.

[Point at the second table, "MPI result vs sequential result"]
> Second, does splitting the work change the answer? All four MPI versions, on 2 and 4 processes, give an error of **exactly zero** compared with sequential, bit for bit. That's on an odd 37 by 53 grid that doesn't split evenly, and the 4-process Cartesian run is a **real 2×2 split**.

---

**Step 2 – Sequential and MPI (≈40 s)**

What you'll see: two cards side by side, **Sequential** and **Slab non-blocking**, with the commands underneath.

[Point at the command] 
> Here's the command: `mpiexec -n 2`, so two processes.

[Point at the MPI card]
> The process grid is **2×1**, so the grid is cut into two strips. And the green box says **"MPI result identical to sequential"**. Every MPI run checks itself against sequential **before** timing anything. If it didn't match, the program would stop.

[Point at median runtime and halo exchange %]
> Only the time-step loop is timed, and I report the **slowest** process. This bar shows how much of the time went on halo exchange.

*Expected on the M1: sequential ≈ 0.44 s, MPI ≈ 0.36 s, speedup ≈ 1.2×, error 0.*

---

**Step 3 – A meaningful comparison (≈40 s)**

What you'll see: "What changes" set to **Communication mode (RQ2)**, a bar chart, and stat tiles.

> Now I change **only one thing**: how the processes swap their edges. Blocking waits for the data. Non-blocking keeps computing the inside of its block while the data travels.

[Point at the **Non-blocking vs blocking** tile and read the %]
> Non-blocking took about **[read %] less time**.

[Point at the **Halo exchange share** tile]
> And the time spent on halo exchange dropped from about **18% to 11%**. The overlap hides part of the communication.
>
> That's one run, so it's just a demonstration. My actual evidence is the full suite, where non-blocking won **all 18 pairs**.

*Expected on the M1: blocking ≈ 0.39–0.42 s, non-blocking ≈ 0.35–0.37 s (about 10–12% faster); halo share ≈ 18% → 11%.*

[Optional, only if you're ahead of time] Switch "What changes" to **Decomposition (RQ1)**, set processes to **4**, and run.
> With 4 processes we get the first real **2×2** split. With only 2 processes, slab and Cartesian are the same 2×1 split, which is why RQ1 needs 4 or more.

---

**Step 4 – Results pipeline (≈45 s)**

[Switch to the terminal and run these one at a time]
```bash
head -3 results/raw/full_20261006-223528.csv
python scripts/summarise.py results/raw/full_20261006-223528.csv
python scripts/show_results.py
```

> [After `head`] This is the raw data from my full experiment. One row per trial, with the variant, process count, grid, runtime, communication time and error.
>
> [After `summarise`] This turns the **324 raw runs** into medians and speedups.
>
> [After `show_results`] And this prints the final results that are on my next slides. Nothing gets re-run, so anyone can rebuild my results from the recorded data.

[Switch back to slides]

## Slide 7 – Results: correctness and speedup (6:00–6:30)

> Three numbers:
> - **0.0** error versus sequential across all 54 configurations.
> - **1.01x** best speedup on 2 ranks. That's basically no speedup, and the reason is that the stencil is **limited by memory bandwidth**, and both cores share that bandwidth.
> - **18 out of 18**: non-blocking beat blocking in every pair.

## Slide 8 – Discussion: RQ2 and RQ1 (6:30–7:15)

> **RQ2:** Non-blocking was **17 to 65% faster** on 2 ranks, and faster in all 18 pairs.
> One surprise: at the largest grid, the saving was **bigger than the communication time itself**. So blocking also costs time outside the send, probably ranks waiting on each other. I didn't test that directly.
>
> **RQ1:** At 2 ranks, both splits are **the same 2×1 split**, so there's nothing to compare. A real 2×2 needs 4 ranks, which is oversubscribed here. So **RQ1 can't be answered on this hardware**.

## Slide 9 – Conclusion (7:15–7:50)

> To sum up: **RQ1 is not answerable on 2 cores. RQ2: overlap cut the runtime in every case.** On a small machine, **how you communicate matters more than how you split the grid**.
>
> Limits: one 2-core machine, oversubscribed 4-rank runs, a NumPy kernel, and synthetic data.
>
> Next steps: rerun on **8 or more cores** to properly test RQ1, use a **compiled kernel**, and eventually use **real Johannesburg data**.

## Slide 10 – References (7:50–8:00)

> These are my references. AI assistance was used as declared in my AI-use statement. Thank you.

---

### If you're running late
- Skip the optional 2×2 switch in the demo.
- In Step 4, run only `show_results.py`.
- On Slide 5, skip the software list.

### If something breaks in the demo
- Server down → use the terminal: `python scripts/validate.py`, then the `src/heat.py` commands in `DEMO.md`.
- Say: *"The recorded results in the repo are what the findings are based on."* and move on.
