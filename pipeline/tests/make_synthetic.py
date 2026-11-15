#!/usr/bin/env python
"""Build a small fake data set (every input type, incl. NISAR-like GCOV HDF5 files) and a config for it.

  python tests/make_synthetic.py /tmp/aw_test          # then: bash tests/run_synthetic.sh /tmp/aw_test
Lets you test the environment and steps 03-12 on the cluster before the real downloads finish.
"""
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import h5py
import numpy as np
import rasterio
import xarray as xr
import yaml
from pyproj import Transformer
from rasterio.transform import from_origin

HERE = Path(__file__).resolve().parent
BBOX = [-4.80, 40.30, -4.62, 40.42]
FIRE = (-4.72, 40.37)          # burn centre (lon, lat)


def field(lon, lat):
    """Forest fraction 0-1, severity class 0-3 and elevation for any lon/lat arrays."""
    u = (lon - BBOX[0]) / (BBOX[2] - BBOX[0])
    v = (lat - BBOX[1]) / (BBOX[3] - BBOX[1])
    forest = np.clip(0.55 + 0.35 * np.sin(5 * u) * np.cos(4 * v) + 0.1 * np.cos(13 * u + 2), 0, 1)
    dx = (lon - FIRE[0]) / 0.045
    dy = (lat - FIRE[1]) / 0.03
    r = np.hypot(dx, dy)
    sev = np.select([r < 0.45, r < 0.75, r < 1.0], [3, 2, 1], 0)
    z = 1100 - 500 * (1 - v) + 120 * np.sin(9 * u) * np.cos(7 * v) - 80 * np.cos(14 * u)
    return forest, sev, z


def write_tif(p, arr, transform, crs, nodata=None, dtype="float32"):
    p.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(p, "w", driver="GTiff", height=arr.shape[0], width=arr.shape[1], count=1, dtype=dtype,
                       crs=crs, transform=transform, nodata=nodata) as dst:
        dst.write(arr.astype(dtype), 1)


def ll_grid(res_deg, pad=0.03):
    w, s, e, n = BBOX[0] - pad, BBOX[1] - pad, BBOX[2] + pad, BBOX[3] + pad
    lons = np.arange(w, e, res_deg) + res_deg / 2
    lats = np.arange(n, s, -res_deg) - res_deg / 2
    LON, LAT = np.meshgrid(lons, lats)
    return LON, LAT, from_origin(w, n, res_deg, res_deg)


def main(root):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    raw = root / "data" / "raw"
    rng = np.random.default_rng(0)

    # config
    cfg = yaml.safe_load((HERE.parent / "config" / "avila.yaml").read_text())
    cfg["name"] = "synthetic"
    cfg["paths"] = {"data_root": str(root / "data"), "web_out": str(root / "web")}
    cfg["aoi"]["bbox"] = BBOX
    cfg["aoi"]["center"] = [-4.71, 40.36]
    cfg["grid"].update(res_m=60, margin_m=600)
    cfg["towns"]["named"] = ["Casavieja", "Piedralaves", "Burgohondo"]
    cfg["towns"]["reservoirs"] = ["Embalse de El Burguillo"]
    cfg["ash"]["mc_draws"] = 500
    cfg["severity"]["rf_samples"] = 8000
    (root / "synthetic.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False))

    # DEM (WGS84, ~50 m)
    LON, LAT, tr = ll_grid(0.0005)
    forest, sev, z = field(LON, LAT)
    write_tif(raw / "dem" / "Copernicus_DSM_fake_DEM.tif", z + rng.normal(0, 1, z.shape), tr, "EPSG:4326")

    # CCI biomass (WGS84 ~100 m), Mg/ha, consistent with the radar model below
    LON, LAT, tr = ll_grid(0.001)
    f, _, _ = field(LON, LAT)
    write_tif(raw / "cci" / "N50W010_ESACCI-BIOMASS-L4-AGB-MERGED-100m-2021-fake.tif",
              np.clip(140 * f ** 1.3 + rng.normal(0, 8, f.shape), 0, None), tr, "EPSG:4326", nodata=-1)

    # SoilGrids-like layers in native units (g/kg, dg/kg) on a WGS84 grid (like the wget route)
    LON, LAT, tr = ll_grid(0.0025)
    for v, val in (("sand", 480), ("silt", 290), ("clay", 230), ("soc", 180)):
        write_tif(raw / "soil" / f"{v}_0-5cm.tif", np.full(LON.shape, val) + rng.normal(0, 15, LON.shape), tr, "EPSG:4326")

    # UTM 30N helpers for radar and optical
    to_utm = Transformer.from_crs("EPSG:4326", "EPSG:32630", always_xy=True)
    to_ll = Transformer.from_crs("EPSG:32630", "EPSG:4326", always_xy=True)
    x0, y0 = to_utm.transform(BBOX[0] - 0.03, BBOX[3] + 0.03)
    x1, y1 = to_utm.transform(BBOX[2] + 0.03, BBOX[1] - 0.03)

    def utm_field(res):
        xs = np.arange(x0, x1, res) + res / 2
        ys = np.arange(y0, y1, -res) - res / 2
        X, Y = np.meshgrid(xs, ys)
        lo, la = to_ll.transform(X, Y)
        return xs, ys, *field(lo, la)

    # NISAR-like GCOV files: two passes, pre / post / autumn dates
    xs, ys, f, sev, _ = utm_field(20.0)
    drop = np.array([0.0, 1.5, 3.0, 5.0])[sev]
    passes = {("023", "D", "068"): ["2026-06-20", "2026-07-02", "2026-07-14", "2026-08-19", "2026-08-31",
                                    "2026-09-12", "2026-10-01", "2026-10-13"],
              ("087", "A", "022"): ["2026-06-27", "2026-07-09", "2026-07-21", "2026-08-14", "2026-08-26",
                                    "2026-09-07", "2026-09-19", "2026-10-06"]}
    for (track, d, frame), dates in passes.items():
        for ds in dates:
            dt = date.fromisoformat(ds)
            post = dt >= date(2026, 7, 22)
            months_after = max(0, (dt - date(2026, 8, 7)).days / 30)
            dd = drop * post - 0.3 * months_after * (drop > 0)
            hv = -22 + 9 * f - dd
            hh = -13 + 3 * f - dd / 2 + (1.5 if dt >= date(2026, 10, 1) else 0) * (sev > 0)
            spk = lambda: rng.gamma(8, 1 / 8, f.shape)  # noqa: E731  multiplicative speckle
            name = (f"NISAR_L2_PR_GCOV_025_{track}_{d}_{frame}_2005_DHDH_A_{dt:%Y%m%d}T191743_"
                    f"{dt:%Y%m%d}T191820_P05023_N_F_J_001.h5")
            p = raw / "nisar" / name
            p.parent.mkdir(parents=True, exist_ok=True)
            with h5py.File(p, "w") as h:
                g = h.create_group("science/LSAR/GCOV/grids/frequencyA")
                g["HHHH"] = (10 ** (hh / 10) * spk()).astype("float32")
                g["HVHV"] = (10 ** (hv / 10) * spk()).astype("float32")
                g["xCoordinates"] = xs
                g["yCoordinates"] = ys
                pr = g.create_dataset("projection", data=np.uint32(32630))
                pr.attrs["epsg_code"] = 32630
    # urgent-response duplicate that must be skipped
    (raw / "nisar" / name.replace("_PR_", "_UR_")).write_bytes(b"")

    # Sentinel-2 items (DN = reflectance * 1e4, offset already removed as in the Earth Search files)
    xs, ys, f, sev, _ = utm_field(20.0)
    tr = from_origin(xs[0] - 10, ys[0] + 10, 20, 20)
    for period, burned in (("pre", False), ("post", True)):
        for k in range(2):
            nir = 0.12 + 0.25 * f
            sw = 0.10 + 0.05 * (1 - f)
            if burned:
                nir = nir - np.array([0, 0.05, 0.12, 0.2])[sev]
                sw = sw + np.array([0, 0.03, 0.08, 0.12])[sev]
            nir, sw = np.clip(nir, 0.02, None), np.clip(sw, 0.02, None)   # DN 0 would read as nodata
            scl = np.full(f.shape, 4)
            scl[: f.shape[0] // 5, k * 40: k * 40 + 60] = 9      # a cloud
            iid = f"S2X_30TUK_2026{'0715' if not burned else '0815'}_{k}_L2A"
            write_tif(raw / "s2" / period / f"{iid}_nir08.tif", nir * 1e4 + rng.normal(0, 30, f.shape), tr, "EPSG:32630", dtype="uint16")
            write_tif(raw / "s2" / period / f"{iid}_swir22.tif", sw * 1e4 + rng.normal(0, 30, f.shape), tr, "EPSG:32630", dtype="uint16")
            write_tif(raw / "s2" / period / f"{iid}_scl.tif", scl, tr, "EPSG:32630", dtype="uint8")

    # OSM-like GeoJSON
    def pt(lon, lat, **props):
        return {"type": "Feature", "geometry": {"type": "Point", "coordinates": [lon, lat]}, "properties": props}
    rv = [[-4.665, 40.395], [-4.645, 40.395], [-4.645, 40.41], [-4.665, 40.41], [-4.665, 40.395]]
    feats = [pt(-4.70, 40.33, name="Casavieja", place="village", population="1400"),
             pt(-4.66, 40.35, name="Piedralaves", place="village"),
             pt(-4.78, 40.40, name="Burgohondo", place="village"),
             pt(-4.75, 40.31, name="Somewhere", place="hamlet"),
             pt(-4.715, 40.36, natural="spring", name="Fuente del Pinar"),
             pt(-4.69, 40.35, man_made="water_well"),
             pt(-4.63, 40.41, man_made="water_works", name="ETAP"),
             {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [rv]},
              "properties": {"name": "Embalse de El Burguillo", "water": "reservoir", "natural": "water"}}]
    (raw / "osm").mkdir(parents=True, exist_ok=True)
    (raw / "osm" / "osm.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": feats}))

    # ERA5-like netCDF (new CDS layout: valid_time, latitude, longitude)
    t = np.arange(np.datetime64("2026-07-15T00"), np.datetime64("2026-10-11T00"), np.timedelta64(1, "h"))
    lat = np.arange(40.9, 39.6, -0.25)
    lon = np.arange(-5.5, -3.7, 0.25)
    n = t.size
    u = 3 + 2 * rng.standard_normal(n)
    v = 1 + 2 * rng.standard_normal(n)
    tp = np.zeros(n)
    tp[(t >= np.datetime64("2026-09-20T00")) & (t < np.datetime64("2026-09-20T06"))] = 0.003
    shape3 = (n, lat.size, lon.size)
    ds = xr.Dataset({"u10": (("valid_time", "latitude", "longitude"), np.broadcast_to(u[:, None, None], shape3).copy()),
                     "v10": (("valid_time", "latitude", "longitude"), np.broadcast_to(v[:, None, None], shape3).copy()),
                     "tp": (("valid_time", "latitude", "longitude"), np.broadcast_to(tp[:, None, None], shape3).copy())},
                    coords={"valid_time": t, "latitude": lat, "longitude": lon})
    (raw / "era5").mkdir(parents=True, exist_ok=True)
    for m in (7, 8, 9, 10):
        ds.sel(valid_time=ds.valid_time.dt.month == m).to_netcdf(raw / "era5" / f"era5_2026{m:02d}.nc")

    # IMERG-like half-hourly HDF5 (regional), a storm on Oct 6
    (raw / "imerg").mkdir(parents=True, exist_ok=True)
    glon = np.arange(-5.55, -3.9, 0.1)
    glat = np.arange(39.85, 40.95, 0.1)
    t0 = datetime(2026, 10, 5)
    for k in range(96):
        tt = t0 + timedelta(minutes=30 * k)
        peak = 40 * np.exp(-((k - 60) / 4) ** 2)
        p = np.full((1, glon.size, glat.size), peak, "float32")
        fn = f"3B-HHR-L.MS.MRG.3IMERG.{tt:%Y%m%d}-S{tt:%H%M%S}-E{(tt + timedelta(minutes=29, seconds=59)):%H%M%S}.0000.V07B.HDF5"
        with h5py.File(raw / "imerg" / fn, "w") as h:
            g = h.create_group("Grid")
            g["precipitation"] = p
            g["lon"] = glon
            g["lat"] = glat
    print("synthetic data in", root)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "/tmp/aw_test")
