"""Render the payload into one self-contained HTML file.

Provenance: adapted from ``02-Maintain/hangar/hangar/render.py``. CSS, JavaScript and data
are inlined so the page opens from file:// with no fetches of its own. ``_embed`` is
copied verbatim from hangar: headlines are third-party text, so escaping is load-bearing.
"""

from __future__ import annotations

import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

TEMPLATES = Path(__file__).resolve().parent / "templates"


def render(data: dict, out: Path) -> Path:
    env = Environment(
        loader=FileSystemLoader(TEMPLATES),
        autoescape=select_autoescape(default=False),
    )
    template = env.get_template("page.html.j2")
    html = template.render(
        styles=(TEMPLATES / "styles.css").read_text(encoding="utf-8"),
        app=(TEMPLATES / "app.js").read_text(encoding="utf-8"),
        payload=_embed(data),
        generated=data["meta"]["generated"].replace("T", " "),
    )
    out.write_text(html, encoding="utf-8")
    return out


def _embed(data: dict) -> str:
    """Serialise the payload for inlining inside a <script> block.

    ``</script>`` anywhere in the data would close the block early, and ``<!--``
    opens an HTML comment inside it. Both are escaped at the JSON level, which
    leaves the parsed values identical. Headlines are user-supplied text from
    third-party feeds, so this is load-bearing, not theoretical.
    """
    text = json.dumps(data, separators=(",", ":"), allow_nan=False, default=str)
    return text.replace("<\\/", "<\\\\/").replace("</", "<\\/").replace("<!--", "\\u003c!--")
