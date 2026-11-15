# Fire Before the Storm: Ash Watch

**The fire is out. The danger isn't.**

Ash Watch is a post-fire warning for drinking water. After a wildfire it tells each town downstream how its
water could be polluted, by which pathway, and how confident that estimate is. It is built on NASA-ISRO NISAR
L-band radar, which measures the forest before the fire, the burn through smoke, and the regrowth afterwards.

Project for the [NASA Space Apps Challenge 2026](https://www.spaceappschallenge.org/2026/), challenge
*Dancing with the SARs*. Team: Andrea Serio and Masha Golikova. Demo case: the Burgohondo fire in Ávila,
Spain (July 2026) and the ash-laden runoff that followed the first autumn rain in October.

![Fire Before the Storm](media/Lockup%20%C2%B7%20drop%20in%20the%20flame.png)

## How it works

```
NISAR GCOV (HH, HV) ─┐
Sentinel-2, DEM,     ├─►  pipeline/ on the HPC cluster  ─►  web/public/data/  ─►  web/ story site
biomass, soil, wind, ┘    13 steps, run once per fire        small files            static, MapLibre
rain, OpenStreetMap                                          (the data contract)
```

| Pathway | Question for the town | Confidence |
| --- | --- | --- |
| Surface runoff | Will rain wash ash and sediment into the stream or reservoir we drink from? | High |
| Debris flow | Can one storm send mud and ash into our intakes? | Medium: model calibrated in the western US |
| Groundwater | Should we test our wells and springs? | Screening only |
| Airborne ash | Did ash fall on our reservoir, and can dry ash still blow in? | Indicative only |

Methods, one paragraph each: [pipeline/README.md](pipeline/README.md). Full plan:
[Fire Before the Storm — Ash Watch build plan.md](Fire%20Before%20the%20Storm%20%E2%80%94%20Ash%20Watch%20build%20plan.md).

## Repository

```
pipeline/           HPC jobs (steps 01 to 13), config, Slurm scripts, synthetic end-to-end test
web/                story site: Vite + React + MapLibre GL
  public/data/      exported files, written by pipeline step 12 (the data contract)
  src/chapters.js   the story as data: text, camera and layers per chapter
tools/check_data.py checks the exported files against the contract
docs/               data contract, site concepts
.github/workflows/  CI on every pull request, deploy to GitHub Pages on main
CLAUDE.md           how the two of us (and Claude Code) work in this repository
```

## Run the site

```bash
cd web
npm install
npm run dev
```

Open http://localhost:5173. The site reads `web/public/data/` as committed; no pipeline run is needed.

## Check the data

```bash
python tools/check_data.py
```

Standard library only. Errors mean the site would break or show something wrong; warnings mean a number
looks implausible and needs a human look. The same check runs in CI and before each deploy.

## Run the pipeline

Needs an HPC cluster or a large workstation, a NASA Earthdata login and a Copernicus CDS key. See
[pipeline/README.md](pipeline/README.md), or [pipeline/BLUEBEAR.md](pipeline/BLUEBEAR.md) for the University
of Birmingham cluster. A smoke test on synthetic data needs no downloads:

```bash
cd pipeline
bash tests/run_synthetic.sh /tmp/aw_test
```

## Limits, stated plainly

- One fire is a case study, not a validation.
- The debris-flow model (Staley et al. 2017, M1) was calibrated in the western United States; read its output
  as a ranking.
- Burn severity classes come from Sentinel-2 dNBR where the ground is visible; the radar confirms the burn and
  fills cloud and smoke gaps.
- L-band HV saturates near 100 Mg/ha of biomass, so ash in dense stands is a lower bound.
- IMERG rain is a 10 km, 30-minute average and underestimates short storm peaks.
- Groundwater and airborne ash have no local measurements behind them and are labelled screening and
  indicative.

## Data and credits

NASA-ISRO NISAR L2 GCOV (ASF DAAC) · NASA GPM IMERG · Copernicus Sentinel-2 L2A · Copernicus DEM GLO-30 ·
ESA CCI Biomass · ISRIC SoilGrids · ERA5 (Copernicus C3S) · OpenStreetMap contributors · Staley et al. (2017)
M1 debris-flow model (USGS). Basemap: OpenFreeMap, OpenMapTiles, OpenStreetMap contributors.

Code written with heavy use of Claude Code; commits carry a `Co-Authored-By` line where it applies.

## License

Apache-2.0, see [LICENSE](LICENSE).
