# EENE Navigation Bandit Simulator: Documentation

This folder is the documentation wiki for the EENE Navigation Bandit Simulator, the code that reproduces
Åkerblom & Haghir Chehreghani (2023), *A Combinatorial Semi-Bandit Approach to Charging Station Selection for
Electric Vehicles* (TMLR).

All pages describe the code as it is in this repository. File paths are relative to the repository root, and the
Python source lives in the inner folder `eene-nav-bandit-sim/`.

## Pages

| Page | What it covers |
|:-----|:---------------|
| [Overview](overview.md) | What the project is, the paper it reproduces, the four exploration strategies and how they are compared with regret |
| [Architecture](architecture.md) | The two-phase pipeline and the three code layers (`core/`, `navigation/`, `util/`), with a component diagram |
| [Data flows](data-flows.md) | Phase 1 preprocessing and Phase 2 simulation step by step, seeds, outputs, and a sequence diagram of one iteration |
| [Algorithms](algorithms.md) | How Greedy, Epsilon-Greedy, Thompson Sampling and BayesUCB pick a route, and the Bayesian posterior updates behind them |
| [Usage](usage.md) | Installing, running both phases end to end, every command-line argument, and the output files |

## Suggested reading order

1. [Overview](overview.md) for the big picture.
2. [Usage](usage.md) to run the simulator.
3. [Architecture](architecture.md) and [Data flows](data-flows.md) to find your way around the code.
4. [Algorithms](algorithms.md) for the maths.
