"""stdio wrapper proxy.

Wraps a subprocess-based MCP server, intercepting stdin/stdout communication
and recording it to the witness log.
"""
from __future__ import annotations


class StdioProxy:
    """Transparent stdio proxy for subprocess MCP servers.

    Spawns the target MCP server as a child process and pipes stdin/stdout
    through the proxy, logging every message to the witness log.

    Attributes:
        command: The command and arguments used to start the MCP server.
        witness_logger: Logger instance for recording events.
    """

    def __init__(self, command: list[str], witness_logger: object) -> None:
        """Initialise the stdio proxy.

        Args:
            command: Command + arguments to launch the MCP server subprocess
                (e.g. ``["npx", "my-mcp-server"]``).
            witness_logger: A :class:`~agentwit.witness.log.WitnessLogger`.
        """
        self.command = command
        self.witness_logger = witness_logger

    async def run(self) -> None:
        """Start the subprocess and begin proxying stdin/stdout.

        .. note::
            Not yet implemented.
        """
        raise NotImplementedError("StdioProxy.run is not yet implemented")
