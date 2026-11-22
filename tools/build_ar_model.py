# /// script
# requires-python = ">=3.11,<3.14"
# dependencies = ["numpy", "pillow>=10.1", "rasterio", "usd-core"]
# ///
"""Build the augmented-reality model of the fire area for the site's "View in AR" button (issue #23).

It reads only public data and the files the pipeline already exported:

- elevation: Copernicus DEM GLO-30, read straight from the public AWS bucket (no login);
- the area: the overlays' extent in web/public/data/layers.json;
- the texture: burn severity (img/severity.png), the burned-area outline, the streams and the towns with
  their overall risk, all from web/public/data/.

It writes web/public/ar/: burgohondo.glb (Android, browsers), burgohondo.usdz (iPhone Quick Look) and
model.json (size and dates the site shows). That folder is not part of the data contract; only this script
writes it. Re-run it after a data re-export, from the repository root:

    uv run tools/build_ar_model.py

The model is one moment (after the fire); it does not follow the story chapters.
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import struct
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "web" / "public" / "data"
DEM_BASE = "https://copernicus-dem-30m.s3.amazonaws.com"  # same source as pipeline/config/avila.yaml (dem_base)

# the site's colours (web/src/data.js LEVEL_COLOR, web/src/components/MapView.jsx)
LEVEL_COLOR = {"high": "#b2182b", "medium": "#ef8a62", "low": "#4d9ac4"}
BURN_LINE = "#3b2a20"
STREAM = "#2c6fa8"
INK = "#1c1917"
LAND = (236, 230, 214)  # warm paper colour under the hillshade
SKIRT = "#7a6a5a"  # sides of the block

M_PER_DEG_LAT = 110_574.0
M_PER_DEG_LON_EQ = 111_320.0


# ---------------------------------------------------------------- inputs


def load_bbox() -> tuple[float, float, float, float]:
    """West, south, east, north of the exported overlays (all layers share one extent)."""
    layers = json.loads((DATA / "layers.json").read_text(encoding="utf-8"))
    xs = [c[0] for l in layers for c in l["coordinates"]]
    ys = [c[1] for l in layers for c in l["coordinates"]]
    return min(xs), min(ys), max(xs), max(ys)


def dem_tile_url(lat: int, lon: int) -> str:
    ns = f"N{lat:02d}" if lat >= 0 else f"S{-lat:02d}"
    ew = f"E{lon:03d}" if lon >= 0 else f"W{-lon:03d}"
    name = f"Copernicus_DSM_COG_10_{ns}_00_{ew}_00_DEM"
    return f"{DEM_BASE}/{name}/{name}.tif"


def load_dem(bbox, cache: Path) -> np.ndarray:
    """Elevation in metres on the DEM's own 1 arc-second grid, cropped to bbox; north-up. Cached."""
    w, s, e, n = bbox
    cached = cache / f"dem_{w:.4f}_{s:.4f}_{e:.4f}_{n:.4f}.npy"
    if cached.exists():
        return np.load(cached)
    import rasterio
    from rasterio.merge import merge

    urls = [
        dem_tile_url(lat, lon)
        for lat in range(math.floor(s), math.floor(n - 1e-9) + 1)
        for lon in range(math.floor(w), math.floor(e - 1e-9) + 1)
    ]
    print(f"reading {len(urls)} Copernicus DEM tile(s) from AWS ...", flush=True)
    with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif"):
        srcs = [rasterio.open(f"/vsicurl/{u}") for u in urls]
        try:
            arr, _ = merge(srcs, bounds=(w, s, e, n), nodata=np.nan)
        finally:
            for src in srcs:
                src.close()
    dem = arr[0].astype(np.float32)
    if np.isnan(dem).any():
        dem = np.where(np.isnan(dem), np.nanmin(dem), dem)
    cache.mkdir(parents=True, exist_ok=True)
    np.save(cached, dem)
    return dem


def resample(a: np.ndarray, width: int, height: int) -> np.ndarray:
    return np.asarray(Image.fromarray(a.astype(np.float32), mode="F").resize((width, height), Image.BILINEAR))


def hillshade(z: np.ndarray, dx: float, dy: float, azimuth=315.0, altitude=45.0, zfactor=1.0) -> np.ndarray:
    gy, gx = np.gradient(z * zfactor, dy, dx)
    slope = np.arctan(np.hypot(gx, gy))
    aspect = np.arctan2(-gx, gy)
    az, alt = math.radians(360.0 - azimuth + 90.0), math.radians(altitude)
    shade = np.sin(alt) * np.cos(slope) + np.cos(alt) * np.sin(slope) * np.cos(az - aspect)
    return np.clip(shade, 0, 1)


# ---------------------------------------------------------------- texture


# Pillow's bundled font has no accents (Ávila, Muñotello), so use a system font with Latin-1 glyphs:
# DejaVu on Linux, Arial on Windows and macOS.
FONT_FILES = {
    False: [
        "DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "arial.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial.ttf",
    ],
    True: [
        "DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "arialbd.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/Library/Fonts/Arial Bold.ttf",
    ],
}


def font(size: int, bold: bool = False):
    for name in FONT_FILES[bold]:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    print("warning: no DejaVu or Arial font found; accented names will not render", file=sys.stderr)
    return ImageFont.load_default(size=size)


def hex_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))


def dashed(draw: ImageDraw.ImageDraw, pts, fill, width, dash=22.0, gap=14.0):
    """Polyline with a dash pattern that carries over from one segment to the next."""
    on, left = True, dash
    for (x0, y0), (x1, y1) in itertools.pairwise(pts):
        seg = math.hypot(x1 - x0, y1 - y0)
        t = 0.0
        while t < seg:
            step = min(left, seg - t)
            if on:
                a, b = t / seg, (t + step) / seg
                draw.line(
                    [(x0 + (x1 - x0) * a, y0 + (y1 - y0) * a), (x0 + (x1 - x0) * b, y0 + (y1 - y0) * b)], fill=fill, width=width
                )
            t += step
            left -= step
            if left <= 1e-9:
                on = not on
                left = dash if on else gap


STRIP_PX = 350  # height of the label strip under the map, in texture pixels


def bake_texture(dem: np.ndarray, bbox, width_px: int, meta: dict, exaggeration: float):
    """Map (north up) with a label strip under it. The strip becomes a flat ledge in front of the terrain,
    so the key never hides a town."""
    w, s, e, n = bbox
    lat0 = (s + n) / 2
    ground_w = (e - w) * M_PER_DEG_LON_EQ * math.cos(math.radians(lat0))
    ground_h = (n - s) * M_PER_DEG_LAT
    height_px = round(width_px * ground_h / ground_w)
    W, H = width_px, height_px

    def px(lon, lat):
        return ((lon - w) / (e - w) * W, (n - lat) / (n - s) * H)

    # relief: hillshade on a warm paper colour, slightly lighter on the high ground
    z = resample(dem, W, H)
    shade = hillshade(z, ground_w / W, ground_h / H, zfactor=1.6)
    lift = (z - z.min()) / max(1.0, float(z.max() - z.min()))
    tone = (0.62 + 0.38 * shade) * (0.93 + 0.07 * lift)
    base = np.clip(np.array(LAND, np.float32)[None, None, :] * tone[..., None], 0, 255).astype(np.uint8)
    img = Image.fromarray(base, "RGB").convert("RGBA")

    # burn severity, as exported (transparent where unburned)
    sev = Image.open(DATA / "img" / "severity.png").convert("RGBA").resize((W, H), Image.NEAREST)
    img = Image.alpha_composite(img, sev)
    draw = ImageDraw.Draw(img)

    # streams, wider downstream
    streams = json.loads((DATA / "streams.geojson").read_text(encoding="utf-8"))["features"]
    streams.sort(key=lambda f: f["properties"].get("area_km2") or 0)
    for f in streams:
        area = f["properties"].get("area_km2") or 0
        if area < 3:
            continue
        lw = max(1, round(1 + 1.6 * math.log10(area)))
        coords = f["geometry"]["coordinates"]
        lines = coords if f["geometry"]["type"] == "MultiLineString" else [coords]
        for line in lines:
            draw.line([px(*c[:2]) for c in line], fill=STREAM, width=lw, joint="curve")

    # edge of the burned area, dashed like on the site
    burned = json.loads((DATA / "burned_area.geojson").read_text(encoding="utf-8"))["features"]
    for f in burned:
        g = f["geometry"]
        polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        for poly in polys:
            for ring in poly:
                if len(ring) < 12:  # tiny islands would only add noise at desk scale
                    continue
                dashed(draw, [px(*c[:2]) for c in ring], BURN_LINE, 4)

    # towns and reservoirs: dot by overall risk; the riskier name wins where labels collide
    towns = json.loads((DATA / "towns.geojson").read_text(encoding="utf-8"))["features"]
    rank = {"high": 0, "medium": 1, "low": 2}
    towns.sort(key=lambda f: rank.get(f["properties"].get("overall"), 3))
    r, f_label = 13, font(32, bold=True)
    for t in towns:
        x, y = px(*t["geometry"]["coordinates"][:2])
        col = LEVEL_COLOR.get(t["properties"].get("overall"), "#9a9a9a")
        if t["properties"].get("kind") == "reservoir":
            draw.rectangle([x - r, y - r, x + r, y + r], fill=col, outline="white", width=4)
        else:
            draw.ellipse([x - r, y - r, x + r, y + r], fill=col, outline="white", width=4)
    taken: list[tuple[float, float, float, float]] = [
        (x - r - 2, y - r - 2, x + r + 2, y + r + 2) for x, y in (px(*t["geometry"]["coordinates"][:2]) for t in towns)
    ]
    for t in towns:
        x, y = px(*t["geometry"]["coordinates"][:2])
        name = t["properties"]["name"]
        tw = draw.textlength(name, font=f_label)
        th = 34
        for ax, ay in (
            (x - tw / 2, y + r + 4),
            (x - tw / 2, y - r - 6 - th),
            (x + r + 6, y - th / 2),
            (x - r - 6 - tw, y - th / 2),
        ):
            box = (ax - 3, ay - 3, ax + tw + 3, ay + th + 3)
            inside = box[0] > 0 and box[1] > 0 and box[2] < W and box[3] < H
            if inside and not any(box[0] < b[2] and b[0] < box[2] and box[1] < b[3] and b[1] < box[3] for b in taken):
                draw.text((ax, ay), name, font=f_label, fill=INK, stroke_width=5, stroke_fill="white")
                taken.append(box)
                break

    full = Image.new("RGB", (W, H + STRIP_PX), (250, 248, 242))
    full.paste(img.convert("RGB"), (0, 0))
    draw_key(ImageDraw.Draw(full), (0, H, W, H + STRIP_PX), meta, exaggeration, ground_w / W)
    return full, (ground_w, ground_h), H / (H + STRIP_PX)


def draw_key(draw: ImageDraw.ImageDraw, box, meta: dict, exaggeration: float, m_per_px: float):
    """Title, legend, sources, north arrow and 10 km scale bar, baked in: AR viewers show no HTML."""
    x0, y0, x1, _ = box
    f_title, f_head, f_text, f_small = font(58, bold=True), font(36, bold=True), font(36), font(30)
    draw.line([(x0, y0), (x1, y0)], fill=INK, width=4)

    # left: what it is, and what it is not
    x, y = x0 + 60, y0 + 40
    draw.text((x, y), "Burgohondo fire, Ávila, July 2026", font=f_title, fill=INK)
    y += 84
    draw.text((x, y), "After the fire: burn severity and drinking-water risk per town", font=f_text, fill=INK)
    y += 62
    for line in (
        f"One moment after the fire (data export of {meta['generated'][:10]}). Relief exaggerated {exaggeration:g}×.",
        "Elevation: Copernicus DEM GLO-30. Burn severity: Sentinel-2 dNBR, checked with NISAR. Ash Watch.",
    ):
        draw.text((x, y), line, font=f_small, fill=INK)
        y += 46

    # middle: legend
    x = x0 + 1900
    y = y0 + 52
    sev = next(l for l in json.loads((DATA / "layers.json").read_text(encoding="utf-8")) if l["id"] == "severity")
    col_x = x + 300
    draw.text((x, y), "Burn severity", font=f_head, fill=INK)
    sx = col_x
    for cls, col in zip(sev["legend"]["classes"], sev["legend"]["colors"]):
        if cls == "unburned":
            continue
        rgb = tuple(int(float(v)) for v in col[col.index("(") + 1 : col.index(")")].split(",")[:3])
        draw.rectangle([sx, y + 4, sx + 36, y + 40], fill=rgb)
        draw.text((sx + 48, y), cls, font=f_text, fill=INK)
        sx += 48 + draw.textlength(cls, font=f_text) + 40
    y += 70
    draw.text((x, y), "Overall risk", font=f_head, fill=INK)
    sx = col_x
    for lvl in ("high", "medium", "low"):
        draw.ellipse([sx + 2, y + 6, sx + 34, y + 38], fill=LEVEL_COLOR[lvl], outline="white", width=3)
        draw.text((sx + 48, y), lvl, font=f_text, fill=INK)
        sx += 48 + draw.textlength(lvl, font=f_text) + 40
    y += 74
    draw.text((x, y), "Dot: town. Square: reservoir.", font=f_small, fill=INK)
    y += 46
    draw.text((x, y), "Blue: streams. Dashed: edge of the burned area.", font=f_small, fill=INK)

    # right: north arrow (north is away from the viewer) and scale bar
    ax, ay = x1 - 170, y0 + 40
    draw.polygon([(ax, ay), (ax - 40, ay + 130), (ax, ay + 100), (ax + 40, ay + 130)], fill=INK)
    draw.text((ax, ay + 175), "N", font=font(60, bold=True), fill=INK, anchor="mm")
    km10 = 10_000 / m_per_px
    bx, by = x1 - 300 - km10, y0 + 250
    draw.rectangle([bx, by, bx + km10, by + 18], fill=INK)
    draw.rectangle([bx + km10 / 2, by + 3, bx + km10 - 3, by + 15], fill="white")
    draw.text((bx + km10 / 2, by - 14), "10 km", font=f_text, fill=INK, anchor="mb")


# ---------------------------------------------------------------- mesh


def build_mesh(
    dem: np.ndarray,
    nx: int,
    size_m: tuple[float, float],
    ground: tuple[float, float],
    exaggeration: float,
    base_m: float,
    map_v: float,
):
    """Terrain grid on a closed block, with a flat ledge in front that carries the key (texture below map_v).
    Units are metres, +Y up, north towards -Z (glTF); centred on the origin, bottom at y=0."""
    width_m, depth_m = size_m
    ny = max(2, round(nx * depth_m / width_m))
    z = resample(dem, nx, ny)
    scale = width_m / ground[0]  # model metres per ground metre
    h = (z - z.min()) * scale * exaggeration + base_m

    xs = np.linspace(-width_m / 2, width_m / 2, nx, dtype=np.float32)
    zs = np.linspace(-depth_m / 2, depth_m / 2, ny, dtype=np.float32)  # row 0 = north = back
    X, Z = np.meshgrid(xs, zs)
    pos = np.stack([X, h.astype(np.float32), Z], -1).reshape(-1, 3)
    u, v = np.meshgrid(np.linspace(0, 1, nx, dtype=np.float32), np.linspace(0, map_v, ny, dtype=np.float32))
    uv = np.stack([u, v], -1).reshape(-1, 2)

    # normals from the height field
    gz, gx = np.gradient(h, zs, xs)
    nrm = np.stack([-gx, np.ones_like(gx), -gz], -1)
    nrm /= np.linalg.norm(nrm, axis=-1, keepdims=True)
    nrm = nrm.reshape(-1, 3).astype(np.float32)

    idx = np.arange(nx * ny, dtype=np.uint32).reshape(ny, nx)
    a, b, c, d = idx[:-1, :-1], idx[:-1, 1:], idx[1:, :-1], idx[1:, 1:]
    tris = np.concatenate([np.stack([a, c, b], -1).reshape(-1, 3), np.stack([b, c, d], -1).reshape(-1, 3)])
    tris = tris.reshape(-1).astype(np.uint32)

    # the ledge in front: a flat strip a little below the lowest ground, textured with the key
    ledge_d = depth_m * (1 - map_v) / map_v
    ledge_y = base_m * 0.5
    z1, z2 = zs[-1], zs[-1] + ledge_d
    k = len(pos)
    pos = np.concatenate(
        [pos, np.array([[xs[0], ledge_y, z1], [xs[-1], ledge_y, z1], [xs[0], ledge_y, z2], [xs[-1], ledge_y, z2]], np.float32)]
    )
    nrm = np.concatenate([nrm, np.tile(np.array([0, 1, 0], np.float32), (4, 1))])
    uv = np.concatenate([uv, np.array([[0, map_v], [1, map_v], [0, 1], [1, 1]], np.float32)])
    tris = np.concatenate([tris, np.array([k, k + 2, k + 1, k + 1, k + 2, k + 3], np.uint32)])
    terrain = {"pos": pos, "nrm": nrm, "uv": uv, "idx": tris}

    # block: four walls down to y=0 and a bottom face, flat-shaded
    sp, sn, si = [], [], []
    hh = h.astype(np.float32)

    def wall(top_pts, normal):
        n0 = sum(len(p) for p in sp)
        top = np.asarray(top_pts, np.float32)
        bottom = top.copy()
        bottom[:, 1] = 0
        verts = np.concatenate([top, bottom])
        m = len(top)
        sp.append(verts)
        sn.append(np.tile(np.asarray(normal, np.float32), (2 * m, 1)))
        i = np.arange(m - 1, dtype=np.uint32)
        t0, t1, b0, b1 = n0 + i, n0 + i + 1, n0 + m + i, n0 + m + i + 1
        si.append(np.stack([t0, b0, t1, t1, b0, b1], -1).reshape(-1))

    wall(np.stack([xs, hh[-1], np.full(nx, zs[-1])], -1), (0, 0, 1))  # south, faces the viewer
    wall(np.stack([xs[::-1], hh[0][::-1], np.full(nx, zs[0])], -1), (0, 0, -1))  # north
    wall(np.stack([np.full(ny, xs[-1]), hh[:, -1][::-1], zs[::-1]], -1), (1, 0, 0))  # east
    wall(np.stack([np.full(ny, xs[0]), hh[:, 0], zs], -1), (-1, 0, 0))  # west
    wall([[xs[0], ledge_y, z2], [xs[-1], ledge_y, z2]], (0, 0, 1))  # ledge front
    wall([[xs[-1], ledge_y, z2], [xs[-1], ledge_y, z1]], (1, 0, 0))  # ledge east
    wall([[xs[0], ledge_y, z1], [xs[0], ledge_y, z2]], (-1, 0, 0))  # ledge west
    n0 = sum(len(p) for p in sp)
    sp.append(np.array([[xs[0], 0, zs[0]], [xs[-1], 0, zs[0]], [xs[0], 0, z2], [xs[-1], 0, z2]], np.float32))
    sn.append(np.tile(np.array([0, -1, 0], np.float32), (4, 1)))
    si.append(np.array([n0, n0 + 1, n0 + 2, n0 + 1, n0 + 3, n0 + 2], np.uint32))
    skirt = {"pos": np.concatenate(sp), "nrm": np.concatenate(sn), "idx": np.concatenate(si).astype(np.uint32)}
    for part in (terrain, skirt):  # centre front to back
        part["pos"][:, 2] -= ledge_d / 2
    return terrain, skirt, (nx, ny), depth_m + ledge_d


# ---------------------------------------------------------------- writers


def write_glb(path: Path, terrain: dict, skirt: dict, jpeg: bytes, name: str):
    blob = bytearray()
    views, accessors = [], []

    def add_view(data: bytes, target=None) -> int:
        while len(blob) % 4:
            blob.append(0)
        views.append({"buffer": 0, "byteOffset": len(blob), "byteLength": len(data), **({"target": target} if target else {})})
        blob.extend(data)
        return len(views) - 1

    def add_acc(arr: np.ndarray, kind: str, target: int, minmax=False) -> int:
        comp = 5125 if arr.dtype == np.uint32 else 5126
        acc = {"bufferView": add_view(arr.tobytes(), target), "componentType": comp, "count": int(arr.shape[0]), "type": kind}
        if minmax:
            acc["min"] = arr.min(0).tolist()
            acc["max"] = arr.max(0).tolist()
        accessors.append(acc)
        return len(accessors) - 1

    ARRAY, ELEMENTS = 34962, 34963
    t_prim = {
        "attributes": {
            "POSITION": add_acc(terrain["pos"], "VEC3", ARRAY, True),
            "NORMAL": add_acc(terrain["nrm"], "VEC3", ARRAY),
            "TEXCOORD_0": add_acc(terrain["uv"], "VEC2", ARRAY),
        },
        "indices": add_acc(terrain["idx"], "SCALAR", ELEMENTS),
        "material": 0,
    }
    s_prim = {
        "attributes": {"POSITION": add_acc(skirt["pos"], "VEC3", ARRAY, True), "NORMAL": add_acc(skirt["nrm"], "VEC3", ARRAY)},
        "indices": add_acc(skirt["idx"], "SCALAR", ELEMENTS),
        "material": 1,
    }
    img_view = add_view(jpeg)
    skirt_rgb = [c / 255 for c in hex_rgb(SKIRT)]
    gltf = {
        "asset": {"version": "2.0", "generator": "Ash Watch tools/build_ar_model.py"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0, "name": name}],
        "meshes": [{"name": name, "primitives": [t_prim, s_prim]}],
        "materials": [
            {
                "name": "map",
                "pbrMetallicRoughness": {"baseColorTexture": {"index": 0}, "metallicFactor": 0, "roughnessFactor": 1},
            },
            {
                "name": "sides",
                "pbrMetallicRoughness": {"baseColorFactor": skirt_rgb + [1], "metallicFactor": 0, "roughnessFactor": 1},
            },
        ],
        "textures": [{"source": 0, "sampler": 0}],
        "samplers": [{"magFilter": 9729, "minFilter": 9987, "wrapS": 33071, "wrapT": 33071}],
        "images": [{"bufferView": img_view, "mimeType": "image/jpeg"}],
        "accessors": accessors,
        "bufferViews": views,
    }
    while len(blob) % 4:
        blob.append(0)
    gltf["buffers"] = [{"byteLength": len(blob)}]
    js = json.dumps(gltf, separators=(",", ":")).encode()
    js += b" " * (-len(js) % 4)
    out = bytearray(b"glTF") + struct.pack("<II", 2, 12 + 8 + len(js) + 8 + len(blob))
    out += struct.pack("<I4s", len(js), b"JSON") + js + struct.pack("<I4s", len(blob), b"BIN\0") + blob
    path.write_bytes(out)


def write_usdz(path: Path, terrain: dict, skirt: dict, texture: Path, work: Path):
    """USDZ for AR Quick Look on iPhone and iPad. Needs usd-core (pxr)."""
    from pxr import Gf, Sdf, Usd, UsdGeom, UsdShade, UsdUtils, Vt

    usdc = work / "burgohondo.usdc"
    stage = Usd.Stage.CreateNew(str(usdc))
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)
    root = UsdGeom.Xform.Define(stage, "/Burgohondo")
    stage.SetDefaultPrim(root.GetPrim())

    def material(name, texture_file=None, rgb=None):
        mat = UsdShade.Material.Define(stage, f"/Burgohondo/Looks/{name}")
        pbr = UsdShade.Shader.Define(stage, f"/Burgohondo/Looks/{name}/PBR")
        pbr.CreateIdAttr("UsdPreviewSurface")
        pbr.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(1.0)
        pbr.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(0.0)
        mat.CreateSurfaceOutput().ConnectToSource(pbr.ConnectableAPI(), "surface")
        if texture_file:
            st = UsdShade.Shader.Define(stage, f"/Burgohondo/Looks/{name}/st")
            st.CreateIdAttr("UsdPrimvarReader_float2")
            st.CreateInput("varname", Sdf.ValueTypeNames.String).Set("st")
            tex = UsdShade.Shader.Define(stage, f"/Burgohondo/Looks/{name}/tex")
            tex.CreateIdAttr("UsdUVTexture")
            tex.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(texture_file)
            tex.CreateInput("wrapS", Sdf.ValueTypeNames.Token).Set("clamp")
            tex.CreateInput("wrapT", Sdf.ValueTypeNames.Token).Set("clamp")
            tex.CreateInput("st", Sdf.ValueTypeNames.Float2).ConnectToSource(st.ConnectableAPI(), "result")
            tex.CreateOutput("rgb", Sdf.ValueTypeNames.Float3)
            pbr.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).ConnectToSource(tex.ConnectableAPI(), "rgb")
        else:
            pbr.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*rgb))
        return mat

    def mesh(name, part, mat, with_uv):
        m = UsdGeom.Mesh.Define(stage, f"/Burgohondo/{name}")
        m.CreatePointsAttr(Vt.Vec3fArray.FromNumpy(part["pos"]))
        m.CreateNormalsAttr(Vt.Vec3fArray.FromNumpy(part["nrm"]))
        m.SetNormalsInterpolation(UsdGeom.Tokens.vertex)
        m.CreateFaceVertexCountsAttr(Vt.IntArray.FromNumpy(np.full(len(part["idx"]) // 3, 3, np.int32)))
        # glTF winds counter-clockwise like USD's default "rightHanded" orientation
        m.CreateFaceVertexIndicesAttr(Vt.IntArray.FromNumpy(part["idx"].astype(np.int32)))
        m.CreateSubdivisionSchemeAttr(UsdGeom.Tokens.none)
        m.CreateExtentAttr(Vt.Vec3fArray([Gf.Vec3f(*part["pos"].min(0).tolist()), Gf.Vec3f(*part["pos"].max(0).tolist())]))
        if with_uv:
            st = part["uv"].copy()
            st[:, 1] = 1.0 - st[:, 1]  # USD texture origin is bottom-left
            pv = UsdGeom.PrimvarsAPI(m).CreatePrimvar("st", Sdf.ValueTypeNames.TexCoord2fArray, UsdGeom.Tokens.vertex)
            pv.Set(Vt.Vec2fArray.FromNumpy(st))
        UsdShade.MaterialBindingAPI.Apply(m.GetPrim()).Bind(mat)

    mesh("Terrain", terrain, material("Map", texture_file=f"./{texture.name}"), True)
    mesh("Sides", skirt, material("Sides", rgb=[c / 255 for c in hex_rgb(SKIRT)]), False)
    stage.GetRootLayer().Save()
    if not UsdUtils.CreateNewARKitUsdzPackage(Sdf.AssetPath(str(usdc)), str(path)):
        raise RuntimeError("usdz packaging failed")


# ---------------------------------------------------------------- main


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", type=Path, default=ROOT / "web" / "public" / "ar")
    ap.add_argument(
        "--cache",
        type=Path,
        default=Path.home() / ".cache" / "ashwatch-ar",
        help="where the DEM crop and the texture are kept between runs",
    )
    ap.add_argument("--width-cm", type=float, default=50.0, help="real-world width of the model in AR")
    ap.add_argument("--exaggeration", type=float, default=2.5, help="vertical exaggeration (the site map uses 2.5)")
    ap.add_argument("--grid", type=int, default=300, help="vertices across; 300 gives about 140k triangles")
    ap.add_argument("--texture", type=int, default=4096, help="texture width in pixels")
    ap.add_argument("--base-mm", type=float, default=8.0, help="thickness of the block under the lowest point")
    ap.add_argument("--no-usdz", action="store_true", help="skip the iPhone file (no usd-core needed)")
    args = ap.parse_args()

    bbox = load_bbox()
    meta = json.loads((DATA / "meta.json").read_text(encoding="utf-8"))
    aw, as_, ae, an = meta["aoi_bbox"]
    if not (aw - 0.25 < bbox[0] < bbox[2] < ae + 0.25 and as_ - 0.25 < bbox[1] < bbox[3] < an + 0.25):
        # exports made before pipeline commit 794f4f2 had swapped corners (see web/src/data.js)
        print(f"error: layers.json extent {bbox} is outside the AOI in meta.json; re-export first", file=sys.stderr)
        return 1
    dem = load_dem(bbox, args.cache)
    print(f"DEM {dem.shape[1]}x{dem.shape[0]} px, {dem.min():.0f} to {dem.max():.0f} m", flush=True)

    w, s, e, n = bbox
    lat0 = (s + n) / 2
    ground = ((e - w) * M_PER_DEG_LON_EQ * math.cos(math.radians(lat0)), (n - s) * M_PER_DEG_LAT)
    width_m = args.width_cm / 100
    size_m = (width_m, width_m * ground[1] / ground[0])

    tex_img, _, map_v = bake_texture(dem, bbox, args.texture, meta, args.exaggeration)
    args.cache.mkdir(parents=True, exist_ok=True)
    tex_path = args.cache / "burgohondo_texture.jpg"
    tex_img.save(tex_path, quality=86, optimize=True, progressive=False)
    jpeg = tex_path.read_bytes()

    terrain, skirt, grid, total_depth = build_mesh(dem, args.grid, size_m, ground, args.exaggeration, args.base_mm / 1000, map_v)
    n_tri = (len(terrain["idx"]) + len(skirt["idx"])) // 3

    args.out.mkdir(parents=True, exist_ok=True)
    glb = args.out / "burgohondo.glb"
    write_glb(glb, terrain, skirt, jpeg, "Burgohondo fire area")
    print(
        f"wrote {glb.relative_to(ROOT)}: {glb.stat().st_size / 1e6:.1f} MB, {n_tri:,} triangles, "
        f"texture {tex_img.width}x{tex_img.height}",
        flush=True,
    )

    usdz = args.out / "burgohondo.usdz"
    if args.no_usdz:
        print("skipped the .usdz (--no-usdz); model-viewer then builds one on the phone from the .glb")
    else:
        try:
            write_usdz(usdz, terrain, skirt, tex_path, args.cache)
            print(f"wrote {usdz.relative_to(ROOT)}: {usdz.stat().st_size / 1e6:.1f} MB")
        except ImportError:
            print("usd-core is not installed: skipped the .usdz. Run with `uv run` to get it.", file=sys.stderr)

    relief_cm = float(terrain["pos"][:, 1].max() - args.base_mm / 1000) * 100
    info = {
        "title": "Burgohondo fire area, after the fire",
        "glb": glb.name,
        "usdz": usdz.name if usdz.exists() else None,
        "width_cm": round(size_m[0] * 100, 1),
        "depth_cm": round(total_depth * 100, 1),
        "relief_cm": round(relief_cm, 1),
        "ground_km": [round(ground[0] / 1000, 1), round(ground[1] / 1000, 1)],
        "bbox": [round(v, 5) for v in bbox],
        "exaggeration": args.exaggeration,
        "triangles": n_tri,
        "grid": list(grid),
        "dem": "Copernicus DEM GLO-30 (AWS open data)",
        "data_generated": meta["generated"],
        "built": datetime.now(UTC).replace(microsecond=0).isoformat(),
    }
    (args.out / "model.json").write_text(json.dumps(info, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {(args.out / 'model.json').relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
