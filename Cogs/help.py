from asyncio import TimeoutError
from psutil import virtual_memory, cpu_percent, Process
from humanize import naturalsize
from platform import python_version
from datetime import datetime

# import asyncpg
import discord
from discord.ext import commands, tasks

from Cogs.owner import Owner
from Utils.checks import prefix


class HelpCommand(commands.HelpCommand):
    """The custom help command class for the bot"""

    def __init__(self):
        super().__init__(command_attrs={
            'help': 'Shows help about the bot, a command, or a cog',
            'cooldown': commands.Cooldown(1, 3.0, commands.BucketType.member),
        })

    def get_command_signature(self, command):
        """Method to return a commands name and signature"""
        if not command.signature and not command.parent:  # checking if it has no args and isn't a subcommand
            return f'`{self.clean_prefix}{command.name}`'
        if command.signature and not command.parent:  # checking if it has args and isn't a subcommand
            return f'`{self.clean_prefix}{command.name}` `{command.signature}`'
        if not command.signature and command.parent:  # checking if it has no args and is a subcommand
            return f'`{command.name}`'
        else:  # else assume it has args a signature and is a subcommand
            return f'`{command.name}` `{command.signature}`'

    def get_command_aliases(self, command):  # this is a custom written method along with all the others below this
        """Method to return a commands aliases"""
        if not command.aliases:  # check if it has any aliases
            return ''
        else:
            return f'command aliases are [`{"` | `".join([alias for alias in command.aliases])}`]'

    def get_command_description(self, command):
        """Method to return a commands short doc/brief"""
        if not command.short_doc:  # check if it has any brief
            return 'There is no documentation for this command currently'
        else:
            return command.short_doc.format(prefix=self.clean_prefix)

    def get_command_help(self, command):
        """Method to return a commands full description/doc string"""
        if not command.help:  # check if it has any brief or doc string
            return 'There is no documentation for this command currently'
        else:
            return command.help.format(prefix=self.clean_prefix)

    async def send_bot_help(self, mapping):
        ctx = self.context
        bot = ctx.bot
        page = 0
        cogs = [name for name, obj in bot.cogs.items() if await obj.cog_check(ctx)]  # get all of your cogs
        cogs.sort()

        def check(reaction, user):  # check who is reacting to the message
            return user == ctx.author
        embed = await self.bot_help_paginator(page, cogs)
        help_embed = await ctx.send(embed=embed)  # sends the first help page

        reactions = ('\N{BLACK LEFT-POINTING DOUBLE TRIANGLE WITH VERTICAL BAR}',
                     '\N{BLACK LEFT-POINTING TRIANGLE}',
                     '\N{BLACK RIGHT-POINTING TRIANGLE}',
                     '\N{BLACK RIGHT-POINTING DOUBLE TRIANGLE WITH VERTICAL BAR}',
                     '\N{BLACK SQUARE FOR STOP}',
                     '\N{INFORMATION SOURCE}')  # add reactions to the message
        bot.loop.create_task(self.bot_help_paginator_reactor(help_embed, reactions))
        # this allows the bot to carry on setting up the help command

        while 1:
            try:
                reaction, user = await bot.wait_for('reaction_add', timeout=60, check=check)  # checks message reactions
            except TimeoutError:  # session has timed out
                try:
                    await help_embed.clear_reactions()
                except discord.errors.Forbidden:
                    pass
                break
            else:
                try:
                    await help_embed.remove_reaction(str(reaction.emoji), ctx.author)  # remove the reaction
                except discord.errors.Forbidden:
                    pass

                if str(reaction.emoji) == '⏭':  # go to the last the page
                    page = len(cogs) - 1
                    embed = await self.bot_help_paginator(page, cogs)
                    await help_embed.edit(embed=embed)
                elif str(reaction.emoji) == '⏮':  # go to the first page
                    page = 0
                    embed = await self.bot_help_paginator(page, cogs)
                    await help_embed.edit(embed=embed)

                elif str(reaction.emoji) == '◀':  # go to the previous page
                    page -= 1
                    if page == -1:  # check whether to go to the final page
                        page = len(cogs) - 1
                    embed = await self.bot_help_paginator(page, cogs)
                    await help_embed.edit(embed=embed)
                elif str(reaction.emoji) == '▶':  # go to the next page
                    page += 1
                    if page == len(cogs):  # check whether to go to the first page
                        page = 0
                    embed = await self.bot_help_paginator(page, cogs)
                    await help_embed.edit(embed=embed)

                elif str(reaction.emoji) == 'ℹ':  # show information help
                    all_cogs = '`, `'.join([cog for cog in cogs])
                    embed = discord.Embed(title=f'Help with {bot.user.name}\'s commands', description=bot.description,
                                          color=discord.Colour.purple())
                    embed.add_field(
                        name=f'Currently there are {len(cogs)} cogs loaded, which includes (`{all_cogs}`) :gear:',
                        value='`<...>` indicates a required argument,\n`[...]` indicates an optional argument.\n\n'
                              '**Don\'t however type these around your argument**')
                    embed.add_field(name='What do the emojis do:',
                                    value=':track_previous: Goes to the first page\n'
                                          ':track_next: Goes to the last page\n'
                                          ':arrow_backward: Goes to the previous page\n'
                                          ':arrow_forward: Goes to the next page\n'
                                          ':stop_button: Deletes and closes this message\n'
                                          ':information_source: Shows this message')
                    embed.set_author(name=f'You were on page {page + 1}/{len(cogs)} before',
                                     icon_url=ctx.author.avatar_url)
                    embed.set_footer(text=f'Use "{self.clean_prefix}help <command>" for more info on a command.',
                                     icon_url=ctx.bot.user.avatar_url)
                    await help_embed.edit(embed=embed)

                elif str(reaction.emoji) == '⏹':  # delete the message and break from the wait_for
                    await help_embed.delete()
                    break

    async def bot_help_paginator_reactor(self, message, reactions):
        for reaction in reactions:
            await message.add_reaction(reaction)

    async def bot_help_paginator(self, page: int, cogs):
        ctx = self.context
        bot = ctx.bot
        all_commands = [command for command in await self.filter_commands(bot.commands)]  # filter the commands the user can use
        cog = bot.get_cog(cogs[page])  # get the current cog

        embed = discord.Embed(title=f'Help with {cog.qualified_name} ({len(all_commands)} commands)',
                              description=cog.description, color=discord.Colour.blurple())
        embed.set_author(name=f'We are currently on page {page + 1}/{len(cogs)}', icon_url=ctx.author.avatar_url)
        for c in cog.walk_commands():
            if await c.can_run(ctx) and not c.hidden:
                signature = self.get_command_signature(c)
                description = self.get_command_description(c)
                if c.parent:  # it is a sub-command
                    embed.add_field(name=f'**╚╡**{signature}', value=description)
                else:
                    embed.add_field(name=signature, value=description, inline=False)
        embed.set_footer(text=f'Use "{self.clean_prefix}help <command>" for more info on a command.',
                         icon_url=ctx.bot.user.avatar_url)
        return embed

    async def send_cog_help(self, cog):
        ctx = self.context
        cog_commands = [command for command in await self.filter_commands(cog.walk_commands())]  # get commands

        embed = discord.Embed(title=f'Help with {cog.qualified_name} ({len(cog_commands)} commands)',
                              description=cog.description, color=discord.Colour.blurple())
        embed.set_author(name=f'We are currently looking at the module {cog.qualified_name} and its commands',
                         icon_url=ctx.author.avatar_url)
        for c in cog_commands:
            signature = self.get_command_signature(c)
            aliases = self.get_command_aliases(c)
            description = self.get_command_description(c)
            if c.parent:
                embed.add_field(name=f'`╚╡`{signature}', value=description)
            else:
                embed.add_field(name=f'{signature} {aliases}',
                                value=description, inline=False)
        embed.set_footer(text=f'Use "{self.clean_prefix}help <command>" for more info on a command.',
                         icon_url=ctx.bot.user.avatar_url)
        await ctx.send(embed=embed)

    async def send_command_help(self, command):
        ctx = self.context

        if await command.can_run(ctx):
            embed = discord.Embed(title=f'Help with `{command.name}`', color=discord.Colour.blurple())
            embed.set_author(
                name=f'We are currently looking at the {command.cog.qualified_name} cog and its command {command.name}',
                icon_url=ctx.author.avatar_url)
            signature = self.get_command_signature(command)
            description = self.get_command_help(command)
            aliases = self.get_command_aliases(command)

            if command.parent:
                embed.add_field(name=f'`╚╡`{signature}', value=description, inline=False)
            else:
                embed.add_field(name=f'{signature} {aliases}', value=description, inline=False)
            embed.set_footer(text=f'Use "{self.clean_prefix}help <command>" for more info on a command.')
            await ctx.send(embed=embed)

    async def send_group_help(self, group):
        ctx = self.context
        bot = ctx.bot

        embed = discord.Embed(title=f'Help with `{group.name}`', description=bot.get_command(group.name).help,
                              color=discord.Colour.blurple())
        embed.set_author(
            name=f'We are currently looking at the {group.cog.qualified_name} cog and its command {group.name}',
            icon_url=ctx.author.avatar_url)
        for command in group.walk_commands():
            if await command.can_run(ctx):
                signature = self.get_command_signature(command)
                description = self.get_command_description(command)
                aliases = self.get_command_aliases(command)

                if command.parent:
                    embed.add_field(name=f'`╚╡`{signature}', value=description, inline=False)
                else:
                    embed.add_field(name=f'{signature} {aliases}', value=description, inline=False)
        embed.set_footer(text=f'Use "{self.clean_prefix}help <command>" for more info on a command.')
        await ctx.send(embed=embed)

    async def send_error_message(self, error):
        pass

    async def command_not_found(self, string):
        embed = discord.Embed(title='Error!',
                              description=f'**Error 404:** Command or cog "{string}" not found ¯\_(ツ)_/¯',
                              color=discord.Colour.red())
        embed.add_field(name='The current loaded cogs are',
                        value=f'(`{"`, `".join([cog for cog in self.context.bot.cogs])}`) :gear:')
        await self.context.send(embed=embed)


class Help(commands.Cog):
    """Need help? Try these with `!help <command>`"""

    def __init__(self, bot):
        self.process = Process()
        self.bot = bot
        self._original_help_command = bot.help_command
        bot.help_command = HelpCommand()
        bot.help_command.cog = self

    def cog_unload(self):
        self.bot.help_command = self._original_help_command

    async def cog_check(self, ctx):
        return True

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

    @commands.group()
    @commands.has_permissions(administrator=True)
    async def prefix(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send(f'Your current prefix is `{self.bot.prefixes[ctx.guild.id]}`')

    @prefix.command()
    async def add(self, ctx, prefix):
        if prefix.startswith(f'<@{self.bot.user.id}>') or prefix.startswith(f'<@!{self.bot.user.id}>'):
            await ctx.send('I\'m sorry but you can\'t use that prefix')
        else:
            # add to db
            # add to cached dict
            await ctx.send(f'Prefix successfully changed to `{prefix}`')

    @prefix.command()
    async def remove(self, ctx, prefix):
        if prefix.startswith(f'<@{self.bot.user.id}>') or prefix.startswith(f'<@!{self.bot.user.id}>'):
            await ctx.send('I\'m sorry but you can\'t use that prefix')
        else:
            # add to db
            # add to cached dict
            await ctx.send(f'Prefix successfully changed to `{prefix}`')


def setup(bot):
    bot.add_cog(Help(bot))
