from datetime import datetime
from psutil import Process, virtual_memory, cpu_percent
from humanize import naturalsize
from platform import python_version

import discord
from discord.ext import commands

from Utils.checks import prefix


class User(commands.Cog):
    """Everyone by default has access to these commands"""

    def __init__(self, bot):
        self.bot = bot
        self.process = Process()

    async def get_uptime(self):
        delta_uptime = datetime.utcnow() - self.bot.launch_time
        hours, remainder = divmod(int(delta_uptime.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        days, hours = divmod(hours, 24)
        return f'`{days}d, {hours}h, {minutes}m, {seconds}s`'

    @commands.command(aliases=['about', 'stats', 'status'])
    @commands.cooldown(rate=1, per=10, type=commands.BucketType.user)
    async def info(self, ctx):
        """Get some info and stats about the bot"""
        uptime = await self.get_uptime()
        memory_usage = self.process.memory_full_info().uss
        rawram = virtual_memory()
        embed = discord.Embed(title=f'**{self.bot.user.name}** - System information',
                              description=f'Commands loaded & Cogs loaded: `{len(self.bot.commands)}` commands loaded, '
                                          f'`{len(self.bot.cogs)}` cogs loaded :gear:', colour=discord.Colour.blurple())
        embed.add_field(name="<:compram:622622385182474254> RAM Usage",
                        value=f'Using `{naturalsize(rawram[3])}` / `{naturalsize(rawram[0])}` `{round(rawram[3] / rawram[0] * 100, 2)}`% '
                              f'of your physical memory and `{naturalsize(memory_usage)}` of which unique to this process.')
        embed.add_field(name="<:cpu:622621524418887680> CPU Usage", value=f'`{cpu_percent()}`% used')
        embed.add_field(name=f'{self.bot.user.name} has been online for:', value=uptime)
        embed.add_field(name=':exclamation:Command prefix',
                        value=f'Your command prefix is `{prefix(ctx)}`. Type {prefix(ctx)}help to list the '
                              f'commands you can use')
        embed.add_field(name='<:dpy:622794044547792926> Discord.py Version',
                        value=f'`{discord.__version__}` works with versions 1.1+ of Discord.py and versions 3.5.4+ of Python')
        embed.add_field(name='<:python:622621989474926622> Python Version',
                        value=f'`{python_version()}` works with versions 3.6+ (uses f-strings)')
        embed.set_footer(text="If you need any help join the help server of this code discord.gg",
                         icon_url='https://cdn.discordapp.com/avatars/340869611903909888/9e3719ecc71ebfb3612ceccf02da4c7a.webp?size=1024')
        await ctx.send(embed=embed)

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def prefix(self, ctx, *, prefix=None):
        if prefix is None:
            await ctx.send(f'Your current prefix is `{self.bot.prefixes[ctx.author.id]}`')
        elif prefix == f'<@{self.bot.user.id}>' or prefix == f'<@!{self.bot.user.id}>':
            await ctx.send('I\'m sorry but you can\'t use that prefix')
        else:
            # add to db
            # add to cached dict
            await ctx.send(f'Prefix successfully changed to `{prefix}`')


def setup(bot):
    bot.add_cog(User(bot))
