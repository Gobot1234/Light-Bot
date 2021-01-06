from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from . import Cog
from .utils.db import Config

if TYPE_CHECKING:
    from .utils.context import Context


class Staff(Cog):
    """These commands can only be used by people who already have the discord permissions to do so."""

    async def cog_check(self, ctx: Context):
        if ctx.guild is None:
            return False
        return (
            ctx.author == ctx.bot.owner
            or ctx.author.guild_permissions.ban_members
            or ctx.author.guild_permissions.kick_members
            or ctx.author.guild_permissions.manage_roles
            or ctx.author.permissions_in(ctx.channel).manage_messages
            or ctx.author.guild_permissions.manage_guild
        )

    @commands.group(invoke_without_subcommand=True, aliases=["prefixes"])
    @commands.has_permissions(manage_guild=True)
    async def prefix(self, ctx):
        """View your current prefixes by just typing {prefix}prefix"""
        if ctx.invoked_subcommand is None:
            prefixes = "\n".join(self.bot.config_cache[ctx.guild.id].prefixes)
            embed = discord.Embed(
                title=f"Your current prefixes for {ctx.guild} are",
                description=f"{prefixes}\n& @{self.bot.user.name}",
                colour=discord.Colour.blurple(),
            )
            embed.set_thumbnail(url=ctx.guild.icon_url)

            await ctx.send(embed=embed)

    @prefix.command(name="add")
    async def prefix_add(self, ctx, prefix: str):
        """Add a prefix to your server's prefixes"""
        if prefix.startswith(f"<@{ctx.me.id}>") or prefix.startswith(f"<@!{ctx.me.id}>"):
            await ctx.send("I'm sorry but you can't use that prefix")
        else:
            prefixes = self.bot.config_cache[ctx.guild.id].prefixes
            if len(prefixes) >= 10:
                return await ctx.send("You can't add anymore prefixes")
            if prefix in prefixes:
                return await ctx.send("That prefix is already in use")
            prefixes.add(prefix)
            await Config.insert(prefixes=prefixes, guild_id=ctx.guild.id)
            await ctx.send(f"Successfully added {prefix} to your prefixes")

    @prefix.command(name="remove")
    async def prefix_remove(self, ctx, prefix: str):
        """Remove a prefix from your server's prefixes"""
        if prefix.startswith((self.bot.user.mention, f"<@!{self.bot.user.id}>")):
            return await ctx.send("I'm sorry but you can't use that prefix")

        prefixes = self.bot.config_cache[ctx.guild.id].prefixes
        try:
            prefixes.remove(prefix)
        except ValueError:
            await ctx.send(f"{prefix} isn't in your list of prefixes")
        else:
            await Config.update_where(prefixes=list(prefixes), guild_id=ctx.guild.id)
            await ctx.send(f"Successfully removed {prefix} from prefixes")


def setup(bot):
    bot.add_cog(Staff(bot))
