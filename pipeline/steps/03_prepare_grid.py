#!/usr/bin/env python
"""Step 03: put every non-radar input on the common analysis grid.

Outputs in data/work/grid/: dem, dnbr (+ nbr_pre, nbr_post), agb_cci, sand/silt/clay/soc, kf,
and optionally wtd (water-table depth), logk (permeability), perimeter.
"""
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from rasterio.warp import Resampling

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ashwatch.common import (LOG, cli, grid_from_config, load_config, mosaic_to_grid, path,  # noqa: E402
                             setup_logging, to_grid, write_json, write_raster)
from ashwatch.hydro import epic_k  # noqa: E402

# no data, saturated, clouds, cirrus, snow. Cloud shadow (3) is NOT masked: Sen2Cor labels fresh burn scars as
# shadow or dark area, which would remove dNBR exactly where it matters. Step 05 only accepts a dNBR burn where
# the radar also shows a drop, so a real cloud shadow cannot create a burn on its own.
BAD_SCL = {0, 1, 8, 9, 10, 11}


def s2_composite(cfg, grid, period):
    folder = path(cfg, "raw", "s2", period, "x").parent
    items = defaultdict(dict)
    for f in folder.glob("*.tif"):
        stem = f.stem
        for key in ("nir08", "swir22", "scl"):
            if stem.endswith("_" + key):
                items[stem[: -len(key) - 1]][key] = f
    nbrs = []
    for iid, d in items.items():
        if not {"nir08", "swir22", "scl"} <= d.keys():
            continue
        # Earth Search L2A (processing baseline >= 04.00): reflectance = DN * 1e-4 - 0.1
        nir = to_grid(d["nir08"], grid, Resampling.bilinear, src_nodata=0) * 1e-4 - 0.1
        sw = to_grid(d["swir22"], grid, Resampling.bilinear, src_nodata=0) * 1e-4 - 0.1
        scl = to_grid(d["scl"], grid, Resampling.nearest, src_nodata=0)
        bad = np.isnan(scl) | np.isin(np.nan_to_num(scl, nan=0).astype(int), list(BAD_SCL))
        with np.errstate(invalid="ignore", divide="ignore"):
            nbr = (nir - sw) / (nir + sw)
        nbr[bad] = np.nan
        nbrs.append(nbr)
        LOG.info("  S2 %s %s: %.0f%% clear", period, iid, 100 * np.isfinite(nbr).mean())
    if not nbrs:
        return None
    return np.nanmedian(np.stack(nbrs), axis=0)


def main():
    ap = cli(__doc__)
    args = ap.parse_args()
    setup_logging()
    cfg = load_config(args.config)
    grid = grid_from_config(cfg)
    out = lambda name: path(cfg, "work", "grid", f"{name}.tif")  # noqa: E731
    write_json(path(cfg, "work", "grid", "grid.json"),
               dict(crs=grid.crs.to_string(), transform=list(grid.transform)[:6], width=grid.width, height=grid.height))
    LOG.info("Grid %s: %d x %d at %.0f m", grid.crs, grid.width, grid.height, grid.res)

    # DEM
    tiles = sorted(path(cfg, "raw", "dem", "x").parent.glob("*.tif"))
    if not tiles:
        raise SystemExit("No DEM tiles in data/raw/dem: run steps/02_download_ancillary.py dem")
    dem = mosaic_to_grid(tiles, grid, Resampling.bilinear)
    write_raster(out("dem"), dem, grid, desc="Copernicus DEM GLO-30 (m)")
    LOG.info("DEM: %.0f-%.0f m", np.nanmin(dem), np.nanmax(dem))

    # Sentinel-2 dNBR
    pre, post = s2_composite(cfg, grid, "pre"), s2_composite(cfg, grid, "post")
    if pre is not None and post is not None:
        dnbr = (pre - post) * 1000
        write_raster(out("nbr_pre"), pre, grid)
        write_raster(out("nbr_post"), post, grid)
        write_raster(out("dnbr"), dnbr, grid, desc="dNBR x 1000 (Sentinel-2)")
        LOG.info("dNBR valid on %.0f%% of the grid", 100 * np.isfinite(dnbr).mean())
    else:
        LOG.warning("No Sentinel-2 composites: severity will use radar thresholds only")

    # ESA CCI biomass
    cci = sorted(path(cfg, "raw", "cci", "x").parent.glob("*.tif"))
    cci = [c for c in cci if "_SD" not in c.name.upper()]
    if cci:
        agb = mosaic_to_grid(cci, grid, Resampling.bilinear)
        write_raster(out("agb_cci"), agb, grid, desc="ESA CCI Biomass AGB (Mg/ha)")
    else:
        LOG.warning("No CCI biomass tiles: fuel step will use the fallback HV scaling")

    # Soil and erodibility
    soil = {}
    for var in ("sand", "silt", "clay", "soc"):
        f = path(cfg, "raw", "soil", f"{var}_0-5cm.tif")
        if f.exists():
            soil[var] = to_grid(f, grid, Resampling.bilinear)
    if {"sand", "silt", "clay"} <= soil.keys():
        sand, silt, clay = soil["sand"] / 10, soil["silt"] / 10, soil["clay"] / 10   # g/kg -> %
        soc = soil["soc"] / 100 if "soc" in soil else np.full(grid.shape, 1.5)        # dg/kg -> %
        for name, a in (("sand", sand), ("silt", silt), ("clay", clay), ("soc", soc)):
            write_raster(out(name), a, grid)
        kf = epic_k(sand, silt, clay, soc)
        write_raster(out("kf"), kf, grid, desc="EPIC soil erodibility, US units (KF scale)")
        LOG.info("KF median %.2f", np.nanmedian(kf))
    else:
        LOG.warning("No SoilGrids data: KF set to 0.25 everywhere (ASSUMPTION)")
        write_raster(out("kf"), np.full(grid.shape, 0.25, "float32"), grid)

    # Optional: water-table depth (Fan et al. 2013) in raw/groundwater/*.nc|*.tif
    gw = path(cfg, "raw", "groundwater", "x").parent
    for f in sorted(gw.glob("*.nc")) + sorted(gw.glob("*wtd*.tif")):
        src = f'NETCDF:"{f}":WTD' if f.suffix == ".nc" else str(f)
        try:
            w = np.abs(to_grid(src, grid, Resampling.bilinear))
            write_raster(out("wtd"), w, grid, desc="Water-table depth (m)")
            LOG.info("Water-table depth from %s", f.name)
            break
        except Exception as ex:  # noqa: BLE001
            LOG.warning("Could not read %s: %s", f, ex)

    # Optional: GLHYMPS permeability polygons in raw/groundwater/glhymps.*
    for f in sorted(gw.glob("glhymps*.gpkg")) + sorted(gw.glob("glhymps*.shp")):
        import geopandas as gpd
        from rasterio.features import rasterize
        g = gpd.read_file(f, bbox=tuple(cfg["aoi"]["bbox"])).to_crs(grid.crs)
        col = next(c for c in g.columns if c.lower().startswith("logk_ferr"))
        r = rasterize(((geom, v / 100.0) for geom, v in zip(g.geometry, g[col])), out_shape=grid.shape,
                      transform=grid.transform, fill=np.nan, dtype="float32")
        write_raster(out("logk"), r, grid, desc="log10 permeability (m2), GLHYMPS")
        break

    # Optional: official fire perimeter in raw/effis/*
    eff = path(cfg, "raw", "effis", "x").parent
    for f in sorted(eff.glob("*.gpkg")) + sorted(eff.glob("*.shp")) + sorted(eff.glob("*.geojson")):
        import geopandas as gpd
        from rasterio.features import rasterize
        g = gpd.read_file(f).to_crs(grid.crs)
        r = rasterize(((geom, 1) for geom in g.geometry), out_shape=grid.shape, transform=grid.transform,
                      fill=0, dtype="uint8")
        write_raster(out("perimeter"), r, grid, nodata=255, dtype="uint8", desc="EFFIS perimeter")
        LOG.info("Perimeter from %s: %.0f km2", f.name, r.sum() * grid.res ** 2 / 1e6)
        break
    LOG.info("Done")


if __name__ == "__main__":
    main()
