import difflib
import asyncio
from collections import Counter
from datetime import datetime, timedelta, timezone
from io import BytesIO
from itertools import islice
from platform import python_version
from re import split
from time import perf_counter

import asyncpg
import discord
import matplotlib.pyplot as plt
import pygit2
from discord.ext import commands
from humanize import naturalsize
from matplotlib.figure import figaspect
from psutil import virtual_memory, cpu_percent, Process

from Utils.formats import human_join
from Utils.time import human_timedelta
from Utils.converters import GuildConverter, get_colour


class HelpCommand(commands.HelpCommand):
    """The custom help command class for the bot"""

    def __init__(self):
        super().__init__(verify_checks=True, command_attrs={
            'help': 'Shows help about the bot, a command, or a cog',
            'cooldown': commands.Cooldown(1, 3.0, commands.BucketType.member),
        })

    def get_command_signature(self, command) -> str:
        """Method to return a commands name and signature"""
        if not command.signature and not command.parent:  # checking if it has no args and isn't a subcommand
            return f'`{self.clean_prefix}{command.name}`'
        if command.signature and not command.parent:  # checking if it has args and isn't a subcommand
            sig = '` `'.join(split(r'\B ', command.signature))
            return f'`{self.clean_prefix}{command.name}` `{sig}`'
        if not command.signature and command.parent:  # checking if it has no args and is a subcommand
            return f'`{command.name}`'
        else:  # else assume it has args a signature and is a subcommand
            return '`{}` `{}`'.format(command.name, '`, `'.join(split(r'\B ', command.signature)))

    def get_command_aliases(self, command) -> str:
        """Method to return a commands aliases"""
        if not command.aliases:  # check if it has any aliases
            return ''
        else:
            return f'command aliases are [`{"` | `".join(command.aliases)}`]'

    def get_command_description(self, command) -> str:
        """Method to return a commands short doc/brief"""
        if not command.short_doc:  # check if it has any brief
            return 'There is no documentation for this command currently'
        else:
            return command.short_doc.format(prefix=self.clean_prefix)

    def get_command_help(self, command) -> str:
        """Method to return a commands full description/doc string"""
        if not command.help:  # check if it has any brief or doc string
            return 'There is currently no documentation for this command'
        else:
            return command.help.format(prefix=self.clean_prefix)

    async def send_bot_help(self, mapping):
        ctx = self.context
        bot = ctx.bot
        page = 0
        cogs = [name for name, obj in bot.cogs.items() if await discord.utils.maybe_coroutine(obj.cog_check, ctx)
                and name != 'owner']
        cogs.sort()

        def check(reaction, user):  # check who is reacting to the message
            return user == ctx.author and help_embed.id == reaction.message.id

        embed = await self.bot_help_paginator(page, cogs)

        help_embed = await ctx.send(embed=embed)  # sends the first help page
        bot.loop.create_task(self.bot_help_paginator_reactor(help_embed))
        # this allows the bot to carry on setting up the help command

        while 1:
            try:
                reaction, user = await bot.wait_for('reaction_add', timeout=90, check=check)  # checks message reactions
            except asyncio.TimeoutError:  # session has timed out
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
                    await ctx.send(len(embed))

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
                    embed = discord.Embed(title=f'Help with {bot.user.name}\'s commands', description=bot.description,
                                          color=discord.Colour.blurple())
                    embed.add_field(
                        name=f'Currently there are {len(cogs)} cogs loaded, which includes (`{"`, `".join(cogs)}`) :gear:',
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

    async def bot_help_paginator_reactor(self, message):
        reactions = (
            '\N{BLACK LEFT-POINTING DOUBLE TRIANGLE WITH VERTICAL BAR}',
            '\N{BLACK LEFT-POINTING TRIANGLE}',
            '\N{BLACK RIGHT-POINTING TRIANGLE}',
            '\N{BLACK RIGHT-POINTING DOUBLE TRIANGLE WITH VERTICAL BAR}',
            '\N{BLACK SQUARE FOR STOP}',
            '\N{INFORMATION SOURCE}'
        )  # add reactions to the message
        for reaction in reactions:
            await message.add_reaction(reaction)

    async def bot_help_paginator(self, page: int, cogs) -> discord.Embed:
        ctx = self.context
        bot = ctx.bot
        all_commands = [command for command in
                        await self.filter_commands(bot.commands)]  # filter the commands the user can use
        cog = bot.get_cog(cogs[page])  # get the current cog

        embed = discord.Embed(title=f'Help with {cog.qualified_name} ({len(all_commands)} commands)',
                              description=cog.description,
                              color=bot.config_cache[ctx.guild.id]['colour'] if ctx.guild else discord.Colour.blurple())
        embed.set_author(name=f'We are currently on page {page + 1}/{len(cogs)}', icon_url=ctx.author.avatar_url)
        for c in cog.walk_commands():
            try:
                if await c.can_run(ctx) and not c.hidden:
                    signature = self.get_command_signature(c)
                    description = self.get_command_description(c)
                    if c.parent:  # it is a sub-command
                        embed.add_field(name=f'**╚╡**{signature}', value=description)
                    else:
                        embed.add_field(name=signature, value=description, inline=False)
            except commands.CommandError:
                pass
        embed.set_footer(text=f'Use "{self.clean_prefix}help <command>" for more info on a command.',
                         icon_url=ctx.bot.user.avatar_url)
        return embed

    async def send_cog_help(self, cog):
        ctx = self.context
        cog_commands = [command for command in await self.filter_commands(cog.walk_commands())]  # get commands

        embed = discord.Embed(title=f'Help with {cog.qualified_name} ({len(cog_commands)} commands)',
                              description=cog.description,
                              color=get_colour(ctx))
        embed.set_author(name=f'We are currently looking at the module {cog.qualified_name} and its commands',
                         icon_url=ctx.author.avatar_url)
        for c in cog_commands:
            signature = self.get_command_signature(c)
            aliases = self.get_command_aliases(c)
            description = self.get_command_description(c)
            if c.parent:
                embed.add_field(name=f'**╚╡**{signature}', value=description)
            else:
                embed.add_field(name=f'{signature} {aliases}', value=description, inline=False)
        embed.set_footer(text=f'Use "{self.clean_prefix}help <command>" for more info on a command.',
                         icon_url=ctx.bot.user.avatar_url)
        await ctx.send(embed=embed)

    async def send_command_help(self, command):
        ctx = self.context

        if await command.can_run(ctx):
            embed = discord.Embed(title=f'Help with `{command.name}`', color=get_colour(ctx))
            embed.set_author(
                name=f'We are currently looking at the {command.cog.qualified_name} cog and its command {command.name}',
                icon_url=ctx.author.avatar_url)
            signature = self.get_command_signature(command)
            description = self.get_command_help(command)
            aliases = self.get_command_aliases(command)

            if command.parent:
                embed.add_field(name=f'**╚╡**{signature}', value=description, inline=False)
            else:
                embed.add_field(name=f'{signature} {aliases}', value=description, inline=False)
            embed.set_footer(text=f'Use "{self.clean_prefix}help <command>" for more info on a command.')
            await ctx.send(embed=embed)

    async def send_group_help(self, group):
        ctx = self.context
        bot = ctx.bot

        embed = discord.Embed(title=f'Help with `{group.name}`', description=bot.get_command(group.name).help,
                              color=get_colour(ctx))
        embed.set_author(
            name=f'We are currently looking at the {group.cog.qualified_name} cog and its command {group.name}',
            icon_url=ctx.author.avatar_url)
        for command in group.walk_commands():
            if await command.can_run(ctx):
                signature = self.get_command_signature(command)
                description = self.get_command_description(command)
                aliases = self.get_command_aliases(command)

                if command.parent:
                    embed.add_field(name=f'**╚╡**{signature}', value=description, inline=False)
                else:
                    embed.add_field(name=f'{signature} {aliases}', value=description, inline=False)
        embed.set_footer(text=f'Use "{self.clean_prefix}help <command>" for more info on a command.')
        await ctx.send(embed=embed)

    async def send_error_message(self, error):
        pass

    async def command_not_found(self, string):
        ctx = self.context
        command_names = [command.name for command in ctx.bot.commands]
        close_commands = difflib.get_close_matches(string, command_names, len(command_names), 0)
        joined = "\n".join(f'`{command}`' for command in close_commands[:2])

        embed = discord.Embed(
            title='Error!', description=f'**Error 404:** Command or category "{string}" not found ¯\_(ツ)_/¯\n'
                                        f'Perhaps you meant:\n{joined}',
            color=ctx.bot.config_cache[ctx.guild.id]['colour_bad'] if ctx.guild else discord.Colour.red()
        )
        embed.add_field(name='The current loaded cogs are',
                        value=f'(`{"`, `".join([cog for cog in ctx.bot.cogs])}`) :gear:')
        await self.context.send(embed=embed)


class Help(commands.Cog):
    """Need help? Try these with <@630008145162272778> help <command>"""

    def __init__(self, bot):
        self.process = Process()
        self.bot = bot
        self._original_help_command = bot.help_command
        bot.help_command = HelpCommand()
        bot.help_command.cog = self

    def cog_unload(self):
        self.bot.help_command = self._original_help_command

    def get_uptime(self) -> str:
        delta_uptime = datetime.utcnow() - self.bot.launch_time
        hours, remainder = divmod(int(delta_uptime.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        days, hours = divmod(hours, 24)
        return f'`{days}d, {hours}h, {minutes}m, {seconds}s`'

    def format_commit(self, commit) -> str:
        short, _, _ = commit.message.partition('\n')
        short_sha2 = commit.hex[0:6]
        commit_tz = timezone(timedelta(minutes=commit.commit_time_offset))
        commit_time = datetime.fromtimestamp(commit.commit_time).replace(tzinfo=commit_tz)

        # [`hash`](url) message (offset)
        offset = human_timedelta(commit_time.astimezone(timezone.utc).replace(tzinfo=None), accuracy=1)
        return f'[`{short_sha2}`](https://github.com/Gobot1234/Epic-Bot/commit/{commit.hex}) {short} ({offset})'

    def get_last_commits(self, count=3) -> str:
        repo = pygit2.Repository('.git')
        commits = list(islice(repo.walk(repo.head.target, pygit2.GIT_SORT_TOPOLOGICAL), count))
        return '\n'.join(self.format_commit(c) for c in commits)

    @commands.command()
    async def ping(self, ctx):
        """Check my ping"""
        start = perf_counter()
        await self.bot.session.get('https://discordapp.com')
        end = perf_counter()
        discord_duration = (end - start) * 1000

        start = perf_counter()
        embed = discord.Embed(color=get_colour(ctx)).set_author(name='Pong!')
        m = await ctx.send(embed=embed)
        end = perf_counter()
        message_duration = (end - start) * 1000

        embed.description = f'{self.bot.user.mention} is online.'
        embed.set_author(name='Pong!', icon_url=self.bot.user.avatar_url)
        embed.add_field(name=f':heartbeat: Heartbeat latency is:', value=f'`{self.bot.latency * 1000:.2f}` ms.')
        embed.add_field(name=f'{ctx.emoji.discord} Discord latency is:',
                        value=f'`{discord_duration:.2f}` ms.')
        embed.add_field(name=f'{ctx.emoji.text} Message latency is:',
                        value=f'`{message_duration:.2f}` ms.')

        await m.edit(embed=embed)

    @commands.command(aliases=['info'])
    async def stats(self, ctx):
        # memory_usage = self.process.memory_full_info().uss
        rawram = virtual_memory()
        embed = discord.Embed(title=f'**{self.bot.user.name}** - Official Bot Server Invite & Bot information',
                              description=f'**Commands loaded & Cogs loaded:** '
                                          f'`{len(self.bot.commands)}` commands loaded, '
                                          f'`{len(self.bot.cogs)}` extensions loaded\n\n'
                                          f'**Latest Changes:**\n{self.get_last_commits()}\n',
                              colour=get_colour(ctx),
                              timestamp=datetime.now())
        embed.set_author(name=str(self.bot.owner), icon_url=self.bot.owner.avatar_url)
        embed.set_thumbnail(url=self.bot.user.avatar_url)
        # statistics
        total_bots = 0
        total_members = 0
        total_online = 0
        total_idle = 0
        total_dnd = 0
        total_offline = 0

        online = discord.Status.online
        idle = discord.Status.idle
        dnd = discord.Status.dnd
        offline = discord.Status.offline

        all_members = set(self.bot.get_all_members())
        for member in all_members:
            if member.bot:
                total_bots += 1
                continue
            elif member.status is online:
                total_online += 1
            elif member.status is idle:
                total_idle += 1
            elif member.status is dnd:
                total_dnd += 1
            elif member.status is offline:
                total_offline += 1
            total_members += 1
        total_unique = len(all_members)

        text = 0
        voice = 0
        guilds = 0
        for guild in self.bot.guilds:
            guilds += 1
            for channel in guild.channels:
                if isinstance(channel, discord.TextChannel):
                    text += 1
                elif isinstance(channel, discord.VoiceChannel):
                    voice += 1
        embed.add_field(name='Members', value=f'`{total_members}` {ctx.emoji.discord} total\n'
                                              f'`{total_bots}` :robot: bots\n'
                                              f'`{total_unique}` :star: unique.')
        embed.add_field(name='Statuses',
                        value=f'`{total_online}` {ctx.emoji.discord} online,\n'
                              f'`{total_idle}` {ctx.emoji.idle} idle,\n'
                              f'`{total_dnd}` {ctx.emoji.dnd} dnd,\n'
                              f'`{total_offline}` {ctx.emoji.offline} offline.')
        embed.add_field(name='Servers & Channels',
                        value=f'{guilds} total servers\n{text + voice} total channels\n'
                              f'{text} text channels\n{voice} voice channels')
        # pc info
        embed.add_field(name=f'{ctx.emoji.ram} RAM Usage',
                        value=f'Using `{naturalsize(rawram[3])}` / `{naturalsize(rawram[0])}` `{round(rawram[3] / rawram[0] * 100, 2)}`% ')
        # f'of your physical memory and `{naturalsize(memory_usage)}` of which unique to this process.')
        embed.add_field(name=f'{ctx.emoji.cpu} CPU Usage',
                        value=f'`{cpu_percent()}`% used\n\n'
                              f':arrow_up: Uptime\n {self.bot.user.mention} has been online for: {self.get_uptime()}')
        embed.add_field(name=':exclamation:Command prefix',
                        value=f'Your command prefix is `{ctx.prefix}`. Type {ctx.prefix}help to list the '
                              f'commands you can use')
        embed.add_field(name='Version info:',
                        value=f'{ctx.emoji.dpy}: `{discord.__version__}`, '
                              f'{ctx.emoji.postgres}: `{asyncpg.__version__}`'
                              f'{ctx.emoji.python}: `{python_version()}`',  # TODO add more version info
                        inline=False)
        embed.set_footer(text="If you need any help join the help server discord.gg",
                         icon_url=ctx.author.avatar_url)
        await ctx.send(embed=embed)

    @commands.command()
    async def avatar(self, ctx, member: discord.Member = None):
        """Get a member's avatar with links to download/view in higher quality"""
        member = member or ctx.author
        embed = discord.Embed(
            title=f'{member.display_name}\'s avatar',
            description=f'[PNG]({member.avatar_url_as(format="png")}) | '
                        f'[JPEG]({member.avatar_url_as(format="jpg")}) | '
                        f'[WEBP]({member.avatar_url_as(format="webp")})',
            colour=get_colour(ctx)
        )
        if member.is_avatar_animated():
            embed.description += f' | [GIF]({member.avatar_url_as(format="gif")})'
        embed.set_author(name=member.display_name, icon_url=member.avatar_url)
        embed.set_image(url=member.avatar_url_as(format='gif' if member.is_avatar_animated() else 'png'))
        await ctx.send(embed=embed)

    @commands.command(aliases=['member'])
    async def user(self, ctx, user: discord.Member = None):
        user = user or ctx.author

        voice_perms = [
            'deafen_members',
            'move_members',
            'mute_members',
            'priority_speaker',
            'speak',
            'stream',
            'use_voice_activation',
            'connect'
        ]
        key_to_emoji = {
            "online": '<:online:659012420735467540>',
            "idle": '<:idle:659012420672421888>',
            "dnd": '<:dnd:659012419296952350>',
            "offline": '<:offline:659012420273963008>',
        }

        shared_guilds = [g.name for g in self.bot.guilds if user in g.members]
        perms = [
            f'{ctx.emoji.tick} {perm.title()}' for perm, val in
            sorted(dict(user.permissions_in(ctx.channel)).items()) if val and perm not in voice_perms
        ]
        perms_denied = [
            f'{ctx.emoji.cross} {perm.title()}' for perm, val in
            sorted(dict(user.permissions_in(ctx.channel)).items()) if not val and perm not in voice_perms
        ]
        perms = '\n'.join(perms).replace("_", " ").replace('Tts', 'TTS') if perms else 'None'
        perms_denied = '\n'.join(perms_denied).replace("_", " ").replace('Tts', 'TTS') if perms_denied else 'None'

        embed = discord.Embed(title=f'Info on {user}', colour=user.colour)
        embed.set_author(name=user.display_name, icon_url=user.avatar_url)
        embed.set_thumbnail(url=user.avatar_url)
        embed.add_field(name='ID:', value=user.id)
        embed.add_field(name=f'{user.display_name} created their account:',
                        value=human_timedelta(user.created_at, accuracy=2))
        embed.add_field(name=f'{user.display_name} joined this guild:',
                        value=human_timedelta(user.joined_at, accuracy=2))
        embed.add_field(name='Shared guilds', value=human_join(shared_guilds, final='and')) \
            if user != self.bot.user else embed.add_field(name=f'I am in:', value=f'{len(self.bot.guilds)} servers')

        embed.add_field(
            name=f'{user.display_name} has these permission{"s" if len(perms) != 1 else ""} in this channel:',
            value=perms if 'Administrator' not in perms else 'All as they are Admin')
        embed.add_field(
            name=f'{user.display_name} has these permission{"s" if len(perms) != 1 else ""} denied in this channel:',
            value=perms_denied)
        if user.premium_since:
            embed.add_field(name=f'{user.display_name} has been boosting since:',
                            value=human_timedelta(user.premium_since))

        embed.add_field(
            name=f'Roles ({len(user.roles) - 1})',
            value=human_join(
                [role.mention for role in sorted([role for role in user.roles if role != ctx.guild.default_role],
                                                 reverse=True, key=lambda r: r.position)],
                final='and') if len(user.roles) != 0 else 'None',
            inline=False)
        embed.add_field(name='Status:',
                        value=f'{key_to_emoji[str(user.status)]} '
                              f'{str(user.status).title().replace("Dnd", "Do Not Disturb")}\n'
                              f'Is on mobile: {user.is_on_mobile()}')
        await ctx.send(embed=embed)

    @commands.command(aliases=['guild'])
    async def server(self, ctx, *, server: GuildConverter = None):
        """Get info in the current server"""
        guild = server or ctx.guild

        class Secret:
            pass

        secret_member = Secret()
        secret_member.id = 0
        secret_member.roles = [guild.default_role]

        # figure out what channels are 'secret'
        secret = Counter()
        totals = Counter()
        for channel in guild.channels:
            perms = channel.permissions_for(secret_member)
            channel_type = type(channel)
            totals[channel_type] += 1
            if not perms.read_messages:
                secret[channel_type] += 1
            elif isinstance(channel, discord.VoiceChannel) and (not perms.connect or not perms.speak):
                secret[channel_type] += 1

        member_by_status = Counter(str(m.status) for m in guild.members)

        embed = discord.Embed(title=guild.name, colour=get_colour(ctx))
        embed.add_field(name='ID', value=guild.id)
        embed.add_field(name='Owner', value=guild.owner)

        if guild.icon:
            embed.set_thumbnail(url=guild.icon_url)

        channel_info = []
        key_to_emoji = {
            discord.TextChannel: ctx.emoji.text,
            discord.VoiceChannel: ctx.emoji.voice
        }
        for key, total in totals.items():
            secrets = secret[key]
            try:
                emoji = key_to_emoji[key]
            except KeyError:
                continue

            if secrets:
                channel_info.append(f'{emoji} {total} ({secrets} locked)')
            else:
                channel_info.append(f'{emoji} {total}')

        info = []
        features = set(guild.features)
        all_features = {
            'PARTNERED': 'Partnered',
            'VERIFIED': 'Verified',
            'DISCOVERABLE': 'Server Discovery',
            'PUBLIC': 'Server Discovery/Public',
            'INVITE_SPLASH': 'Invite Splash',
            'VIP_REGIONS': 'VIP Voice Servers',
            'VANITY_URL': 'Vanity Invite',
            'MORE_EMOJI': 'More Emoji',
            'COMMERCE': 'Commerce',
            'LURKABLE': 'Lurkable',
            'NEWS': 'News Channels',
            'ANIMATED_ICON': 'Animated Icon',
            'BANNER': 'Banner'
        }

        for feature, label in all_features.items():
            if feature in features:
                info.append(f'{label}')

        if info:
            embed.add_field(name='Features:', value='\n'.join(info))

        embed.add_field(name='Channels:', value='\n'.join(channel_info))
        embed.add_field(name='Verification level:', value=str(ctx.guild.verification_level).replace('_', ' ').title())
        embed.add_field(name='Region:', value=str(ctx.guild.region).replace('_', ' ').title())

        if guild.premium_tier != 0:
            boosts = f'Level {guild.premium_tier}\n{guild.premium_subscription_count} boosts'
            last_boost = max(guild.members, key=lambda m: m.premium_since or guild.created_at)
            if last_boost.premium_since is not None:
                boosts = f'{boosts}\nLast Boost: {last_boost} ({human_timedelta(last_boost.premium_since, accuracy=2)})'
            embed.add_field(name='Boosts', value=boosts, inline=False)

        fmt = f'{ctx.emoji.online} {member_by_status["online"]}\n' \
              f'{ctx.emoji.idle} {member_by_status["idle"]}\n' \
              f'{ctx.emoji.dnd} {member_by_status["dnd"]}\n' \
              f'{ctx.emoji.offline} {member_by_status["offline"]}\n' \
              f'Total: {guild.member_count}'

        embed.add_field(name='Members', value=fmt, inline=False)
        embed.add_field(name=f'Roles ({len(guild.roles) - 1})',
                        value=human_join([role.mention for role in sorted(
                            [role for role in guild.roles if role != guild.default_role],
                            reverse=True, key=lambda r: r.position)], final='and')
                        if len(guild.roles) < 10 and guild == ctx.guild else f'{len(guild.roles) - 1} roles')
        await ctx.send(embed=embed)

    def gen_steam_stats_graph(self, data):
        graph_data = data['graph']
        steps = timedelta(milliseconds=graph_data['step'])
        timestamp = datetime.utcfromtimestamp(graph_data['start'] / 1000)
        plots = graph_data['data']
        times = []

        for _ in plots:
            timestamp -= steps
            times.append(timestamp)

        plt.style.use('dark_background')
        w, h = figaspect(1 / 3)
        fig, ax = plt.subplots(figsize=(w, h))
        ax.grid(linestyle='-', linewidth='0.5', color='white')

        plt.setp(plt.plot(list(reversed(times)), plots, linewidth=4), color='#00adee')

        plt.title(f'Steam CM status over the last {human_timedelta(timestamp)[:-4]}', size=20)
        plt.axis([None, None, 0, 100])
        plt.xlabel('Time (Month-Day Hour)', fontsize=20)
        plt.ylabel('Uptime (%)', fontsize=20)

        plt.tight_layout(h_pad=20, w_pad=20)
        buf = BytesIO()
        plt.savefig(buf, format='png', transparent=True)
        buf.seek(0)
        plt.close()
        return discord.File(buf, filename='graph.png')

    @commands.command(aliases=['steamstatus'])
    @commands.cooldown(1, 30, commands.BucketType.user)
    async def steamstats(self, ctx):
        async with ctx.typing():
            r = await self.bot.session.get('https://crowbar.steamstat.us/gravity.json')
            if r.status == 200:
                data = await r.json()
                graph = await self.bot.loop.run_in_executor(None, self.gen_steam_stats_graph, data)

                code_to_city = {
                    "ams": 'Amsterdam',
                    "atl": 'Atlanta',
                    "bom": 'Mumbai',
                    "can": 'Guangzhou',
                    "dxb": 'Dubai',
                    "eat": 'Moses Lake',
                    "fra": 'Frankfurt',
                    "gru": 'Sao Paulo',
                    "hkg": 'Hong Kong',
                    "iad": 'Sterling',
                    "jnb": 'Johannesburg',
                    "lax": 'Los Angeles',
                    "lhr": 'London',
                    "lim": 'Lima',
                    "lux": 'Luxembourg',
                    "maa": 'Chennai',
                    "mad": 'Madrid',
                    "man": 'Manilla',
                    "okc": 'Oklahoma City',
                    "ord": 'Chicago',
                    "par": 'Paris',
                    "scl": 'Santiago',
                    "sea": 'Seattle',
                    "sgp": 'Singapore',
                    "sha": 'Shanghai',
                    "sto": 'Stockholm',
                    "syd": 'Sydney',
                    "tsn": 'Tianjin',
                    "tyo": 'Tokyo',
                    "vie": 'Vienna',
                    'waw': 'Warsaw'
                }
                code_to_game = {
                    "artifact": 'Artifact',
                    "csgo": 'CS-GO',
                    "dota2": 'DOTA 2',
                    "tf2": 'TF2',
                    "underlords": 'Underlords',
                }
                code_to_service = {
                    "cms": 'Steam CMs',
                    "community": 'Community',
                    "store": 'Store',
                    "webapi": 'Web API'
                }
                code_to_gamers = {
                    "ingame": 'In-game',
                    "online": 'Online',
                }

                cities = {code_to_city.get(service[0]): service[2] for service in data['services']
                          if code_to_city.get(service[0])}
                games = {code_to_game.get(service[0]): service[2] for service in data['services']
                         if code_to_game.get(service[0])}
                services = {code_to_service.get(service[0]): service[2] for service in data['services']
                            if code_to_service.get(service[0])}
                gamers = {code_to_gamers.get(service[0]): service[2] for service in data['services']
                          if code_to_gamers.get(service[0])}

                server_info = [
                    f'{ctx.emoji.tick if country[1] == "OK" or float(country[1][:-1]) >= 80 else ctx.emoji.cross} '
                    f'{country[0]} - {country[1] if country[1].split(".")[0].isdigit() else "100.0%"}' for country in
                    sorted(cities.items(), key=lambda kv: (kv[0], kv[1]))
                ]
                game_info = [
                    f'{ctx.emoji.tick if game[1] == "Normal" else ctx.emoji.cross} {game[0]} - {game[1]}'
                    for game in sorted(games.items(), key=lambda kv: (kv[0], kv[1]))
                ]
                service_info = [
                    f'{ctx.emoji.tick if service[1] == "Normal" or service[1].split()[0].split(".")[0].isdigit() else ctx.emoji.cross} ' \
                    f'{service[0]} - {service[1]}'
                    for service in sorted(services.items(), key=lambda kv: (kv[0], kv[1]))
                ]

                gamers = '\n'.join([f'{gamer[0]} - {gamer[1]}' for gamer in
                                    sorted(gamers.items(), key=lambda kv: (kv[0], kv[1]))])
                services = '\n'.join(service_info)
                embed = discord.Embed(colour=0x00adee)
                embed.set_author(
                    name=f'Steam Stats: {"Fully operational" if data["online"] >= 70 else "Potentially unstable"} '
                         f'{"👍" if data["online"] >= 70 else "👎"}',
                    icon_url='https://www.freeiconspng.com/uploads/steam-icon-19.png')

                embed.description = f'{services}\n\n{gamers}'
                first = server_info[:len(server_info) // 2]
                second = server_info[len(server_info) // 2:]
                embed.add_field(name='CMs Servers:', value='\n'.join(first))
                embed.add_field(name='\u200b', value='\n'.join(second))
                embed.add_field(name='Games:', value='\n'.join(game_info))
                embed.set_image(url="attachment://graph.png")
                await ctx.send(embed=embed, file=graph)
            else:
                await ctx.send('Could not fetch Steam stats. Try again later.')


def setup(bot):
    bot.add_cog(Help(bot))
