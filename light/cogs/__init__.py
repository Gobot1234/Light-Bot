from discord.ext import commands

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .. import Light


class Cog(commands.Cog):
    def __init__(self, bot: Light):
        self.bot = bot
