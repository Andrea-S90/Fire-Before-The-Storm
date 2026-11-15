# Site concepts

Four ways to turn the plan into an interactive piece. They share one skeleton (`web/src/`): a map, the data
contract, and `chapters.js`. They differ in who drives: the author, the user, the rain, or time.

| | Concept | Who drives | Answers | Needs from the pipeline | Cost from today's skeleton |
| --- | --- | --- | --- | --- | --- |
| A | Scroll story | The author | "Why should I care?" | Nothing new | Built: polish copy, legends, intro image |
| B | Town console | The user | "What about my town?" | Nothing new | Small: search box, card as the main panel, link per town (`#piedralaves`) |
| C | Rain dial | The rain | "How much rain until it goes wrong?" | Nothing new: `streams.geojson` already has `trigger_mmh` | Small: one slider and a map filter |
| D | Radar time machine | Time | "What did NISAR actually see?" | New: one HV-change image per NISAR date, and an HH image pair | Medium: date slider, per-town recovery curve |

## A. Scroll story (the plan)

Eight chapters, a sticky map, text cards on the left. Best for the 30-second video and for a judge who gives
the page one minute. Weakness: the reader watches; the challenge asks for a tool people use.

## B. Town console

Map first. Type or click a town and get its card: four pathways with level and confidence, ash range, what to
test for, and the catchment drawn on the map. Each town has its own link, so a mayor can be sent theirs. This
is the "user-friendly tool" the brief asks for, and it is what a water utility would open twice.

## C. Rain dial

One slider from 0 to 40 mm/h. As it moves, stream segments whose trigger is below the value turn red and the
town list re-sorts by how many red segments sit upstream. It makes the central idea (a trigger, not a
forecast) physical, runs entirely in the browser, and is the most memorable ten seconds of a demo. Add marks
on the slider for the October storm's peak as IMERG saw it and for the 24 mm/h design storm.

## D. Radar time machine

A date slider over every NISAR pass from June to November: the HV-change image for that date on the map, and
below it the HV curve for the selected catchment falling at the fire and recovering after. A toggle switches
HV, HH and their ratio. This is the closest match to the challenge text (track surface change with NISAR,
compare polarizations) and the one that shows NISAR doing something no optical sensor did.

## Recommendation

Ship A as the frame, with C and B inside it, and D if Masha can export the frames.

1. Chapters 1 to 4 stay as a short guided story (the hook, the fire, the radar, the ash).
2. The "pathways" chapter becomes the rain dial (C).
3. The "towns" chapter becomes the town console (B) and is where the page ends up: the last scroll step
   releases the map so the reader can explore.
4. D replaces the single before/after overlay in "What radar sees" once the frames exist. Until then, show
   the `recovery` series already in `towns.json` as a curve on the town card.

Order of work: B and C first (no pipeline dependency), then D.

## What D needs added to the contract

- `layers.json`: one entry per NISAR date, for example `id: "dhv_2026-08-19"`, plus a `date` and `pass_id`
  field, or a separate `frames.json` with the same corner format.
- Two more static layers: `dhh` (HH change) and `hv_hh_ratio`, so the polarization comparison is visible.
- Keep each frame at 1024 px and 8-bit to stay inside the size budget.
