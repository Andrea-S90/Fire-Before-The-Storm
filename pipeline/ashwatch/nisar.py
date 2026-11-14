"""NISAR GCOV helpers: file-name parsing and reading HH/HV backscatter from the HDF5."""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

import h5py
import numpy as np
from affine import Affine
from rasterio.crs import CRS
from rasterio.warp import transform_bounds

# e.g. NISAR_L2_PR_GCOV_035_023_D_068_2005_DHDH_A_20261106T191743_20261106T191820_P05036_N_F_J_001.h5
NAME_RE = re.compile(
    r"NISAR_L2_(?P<prodcfg>[A-Z]{2})_GCOV_(?P<cycle>\d{3})_(?P<track>\d{3})_(?P<dir>[AD])_(?P<frame>\d{3})_"
    r"(?P<mode>\d{4})_(?P<pol>[A-Z]{4})_(?P<side>[A-Z])_(?P<start>\d{8}T\d{6})_(?P<stop>\d{8}T\d{6})_"
    r"(?P<crid>[A-Z]\d{5})_")


def parse_name(name: str) -> dict | None:
    m = NAME_RE.search(Path(name).name)
    if not m:
        return None
    d = m.groupdict()
    d["datetime"] = datetime.strptime(d["start"], "%Y%m%dT%H%M%S")
    d["date"] = d["datetime"].date()
    d["key"] = f"{d['track']}{d['dir']}"   # same track + direction = same viewing geometry
    return d


def _find_grid_group(f: h5py.File, frequency: str):
    hits = []

    def visit(name, obj):
        if isinstance(obj, h5py.Group) and name.endswith(frequency) and "GCOV" in name and "grids" in name:
            hits.append(name)
    f.visititems(visit)
    if not hits:  # be lenient: any group holding HVHV or HHHH
        def visit2(name, obj):
            if isinstance(obj, h5py.Group) and ("HHHH" in obj or "HVHV" in obj):
                hits.append(name)
        f.visititems(visit2)
    if not hits:
        raise KeyError("No GCOV grid group found; run steps/inspect_gcov.py on the file and adjust nisar.py")
    return f[hits[0]]


def _epsg(grp) -> int:
    for key in ("projection", "../projection"):
        try:
            ds = grp[key]
        except KeyError:
            continue
        for attr in ("epsg_code", "epsg"):
            if attr in ds.attrs:
                return int(np.asarray(ds.attrs[attr]).ravel()[0])
        try:
            v = int(np.asarray(ds[()]).ravel()[0])
            if 1000 < v < 100000:
                return v
        except Exception:
            pass
    raise KeyError("No projection/EPSG found in GCOV grid group")


def _coords(grp):
    for xs, ys in (("xCoordinates", "yCoordinates"), ("x", "y")):
        if xs in grp and ys in grp:
            return np.asarray(grp[xs][:], dtype="float64"), np.asarray(grp[ys][:], dtype="float64")
    raise KeyError("No x/yCoordinates in GCOV grid group")


def read_gcov(path: str | Path, pols=("HHHH", "HVHV"), frequency="frequencyA", bounds=None, bounds_crs=None):
    """Read backscatter power (linear gamma0) for the given polarisations.

    bounds/bounds_crs: optional (xmin, ymin, xmax, ymax) to read only a window (saves memory).
    Returns dict(pols={name: array}, transform=Affine, crs=CRS). Missing pols are skipped.
    """
    with h5py.File(path, "r") as f:
        grp = _find_grid_group(f, frequency)
        x, y = _coords(grp)
        crs = CRS.from_epsg(_epsg(grp))
        dx, dy = x[1] - x[0], y[1] - y[0]
        r0, r1, c0, c1 = 0, len(y), 0, len(x)
        if bounds is not None:
            bx0, by0, bx1, by1 = transform_bounds(bounds_crs, crs, *bounds, densify_pts=21) if bounds_crs else bounds
            cols = np.where((x >= bx0 - abs(dx)) & (x <= bx1 + abs(dx)))[0]
            rows = np.where((y >= by0 - abs(dy)) & (y <= by1 + abs(dy)))[0]
            if cols.size == 0 or rows.size == 0:
                return None
            r0, r1, c0, c1 = rows.min(), rows.max() + 1, cols.min(), cols.max() + 1
        transform = Affine(dx, 0, x[c0] - dx / 2, 0, dy, y[r0] - dy / 2)
        out = {}
        for p in pols:
            if p not in grp:
                continue
            a = np.asarray(grp[p][r0:r1, c0:c1], dtype="float32")
            fill = grp[p].attrs.get("_FillValue")
            if fill is not None:
                a[a == np.float32(np.asarray(fill).ravel()[0])] = np.nan
            a[~np.isfinite(a)] = np.nan
            med = np.nanmedian(a) if np.isfinite(a).any() else np.nan
            if np.isfinite(med) and med < 0:      # stored in dB -> convert to linear power
                a = 10 ** (a / 10)
            a[a <= 0] = np.nan
            out[p] = a
    return dict(pols=out, transform=transform, crs=crs)
