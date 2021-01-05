from typing import TYPE_CHECKING

from discord.ext import commands

if TYPE_CHECKING:
    from .. import Light


class Cog(commands.Cog):
    def __init__(self, bot: Light):
        self.bot = bot
