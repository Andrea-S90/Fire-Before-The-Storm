---
description: Sync with main and report what the other person changed, and whether the data is healthy
---

Bring me up to date with the repository. Do these in order and keep the report short.

1. `git fetch origin`, then list the commits on `origin/main` that are not in my branch
   (`git log --oneline HEAD..origin/main`), grouped by area: `pipeline/`, `web/src/`, `web/public/data/`,
   other. If my working tree is clean and my branch has no commits of its own, fast-forward to
   `origin/main`; otherwise tell me and do not merge or rebase without asking.
2. Run `python tools/check_data.py` and report errors and warnings. Say when the export was generated and
   whether it is older than the latest commit that touched `pipeline/steps/` or `pipeline/config/`
   (if so, the committed data is stale and needs a re-export).
3. If `docs/DATA_CONTRACT.md` or `tools/check_data.py` changed, say exactly which fields changed and which
   files in `web/src/` read them.
4. End with: what I should do next in my area, and anything I need to ask the other person.
