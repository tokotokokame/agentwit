"""SSE transparent proxy.

Handles Server-Sent Events streams between an agent and an MCP server,
recording each SSE event to the witness log without interrupting the stream.
"""
from __future__ import annotations


class SseProxy:
    """Transparent SSE proxy that records events to the witness log.

    This is a skeleton implementation. See :mod:`agentwit.proxy.http_proxy`
    for the integrated SSE handling that is used in the MVP.

    Attributes:
        target_url: The upstream SSE endpoint URL.
        witness_logger: Logger instance for recording events.
    """

    def __init__(self, target_url: str, witness_logger: object) -> None:
        """Initialise the SSE proxy.

        Args:
            target_url: Upstream SSE endpoint.
            witness_logger: A :class:`~agentwit.witness.log.WitnessLogger`.
        """
        self.target_url = target_url
        self.witness_logger = witness_logger

    async def stream(self) -> None:
        """Open the upstream SSE stream and forward events to the client.

        .. note::
            Not yet implemented. Use :func:`~agentwit.proxy.http_proxy.create_proxy_app`
            for SSE proxying in the current release.
        """
        raise NotImplementedError("SseProxy.stream is not yet implemented")
