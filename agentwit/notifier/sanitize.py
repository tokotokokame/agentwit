"""Neutralise untrusted fields before they go into a notification.

Tool names, patterns and actors come from MCP traffic an attacker can
influence. Interpolated raw into Slack/Discord markdown or an email they
could forge mentions (@channel), inject control sequences, or break out of
code spans. This strips those teeth while keeping the text readable.
"""
from __future__ import annotations

import re

_CTRL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")       # control chars (keep \t,\n handled below)
_SLACK_CTRL = re.compile(r"<[!@#][^>]*>")             # <!channel>, <@U…>, <#C…>
_MENTION = re.compile(r"(?i)@(channel|here|everyone)")


def clean_field(value: object, limit: int = 200) -> str:
    """Return a safe, single-line, length-bounded version of *value*."""
    s = str(value if value is not None else "")
    s = s.replace("\r", " ").replace("\n", " ").replace("\t", " ")
    s = _CTRL.sub("", s)
    s = _SLACK_CTRL.sub("", s)                        # drop Slack control spans
    s = _MENTION.sub(r"@​\1", s)                 # @channel -> @<zws>channel (no ping)
    s = s.replace("`", "ʼ")                           # keep it out of code-span breakout
    if len(s) > limit:
        s = s[: limit - 1] + "…"
    return s
