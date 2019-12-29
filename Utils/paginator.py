from discord.ext import commands


class Paginator(commands.Context):

    @property
    def uptime(self):
        return 'Uptime'