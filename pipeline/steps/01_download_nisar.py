#!/usr/bin/env python
"""Step 01: find and download NISAR L2 GCOV files over the AOI from the ASF DAAC.

Credentials (one of):
  export EARTHDATA_TOKEN=...                      # EDL token from urs.earthdata.nasa.gov -> Generate Token
  export EARTHDATA_USERNAME=... EARTHDATA_PASSWORD=...
  or a ~/.netrc line:  machine urs.earthdata.nasa.gov login USER password PASS

Always writes data/raw/nisar/urls.txt and manifest.csv, so you can also download with wget
(see scripts/download_wget.sh). Use --dry-run to only list.
"""
import csv
import netrc
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ashwatch.common import LOG, cli, earthdata_token, load_config, n_workers, path, setup_logging  # noqa: E402
from ashwatch.nisar import parse_name  # noqa: E402


def session():
    import asf_search as asf
    s = asf.ASFSession()
    tok = earthdata_token()
    if tok:
        return s.auth_with_token(tok)
    user, pw = os.environ.get("EARTHDATA_USERNAME"), os.environ.get("EARTHDATA_PASSWORD")
    if not (user and pw):
        try:
            auth = netrc.netrc().authenticators("urs.earthdata.nasa.gov")
            if auth:
                user, _, pw = auth
        except (FileNotFoundError, netrc.NetrcParseError):
            pass
    if not (user and pw):
        raise SystemExit("No Earthdata credentials: run scripts/setup_credentials.sh, or set EARTHDATA_TOKEN, or EARTHDATA_USERNAME/PASSWORD, or ~/.netrc")
    return s.auth_with_creds(user, pw)


def size_mb(props):
    """File size in MB, or "" if unknown. Depending on the asf_search version `bytes` is a number,
    missing, or a dict {file name: {"bytes": n, "format": ...}} listing every file of the granule."""
    b = props.get("bytes")
    if isinstance(b, dict):
        name = Path(props.get("url", "")).name
        vals = {k: (v.get("bytes") if isinstance(v, dict) else v) for k, v in b.items()}
        b = vals.get(name) or sum(v for v in vals.values() if isinstance(v, (int, float)))
    try:
        return int(float(b) // 1e6) if b else ""
    except (TypeError, ValueError):
        return ""


def main():
    ap = cli(__doc__)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--max-files", type=int, default=0)
    ap.add_argument("--passes", nargs="*", default=[], metavar="TRACKDIR",
                    help="only these passes, e.g. 087A 095D (see the track and dir columns of manifest.csv)")
    args = ap.parse_args()
    setup_logging()
    cfg = load_config(args.config)
    import asf_search as asf

    w, s, e, n = cfg["aoi"]["bbox"]
    wkt = f"POLYGON(({w} {s},{e} {s},{e} {n},{w} {n},{w} {s}))"
    d = cfg["dates"]
    LOG.info("Searching ASF for NISAR %s %s..%s", cfg["nisar"]["product"], d["pre_start"], d["series_end"])
    res = asf.search(dataset="NISAR", processingLevel=cfg["nisar"]["product"], intersectsWith=wkt,
                     start=f"{d['pre_start']}T00:00:00Z", end=f"{d['series_end']}T23:59:59Z", maxResults=2000)
    best = {}   # granule name without the trailing product counter -> (counter, result, info)
    for r in res:
        name = r.properties.get("fileID") or r.properties.get("sceneName") or r.properties.get("fileName", "")
        info = parse_name(name) or parse_name(r.properties.get("fileName", ""))
        if not info or info["prodcfg"] != cfg["nisar"]["production_config"]:
            continue
        # the same granule can be listed twice (..._001.h5 and ..._002.h5): keep the newest only
        stem = Path(r.properties["url"]).stem
        m = re.match(r"(.*)_(\d{3})$", stem)
        base, counter = (m.group(1), int(m.group(2))) if m else (stem, 0)
        if base not in best or counter > best[base][0]:
            best[base] = (counter, r, info)
    n_listed = len(res)
    keep = [(r, info) for _, r, info in best.values()]
    keep.sort(key=lambda t: t[1]["datetime"])
    LOG.info("%d products listed, %d kept after dropping other configs and older duplicates", n_listed, len(keep))
    if args.passes:
        keep = [t for t in keep if t[1]["key"] in args.passes]
    if args.max_files:
        keep = keep[: args.max_files]
    LOG.info("%d GCOV products after filtering (production config %s)", len(keep), cfg["nisar"]["production_config"])

    out_dir = path(cfg, "raw", "nisar", "x").parent
    with open(out_dir / "urls.txt", "w") as f:
        for r, _ in keep:
            f.write(r.properties["url"] + "\n")
    with open(out_dir / "manifest.csv", "w", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(["date", "track", "dir", "frame", "crid", "size_mb", "url"])
        for r, i in keep:
            wr.writerow([i["date"], i["track"], i["dir"], i["frame"], i["crid"], size_mb(r.properties), r.properties["url"]])
    LOG.info("Wrote %s and manifest.csv", out_dir / "urls.txt")
    if args.dry_run:
        return
    todo = asf.ASFSearchResults([r for r, _ in keep if not (out_dir / Path(r.properties["url"]).name).exists()])
    LOG.info("Downloading %d files to %s with %d processes", len(todo), out_dir, min(4, n_workers()))
    todo.download(path=str(out_dir), session=session(), processes=min(4, n_workers()))
    LOG.info("Done")


if __name__ == "__main__":
    main()
