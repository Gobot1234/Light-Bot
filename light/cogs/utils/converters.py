from __future__ import annotations

from typing import TYPE_CHECKING

import steam
from discord.ext import commands
from discord.ext.alternatives import asset_converter

from .context import Context


class SteamUser(commands.Converter):
    async def convert(self, ctx: Context, argument: str) -> steam.User:
        try:
            return await ctx.bot.client.fetch_user(argument)
        except steam.InvalidSteamID:
            steam_id = await steam.utils.id64_from_url(argument, ctx.bot.session)
            if steam_id is None:
                raise commands.BadArgument(f"I couldn't fine a matching ID or URL for {argument}")
            return await ctx.bot.client.fetch_user(steam_id)


class SteamClan(commands.Converter):
    async def convert(self, ctx: Context, argument: str) -> steam.Clan:
        try:
            return await ctx.bot.client.fetch_clan(argument)
        except steam.InvalidSteamID:
            steam_id = await steam.utils.id64_from_url(argument, ctx.bot.session)
            if steam_id is None:
                raise commands.BadArgument(f"I couldn't fine a matching ID or URL for {argument}")
            return await ctx.bot.client.fetch_clan(steam_id)


if TYPE_CHECKING:
    # make linters play nicely with d.py's converters
    SteamUser = steam.User
    SteamClan = steam.Clan
