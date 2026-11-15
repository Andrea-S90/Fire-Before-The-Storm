#!/usr/bin/env python
"""Step 05: pre-fire fuel (biomass) and burn severity from NISAR, checked against Sentinel-2.

Fuel:     pre-fire HV (dB) -> AGB with a power law fitted on ESA CCI pixels (log AGB = a + b * HV_dB).
Severity: per-pass HV and HH change (post-fire vs pre-fire mean). A random forest learns Sentinel-2
          dNBR classes from the radar features on cloud/smoke-free pixels, then maps every pixel.
          Without dNBR, fixed HV-change breaks from the config are used.
Outputs (data/work/): fuel/agb.tif, fuel/saturated.tif, severity/{dhv_db,dhh_db,hv_pre_db,hv_post_db,
          class,prob}.tif, severity/metrics.json
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ashwatch.common import (LOG, cli, grid_from_config, load_config, n_workers, path,  # noqa: E402
                             read_raster, setup_logging, write_json, write_raster)
from ashwatch.stack import change_db, load_index  # noqa: E402

CLASSES = ["unburned", "low", "moderate", "high"]


def classify_dnbr(dnbr, breaks):
    c = np.digitize(dnbr, breaks).astype("float32")
    c[~np.isfinite(dnbr)] = np.nan
    return c


def main():
    ap = cli(__doc__)
    args = ap.parse_args()
    setup_logging()
    cfg = load_config(args.config)
    grid = grid_from_config(cfg)
    d = cfg["dates"]
    rows = load_index(cfg)
    pre, post = (d["pre_start"], d["fire_start"]), (d["post_start"], d["post_end"])
    metrics = dict(pre_window=pre, post_window=post)

    dhv, hv_pre, hv_post, used = change_db(cfg, rows, "HV", pre, post, normalize=True)
    dhh, hh_pre, hh_post, _ = change_db(cfg, rows, "HH", pre, post, normalize=True)
    metrics["passes"] = used
    for name, a in (("dhv_db", dhv), ("dhh_db", dhh), ("hv_pre_db", hv_pre), ("hv_post_db", hv_post),
                    ("hh_pre_db", hh_pre), ("hh_post_db", hh_post)):
        write_raster(path(cfg, "work", "severity", f"{name}.tif"), a, grid)
    LOG.info("HV change: median %.2f dB, 5th pct %.2f dB", np.nanmedian(dhv), np.nanpercentile(dhv, 5))

    # ---------------- fuel
    fc = cfg["fuel"]
    cci_p = path(cfg, "work", "grid", "agb_cci.tif")
    if cci_p.exists():
        from sklearn.linear_model import HuberRegressor
        cci = read_raster(cci_p)
        ok = np.isfinite(cci) & np.isfinite(hv_pre) & (cci >= fc["fit_agb_min"]) & (cci <= fc["fit_agb_max"])
        idx = np.flatnonzero(ok)
        rng = np.random.default_rng(0)
        idx = rng.choice(idx, size=min(200_000, idx.size), replace=False)
        X, y = hv_pre.ravel()[idx, None], np.log(cci.ravel()[idx])
        model = HuberRegressor(max_iter=500).fit(X, y)
        a, b = float(model.intercept_), float(model.coef_[0])
        agb = np.exp(a + b * hv_pre)
        r2 = float(np.corrcoef(np.exp(model.predict(X)), np.exp(y))[0, 1] ** 2)
        metrics["fuel"] = dict(method="HV power law fitted on ESA CCI", a=a, b=b, r2=r2, n=int(idx.size))
        LOG.info("Fuel model: ln(AGB) = %.3f + %.3f * HV_dB  (R2 = %.2f, n = %d)", a, b, r2, idx.size)
    else:
        lo, hi = fc["fallback_hv_db_range"]
        agb = np.clip((hv_pre - lo) / (hi - lo), 0, 1) * fc["fallback_max_agb"]
        metrics["fuel"] = dict(method="fallback linear HV scaling (ASSUMPTION, no CCI)")
        LOG.warning("No CCI: fallback fuel scaling")
    agb = np.clip(agb, 0, fc["max_agb"]).astype("float32")
    write_raster(path(cfg, "work", "fuel", "agb.tif"), agb, grid, desc="Pre-fire AGB from NISAR HV (Mg/ha)")
    sat = (agb > fc["saturation_mg_ha"]).astype("uint8")
    write_raster(path(cfg, "work", "fuel", "saturated.tif"), sat, grid, nodata=255, dtype="uint8")
    metrics["fuel"]["saturated_share"] = float(sat[np.isfinite(hv_pre)].mean())

    # ---------------- severity
    # A pixel counts as burned only where the radar and, where it can see the ground, Sentinel-2 agree:
    #   radar    smoothed HV change (relative to the landscape median) at or below severity.burn_dhv_db
    #   optical  dNBR at or above the first break; under cloud or smoke the radar decides alone
    # and only in patches of at least severity.min_burn_patch_ha (and inside the official perimeter if given).
    # Inside the burn the class comes from dNBR; where dNBR is missing, a random forest trained on the
    # burned pixels predicts the class from the radar features.
    from scipy.ndimage import binary_dilation, label, median_filter
    sc = cfg["severity"]
    gate_db = float(sc.get("burn_dhv_db", -1.0))
    px_ha = grid.res ** 2 / 1e4
    seen = np.isfinite(dhv)
    dhv_s = median_filter(np.nan_to_num(dhv, nan=0.0), size=5)        # 5 x 5 median against speckle
    # water and bare ground have no canopy to lose: HV too low before the fire -> never burned
    seen_veg = seen & (hv_pre >= float(sc.get("min_hv_pre_db", -23.0)))
    radar_burn = seen_veg & (dhv_s <= gate_db)
    radar_burn_strict = seen_veg & (dhv_s <= float(sc.get("burn_dhv_radar_only_db", -2.0)))
    dnbr_p = path(cfg, "work", "grid", "dnbr.tif")
    dnbr = read_raster(dnbr_p) if dnbr_p.exists() else None
    if dnbr is not None:
        has_opt = np.isfinite(dnbr)
        opt_burn = has_opt & (dnbr >= sc["dnbr_breaks"][0])
        burn = (radar_burn & opt_burn) | (radar_burn_strict & ~has_opt)   # radar alone needs a clearer drop
    else:
        has_opt = np.zeros(grid.shape, bool)
        burn = radar_burn_strict
    perim_p = path(cfg, "work", "grid", "perimeter.tif")
    if perim_p.exists():   # nothing is burned outside the official perimeter (+ ~500 m)
        per = binary_dilation(read_raster(perim_p) > 0, iterations=max(1, int(500 / grid.res)))
        burn &= per
    lab, _ = label(burn)                                              # drop small isolated patches
    sizes = np.bincount(lab.ravel())
    keep = sizes >= max(2, int(float(sc.get("min_burn_patch_ha", 5)) / px_ha))
    keep[0] = False
    burn = keep[lab]

    def radar_class(a):   # fixed HV-change breaks (more negative = more severe); at least "low" inside the burn
        br = sc["dhv_breaks_db"]
        return 1 + (a <= br[1]).astype("float32") + (a <= br[2]).astype("float32")

    sev = np.where(seen, 0, np.nan).astype("float32")
    prob = np.full(grid.shape, np.nan, "float32")
    info = dict(method="burned where NISAR HV drop and Sentinel-2 dNBR agree; class from dNBR, "
                       "random forest on NISAR features where dNBR is missing",
                burn_dhv_db=gate_db, burn_dhv_radar_only_db=sc.get("burn_dhv_radar_only_db", -2.0),
                min_hv_pre_db=sc.get("min_hv_pre_db", -23.0), min_burn_patch_ha=sc.get("min_burn_patch_ha", 5),
                perimeter_used=perim_p.exists())
    if dnbr is None:
        sev[burn] = radar_class(dhv_s)[burn]
        info["method"] = "NISAR HV drop only, classes from fixed HV-change breaks (ASSUMPTION, no dNBR)"
    else:
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.metrics import cohen_kappa_score, confusion_matrix
        cls = np.clip(np.digitize(np.nan_to_num(dnbr), sc["dnbr_breaks"]), 1, 3).astype("float32")
        opt = burn & has_opt
        gap = burn & ~has_opt
        sev[opt] = cls[opt]
        # how well the radar alone finds the burn, judged against dNBR on clear pixels
        both = seen & has_opt
        r, o = radar_burn[both], opt_burn[both]
        info["radar_vs_optical"] = dict(
            agreement=float((r == o).mean()), kappa=float(cohen_kappa_score(o, r)) if o.any() and r.any() else None,
            both_ha=float((r & o).sum() * px_ha), radar_only_ha=float((r & ~o).sum() * px_ha),
            optical_only_ha=float((~r & o).sum() * px_ha),
            note="optical-only is mostly summer drying and harvest, not fire")
        feats = np.stack([dhv, dhh, dhv - dhh, hv_pre, hh_pre]).reshape(5, -1).T
        valid = np.all(np.isfinite(feats), axis=1)
        labels = cls.ravel()
        train = np.flatnonzero(opt.ravel() & valid)
        present = [c for c in (1, 2, 3) if (labels[train] == c).sum() >= 50]
        if len(present) >= 2:
            rng = np.random.default_rng(1)
            per_class = sc["rf_samples"] // 3
            pick = np.concatenate([rng.choice(train[labels[train] == c],
                                              size=min(per_class, int((labels[train] == c).sum())), replace=False)
                                   for c in present])
            rng.shuffle(pick)
            cut = int(0.7 * pick.size)
            tr, te = pick[:cut], pick[cut:]
            rf = RandomForestClassifier(n_estimators=200, max_depth=14, min_samples_leaf=5, n_jobs=n_workers(),
                                        class_weight="balanced", random_state=0)
            rf.fit(feats[tr], labels[tr].astype(int))
            pred_te = rf.predict(feats[te])
            info["radar_class_model"] = dict(
                holdout_accuracy=float((pred_te == labels[te].astype(int)).mean()),
                kappa=float(cohen_kappa_score(labels[te].astype(int), pred_te)),
                confusion=confusion_matrix(labels[te].astype(int), pred_te, labels=list(rf.classes_)).tolist(),
                classes=[CLASSES[int(c)] for c in rf.classes_], n_train=int(tr.size),
                feature_importance=dict(zip(["dHV", "dHH", "dHV-dHH", "HV_pre", "HH_pre"],
                                            rf.feature_importances_.round(3).tolist())))
            gi = np.flatnonzero(gap.ravel() & valid)
            if gi.size:
                p = rf.predict_proba(feats[gi])
                sev.ravel()[gi] = np.asarray(rf.classes_)[p.argmax(axis=1)]
                prob.ravel()[gi] = p.max(axis=1)
            rest = gap & ~valid.reshape(grid.shape)
            LOG.info("Radar class model: accuracy %.2f, kappa %.2f (holdout n=%d)",
                     info["radar_class_model"]["holdout_accuracy"], info["radar_class_model"]["kappa"], te.size)
        else:
            rest = gap
        sev[rest] = radar_class(dhv_s)[rest]
        info["burned_ha_class_from"] = dict(dnbr=float(opt.sum() * px_ha), radar=float(gap.sum() * px_ha))
    metrics["severity"] = info

    write_raster(path(cfg, "work", "severity", "class.tif"), np.nan_to_num(sev, nan=255).astype("uint8"), grid,
                 nodata=255, dtype="uint8", desc="0 unburned, 1 low, 2 moderate, 3 high")
    write_raster(path(cfg, "work", "severity", "prob.tif"), prob, grid)
    metrics["burned_ha"] = {CLASSES[c]: float((sev == c).sum() * px_ha) for c in range(1, 4)}
    write_json(path(cfg, "work", "severity", "metrics.json"), metrics, indent=1)
    LOG.info("Burned area (ha): %s", {k: round(v) for k, v in metrics["burned_ha"].items()})


if __name__ == "__main__":
    main()
