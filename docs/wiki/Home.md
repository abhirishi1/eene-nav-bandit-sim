# EENE Navigation Bandit Simulator: Wiki

This simulator is research code from Volvo Cars for the paper *"A Combinatorial Semi-Bandit Approach to Charging Station Selection for Electric Vehicles"* (Åkerblom & Haghir Chehreghani, TMLR 2023).
It studies how an electric car can **learn which charging stations to use on a long trip** when it doesn't know in advance how fast each charger really is or how long the queue will be.

The car makes the same trip many times. On each trip it picks a route with charging stops, sees how long everything actually took, and updates what it believes about the stations it used.
Four learning strategies are compared by their **regret**: the extra trip time their choices cost compared with an all-knowing planner.

## Pages

| Page | What it covers |
|------|----------------|
| [Architecture](Architecture.md) | The three code layers, the main classes and how they connect, and how the "charging graph" is built |
| [Data flow](Data-flow.md) | Step by step from your CSV files to `results.csv` and the regret chart, including what happens on each simulated trip |

## Folder map

```text
eene-nav-bandit-sim/                  repository root
├── README.md                         original usage guide (inputs, arguments, defaults)
├── requirements.txt                  pinned library versions
├── setup.py                          package metadata (does not list dependencies)
├── output/                           default output folder (only a PLACEHOLDER file in git)
├── docs/wiki/                        this wiki
└── eene-nav-bandit-sim/              all Python code; run the scripts from this folder
    ├── charging_graph_preprocesser.py    step 1: road map + stations -> travel tables
    ├── sim_runner.py                     step 2: run the 4 strategies -> results.csv + regret_plot.png
    ├── core/          generic "learn over repeated trials" building blocks
    ├── navigation/    the EV trip world and the 4 strategies
    ├── util/          road-graph data structure, probability maths, samplers
    └── tests/         12 pytest tests
```

## Quick start

From the inner `eene-nav-bandit-sim/` folder, using Python 3.9 (see [Python and libraries](#python-and-libraries)):

```bash
pip install -r ../requirements.txt
python -m pytest tests                     # 12 tests
python charging_graph_preprocesser.py --road-graph-csv-path ROAD.csv --charging-station-csv-path STATIONS.csv
python sim_runner.py --charging-station-csv-path STATIONS.csv --start-node-id START --end-node-id END
```

The repository ships no road or station data. You supply both as CSV files (formats in [Data flow](Data-flow.md)).

## Python and libraries

- **Python 3.9 only** on this code. On 3.10 to 3.12 the libraries install, but the code fails to start: `util/road_graph.py` uses `from collections import MutableMapping`, which Python 3.10 removed. On 3.13 the install fails, because SciPy 1.11 doesn't support it.
- Nothing enforces the version: `setup.py` has no `python_requires`, and there's no `.python-version` or lock file. The README's "developed using Python 3.9" is the only mention.
- The libraries are listed only in `requirements.txt` (with `~=` pins and no lock file):
  - **pandas** reads the CSVs and writes `results.csv`
  - **NetworkX** finds the fastest paths (step 1) and the best route (step 2)
  - **NumPy** holds and saves the travel tables and draws the random numbers
  - **SciPy** samples the charging-power beliefs and computes the BayesUCB quantiles
  - **Matplotlib** draws the regret chart
  - **pytest** runs the tests

## Key terms

| Term | Meaning in this code |
|------|----------------------|
| **Bandit problem** | Repeatedly choosing between options with uncertain payoffs, balancing *exploring* (trying less-known options) against *exploiting* (using what looks best) |
| **Action** | One route: the list of graph nodes driven through, plus the IDs of the charging stations stopped at |
| **Feedback** | The observed times from one trip: driving time per leg, plus queue time and charging time at each station used |
| **Iteration / horizon** | One trip / the number of trips per experiment (`--experiment-horizon`, default 100) |
| **Experiment run** | One full repeat of all four strategies with fresh random worlds (`--number-of-experiment-runs`, default 5) |
| **Prior / posterior** | What a strategy believes about a station before any visits / after updating with observed visits |
| **Regret** | Expected trip time of the chosen route minus that of the best route, in seconds. "Cumulative regret" is the running total over trips |

## Known issues

A list of 10 bugs with proposed fixes is in [`docs/BUG_REPORT.md`](https://github.com/abhirishi1/eene-nav-bandit-sim/blob/devin/1791560357-bug-report/docs/BUG_REPORT.md) (on its own branch). [Data flow](Data-flow.md#where-known-issues-occur) shows where each one occurs.
