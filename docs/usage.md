# Usage

[Home](README.md) · [Overview](overview.md) · [Architecture](architecture.md) · [Data flows](data-flows.md) ·
[Algorithms](algorithms.md) · **Usage**

## Requirements

The README states the project was developed with **Python 3.9**. Use 3.9: `eene-nav-bandit-sim/util/road_graph.py`
imports `MutableMapping` from `collections`, which Python 3.10 removed, so on 3.10+ every import of the package
fails. Dependencies are pinned in `requirements.txt` (NumPy, SciPy, NetworkX, pandas, Matplotlib, pytest):

```
python3.9 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

All commands below are run from the **inner** `eene-nav-bandit-sim/` folder. The scripts import modules as
`core.…`, `navigation.…` and `util.…`, and their default paths (`../output/…`) point at the repository's `output/`
folder relative to that inner folder.

```
cd eene-nav-bandit-sim
```

## Input files

No input data is included in the repository. You need two CSV files.

**Road graph CSV**: one row per **directed** edge (add both directions for a two-way road):

| from_id | from_y | from_x | to_id | to_y | to_x | mean_consumption | mean_time |
|---------|--------|--------|-------|------|------|------------------|-----------|
| ...     | ...    | ...    | ...   | ...  | ...  | ...              | ...       |

- `from_id`, `to_id`: string vertex IDs.
- `from_y`/`from_x`, `to_y`/`to_x`: float latitude/longitude of each vertex.
- `mean_consumption`: float mean energy use of the edge in **joules**.
- `mean_time`: float mean travel time of the edge in **seconds**.

**Charging station CSV**: one row per station:

| station_id | node_id | node_y | node_x | power |
|------------|---------|--------|--------|-------|
| ...        | ...     | ...    | ...    | ...   |

- `station_id`: distinct string ID.
- `node_id`, `node_y`, `node_x`: the closest road graph vertex and its float coordinates.
- `power`: float station power in **watts**.

The paper's sources were [OpenStreetMap](https://www.openstreetmap.org/) (road graph) and
[Open Charge Map](https://openchargemap.org/) (stations). The README notes that mean consumption can be computed with
Eq. 15 of the paper, and mean time from each edge's length and speed limit. The unit tests in
`eene-nav-bandit-sim/tests/utils_for_tests.py` show example station data and Phase 1 outputs.

## Phase 1: preprocessing (`charging_graph_preprocesser.py`)

```
python charging_graph_preprocesser.py --road-graph-csv-path [road graph CSV path] --charging-station-csv-path [charging station CSV path]
```

| Argument | Type | Default | Description |
|:---------|:----:|:-------:|:------------|
| `--road-graph-csv-path` | String | none | Road graph CSV path |
| `--charging-station-csv-path` | String | none | Charging station CSV path |
| `--output-dir` | String | `"../output/"` | Output directory (must end with `/`) |
| `--logging-level` | String | `"info"` | `"debug"`, `"info"`, `"warning"`, `"error"` or `"critical"` (anything else means `info`) |

It writes `complete_time_array.npy`, `complete_consumption_array.npy` and `charging_graph_ids.csv` to the output
directory (contents in [Data flows](data-flows.md#phase-1-preprocessing-charging_graph_preprocesserpy)). On a large
road graph with many stations this can take several hours.

## Phase 2: simulation (`sim_runner.py`)

Minimum command:

```
python sim_runner.py --charging-station-csv-path [charging station CSV path] --start-node-id [start vertex ID] --end-node-id [end vertex ID]
```

Use the **same** station CSV as in Phase 1. Defaults below are taken from the `argparse` definitions in `sim_runner.py`:

| Argument | Type | Default | Description |
|:---------|:----:|:-------:|:------------|
| `--charging-station-csv-path` | String | none | Charging station CSV path |
| `--start-node-id` | String | none | Start vertex ID (**must** be the `node_id` of a charging station) |
| `--end-node-id` | String | none | End vertex ID (**must** be the `node_id` of a charging station) |
| `--charging-graph-ids-csv-path` | String | `"../output/charging_graph_ids.csv"` | Phase 1 `charging_graph_ids.csv` |
| `--charging-consumption-npy-path` | String | `"../output/complete_consumption_array.npy"` | Phase 1 `complete_consumption_array.npy` |
| `--charging-time-npy-path` | String | `"../output/complete_time_array.npy"` | Phase 1 `complete_time_array.npy` |
| `--output-dir` | String | `"../output/"` | Output directory (must end with `/`) |
| `--number-of-experiment-runs` | Int | `5` | Runs per strategy |
| `--experiment-horizon` | Int | `100` | Iterations (trips) per run |
| `--start-seed` | Int | `0` | First random seed (see [seeds](data-flows.md#phase-2-simulation-sim_runnerpy)) |
| `--battery-capacity` | Float | `70.*1000.*3600.` = `252000000.0` | Battery capacity in **joules** (70 kWh) |
| `--min-power-factor` | Float | `0.5` | Minimum power of each station as a fraction of its `power` |
| `--power-scale` | Float | `300.0` | Scale factor of each station's power distribution |
| `--charge-prior-param-ln-p0` | Float | `13.5` | Charging power prior `ln_p0` (`log(pi_0)` in the paper) |
| `--charge-prior-param-q0` | Float | `300.0` | Charging power prior `q0` (`gamma_0` in the paper) |
| `--charge-prior-param-r0` | Float | `3.0` | Charging power prior `r0` (`xi_0` in the paper) |
| `--charge-prior-param-s0` | Float | `3.0` | Charging power prior `s0` (`xi_0` in the paper) |
| `--queue-prior-param-alpha0` | Float | `2.0` | Queue time prior `alpha0` (`alpha_0` in the paper) |
| `--queue-prior-param-beta0` | Float | `2400.0` | Queue time prior `beta0` (`beta_0` in the paper) |
| `--logging-level` | String | `"info"` | `"debug"`, `"info"`, `"warning"`, `"error"` or `"critical"` (anything else means `info`) |

The paper merges `r0` and `s0` into one parameter, `xi_0`. What the priors mean is explained in
[Algorithms](algorithms.md#the-simulated-world).

## End-to-end example

With the default output folder (the repository's `output/`):

```
cd eene-nav-bandit-sim
python charging_graph_preprocesser.py \
    --road-graph-csv-path /data/road_graph.csv \
    --charging-station-csv-path /data/charging_stations.csv
python sim_runner.py \
    --charging-station-csv-path /data/charging_stations.csv \
    --start-node-id J01 --end-node-id J19
```

With a separate output folder and a smaller battery and longer experiment:

```
cd eene-nav-bandit-sim
mkdir -p /tmp/eene-out
python charging_graph_preprocesser.py \
    --road-graph-csv-path /data/road_graph.csv \
    --charging-station-csv-path /data/charging_stations.csv \
    --output-dir /tmp/eene-out/
MPLBACKEND=Agg python sim_runner.py \
    --charging-station-csv-path /data/charging_stations.csv \
    --start-node-id J01 --end-node-id J19 \
    --charging-graph-ids-csv-path /tmp/eene-out/charging_graph_ids.csv \
    --charging-consumption-npy-path /tmp/eene-out/complete_consumption_array.npy \
    --charging-time-npy-path /tmp/eene-out/complete_time_array.npy \
    --output-dir /tmp/eene-out/ \
    --battery-capacity 54e6 --experiment-horizon 200 --number-of-experiment-runs 20
```

`J01`/`J19` are placeholders: use `node_id`s from your station CSV. `MPLBACKEND=Agg` lets Matplotlib save the plot on
a machine without a display.

## Output folder and artifacts

The repository has an `output/` folder containing only `PLACEHOLDER`; `.gitignore` ignores `output/*.png`,
`output/*.csv` and `output/*.npy`, so generated files are not committed. Both scripts write there by default.

| File | Written by | Content |
|:-----|:-----------|:--------|
| `complete_time_array.npy` | Phase 1 | N×N station-to-station travel times (seconds) |
| `complete_consumption_array.npy` | Phase 1 | N×N station-to-station energy use (joules) |
| `charging_graph_ids.csv` | Phase 1 | `station_id`, `node_id`, `matrix_id` per station |
| `results.csv` | Phase 2 | One row per run, strategy and iteration: unnamed index, `experiment_id`, `experiment_name` (`Greedy`, `Epsilon-Greedy`, `Thompson Sampling`, `BayesUCB`), `iteration` (1 … horizon), `instant_regret`, `cumulative_regret` |
| `regret_plot.png` | Phase 2 | Mean cumulative regret per strategy over iterations, with a ±1 standard deviation band across runs |

Regret is in seconds of extra expected trip time (see [Overview](overview.md#how-the-strategies-are-evaluated-regret)).
The run number of a row is `experiment_id // 4`.

## Running the tests

```
cd eene-nav-bandit-sim
python -m pytest
```

## Common pitfalls

- **Trailing slash on `--output-dir`.** File names are appended directly (`args.output_dir + 'results.csv'`), so
  `--output-dir /tmp/out` writes `/tmp/outresults.csv`. Always end the folder with `/`.
- **Arguments are not checked.** None of the arguments are marked required, and both scripts use
  `parse_known_args()`, so a misspelt option is silently ignored. Forgetting `--charging-station-csv-path` fails
  with `ValueError: Invalid file path or buffer object type: <class 'NoneType'>`.
- **Start and end must be station nodes.** `--start-node-id` and `--end-node-id` must be `node_id`s of stations that
  are in `charging_graph_ids.csv`.
- **Use non-numeric IDs.** With purely numeric IDs (for example `101`), `sim_runner.py` fails with `KeyError: 101`
  while building the charging graph: `charging_graph_ids.csv` is read back with integer IDs while the station
  dictionary uses string keys. IDs such as `S101` work.
- **One station per road vertex.** Phase 1 keeps only the highest-power station at each `node_id`.
- **Battery capacity is in joules.** Station-to-station legs that use more than `--battery-capacity` are left out of
  the charging graph, so a battery that is too small can leave no route at all.
- **Results vary between runs with the same seed.** See the
  [reproducibility note](data-flows.md#reproducibility-note).
