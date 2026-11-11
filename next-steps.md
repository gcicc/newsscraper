---
name: newsscraper
type: maintain
category: building
tier: 02-Maintain
updated: 2026-11-11
---
# Wire (NewsScraper rebuild) — next steps

## Where this stands

Rebuilt 2026-11-11 as a static site on the hangar pattern. `python run.py --force` fetches Drudge (HTML, 49 headlines), Fox (13 official feeds, 311), CNBC (17 official feeds, 371) and 7 Google News category feeds (419), and renders `docs/index.html`. 22 tests pass, ruff clean. Local git only; nothing pushed, no remote. The old shinyapps app is untouched and still live.

## Next task

Greg reviews the page and `SPEC.md` open questions (Google News robots.txt position; Fox 25-item windows). On approval: create the GitHub repo, push, enable Pages from `/docs`, flip the `newsscraper` url in `03-Tools/suite-nav/suite.json` from the shinyapps address, then retire the Shiny app (his call).

## Blockers

- Not yet published, so `gcicc.github.io/suite/network.js` is a 404 and the RANGER masthead does not render until the suite is deployed.
- `data-built` and the chrome only verify once the page is served next to suite `dist/`.

## What keeps this current

- `.github/workflows/refresh.yml` runs every 2 hours and commits `docs/` and `data/` (once the repo exists).
- The status bus on the page shows fresh / stale / failed per source; a Drudge markup change shows as a count collapse or a failed source.
- Liveness of the published url is covered by `03-Tools/project-management` once `suite.json` points at it.
