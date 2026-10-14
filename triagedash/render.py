"""Writes the static site from the computed team pages. Pure string building."""

from __future__ import annotations

import html
import json
from pathlib import Path

from .teams import Team

TEMPLATES = Path(__file__).resolve().parent.parent / "templates"


def embed_json(value) -> str:
    """JSON that is safe inside a <script> element."""
    return json.dumps(value, separators=(",", ":")).replace("</", "<\\/")


def team_html(template: str, team: Team, page: dict) -> str:
    return (
        template.replace("__TEAM__", html.escape(team.slug))
        .replace("__LABEL__", html.escape(team.label))
        .replace("__DATA__", embed_json(page))
    )


def team_row(index: int, team: Team, page: dict | None) -> str:
    components = '<span class="sep">·</span>'.join(html.escape(c) for _, c in team.components)
    if page:
        counts = page["overview"]["1w"]["counts"]
        stats = (
            f"<strong>{counts['all']}</strong>bugs handled in 1 week"
            f" · {counts['close']} closed or reassigned"
        )
    else:
        stats = "<strong>-</strong>no runs yet"
    return (
        f'  <a class="team-row" href="{html.escape(team.slug)}/index.html">'
        f'<div class="row-num">{index:02d}</div>'
        f'<div class="row-meta"><div class="row-name">{html.escape(team.slug)}</div>'
        f'<div class="row-paths">{components}</div></div>'
        f'<div class="row-stats">{stats}</div><div class="row-arrow">→</div></a>'
    )


def landing_html(template: str, teams: tuple[Team, ...], pages: dict[str, dict]) -> str:
    rows = "\n".join(team_row(i, t, pages.get(t.slug)) for i, t in enumerate(teams, 1))
    meta = (
        f"<span>{len(teams)} {'dashboard' if len(teams) == 1 else 'dashboards'}</span>"
        '\n    <span class="sep">·</span>\n    <span>What the bot changed, riskiest first</span>'
    )
    return template.replace("__ROWS__", rows).replace("__META__", meta)
