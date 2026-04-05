from __future__ import annotations

import importlib
import pkgutil
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from pyrogram import Client

    from src.core.context import AppContext


class Plugin(ABC):
    name: str = ""
    priority: int = 100

    @abstractmethod
    async def setup(self, client: Client, ctx: AppContext) -> None:
        pass

    async def teardown(self) -> None:  # noqa: B027
        pass


_registry: list[Plugin] = []


def register(plugin: Plugin) -> None:
    _registry.append(plugin)
    logger.debug(f"Plugin registered: {plugin.name}")


def get_plugins() -> list[Plugin]:
    return sorted(_registry, key=lambda p: p.priority)


def autodiscover(package: str = "src.plugins") -> None:
    plugins_path = Path(__file__).parent.parent / "plugins"
    for mod_info in pkgutil.iter_modules([str(plugins_path)]):
        module_name = f"{package}.{mod_info.name}"
        try:
            importlib.import_module(module_name)
            logger.debug(f"Loaded plugin module: {module_name}")
        except Exception as e:
            logger.error(f"Failed to load plugin {module_name}: {e}")
            raise
