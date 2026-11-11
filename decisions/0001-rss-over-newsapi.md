# 0001 — Keyless RSS instead of NewsAPI for the category view

Date: 2026-11-11. Status: accepted (approved in the Phase 3 plan). Never edited; supersede with a new ADR.

## Decision

Replace NewsAPI with keyless RSS per category (Google News topic feeds). Keep the Drudge, Fox and CNBC sections.

## Context

The old app used NewsAPI's free tier for its category dropdown. That tier is licensed for development, not production, and serves articles about 24 hours late. A static GitHub Pages build would also need the key in Actions secrets.

## Options

| Option | Cost |
|---|---|
| Keep NewsAPI | Licence breach in production, 24h delay, secret to manage |
| Google News topic RSS | No key, no delay, one feed per category, publisher names in titles. `news.google.com/robots.txt` disallows `/rss` for generic agents |
| Publisher RSS (BBC, NPR) per category | Clean robots, but one publisher per category, narrower than the old multi-publisher list |

## Recommendation and consequence

Google News topic RSS, one request per category per refresh, plain User-Agent. The robots.txt disallow is a known caveat: these are Google's published syndication endpoints, not an HTML scrape, and hangar and GRUDGE already consume them. The category feed map is one block in `wire/feeds.py`; swapping to publisher feeds is a config change. Change course if Google begins refusing non-browser clients or Greg objects to the robots.txt position.
