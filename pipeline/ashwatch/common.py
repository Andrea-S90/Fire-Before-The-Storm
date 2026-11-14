"""Shared helpers: configuration, the analysis grid, raster I/O and JSON output."""
from __future__ import annotations

import argparse
import json
import logging
import os
from datetime import date, datetime
from pathlib import Path

import numpy as np
import rasterio
import yaml
from rasterio.crs import CRS
from rasterio.transform import from_origin
from rasterio.vrt import WarpedVRT
from rasterio.warp import Resampling, reproject, transform_bounds

LOG = logging.getLogger("ashwatch")
PIPELINE_DIR = Path(__file__).resolve().parents[1]


def setup_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def cli(description: str) -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=description)
    ap.add_argument("--config", default=None, help="YAML config (default: $ASHWATCH_CONFIG or config/avila.yaml)")
    return ap


# --------------------------------------------------------------------------- config
def load_config(path: str | None = None) -> dict:
    path = Path(path or os.environ.get("ASHWATCH_CONFIG") or PIPELINE_DIR / "config" / "avila.yaml").resolve()
    with open(path) as f:
        cfg = yaml.safe_load(f)
    root = os.environ.get("ASHWATCH_DATA") or cfg["paths"]["data_root"]
    root = Path(root).expanduser()
    if not root.is_absolute():
        root = (path.parent / root).resolve()
    web = os.environ.get("ASHWATCH_WEB_OUT") or cfg["paths"]["web_out"]
    web = Path(web).expanduser()
    if not web.is_absolute():
        web = (path.parent / web).resolve()
    cfg["_config_path"] = str(path)
    cfg["_root"] = root
    cfg["_web"] = web
    for k, v in cfg.get("dates", {}).items():  # YAML dates -> date objects
        if isinstance(v, str):
            try:
                cfg["dates"][k] = date.fromisoformat(v)
            except ValueError:
                pass
        elif isinstance(v, list):
            cfg["dates"][k] = [date.fromisoformat(x) if isinstance(x, str) else x for x in v]
    return cfg


def path(cfg: dict, *parts: str, mkdir: bool = True) -> Path:
    """Path under the data root; creates the parent folder."""
    p = Path(cfg["_root"]).joinpath(*parts)
    if mkdir:
        p.parent.mkdir(parents=True, exist_ok=True)
    return p


def earthdata_token() -> str | None:
    """Earthdata bearer token from $EARTHDATA_TOKEN or the first line of ~/.earthdata_token (if any)."""
    tok = os.environ.get("EARTHDATA_TOKEN", "").strip()
    f = Path.home() / ".earthdata_token"
    if not tok and f.exists():
        tok = f.read_text().strip().splitlines()[0].strip() if f.read_text().strip() else ""
    return tok or None


def n_workers() -> int:
    return int(os.environ.get("SLURM_CPUS_PER_TASK") or os.cpu_count() or 1)


# --------------------------------------------------------------------------- grid
class Grid:
    """The common analysis grid every layer is resampled to."""

    def __init__(self, crs, transform, width, height):
        self.crs = CRS.from_user_input(crs)
        self.transform = transform
        self.width = int(width)
        self.height = int(height)

    @property
    def res(self) -> float:
        return float(self.transform.a)

    @property
    def shape(self):
        return (self.height, self.width)

    @property
    def bounds(self):
        t = self.transform
        return (t.c, t.f + t.e * self.height, t.c + t.a * self.width, t.f)

    def coarse(self, factor: int) -> "Grid":
        t = self.transform
        return Grid(self.crs, from_origin(t.c, t.f, t.a * factor, -t.e * factor),
                    int(np.ceil(self.width / factor)), int(np.ceil(self.height / factor)))

    def xy(self, rows, cols):
        """Cell-centre coordinates in the grid CRS."""
        t = self.transform
        return t.c + (np.asarray(cols) + 0.5) * t.a, t.f + (np.asarray(rows) + 0.5) * t.e

    def rowcol(self, x, y):
        t = self.transform
        col = np.floor((np.asarray(x) - t.c) / t.a).astype(int)
        row = np.floor((np.asarray(y) - t.f) / t.e).astype(int)
        return row, col

    def profile(self, dtype="float32", nodata=np.nan, count=1) -> dict:
        return dict(driver="GTiff", height=self.height, width=self.width, count=count, dtype=dtype,
                    crs=self.crs, transform=self.transform, nodata=nodata, tiled=True,
                    blockxsize=256, blockysize=256, compress="deflate", BIGTIFF="IF_SAFER")


def grid_from_config(cfg: dict) -> Grid:
    g = cfg["grid"]
    crs = CRS.from_user_input(g["crs"])
    res = float(g["res_m"])
    m = float(g.get("margin_m", 0))
    w, s, e, n = cfg["aoi"]["bbox"]
    x0, y0, x1, y1 = transform_bounds("EPSG:4326", crs, w, s, e, n, densify_pts=21)
    x0 = np.floor((x0 - m) / res) * res
    y0 = np.floor((y0 - m) / res) * res
    x1 = np.ceil((x1 + m) / res) * res
    y1 = np.ceil((y1 + m) / res) * res
    return Grid(crs, from_origin(x0, y1, res, res), round((x1 - x0) / res), round((y1 - y0) / res))


# --------------------------------------------------------------------------- raster I/O
def write_raster(p: Path | str, arr: np.ndarray, grid: Grid, nodata=np.nan, dtype=None, desc: str | None = None) -> Path:
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    arr = np.asarray(arr)
    dtype = dtype or (arr.dtype.name if arr.dtype != np.float64 else "float32")
    if arr.ndim == 2:
        arr = arr[None]
    with rasterio.open(p, "w", **grid.profile(dtype=dtype, nodata=nodata, count=arr.shape[0])) as dst:
        dst.write(arr.astype(dtype))
        if desc:
            dst.update_tags(description=desc)
    return p


def read_raster(p: Path | str, band: int = 1) -> np.ndarray:
    with rasterio.open(p) as src:
        a = src.read(band).astype("float32")
        if src.nodata is not None and not np.isnan(src.nodata):
            a[a == src.nodata] = np.nan
    return a


def to_grid(src_path: Path | str, grid: Grid, resampling=Resampling.bilinear, band: int = 1,
            src_nodata=None) -> np.ndarray:
    """Read any raster (local or /vsicurl/) and resample it onto the grid."""
    with rasterio.open(src_path) as src:
        nod = src_nodata if src_nodata is not None else src.nodata
        with WarpedVRT(src, crs=grid.crs, transform=grid.transform, width=grid.width, height=grid.height,
                       resampling=resampling, src_nodata=nod, nodata=np.nan, dtype="float32") as vrt:
            return vrt.read(band).astype("float32")


def array_to_grid(arr: np.ndarray, src_transform, src_crs, grid: Grid,
                  resampling=Resampling.average, src_nodata=np.nan) -> np.ndarray:
    out = np.full(grid.shape, np.nan, dtype="float32")
    reproject(arr.astype("float32"), out, src_transform=src_transform, src_crs=src_crs,
              src_nodata=src_nodata, dst_transform=grid.transform, dst_crs=grid.crs,
              dst_nodata=np.nan, resampling=resampling)
    return out


def mosaic_to_grid(paths, grid: Grid, resampling=Resampling.bilinear) -> np.ndarray:
    out = np.full(grid.shape, np.nan, dtype="float32")
    for p in paths:
        a = to_grid(p, grid, resampling)
        m = np.isnan(out) & ~np.isnan(a)
        out[m] = a[m]
    return out


# --------------------------------------------------------------------------- misc
def db(x):
    with np.errstate(divide="ignore", invalid="ignore"):
        return 10.0 * np.log10(x)


def lin(x_db):
    return 10.0 ** (np.asarray(x_db) / 10.0)


def _json_default(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return None if np.isnan(o) else float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, (date, datetime)):
        return o.isoformat()
    if isinstance(o, Path):
        return str(o)
    raise TypeError(type(o))


def clean_nans(o):
    if isinstance(o, float) and np.isnan(o):
        return None
    if isinstance(o, dict):
        return {k: clean_nans(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean_nans(v) for v in o]
    return o


def write_json(p: Path | str, obj, indent=None) -> Path:
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w") as f:
        json.dump(clean_nans(json.loads(json.dumps(obj, default=_json_default))), f, indent=indent,
                  allow_nan=False)
    return p


def read_json(p):
    with open(p) as f:
        return json.load(f)


def require(p: Path, hint: str) -> Path:
    if not Path(p).exists():
        raise SystemExit(f"Missing input {p}\n  -> {hint}")
    return Path(p)
