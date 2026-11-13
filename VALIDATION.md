# Validation report — polymarket-nvidia-ceo-forecast-01 entry

## Chosen model

Persistence median (last price at the checkpoint) with a per-market,
two-timescale Gaussian spread in sqrt(h), peaked centre and fat tails:

```
sigma_m = 0.65 * mean(mean|1-min move| last 1080 min, mean|1-min move| last 360 min)
sigma_m in [0.0002, 0.01]
q_tau(h) = clamp(x + z_tau * shape_tau * sigma_m * sqrt(h), 0, 1)
shape = (1.30, 0.85, 1.0, 0.85, 1.30) for tau = (0.05, 0.25, 0.5, 0.75, 0.95)
```

## Local practice results

Practice actuals were fetched from Polymarket's public CLOB
(`GET /prices-history`, fidelity 1) for 2026-11-12T06:00Z–2026-11-13T06:00Z
for all 24 universe tokens, rebuilt onto the 1-minute grid exactly as the
rules describe (last point ≤ minute, forward-filled), and scored with the
pinball loss. Sanity check: this scorer reproduces the house baseline
exactly — loss 0.363589, median error 0.767503, 90% coverage 0.949642 —
and reproduces every input price on the grid (0 mismatches).

| | pinball loss | median error | 90% coverage |
|---|---|---|---|
| **This entry** | **0.270707** | 0.767503 | 0.876204 |
| House baseline (sigma 0.0025) | 0.363589 | 0.767503 | 0.949642 |

**25.5% lower loss than the baseline.**

Per-case losses (entry vs baseline):

| case | checkpoint (UTC) | entry | baseline |
|---|---|---|---|
| p00 | 2026-11-12 06:00 | 0.463 | 0.536 |
| p01 | 2026-11-12 10:00 | 0.309 | 0.380 |
| p02 | 2026-11-12 14:00 | 0.360 | 0.408 |
| p03 | 2026-11-12 18:00 | 0.241 | 0.369 |
| p04 | 2026-11-12 22:00 | 0.213 | 0.299 |
| p05 | 2026-11-13 02:00 | 0.103 | 0.238 |

Better than baseline on **all 6 cases** — the win is not driven by one case.

## Data evidence behind the model

- Prices are extremely sticky: ~87% of 1-minute moves are exactly zero;
  the median 240-minute change is zero. A single global sigma is far too
  wide for quiet markets (some move ~0.00001/min) and too narrow for
  jumpy ones (~0.011/min). Per-market scaling is the whole win.
- Per-market 1-minute move scales (last 1440 min) span ~100x, e.g.
  Hock Tan mean|move| 0.00001 vs Colette Kress 0.00264.
- 1-minute diff autocorrelation is ~−0.08 at lag 1 (mild mean reversion);
  after a ≥0.01 jump the next minute reverses only ~6% on average — no
  usable reversal signal. The sum of all 24 prices at checkpoints was
  0.81–1.09, i.e. no usable adding-up constraint.
- Move distribution is peaked with fat tails: at h=60 the pooled
  empirical 5%/95% changes are −0.0615/+0.0300 while the sd implies
  ±0.133 for a Gaussian — hence the 0.85 inner / 1.30 outer shape.

## What was tried and rejected

| idea | practice loss | verdict |
|---|---|---|
| House baseline, global sigma 0.0025 | 0.363589 | baseline |
| Global sigma sweep (best 0.0008) | 0.326921 | too wide for quiet markets |
| Per-market mean\|move\|, W=720, k=0.7 | 0.277298 | good, superseded by blend |
| Per-market mean\|move\|, W=1080, k=0.6, tail 1.3, inner 0.85 | 0.272609 | close second |
| **Chosen: blend W=1080+360, k=0.65, tail 1.3, inner 0.85** | **0.270707** | **chosen** |
| Empirical h-step quantiles (per-market, hist 1440) | 0.356279 | inherits last regime's trend; median ≠ last price |
| Empirical quantiles blended 50% with Gaussian | 0.299423 | still worse |
| Trimmed-RMS sigma (k=0.9) | 0.319753 | jump-dominated, over-widens |
| 90th-percentile \|move\| sigma (k=0.5) | 0.279138 | worse than mean\|move\| |
| Drift from recent slope (k=0.1–0.5, win 60–720) | 0.278–0.343 | median error rises; rejected |
| Mean-reversion pull to trailing mean (0.05–0.2) | 0.276–0.300 | median error rises; rejected |
| sqrt(h) exponent 0.4 / 0.6 | 0.284 / 0.283 | 0.5 best |
| Shrinkage of sigma toward pooled value (0.15–0.5) | 0.274–0.283 | hurts |
| EWMA |move| (halflife 120–720) | 0.293–0.325 | worse than flat windows |

Differences of ~±0.001 between the top few Gaussian variants are noise
across 6 cases; the chosen configuration sits in the middle of that
flat optimum rather than at an extreme, and uses two timescales so it
adapts if the final 48 h regime differs from practice.

## Format / runtime validation

- Ran `python3 main.py` on all 6 practice inputs
  (`MAKEFUN_INPUT_DIR=<kit>/input`): all 6 outputs valid — exactly one
  `forecasts` key, every market exactly once, 240 rows × 5 numbers,
  all in [0, 1], non-decreasing per row, files 184–249 KB (< 1 MiB).
- Determinism: two full runs byte-identical (`diff -r` clean).
- Runtime: 0.38 s for all 6 cases together; 0.10 s for a single case
  (p05, 24 markets) — far under the 8 s cap.
- Python 3.13, standard library only, no network, no randomness.
