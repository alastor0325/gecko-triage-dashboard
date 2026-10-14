"""Renders the Markdown subset the bot writes in its comments: paragraphs, numbered and
bulleted lists, a `---` rule, bold, inline code and https links. The text is escaped
first, so no HTML from a comment reaches the page."""

from __future__ import annotations

import html
import re

_CODE = re.compile(r"`([^`]+)`")
_BOLD = re.compile(r"\*\*([^*]+)\*\*")
_LINK = re.compile(r"\[([^\]]+)\]\((https?:[^)\s]+)\)")
_OL = re.compile(r"^\s*\d+\.\s+")
_UL = re.compile(r"^\s*[-*]\s+")
_RULE = re.compile(r"^-{3,}$")
_BLOCKS = re.compile(r"\n\s*\n")


def inline(text: str) -> str:
    out = _CODE.sub(r"<code>\1</code>", html.escape(text, quote=True))
    out = _BOLD.sub(r"<strong>\1</strong>", out)
    return _LINK.sub(r'<a href="\2">\1</a>', out)


def block(text: str) -> str:
    if _RULE.match(text.strip()):
        return "<hr>"
    lines = text.split("\n")
    for pattern, tag in ((_OL, "ol"), (_UL, "ul")):
        if all(pattern.match(line) for line in lines):
            items = "".join(f"<li>{inline(pattern.sub('', line))}</li>" for line in lines)
            return f"<{tag}>{items}</{tag}>"
    return "<p>" + "<br>".join(inline(line) for line in lines) + "</p>"


def render(text: str) -> str:
    return "".join(block(b) for b in _BLOCKS.split(text.strip()))
