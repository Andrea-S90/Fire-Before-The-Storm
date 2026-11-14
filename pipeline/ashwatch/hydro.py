"""Hydrology and hazard models.

- D8 flow routing with pysheds (pure Python, pip-installable).
- Staley et al. (2017) M1 debris-flow likelihood, implemented from the published equation:
      p = exp(X) / (1 + exp(X)),   X = B + Ct*T*R + Cf*F*R + Cs*S*R
  T = share of upslope area burned at moderate/high severity on slopes >= 23 degrees
  F = mean dNBR/1000 of the upslope area,  S = mean soil KF-factor of the upslope area
  R = rainfall accumulation (mm) in 15 minutes.
  Inverted for p = 0.5:  R = -B / (Ct*T + Cf*F + Cs*S)
  The USGS pfdf library implements the same model; steps/13_pfdf_crosscheck.py compares the two.
- EPIC soil erodibility (Williams 1995) from SoilGrids texture and organic carbon.
- Relative RUSLE erosion index and a sediment delivery ratio.
"""
from __future__ import annotations

import numpy as np

if not hasattr(np, "in1d"):   # numpy >= 2.4 removed in1d; pysheds 0.5 still calls it
    np.in1d = lambda a, b, *args, **kw: np.isin(np.ravel(a), b, *args, **kw)  # noqa: E731

from pysheds.grid import Grid as PGrid  # noqa: E402
from pysheds.sview import Raster

DIRMAP = (64, 128, 1, 2, 4, 8, 16, 32)


class Flow:
    """Conditioned DEM, flow directions and accumulation for one grid."""

    def __init__(self, dem_path):
        self.pg = PGrid.from_raster(str(dem_path))
        dem = self.pg.read_raster(str(dem_path))
        dem = np.where(np.isfinite(dem), dem, np.nanmin(dem))  # pysheds dislikes NaN
        self.dem_raw = Raster(np.asarray(dem, dtype="float64"), viewfinder=self.pg.viewfinder)
        filled = self.pg.fill_pits(self.dem_raw)
        filled = self.pg.fill_depressions(filled)
        self.dem = self.pg.resolve_flats(filled)
        self.fdir = self.pg.flowdir(self.dem, dirmap=DIRMAP)
        self.acc = self.pg.accumulation(self.fdir, dirmap=DIRMAP)   # number of cells (incl. self)
        self.res = abs(self.pg.affine.a)
        self.cell_km2 = self.res ** 2 / 1e6

    def raster(self, arr):
        return Raster(np.asarray(arr, dtype="float64"), viewfinder=self.pg.viewfinder)

    def upslope_sum(self, weights):
        w = np.nan_to_num(np.asarray(weights, dtype="float64"), nan=0.0)
        return np.asarray(self.pg.accumulation(self.fdir, weights=self.raster(w), dirmap=DIRMAP))

    def upslope_mean(self, values):
        v = np.asarray(values, dtype="float64")
        ok = np.isfinite(v)
        s = self.upslope_sum(np.where(ok, v, 0.0))
        n = self.upslope_sum(ok.astype("float64"))
        with np.errstate(invalid="ignore", divide="ignore"):
            return s / n

    def area_km2(self):
        return np.asarray(self.acc) * self.cell_km2

    def catchment(self, row, col):
        """All cells draining through (row, col). Uses grid indices: exact, no coordinate snapping."""
        c = self.pg.catchment(x=int(col), y=int(row), fdir=self.fdir, dirmap=DIRMAP, xytype="index")
        return np.asarray(c).astype(bool)

    def river_network(self, stream_mask):
        return self.pg.extract_river_network(self.fdir, self.raster(stream_mask.astype("float64")) > 0,
                                             dirmap=DIRMAP)

    def hand(self, stream_mask):
        h = self.pg.compute_hand(self.fdir, self.dem, self.raster(stream_mask.astype("float64")) > 0,
                                 dirmap=DIRMAP)
        h = np.asarray(h, dtype="float32")
        h[~np.isfinite(h)] = np.nan
        return h


def slope_tan(dem: np.ndarray, res: float) -> np.ndarray:
    gy, gx = np.gradient(np.asarray(dem, dtype="float64"), res)
    return np.hypot(gx, gy).astype("float32")


def m1_variables(flow: Flow, modhigh: np.ndarray, slope_t: np.ndarray, dnbr: np.ndarray, kf: np.ndarray,
                 steep_deg: float = 23.0):
    steep = slope_t >= np.tan(np.radians(steep_deg))
    T = flow.upslope_mean((modhigh & steep).astype("float64"))
    F = flow.upslope_mean(np.clip(dnbr, 0, None) / 1000.0)
    S = flow.upslope_mean(kf)
    return T, F, S


def m1_likelihood(T, F, S, R_mm, params):
    B, Ct, Cf, Cs = params
    X = B + (Ct * T + Cf * F + Cs * S) * R_mm
    return 1.0 / (1.0 + np.exp(-X))


def m1_threshold_mm(T, F, S, params, p=0.5):
    """Rainfall accumulation (mm in the model duration) that gives likelihood p."""
    B, Ct, Cf, Cs = params
    denom = Ct * T + Cf * F + Cs * S
    with np.errstate(divide="ignore", invalid="ignore"):
        return (np.log(p / (1 - p)) - B) / denom


def epic_k(sand_pct, silt_pct, clay_pct, orgc_pct):
    """Soil erodibility (US customary units, same scale as STATSGO KF, ~0.0-0.7). Williams (1995)."""
    sn = np.clip(sand_pct, 0, 100)
    si = np.clip(silt_pct, 0, 100)
    cl = np.clip(clay_pct, 0, 100)
    oc = np.clip(orgc_pct, 0, 20)
    sn1 = 1 - sn / 100.0
    with np.errstate(divide="ignore", invalid="ignore"):
        f_csand = 0.2 + 0.3 * np.exp(-0.256 * sn * (1 - si / 100.0))
        f_clsi = np.where((cl + si) > 0, (si / (cl + si)) ** 0.3, 0.0)
        f_orgc = 1 - 0.25 * oc / (oc + np.exp(3.72 - 2.95 * oc))
        f_hisand = 1 - 0.7 * sn1 / (sn1 + np.exp(-5.51 + 22.9 * sn1))
    return (f_csand * f_clsi * f_orgc * f_hisand).astype("float32")


def rusle_ls(area_cells: np.ndarray, slope_t: np.ndarray, res: float) -> np.ndarray:
    """Moore and Burch (1986) LS factor from specific catchment area and slope."""
    As = np.clip(area_cells * res, 0, 1e5)             # m of contributing length per unit width
    sin_t = np.sin(np.arctan(slope_t))
    return ((As / 22.13) ** 0.4 * (sin_t / 0.0896) ** 1.3).astype("float32")


def sdr(area_km2):
    """Sediment delivery ratio (Vanoni 1975), area converted to square miles."""
    a_mi2 = np.maximum(np.asarray(area_km2, dtype="float64") * 0.386102, 1e-3)
    return np.clip(0.42 * a_mi2 ** -0.125, 0, 1)
