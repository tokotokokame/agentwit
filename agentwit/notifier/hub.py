"""Notification hub: fan risk alerts out to many routes with routing + limits.

Built from ``config["notify"]``. Each route declares a ``kind``
(``slack`` / ``discord`` / ``webhook`` / ``email``), the severities it wants
(``on``), and where to send. Secrets are ``${env:...}`` references resolved
at build time. Webhook URLs are checked against an allow-list and must be
https (SSRF guard). A global per-minute rate limit stops an alert storm from
turning the monitor into its own denial-of-service.

Everything is best-effort: a broken route logs and is skipped, never raising
into the proxy request path.
"""
from __future__ import annotations

import logging
import time
from collections import deque
from typing import Any, Awaitable, Callable
from urllib.parse import urlparse

from ..config.defaults import ALLOWED_NOTIFY_HOSTS

logger = logging.getLogger(__name__)

_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}

Dispatch = Callable[[dict, list, str], Awaitable[None]]


def _worst(indicators: list[dict]) -> str:
    worst = "low"
    for ind in indicators:
        sev = str(ind.get("severity", "low")).lower()
        if _ORDER.get(sev, 0) > _ORDER.get(worst, 0):
            worst = sev
    return worst


def _safe_webhook_url(url: str | None) -> str | None:
    """Return the URL only if it is https and on the allow-list (SSRF guard)."""
    if not url:
        return None
    parsed = urlparse(url)
    if parsed.scheme != "https":
        # Do not log the URL itself — a webhook URL is a secret. Scheme only.
        logger.warning("agentwit notify: refusing non-https webhook (scheme=%r)",
                       parsed.scheme or "")
        return None
    host = (parsed.hostname or "").lower()
    if host not in ALLOWED_NOTIFY_HOSTS:
        logger.warning("agentwit notify: refusing webhook to disallowed host %r", host)
        return None
    return url


class _Route:
    def __init__(self, name: str, on: set[str], dispatch: Dispatch) -> None:
        self.name = name
        self.on = on
        self._dispatch = dispatch

    async def maybe_send(self, event: dict, indicators: list, severity: str) -> None:
        if severity not in self.on:
            return
        try:
            await self._dispatch(event, indicators, severity)
        except Exception as exc:  # pragma: no cover - defensive
            # exception text may embed the destination URL (a secret); type only.
            logger.warning("agentwit notify: route %s failed: %s", self.name, type(exc).__name__)


class NotificationHub:
    """Routes risk alerts to zero or more configured destinations."""

    def __init__(self, routes: list[_Route], max_per_min: int = 10) -> None:
        self._routes = routes
        self._max_per_min = max_per_min
        self._sent: deque[float] = deque()

    # ------------------------------------------------------------------

    @classmethod
    def from_config(cls, config: dict | None, resolver: Any = None) -> "NotificationHub":
        """Build a hub from the ``notify`` section. ``resolver`` resolves
        ``${env:...}`` references (a :class:`SecretResolver`)."""
        notify = (config or {}).get("notify", {}) or {}
        rate = (notify.get("rate_limit") or {}).get("max_per_min", 10)

        def _resolve(v: Any) -> Any:
            return resolver.resolve(v) if resolver is not None else v

        routes: list[_Route] = []
        for i, raw in enumerate(notify.get("routes", []) or []):
            if not isinstance(raw, dict):
                continue
            name = raw.get("name", f"route{i}")
            kind = str(raw.get("kind", "webhook")).lower()
            on = {str(s).lower() for s in (raw.get("on") or [])}
            if not on:
                on = {"high", "critical"}

            dispatch = cls._build_dispatch(kind, raw, _resolve, name)
            if dispatch is not None:
                routes.append(_Route(name, on, dispatch))

        return cls(routes, max_per_min=int(rate))

    @staticmethod
    def _build_dispatch(kind, raw, resolve, name) -> Dispatch | None:
        if kind in ("slack", "discord", "webhook"):
            url = _safe_webhook_url(resolve(raw.get("url") or raw.get("secret_ref")))
            if not url:
                return None
            from .webhook import WebhookNotifier

            notifier = WebhookNotifier(url=url, min_severity="low")

            async def _dispatch(event, indicators, severity):
                await notifier.notify_if_threshold(event, indicators)

            return _dispatch

        if kind == "email":
            from .email import EmailSender

            sender = EmailSender(
                host=resolve(raw.get("smtp_host", "")),
                port=raw.get("smtp_port", 587),
                use_tls=raw.get("smtp_tls", True),
                username=resolve(raw.get("smtp_user")) if raw.get("smtp_user") else None,
                password=resolve(raw.get("password_ref")) if raw.get("password_ref") else None,
                mail_from=raw.get("mail_from"),
                mail_to=raw.get("mail_to") or [],
            )
            if not sender.host:
                logger.warning("agentwit notify: email route %s has no smtp_host", name)
                return None

            async def _dispatch(event, indicators, severity):
                await sender.send(event, indicators, severity)

            return _dispatch

        logger.warning("agentwit notify: unknown route kind %r", kind)
        return None

    # ------------------------------------------------------------------

    @property
    def active(self) -> bool:
        return bool(self._routes)

    def _rate_ok(self) -> bool:
        now = time.monotonic()
        while self._sent and now - self._sent[0] > 60.0:
            self._sent.popleft()
        if len(self._sent) >= self._max_per_min:
            return False
        self._sent.append(now)
        return True

    async def notify(self, event: dict, indicators: list[dict]) -> None:
        """Dispatch an alert to every route whose severity window matches."""
        if not self._routes or not indicators:
            return
        severity = _worst(indicators)
        if not self._rate_ok():
            logger.warning(
                "agentwit notify: rate limit (%d/min) hit; dropping alert",
                self._max_per_min,
            )
            return
        for route in self._routes:
            await route.maybe_send(event, indicators, severity)
