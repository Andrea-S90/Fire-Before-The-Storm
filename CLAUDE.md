# Fire Before the Storm: Ash Watch

NASA Space Apps 2026, challenge "Dancing with the SARs". Ash Watch turns NISAR radar plus open data into a
post-fire drinking-water warning per town, shown on a scrolling story site. Demo case: the Burgohondo fire,
Ávila, Spain, July 2026. Plan: `Fire Before the Storm — Ash Watch build plan.md`.

Two people, both working with Claude Code:

| Area | Owner | Runs on |
| --- | --- | --- |
| `pipeline/` (HPC jobs, config, Slurm) | Masha | BlueBEAR cluster, Linux |
| `web/src/`, `web/index.html` (story site) | Andrea | laptop, deployed by GitHub Actions |
| `web/public/data/` (the data contract) | written only by pipeline step 12 | committed by Masha |
| `tools/`, `docs/`, `.github/`, this file | shared | |

## Rules that keep us aligned

1. **The data contract is the only interface.** The site reads `web/public/data/` and nothing else; the
   pipeline writes it and nothing else in `web/`. The fields are in `docs/DATA_CONTRACT.md`.
2. **Never edit files in `web/public/data/` by hand**, and never "fix" a number in the site. If the data is
   wrong, fix the pipeline step and re-export. Mock or placeholder data goes in `web/src/`, clearly named.
3. **Run `python tools/check_data.py` after every export and before every commit that touches data.** Errors
   block the deploy. Read the warnings: they flag numbers that would not survive a judge's question.
4. **A contract change is one pull request** that updates `docs/DATA_CONTRACT.md`, `tools/check_data.py` and
   the site code together. Adding fields is free; renaming or removing is a contract change.
5. **Stay in your area.** If a task needs a change in the other person's area, say so and keep that change in
   its own commit, so it is easy to review or revert.
6. **Small commits, pull before you start, rebase before you push.** Work on a branch and open a pull request;
   CI must be green before merging. Direct pushes to `main` are for data re-exports only.
7. **Every unmeasured number is an ASSUMPTION** and lives in `pipeline/config/avila.yaml`, marked as such.
   Never hard-code a threshold in a step or in the site.
8. **Do not overclaim.** Groundwater is "screening", airborne ash is "indicative", the debris-flow model is
   US-calibrated, and one fire is a case study. Site copy and the pitch must match what `meta.json` and
   `hindcast.json` actually say.

## Commands

```bash
# data contract (standard library only, runs anywhere)
python tools/check_data.py

# site
cd web && npm install && npm run dev      # http://localhost:5173
cd web && npm run build                   # what CI and the deploy run

# pipeline (needs the ashwatch environment; see pipeline/README.md and pipeline/BLUEBEAR.md)
cd pipeline && bash tests/run_synthetic.sh /tmp/aw_test        # whole chain on fake data, 2 to 5 min
cd pipeline && sbatch --export=ALL,STEPS="10 11 12" slurm/bluebear_process.sbatch
```

## How an update reaches the live site

Masha re-runs steps on the cluster, step 12 writes `web/public/data/`, she runs the checker and pushes. CI
checks the contract and builds the site; the deploy workflow publishes it to GitHub Pages. The site footer
shows the export time from `meta.json`. Andrea does nothing unless the contract changed.

## Site

Vite + React + MapLibre GL, static files only. `web/src/chapters.js` is the story as data: text, camera,
which overlays and vectors are on, which panel shows. Change the story there. `web/src/project.js` holds the
project facts shown in the About section, under the same headings as the Space Apps project page. `web/src/data.js` is the only
place that fetches. Components are in `web/src/components/`.

## Pipeline

Steps `pipeline/steps/01..13_*.py` run in order and share `pipeline/ashwatch/`. Raw and intermediate data
live under `$ASHWATCH_DATA` on the cluster and are never committed. Scripts must keep Unix line endings
(`.gitattributes` enforces it). Code style: `ruff`; the pipeline uses long lines (up to about 130 columns), so do not reflow it to 88.

## For Claude

- Start a session with `/catchup`: it pulls `main`, runs the checker and says what changed.
- Deadlines, Sunday 15 November 2026: Barcelona local event wants the submission by 16:00 and a live
  presentation at 16:30. The global form accepts edits and resubmissions until 23:59 local time, and only the
  last saved submission is judged globally.
- The project page has a field on AI use: code and data written with AI must say so in text (the README
  does); AI-generated images or video need a visible watermark.
- No secrets in the repo: Earthdata and CDS credentials stay in `~/.netrc`, `~/.cdsapirc` or environment
  variables; BlueBEAR site settings stay in `pipeline/slurm/bluebear.local.sh` (ignored).
- Ask before deleting files, rewriting git history or force-pushing.
- Write plain English in docs and site copy; cite a source for every factual claim about the fire.
