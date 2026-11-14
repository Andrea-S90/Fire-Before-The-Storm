"""Ash load: fuel x share consumed x ash fraction, with a Monte Carlo over the uncertain fractions."""
from __future__ import annotations

import numpy as np


def _mid(r):
    return 0.5 * (r[0] + r[1])


def ash_best_t_ha(agb_t_ha: np.ndarray, sev_class: np.ndarray, cfg_ash: dict) -> np.ndarray:
    """Best-estimate ash (t/ha) per pixel, using the midpoint of every range."""
    out = np.zeros_like(agb_t_ha, dtype="float32")
    surf = _mid(cfg_ash["surface_fuel_t_ha"])
    frac = _mid(cfg_ash["ash_fraction"])
    for c in (1, 2, 3):
        m = sev_class == c
        cons = np.nan_to_num(agb_t_ha[m]) * _mid(cfg_ash["agb_consumed"][c - 1]) + surf * _mid(cfg_ash["surface_consumed"][c - 1])
        out[m] = cons * frac
    out[~np.isfinite(agb_t_ha)] = np.nan
    return out


def ash_monte_carlo(agb_sum_by_class_t, area_ha_by_class, cfg_ash: dict, n=None, rng=None):
    """Ash (t) for one area, given total AGB (t) and burned area (ha) in classes 1..3.

    Draws every uncertain fraction uniformly from its range. Returns the draws (array of n).
    """
    n = n or int(cfg_ash.get("mc_draws", 5000))
    rng = rng or np.random.default_rng(cfg_ash.get("seed", 42))
    u = lambda r: rng.uniform(r[0], r[1], n)
    frac = u(cfg_ash["ash_fraction"])
    surf = u(cfg_ash["surface_fuel_t_ha"])
    total = np.zeros(n)
    for c in (1, 2, 3):
        total += agb_sum_by_class_t[c - 1] * u(cfg_ash["agb_consumed"][c - 1])
        total += area_ha_by_class[c - 1] * surf * u(cfg_ash["surface_consumed"][c - 1])
    return total * frac


def pctl(draws, qs=(10, 50, 90)):
    return {f"p{q}": float(np.percentile(draws, q)) for q in qs}
