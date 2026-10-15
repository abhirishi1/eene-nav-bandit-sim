# Overview

[Home](README.md) · **Overview** · [Architecture](architecture.md) · [Data flows](data-flows.md) ·
[Algorithms](algorithms.md) · [Usage](usage.md)

## What this project is

The EENE Navigation Bandit Simulator is a Python simulation framework that replicates the results of the following
[paper](https://openreview.net/forum?id=ndw90pkNM9):

> Niklas Åkerblom & Morteza Haghir Chehreghani (2023). A Combinatorial Semi-Bandit Approach to Charging Station
> Selection for Electric Vehicles. *Transactions on Machine Learning Research (TMLR)*.

The code is copyright 2023 Volvo Car Corporation and licensed under Apache 2.0. The work was funded by the Strategic
Vehicle Research and Innovation Programme (FFI) of Sweden through the project
[EENE](https://www.vinnova.se/en/p/eene-energy-effective-navigation-for-evs) (Energy Effective Navigation for EVs,
reference number 2018-01937). The root [`README.md`](../README.md) has the BibTeX entry to cite.

## The problem being simulated

An electric vehicle has to drive a long trip from a start location to an end location, and its battery is too small
to make the trip in one go. It has to stop at one or more charging stations on the way. Each candidate route is a
sequence of charging stations, and the cost of a route is its **total trip time**:

- **driving time** between stations (known in advance, from the road network),
- **queue time** at each visited station (random, and its average is unknown), and
- **charging time** at each visited station (random, because the power a station actually delivers is random and its
  distribution is unknown).

The vehicle makes the same trip again and again (one trip per *iteration*). After each trip it observes the queue and
charging times at the stations it actually visited, and it uses those observations to choose better stations next
time. This is a **combinatorial semi-bandit** problem:

- *combinatorial*, because an action is a whole route (a path through several stations), not a single choice, and
- *semi-bandit*, because feedback is observed separately for every station on the chosen route, not just as one total.

## The four exploration strategies compared

All four strategies keep a Bayesian posterior over each station's queue-time and charging-power distributions, and all
four choose a route by running a shortest-path search over a graph whose weights are estimated travel, queue and
charge times. They differ only in **which estimate** of each station they plug into that search (details in
[Algorithms](algorithms.md)):

| Strategy | Class | Estimate used for each station |
|:---------|:------|:-------------------------------|
| Greedy | `GreedyNavigationBanditAlgorithm` | Posterior mode (MAP) estimate, always (Epsilon-Greedy with epsilon fixed at 0) |
| Epsilon-Greedy | `EpsilonGreedyNavigationBanditAlgorithm` | With probability epsilon a random route, otherwise the MAP route; `sim_runner.py` uses epsilon = 1/sqrt(t) |
| Thompson Sampling | `ThompsonSamplingNavigationBanditAlgorithm` | A random sample drawn from the posterior |
| BayesUCB | `BayesUcbNavigationBanditAlgorithm` | An optimistic posterior quantile at level 1 - 1/(t+1) |

All four classes are in `eene-nav-bandit-sim/navigation/alg_impl.py`.

## How the strategies are evaluated: regret

The simulated environment knows the true parameters of every station, so it can compute the **optimal route** (the
one with the lowest expected trip time). In each iteration the simulator records the **instant regret** of the route
the strategy chose:

instant regret = expected trip time of the chosen route − expected trip time of the optimal route

(in the code this is computed as `optimal_expected_reward - action_expected_reward`, where a reward is the negative
expected trip time). With the README's units (times in seconds), regret is extra trip seconds. Summing instant regret
over iterations gives the **cumulative regret**. A good strategy has cumulative regret that flattens out quickly,
meaning it has stopped picking poor routes.

The simulator runs every strategy several times (`--number-of-experiment-runs`, default 5) for a fixed number of
iterations (`--experiment-horizon`, default 100), and writes:

- `results.csv`, with instant and cumulative regret per run, strategy and iteration, and
- `regret_plot.png`, the mean cumulative regret per strategy with a ±1 standard deviation band.

## Input data

The repository ships no input data. You provide two CSV files: a road network graph (one directed edge per row, with
mean energy consumption in joules and mean travel time in seconds) and a list of charging stations (with power in
watts). The paper used [OpenStreetMap](https://www.openstreetmap.org/) and [Open Charge Map](https://openchargemap.org/).
The column formats are in [Usage](usage.md#input-files).

## Where to go next

- [Architecture](architecture.md): how the code is organised.
- [Data flows](data-flows.md): what happens, step by step, when you run it.
- [Algorithms](algorithms.md): the maths of each strategy.
- [Usage](usage.md): how to run it.
