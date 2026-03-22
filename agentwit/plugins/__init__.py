"""agentwit plugin loader.

Discovers and instantiates plugins registered under the
``agentwit.plugins`` entry-point group.
"""
from __future__ import annotations

import importlib.metadata
import logging

logger = logging.getLogger(__name__)


def load_plugins() -> list:
    """entry_points "agentwit.plugins" からプラグインを自動ロード。

    Returns:
        A list of instantiated :class:`~agentwit.plugins.base.PluginBase`
        objects.  Returns an empty list when no plugins are installed or
        when every plugin fails to load.
    """
    plugins = []
    try:
        eps = importlib.metadata.entry_points(group="agentwit.plugins")
        for ep in eps:
            try:
                plugin_class = ep.load()
                plugin = plugin_class()
                plugins.append(plugin)
                logger.info("Loaded plugin: %s v%s", plugin.name, plugin.version)
            except Exception as e:
                logger.warning("Failed to load plugin %s: %s", ep.name, e)
    except Exception as e:
        logger.debug("No plugins found: %s", e)
    return plugins
