# Polymarket NVIDIA CEO forecast — entry

Forecasts the Yes price of every market of Polymarket's "Next CEO of
NVIDIA?" event, minute by minute, 4 hours ahead, as five quantiles
(0.05, 0.25, 0.5, 0.75, 0.95). Python 3.13, standard library only, no
network. Run: `python3 main.py` with `MAKEFUN_INPUT_DIR` /
`MAKEFUN_OUTPUT_DIR` set (defaults `/input`, `/output`).

## Model

**Median = last price (persistence).** The prices behave as a
martingale over 4 hours: fitting a drift from the recent slope, and
pulling the median toward the trailing 24 h / 12 h mean, both raised the
practice pinball loss, so neither is used.

**Spread = per-market Gaussian in sqrt(h), with a peaked centre and
fat tails.** For each market:

```
sigma = 0.65 * mean(mean|1-min move| over last 1080 min,
                    mean|1-min move| over last 360 min)
sigma clamped to [0.0002, 0.01]
q_tau(h) = clamp(x + z_tau * shape_tau * sigma * sqrt(h), 0, 1)
shape = (1.30, 0.85, 1.0, 0.85, 1.30) for tau = (.05, .25, .5, .75, .95)
```

## Why (evidence from the 6 practice cases, scored locally against
Polymarket public history)

- Prices are extremely sticky: ~87% of 1-minute moves are exactly
  zero; the median 240-minute change is zero. One global sigma (the
  house baseline's 0.0025) is far too wide for quiet markets (some move
  ~0.00001/min) and too narrow for jumpy ones (~0.011/min). Per-market
  mean-|move| scaling is the whole win.
- Mean absolute move beats RMS / trimmed-RMS / 90th-percentile scales,
  which are dominated by rare jumps.
- Empirical h-step quantiles were tried and rejected (loss ~0.36, no
  better than baseline): they inherit the last regime's trend.
- Drift and mean-reversion median adjustments both hurt. sqrt(h)
  growth beats h^0.4 / h^0.6. Shrinkage toward pooled sigma hurt.
- The 1080/360 two-window blend beat either window alone on 4 of 6
  cases.

## Local practice results

| | pinball loss | median error | 90% coverage |
|---|---|---|---|
| This entry | **0.270707** | 0.7675 | 0.8762 |
| House baseline | 0.363589 | 0.7675 | 0.9496 |

Per-case losses: p00 0.463, p01 0.309, p02 0.360, p03 0.241,
p04 0.213, p05 0.103 — better than baseline on every case
(baseline: 0.536, 0.380, 0.408, 0.369, 0.299, 0.238).

See `VALIDATION.md` for the full validation report, including what was
tried and rejected.
