# Presentation and demo video plan

Sunday 15 November 2026. Two different deliverables, built from the same story:

| | What | Limit | When |
| --- | --- | --- | --- |
| A | Demo video for the project page (global judging) | 30 s or less, English, public link, no login | in the 16:00 submission |
| B | Live pitch at the Barcelona local event | set by the Local Lead (unknown: see questions) | 16:30 |

Judging criteria: Impact, Creativity, Validity, Relevance, Presentation. The challenge name must be said or
shown in the first five seconds of the video. Going over 30 s makes the project ineligible for global judging.

## What the 12:25 export lets us say (and not say)

- Data ends on 25 September, before the October rain. From it, Piedralaves (runoff high, debris flow high,
  29.6% of its upstream area burned) and Casavieja (debris flow high) both come out **high** overall.
- El Barraco comes out **low** (only airborne ash medium). Do not feature it, even though the news quoted its mayor.
- Satellite rain (IMERG) never passes any town's debris-flow trigger. Never say we "predicted the storm" or
  that "a trigger was exceeded". IMERG is a lower bound on 15-minute peaks.
- The site has no world map: the "any fire, anywhere" line must be about global open inputs, not a global
  result. Say "built on global open data", not "works anywhere".
- Numbers a judge may ask about (`meta.json`): radar and optical burn maps agree on 85% of pixels (kappa 0.33);
  the radar-only severity classes have 61% hold-out accuracy (kappa 0.41); the HV-to-biomass fit has R² 0.35.
  These are honest but modest: present them as "checked against Sentinel-2", and have the figures ready for Q&A.

## A. The 30-second demo video

Silent screen recording of the live site, 1920×1080, 30 fps, H.264 MP4, **29.5 s** (half a second of margin).
You add the title card, the voice and the subtitles in post, using the timecodes below. The speech is 72 words,
about 145 words a minute: calm, not rushed.

| Time (s) | Site on screen (recorded) | Overlay added in post | Voice |
| --- | --- | --- | --- |
| 0.0–4.0 | Chapter 1, towns on the map | Lockup, "Andrea Serio · Masha Golikova", "NASA Space Apps 2026 · Dancing with the SARs" | "Team Fire Before the Storm, for Dancing with the SARs." |
| 4.0–9.0 | Chapter 1 headline cards (El Debate 28 Jul, Reuters 7 Oct) | none | "In October, rain washed ash from the Burgohondo fire into Ávila's rivers. Tap water became undrinkable." |
| 9.0–14.0 | Chapter 2: burn severity + "How Sentinel-2 grades the burn" card (NBR formula) | none | "Sentinel-2 maps how hard it burned…" |
| 14.0–19.0 | Chapter 3: radar change + "How NISAR sees a forest" card | none | "…and NISAR's radar sees through the smoke where the forest is gone." |
| 19.0–23.0 | Chapter 6: rain dial swept 0 → 40 mm/h, streams turn red | none | "Ash Watch finds how much rain each stream can take." |
| 23.0–27.5 | Chapter 7: Piedralaves card shows HIGH, then Casavieja | "Data up to 25 Sep, before the rain" | "From data before the rain, it rated Piedralaves and Casavieja high." |
| 27.5–29.5 | Zoom out to the whole region | Tagline + site URL | "The fire is out. The danger isn't." |

The headline cards and the two satellite explainers are part of the site (chapters 1 to 3), so the recording
captures them with no compositing in post. The explainer drawings are schematic and carry a visible
"made with AI assistance" line, which covers the project page rule on AI-generated images.

Also delivered: a matching subtitle file (`.srt`) with the same cues, since the guide asks for English or
English subtitles, and many judges watch muted.

### How I would record it

- A script (`tools/record_demo.mjs`, Playwright) opens the site at 1920×1080, waits for the basemap and
  layers to load, then drives the story with exact waits: Next button, the rain slider, clicks on town dots.
  It is repeatable: if the data or copy changes, one command re-records the same cut.
- ffmpeg converts the recording to MP4 and trims it to 29.5 s.
- Output in `media/demo/` (not committed unless you want it): `ashwatch_demo_raw.mp4`, `ashwatch_demo.srt`,
  and a contact sheet of one frame per cue so you can check the cut without opening an editor.
- Needs two downloads, which I will not start without your yes: Playwright's Chromium (about 150 MB) and
  ffmpeg via winget (about 100 MB).

### Post-production checklist (yours)

- [ ] Record the voice: one take per cue, or one take read against the timecodes.
- [ ] Add the title card, lower thirds and tagline; check the total is still 30 s or less.
- [ ] Burn in or attach the subtitles.
- [ ] If any voice or image is AI-generated, add a visible watermark (project page rule). Our own voice over
      our own screen recording needs none.
- [ ] Upload with a public link (YouTube unlisted works, no login) and put it in `web/src/project.js` → `links.demo`.

## B. The live pitch (16:30)

Built around the five criteria; timings for a 3-minute slot, with what to cut if it is shorter.

| # | Block | Time | Criterion | Content |
| --- | --- | --- | --- | --- |
| 1 | Hook | 0:00–0:20 | Impact | "The fire is out. The danger isn't." October 2026: tap water in Casavieja and Piedralaves declared unfit (Reuters). Headline only, linked, no news photos. |
| 2 | Problem and gap | 0:20–0:45 | Impact, Relevance | Pollutants up to 103× pre-fire levels, high for up to 8 years (500 US watersheds). The US has USGS post-fire assessments; the EU has a patchwork. Users: town halls, water utilities, basin authorities. |
| 3 | Why NISAR | 0:45–1:10 | Relevance | L-band, through smoke and cloud, every 12 days. HV tracks branches and trunks (fuel, burn, regrowth); HH tracks bare, wet ground. Using both separates "burned" from "just wet". |
| 4 | Live demo | 1:10–2:10 | Creativity, Presentation | On the site: fire → radar → ash → rain dial → Piedralaves card. Fallback: play video A. |
| 5 | Is it right? | 2:10–2:40 | Validity | Data ending 25 Sep rates the two affected towns high. Radar burn map checked against Sentinel-2. Then the honest part: one fire is a case study; debris-flow model is US-calibrated, so a ranking; groundwater and airborne ash are screening; satellite rain never passed a trigger, because 10 km pixels flatten short storms. |
| 6 | Next and close | 2:40–3:00 | Impact | Every input is a global open dataset: next fire = new bounding box and a re-run (Gironde next). Tagline, QR code to the site. |

If the slot is 2 minutes: drop block 2 to one sentence and cut the demo to the rain dial and one town card.
If it is 5 minutes: add the four pathways (chapter 5, wind rose) and the hindcast chart (chapter 8).

Slides: at most 7 if we also want them as the submission's slide alternative (title and intro count). Suggested
seven: Title · Hook · Gap · Why NISAR · Demo (live) · Validity · Next. The demo is the site itself, not a slide.

Reliability: keep a local build ready on the laptop in case the venue Wi-Fi fails, plus the video file offline.

```bash
cd web && npm run build && npx vite preview      # serves the built site locally
```

Q&A sheet (one page, in the presenter's pocket): the `meta.json` figures above, the data sources from the
About section, and the line "we label groundwater screening and airborne ash indicative because we have no
local measurements".

## Questions for the team

1. **Live pitch format.** How long is the 16:30 slot, is there Q&A, can we use our own laptop and the
   internet, and are slides expected?
2. **Submission demo.** Video (this plan) or the 7-slide alternative? Confirm video.
3. **Voice.** Who speaks in the video: one of you or both (e.g. Andrea cues 1–3, Masha 4–6)? Human voice is
   the recommendation; an AI voice would need disclosure.
4. **Editor.** Which tool do you edit in (CapCut, DaVinci Resolve, Clipchamp, iMovie)? I will deliver MP4
   H.264 1920×1080 30 fps unless you need something else (for example 1080×1920 vertical).
5. **Downloads.** OK to install Playwright's Chromium and ffmpeg for the recording?
6. **Source.** Record the live GitHub Pages site (what judges will see) or a local build (steadier)? Is the
   12:25 export final, or will data or copy change before 15:30 (that means re-recording)?
7. **Featured towns.** Piedralaves and Casavieja, as above? Any objection to leaving out El Barraco?
8. **Local Lead.** Has anyone confirmed whether edits after 16:00 count locally?
9. **Clock.** Plan says submit a complete version by 15:30. What time is the voice-over recording slot, so the
   video is ready before then?
