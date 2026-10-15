# Algorithms

[Home](README.md) · [Overview](overview.md) · [Architecture](architecture.md) · [Data flows](data-flows.md) ·
**Algorithms** · [Usage](usage.md)

This page describes what the code in `eene-nav-bandit-sim/navigation/alg_impl.py`,
`eene-nav-bandit-sim/navigation/env_impl.py`, `eene-nav-bandit-sim/util/utils_gamma.py` and
`eene-nav-bandit-sim/util/common.py` actually computes. Gamma distributions are written with shape and **rate**,
$\mathrm{Gamma}(\text{shape}, \text{rate})$; the code calls NumPy/SciPy with `scale = 1 / rate`.

## The simulated world

Every station has two unknown random quantities: its **queue time** and its **charging power**.

**Queue time.** `NavigationBanditEnvironment._generate_base_action_parameters` draws a true rate for each station
from the queue prior, and `_charging_station_update` draws a new queue time every iteration:

```math
\lambda \sim \mathrm{Gamma}(a_0, b_0), \qquad \text{queue time} \sim \mathrm{Exponential}(\text{mean } 1/\lambda)
```

with $a_0$ = `--queue-prior-param-alpha0` (default 2) and $b_0$ = `--queue-prior-param-beta0` (default 2400). The
true expected queue time is $1/\lambda$.

**Charging power.** The power is modelled through a gamma-distributed "power drop" $G$:

```math
G \sim \mathrm{Gamma}(\alpha, \beta), \qquad P = \max\left(P_{\min},\ P_{\max} - c\,G\right)
```

where $P_{\max}$ is the station's `power` column, $P_{\min}$ = `--min-power-factor` × $P_{\max}$ and $c$ =
`--power-scale` (default 300). The true $(\alpha, \beta)$ are drawn once per station from the charge prior: $\alpha$
from `GammaConjugatePriorAlphaDist(ln_p0, q0, r0, s0)` with SciPy's `TransformedDensityRejection(..., c=0.)`, then
$\beta \sim \mathrm{Gamma}(s_0\alpha, q_0)$.

**Expected times.** Driving a leg that uses energy $E$ and then charging at a station takes $E / P$ seconds of
charging, so the expected charging time is $E \cdot \mathbb{E}[1/P]$. The code computes
$\bar P = 1 / \widehat{\mathbb{E}}[1/P]$ with `mc_estimate_of_mean_charge_power_reciprocal` (1000 Monte Carlo
samples) and uses $E / \bar P$. The environment does this once, at construction, to get each station's true expected
power, which is what `expected_reward_for_action` (and therefore regret) uses.

## What every algorithm learns

`AbstractNavigationBanditAlgorithm._create_posterior_parameter_dictionaries` gives every station the same starting
posterior (the prior), stored in `self.posterior_parameters[station_id]` as

```
((alpha, beta), (ln_p, q, r, s))
```

- `(alpha, beta)`: a $\mathrm{Gamma}(\alpha, \beta)$ posterior over the queue rate $\lambda$, starting at
  $(a_0, b_0)$.
- `(ln_p, q, r, s)`: a gamma conjugate prior/posterior over the power-drop parameters $(\alpha, \beta)$, starting at
  `ChargePrior(ln_p, q, r, s)` (defaults 13.5, 300, 3, 3). See
  [the helpers section](#gamma-conjugate-prior-helpers-utilutils_gammapy).

It also caches the posterior mode of the power-drop shape, `self.posterior_alpha_modes[station_id]` $= \hat\alpha$,
computed with `gamma_prior_alpha_mode`.

## From posterior to edge weights (shared by all four)

Each strategy's `select_action` does the same three things; only step 1 differs.

1. For every station, choose a queue rate and a pair $(\alpha_c, \beta_c)$ from the posterior (mode, sample or
   quantile, see below), and turn them into an **expected queue time** $\tau$ and an **expected charging power**
   $\bar P$ with `_expectation_transformation(charging_station, (tau, gamma_mean, alpha_c, beta_c))`. That function
   returns $\tau$ unchanged and

   ```math
   \bar P = \left( \frac{1}{1000} \sum_{k=1}^{1000} \frac{1}{\max(P_{\min},\ P_{\max} - 300\,G_k)} \right)^{-1},
   \qquad G_k \sim \mathrm{Gamma}(\alpha_c, \beta_c)
   ```

   (the second tuple element, `gamma_mean`, is not used; 1000 and 300 are the helper's defaults `number_of_samples`
   and `scale`). Because every sampled power lies in $[P_{\min}, P_{\max}]$, so does $\bar P$.
2. Pass `{station_id: (tau, P_bar, ...)}` to the internal environment's `replace_action_parameters(None, ...)`. For
   every station that is not the end node this sets the weight of the `QUEUE` edge `"<node>_queue" → "<node>"` to
   $\tau$ and sets `charging_graph_power_ndarray[j]` to $\bar P$, so the `CHARGE` edge weight computed by
   `_nx_weight_function` becomes $E_{h \to j} / \bar P_j$.
3. Call the internal environment's `find_best_action(iteration)`: A* (`networkx.astar_path`) from start to end. The
   chosen route minimises

   ```math
   \sum_{\text{legs}} \text{drive time} + \sum_{\text{stops } j} \left( \tau_j + \frac{E_{\text{leg into } j}}{\bar P_j} \right)
   ```

   and the action returned is `(path, station_ids)`, where `station_ids` lists the stations whose `QUEUE` edge is on
   the path.

## Greedy and Epsilon-Greedy

`EpsilonGreedyNavigationBanditAlgorithm.select_action`:

```python
epsilon = self.epsilon_function(iteration)
if epsilon > 0.0 and self.rng.random() < epsilon:
    (path, station_ids) = self.bandit_algorithm_environment.find_random_action(iteration)
else:
    posterior_modes = self._compute_posterior_modes()
    self.bandit_algorithm_environment.replace_action_parameters(None, posterior_modes)
    (path, station_ids) = self.bandit_algorithm_environment.find_best_action(iteration)
```

- **Explore** (probability $\epsilon$): `find_random_action` picks a station uniformly at random (excluding IDs equal
  to the start/end node) and returns the shortest path start → station → end, using whatever weights the internal
  environment currently holds. `sim_runner.py` sets `epsilon_function=lambda t: 1. / np.sqrt(t)`, so iteration 1 is
  always random and exploration then decays.
- **Exploit**: `_compute_posterior_modes` uses MAP (posterior mode) estimates:

  ```math
  \hat\lambda = \frac{\alpha - 1}{\beta} \ \ (\text{if } \alpha \ge 1), \qquad \tau = 1/\hat\lambda
  ```

  ```math
  \hat\alpha = \text{its cached posterior mode}, \qquad
  \hat\beta = \frac{s\hat\alpha - 1}{q} \ \ (\text{if } s\hat\alpha > 1)
  ```

  $\hat\beta$ is the mode of $\beta \mid \hat\alpha \sim \mathrm{Gamma}(s\hat\alpha, q)$. If a condition fails, the
  code logs a warning and uses `EPSILON / beta` (for $\hat\lambda$) or `EPSILON / q` (for $\hat\beta$), where
  `EPSILON = np.finfo(float).eps`. Then $\bar P$ comes from `_expectation_transformation` with
  $(\alpha_c, \beta_c) = (\hat\alpha, \hat\beta)$.

**Greedy** is `GreedyNavigationBanditAlgorithm`, a subclass that calls the Epsilon-Greedy constructor with
`epsilon_function=lambda t: 0.0`, so it always exploits.

## Thompson Sampling

`ThompsonSamplingNavigationBanditAlgorithm.select_action` calls `_generate_posterior_samples(iteration)`, which for
each station draws one plausible world from the posterior:

```math
\lambda^\ast \sim \mathrm{Gamma}(\alpha, \beta), \quad \tau = 1/\lambda^\ast; \qquad
\alpha^\ast \sim \text{GamCon-II}(\ln p, q, r, s), \quad \beta^\ast \sim \mathrm{Gamma}(s\alpha^\ast, q)
```

and then $\bar P$ from `_expectation_transformation` with $(\alpha_c, \beta_c) = (\alpha^\ast, \beta^\ast)$.

Sampling $\alpha^\ast$ needs a SciPy `TransformedDensityRejection` sampler, which is slow to build, so:

- `_create_sampler(ln_p, q, r, s, mode=alpha_hat)` builds `TransformedDensityRejection(GammaConjugatePriorAlphaDist(ln_p, q, r, s), c=0., center=mode)`
  and the code draws `number_of_cached_samples` (100 in `sim_runner.py`) values at once into `self.cached_samples[station_id]`.
  Each iteration uses the next cached value.
- The overridden `update_with_feedback` first runs the shared posterior update, then sets
  `cached_samples_indices[station_id] = number_of_cached_samples` for every visited station, so the next iteration
  builds a new sampler from that station's updated posterior. Unvisited stations keep using their cached draws (their
  posterior has not changed).
- If building the sampler raises, the error is logged and `MillerDummyModeSampler(alpha_hat)` is used instead, which
  always returns $\hat\alpha$. `use_mode_sampler[station_id]` is then `True`, and that station uses the mode sampler
  for the rest of the experiment.

## BayesUCB

`BayesUcbNavigationBanditAlgorithm.select_action` calls `_compute_posterior_ucbs(iteration)`, which uses posterior
**quantiles** at level

```math
u_t = 1 - \frac{1}{t + 1}
```

(0.5 at $t = 1$, rising towards 1), via `scipy.stats.gamma.ppf`:

```math
\lambda^{+} = F^{-1}_{\mathrm{Gamma}(\alpha, \beta)}(u_t), \quad \tau = 1/\lambda^{+}; \qquad
\beta^{+} = F^{-1}_{\mathrm{Gamma}(s\hat\alpha, q)}(u_t)
```

and $\bar P$ from `_expectation_transformation` with $(\alpha_c, \beta_c) = (\hat\alpha, \beta^{+})$. Both
choices are **optimistic**: an upper quantile of the queue rate $\lambda$ means a shorter expected queue, and an upper
quantile of the rate $\beta$ means a smaller power drop $G$, so a higher expected power. The shape $\hat\alpha$ is the
posterior mode, not a quantile. (The code also computes `posterior_charge_gamma_ucb` $= \hat\alpha / \beta^{+}$ and
passes it as the unused `gamma_mean` element.)

## Learning from feedback: `update_with_feedback`

`AbstractNavigationBanditAlgorithm.update_with_feedback(iteration, action, feedback)` is shared by all four strategies.
It only uses the per-station part of the feedback, `feedback[1]`, a list of `[-queue_time, -charging_time]` in the
order of `action[1]` (see [Data flows](data-flows.md#what-the-feedback-looks-like)).

1. **Find the leg into each station.** For each `CHARGE` edge at position `i` on the path, the `TRIP` edge from
   `path[i-1]` to `path[i]` is the leg driven just before charging; its `parameters` are `(mean_time, mean_consumption)`.
2. **Turn the observation into a power-drop sample** with `_feedback_transformation(trip_edge, charging_station, feedback)`:

   ```math
   P_{\text{obs}} = \frac{E_{\text{leg}}}{t_{\text{charge}}}, \qquad g = \frac{P_{\max} - P_{\text{obs}}}{c}
   ```

   with $c$ = `self.power_scale`. If $E_{\text{leg}} \le 0$ or $t_{\text{charge}} \le 0$ the code sets
   $P_{\text{obs}} = P_{\max}$ (so $g = 0$).
3. **Queue posterior** (gamma prior, exponential likelihood):

   ```math
   \alpha \leftarrow \alpha + 1, \qquad \beta \leftarrow \beta + \text{queue time}
   ```

4. **Charging posterior** (gamma conjugate prior, gamma likelihood for one sample $g$):

   ```math
   \ln p \leftarrow \ln p + \ln g, \qquad q \leftarrow q + g, \qquad r \leftarrow r + 1, \qquad s \leftarrow s + 1
   ```

5. **Recompute the mode** $\hat\alpha$ = `gamma_prior_alpha_mode(ln_p, q, r, s)` and store both in
   `posterior_parameters` and `posterior_alpha_modes`.

Why these updates are conjugate (a derivation, not code): with
$\pi(\lambda) \propto \lambda^{\alpha-1} e^{-\beta\lambda}$ and likelihood $\lambda e^{-\lambda x}$ the posterior is
$\lambda^{\alpha} e^{-(\beta + x)\lambda}$, i.e. $\mathrm{Gamma}(\alpha + 1, \beta + x)$. For the power drop, the
joint density that matches the code's helpers is

```math
\pi(\alpha, \beta) \propto \frac{p^{\alpha-1}\, \beta^{s\alpha - 1}\, e^{-q\beta}}{\Gamma(\alpha)^{r}}
```

Multiplying by one gamma likelihood $\beta^{\alpha} g^{\alpha-1} e^{-\beta g} / \Gamma(\alpha)$ gives the same form
with $p \to p\,g$, $q \to q + g$, $r \to r + 1$, $s \to s + 1$, which is exactly step 4 (in log form for $p$).
Integrating $\beta$ out gives the marginal over $\alpha$ that `utils_gamma.py` implements, and conditioning on
$\alpha$ gives $\beta \mid \alpha \sim \mathrm{Gamma}(s\alpha, q)$, which is how the code draws or estimates $\beta$
everywhere.

## Gamma conjugate prior helpers (`util/utils_gamma.py`)

The docstrings call this distribution GamCon-II: the marginal distribution of the gamma shape $\alpha$ under the
conjugate prior above. All functions take `(alpha, ln_p, q, r, s)`.

| Function | Computes |
|:---------|:---------|
| `gamma_prior_alpha_lpdf` | $\ell(\alpha) = \alpha \ln p - s\,\alpha \ln q - r \ln\Gamma(\alpha) + \ln\Gamma(s\alpha)$ (via `scipy.special.gammaln`) |
| `gamma_prior_alpha_dlpdf` | $\ell'(\alpha) = \ln p - s \ln q - r\,\psi(\alpha) + s\,\psi(s\alpha)$, with $\psi$ = `scipy.special.digamma` |
| `gamma_prior_alpha_pdf` | $\exp(\ell(\alpha))$ |
| `gamma_prior_alpha_dpdf` | $\exp(\ell(\alpha))\,\ell'(\alpha)$ |
| `gamma_prior_alpha_mode(ln_p, q, r, s, center=1.0)` | $\arg\max_\alpha \ell(\alpha)$ by `scipy.optimize.minimize` of $-\ell$ with gradient $-\ell'$, start `x0 = center`, bounds $[\,$`EPSILON`$, \infty)$ (with bounds and no method given, SciPy uses L-BFGS-B) |

Notes:

- The density is **unnormalised**. $\ell$ equals the log of $p^{\alpha-1}\Gamma(s\alpha) / (q^{s\alpha}\Gamma(\alpha)^r)$
  up to the constant $\ln p$. That is fine for the mode and for `TransformedDensityRejection`, neither of which needs
  a normalising constant.
- `GammaConjugatePriorAlphaDist(ln_p, q, r, s)` wraps these as `pdf(x)`, `dpdf(x)` and `support()` →
  `(EPSILON, np.inf)`, the interface SciPy's `TransformedDensityRejection` expects. Both callers pass `c=0.`, which
  is the log transformation and requires a log-concave density (the error message in `_create_sampler` says
  "log-concave").

## Monte Carlo and fallback helpers (`util/common.py`)

- `mc_estimate_of_mean_charge_power_reciprocal(charge_alpha, charge_beta, min_power, max_power, number_of_samples=1000, scale=300., rng=...)`:
  draws `number_of_samples` values $G_k \sim \mathrm{Gamma}(\alpha, \beta)$ with `rng.gamma(alpha, scale=1/beta)`,
  computes $P_k = \max(P_{\min}, P_{\max} - \text{scale}\cdot G_k)$, and returns the mean of $1/P_k$. Callers invert
  it to get $\bar P$.
- `MillerDummyModeSampler(mode)`: `rvs(size)` returns `mode * np.ones(size)`, a drop-in for the TDR sampler when it
  cannot be built.

## Implementation notes

These are observations about the code as written, useful when reading results or changing it:

- `_expectation_transformation` calls `mc_estimate_of_mean_charge_power_reciprocal` without `scale`, so the
  algorithms always use the default 300, whereas the environment passes `scale=self.power_scale` and
  `_feedback_transformation` divides by `self.power_scale`. With the default `--power-scale 300` these agree; with any
  other value the algorithms' power model differs from the environment's.
- When the true power hits the floor $P_{\min}$, the observed $g$ is $(P_{\max} - P_{\min})/c$ rather than the actual
  draw of $G$ (the observation is censored), and the update treats it as an exact sample.
- If $g = 0$ (the $E_{\text{leg}} \le 0$ fallback), `np.log(gamma_sample)` makes $\ln p = -\infty$ for that station.
- The Monte Carlo estimate in step 1 uses the algorithm's RNG, so even Greedy's estimates carry a little sampling noise.
