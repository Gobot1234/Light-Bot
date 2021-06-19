from __future__ import annotations

import inspect
import os
from functools import partial
from typing import TYPE_CHECKING, Callable

from discord.ext import commands

from .utils import __

if TYPE_CHECKING:
    from .. import Light


class Cog(commands.Cog):
    def __init__(self, bot: Light) -> None:
        self.bot = bot


class TypedCommand(commands.Command):
    @property
    def params(self) -> dict[str, inspect.Parameter]:
        return self._params

    @params.setter
    def params(self, params: dict[str, inspect.Parameter]) -> None:
        for name, param in params.items():
            if inspect.isclass(param.annotation):
                params[name] = param.replace(
                    annotation=commands.converter.CONVERTER_MAPPING.get(param.annotation, param.annotation)
                )

        self._params = params


class TypedGroup(TypedCommand, commands.Group):
    def command(self, *args, **kwargs) -> Callable[..., TypedCommand]:
        return super().command(*args, cls=TypedCommand, **kwargs)

    def group(self, *args, **kwargs) -> Callable[..., TypedGroup]:
        return super().group(*args, cls=TypedGroup, **kwargs)


command: Callable[..., Callable[..., TypedCommand]] = partial(commands.command, cls=TypedCommand)
group: Callable[..., Callable[..., TypedGroup]] = partial(commands.group, cls=TypedGroup)

os.environ["JISHAKU_RETAIN"] = "true"
os.environ["JISHAKU_NO_UNDERSCORE"] = "true"
