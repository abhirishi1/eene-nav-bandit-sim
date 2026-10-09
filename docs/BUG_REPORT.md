# Bug Report: eene-nav-bandit-sim

**Repository:** [abhirishi1/eene-nav-bandit-sim](https://github.com/abhirishi1/eene-nav-bandit-sim), branch `main`, commit `6ce69ee`. This is identical to Volvo's upstream.

**Status:** none of these bugs are fixed yet. No application code has been changed. Every fix below is a proposal waiting for your approval.

## Scope and test approach

- I read all the program code: `core/`, `navigation/`, `util/`, `sim_runner.py`, `charging_graph_preprocesser.py` and the tests.
- I ran the existing 12 tests. On Python 3.9 they all pass. On Python 3.10 none of them can start.
- I ran both programs end to end on a tiny made-up map of 6 road junctions and 6 charging stations, with 20 trips and 2 runs. I did this twice: once with text station IDs (`S101`…), once with number IDs (`101`…).
- I wrote small probe scripts that hit each edge case directly.
- All test data and scripts were kept outside the repo, on the machine used for this review.
- Each bug is labelled **Confirmed** (I reproduced it) or **From reading the code** (the consequence is inferred, not observed).

**Guiding rule for all fixes:** make the smallest change that removes the bug and leaves results that were already correct exactly as they are. This code reproduces a published paper, so the same random seed must keep producing the same numbers.

## Summary

| # | Severity | Bug | Status |
|---|----------|-----|--------|
| 1 | Serious | Simulator crashes when station IDs are numbers | Confirmed |
| 2 | Serious | Program won't start on Python 3.10 or newer | Confirmed |
| 3 | Serious | Epsilon-Greedy can freeze forever | Confirmed |
| 4 | Serious | One zero-energy drive permanently breaks a station's learned charging speed | Confirmed |
| 5 | Medium | Start/end stations not excluded from random detours | Confirmed (consequence from reading the code) |
| 6 | Medium | `--output-dir` without a trailing `/` misplaces output files | Confirmed |
| 7 | Medium | Test for random exploration actually tests something else | Confirmed |
| 8 | Minor | An error message crashes while being built, hiding the real error | Confirmed |
| 9 | Minor | Missing required settings give a confusing error | Confirmed |
| 10 | Minor | Broken, unused code in the road-graph container | Confirmed |

## Bugs and proposed solutions

### Bug 1: Simulator crashes when station IDs are numbers (Serious)

- **What happens:** if the charging-station CSV uses number IDs like `101`, preprocessing works but `sim_runner.py` stops at once with `KeyError: 101`. The same data with IDs like `S101` runs fine. I believe Open Charge Map, the data source the README suggests, uses number IDs, which would mean real data hits this. I haven't checked that against their data.
- **Where:** `navigation/env_impl.py`, line 186 (`_create_charging_graph`), and the failing lookup on line 190.
- **Cause:** the program stores each station under its ID as *text* (lines 109–110 use `str(...)`). When the simulator reads `charging_graph_ids.csv` back, though, the IDs come in as *numbers*. Line 186 uses them unchanged, so `101` (number) doesn't match `"101"` (text).
- **Evidence:** the run stops in `_create_charging_graph` on the line `from_station = charging_stations[matrix_idx_to_stations[i]]` with `KeyError: 101`.
- **Proposed solution:** on line 186, convert the ID to text: `str(record['station_id'])`. This matches what lines 104 and 109–110 already do. Fixing it here also covers anyone who builds the environment directly in Python instead of going through `sim_runner.py`.
- **New test:** build the test environment with number station IDs and check that it finds a route.
- **Before / after:** before, number IDs crash. After, they work. Results for text IDs stay identical.

### Bug 2: Program won't start on Python 3.10 or newer (Serious)

- **What happens:** `ImportError: cannot import name 'MutableMapping' from 'collections'`. Every test and both programs fail before doing anything.
- **Where:** `util/road_graph.py`, line 4: `from collections import MutableMapping`.
- **Cause:** Python moved `MutableMapping` to `collections.abc` long ago and removed the old location in Python 3.10.
- **Proposed solution:** change the line to `from collections.abc import MutableMapping`. The new location has existed since Python 3.3, so Python 3.9 keeps working.
- **Verification:** run all 12 tests on Python 3.9 and 3.10.
- **Before / after:** before, 0 of 12 tests can start on 3.10. After, all 12 should pass on both versions. No results change.

### Bug 3: Epsilon-Greedy can freeze forever (Serious)

- **What happens:** when Epsilon-Greedy decides to explore, it picks a random charging station to detour through. If no station can be used as a detour, it keeps retrying forever. On my test map built to trigger this, it was still stuck after 20 seconds and had to be killed.
- **Where:** `navigation/env_impl.py`, `find_random_action`, lines 467–484.
- **Cause:** a `while not found_station` loop with no stopping condition, plus a bare `except:` that silently swallows *every* error, not just "no route". It also has no check for an empty list of candidate stations.
- **Proposed solution:**
    1. Keep the existing "pick a random station, retry if it fails" loop unchanged, so normal runs draw exactly the same random numbers as before.
    2. Remember which stations have already failed, and stop once every candidate has failed (or if there are no candidates).
    3. Catch only NetworkX's "no route" errors (`NetworkXNoPath`, `NodeNotFound`), so genuine bugs still show up.
- **Decision needed (yours):** what should happen when no detour exists?
    - **(a)** Stop with a clear error message. *Recommended*: it doesn't make up new behaviour.
    - **(b)** Use the current best route for that trip. The simulation keeps running, but the strategy explores less than the paper describes.
- **New test:** the "no reachable detour" map must finish promptly, with (a) a clear error or (b) a valid route.
- **Before / after:** before, it hangs forever. After, it gives a clear outcome. Runs that worked before produce identical results.

### Bug 4: One zero-energy drive permanently breaks a station's learned charging speed (Serious)

- **What happens:** if the drive leading to a charging stop uses zero (or negative) energy, the program's estimate of that charger's speed turns into "minus infinity" and never recovers. Nothing crashes, so the learning goes wrong silently. In my probe the learned value went from a normal `17.0` to `-inf`, and the estimated "typical" value fell back to the optimiser's starting guess (`1.0`).
- **Where:** `navigation/alg_impl.py`. `_feedback_transformation` (lines 84–91) turns this case into a value of exactly 0, and line 151 then computes `np.log(0)`.
- **Cause:** the code comment on line 86 intends "assume the charger ran at full power". That produces exactly 0, though, and the charging-speed model (a gamma distribution) can't use 0 as an observation because its logarithm is minus infinity. Zero or negative energy could plausibly come from downhill legs with regenerative braking (my guess; not tested on real maps).
- **Proposed solution:** when the leg's energy or the charging time is zero or negative, the stop tells us nothing about the charger's speed. So skip the charging-speed update for that visit, but still update the queue-time estimate as normal.
- **Decision needed (yours):** this is a modelling choice. I haven't read how the paper handles this case. Please confirm "skip the update", or ask me to check the paper first.
- **New test:** the zero-energy scenario must leave the charging-speed values unchanged and finite, while the queue-time values still update.
- **Before / after:** before, the estimate is permanently corrupted. After, that one visit is ignored for charging speed. Runs without zero-energy legs are unchanged.

### Bug 5: Start/end stations not excluded from random detours (Medium)

- **What happens:** the code meant to stop the start and end stations being picked as a "random detour" never excludes anything when station IDs differ from road-junction IDs. In my probe (stations `s1`, `s2`, `s3`; start junction `1`, end junction `3`) all three stations stayed candidates. From reading the code, picking the start or end station as the "detour" just gives the direct route, so some exploration trips aren't really exploring.
- **Where:** `navigation/env_impl.py`, lines 463–464.
- **Cause:** it compares *station* IDs with the start/end *junction* IDs. The comments on lines 65–66 say start and end are junction (node) IDs.
- **Proposed solution:** compare each station's `node_id` instead.
- **Note:** this changes which stations can be picked at random, so for maps where the IDs differ, results with the same seed will change. That's why I'd keep it as a separate decision from the serious bugs. Maps where station ID equals junction ID, like the tests, are unaffected.
- **New test:** with station IDs different from junction IDs, the start and end stations must not be candidates.

### Bug 6: `--output-dir` without a trailing `/` misplaces output files (Medium)

- **What happens:** with `--output-dir /home/ubuntu/eene-bugcheck/noslash`, the simulator wrote `noslashresults.csv` and `noslashregret_plot.png` *next to* that folder, and the folder stayed empty.
- **Where:** `sim_runner.py`, lines 109–114, and `charging_graph_preprocesser.py`, lines 77–78 and 91.
- **Cause:** paths are glued together as text (`args.output_dir + 'results.csv'`) instead of joined as folder + file name.
- **Proposed solution:** use `os.path.join(args.output_dir, 'results.csv')` and the same for the other files. Paths that already end in `/` behave exactly as before.

### Bug 7: Test for random exploration actually tests something else (Medium)

- **What happens:** `test_find_random_action` (`tests/test_env_impl.py`, lines 56–61) calls `find_best_action`, not `find_random_action`. Random exploration therefore has no test at all, which is how bugs 3 and 5 went unnoticed.
- **Proposed solution:** make the test call `find_random_action` with a fixed random seed. Check that it returns a valid route through a charging station that isn't the start or end. The new tests for bugs 3 and 5 extend it.

### Bug 8: An error message crashes while being built, hiding the real error (Minor)

- **What happens:** when a charging time is invalid (e.g. a charger with power 0), the program means to raise `ValueError: Invalid charging time…`. Building that message fails, so you get `TypeError: can only concatenate str (not "numpy.float64") to str` instead.
- **Where:** `navigation/env_impl.py`, line 342.
- **Cause:** it adds text and a number with `+`.
- **Proposed solution:** wrap the number in `str(...)` (or use an f-string). The intended `ValueError` then appears.

### Bug 9: Missing required settings give a confusing error (Minor)

- **What happens:** running `sim_runner.py` without the station file, start or end setting gives `ValueError: Invalid file path or buffer object type: <class 'NoneType'>`. It doesn't say which setting is missing.
- **Where:** `sim_runner.py`, lines 24–26.
- **Proposed solution:** mark those three settings `required=True`. Python's argument parser then prints a clear "the following arguments are required: …" message. Runs that give all the settings are unaffected.

### Bug 10: Broken, unused code in the road-graph container (Minor)

- **What happens:** assigning a new edge with `container[key] = value` raises `KeyError`.
- **Where:** `util/road_graph.py`, `VertexOutgoingEdges.__setitem__`, lines 30–33.
- **Cause:** it reads `self.edges[key]` to check whether the key exists, which fails when it doesn't.
- **Impact:** none today. The program always uses `set_edge()` instead.
- **Proposed solution:** check with `self.edges.get(key) is None`. Alternatively, leave it alone because it's unused. I'd fix it only if we're already editing this file for bug 2.

## Verification plan for the fixes

For each approved fix:
1. Add the new test, and show it fails *before* the fix.
2. Apply the fix and show the new test passes.
3. Run all tests on Python 3.9 (and on 3.10 once bug 2 is fixed).
4. Re-run the end-to-end test with text station IDs and check that `results.csv` is **identical** to the run before the fix (same seed), except for bug 5 where a change is expected.
5. Re-run the end-to-end test with number station IDs (after bug 1).

**Suggested order:** 2 → 1 → 3 → 4, then 6–10, then 5. Each fix goes on a branch in your fork only and gets your approval before it's committed. Nothing goes to Volvo's repo.

## Known limitations of this review

- Everything was tested on a tiny made-up map, not real OpenStreetMap or Open Charge Map data.
- I didn't read the paper's full text, so I haven't checked whether the maths matches it beyond these bugs.
- The regret chart's shaded band can dip below zero, which regret can't actually do. It's ±1 standard deviation averaged over only a few runs, so it's a display quirk, not a calculation bug.
