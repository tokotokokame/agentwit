"""Timeline construction from witness log events.

Provides a chronological view of events within a session, annotated with
timing information and risk scores.
"""
from __future__ import annotations


class Timeline:
    """Build and display a chronological timeline of witness log events.

    Attributes:
        events: The ordered list of events this timeline is built from.
    """

    def __init__(self, events: list[dict]) -> None:
        """Initialise the Timeline.

        Args:
            events: Ordered list of signed witness log event dicts.
        """
        self.events = events

    def build(self) -> list[dict]:
        """Build the timeline entries.

        Returns:
            A list of timeline entry dicts, each containing at minimum the
            event's ``timestamp``, ``action``, ``tool``, and ``witness_id``.

        .. note::
            Not yet fully implemented.
        """
        raise NotImplementedError("Timeline.build is not yet implemented")

    def render_text(self) -> str:
        """Render the timeline as a human-readable text string.

        Returns:
            A multi-line string representation of the timeline.

        .. note::
            Not yet fully implemented.
        """
        raise NotImplementedError("Timeline.render_text is not yet implemented")
