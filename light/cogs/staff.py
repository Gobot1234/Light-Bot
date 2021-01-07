from __future__ import annotations

import discord
from discord.ext import commands

from . import Cog
from .utils.db import Config
from .utils.formats import human_join
from .utils.context import Context


class Staff(Cog):
    """These commands can only be used by people who already have the discord permissions to do so."""

    @commands.group(invoke_without_subcommand=True, aliases=["prefixes"])
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def prefix(self, ctx: Context):
        """View your current prefixes by just typing {prefix}prefix"""
        if ctx.invoked_subcommand is None:
            embed = discord.Embed(
                title=f"Your current prefixes are",
                description=human_join(
                    tuple(self.bot.config_cache[ctx.guild.id].prefixes) + (self.bot.user.mention,),
                ),
                colour=discord.Colour.blurple(),
            )

            await ctx.send(embed=embed)

    @prefix.command(name="add")
    async def prefix_add(self, ctx: Context, prefix: str):
        """Add a prefix to your server's prefixes"""
        prefixes = self.bot.config_cache[ctx.guild.id].prefixes
        if len(prefixes) >= 10:
            return await ctx.send("You can't add anymore prefixes")
        if prefix in prefixes:
            return await ctx.send("That prefix is already in use")
        if prefix.startswith((self.bot.user.mention, f"<@!{self.bot.user.id}>")):
            return await ctx.send("I'm sorry but you can't use that prefix")

        await Config.insert(prefixes=list(prefixes), guild_id=ctx.guild.id, update_on_conflict=Config.prefixes)
        prefixes.add(prefix)
        await ctx.send(f"Successfully added {prefix} to your prefixes")

    @prefix.command(name="remove")
    async def prefix_remove(self, ctx: Context, prefix: str):
        """Remove a prefix from your server's prefixes"""
        prefixes = self.bot.config_cache[ctx.guild.id].prefixes
        try:
            prefixes.remove(prefix)
        except ValueError:
            return await ctx.send(f"{prefix} isn't in your list of prefixes")

        await Config.insert(prefixes=list(prefixes), guild_id=ctx.guild.id, update_on_conflict=Config.prefixes)
        await ctx.send(f"Successfully removed {prefix} from prefixes")


def setup(bot):
    bot.add_cog(Staff(bot))
