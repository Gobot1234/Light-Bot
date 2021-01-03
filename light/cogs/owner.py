from __future__ import annotations
import importlib
from discord.ext import commands
from typing import TYPE_CHECKING

from .utils.context import Context
from .utils.formats import format_error

from .utils.checks import is_mod
if TYPE_CHECKING:
    from .. import Light


class Owner(commands.Cog, command_attrs={"hidden": True}):
    """These commands can only be used by the owner of the bot, or the guild owner"""

    def __init__(self, bot: Light):
        self.bot = bot
        self.first = True

    async def cog_check(self, ctx):
        if await ctx.bot.is_owner(ctx.author):
            return True
        elif ctx.guild:
            return is_mod()
        return False

    @commands.command(aliases=["logout", "close"])
    @commands.is_owner()
    async def restart(self, ctx: Context) -> None:
        """Used to restart the bot"""
        await ctx.message.add_reaction(ctx.emoji.loading)
        await ctx.send(f"**Restarting the Bot** {ctx.author.mention}")
        await self.bot.close()

    @commands.command(aliases=["ru"])
    @commands.is_owner()
    async def reload_util(self, ctx: Context, name: str) -> None:
        """Reload a Utils module"""
        try:
            module_name = importlib.import_module(f"light.cogs.utils.{name}")
            importlib.reload(module_name)
        except ModuleNotFoundError:
            await ctx.send(f"I couldn't find module named **{name}** in utils.")
        except Exception as e:
            await ctx.send(f"Module **{name}** raised an error and was not reloaded...\n```py\n{format_error(e)}```")
        else:
            await ctx.send(f"Reloaded module **{name}**")


def setup(bot):
    bot.add_cog(Owner(bot))
