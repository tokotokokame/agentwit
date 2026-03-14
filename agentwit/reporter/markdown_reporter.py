"""Markdown report generator for witness log sessions."""
from __future__ import annotations

from pathlib import Path


class MarkdownReporter:
    """Generate a Markdown-formatted audit report from a witness log session.

    Attributes:
        session_dir: Path to the session directory.
    """

    def __init__(self, session_dir: Path) -> None:
        """Initialise the MarkdownReporter.

        Args:
            session_dir: Path to the session directory containing
                ``witness.jsonl``.
        """
        self.session_dir = Path(session_dir)

    def load_events(self) -> list[dict]:
        """Read all events from ``witness.jsonl``.

        Returns:
            Ordered list of event dicts.

        .. note::
            Not yet fully implemented.
        """
        raise NotImplementedError("MarkdownReporter.load_events is not yet implemented")

    def generate(self) -> str:
        """Build and return the Markdown report string.

        Returns:
            A Markdown-formatted report.

        .. note::
            Not yet fully implemented.
        """
        raise NotImplementedError("MarkdownReporter.generate is not yet implemented")

    def render(self) -> str:
        """Alias for :meth:`generate`.

        Returns:
            A Markdown-formatted report string.
        """
        return self.generate()
