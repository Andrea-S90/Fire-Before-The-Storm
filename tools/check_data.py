#!/usr/bin/env python3
"""Check web/public/data against the data contract (docs/DATA_CONTRACT.md).

Standard library only, so it runs anywhere: laptop, cluster login node, CI.

    python tools/check_data.py              # errors fail (exit 1), warnings are printed
    python tools/check_data.py --strict     # warnings fail too
    python tools/check_data.py path/to/data # another export folder

Errors   = the site would break or show something wrong (missing file, bad field, overlay off the map).
Warnings = the numbers look implausible and a human should look before it goes in the pitch.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

LEVELS = {"high", "medium", "low", "unknown", "none"}
PATHWAYS = ("runoff", "debris_flow", "groundwater", "airborne")
REQUIRED_FILES = ("meta.json", "layers.json", "towns.json", "towns.geojson", "catchments.geojson",
                  "streams.geojson", "water_points.geojson", "burned_area.geojson", "hindcast.json",
                  "wind_rose.json")
TOWN_FIELDS = ("id", "name", "kind", "lon", "lat", "catchment_km2", "upstream_burned_pct", "ash_t",
               "pathways", "recovery", "tests", "overall")
MAX_TOTAL_MB = 100      # plan: exported files stay under about 100 MB
MAX_FILE_MB = 15
PAD_DEG = 0.25          # overlays and features may stick out of the AOI by the grid margin


class Report:
    def __init__(self):
        self.errors, self.warnings = [], []

    def err(self, msg):
        self.errors.append(msg)

    def warn(self, msg):
        self.warnings.append(msg)


def load(p: Path, rep: Report):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except FileNotFoundError:
        rep.err(f"{p.name}: missing")
    except json.JSONDecodeError as e:
        rep.err(f"{p.name}: not valid JSON ({e})")
    return None


def in_box(lon, lat, bbox, pad=PAD_DEG):
    w, s, e, n = bbox
    return w - pad <= lon <= e + pad and s - pad <= lat <= n + pad


def first_coord(geom):
    c = geom.get("coordinates")
    while isinstance(c, list) and c and isinstance(c[0], list):
        c = c[0]
    return c


def check_meta(meta, rep):
    bbox = meta.get("aoi_bbox")
    if not (isinstance(bbox, list) and len(bbox) == 4 and bbox[0] < bbox[2] and bbox[1] < bbox[3]):
        rep.err("meta.json: aoi_bbox must be [lon_min, lat_min, lon_max, lat_max]")
        bbox = None
    try:
        gen = datetime.fromisoformat(meta["generated"])
        age_h = (datetime.now(timezone.utc) - gen).total_seconds() / 3600
        print(f"  export generated {meta['generated']} ({age_h:.1f} h ago), config {meta.get('config')}")
    except (KeyError, ValueError):
        rep.err("meta.json: 'generated' must be an ISO timestamp")
    for k, v in (meta.get("dates") or {}).items():
        if "datetime.date(" in str(v):
            rep.warn(f"meta.json: dates.{k} is a Python repr ({v}), not ISO dates")
    burned = (meta.get("severity") or {}).get("burned_ha")
    if bbox and isinstance(burned, dict):
        ha = sum(burned.values())
        # rough AOI area in ha (1 deg lat = 111 km; lon shrinks with cos(lat), ~0.76 at 40N)
        aoi_ha = (bbox[2] - bbox[0]) * 111 * 0.76 * (bbox[3] - bbox[1]) * 111 * 100
        print(f"  burned area {ha:,.0f} ha = {100 * ha / aoi_ha:.0f}% of the AOI")
        if ha > 0.3 * aoi_ha:
            rep.warn(f"burned area is {100 * ha / aoi_ha:.0f}% of the AOI: check against the official perimeter")
    return bbox


def check_layers(layers, data: Path, bbox, rep):
    if not isinstance(layers, list) or not layers:
        rep.err("layers.json: must be a non-empty list")
        return
    seen = set()
    for la in layers:
        lid = la.get("id")
        if not lid or lid in seen:
            rep.err(f"layers.json: missing or duplicate id {lid!r}")
        seen.add(lid)
        for k in ("title", "url", "coordinates", "units", "legend"):
            if k not in la:
                rep.err(f"layers.json[{lid}]: missing '{k}'")
        if la.get("url") and not (data / la["url"]).is_file():
            rep.err(f"layers.json[{lid}]: image {la['url']} not found")
        c = la.get("coordinates") or []
        if len(c) != 4 or any(len(p) != 2 for p in c):
            rep.err(f"layers.json[{lid}]: coordinates must be 4 [lon, lat] corners")
            continue
        # MapLibre image source order: top-left, top-right, bottom-right, bottom-left
        (tlx, tly), (trx, try_), (brx, bry), (blx, bly) = c
        if not (tlx < trx and blx < brx and tly > bly and try_ > bry):
            rep.err(f"layers.json[{lid}]: corners are not top-left, top-right, bottom-right, bottom-left")
        if bbox and not all(in_box(x, y, bbox) for x, y in c):
            rep.err(f"layers.json[{lid}]: corners {c[0]}..{c[2]} are outside the AOI {bbox} "
                    "(lon/lat swapped or a stale export?)")


def check_towns(towns, bbox, rep):
    ids = []
    if not isinstance(towns, list) or not towns:
        rep.err("towns.json: must be a non-empty list")
        return ids
    for t in towns:
        tid = t.get("id", "?")
        ids.append(tid)
        if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", str(tid)):
            rep.err(f"towns.json[{tid}]: id must be a lowercase slug")
        for k in TOWN_FIELDS:
            if k not in t:
                rep.err(f"towns.json[{tid}]: missing '{k}'")
        if bbox and isinstance(t.get("lon"), (int, float)) and not in_box(t["lon"], t["lat"], bbox, 0):
            rep.err(f"towns.json[{tid}]: lon/lat outside the AOI")
        if t.get("overall") not in LEVELS:
            rep.err(f"towns.json[{tid}]: overall={t.get('overall')!r} is not a level")
        pw = t.get("pathways") or {}
        for p in PATHWAYS:
            if p not in pw:
                rep.err(f"towns.json[{tid}]: pathways.{p} missing")
            elif pw[p].get("level") not in LEVELS:
                rep.err(f"towns.json[{tid}]: pathways.{p}.level={pw[p].get('level')!r} is not a level")
            elif "confidence" not in pw[p]:
                rep.err(f"towns.json[{tid}]: pathways.{p}.confidence missing")
        ash = t.get("ash_t") or {}
        if not all(k in ash for k in ("p10", "p50", "p90")):
            rep.err(f"towns.json[{tid}]: ash_t needs p10, p50, p90")
        elif not ash["p10"] <= ash["p50"] <= ash["p90"]:
            rep.err(f"towns.json[{tid}]: ash_t percentiles are not ordered")
        if t.get("named_in_reports") and t.get("overall") == "low":
            rep.warn(f"{t.get('name')}: named in the October reports but rated low "
                     f"({t.get('upstream_burned_pct')}% burned upstream): the hindcast claim does not hold for it")
    if len(set(ids)) != len(ids):
        rep.err("towns.json: duplicate ids")
    if not any(t.get("named_in_reports") for t in towns):
        rep.warn("towns.json: no town is flagged named_in_reports")
    n_high = sum(t.get("overall") == "high" for t in towns)
    print(f"  {len(towns)} towns: {n_high} high, "
          f"{sum(t.get('overall') == 'medium' for t in towns)} medium, "
          f"{sum(t.get('overall') == 'low' for t in towns)} low")
    if n_high > 0.5 * len(towns):
        rep.warn(f"{n_high} of {len(towns)} towns are rated high: a warning that flags most towns is not a warning")
    return ids


def check_geojson(name, gj, bbox, rep, id_key=None):
    if not isinstance(gj, dict) or gj.get("type") != "FeatureCollection":
        rep.err(f"{name}: not a FeatureCollection")
        return []
    feats = gj.get("features") or []
    if not feats:
        rep.warn(f"{name}: no features")
    for f in feats[:: max(1, len(feats) // 50)]:      # sample: enough to catch a wrong CRS
        c = first_coord(f.get("geometry") or {})
        if not c or not bbox or not in_box(c[0], c[1], bbox):
            rep.err(f"{name}: coordinates {c} are not WGS84 lon/lat inside the AOI")
            break
    return [f["properties"].get(id_key) for f in feats] if id_key else []


def check_hindcast(h, town_ids, rep):
    if not isinstance(h, dict) or "towns" not in h:
        rep.err("hindcast.json: needs 'window', 'source', 'towns'")
        return
    for t in h["towns"]:
        for k in ("id", "trigger_mm_h", "peak_30min_mm_h", "total_mm", "exceeded", "series"):
            if k not in t:
                rep.err(f"hindcast.json[{t.get('id')}]: missing '{k}'")
    ids = [t.get("id") for t in h["towns"]]
    if set(ids) != set(town_ids):
        rep.err(f"hindcast.json: town ids differ from towns.json ({len(set(ids) ^ set(town_ids))} mismatched)")
    hit = [t["id"] for t in h["towns"] if t.get("exceeded")]
    print(f"  hindcast: trigger exceeded at {len(hit)} of {len(ids)} towns {hit[:6]}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("data", nargs="?", default=Path(__file__).resolve().parents[1] / "web" / "public" / "data")
    ap.add_argument("--strict", action="store_true", help="warnings fail too")
    args = ap.parse_args()
    data = Path(args.data)
    rep = Report()
    print(f"Checking {data}")
    if not data.is_dir():
        print("ERROR: folder not found")
        return 1
    for f in REQUIRED_FILES:
        if not (data / f).is_file():
            rep.err(f"{f}: missing")

    meta = load(data / "meta.json", rep) or {}
    bbox = check_meta(meta, rep) if meta else None
    layers = load(data / "layers.json", rep)
    if layers is not None:
        check_layers(layers, data, bbox, rep)
    towns = load(data / "towns.json", rep)
    town_ids = check_towns(towns, bbox, rep) if towns is not None else []
    for name, key in (("towns.geojson", "id"), ("catchments.geojson", "id"), ("streams.geojson", None),
                      ("water_points.geojson", None), ("burned_area.geojson", None)):
        if (data / name).is_file():
            ids = check_geojson(name, load(data / name, rep), bbox, rep, key)
            if key and town_ids and set(ids) != set(town_ids):
                rep.err(f"{name}: ids differ from towns.json")
    h = load(data / "hindcast.json", rep)
    if h is not None:
        check_hindcast(h, town_ids, rep)
    rose = load(data / "wind_rose.json", rep)
    if rose is not None and not (isinstance(rose.get("sectors"), list) and rose["sectors"]):
        rep.err("wind_rose.json: needs a non-empty 'sectors' list")

    total = 0
    for f in data.rglob("*"):
        if f.is_file():
            mb = f.stat().st_size / 1e6
            total += mb
            if mb > MAX_FILE_MB:
                rep.warn(f"{f.relative_to(data)} is {mb:.0f} MB: slow on a phone")
    print(f"  total size {total:.0f} MB")
    if total > MAX_TOTAL_MB:
        rep.err(f"export is {total:.0f} MB, over the {MAX_TOTAL_MB} MB budget")

    for w in rep.warnings:
        print(f"WARNING  {w}")
    for e in rep.errors:
        print(f"ERROR    {e}")
    print(f"{len(rep.errors)} error(s), {len(rep.warnings)} warning(s)")
    return 1 if rep.errors or (args.strict and rep.warnings) else 0


if __name__ == "__main__":
    sys.exit(main())
