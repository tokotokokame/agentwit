"""agentwit - Transparent proxy witness for AI agent ↔ MCP server communications."""
__version__ = "0.2.0"
from .witness.log import WitnessLogger
from .witness.chain import ChainManager
__all__ = ["WitnessLogger", "ChainManager"]
