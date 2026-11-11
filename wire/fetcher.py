"""HTTP + RSS fetching, normalization and dedupe for Wire.

Provenance: adapted from ``02-Maintain/hangar/hangar/fetcher.py`` (itself ported from
clintrialist-report / GRUDGE). Changes: fetch errors now RAISE (hangar swallowed them
into an empty list, which the cache cannot tell from a quiet day), requests supplies the
timeout and User-Agent, and the Google News " - Publisher" suffix is split into a source
field. feedparser times are UTC struct_time, so they go through calendar.timegm (hangar's
mktime reads them as local time and is off by the UTC offset). ``dedupe_key``/``dedupe`` are kept as written.
"""

from __future__ import annotations

import re
from calendar import timegm
from datetime import UTC, datetime

import feedparser
import requests

# Plain and descriptive; no personal information.
USER_AGENT = "WireHeadlineReader/0.1 (static headline aggregator; links and titles only)"
TIMEOUT = 25

# Trailing " - Publisher" / " | Publisher" suffix, Google News style.
_PUBLISHER_SUFFIX = re.compile(r"\s+[-–—|]\s+[^-–—|]{1,40}$")


def http_get(url: str) -> requests.Response:
    """One GET with the plain User-Agent. Raises on a non-2xx status."""
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp


def _parse_date(entry: dict) -> datetime | None:
    for field in ("published_parsed", "updated_parsed"):
        parsed = entry.get(field)
        if parsed:
            try:
                return datetime.fromtimestamp(timegm(parsed), tz=UTC)
            except (ValueError, OverflowError, OSError):
                pass
    return None


def split_publisher(title: str) -> tuple[str, str | None]:
    """Split "Headline - Publisher" into (headline, publisher)."""
    m = _PUBLISHER_SUFFIX.search(title)
    if not m:
        return title, None
    pub = re.sub(r"^\s*[-–—|]\s+", "", m.group()).strip()
    return title[: m.start()].strip(), pub


def parse_feed(content: bytes | str, feed: str, split_pub: bool = False) -> list[dict]:
    """Normalize RSS/Atom bytes into headline dicts. Links and titles only.

    Article bodies (``description`` / ``content:encoded``) are deliberately dropped.
    Raises ValueError when the document yields no entries at all, so a 200 that is
    really an error page is a failure, not an empty section.
    """
    parsed = feedparser.parse(content)
    if parsed.bozo and not parsed.entries:
        raise ValueError(f"{feed}: unparseable feed ({parsed.bozo_exception})")
    out: list[dict] = []
    for entry in parsed.entries:
        title = (entry.get("title") or "").strip()
        link = (entry.get("link") or "").strip()
        if not title or not link:
            continue
        source = None
        if split_pub:
            title, source = split_publisher(title)
            source = (entry.get("source") or {}).get("title") or source
        published = _parse_date(entry)
        out.append(
            {
                "t": title,
                "u": link,
                "s": source,
                "f": feed,
                "p": published.isoformat(timespec="seconds") if published else None,
            }
        )
    if not out:
        raise ValueError(f"{feed}: feed parsed but held no headlines")
    return out


def fetch_feed(feed: str, url: str, split_pub: bool = False) -> list[dict]:
    """Fetch and parse one feed; raises on any failure. One request."""
    items = parse_feed(http_get(url).content, feed, split_pub)
    print(f"  [OK]   {feed}: {len(items)} items")
    return items


def dedupe_key(title: str) -> str:
    """Normalize a headline so near-duplicates collapse to one key."""
    key = title.lower().strip()
    key = _PUBLISHER_SUFFIX.sub("", key)
    key = re.sub(r"[^a-z0-9]+", " ", key).strip()
    return key


def dedupe(entries: list[dict], seen: set[str] | None = None, key: str = "t") -> list[dict]:
    """Drop duplicate titles, keeping the first occurrence.

    Pass a shared ``seen`` set across sections so one story cannot appear twice.
    """
    if seen is None:
        seen = set()
    unique: list[dict] = []
    for e in entries:
        k = dedupe_key(e[key])
        if k and k not in seen:
            seen.add(k)
            unique.append(e)
    return unique
