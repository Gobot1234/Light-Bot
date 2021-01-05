from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

import dateparser
import steam
from discord.ext import commands
from discord.ext.alternatives import asset_converter, guild_converter
from jishaku.codeblocks import codeblock_converter

from .context import Context


class DatetimeConverter(commands.Converter):
    def __init__(self, *args: Any, **kwargs: Any):
        self.date_parser = dateparser.DateDataParser(*args, **kwargs)

    async def convert(self, ctx: Context, argument: str) -> datetime:
        if date := self.date_parser.get_date_data(argument)["date_obj"]:
            return date
        raise commands.BadArgument("I'm sorry I couldn't convert that to a time.")


class SteamUser(commands.Converter):
    async def convert(self, ctx: Context, argument: str) -> steam.User:
        try:
            return await ctx.bot.client.fetch_user(argument)
        except steam.InvalidSteamID:
            steam_id = await steam.utils.id64_from_url(argument)
            if steam_id is None:
                raise commands.BadArgument(f"I couldn't fine a matching ID or URL for {argument}")
            return await ctx.bot.client.fetch_user(steam_id)


if TYPE_CHECKING:
    # make linters play nicely with d.py's converters
    SteamUser = steam.User
    DatetimeConverter = datetime
