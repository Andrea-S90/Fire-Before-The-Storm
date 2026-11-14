#!/usr/bin/env python
"""Step 12: export small web-ready files for the story site (the data contract).

Writes to paths.web_out (default ../web/public/data):
  layers.json                 manifest of map overlays (PNG + lon/lat corners for a MapLibre image source)
  img/<layer>.png             colour-mapped overlays in Web Mercator
  towns.json                  one record per town/reservoir (step 10)
  towns.geojson, catchments.geojson, streams.geojson, water_points.geojson, burned_area.geojson (WGS84)
  hindcast.json, wind_rose.json, meta.json
"""
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import rasterio
from rasterio.warp import Resampling, calculate_default_transform, reproject, transform_bounds

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ashwatch.common import (LOG, cli, grid_from_config, load_config, path, read_json, read_raster,  # noqa: E402
                             setup_logging, write_json)

SEV_COLORS = {0: (0, 0, 0, 0), 1: (254, 224, 139, 200), 2: (244, 109, 67, 220), 3: (165, 0, 38, 235)}

LAYERS = [
    # id, file under work/, title, cmap, vmin, vmax, units, categorical
    ("hv_pre", "severity/hv_pre_db.tif", "NISAR HV before the fire", "gray", -25, -8, "dB", False),
    ("hv_post", "severity/hv_post_db.tif", "NISAR HV after the fire", "gray", -25, -8, "dB", False),
    ("dhv", "severity/dhv_db.tif", "Change in HV backscatter", "RdBu", -5, 5, "dB", False),
    ("severity", "severity/class.tif", "Burn severity", None, 0, 3, "class", True),
    ("biomass", "fuel/agb.tif", "Pre-fire biomass (fuel)", "Greens", 0, 150, "Mg/ha", False),
    ("ash", "ash/ash_t_ha.tif", "Ash load", "YlOrBr", 0, 8, "t/ha", False),
    ("erosion", "hydro/erosion_idx.tif", "Erosion index (relative)", "Oranges", 0, None, "index", False),
    ("gw_vuln", "groundwater/vulnerability.tif", "Groundwater vulnerability", "Blues", 0, 1, "0-1", False),
    ("wind_exposure", "wind/exposure.tif", "Downwind ash exposure (indicative)", "Purples", 0, 1, "0-1", False),
]


def to_mercator(src_path, max_px, categorical):
    with rasterio.open(src_path) as src:
        dst_crs = "EPSG:3857"
        tr, w, h = calculate_default_transform(src.crs, dst_crs, src.width, src.height, *src.bounds)
        scale = max(1.0, max(w, h) / max_px)
        w2, h2 = int(w / scale), int(h / scale)
        tr2 = tr * tr.scale(w / w2, h / h2)
        out = np.full((h2, w2), np.nan, "float32")
        srcarr = src.read(1).astype("float32")
        if src.nodata is not None and not np.isnan(src.nodata):
            srcarr[srcarr == src.nodata] = np.nan
        reproject(srcarr, out, src_transform=src.transform, src_crs=src.crs, src_nodata=np.nan,
                  dst_transform=tr2, dst_crs=dst_crs, dst_nodata=np.nan,
                  resampling=Resampling.nearest if categorical else Resampling.average)
        b = rasterio.transform.array_bounds(h2, w2, tr2)
        west, south, east, north = transform_bounds(dst_crs, "EPSG:4326", b[1], b[0], b[3], b[2])
    return out, [[west, north], [east, north], [east, south], [west, south]]


def colorize(a, cmap, vmin, vmax, categorical, clear_low=False):
    from matplotlib import colormaps
    rgba = np.zeros(a.shape + (4,), "uint8")
    ok = np.isfinite(a)
    if categorical:
        for k, col in SEV_COLORS.items():
            rgba[ok & (np.round(a) == k)] = col
        return rgba
    x = np.clip((a - vmin) / (vmax - vmin), 0, 1)
    rgba[ok] = (colormaps[cmap](x[ok]) * 255).astype("uint8")
    rgba[..., 3][ok] = 210
    if clear_low:   # no ash / no exposure -> transparent, so the base map shows through
        rgba[..., 3][ok & (x <= 0.02)] = 0
    return rgba


def reproject_geojson(gj, src_crs, nd=5):
    from pyproj import Transformer
    import shapely
    from shapely.geometry import mapping, shape
    tr = Transformer.from_crs(src_crs, "EPSG:4326", always_xy=True).transform
    feats = []
    for f in gj["features"]:
        g = shapely.transform(shape(f["geometry"]), lambda xy: np.column_stack(tr(xy[:, 0], xy[:, 1])))
        g = json.loads(json.dumps(mapping(g)), parse_float=lambda s: round(float(s), nd))
        feats.append({"type": "Feature", "geometry": g, "properties": f["properties"]})
    return {"type": "FeatureCollection", "features": feats}


def main():
    ap = cli(__doc__)
    args = ap.parse_args()
    setup_logging()
    cfg = load_config(args.config)
    grid = grid_from_config(cfg)
    web = Path(cfg["_web"])
    (web / "img").mkdir(parents=True, exist_ok=True)
    from PIL import Image

    manifest = []
    for lid, rel, title, cmap, vmin, vmax, units, cat in LAYERS:
        src = path(cfg, "work", rel, mkdir=False)
        if not src.exists():
            LOG.warning("skip layer %s (missing %s)", lid, rel)
            continue
        a, corners = to_mercator(src, cfg["export"]["max_png_px"], cat)
        if vmax is None:
            vmax = float(np.nanpercentile(a, 98)) if np.isfinite(a).any() else 1.0
        Image.fromarray(colorize(a, cmap, vmin, vmax, cat, clear_low=lid in ("ash", "erosion", "wind_exposure"))).save(web / "img" / f"{lid}.png", optimize=True)
        manifest.append(dict(id=lid, title=title, url=f"img/{lid}.png", coordinates=corners, units=units,
                             legend=dict(cmap=cmap, min=vmin, max=vmax) if not cat else
                             dict(classes=["unburned", "low", "moderate", "high"],
                                  colors=[f"rgba{SEV_COLORS[k]}" for k in range(4)])))
        LOG.info("layer %-14s %s", lid, (web / "img" / f"{lid}.png").stat().st_size // 1024)
    write_json(web / "layers.json", manifest, indent=1)

    # vectors
    crs = grid.crs.to_string()
    for src_rel, name in (("hydro/streams.geojson", "streams"), ("towns/catchments.geojson", "catchments"),
                          ("groundwater/points.geojson", "water_points")):
        p = path(cfg, "work", src_rel, mkdir=False)
        if not p.exists():
            continue
        gj = json.loads(p.read_text())
        if name == "streams":   # keep the network that matters: burned or large
            gj["features"] = [f for f in gj["features"] if (f["properties"].get("burned_share") or 0) > 0.01
                              or (f["properties"].get("area_km2") or 0) > 5]
        (web / f"{name}.geojson").write_text(json.dumps(reproject_geojson(gj, crs)))
        LOG.info("%s: %d features", name, len(gj["features"]))

    # burned area outline (from the severity map, simplified)
    sev = read_raster(path(cfg, "work", "severity", "class.tif"))
    from rasterio.features import shapes
    from shapely.geometry import mapping, shape
    from shapely.ops import unary_union
    m = np.nan_to_num(sev) >= 1
    polys = [shape(g) for g, v in shapes(m.astype("uint8"), mask=m, transform=grid.transform) if v == 1]
    if polys:
        u = unary_union(polys).buffer(grid.res).buffer(-grid.res).simplify(grid.res * 2)
        gj = {"type": "FeatureCollection", "features": [{"type": "Feature", "geometry": mapping(u), "properties": {}}]}
        (web / "burned_area.geojson").write_text(json.dumps(reproject_geojson(gj, crs)))

    towns_p = path(cfg, "work", "towns", "towns.json", mkdir=False)
    if towns_p.exists():
        towns = read_json(towns_p)
        shutil.copy(towns_p, web / "towns.json")
        (web / "towns.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": [
            {"type": "Feature", "geometry": {"type": "Point", "coordinates": [t["lon"], t["lat"]]},
             "properties": dict(id=t["id"], name=t["name"], kind=t["kind"], overall=t["overall"],
                                runoff=t["pathways"]["runoff"]["level"], debris_flow=t["pathways"]["debris_flow"]["level"],
                                groundwater=t["pathways"]["groundwater"]["level"], airborne=t["pathways"]["airborne"]["level"])}
            for t in towns]}))
    for src_rel, name in (("hindcast/hindcast.json", "hindcast.json"), ("wind/rose.json", "wind_rose.json")):
        p = path(cfg, "work", src_rel, mkdir=False)
        if p.exists():
            shutil.copy(p, web / name)

    meta = dict(generated=datetime.now(timezone.utc).isoformat(timespec="seconds"), config=cfg["name"],
                aoi_bbox=cfg["aoi"]["bbox"], dates={k: str(v) for k, v in cfg["dates"].items()})
    for k, rel in (("severity", "severity/metrics.json"), ("ash", "ash/summary.json"), ("hydro", "hydro/summary.json"),
                   ("wind", "wind/summary.json"), ("groundwater", "groundwater/summary.json")):
        p = path(cfg, "work", rel, mkdir=False)
        if p.exists():
            meta[k] = read_json(p)
    meta["sources"] = ["NASA-ISRO NISAR L2 GCOV (ASF DAAC)", "Copernicus Sentinel-2 L2A", "Copernicus DEM GLO-30",
                       "ESA CCI Biomass", "ISRIC SoilGrids", "ERA5 (Copernicus C3S)", "NASA GPM IMERG",
                       "OpenStreetMap contributors", "Staley et al. 2017 M1 model (USGS)"]
    write_json(web / "meta.json", meta, indent=1)
    total = sum(f.stat().st_size for f in web.rglob("*") if f.is_file())
    LOG.info("Web export: %s (%.1f MB)", web, total / 1e6)


if __name__ == "__main__":
    main()
