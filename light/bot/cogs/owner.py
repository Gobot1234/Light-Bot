from __future__ import annotations

from typing import TYPE_CHECKING, Union

import discord
from discord.ext import commands
from jishaku.codeblocks import Codeblock

from . import Cog, command
from .utils.checks import is_mod
from .utils.context import Context

if TYPE_CHECKING:
    from .. import Config, Light


class Owner(Cog, command_attrs=dict(hidden=True)):
    async def cog_check(self, ctx: Context):
        if await ctx.bot.is_owner(ctx.author):
            return True
        elif ctx.guild:
            return is_mod()
        return False

    @command()
    @commands.is_owner()
    async def blacklist(self, ctx: Context, guild: Union[discord.Guild, discord.Object]) -> None:
        await Config.update_where(f"guild_id={guild.id}", blacklisted=True)
        await ctx.send(f"Blacklisted {guild!r}")
        if hasattr(guild, "leave"):
            await guild.leave()

    async def invoke_jsk_command(self, command_name: str, ctx: Context, *args, **kwargs):
        await self.bot.get_command("jsk").get_command(command_name)(ctx, *args, **kwargs)

    @command(aliases=["logout", "close"])
    @commands.is_owner()
    async def restart(self, ctx: Context) -> None:
        await self.invoke_jsk_command("shutdown", ctx)

    @command(aliases=["e"])
    @commands.is_owner()
    async def eval(self, ctx: Context, *, codeblock: Codeblock) -> None:
        await self.invoke_jsk_command("py", ctx, argument=codeblock)

    @command()
    async def reload(self, ctx: Context):
        # await self.invoke_jsk_command("reload", ctx)
        ...


def setup(bot: Light) -> None:
    bot.add_cog(Owner(bot))
