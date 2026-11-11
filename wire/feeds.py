"""Feed registry and multi-feed assembly for Wire.

Provenance: the registry-of-named-feeds shape and shared-``seen`` dedupe come from
``02-Maintain/hangar/hangar/feeds.py``. Wire's registry is its own: official publisher
RSS for Fox and CNBC, Google News topic RSS for the category view (replaces NewsAPI,
see decisions/0001-rss-over-newsapi.md).

``assemble`` is the failure-mode core. One feed failing must not silently shrink a
section that looks complete: the failed feed's items are carried over from the previous
payload (flagged in ``failed_feeds``) and only a total failure raises, which makes the
cache keep the whole previous payload and mark the source failed.
"""

from __future__ import annotations

from collections.abc import Callable

from .fetcher import dedupe, fetch_feed

GN = "https://news.google.com/rss"
_GN_Q = "hl=en-US&gl=US&ceid=US:en"

FOX_FEEDS = {
    name: f"https://moxie.foxnews.com/google-publisher/{slug}.xml"
    for name, slug in [
        ("Latest", "latest"),
        ("Politics", "politics"),
        ("U.S.", "us"),
        ("World", "world"),
        ("Opinion", "opinion"),
        ("Media", "media"),
        ("Sports", "sports"),
        ("Science", "science"),
        ("Tech", "tech"),
        ("Health", "health"),
        ("Lifestyle", "lifestyle"),
        ("Entertainment", "entertainment"),
        ("Travel", "travel"),
    ]
}

CNBC_FEEDS = {
    name: f"https://www.cnbc.com/id/{fid}/device/rss/rss.html"
    for name, fid in [
        ("Top News", 100003114),
        ("Business", 10001147),
        ("Investing", 15839069),
        ("Finance", 10000664),
        ("Economy", 20910258),
        ("Earnings", 15839135),
        ("Tech", 19854910),
        ("Politics", 10000113),
        ("Health & Science", 10000108),
        ("Energy", 19836768),
        ("Real Estate", 10000115),
        ("Wealth", 10001054),
        ("Media", 10000110),
        ("Retail", 10000116),
        ("Autos", 10000101),
        ("International", 100727362),
        ("U.S.", 15837362),
    ]
}

# The old dropdown's seven categories, in its order. Google News has no "general" topic
# section; the front-page headlines feed is the closest analogue.
CATEGORY_LABELS = {
    "business": "Business",
    "entertainment": "Entertainment",
    "general": "General",
    "health": "Health",
    "science": "Science",
    "sports": "Sports",
    "technology": "Technology",
}
CATEGORY_FEEDS = {
    "business": f"{GN}/headlines/section/topic/BUSINESS?{_GN_Q}",
    "entertainment": f"{GN}/headlines/section/topic/ENTERTAINMENT?{_GN_Q}",
    "general": f"{GN}?{_GN_Q}",
    "health": f"{GN}/headlines/section/topic/HEALTH?{_GN_Q}",
    "science": f"{GN}/headlines/section/topic/SCIENCE?{_GN_Q}",
    "sports": f"{GN}/headlines/section/topic/SPORTS?{_GN_Q}",
    "technology": f"{GN}/headlines/section/topic/TECHNOLOGY?{_GN_Q}",
}


def assemble(
    feeds: dict[str, str],
    previous: list[dict] | None = None,
    fetcher: Callable[..., list[dict]] = fetch_feed,
    split_pub: bool = False,
    sort_newest: bool = True,
    per_feed_dedupe: bool = False,
) -> dict:
    """Fetch every feed once, dedupe across feeds, and report which feeds failed.

    Returns ``{"items": [...], "failed_feeds": {name: error}}``. A failed feed keeps its
    previous items (marked by the unchanged ``f`` tag). Raises RuntimeError if every
    feed failed, so the cache falls back to the full previous payload.
    """
    previous = previous or []
    items: list[dict] = []
    failed: dict[str, str] = {}
    for name, url in feeds.items():
        try:
            items.extend(fetcher(name, url, split_pub))
        except Exception as e:  # noqa: BLE001 - one bad feed must not stop the others
            print(f"  [FAIL] {name}: {e}")
            failed[name] = f"{type(e).__name__}: {e}"
            items.extend(i for i in previous if i.get("f") == name)
    if len(failed) == len(feeds):
        raise RuntimeError(f"all {len(feeds)} feeds failed: {next(iter(failed.values()))}")
    if sort_newest:
        items.sort(key=lambda i: i.get("p") or "", reverse=True)
    if per_feed_dedupe:  # category view: a story may sit in two categories
        unique: list[dict] = []
        for name in feeds:
            unique.extend(dedupe([i for i in items if i.get("f") == name]))
        return {"items": unique, "failed_feeds": failed}
    return {"items": dedupe(items), "failed_feeds": failed}
