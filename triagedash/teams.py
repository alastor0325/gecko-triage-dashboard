"""Teams that gecko-triage triages. A copy of the components in the agent's
`teams/<team>/team.toml`; keep the two in step."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Team:
    slug: str
    label: str
    components: tuple[tuple[str, str], ...]


TEAMS: tuple[Team, ...] = (
    Team(
        slug="media",
        label="Firefox Audio/Video",
        components=(
            ("Core", "Audio/Video"),
            ("Core", "Audio/Video: cubeb"),
            ("Core", "Audio/Video: GMP"),
            ("Core", "Audio/Video: MediaStreamGraph"),
            ("Core", "Audio/Video: Playback"),
            ("Core", "Audio/Video: Recording"),
            ("Core", "Web Audio"),
            ("Core", "Audio/Video: Web Codecs"),
        ),
    ),
)


def team_for(product: str | None, component: str | None) -> str | None:
    for team in TEAMS:
        if (product, component) in team.components:
            return team.slug
    return None
