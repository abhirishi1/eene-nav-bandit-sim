# Data flow

[Home](Home.md) · [Architecture](Architecture.md) · [Dependencies](Dependencies.md) · **Data flow**

## End to end

```mermaid
flowchart TB
    R[/"road graph CSV<br/>(one row per road segment)"/] --> P
    S[/"charging station CSV<br/>(one row per station)"/] --> P
    P["Step 1: charging_graph_preprocesser.py"] --> T[/"complete_time_array.npy<br/>N x N driving times (s)"/]
    P --> C[/"complete_consumption_array.npy<br/>N x N energy use (J)"/]
    P --> I[/"charging_graph_ids.csv<br/>station_id, node_id, matrix_id"/]
    S --> M
    T --> M
    C --> M
    I --> M
    M["Step 2: sim_runner.py"] --> OUT1[/"results.csv"/]
    M --> OUT2[/"regret_plot.png"/]
```

Step 1 is slow on real maps (the README warns it can take hours) but only needs to run once per map. Step 2 can then be re-run with different settings.

## Inputs

All units are SI: energy in **joules**, time in **seconds**, power in **watts**.

**Road graph CSV**: one row per *directed* road segment (a two-way road needs two rows):

| Column | Meaning |
|--------|---------|
| `from_id`, `to_id` | Start and end junction IDs (read as text) |
| `from_y`, `from_x`, `to_y`, `to_x` | Latitude and longitude of both ends |
| `mean_consumption` | Average energy used on the segment (J) |
| `mean_time` | Average driving time on the segment (s) |

**Charging station CSV**: one row per station:

| Column | Meaning |
|--------|---------|
| `station_id` | Unique station ID |
| `node_id` | Road junction the station sits at (must exist in the road graph) |
| `node_y`, `node_x` | Coordinates of that junction |
| `power` | Rated charging power (W) |

The start and end of the trip (`--start-node-id`, `--end-node-id`) must be the `node_id` of a station.

## Step 1: preprocessing (`charging_graph_preprocesser.py`)

1. **Read and check** both CSVs with pandas. `util/csv_validation.py` lists every missing column, blank or invalid value, duplicate `station_id` and station `node_id` that isn't in the road graph, with its line number, and the script stops before doing any work.
2. **Keep one station per junction.** `filter_charging_stations` keeps the highest-power station when several share a `node_id`. *N* = the number of stations left.
3. **Build the road graph** as a `RoadGraph`, plus a NetworkX `DiGraph` weighted by driving time.
4. **For each station:** find the *fastest* path to every junction (Dijkstra on driving time), then add up both time and energy along those paths (`add_consumption_to_distances`).
   - The energy figure is for the fastest route, not the most energy-efficient one.
5. **Fill the N x N tables.**
   - Row = from-station, column = to-station, in the order of the filtered station list.
   - Stations that can't be reached stay at infinity.
6. **Save** the two tables as `.npy` files.
   - `charging_graph_ids.csv` records which row/column (`matrix_id`) belongs to which `station_id` and `node_id`.

## Step 2: simulation (`sim_runner.py`)

1. **Read settings.**
   - Priors: `--queue-prior-param-*`, `--charge-prior-param-*`.
   - Battery capacity: default 252,000,000 J = 70 kWh.
   - Number of trips and runs, start seed.
2. **Load and check** the station CSV (the same station checks, plus: the start and end nodes must be station `node_id`s), then load the ID CSV and both tables.
3. **Create experiments** (`create_experiments`): for each run *r*, four `BanditExperiment`s, one per strategy (IDs `4r` to `4r+3`).
   - The real world uses seed `start_seed + r`. Each strategy's private planning copy uses seed `start_seed + runs + r`.
   - So in a given run, all four strategies are meant to face the same world. Bug 11 (an unseeded sampler) means the hidden charging powers can still differ.
4. **Run each experiment** in turn. It runs `--experiment-horizon` trips (default 100).
5. **Collect results.** Add up the regret per trip into a running total, then save everything to `results.csv`.
6. **Plot** the average running total per strategy across runs, with a band of ±1 standard deviation, as `regret_plot.png`.

### Setting up one experiment

When `NavigationBanditEnvironment` is created (the real world), for every station it:
- draws a hidden **queue rate** `λ ~ Gamma(a, 1/b)`. The station's mean wait is `1/λ`.
- draws a hidden **charging-power distribution**:
  - a shape parameter from the GamCon-II prior, using SciPy's sampler;
  - a rate parameter from a gamma distribution;
  - from these two, an estimate of the station's typical power.
- builds the **charging graph** from the tables (see [Architecture](Architecture.md#the-charging-graph)).

The experiment then finds the **best possible route** using the true expected times. That route's expected time is the yardstick for regret.

### What happens on each trip

```mermaid
sequenceDiagram
    participant X as BanditExperiment
    participant A as Strategy (algorithm)
    participant P as Strategy's private copy
    participant W as Real world (environment)
    X->>A: select_action(trip)
    A->>P: replace_action_parameters(estimated queue times and powers)
    A->>P: find_best_action() or find_random_action()
    P-->>A: route + station IDs
    A-->>X: action (route)
    X->>W: receive_feedback_for_action(route)
    W-->>X: observed driving, queue and charging times
    X->>A: update_with_feedback(route, feedback)
    Note over A: update beliefs for each station visited
    X->>W: expected_reward_for_action(route)
    W-->>X: expected trip time of that route
    Note over X: regret = chosen route's expected time minus best route's expected time
    X->>W: update_environment()
    Note over W: draw new random queue wait and charging power for every station
```

- **Observed values:**
  - Driving times are fixed: the table value.
  - Each station's queue time is random, drawn from an exponential distribution with its hidden rate.
  - Charging power is `max(min_power, rated_power - scale x g)`, where `g` is random from the station's hidden gamma distribution.
  - `min_power` = `--min-power-factor` (default 0.5) x rated power, and `scale` = `--power-scale` (default 300).
  - Charging time = energy of the leg just driven / that power.
- **Belief update:**
  - Queue: `alpha + 1`, `beta + observed wait`.
  - Charging: the observed power is turned back into a shortfall `g = (rated - observed) / scale`. Then `ln_p + ln(g)`, `q + g`, `r + 1`, `s + 1`.
- **Regret is based on expected values**, not on the random times of that trip, so luck on a single trip doesn't affect it.

## Outputs

**`results.csv`**: one row per strategy per trip per run:

| Column | Meaning |
|--------|---------|
| *(unnamed first column)* | Row number (pandas index) |
| `experiment_id` | `4 x run + strategy index` (0 Greedy, 1 Epsilon-Greedy, 2 Thompson Sampling, 3 BayesUCB) |
| `experiment_name` | Strategy name |
| `iteration` | Trip number, from 1 to the horizon |
| `instant_regret` | Extra expected time of this trip's route over the best route (s) |
| `cumulative_regret` | Running total of `instant_regret` within that run (s) |

**`regret_plot.png`**: one line per strategy (average across runs) with a shaded ±1 standard deviation band.
- With few runs, the band can dip below zero even though regret itself can't be negative.

## Where known issues occur

Bug numbers refer to [`docs/BUG_REPORT.md`](https://github.com/abhirishi1/eene-nav-bandit-sim/blob/devin/1791560357-bug-report/docs/BUG_REPORT.md).

| Stage | Issue |
|-------|-------|
| Inputs | Checked by `util/csv_validation.py` on this branch. On the original code, a blank `power` stops step 1 with a cryptic `KeyError`, a blank `mean_time` makes step 2 run without finishing (still running after 60 s in testing), and a blank `mean_consumption` silently leaves blank entries in the energy table. The checks don't cover values that are filled in but wrong, e.g. an implausible energy figure |
| Starting either script | Python 3.10+ won't start on the original code (bug 2, fixed on this branch). Missing required arguments give a confusing error (bug 9) |
| Saving outputs (both steps) | Fixed on this branch: paths are joined with `os.path.join` and a missing folder is created. On the original code, `--output-dir` without a trailing `/` puts files next to the folder, not inside it (bug 6) |
| Step 2, loading IDs | Numeric station IDs (e.g. `101`) crash with `KeyError` (bug 1) |
| Step 2, experiment setup | The SciPy sampler ignores the seed, so results vary between identical runs (bug 11, found later and not yet in the report) |
| Each trip, Epsilon-Greedy detours | Can loop forever if no detour station is reachable (bug 3). Start and end stations aren't reliably excluded (bug 5). No test covers this (bug 7) |
| Each trip, belief update | A leg with zero or negative energy breaks that station's charging-power belief for good (`ln(0)`; bug 4) |
| Charging-time error path | The error message itself crashes (bug 8) |
| Unused code | `VertexOutgoingEdges.__setitem__` is broken but never called (bug 10) |
