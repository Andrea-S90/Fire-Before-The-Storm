"""Access to the gridded NISAR stack written by step 04."""
from __future__ import annotations

import csv
from collections import defaultdict
from datetime import date

import numpy as np

from .common import db, path, read_raster


def load_index(cfg):
    p = path(cfg, "work", "nisar", "index.csv")
    if not p.exists():
        raise SystemExit("No NISAR stack: run steps/04_nisar_stack.py")
    with open(p) as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["date"] = date.fromisoformat(r["date"])
    return rows


def by_pass(rows):
    out = defaultdict(list)
    for r in rows:
        out[r["key"]].append(r)
    return out


def period_mean(cfg, rows, pol, d0, d1):
    """Mean linear power over dates d0 <= date < d1 (None if no dates). Returns (array, n_dates)."""
    sel = [r for r in rows if d0 <= r["date"] < d1 and r.get(pol)]
    if not sel:
        return None, 0
    arrs = [read_raster(path(cfg, "work", "nisar", r[pol])) for r in sel]
    with np.errstate(invalid="ignore"):
        return np.nanmean(np.stack(arrs), axis=0), len(sel)


def change_db(cfg, rows, pol, pre, post, normalize=False):
    """Per-pass change (post/pre, dB) averaged across passes, weighted by dates used.

    Comparing each pass only with itself keeps the viewing geometry identical.
    normalize=True subtracts each pass's median change over the whole scene first, so that what is left is
    change relative to the landscape (summer drying, calibration drift and soil moisture shift every pixel;
    a fire is a small share of the scene and does not move the median).
    Returns (change_db, pre_db, post_db, passes_used).
    """
    num = den = None
    pre_acc = post_acc = None
    used = []
    for key, rr in by_pass(rows).items():
        a0, n0 = period_mean(cfg, rr, pol, *pre)
        a1, n1 = period_mean(cfg, rr, pol, *post)
        if a0 is None or a1 is None:
            continue
        wgt = min(n0, n1)
        ch = db(a1) - db(a0)
        offset = float(np.nanmedian(ch)) if normalize and np.isfinite(ch).any() else 0.0
        ch = ch - offset
        ok = np.isfinite(ch)
        if num is None:
            num = np.zeros_like(ch)
            den = np.zeros_like(ch)
            pre_acc = np.zeros_like(ch)
            post_acc = np.zeros_like(ch)
        num[ok] += wgt * ch[ok]
        pre_acc[ok] += wgt * db(a0)[ok]
        post_acc[ok] += wgt * db(a1)[ok]
        den[ok] += wgt
        used.append(dict(key=key, pre_dates=n0, post_dates=n1, scene_median_db=round(offset, 2)))
    if num is None:
        raise SystemExit(f"No pass has {pol} both before and after the fire: check dates in the config")
    with np.errstate(invalid="ignore", divide="ignore"):
        return num / den, pre_acc / den, post_acc / den, used
