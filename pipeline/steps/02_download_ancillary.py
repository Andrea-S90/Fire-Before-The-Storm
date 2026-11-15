#!/usr/bin/env python
"""Step 02: download every non-NISAR input for the AOI.

  python steps/02_download_ancillary.py all            # everything below, continues past failures
  python steps/02_download_ancillary.py dem s2 osm     # just some sources

Sources and credentials:
  dem    Copernicus DEM GLO-30 tiles (AWS open data, no login)
  s2     Sentinel-2 L2A B8A, B12, SCL subsets via the Earth Search STAC (no login)
  cci    ESA CCI Biomass AGB 100 m tiles from CEDA (no login)
  soil   SoilGrids sand/silt/clay/soc 0-5 cm, read remotely and resampled to the grid (no login)
  osm    Towns, springs, wells, water works, reservoirs from the Overpass API (no login)
  era5   Hourly 10 m wind + precipitation (needs ~/.cdsapirc, see README)
  imerg  GPM IMERG half-hourly precipitation (Earthdata login, ~/.netrc or env vars)
  wtd    Optional global water-table depth if downloads.wtd_url is set
"""
import json
import math
import re
import sys
from pathlib import Path

import numpy as np
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ashwatch.common import (LOG, cli, earthdata_token, grid_from_config, load_config, path, setup_logging,  # noqa: E402
                             to_grid, write_raster)

UA = {"User-Agent": "AshWatch/1.0 (NASA Space Apps 2026)"}


def fetch(url, dest: Path, chunk=1 << 20, headers=None):
    if dest.exists() and dest.stat().st_size > 0:
        LOG.info("  have %s", dest.name)
        return dest
    with requests.get(url, stream=True, timeout=120, headers={**UA, **(headers or {})}) as r:
        if r.status_code == 404:
            LOG.warning("  404 %s", url)
            return None
        r.raise_for_status()
        tmp = dest.with_suffix(dest.suffix + ".part")
        with open(tmp, "wb") as f:
            for b in r.iter_content(chunk):
                f.write(b)
        tmp.rename(dest)
    LOG.info("  got %s", dest.name)
    return dest


# --------------------------------------------------------------------------- DEM
def dem(cfg):
    w, s, e, n = cfg["aoi"]["bbox"]
    pad = 0.05
    base = cfg["downloads"]["dem_base"]
    urls = []
    for lat in range(math.floor(s - pad), math.floor(n + pad) + 1):
        for lon in range(math.floor(w - pad), math.floor(e + pad) + 1):
            ns, ew = ("N" if lat >= 0 else "S"), ("E" if lon >= 0 else "W")
            name = f"Copernicus_DSM_COG_10_{ns}{abs(lat):02d}_00_{ew}{abs(lon):03d}_00_DEM"
            urls.append(f"{base}/{name}/{name}.tif")
    out = path(cfg, "raw", "dem", "x").parent
    (out / "urls.txt").write_text("\n".join(urls) + "\n")
    for u in urls:
        fetch(u, out / Path(u).name)


# --------------------------------------------------------------------------- Sentinel-2
def s2(cfg):
    import rasterio
    from pystac_client import Client
    from rasterio.warp import transform_bounds
    from rasterio.windows import from_bounds

    sc = cfg["sentinel2"]
    bbox = cfg["aoi"]["bbox"]
    cat = Client.open(sc["stac_url"])
    env = rasterio.Env(AWS_NO_SIGN_REQUEST="YES", GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
                       GDAL_HTTP_MAX_RETRY="4", GDAL_HTTP_RETRY_DELAY="2")
    with env:
        for period in ("pre", "post"):
            t0, t1 = cfg["dates"][f"s2_{period}"]
            items = list(cat.search(collections=[sc["collection"]], bbox=bbox, datetime=f"{t0}/{t1}",
                                    query={"eo:cloud_cover": {"lt": sc["max_cloud"]}}).items())
            items.sort(key=lambda it: it.properties.get("eo:cloud_cover", 100))
            items = items[: sc["max_items_per_period"]]
            LOG.info("S2 %s: %d items", period, len(items))
            out = path(cfg, "raw", "s2", period, "x").parent
            for it in items:
                for key in sc["assets"]:
                    dest = out / f"{it.id}_{key}.tif"
                    if dest.exists():
                        continue
                    href = it.assets[key].href
                    with rasterio.open(href) as src:
                        b = transform_bounds("EPSG:4326", src.crs, *bbox, densify_pts=21)
                        win = from_bounds(*b, transform=src.transform).round_offsets().round_lengths()
                        win = win.intersection(rasterio.windows.Window(0, 0, src.width, src.height))
                        data = src.read(1, window=win)
                        prof = src.profile.copy()
                        prof.update(driver="GTiff", height=data.shape[0], width=data.shape[1],
                                    transform=src.window_transform(win), compress="deflate", tiled=True)
                        with rasterio.open(dest, "w", **prof) as dst:
                            dst.write(data, 1)
                    LOG.info("  %s", dest.name)


# --------------------------------------------------------------------------- ESA CCI Biomass
def cci(cfg):
    import rasterio
    base = cfg["downloads"]["cci_base"]
    w, s, e, n = cfg["aoi"]["bbox"]
    out = path(cfg, "raw", "cci", "x").parent
    try:
        html = requests.get(base, timeout=60, headers=UA).text
    except Exception as ex:  # noqa: BLE001
        raise SystemExit(f"Could not list {base}: {ex}. Download the AGB tile by hand into {out}")
    names = sorted(set(re.findall(r"([NS]\d{2}[EW]\d{3}_ESACCI-BIOMASS-L4-AGB-MERGED-100m-\d{4}-fv[\d.]+\.tif)", html)))
    if not names:
        raise SystemExit(f"No AGB tiles listed at {base}. Download the tile covering the AOI by hand into {out}")

    def corner(nm):
        lat = int(nm[1:3]) * (1 if nm[0] == "N" else -1)
        lon = int(nm[4:7]) * (1 if nm[3] == "E" else -1)
        return lat, lon

    picks = []
    for nm in names:
        lat, lon = corner(nm)
        lon_ok = lon <= e and lon + 10 >= w
        if lon_ok and ((lat - 10 <= n and lat >= s) or (lat <= n and lat + 10 >= s)):  # either naming convention
            picks.append(nm)
    LOG.info("CCI candidate tiles: %s", picks)
    for nm in picks:
        dest = fetch(base + nm, out / nm)
        if dest:
            with rasterio.open(dest) as src:
                from rasterio.warp import transform_bounds
                b = transform_bounds(src.crs, "EPSG:4326", *src.bounds)
            if b[0] > e or b[2] < w or b[1] > n or b[3] < s:
                LOG.info("  %s does not cover the AOI, removing", nm)
                dest.unlink()


# --------------------------------------------------------------------------- SoilGrids
def soil(cfg):
    grid = grid_from_config(cfg)
    base = cfg["downloads"]["soilgrids_base"]
    for var in ("sand", "silt", "clay", "soc"):
        dest = path(cfg, "raw", "soil", f"{var}_0-5cm.tif")
        if dest.exists():
            continue
        url = f"/vsicurl?max_retry=3&retry_delay=1&list_dir=no&url={base}/{var}/{var}_0-5cm_mean.vrt"
        LOG.info("SoilGrids %s -> grid", var)
        a = to_grid(url, grid)
        write_raster(dest, a, grid, desc=f"SoilGrids {var} 0-5cm mean (native units)")


# --------------------------------------------------------------------------- OSM
def osm(cfg):
    from shapely.geometry import LineString, Polygon, mapping
    from shapely.ops import polygonize, unary_union

    w, s, e, n = cfg["aoi"]["bbox"]
    bb = f"{s},{w},{n},{e}"
    q = f"""[out:json][timeout:300];
(
  node["place"~"^(city|town|village|hamlet)$"]({bb});
  node["natural"="spring"]({bb});
  node["man_made"~"^(water_well|water_works|water_tower|reservoir_covered|pumping_station)$"]({bb});
  way["man_made"~"^(water_works|reservoir_covered)$"]({bb});
  node["amenity"="drinking_water"]({bb});
  way["water"="reservoir"]({bb});
  relation["water"="reservoir"]({bb});
  way["landuse"="reservoir"]({bb});
);
out geom tags;"""
    r = requests.post(cfg["downloads"]["overpass_url"], data={"data": q}, timeout=400, headers=UA)
    r.raise_for_status()
    feats = []
    for el in r.json()["elements"]:
        tags = el.get("tags", {})
        geom = None
        if el["type"] == "node":
            geom = {"type": "Point", "coordinates": [el["lon"], el["lat"]]}
        elif el["type"] == "way" and el.get("geometry"):
            pts = [(p["lon"], p["lat"]) for p in el["geometry"]]
            geom = mapping(Polygon(pts)) if len(pts) > 3 and pts[0] == pts[-1] else mapping(LineString(pts))
        elif el["type"] == "relation":
            lines = [LineString([(p["lon"], p["lat"]) for p in m["geometry"]])
                     for m in el.get("members", []) if m.get("role") == "outer" and m.get("geometry")]
            polys = list(polygonize(unary_union(lines))) if lines else []
            if polys:
                geom = mapping(unary_union(polys))
        if geom:
            feats.append({"type": "Feature", "geometry": geom,
                          "properties": {**tags, "osm_id": f"{el['type']}/{el['id']}"}})
    dest = path(cfg, "raw", "osm", "osm.geojson")
    dest.write_text(json.dumps({"type": "FeatureCollection", "features": feats}))
    LOG.info("OSM: %d features -> %s", len(feats), dest)


# --------------------------------------------------------------------------- ERA5
def era5(cfg):
    import cdsapi
    from datetime import timedelta
    d0, d1 = cfg["dates"]["era5_start"], cfg["dates"]["era5_end"]
    w, s, e, n = cfg["aoi"]["bbox"]
    days, d = [], d0
    while d <= d1:
        days.append(d)
        d += timedelta(days=1)
    c = cdsapi.Client()
    for ym in sorted({(x.year, x.month) for x in days}):
        dest = path(cfg, "raw", "era5", f"era5_{ym[0]}{ym[1]:02d}.nc")
        if dest.exists():
            unzip_era5(dest)     # a file from an earlier run may still be a zip
            continue
        req = {"product_type": ["reanalysis"],
               "variable": ["10m_u_component_of_wind", "10m_v_component_of_wind", "total_precipitation"],
               "year": [str(ym[0])], "month": [f"{ym[1]:02d}"],
               "day": sorted({f"{x.day:02d}" for x in days if (x.year, x.month) == ym}),
               "time": [f"{h:02d}:00" for h in range(24)],
               "area": [n + 0.5, w - 0.5, s - 0.5, e + 0.5], "data_format": "netcdf", "download_format": "unarchived"}
        LOG.info("ERA5 %s-%02d", *ym)
        c.retrieve("reanalysis-era5-single-levels", req, str(dest))
        unzip_era5(dest)


def unzip_era5(dest: Path):
    """The CDS sends a zip when a request mixes instantaneous (wind) and accumulated (rain) variables:
    one netCDF per kind. Merge them into the single netCDF that step 08 reads. No-op for a real netCDF."""
    import tempfile
    import zipfile

    import xarray as xr
    if not zipfile.is_zipfile(dest):
        return
    with tempfile.TemporaryDirectory(dir=dest.parent) as tmp:
        with zipfile.ZipFile(dest) as z:
            members = [m for m in z.namelist() if m.endswith(".nc")]
            z.extractall(tmp, members)
        parts = [xr.open_dataset(Path(tmp) / m).load() for m in members]
        for p in parts:
            p.close()
        drop = [v for v in ("expver", "number") if all(v in p.variables and v not in p.dims for p in parts)]
        merged = xr.merge([p.drop_vars(drop) for p in parts], compat="override", join="outer")
        out = Path(tmp) / "merged.nc"
        merged.to_netcdf(out)
        out.replace(dest)
    LOG.info("  %s: merged %d netCDF files from the zip (%s)", dest.name, len(members), ", ".join(merged.data_vars))


# --------------------------------------------------------------------------- IMERG
def imerg(cfg):
    w, s, e, n = cfg["aoi"]["bbox"]
    t0, t1 = cfg["dates"]["hindcast_start"], cfg["dates"]["hindcast_end"]
    short, ver = cfg["downloads"]["imerg_short_name"], cfg["downloads"]["imerg_version"]
    out = path(cfg, "raw", "imerg", "x").parent
    token = earthdata_token()
    if not token:   # user name + password: EARTHDATA_USERNAME/PASSWORD or ~/.netrc
        import earthaccess
        earthaccess.login()
        res = earthaccess.search_data(short_name=short, version=ver, temporal=(f"{t0}T00:00:00", f"{t1}T23:59:59"),
                                      bounding_box=(w, s, e, n))
        (out / "urls.txt").write_text("\n".join(l for g in res for l in g.data_links()) + "\n")
        LOG.info("IMERG: %d granules", len(res))
        earthaccess.download(res, local_path=str(out))
        return
    # Token route: the catalogue search needs no login; each file is fetched with the bearer token.
    r = requests.get("https://cmr.earthdata.nasa.gov/search/granules.json", timeout=120, headers=UA,
                     params={"short_name": short, "version": ver, "page_size": 2000,
                             "temporal": f"{t0}T00:00:00Z,{t1}T23:59:59Z", "bounding_box": f"{w},{s},{e},{n}"})
    r.raise_for_status()
    urls = sorted({l["href"] for g in r.json()["feed"]["entry"] for l in g.get("links", [])
                   if l.get("rel", "").endswith("/data#") and l.get("href", "").startswith("https://")
                   and l["href"].upper().endswith((".HDF5", ".H5"))})
    (out / "urls.txt").write_text("\n".join(urls) + "\n")
    LOG.info("IMERG: %d files", len(urls))
    if not urls:
        raise SystemExit("No IMERG files found for the hindcast window")
    missing = 0
    for url in urls:
        try:
            missing += fetch(url, out / Path(url).name, headers={"Authorization": f"Bearer {token}"}) is None
        except requests.HTTPError as ex:
            if ex.response.status_code in (401, 403):
                raise SystemExit(f"IMERG download refused ({ex.response.status_code}): the token is wrong or "
                                 "expired, or the 'NASA GESDISC DATA ARCHIVE' app is not approved in your "
                                 "Earthdata profile")
            raise
    if missing:
        raise SystemExit(f"{missing} IMERG files were not found")


# --------------------------------------------------------------------------- water-table depth (optional)
def wtd(cfg):
    url = cfg["downloads"].get("wtd_url")
    if not url:
        LOG.info("wtd_url empty: groundwater step will use the terrain proxy (height above nearest drainage)")
        return
    fetch(url, path(cfg, "raw", "groundwater", Path(url).name))


SOURCES = {"dem": dem, "s2": s2, "cci": cci, "soil": soil, "osm": osm, "era5": era5, "imerg": imerg, "wtd": wtd}


def main():
    ap = cli(__doc__)
    ap.add_argument("sources", nargs="+", choices=list(SOURCES) + ["all"])
    args = ap.parse_args()
    setup_logging()
    cfg = load_config(args.config)
    todo = list(SOURCES) if "all" in args.sources else args.sources
    failed = []
    for name in todo:
        LOG.info("=== %s", name)
        try:
            SOURCES[name](cfg)
        except (Exception, SystemExit) as ex:  # noqa: BLE001
            LOG.error("%s failed: %s", name, ex)
            failed.append(name)
    if failed:
        LOG.error("Failed sources: %s (re-run them, or see README for the manual route)", failed)
        sys.exit(1)


if __name__ == "__main__":
    main()
