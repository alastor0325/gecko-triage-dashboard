"""Teams that the dashboard shows. The components are a copy of the agent's
`teams/<team>/team.toml`, for the landing page; keep the two in step."""

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


# The dashboard is built for the media team only. Every local run (a pilot day folder or a
# test round) is made for it: run-round.sh runs with TEAM=media.
LOCAL_TEAM = "media"


_SHOWN = frozenset(t.slug for t in TEAMS)


def is_shown(team: str | None) -> bool:
    """Only the runs whose input names a team of TEAMS are shown, not a run made for no
    team or for another team."""
    return team in _SHOWN
