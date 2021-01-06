from __future__ import annotations

from random import choice
from typing import Literal

import discord
from discord.ext import commands, tasks

from . import Cog
from .utils.context import Context
from .utils.db import Config


class Listeners(Cog):
    """Listeners for the bot"""

    async def cog_check(self, ctx: Context) -> Literal[False]:
        return False

    @tasks.loop(minutes=60)
    async def status(self) -> None:
        status = choice(
            [
                f"over {len(self.bot.guilds)} servers",
                f"over {len(set(self.bot.get_all_members()))} members",
                f"for =help",
            ]
        )
        activity = discord.Activity(name=status, type=discord.ActivityType.watching)
        await self.bot.change_presence(activity=activity)

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        if self.bot.first_ready:
            self.status.start()

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild) -> None:
        record = await Config.fetch_row(guild_id=guild.id)
        if record is not None and record.blacklisted:
            self.bot.log.info(f"Leaving {guild.name!r} - {guild.id} as it is a blacklisted guild")
            return await guild.leave()
        else:
            await Config.insert(
                guild_id=guild.id, blacklisted=False, prefixes=["="]
            )
            record = await Config.fetch_row(guild_id=guild.id)
            record.prefixes = {"="}
        self.bot.config_cache[record.guild_id] = record

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild) -> None:
        if not (await Config.fetch_row(guild_id=guild.id)).blacklisted:
            await Config.delete(guild_id=guild.id)
            self.bot.config_cache.pop(guild.id)
            self.bot.log.info(f"Leaving guild {guild.name} - {guild.id}")


def setup(bot):
    bot.add_cog(Listeners(bot))
