"""Per-source JSON cache with age gating and a status ledger.

Provenance: adapted from ``02-Maintain/hangar/hangar/cache.py``. Kept: the envelope,
``refresh`` with its three distinct outcomes, and the ledger. Changed: Wire has four
sources, no published-file split, and ``status_report`` yields a three-way ``state``
(fresh / stale / failed) for the page's status bus.

The three outcomes of ``refresh`` must never be confused:

1. **Fetch failed** - keep the previous payload, mark the source failed and record the
   error. The page renders the old data with a visible marker. An empty panel would be
   indistinguishable from a quiet news day.
2. **Upstream unchanged** (``NotModified``) - a success; the cached copy and its
   timestamp are kept and nothing is flagged.
3. **Still fresh** - younger than ``max_age``; no network call is made at all.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# One request per source per refresh; the workflow fires every 2 hours.
MAX_AGE: dict[str, timedelta] = {
    "drudge": timedelta(hours=2),
    "fox": timedelta(hours=2),
    "cnbc": timedelta(hours=2),
    "categories": timedelta(hours=2),
}

# Older than STALE_FACTOR x max_age counts as stale even with no recorded error, so one
# missed cron run does not paint the page, but a stopped workflow does.
STALE_FACTOR = 2


class NotModified(Exception):
    """Upstream reports its data is unchanged since our last successful fetch."""


def _path(name: str) -> Path:
    return DATA_DIR / f"{name}.json"


def _now() -> datetime:
    return datetime.now(UTC)


def _parse_ts(text: str | None) -> datetime | None:
    if not text:
        return None
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def load(name: str) -> dict | None:
    """Return the cached envelope ``{fetched_at, data}`` for ``name``, or None."""
    path = _path(name)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        print(f"  [WARN] cache unreadable for {name}: {e}")
        return None


def save(name: str, data: Any) -> dict:
    """Write ``data`` under a ``fetched_at`` envelope and return the envelope."""
    path = _path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    envelope = {"fetched_at": _now().isoformat(timespec="seconds"), "data": data}
    path.write_text(json.dumps(envelope, indent=1, sort_keys=True, default=str), encoding="utf-8")
    return envelope


def age(name: str) -> timedelta | None:
    envelope = load(name)
    if not envelope:
        return None
    ts = _parse_ts(envelope.get("fetched_at"))
    return None if ts is None else _now() - ts


def is_fresh(name: str) -> bool:
    a = age(name)
    return a is not None and a < MAX_AGE.get(name, timedelta(hours=2))


def refresh(name: str, fetch_fn: Callable[[], Any], force: bool = False) -> Any:
    """Return data for ``name``, fetching only if the cache has expired."""
    if not force and is_fresh(name):
        print(f"  [SKIP] {name}: cached {_humanize(age(name))} ago, still fresh")
        _record(name, ok=True, fetched=False)
        envelope = load(name)
        return envelope["data"] if envelope else None

    try:
        data = fetch_fn()
    except NotModified as e:
        print(f"  [SAME] {name}: {e}")
        _record(name, ok=True, fetched=False)
        envelope = load(name)
        return envelope["data"] if envelope else None
    except Exception as e:  # noqa: BLE001 - any upstream failure must fall back
        print(f"  [FAIL] {name}: {e}")
        _record(name, ok=False, error=f"{type(e).__name__}: {e}")
        envelope = load(name)
        if envelope:
            print(f"  [WARN] {name}: serving cached copy from {envelope.get('fetched_at')}")
            return envelope["data"]
        return None

    save(name, data)
    _record(name, ok=True, fetched=True)
    print(f"  [OK]   {name}: refreshed")
    return data


def _humanize(delta: timedelta | None) -> str:
    if delta is None:
        return "never"
    seconds = int(delta.total_seconds())
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m"
    if seconds < 86400:
        return f"{seconds // 3600}h"
    return f"{seconds // 86400}d"


# --- status ledger -------------------------------------------------------


def _status_path() -> Path:
    return DATA_DIR / "status.json"


def _read_status() -> dict:
    path = _status_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _record(name: str, ok: bool, fetched: bool = False, error: str | None = None) -> None:
    """Update one source's entry in the status ledger."""
    status = _read_status()
    entry = status.get(name, {})
    entry["last_attempt"] = _now().isoformat(timespec="seconds")
    if ok:
        if fetched:
            entry["last_success"] = _now().isoformat(timespec="seconds")
        entry["last_error"] = None
    else:
        entry["last_error"] = error
        entry["last_error_at"] = _now().isoformat(timespec="seconds")
    status[name] = entry
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    _status_path().write_text(json.dumps(status, indent=1, sort_keys=True), encoding="utf-8")


def status_report() -> dict[str, dict]:
    """Per-source freshness for the page's status bus.

    ``state`` is ``failed`` when the last attempt errored (the page is showing the
    previous payload), ``stale`` when the copy is older than STALE_FACTOR x max_age or
    absent, else ``fresh``.
    """
    status = _read_status()
    report: dict[str, dict] = {}
    for name, max_age in MAX_AGE.items():
        a = age(name)
        entry = status.get(name, {})
        error = entry.get("last_error")
        if error:
            state = "failed"
        elif a is None or a > max_age * STALE_FACTOR:
            state = "stale"
        else:
            state = "fresh"
        report[name] = {
            "state": state,
            "fetched_at": (load(name) or {}).get("fetched_at"),
            "age": _humanize(a),
            "last_error": error,
            "last_error_at": entry.get("last_error_at"),
        }
    return report
