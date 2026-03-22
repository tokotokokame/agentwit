"""Base class for agentwit plugins.

Third-party plugins implement :class:`PluginBase` and register themselves
via the ``agentwit.plugins`` entry-point group in their ``pyproject.toml``::

    [project.entry-points."agentwit.plugins"]
    my_plugin = "my_package:MyPlugin"

agentwit will then discover and load the plugin automatically at startup.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class PluginBase(ABC):
    """agentwitプラグインの基底クラス。

    使い方:
        pip install agentwit-plugin-myname
        # pyproject.tomlに以下を記述:
        # [project.entry-points."agentwit.plugins"]
        # my_plugin = "my_package:MyPlugin"
    """

    @property
    def name(self) -> str:
        """プラグイン名（英数字・ハイフンのみ）"""
        return self.__class__.__name__.lower()

    @property
    def version(self) -> str:
        return "0.1.0"

    @abstractmethod
    def scan(self, event: dict) -> list[dict]:
        """イベントを受け取り、アラートリストを返す。

        Args:
            event: A witness log event dict containing keys such as
                ``action``, ``tool``, ``full_payload``, etc.

        Returns:
            A list of alert dicts, each with at minimum::

                {"pattern": "my_pattern", "severity": "HIGH",
                 "description": "..."}

            Return an empty list when no issues are found.
        """
        raise NotImplementedError
