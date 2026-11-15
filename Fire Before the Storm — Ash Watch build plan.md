# Fire Before the Storm — Ash Watch build plan

Nov 14, 2026 · @Masha

## The pitch

**Ash Watch is a post-fire warning service: days after a wildfire, it tells every town downstream how its drinking water could be polluted, by which pathway, and at how much rain.** Team: Fire Before the Storm. Tagline: *The fire is out. The danger isn't.*

- **The Ávila case.** In early October 2026, rain washed ash from the Burgohondo fire into the Tiétar basin. Tap water in Casavieja and Piedralaves was declared unfit, and El Barraco's mayor warned that El Burguillo reservoir could be next ([Reuters via KFGO](https://kfgo.com/2026/10/07/wildfire-ash-turns-spanish-mountain-river-black-contaminating-water-supply/)).
- **It lasts for years.** Across 500 western-US watersheds, pollutants after fires peaked up to 103 times pre-fire levels, and nitrogen and sediment stayed high for up to eight years ([Grist](https://grist.org/wildfires/pollution-from-wildfires-can-contaminate-our-water-for-up-to-eight-years-new-study-finds/)).
- **The gap.** The USGS runs post-fire hazard assessments for US fires ([USGS](https://pubs.usgs.gov/publication/ofr20231025/full)); in the EU, post-fire management is a patchwork of regional tools ([Fire Ecology, 2026](https://link.springer.com/10.1186/s42408-026-00481-9)).
- **Users.** Town halls, water utilities, river basin authorities, civil protection.
- **Why NISAR.** One L-band radar measures the fuel before the fire, the burn through smoke, and the regrowth after it, everywhere on land, every 12 days.
- **Global by design.** Ávila is the demo. Every input has a global dataset, so the same pipeline runs for any fire NISAR has seen.

## What Ash Watch tells a town

Each town gets one card: a level per pathway, the evidence behind it, and the rain that would trigger the main one. Weakly evidenced pathways are labelled as screening, so the tool never overclaims.

| Pathway | The town's question | Main drivers | Confidence |
| --- | --- | --- | --- |
| Surface runoff | Will rain wash ash and sediment into the stream or reservoir we drink from? | Burned share upstream, ash load, slope, soil, rain | High: well-studied |
| Debris flow | Can one storm send mud and ash into our intakes, roads and bridges? | Steep burned catchments, soil, 15-min rain | Medium: model calibrated in the US |
| Groundwater | Should we test our wells and springs? | Burn over the recharge area, depth to water, aquifer type, soil | Low: screening only |
| Airborne ash | Did ash fall on our reservoir during the fire, and can dry ash still blow in? | Wind during and after the fire, distance downwind | Low to medium: indicative |

Every card also shows the **trigger rain** (mm in 15 minutes) and a **risk trend** that falls as NISAR sees vegetation regrow.

## Architecture

The cluster does all the heavy maths once per fire; the story site and the laptop only read the small exported files.

&#91;embedded content: Ash Watch architecture · 6 inputs, 4 cluster steps, 1 export, 2 consumers\]

Scaling to another fire means a new area of interest and a re-run of the cluster jobs; nothing in the site changes.

## The science of each layer

Each layer uses an established method; where the evidence is thin, the layer becomes a screening index, not a forecast.

**Polarization does two jobs.** HV comes from volume scattering in branches and trunks, so it tracks biomass and its loss in the fire. HH responds to bare and wet ground. After the fire HV drops; after rain HH rises on bare soil. Using both, plus the HV/HH ratio, separates "burned" from "just wet".

| Layer | How we compute it | Evidence and caveat |
| --- | --- | --- |
| Fuel (forest density) | Mean HV over the pre-fire dates (Jun 20 to Jul 21), regressed to biomass using ESA CCI Biomass as reference | L-band HV stays sensitive up to about 100 Mg/ha on average ([Yu and Saatchi, 2016](https://mdpi.com/2072-4292/8/6/522)); denser stands are capped, so ash is a lower bound there |
| Burn severity | Log-ratio of HV and HH, Jul 21 to Jul 26, classified against Sentinel-2 dNBR on smoke-free pixels | Radar works through smoke; class probabilities carry the uncertainty |
| Ash load | Biomass × share burned (by severity) × ash fraction, Monte Carlo over the uncertain fractions | Ash amount depends on fuel load, fuel type and combustion completeness ([Bodí et al., 2014](https://agris.fao.org/search/en/records/65df0fb94c5aef494fdf5e3a)); one field study measured ash at about 12.5% of fuel consumed ([Quigley et al., 2019](https://link.springer.com/doi/10.1186/s42408-018-0015-7)) |
| Surface runoff | Per catchment: upstream ash, plus post-fire soil loss (RUSLE with a severity-based cover factor) × sediment delivery ratio | Standard erosion modelling; flow-based catchments replace fixed buffer zones |
| Debris flow | USGS pfdf Staley M1 likelihood and 15-min trigger rain per stream segment | Calibrated in the western US: show a parameter-sweep band |
| Groundwater | DRASTIC-style vulnerability (depth to water, recharge, aquifer type, soil, slope) × burned share of each well's or spring's recharge area | Fire impacts on groundwater are poorly studied ([Emelko et al., EGU 2023](https://meetingorganizer.copernicus.org/EGU23/EGU23-10824.html)), but some fire-mobilised metals leach into it and persist ([High Country News](https://mavensnotebook.com/2026/04/20/high-country-news-wildfires-make-soils-poisonous/)): output is "test first" priority |
| Airborne ash | ERA5 hourly wind during the fire: wind rose, downwind sectors with distance decay; dry windy days before the first rain | Indicative only, no deposition measurements; wind sectors replace circular buffers |
| Recovery | HV regrowth per catchment, Aug to Nov | Lowers the runoff score as cover returns; flags slopes still bare before winter |

**What to test for.** A global dataset of wildfire ash found mean manganese at 1,488 mg/kg, zinc 181 mg/kg and lead 66.9 mg/kg ([global wildfire-ash study](https://edepot.wur.nl/637298)). Town cards list these, plus turbidity, nitrogen and phosphorus, as the first lab checks.

## Scope

Core ships by Sunday 13:00 for Ávila; stretch only after that.

**Core**

1. NISAR stack, fuel, burn severity and ash load (single best estimate).
2. Surface runoff and debris-flow scores with trigger rain, per stream and per town.
3. Airborne ash: fire-period wind rose and downwind exposure.
4. Groundwater screening for wells and springs found in OpenStreetMap.
5. Town cards for Casavieja, Piedralaves, El Barraco and El Burguillo reservoir.
6. October hindcast.
7. Scroll story on Vercel with the Ávila map.

**Stretch, in order**

1. Monte Carlo ash ranges (P10 to P90).
2. Recovery trend from NISAR regrowth.
3. Second fire (Gironde, France) to prove it travels.
4. Europe atlas of 2026 fires, batch-run on the cluster.

## Data: Ávila and the global version

Every layer runs on a global dataset; a national map is only an optional upgrade. That is the scaling story.

| Layer | Ávila demo | Global equivalent | Access |
| --- | --- | --- | --- |
| Radar | [NISAR L2 GCOV](https://nisar-docs.asf.alaska.edu/products-overview/) HH/HV, Jun 20 to Nov 6 (gap Jul 27 to Aug 10) | Same, all land every 12 days | `asf_search` / `earthaccess`, Earthdata login |
| Fire perimeter | [EFFIS](https://effis.jrc.ec.europa.eu/) | [GWIS](https://gwis.jrc.ec.europa.eu/), FIRMS hotspots | Download |
| Optical severity | Sentinel-2 L2A | Sentinel-2, Landsat | [Earth Search STAC](https://earth-search.aws.element84.com/v1) |
| Biomass reference | [ESA CCI Biomass](https://climate.esa.int/en/projects/biomass/), 100 m | Same | Download (large: subset on the cluster) |
| Terrain and rivers | [Copernicus DEM GLO-30](https://registry.opendata.aws/copernicus-dem/) | Same, plus MERIT Hydro | AWS open bucket |
| Soil | [ESDAC K-factor](https://esdac.jrc.ec.europa.eu/content/soil-erodibility-k-factor-high-resolution-dataset-europe) | [SoilGrids](https://soilgrids.org/) | Direct (ESDAC needs a form) |
| Groundwater | IGME hydrogeological map (Spain), BGR IHME1500 (Europe) | Fan et al. global water-table depth, GLHYMPS permeability | Download; check licences |
| Wind | ERA5 hourly 10 m wind | Same | [Copernicus CDS](https://cds.climate.copernicus.eu/) API key |
| Rain | GPM IMERG half-hourly | Same | `earthaccess` |
| People and water points | OpenStreetMap (towns, wells, springs, water works), GHSL population | Same | Geofabrik, GHSL |

Open question: Spanish municipal water-intake locations. If none are public, we use OSM plus the towns named in the October reports.

## Pre-computed on the cluster

Everything heavy runs once on the HPC cluster; the website and the laptop only read the exported files, kept under about 100 MB.

| # | Job on the cluster | Exported for the web |
| --- | --- | --- |
| 1 | Download and subset all NISAR GCOV dates to the AOI, 30 m, HH and HV in dB | Before/after images (PMTiles); per-catchment HV and HH time series (JSON) |
| 2 | Fuel: pre-fire HV to biomass, calibrated on ESA CCI | Biomass layer |
| 3 | Burn severity: radar change classified against dNBR | Severity layer with confidence |
| 4 | Ash load per pixel and per catchment (Monte Carlo in stretch) | Ash layer; tonnes per catchment |
| 5 | Hydrology: pfdf streams, M1 likelihood, trigger rain, RUSLE | Streams with attributes (GeoJSON) |
| 6 | Wind: ERA5 wind rose for the fire period, downwind exposure | Wind rose (JSON), exposure layer |
| 7 | Groundwater screening grid; score every OSM well and spring | Wells and springs with scores (GeoJSON) |
| 8 | Town table: every pathway joined per settlement | `towns.json` |
| 9 | Hindcast: IMERG Oct 1 to 7 peak intensities against thresholds | `hindcast.json` |
| 10 | Stretch: jobs 1 to 8 for every 2026 EU fire over 1,000 ha | `atlas.geojson` |

**Formats.** Rasters as Cloud-Optimized GeoTIFF on the cluster, converted to raster PMTiles for the map; vectors as GeoJSON, or PMTiles via tippecanoe if large. All web files go to `web/public/data/`.

**Data contract, agreed by 17:00 today.** The site is built on mock files with the same names and fields, then swapped. One record of `towns.json`:

```json
{"id": "casavieja", "name": "Casavieja", "lon": null, "lat": null, "population": null,
 "upstream_burned_pct": null, "ash_t": {"p10": null, "p50": null, "p90": null},
 "pathways": {
   "runoff":      {"level": "high|medium|low", "trigger_mm_15min": null},
   "debris_flow": {"level": "...", "likelihood_at_24mm_h": null},
   "groundwater": {"level": "...", "confidence": "screening"},
   "airborne":    {"level": "...", "downwind_hours": null}},
 "recovery": [{"date": "2026-08-19", "hv_db": null}],
 "tests": ["turbidity", "manganese", "lead", "nitrogen", "phosphorus"]}
```

**Repository layout** ([Fire-Before-The-Storm](https://github.com/Andrea-S90/Fire-Before-The-Storm), Apache-2.0):

```
pipeline/     HPC jobs 01_download ... 09_hindcast, plus Slurm scripts
notebooks/    laptop checks on the exported files
web/          story site (Vercel root directory)
  public/data/  exported files, the data contract
docs/         method notes, data credits
```

## Story site on Vercel

One scrolling page, problem to solution to the Ávila demo, with a sticky map that changes as the reader scrolls. It is also the challenge's interactive application.

**Stack.** Vite + React, Scrollama for scroll steps, MapLibre GL JS with the PMTiles protocol for layers, plain SVG for the wind rose and small charts. In Vercel: import the repo, root directory `web`, framework Vite, output `dist`. Static files only, no server.

| # | Chapter | What the reader sees | Data |
| --- | --- | --- | --- |
| 1 | The tap water turned black | Text over a Sentinel-2 view of the Tiétar valley; quote of the October reports, no news photos | Sentinel-2 |
| 2 | The fire | Perimeter grows Jul 22 to Aug 6 | EFFIS |
| 3 | What radar sees | Before/after slider of NISAR HV; one line on HH vs HV | Job 1 |
| 4 | From forest to ash | Biomass layer fades into the ash layer | Jobs 2 to 4 |
| 5 | Four ways ash reaches your tap | Map steps: streams, debris-flow segments, wind rose and plume sector, wells and springs | Jobs 5 to 7 |
| 6 | Town cards | Casavieja, Piedralaves, El Barraco, El Burguillo; click any town on the map | `towns.json` |
| 7 | Could we have known? | October rain against each stream's trigger | `hindcast.json` |
| 8 | The land heals | Regrowth curve per catchment (stretch) | Job 1 |
| 9 | Any fire, anywhere | Global data table; Europe atlas if ready | Job 10 |
| 10 | Team and credits | NASA, ESA, Copernicus, USGS pfdf, OSM | — |

Keep images to our own maps and open satellite data; link the news reports rather than reuse their photos.

**Later, tracked in its own issue (not for the 16:00 submission):** open the story with screenshots of the news headlines about the contaminated water, so the reader sees the event was real before any map appears. Crop to the headline, outlet and date, link each to its article, and leave out the outlets' photos; check each outlet's terms before publishing.

## Timeline and roles

The mathematician owns the radar and the model on the cluster; the analyst owns the story site, design, slides and video. Shared: the data contract at 17:00 and the hindcast check.

&#91;embedded content: Build timeline · 6 phases, 2 people, 2 gates\]

Rule of thumb: if a step is two hours late, drop the next stretch item, never the hindcast or the video. Update, Sunday morning: the hard stop is 16:00 (Barcelona local event), not 23:59, so the core freeze at 13:00 stands and stretch items are off.

## Validation: the October hindcast

The headline test: using only data available on August 1, would Ash Watch have flagged the streams above Casavieja and Piedralaves before the early-October rains?

1. **Freeze inputs at Aug 1.** NISAR Jul 21 and Jul 26, Sentinel-2 to Aug 1, DEM, soil.
2. **Compare thresholds with the storm.** Peak 15- and 30-minute IMERG rain over each catchment in early October, against each segment's trigger threshold.
3. **Check against what happened.** Black water and washed-out bridges at Casavieja, unfit tap water at Piedralaves ([Reuters via devdiscourse](https://www.devdiscourse.com/article/international/3988408-wildfire-ash-turns-spanish-mountain-river-black-contaminating-water-supply)).
4. **Independent look.** Sentinel-2 colour of the Tiétar and El Burguillo before and after the rain; NISAR Oct 1 against Oct 6.
5. **Severity cross-check.** NISAR severity classes against dNBR classes: confusion matrix and kappa.

Be honest in the pitch: one fire is a case study, not proof. IMERG's 10 km grid also underestimates short storm peaks, so treat its intensities as a lower bound. The groundwater and airborne pathways have no local measurements to check against, which is why they stay labelled as screening.

## Demo and submission

**Two deadlines, both on Sunday Nov 15.** We are at the Barcelona local event: submit by **16:00** and present live at **16:30**. The global form closes at 23:59 Barcelona time ([submission guide](https://www.spaceappschallenge.org/resources/project-submission-guide/)).

- **Edits after submitting.** The guide allows editing and resubmitting as often as we like until 23:59; only the last saved submission is judged globally. Whether Barcelona's judges accept changes after 16:00 is the Local Lead's call: ask before relying on it. Plan: submit a complete version by 15:30, then improve and resubmit only if allowed.
- **Demo.** A video of 30 seconds or less, or at most 7 slides including title and intro. Going over either limit makes the project ineligible for global judging. English, or English subtitles. Public link, no login.
- **Required fields.** Project name, high-level summary, link to demo, link to final project, detailed description, use of AI, NASA data, partner data and references. The form will not submit with one empty. The site's "About this project" section holds the same text (`web/src/project.js`), so copy from there.
- **AI use.** Code and data made with AI must be acknowledged in text (the README and the About section do); AI-generated images or video need a visible watermark.
- **Judging criteria.** Impact, Creativity, Validity, Relevance, Presentation.
- **Optional.** Request a FortiGuard web-filter classification for the site so judges are not blocked.

**30-second video**

| Seconds | On screen | Voice |
| --- | --- | --- |
| 0–5 | Logo, names | "We're Fire Before the Storm." |
| 5–12 | Tiétar valley, October 2026 | "After Ávila burned, the first rain poisoned the tap water." |
| 12–22 | Story site: NISAR before/after, ash layer, a town card | "NASA's NISAR radar sees the fuel, the burn and the regrowth. Ash Watch turns that into a warning for every town downstream." |
| 22–30 | Hindcast, then a world map | "It would have flagged Casavieja before the October rain. Any fire, anywhere." (first line only if the hindcast holds) |

**Checklist**

- [ ] Public GitHub repo with README and open-source license
- [ ] App online (GitHub Pages or similar)
- [ ] Video uploaded, public, English subtitles, 30 s or less
- [ ] Project page: all eight required fields, copied from `web/src/project.js`
- [ ] Demo and site links set in `web/src/project.js`
- [ ] Local Lead asked whether changes after 16:00 count
- [ ] Terms and conditions box ticked, Submit pressed

## Risks and fallbacks

| Risk | Fallback |
| --- | --- |
| NISAR downloads slow or HDF5 awkward | Start now; subset on the cluster; minimum is three dates (Jul 21, Jul 26, Oct 6) |
| Provisional calibration artefacts | Ratio-based change between dates; read the known-issues page |
| HV saturates in dense stands | Treat ash there as a lower bound and flag those pixels |
| Groundwater data coarse or licence unclear | Keep it a "test first" screening index; fall back to the global layers |
| Wind layer read as measured deposition | Label it indicative; show the wind rose and sectors, not a precise plume |
| US-calibrated debris-flow model | Relative ranking plus a parameter-sweep band |
| ESDAC soil form not approved in time | K factor from SoilGrids |
| Web files too big | 8-bit overlays, fewer zoom levels; large files on GitHub Releases |
| Front end blocked waiting for data | Mock files that follow the data contract from 17:00 |
| Scope creep | Core frozen Sunday 13:00 |
