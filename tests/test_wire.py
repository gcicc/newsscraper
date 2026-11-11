"""Tests for the parts where being wrong is silent.

Parsers run against responses saved once from the live sources (tests/fixtures/).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import run
from wire import cache, drudge, feeds
from wire.fetcher import dedupe, dedupe_key, parse_feed, split_publisher
from wire.render import _embed

FIX = Path(__file__).parent / "fixtures"


def _read(name: str) -> bytes:
    return (FIX / name).read_bytes()


# --- parsers ---------------------------------------------------------------


def test_drudge_headlines_only_and_in_page_order():
    items = drudge.parse(_read("drudge.html").decode("latin-1"))
    assert 40 <= len(items) <= 80  # the old app listed 202 anchors, ~150 of them outlet links
    assert items[0]["t"] == "Huang Affair Puts Wife in Spotlight..."
    assert items[0]["f"] == "Top left" and items[0]["s"] == "nytimes.com"
    titles = [i["t"] for i in items]
    # Outlet directory entries and Drudge utility links must be gone.
    for junk in ("BOSTON GLOBE", "REUTERS", "AGENCE FRANCE-PRESSE", "ARCHIVES", "PRIVACY POLICY"):
        assert junk not in titles
    assert all(i["u"].startswith("http") for i in items)
    assert not any("drudgereport" in i["u"] for i in items)
    assert all(i["p"] is None for i in items)
    regions = [i["f"] for i in items]
    assert regions.index("Top left") < regions.index("Main splash") < regions.index("Column 1")


def test_drudge_keeps_all_caps_main_stack():
    titles = [i["t"] for i in drudge.parse(_read("drudge.html").decode("latin-1"))]
    assert any(t.startswith("BESSENT MOVED") for t in titles)


def test_drudge_robots_respected():
    robots = _read("drudge_robots.txt").decode()
    assert drudge.robots_allows(drudge.URL, robots)
    assert not drudge.robots_allows(drudge.URL, "User-agent: *\nDisallow: /\n")


def test_fox_feed_parses_links_and_titles_without_bodies():
    items = parse_feed(_read("fox_latest.xml"), "Latest")
    assert len(items) == 25
    first = items[0]
    assert set(first) == {"t", "u", "s", "f", "p"}  # no description/content keys
    assert first["u"].startswith("https://www.foxnews.com/")
    assert first["p"] and first["f"] == "Latest"


def test_cnbc_feed_parses():
    items = parse_feed(_read("cnbc_top.xml"), "Top News")
    assert len(items) == 30
    assert all(i["t"] and i["u"].startswith("https://www.cnbc.com/") for i in items)


def test_google_news_category_splits_publisher():
    items = parse_feed(_read("gn_business.xml"), "business", split_pub=True)
    assert len(items) >= 50
    with_source = [i for i in items if i["s"]]
    assert len(with_source) > 0.9 * len(items)
    assert not any(i["t"].endswith(" - " + i["s"]) for i in with_source)


def test_parse_feed_rejects_error_page_and_empty_feed():
    with pytest.raises(ValueError):
        parse_feed(b"<html><body>Access denied</body></html>", "x")
    with pytest.raises(ValueError):
        parse_feed(b"<rss version='2.0'><channel><title>t</title></channel></rss>", "x")


def test_split_publisher():
    assert split_publisher("Fed holds rates - Reuters") == ("Fed holds rates", "Reuters")
    assert split_publisher("No suffix here") == ("No suffix here", None)


# --- dedupe -----------------------------------------------------------------


def test_dedupe_collapses_publisher_suffix_and_punctuation():
    a = {"t": "Fed holds rates - Reuters"}
    b = {"t": "Fed Holds Rates!"}
    assert dedupe_key(a["t"]) == dedupe_key(b["t"])
    assert dedupe([a, b]) == [a]


def test_dedupe_shared_seen_across_sections():
    seen: set[str] = set()
    first = dedupe([{"t": "Same story"}], seen)
    second = dedupe([{"t": "same story."}, {"t": "Other"}], seen)
    assert len(first) == 1 and [e["t"] for e in second] == ["Other"]


def test_assemble_dedupes_across_feeds_keeping_first():
    data = {
        "A": [{"t": "Story one", "u": "u1", "s": None, "f": "A", "p": "2026-11-11T10:00:00"}],
        "B": [{"t": "Story one", "u": "u2", "s": None, "f": "B", "p": "2026-11-11T09:00:00"}],
    }
    out = feeds.assemble({"A": "a", "B": "b"}, fetcher=lambda n, u, sp: data[n])
    assert len(out["items"]) == 1 and out["items"][0]["f"] == "A"


# --- stale-on-failure: the three outcomes -----------------------------------


@pytest.fixture
def tmp_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, "DATA_DIR", tmp_path)
    return tmp_path


def test_failed_fetch_keeps_previous_payload_and_marks_failed(tmp_cache):
    cache.save("fox", {"items": [{"t": "old"}], "failed_feeds": {}})

    def boom():
        raise ConnectionError("down")

    out = cache.refresh("fox", boom, force=True)
    assert out["items"] == [{"t": "old"}]  # not blanked
    rep = cache.status_report()["fox"]
    assert rep["state"] == "failed" and "ConnectionError" in rep["last_error"]
    # The next success clears the error.
    cache.refresh("fox", lambda: {"items": [{"t": "new"}], "failed_feeds": {}}, force=True)
    assert cache.status_report()["fox"]["state"] == "fresh"


def test_failed_fetch_with_no_cache_returns_none_not_crash(tmp_cache):
    assert cache.refresh("cnbc", lambda: 1 / 0, force=True) is None
    assert cache.status_report()["cnbc"]["state"] == "failed"


def test_upstream_unchanged_is_not_a_failure(tmp_cache):
    cache.save("fox", {"items": [1], "failed_feeds": {}})

    def same():
        raise cache.NotModified("304")

    assert cache.refresh("fox", same, force=True)["items"] == [1]
    rep = cache.status_report()["fox"]
    assert rep["state"] == "fresh" and rep["last_error"] is None


def test_fresh_cache_makes_no_network_call(tmp_cache):
    cache.save("fox", {"items": [1], "failed_feeds": {}})
    calls = []
    cache.refresh("fox", lambda: calls.append(1), force=False)
    assert calls == []


def test_old_cache_without_error_reports_stale(tmp_cache):
    cache.save("fox", {"items": [1], "failed_feeds": {}})
    path = tmp_cache / "fox.json"
    env = json.loads(path.read_text())
    env["fetched_at"] = "2020-01-01T00:00:00+00:00"
    path.write_text(json.dumps(env))
    assert cache.status_report()["fox"]["state"] == "stale"
    assert cache.status_report()["drudge"]["state"] == "stale"  # never fetched


def test_partial_feed_failure_carries_over_previous_items_and_flags_it():
    previous = [{"t": "kept", "u": "u", "s": None, "f": "B", "p": None}]
    good = [{"t": "fresh", "u": "u", "s": None, "f": "A", "p": "2026-11-11T10:00:00"}]

    def fetcher(name, url, split_pub):
        if name == "B":
            raise TimeoutError("slow")
        return good

    out = feeds.assemble({"A": "a", "B": "b"}, previous, fetcher=fetcher)
    assert {i["t"] for i in out["items"]} == {"fresh", "kept"}
    assert list(out["failed_feeds"]) == ["B"]


def test_all_feeds_failing_raises_so_cache_keeps_whole_payload():
    def fetcher(name, url, split_pub):
        raise TimeoutError("slow")

    with pytest.raises(RuntimeError):
        feeds.assemble({"A": "a", "B": "b"}, [], fetcher=fetcher)


def test_build_payload_never_crashes_on_empty_cache(tmp_cache):
    payload = run.build_payload()
    assert payload["sources"]["fox"]["items"] == []
    assert payload["status"]["fox"]["state"] == "stale"


# --- _embed escaping ----------------------------------------------------------


def test_embed_escapes_script_close_and_comment_open():
    data = {"t": "</script><script>alert(1)</script> <!-- x"}
    text = _embed(data)
    assert "</" not in text and "<!--" not in text
    # Parsed values are identical after a JSON round-trip.
    assert json.loads(text) == {"t": "</script><script>alert(1)</script> <!-- x"}


def test_rendered_page_has_title_chrome_and_no_na(tmp_path):
    from wire.render import render

    payload = run.build_payload()
    payload["sources"]["drudge"]["items"] = [
        {"t": "A </script> headline", "u": "https://e.com/x", "s": "e.com", "f": "Main", "p": None}
    ]
    out = render(payload, tmp_path / "index.html")
    html = out.read_text(encoding="utf-8")
    assert "<title>Wire — RANGE</title>" in html
    assert 'data-section="newsscraper"' in html and 'data-next="every 2h"' in html
    assert "data-built=" in html
    assert html.count("</script>") == html.count("<script")
    assert ">NA<" not in html


def test_feed_dates_are_read_as_utc_not_local_time():
    # <pubDate>Wed, 11 Nov 2026 14:06:28 -0500</pubDate> is 19:06:28 UTC.
    items = parse_feed(_read("fox_latest.xml"), "Latest")
    assert items[0]["p"] == "2026-11-11T19:06:28+00:00"
