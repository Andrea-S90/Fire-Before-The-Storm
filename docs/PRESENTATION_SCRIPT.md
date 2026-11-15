# Presentation script

Two scripts: the 30-second video for the project page, and the live pitch at the Barcelona event (16:30).
Every number below comes from the 12:25 export (`meta.json`, `towns.json`, `hindcast.json`) or a source cited
in the site's About section. Do not add claims in the edit that are not here.

## 1. Demo video voice-over (29.5 s)

Recording: `media/demo/ashwatch_demo_raw.mp4` (1920×1080, 30 fps, silent, 29.5 s). Subtitles with the same
cues: `media/demo/ashwatch_demo.srt`. About 75 words: read calmly, about 150 words a minute.

| Time | On screen (recording) | Add in post | Voice |
| --- | --- | --- | --- |
| 0.0–4.0 | Map of the towns, opening card | Title card: **Ash Watch** · Fire Before the Storm · NASA Space Apps 2026 · *Dancing with the SARs* · Andrea Serio, Masha Golikova | "We are Fire Before the Storm, for NASA's Dancing with the SARs challenge." |
| 4.0–9.0 | Headline cards: El Debate (28 Jul), Reuters (7 Oct) | none (the headlines are on screen) | "After the Ávila fire, the first rain made tap water unfit to drink." |
| 9.0–14.0 | Burn severity map, "How Sentinel-2 grades the burn" card | Lower third: "ESA Sentinel-2 · burn ratio" | "Sentinel-2's infrared bands show how hard each slope burned." |
| 14.0–19.0 | Radar change map, "How NISAR sees a forest" card | Lower third: "NASA-ISRO NISAR · L-band radar" | "NISAR's radar sees through the smoke, where the forest is gone." |
| 19.0–23.0 | Rain dial moving up to 40 mm/h | Lower third: "Debris-flow trigger per stream" | "Ash Watch works out how much rain each stream can take." |
| 23.0–27.2 | Town cards: Navaluenga, then Casavieja, both HIGH | Lower third: "Data up to 25 Sep 2026, before the rain" | "Using only data from before the storm, it rated Casavieja high." |
| 27.2–29.5 | Zoom out, data sources | Tagline + site address: andrea-s90.github.io/Fire-Before-The-Storm | "The fire is out. The danger isn't." |

Notes for the edit:

- Keep the total at 30 s or less after adding the title card. Do not lengthen any scene.
- In this take the map is slow to redraw in the rain scene: the dial moves but the red channels appear only
  at the end. The voice line does not depend on them. If you want them visible, hold the last frame of that
  scene, or cut in a screenshot of chapter 6 at 40 mm/h from the live site.
- The town shown first is Navaluenga (the site's default town), not Piedralaves; the voice names only
  Casavieja, which the recording shows.
- Why these claims hold: Casavieja's overall level is high (debris flow high) from data that ends on 25
  September; the October rain came after. Do not say the tool "predicted the storm": satellite rain never
  passed any town's trigger (see `hindcast.json`).
- The explainer drawings already carry "made with AI assistance" on screen. Our own voice needs no watermark.

Full voice text, for one continuous take:

> We are Fire Before the Storm, for NASA's Dancing with the SARs challenge.
> After the Ávila fire, the first rain made tap water unfit to drink.
> Sentinel-2's infrared bands show how hard each slope burned.
> NISAR's radar sees through the smoke, where the forest is gone.
> Ash Watch works out how much rain each stream can take.
> Using only data from before the storm, it rated Casavieja high.
> The fire is out. The danger isn't.

## 2. Live pitch (3 minutes)

Two speakers: **A** (Andrea, story and site) and **M** (Masha, radar and model). Swap if you prefer. Each
block shows its time and the judging criterion it serves. Words in *[brackets]* are stage directions.

### 0:00–0:20 · Hook (Impact) · A

*[Site open on chapter 1, headline cards visible.]*

> In July, the Burgohondo fire burned the hills of Ávila. While it burned, Casavieja had no power and no
> drinking water. Two months later the fire was long out, and the first autumn rain washed its ash into the
> rivers. In Piedralaves, tap water was declared unfit to drink. The fire is out. The danger isn't.

### 0:20–0:45 · The problem (Impact, Relevance) · A

> This is not a one-off. A study of 500 watersheds in the western US found pollutants after fires up to 103
> times pre-fire levels, with nitrogen and sediment high for up to eight years. The US runs post-fire hazard
> assessments; in Europe it is a patchwork of regional tools. The people who need an answer are town halls,
> water utilities and basin authorities, and their question is simple: is our water at risk, from where,
> and how much rain would it take?

### 0:45–1:10 · Why NISAR (Relevance) · M

*[Next: chapter 2, then chapter 3 with the NISAR card.]*

> Sentinel-2 grades the burn from two infrared bands, but only when there is no smoke or cloud. NISAR, the new
> NASA-ISRO radar, works through both, every 12 days. It sends horizontally polarized microwaves. In a forest,
> branches and trunks bounce them around and send part of the echo back vertical: a strong HV signal. When the
> canopy burns, HV drops. Bare, wet ground answers in HH instead. Using both, we can tell "burned" from "just
> wet". We count a pixel as burned only where radar and optical agree.

### 1:10–2:10 · Demo (Creativity, Presentation) · A

*[Chapter 4, ash load.]*

> Fuel before the fire, times how much burned, times how much becomes ash: that gives the ash on every slope.

*[Chapter 5, pathways and wind rose.]*

> Ash reaches a tap four ways: runoff into streams, debris flows from steep slopes, seepage into wells, and the
> wind.

*[Chapter 6, move the rain dial slowly from 10 to 40.]*

> For every small stream, a published US debris-flow model gives the rain that would set it off. Move the
> dial: these channels turn red as the rain gets stronger.

*[Chapter 7, choose Piedralaves, then Casavieja.]*

> And every town gets one card. Piedralaves: almost 30 percent of the land above it burned, runoff high,
> debris flow high. Casavieja: debris flow high. Both from data that ends on 25 September, before the rain.
> Each card also lists the first lab tests to run: turbidity, manganese, lead, nitrogen.

### 2:10–2:40 · Is it right? (Validity) · M

*[Chapter 8, hindcast chart.]*

> We are careful about what this shows. The two towns that lost their water were rated high before the rain.
> Our radar burn map agrees with Sentinel-2 on 85 percent of pixels. But one fire is a case study, not proof.
> The debris-flow model was calibrated in the US, so we read it as a ranking. Satellite rain never passed a
> trigger, because its 10-kilometre pixels smooth out short storms. And groundwater and airborne ash have no
> local measurements, so the site labels them screening and indicative.

### 2:40–3:00 · Next and close (Impact) · A

*[Chapter 9, zoom out.]*

> Every input is a free global dataset, so the next fire needs a new box on the map and a re-run, not a new
> tool. Next we want a second fire, in Gironde, to show it travels. Ash Watch: the fire is out, the danger
> isn't. Thank you.

### If the slot is shorter or longer

- **2 minutes:** cut "The problem" to its first and last sentences, and in the demo keep only the rain dial
  and Piedralaves.
- **5 minutes:** add the ash range (P10 to P90 on the town card) and the full hindcast chart for one town.
- **If the site or Wi-Fi fails:** play the 30-second video, then continue from "Is it right?".

### Likely questions

| Question | Answer |
| --- | --- |
| How good is the radar burn map? | It agrees with Sentinel-2 on 85% of pixels (kappa 0.33). Radar-only severity classes, used under cloud, reach 61% accuracy (kappa 0.41). |
| Did you predict the October storm? | No. We rate the risk and the rain that would trigger it. Satellite rain stayed below every trigger, which says more about its 10 km pixels than about the risk. |
| Why should Europe trust a US model? | We use it as a ranking, not a forecast, and the site says so. Calibrating it on European fires is the obvious next step. |
| What about El Barraco, named in the news? | Our data rates it low: almost none of its catchment burned. We show it as it is. |
| How does it scale? | All inputs are global open data. A new fire is a new bounding box and a re-run of the pipeline. |
| How was AI used? | The code and docs were written with Claude Code, directed and reviewed by us; the diagrams say so on screen. The ideas, methods and interpretation are ours. |
