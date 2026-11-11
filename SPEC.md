# Wire (NewsScraper rebuild) — SPEC

Status: build complete 2026-11-11; awaiting Greg's review. The old shinyapps app stays up until he has seen the replacement.

## Goal

Greg's words: "show headlines from Drudge and Fox and financial news and also give headlines by category. I get everything going on at those sites, minus the ads."
Mirror each source's full headline set (link plus headline text only) and give a by-category view, as one static page refreshed every 2 hours.

## What the old app is (reverse-engineered 2026-11-11 from https://grego1074.shinyapps.io/Stable-NewsScraper/)

R Shiny, no title (`<title>` empty), one page, four DataTables (`newsapi_table`, `drudge_table`, `fox_table`, `cnbc_table`), each in its own scroll region inside a page that also scrolls.

| Panel | Control | Columns | Rows observed |
|---|---|---|---|
| Explore NewsAPI Categories | `selectize` "Select NewsAPI Category:", values `business` (default), `entertainment`, `general`, `health`, `science`, `sports`, `technology` | Headline (link), Author, Source, Description, PublishedAt (ISO Z); sortable | up to the NewsAPI page, newest first; scroller shows ~9 rows at a time |
| Drudge Report | DataTables: "Show 10/25/50/100 entries" (default 25), Search box, pager | Headline (link), Source (link domain) | 202 entries |
| Fox News | same | Headline (link) | 231 entries |
| CNBC Financial News | same | Headline (link) | 30 entries |

Observed defects: no `<title>`; nested scroll regions on every panel (page scroll plus table scroll); four separate search boxes; paging at 25; Drudge's 202 entries include about 150 outlet-directory links (BOSTON GLOBE, REUTERS, ...) and Drudge's own utility links, not headlines; NewsAPI free tier is dev-only licence and about 24h delayed; literal "NA" in empty cells (per the Phase 3 review).

## Parity map

| Old | New |
|---|---|
| Category dropdown, 7 values | Category tabs, same 7 values and order; client-side switching over prefetched data |
| NewsAPI headlines | Google News topic RSS (keyless), see mapping below and `decisions/0001-rss-over-newsapi.md` |
| Author / Description columns | Dropped deliberately: intent is headlines only, no article bodies. Source (publisher) and relative age kept |
| Drudge panel (Headline, Source) | Drudge section: headline link, domain as source, region (Top left / Main splash / Column n), page order |
| Fox panel | Fox section from official RSS feeds |
| CNBC panel | CNBC section from official RSS feeds |
| 4 DataTables search boxes | One global filter over every list |
| Pager, entries-per-page | None: every headline is listed, single page scroll |

## Source to feed mapping

| Section | Source | Method | Notes |
|---|---|---|---|
| Drudge | https://drudgereport.com/ | HTML parse, page order | robots.txt read each run and honoured (currently `Allow: /`). Anchors only; images ignored. Outlet directory runs (6+ short ALL-CAPS single-`<BR>` links) and own-domain/utility links dropped. No timestamps exist, so no age is shown |
| Fox | `moxie.foxnews.com/google-publisher/{latest,politics,us,world,opinion,media,sports,science,tech,health,lifestyle,entertainment,travel}.xml` | official RSS, 13 feeds, 25 items each | deduped across feeds; each feed returns exactly 25, so the set is the union of 13 windows, not an archive. Bodies (`description`, `content:encoded`) discarded |
| CNBC | `cnbc.com/id/{id}/device/rss/rss.html`, 17 channels (Top News, Business, Investing, Finance, Economy, Earnings, Tech, Politics, Health & Science, Energy, Real Estate, Wealth, Media, Retail, Autos, International, U.S.) | official RSS, 30 items each | |
| Categories | `news.google.com/rss/headlines/section/topic/{BUSINESS,ENTERTAINMENT,HEALTH,SCIENCE,SPORTS,TECHNOLOGY}` and `news.google.com/rss` (front page) for `general` | RSS | Google News titles end " - Publisher"; split into headline plus source |

Caveat to review: news.google.com/robots.txt disallows `/rss` for generic agents. These are Google's published syndication endpoints, not an HTML scrape, and hangar and GRUDGE already use them, but it is flagged in the ADR for Greg's call. The category feeds are one config block in `wire/feeds.py` if he prefers publisher feeds.

Every request: plain User-Agent `WireHeadlineReader/0.1 (static headline aggregator; links and titles only)`, no personal info, one request per feed per refresh (Drudge additionally reads robots.txt once).

## Done criteria

1. Parity: three source sections plus a 7-category view exist and list links to the same kinds of content as the old app.
2. Mirror, not sample: Drudge shows its full headline set in page order; Fox and CNBC show the union of their section feeds, deduped; no cap on rows.
3. No ads, no tracking: no images, no bodies, no third-party scripts except the Telemetrics chrome and Google Fonts; links open `noopener noreferrer`.
4. Fixes: real `<title>Wire — Telemetrics`; single page scroll (no nested scroll regions); relative ages ("12m ago"); never prints "NA" (absent age or source is simply omitted); one global filter; HANGAR tokens and light/dark; 390px phone with no horizontal scroll; Telemetrics chrome snippet with `data-section="newsscraper"`, `data-built`, `data-next="every 2h"`.
5. Status bus: each source shows fresh / stale / failed with fetch timestamp; a failed source keeps its previous payload and says so; a feed that fails inside a multi-feed source is named as "Partial" rather than silently shrinking the list.
6. Ops: `python run.py` (refresh stale and render), `--force`, `--render` (offline); GH Actions cron every 2 hours commits `docs/` and `data/`. No secrets.
7. Tests pass against saved real responses; ruff clean.

## Out of scope

Article bodies, images, search beyond the filter box, accounts, push, sentiment or drama scoring (that is GRUDGE), retiring the shinyapps app (Greg's call), publishing to GitHub (not done in this build).

## What would make this wrong

- Drudge changes its markup: the parser returns far fewer or zero links. Zero raises and the source goes failed; a count collapse is visible in `run.py` output and the page count.
- A Fox or CNBC feed id is retired: that feed is named in the Partial note.
- Google News stops serving `/rss` to non-browser clients.

## Open questions

- Google News robots.txt (above): accept, or swap to publisher RSS (BBC/NPR) for the category view?
- Fox's `/latest` window is 25 items, so older-than-a-day stories drop out. Acceptable for "everything currently on the site"?
