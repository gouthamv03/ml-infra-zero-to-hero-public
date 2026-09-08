# Foundations

**Start here.** This step orients you to the series, the repo, and the system before any code is written.

---

## Setup checklist

Before opening any notebook, confirm you have everything installed:

| | Check |
|---|---|
| Python 3.9+ | `python3 --version` |
| Dependencies installed | `pip show fastembed` should return version info |
| VS Code + Jupyter extension | open a `.ipynb` — VS Code should render it as a notebook |

If anything is missing, follow the [setup instructions in the root README](../../../README.md#setup).

---

## What this series builds

A personalized Hacker News feed ranker — built from scratch, scaled to production ML infrastructure.

**Part 1 (this part)** covers the foundation: a working ranking system with no ML — candidate generators, then production storage backends.

The full system — a trained ranking model, training pipelines, feature stores, streaming, A/B testing, scaling, reliability — is built across Parts 2–8, each adding one production layer.

---

## What ML infrastructure actually is

Most ML courses stop at the model. Production ML is the system *around* the model:

| Domain | What it does |
|---|---|
| **Data** | Collect, store, and serve the signals the model reads |
| **Training** | Turn historical data into a model artifact, repeatably |
| **Serving** | Get the model's predictions to users with low latency |
| **Observability** | Know when any of the above is broken or drifting |

This series builds all four, in the order you'd reach for them in practice.

---

## Repo orientation

```
ml-infra-zero-to-hero/
  parts/
    part_1/             ← you are here
      00_foundations/   ← this folder
      01_simple_ranker/
      02_candidate_generators/
      03_storage/
  src/
    ranking_service/    ← the Python service all notebooks import from
  data/
    hn_stories_snapshot.jsonl   ← ~5K HN stories (committed for reproducibility)
  infra/
    docker-compose.yml  ← storage services (needed from the Storage step onward)
```

Each step folder has:
- `README.md` — what's built and why
- `notebook.ipynb` — the walkthrough; run cells top to bottom

---

## Confirm your environment

Open `notebook.ipynb` in this folder. It imports all key packages and prints version info. If every cell runs without errors, you're ready to move to the Simple Ranker step.
