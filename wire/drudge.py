"""Drudge Report front-page parser: headline links in page order, nothing else.

Drudge's HTML is hand-edited 1990s markup: ``<A HREF>`` stacks separated by ``<BR>`` and
``<HR>``, with comment-like markers (``<! MAIN HEADLINE >``) between regions. Images are
the ad/splash art and are ignored outright; only anchors are read, and only their text
and href are kept.

Three kinds of anchor are NOT headlines and are dropped:

* Drudge's own utility links (own domain, relative paths, mailto, app stores, the
  Google Trends widget).
* The outlet directory: runs of six or more consecutive short ALL-CAPS anchors with only
  single ``<BR>`` between them ("BOSTON GLOBE", "BOSTON HERALD", ...). This is a link
  list, not news. Real headlines are separated by ``<HR>`` / double ``<BR>``.
* Anchors with no text.

The old shinyapps build listed all 202 anchors including these; that was the bug.
"""

from __future__ import annotations

import html
import re
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

from .fetcher import USER_AGENT, http_get

URL = "https://drudgereport.com/"
ROBOTS_URL = "https://drudgereport.com/robots.txt"

_ANCHOR = re.compile(r"""(?is)<a\s+[^>]*?href\s*=\s*["']([^"']+)["'][^>]*>(.*?)</a>""")
_MARKER = re.compile(r"(?is)<!\s+([A-Z][^>]*?)\s*>")
_SEP = re.compile(r"(?i)<hr|<br>\s*<br>")
_SKIP_HOSTS = ("drudgereport.com", "drudgereportarchives.com", "apps.apple.com", "play.google.com")
_SKIP_PREFIX = ("https://trends.google.com/",)
_DIRECTORY_RUN = 6

REGION_LABELS = {
    "top": "Top left",
    "main": "Main splash",
    "main-end": "Main splash",
    "col1": "Column 1",
    "col2": "Column 2",
    "col3": "Column 3",
}


def robots_allows(url: str, robots_text: str, agent: str = USER_AGENT) -> bool:
    rp = RobotFileParser()
    rp.parse(robots_text.splitlines())
    return rp.can_fetch(agent, url)


def _region(marker_text: str, current: str) -> str:
    m = marker_text.upper()
    if "TOP LEFT STARTS" in m:
        return "top"
    if "MAIN HEADLINE END" in m:
        return "main-end"
    if "MAIN HEADLINE" in m:
        return "main"
    if "FIRST" in m and "COLUMN" in m:
        return "col1"
    if "SECOND" in m:
        return "col2"
    if "3 R D" in m:
        return "col3"
    return current


def _is_directory_text(text: str) -> bool:
    return len(text) <= 30 and text == text.upper() and any(c.isalpha() for c in text)


def parse(page: str) -> list[dict]:
    """Return headline dicts ``{t,u,s,f,p}`` in page order. ``s`` is the link's domain."""
    events: list[tuple[int, str, tuple]] = []
    for m in _MARKER.finditer(page):
        events.append((m.start(), "marker", (m.group(1),)))
    for m in _ANCHOR.finditer(page):
        events.append((m.start(), "a", (m.group(1), m.group(2), m.end())))
    events.sort(key=lambda e: e[0])

    region = "top"
    rows: list[dict] = []
    prev_end = 0
    for pos, kind, payload in events:
        if kind == "marker":
            region = _region(payload[0], region)
            continue
        href, inner, end = payload
        text = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", inner))).strip()
        gap = page[prev_end:pos]
        prev_end = end
        href = html.unescape(href).strip()
        parsed = urlparse(href)
        host = (parsed.hostname or "").lower()
        if parsed.scheme not in ("http", "https") or not text:
            continue
        if any(host == h or host.endswith("." + h) for h in _SKIP_HOSTS):
            continue
        if href.startswith(_SKIP_PREFIX):
            continue
        rows.append(
            {
                "t": text,
                "u": href,
                "s": host.removeprefix("www."),
                "f": REGION_LABELS.get(region, "Front page"),
                "_text": _is_directory_text(text),
                "_sep_before": bool(_SEP.search(gap)),
                "_region": region,
            }
        )

    # A directory entry is short all-caps text joined to a neighbour by a single <BR>.
    # The first entry of a run follows an <HR>, so it is judged by what follows it.
    for i, r in enumerate(rows):
        nxt_joined = i + 1 < len(rows) and not rows[i + 1]["_sep_before"]
        r["_dir"] = r["_text"] and (not r["_sep_before"] or nxt_joined)

    # Drop directory runs, but only in the column regions: the main stack is also all
    # caps and single-<BR> separated, and is exactly what we want to keep.
    keep: list[dict] = []
    i = 0
    while i < len(rows):
        if rows[i]["_dir"] and rows[i]["_region"].startswith("col"):
            j = i
            while j < len(rows) and rows[j]["_dir"] and rows[j]["_region"].startswith("col"):
                j += 1
            if j - i >= _DIRECTORY_RUN:
                i = j
                continue
        keep.append(rows[i])
        i += 1
    for r in keep:
        del r["_dir"], r["_text"], r["_sep_before"], r["_region"]
        r["p"] = None  # Drudge carries no timestamps; the page shows none, never "NA"
    return keep


def fetch() -> list[dict]:
    """One robots.txt read plus one page request. Refuses if robots disallows."""
    robots = http_get(ROBOTS_URL).text
    if not robots_allows(URL, robots):
        raise PermissionError("robots.txt disallows fetching the Drudge front page")
    items = parse(http_get(URL).content.decode("latin-1"))
    if not items:
        raise ValueError("drudge: parsed zero headlines (markup changed?)")
    print(f"  [OK]   drudge: {len(items)} headlines")
    return items
