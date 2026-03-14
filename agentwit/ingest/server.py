"""Ingest server for receiving witness log events pushed from external agents.

This module provides an HTTP endpoint that accepts witness log events posted
by remote agents and writes them to a local session log.
"""
from __future__ import annotations


class IngestServer:
    """HTTP ingest server that accepts witness log events from remote agents.

    Attributes:
        host: The host address to bind to.
        port: The TCP port to listen on.
        witness_logger: Logger instance for persisting received events.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 9000, witness_logger: object = None) -> None:
        """Initialise the IngestServer.

        Args:
            host: Host address to bind.
            port: TCP port to listen on.
            witness_logger: A :class:`~agentwit.witness.log.WitnessLogger`
                instance.
        """
        self.host = host
        self.port = port
        self.witness_logger = witness_logger

    async def serve(self) -> None:
        """Start accepting ingest requests.

        .. note::
            Not yet implemented.
        """
        raise NotImplementedError("IngestServer.serve is not yet implemented")
