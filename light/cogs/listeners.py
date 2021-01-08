from __future__ import annotations

from typing import TYPE_CHECKING, Literal

import discord
from discord.ext import commands

from . import Cog
from .utils.context import Context
from .utils.db import Config

if TYPE_CHECKING:
    from .. import Light


class Listeners(Cog):
    """Listeners for the bot"""

    async def cog_check(self, ctx: Context) -> Literal[False]:
        return False  # There shouldn't ever be any commands here

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild) -> None:
        record = await Config.fetchrow(guild_id=guild.id)
        if record is not None and record.blacklisted:
            self.bot.log.info(f"Leaving {guild.name!r} - {guild.id} as it is a blacklisted guild")
            return await guild.leave()

        record = await Config.insert(guild_id=guild.id, blacklisted=False, prefixes=["="], returning="*")
        record.prefixes = {"="}
        self.bot.config_cache[record.guild_id] = record

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild) -> None:
        if not (record := await Config.fetchrow(guild_id=guild.id)).blacklisted:
            await record.delete_record()
            self.bot.config_cache.pop(guild.id)
            self.bot.log.info(f"Leaving guild {guild.name} - {guild.id}")


def setup(bot: Light) -> None:
    bot.add_cog(Listeners(bot))
