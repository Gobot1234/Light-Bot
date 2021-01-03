from typing import Optional, TYPE_CHECKING

import steam
from discord.ext import commands
from discord.ext.alternatives import asset_converter, guild_converter, class_commands
from jishaku.codeblocks import codeblock_converter

from .context import Context


class UserConverter(commands.Converter):
    async def convert(self, ctx: Context, argument: str) -> Optional[steam.User]:
        try:
            return await ctx.bot.client.fetch_user(argument)
        except steam.InvalidSteamID:
            steam_id = await steam.utils.id64_from_url(argument)
            if steam_id is None:
                return
            await ctx.bot.client.fetch_user(steam_id)


if TYPE_CHECKING:
    UserConverter = Optional[steam.User]  # make linters play nicely with d.py's converters
