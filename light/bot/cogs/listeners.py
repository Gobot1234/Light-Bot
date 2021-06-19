from __future__ import annotations

from typing import TYPE_CHECKING, Literal

import discord
from discord.ext import commands

from light.db import Config

from . import Cog
from .utils.context import Context

if TYPE_CHECKING:
    from .. import Light


class Listeners(Cog):
    """Listeners for the bot"""

    async def cog_check(self, ctx: Context) -> Literal[False]:
        return False  # There shouldn't ever be any commands here

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild) -> None:
        config = await Config.fetch_row(guild_id=guild.id)
        if config is None:
            config = await Config.insert(guild_id=guild.id, prefixes=["="], returning="*")
        elif config.blacklisted:
            self.bot.log.info(f"Leaving {guild.name!r} - {guild.id} as it is a blacklisted guild")
            return await guild.leave()
        self.bot.configs[config.guild_id] = config

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild) -> None:
        if not (record := await Config.fetch_row(guild_id=guild.id)).blacklisted:
            await Config.delete_record(record)
            self.bot.configs.pop(guild.id)
            self.bot.log.info(f"Leaving guild {guild.name} - {guild.id}")


def setup(bot: Light) -> None:
    bot.add_cog(Listeners(bot))
