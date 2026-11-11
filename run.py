"""Wire entry point.

    python run.py             # refresh sources whose cache has expired, then render
    python run.py --force     # refresh every source regardless of cache age
    python run.py --render    # render from cache only, no network at all

Provenance: shape follows ``02-Maintain/hangar/run.py``. Each source declares a max_age
in ``wire/cache.py``; a run only goes to the network for expired sources, and a failed
source keeps its previous payload and is flagged on the page.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path

from wire import cache, drudge
from wire.feeds import (
    CATEGORY_FEEDS,
    CATEGORY_LABELS,
    CNBC_FEEDS,
    FOX_FEEDS,
    assemble,
)
from wire.render import render

ROOT = Path(__file__).resolve().parent


def _previous(name: str) -> list[dict]:
    env = cache.load(name)
    return (env or {}).get("data", {}).get("items", []) if env else []


def fetch_drudge() -> dict:
    return {"items": drudge.fetch(), "failed_feeds": {}}


def fetch_fox() -> dict:
    return assemble(FOX_FEEDS, _previous("fox"))


def fetch_cnbc() -> dict:
    return assemble(CNBC_FEEDS, _previous("cnbc"))


def fetch_categories() -> dict:
    return assemble(
        CATEGORY_FEEDS,
        _previous("categories"),
        split_pub=True,
        per_feed_dedupe=True,
        sort_newest=False,
    )


FETCHERS = {
    "drudge": fetch_drudge,
    "fox": fetch_fox,
    "cnbc": fetch_cnbc,
    "categories": fetch_categories,
}


def build_payload() -> dict:
    def cached(name: str) -> dict:
        env = cache.load(name)
        return (env or {}).get("data") or {"items": [], "failed_feeds": {}}

    return {
        "meta": {"generated": datetime.now(UTC).isoformat(timespec="seconds"), "version": "0.1.0"},
        "sources": {
            "drudge": {"label": "Drudge Report", **cached("drudge")},
            "fox": {"label": "Fox News", **cached("fox")},
            "cnbc": {"label": "CNBC Financial News", **cached("cnbc")},
        },
        "categories": {
            "labels": CATEGORY_LABELS,
            "failed_feeds": cached("categories")["failed_feeds"],
            "items": {
                k: [i for i in cached("categories")["items"] if i.get("f") == k]
                for k in CATEGORY_LABELS
            },
        },
        "status": cache.status_report(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the Wire page.")
    parser.add_argument("--force", action="store_true", help="refresh every source")
    parser.add_argument("--render", action="store_true", help="render from cache; no network")
    args = parser.parse_args()

    if args.render:
        print("=== RENDER ONLY (no network) ===")
    else:
        for name, fn in FETCHERS.items():
            print(f"\n=== {name.upper()} ===")
            cache.refresh(name, fn, force=args.force)

    payload = build_payload()
    print("\n=== STATUS ===")
    for name, s in payload["status"].items():
        n = (
            sum(len(v) for v in payload["categories"]["items"].values())
            if name == "categories"
            else len(payload["sources"][name]["items"])
        )
        err = f"  last error: {s['last_error']}" if s["last_error"] else ""
        print(f"  {s['state']:6s} {name:11s} items={n:4d} age={s['age']:>6}{err}")

    out = ROOT / "docs" / "index.html"
    out.parent.mkdir(exist_ok=True)
    render(payload, out)
    print(f"\nWrote {out.stat().st_size:,} bytes to {out}")


if __name__ == "__main__":
    main()
