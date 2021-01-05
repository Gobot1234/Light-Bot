from __future__ import annotations

from random import choice
from typing import TYPE_CHECKING

import discord
from discord.ext import commands, tasks

from . import Cog
from .utils.context import Context
from .utils.db import Config
from .utils.formats import format_error

if TYPE_CHECKING:
    from .. import Light


class Listeners(Cog):
    """Listeners for the bot"""

    async def cog_check(self, ctx):
        return False

    @tasks.loop(minutes=60)
    async def status(self):
        status = choice(
            [
                f"over {len(self.bot.guilds)} servers",
                f"over {len(set(self.bot.get_all_members()))} members",
                f"for =help",
            ]
        )
        activity = discord.Activity(name=status, type=discord.ActivityType.watching)
        await self.bot.change_presence(activity=activity)

    @status.before_loop
    async def wait_for_ready_status(self):
        await self.bot.wait_until_ready()

    status.start()

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild) -> None:
        record = await Config.fetchrow(guild_id=guild.id)
        if record is not None and record.blacklisted:
            self.bot.log.info(f"Leaving {guild.name!r} - {guild.id} as it is a blacklisted guild")
            await guild.leave()
        else:
            record = await Config.insert(
                guild_id=guild.id, blacklisted=False, prefixes=["="], logging_channel=None, logged_events=[],
            )
        self.bot.config_cache[record.guild_id] = dict(record.original)

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild) -> None:
        if not (await Config.fetchrow(guild_id=guild.id)).blacklisted:
            await Config.delete(guild_id=guild.id)
            self.bot.config_cache.pop(guild.id)
            self.bot.log.info(f"Leaving guild {guild.name} - {guild.id}")

    @commands.Cog.listener()
    async def on_command_error(self, ctx: Context, error: commands.CommandError):
        """Command error handler"""
        raise error

        if hasattr(ctx.command, "on_error"):
            return
        error = getattr(error, "original", error)
        if isinstance(error, (commands.CommandNotFound, commands.CheckFailure)):
            return
        elif isinstance(error, commands.MissingRequiredArgument):
            title = f"{ctx.command} is missing a required argument {error.param}"
        elif isinstance(error, commands.CommandOnCooldown):
            if ctx.guild and ctx.author.guild_permissions.manage_roles:
                return await ctx.reinvoke()
            title = f"{ctx.command} is on cooldown"
        elif isinstance(error, commands.BadArgument):
            title = "Bad argument"
        elif isinstance(error, commands.NotOwner):
            title = "You are not the owner of the bot"
        elif isinstance(error, commands.MissingPermissions):
            title = f"You do not have the necessarily permissions to run {ctx.command}"
        elif isinstance(error, commands.BotMissingPermissions):
            title = "The bot is missing permissions to perform that command"
        elif isinstance(error, commands.DisabledCommand):
            title = f"{ctx.command} has been disabled."
        elif isinstance(error, commands.NoPrivateMessage):
            title = f"{ctx.command} can not be used in Private Messages"
        elif isinstance(error, discord.Forbidden):
            title = "Forbidden - Discord says no"
        elif isinstance(error, commands.CommandInvokeError):
            title = "This command errored: please hang tight, whilst I try to fix this"
            embed = discord.Embed(
                title=f"Ignoring exception in command {ctx.command}",
                description=f"```py\n{discord.utils.escape_markdown(format_exec(error))}```",
                colour=discord.Colour.red(),
            )
            embed.set_author(
                name=(
                    f'Command {ctx.command} {f"{ctx.guild.name} - {ctx.guild.id}," if ctx.guild else ""} used by '
                    f"{ctx.author.name} - {ctx.author.id}"
                ),
                icon_url=ctx.author.avatar_url,
            )
            try:
                await self.bot.get_channel(655093734525894666).send(embed=embed)
            except discord.HTTPException:
                raise error

        else:
            title = "Unspecified error: please hang tight, whilst I try take a look at this"
            embed = discord.Embed(
                title=f"Ignoring exception in command {ctx.command}",
                description=f"```py\n{discord.utils.escape_markdown(format_error(error))}```",
                colour=discord.Colour.red(),
            )
            embed.set_author(
                name=(
                    f'Command {ctx.command} {f"{ctx.guild.name} - {ctx.guild.id}," if ctx.guild else ""} used by '
                    f"{ctx.author.name} - {ctx.author.id}"
                ),
                icon_url=ctx.author.avatar_url,
            )
            try:
                await self.bot.get_channel(655093734525894666).send(embed=embed)
            except discord.HTTPException:
                raise error

        embed = discord.Embed(title=f":warning: **{title}**", color=discord.Colour.red())
        embed.add_field(name="Error message:", value=f"```py\n{type(error).__name__}: {error}\n```")
        self.bot.log.error("An error", exc_info=error)


def setup(bot):
    bot.add_cog(Listeners(bot))
