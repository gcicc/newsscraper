# Wire

Every headline from Drudge, Fox News and CNBC, plus headlines by category, minus the ads. A Telemetrics network section (`newsscraper`). Replaces the Shiny app at grego1074.shinyapps.io/Stable-NewsScraper, which stays up until Greg retires it.

One self-contained static page, `docs/index.html`, rebuilt every 2 hours. Links and headline text only.

## Run

```
python run.py            # refresh sources whose cache expired, then render
python run.py --force    # refresh everything
python run.py --render   # render from data/ only, no network
python -m pytest         # tests run against saved responses in tests/fixtures/
python -m ruff format . && python -m ruff check .
```

Dependencies are the same as hangar's (feedparser, requests, jinja2; see `requirements-lock.txt`).

## Layout

| Path | Role |
|---|---|
| `wire/drudge.py` | Drudge HTML parser; reads robots.txt first |
| `wire/feeds.py` | Fox, CNBC and category feed registry; `assemble` handles partial failure |
| `wire/fetcher.py`, `wire/cache.py`, `wire/render.py` | Adapted from hangar (provenance in each docstring) |
| `wire/templates/` | `page.html.j2`, `styles.css`, `app.js` |
| `data/*.json` | Per-source cache and `status.json` ledger (committed) |
| `.github/workflows/refresh.yml` | Cron every 2h; commits `docs/` and `data/` |
| `SPEC.md`, `decisions/` | What the old app did, done criteria, ADRs |

## Failure behaviour

Per source, three distinct outcomes: fetch failed (previous payload kept, status `failed`, error shown), upstream unchanged (not an error), still fresh (no request). A single feed failing inside Fox, CNBC or Categories is named as "Partial" on the page and its previous items are kept. The status bus in the header shows fresh / stale / failed for each source.

## Known limits

- Drudge has no timestamps, so its rows show no age.
- Each Fox feed returns 25 items, so Fox is the union of 13 current windows, not an archive.
- The Telemetrics chrome script (`gcicc.github.io/suite/network.js`) returned 404 on 2026-11-11 because the suite is not yet published; the page works without it.
