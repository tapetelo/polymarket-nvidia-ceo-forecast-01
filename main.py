#!/usr/bin/env python3
"""Forecast Polymarket's "Next CEO of NVIDIA?" Yes prices, 4 hours ahead.

Model: persistence median with a per-market, two-timescale volatility.

For each market, the median forecast at every minute of the 240-minute
horizon is the market's price at the checkpoint: these prices are a
martingale to a good approximation (a drift fitted to the recent slope,
and a pull toward the trailing mean, both *raised* the practice pinball
loss, so neither is used).

The spread around the median is Gaussian in sqrt(h) with a per-market
sigma estimated from the mean absolute 1-minute move, averaged over two
trailing windows -- 1080 minutes (18 h, stable) and 360 minutes (6 h,
adapts when a market heats up or cools down):

    sigma = 0.65 * mean(mean|d| over last 1080 min, mean|d| over last 360 min)
    sigma clamped to [0.0002, 0.01]

Why this shape, from the practice data (six cases, 2026-11-12/13):

* Prices are extremely sticky: ~87% of 1-minute moves are exactly zero,
  and the median 240-minute change is zero. A single global sigma (the
  house baseline's 0.0025) is far too wide for the quiet markets (some
  move ~0.00001 a minute) and too narrow for the jumpy ones (up to
  ~0.011 a minute). Per-market mean-|move| scaling is the whole win:
  it cuts the practice loss from 0.363589 to ~0.271.
* Mean absolute move beats RMS / trimmed-RMS / 90th-percentile scales,
  which are dominated by rare jumps and over-widen the forecast.
* The move distribution is peaked with fat tails, not Gaussian: the
  25%/75% quantiles use a 0.85 factor and the 5%/95% quantiles a 1.30
  factor on the Gaussian z-spread. Empirical h-step quantiles were
  tried and rejected: they inherit the last regime's trend (their
  median is not the last price) and scored ~0.36, no better than baseline.
* sqrt(h) growth beats h^0.4 and h^0.6; shrinkage of sigma toward the
  pooled cross-market value hurt; the 1080/360 blend beat either window
  alone on 4 of 6 practice cases and never by much on the other two.

Practice score (local, against Polymarket public history fetched for
2026-11-12T06:00Z..2026-11-13T06:00Z): pinball loss 0.270707 vs the
house baseline's 0.363589, median error 0.7675, 90% coverage 0.8762.
Per-case losses: p00 0.463, p01 0.309, p02 0.360, p03 0.241, p04 0.213,
p05 0.103 -- better than baseline on every case.

Standard library only, no network, deterministic: the same case always
produces the same bytes.
"""

import json
import math
import os
from pathlib import Path

INPUT_DIR = os.environ.get("MAKEFUN_INPUT_DIR", "/input")
OUTPUT_DIR = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")

# The quantile levels the contest scores, in row order.
QUANTILES = (0.05, 0.25, 0.5, 0.75, 0.95)
# Standard normal quantiles at those levels.
Z = (-1.644854, -0.674490, 0.0, 0.674490, 1.644854)
# Shape factors per level: peaked centre (0.85), fat tails (1.30).
SHAPE = (1.30, 0.85, 1.0, 0.85, 1.30)

LONG_WINDOW = 1080   # minutes of history for the stable volatility estimate
SHORT_WINDOW = 360   # minutes of history for the recent volatility estimate
SCALE = 0.65         # mean-|move| -> Gaussian sigma multiplier
SIGMA_FLOOR = 0.0002  # per sqrt-minute; keeps dead-quiet markets forecastable
SIGMA_CAP = 0.01     # per sqrt-minute; keeps one jumpy day from exploding the spread


def clamp6(x):
    """Clamp to [0, 1] and round to 6 decimals (0, never -0)."""
    return round(min(1.0, max(0.0, x)), 6) + 0.0


def market_sigma(prices):
    """Per-market sigma from the mean absolute 1-minute move.

    One backwards pass accumulates the absolute moves for both windows.
    Markets with fewer than two prices (or none) fall back to the floor.
    """
    n = len(prices)
    if n < 2:
        return SIGMA_FLOOR
    long_n = min(LONG_WINDOW, n - 1)
    short_n = min(SHORT_WINDOW, n - 1)
    long_sum = 0.0
    short_sum = 0.0
    for i in range(long_n):
        move = abs(prices[n - 1 - i] - prices[n - 2 - i])
        long_sum += move
        if i < short_n:
            short_sum += move
    mad = 0.5 * (long_sum / long_n + short_sum / short_n)
    sigma = SCALE * mad
    if sigma < SIGMA_FLOOR:
        return SIGMA_FLOOR
    if sigma > SIGMA_CAP:
        return SIGMA_CAP
    return sigma

def forecast_rows(x, sigma, horizon):
    """240 rows of five quantiles around last price x.

    q_tau(h) = clamp6(x + z_tau * shape_tau * sigma * sqrt(h)).
    Rounding and clamping are monotone, so rows stay non-decreasing;
    the running max below guards the boundary cases anyway.
    """
    rows = []
    for h in range(1, horizon + 1):
        spread = sigma * math.sqrt(h)
        row = []
        prev = 0.0
        for z, shape in zip(Z, SHAPE):
            q = clamp6(x + z * shape * spread)
            if q < prev:
                q = prev
            row.append(q)
            prev = q
        rows.append(row)
    return rows


def forecast_case(case):
    """One case dict -> the {"forecasts": [...]} object for its output file."""
    horizon = case.get("horizon_minutes", 240)
    forecasts = []
    for market in case["markets"]:
        prices = market["prices"]
        x = prices[-1] if prices else 0.0
        sigma = market_sigma(prices)
        forecasts.append({"id": market["id"], "q": forecast_rows(x, sigma, horizon)})
    return {"forecasts": forecasts}


def main():
    input_dir = Path(INPUT_DIR)
    output_dir = Path(OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)
    inputs = sorted(p for p in input_dir.iterdir() if p.name.endswith(".in"))
    for path in inputs:
        case_id = path.name[: -len(".in")]
        with open(path, "r", encoding="utf-8") as f:
            case = json.load(f)
        out = forecast_case(case)
        text = json.dumps(out, separators=(",", ":")) + "\n"
        with open(output_dir / (case_id + ".out"), "w", encoding="utf-8") as f:
            f.write(text)


if __name__ == "__main__":
    main()
