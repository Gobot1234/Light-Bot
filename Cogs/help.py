from asyncio import TimeoutError
import asyncio
import json
import os
import random
import re
from datetime import datetime

# import asyncpg

import discord
from discord.ext import commands, tasks

from Cogs.owner import Owner


class HelpCommand(commands.HelpCommand):
    """The custom help command class for the bot"""

    def __init__(self):
        super().__init__(command_attrs={
            'help': 'Shows help about the bot, a command, or a cog'
        })

    def get_command_signature(self, command):
        if len(command.signature) == 0:
            return f'`{self.clean_prefix}{command.name}`'
        else:
            return f'`{self.clean_prefix}{command.name}` `{command.signature}`'

    def get_command_aliases(self, command):
        if len(command.aliases) == 0:
            return ''
        else:
            return f'command aliases are [`{"`, `".join([alias for alias in command.aliases])}`]'

    def get_command_description(self, command):
        if len(command.short_doc) == 0:
            return 'There is no documentation for this command currently'
        else:
            return command.short_doc

    def get_full_command_description(self, command):
        if len(command.help) == 0:
            return 'There is no documentation for this command currently'
        else:
            return command.help

    async def command_callback(self, ctx, *, command=None):
        Owner.__doc__ = """These commands can only be used by the owner of the bot (<@{}>), or {}""".format(
            ctx.bot.owner_id, ctx.guild.owner.mention)
        await self.prepare_help_command(ctx, command)

        if command is None:
            mapping = self.get_bot_mapping()
            return await self.send_bot_help(mapping)

        # Check if it's a cog
        cog = ctx.bot.get_cog(command.title())
        if cog is not None:
            return await self.send_cog_help(cog)

        maybe_coro = discord.utils.maybe_coroutine

        # If it's not a cog then it's a command.
        # Since we want to have detailed errors when someone
        # passes an invalid subcommand, we need to walk through
        # the command group chain ourselves.
        keys = command.split(' ')
        cmd = ctx.bot.all_commands.get(keys[0])
        if cmd is None:
            string = await maybe_coro(self.command_not_found, self.remove_mentions(keys[0]))
            return await self.send_error_message(string)

        for key in keys[1:]:
            try:
                found = cmd.all_commands.get(key)
            except AttributeError:
                string = await maybe_coro(self.subcommand_not_found, cmd, self.remove_mentions(key))
                return await self.send_error_message(string)
            else:
                if found is None:
                    string = await maybe_coro(self.subcommand_not_found, cmd, self.remove_mentions(key))
                    return await self.send_error_message(string)
                cmd = found

        if isinstance(cmd, commands.Group):
            return await self.send_group_help(cmd)
        else:
            return await self.send_command_help(cmd)

    async def bot_help_paginator(self, page: int):
        ctx = self.context
        bot = ctx.bot

        all_commands = [command.name for command in await self.filter_commands(bot.commands)]
        current_cog = bot.get_cog(self.all_cogs[page])
        cog_n = current_cog.qualified_name

        embed = discord.Embed(title=f'Help with {cog_n} ({len(all_commands)} commands)',
                              description=current_cog.description, color=discord.Colour.purple())
        embed.set_author(name=f'We are currently on page {page + 1}/{len(self.all_cogs)}',
                         icon_url=ctx.author.avatar_url)
        for c in current_cog.walk_commands():
            if await c.can_run(ctx) and c.hidden is False:
                signature = self.get_command_signature(c)
                description = self.get_command_description(c)
                if c.parent:
                    embed.add_field(name=f'╚╡**`{signature[2:]}**', value=description, inline=True)
                else:
                    embed.add_field(name=signature, value=description, inline=False)
        embed.set_footer(text=f'Use "{self.clean_prefix}help <command>" for more info on a command.')
        return embed

    async def send_bot_help(self, mapping):
        ctx = self.context
        bot = ctx.bot
        page = 0
        self.all_cogs = [cog for cog in bot.cogs]
        self.all_cogs.sort()

        def check(reaction, user):
            return user == ctx.author

        embed = await self.bot_help_paginator(page)
        help_embed = await ctx.send(embed=embed)

        await help_embed.add_reaction('\U000023ee')
        await help_embed.add_reaction('\U000025c0')
        await help_embed.add_reaction('\U000023f9')
        await help_embed.add_reaction('\U000025b6')
        await help_embed.add_reaction('\U000023ed')
        await help_embed.add_reaction('\U00002139')

        while 1:
            try:
                reaction, user = await bot.wait_for('reaction_add', timeout=30, check=check)
            except TimeoutError:
                try:
                    await help_embed.clear_reactions()
                except discord.errors.Forbidden:
                    pass
                break
            else:
                try:
                    await help_embed.remove_reaction(str(reaction.emoji), ctx.author)
                except discord.errors.Forbidden:
                    pass
                if str(reaction.emoji) == '⏭':
                    page = len(self.all_cogs) - 1
                    embed = await self.bot_help_paginator(page)
                    await help_embed.edit(embed=embed)
                elif str(reaction.emoji) == '⏮':
                    page = 0
                    embed = await self.bot_help_paginator(page)
                    await help_embed.edit(embed=embed)

                elif str(reaction.emoji) == '◀':
                    page -= 1
                    if page == -1:
                        page = len(self.all_cogs) - 1
                    embed = await self.bot_help_paginator(page)
                    await help_embed.edit(embed=embed)
                elif str(reaction.emoji) == '▶':
                    page += 1
                    if page == len(self.all_cogs):
                        page = 0
                    embed = await self.bot_help_paginator(page)
                    await help_embed.edit(embed=embed)

                elif str(reaction.emoji) == 'ℹ':
                    all_cogs = '`, `'.join([cog for cog in self.all_cogs])
                    embed = discord.Embed(title=f'Help with {bot.user.name}\'s commands', description=bot.description,
                                          color=discord.Colour.purple())
                    embed.add_field(
                        name=f'Currently you have {len([cog for cog in self.all_cogs])} cogs loaded, which are (`{all_cogs}`) :gear:',
                        value='`<...>` indicates a required argument,\n`[...]` indicates an optional argument.\n\n'
                              '**Don\'t however type these around your argument**')
                    embed.add_field(name='What do the emojis do:',
                                    value=':track_previous: Goes to the first page\n'
                                          ':track_next: Goes to the last page\n'
                                          ':arrow_backward: Goes to the previous page\n'
                                          ':arrow_forward: Goes to the next page\n'
                                          ':stop_button: Deletes and closes this message\n'
                                          ':information_source: Shows this message')
                    embed.set_author(name=f'You were on page {page + 1}/{len(self.all_cogs)} before',
                                     icon_url=ctx.author.avatar_url)

                    embed.set_footer(text=f'Use "{self.clean_prefix}help <command>" for more info on a command.')
                    await help_embed.edit(embed=embed)

                elif str(reaction.emoji) == '⏹':
                    await help_embed.delete()
                    break

    async def send_cog_help(self, cog):
        ctx = self.context
        bot = ctx.bot

        cog_commands = [command for command in await self.filter_commands(cog.walk_commands())]

        embed = discord.Embed(title=f'Help with {cog.qualified_name} ({len(cog_commands)} commands)',
                              description=cog.description, color=discord.Colour.purple())
        embed.set_author(name=f'We are currently looking at the module {cog.qualified_name} and its commands',
                         icon_url=ctx.author.avatar_url)
        _commands = [c for c in cog_commands if await c.can_run(ctx) and c.hidden is False]
        for c in _commands:
            signature = self.get_command_signature(c)
            aliases = self.get_command_aliases(c)
            description = self.get_command_description(c)
            if c.parent:
                embed.add_field(name=f'╚╡**`{signature[2:]}**', value=description, inline=True)
            else:
                embed.add_field(name=f'{signature} {aliases}',
                                value=description, inline=False)
        embed.set_footer(text=f'Use "{self.clean_prefix}help <command>" for more info on a command.')
        await ctx.send(embed=embed)

    async def send_command_help(self, command):
        ctx = self.context
        bot = ctx.bot
        
        if await command.can_run(ctx):
            embed = discord.Embed(title=f'Help with `{command.name}`', color=discord.Colour.purple())
            embed.set_author(name=f'We are currently looking at the {command.cog.qualified_name} cog and its command {command.name}',
                             icon_url=ctx.author.avatar_url)
            signature = self.get_command_signature(command)
            description = self.get_full_command_description(command)
            aliases = self.get_command_aliases(command)

            if command.parent:
                embed.add_field(name=f'╚╡**`{signature[2:]}**', value=description, inline=False)
            else:
                embed.add_field(name=f'{signature} {aliases}', value=description, inline=False)
            embed.set_footer(text=f'Use "{self.clean_prefix}help <command>" for more info on a command.')
            await ctx.send(embed=embed)

    async def send_group_help(self, group):
        ctx = self.context
        bot = ctx.bot

        embed = discord.Embed(title=f'Help with `{group.name}`', description=bot.get_command(group.name).help,
                              color=discord.Colour.purple())
        embed.set_author(name=f'We are currently looking at the {group.cog.qualified_name} cog and its command {group.name}',
                         icon_url=ctx.author.avatar_url)
        for command in group.walk_commands():
            if await command.can_run(ctx):
                signature = self.get_command_signature(command)
                description = self.get_command_description(command)
                aliases = self.get_command_aliases(command)

                if command.parent:
                    embed.add_field(name=f'╚╡`{signature[2:]}', value=description, inline=False)
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
    """Need help? Try these"""

    def __init__(self, bot):
        self.bot = bot
        self._original_help_command = bot.help_command
        bot.help_command = HelpCommand()
        bot.help_command.cog = self

    def cog_unload(self):
        self.bot.help_command = self._original_help_command



    '''
    f'for {self.bot.prefix} and someone on their cellular device in school',
    f'for {self.bot.prefix} and hortus',
    f'for {self.bot.prefix} and the Year 7s',
    f'for {self.bot.prefix} and over AGSB',
    f'for {self.bot.prefix} and Mr Gartside\'s grave',
    f'for {self.bot.prefix} and gobog',
    f'for {self.bot.prefix} and the Wright Bot development team',
    f'for {self.bot.prefix} and my £3 million bonus'''



    @tasks.loop(minutes=5)
    async def status(self):
        currents = random.choice([f'over {len(self.bot.guilds)} servers',
                                  f'over {len(self.bot.users)} members',
                                  f'for {self.bot.prefix}help'])
        await self.bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name=currents))

    @status.after_loop
    async def afterstatus(self):
        if self.status.failed():
            import traceback
            exc = self.status.exception()
            traceback.print_exception(type(exc), exc, exc.__traceback__)

    '''@tasks.loop(seconds=5)
    async def reminders(self):
        reminders = json.loads(open('Login/reminders.json').read())
        dateNow = str(datetime.now())[:-10]
        for member in reminders:
            for reminder in member:
                if reminder[member].get('date') == dateNow:
                    print(reminders[member])'''

    @commands.Cog.listener()
    async def on_ready(self):
        print(
            f'\n\nLogged in as: {self.bot.user.name} - {self.bot.user.id}\nVersion: {discord.__version__} of Discord.py\n')
        try:
            '''Checks if the bot was restarted using commands and sends a message to the channel not generally 
            recommended but ¯\_(ツ)_/¯ 
            tldr; don't use =restart often
            '''
            channel = int(open('channel.txt', 'r').read())
            await self.bot.get_channel(channel).purge(limit=2)
            await self.bot.get_channel(channel).send('Finished restarting...', delete_after=5)
            os.remove('channel.txt')
        except:
            pass
        print(self.bot.user.name, 'is fully loaded\nSuccessfully logged in and booted...!')

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        # load db check if they have a voice role get its name or change perms
        try:
            if not before.channel and after.channel:
                role = discord.utils.get(member.guild.roles, name='Voice')
                await member.add_roles(role)
            elif before.channel and not after.channel:
                role = discord.utils.get(member.guild.roles, name='Voice')
                await member.remove_roles(role)
        except:
            pass

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        # ask the owner what features they want
        # load db get all members
        embed = discord.Embed(title=':white_check_mark: Server added!',
                              description='Thank you for adding me to your server!', color=discord.Colour.green())
        embed.set_footer(text=f'Joined at: {str(datetime.now())[:-7]}')
        await guild.owner.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_leave(self, guild):
        pass
        # delete the column with the matching guild.id

    @commands.Cog.listener()
    async def on_member_join(self, member):  # check if a member joined before
        # check if they want autoroling after leaving
        """{member} - The user calling the command. Eg: Hello {user}!
        {server} - The server name
        {@member} - Mentions the user
        """
        guild_id = str(member.guild.id)
        m_id = str(member.id)

        guild_settings = json.loads(open('guild_settings.json', 'r').read())[guild_id]
        if m_id in guild_settings['banned users']:
            return await member.kick()

        if guild_settings['welcome message']:
            welcome_msg = guild_settings['welcome message'].replace('@member', 'm_member')
            f_welcome_msg = welcome_msg.format(member=member.name,
                                               server=member.guild.name,
                                               m_member=member.mention)
            await member.send(f_welcome_msg)
        role_list = guild_settings['member role list'][m_id]

        if m_id in role_list:  # add back their old roles if there are any in the users.json
            reason = f'Adding back old roles as requested by {member.guild.owner}'
            role_list = role_list[m_id]
            for role in role_list:
                await member.add_roles(discord.utils.get(member.guild.roles, name=role), reason=reason)
                await asyncio.sleep(5)
        elif guild_settings['auto roling']:
            role = guild_settings['auto_roling']
            reason = f'Autoroled as requested by {member.guild.owner}'
            await member.add_roles(discord.utils.get(member.guild.roles, name=role), reason=reason)

    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):
        embed = discord.Embed(title=str(user),
                              description=f'{user.name} - {user.id} was banned from {guild.name} - {guild.id}',
                              color=discord.Color.red())
        embed.set_footer(text=str(datetime.now())[:-7], icon_url=user.avatar_url)
        await guild.system_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_kick(self, guild, user):
        embed = discord.Embed(title=str(user),
                              description=f'{user.name}-{user.id} was kicked from {guild.name}-{guild.id}',
                              color=discord.Color.red())
        embed.set_footer(text=str(datetime.now())[:-7], icon_url=user.avatar_url)
        await guild.system_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        embed = discord.Embed(title='Member left',
                              description=f'{member} just left {member.guild.name}',
                              color=discord.Color.red())
        embed.set_footer(text=str(datetime.now())[:-7])
        await member.guild.system_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if message.author.bot:
            return
        embed = discord.Embed(title=str(message.author),
                              description=f'**Message by {message.author.mention} deleted in {message.channel.mention}**',
                              color=discord.Color.red())
        embed.add_field(name='Message content:', value=message.content)
        embed.set_footer(text=str(datetime.now())[:-7], icon_url=message.author.avatar_url)
        await message.guild.system_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        embed = discord.Embed(title=str(channel),
                              description=f'{channel.mention} - {channel.id} was just created',
                              color=discord.Color.green())
        embed.set_footer(text=str(datetime.now())[-7])
        await channel.guild.system_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        embed = discord.Embed(title=str(channel),
                              description=f'{channel} - {channel.id} was just deleted',
                              color=discord.Color.red())
        embed.set_footer(text=str(datetime.now())[:-7])
        await channel.guild.system_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_role_create(self, role):
        embed = discord.Embed(title='Role created', description=f'New role {role.mention} created',
                              color=discord.Color.green())
        embed.set_footer(text=str(datetime.now())[:-7])
        await role.guild.system_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        embed = discord.Embed(title='Role deleted', description=f'Role `@{str(role)}` deleted',
                              color=discord.Color.green())
        embed.set_footer(text=str(datetime.now())[:-7])
        await role.guild.system_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        gain = [role for role in after.roles if role not in before.roles]
        lost = [role for role in before.roles if role not in after.roles]
        if before.display_name != after.display_name:
            title = f'{before.name}\'s nickname was changed'
            description = f'Before it was `{before.display_name}`, now it is `{after.display_name}`'
        elif lost:
            title = f'User {before.name}'
            description = f'Lost the role {", ".join([role.mention for role in lost])}'
        elif gain:
            title = f'User {before.name}'
            description = f'Gained the role {", ".join([role.mention for role in gain])}'
        else:
            return
        embed = discord.Embed(title=title, description=description, color=discord.Color.green())
        embed.set_footer(text=str(datetime.now())[:-7], icon_url=before.author.avatar_url)
        await before.guild.system_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_role_update(self, before, after):
        old = [perm for perm in before.permissions if perm not in after.permissions]
        if before.name != after.name:
            embed = discord.Embed(title=f'Role name for {before.name} changed',
                                  description=f'Before it was `{before.name}`, now it is `{after.name}`',
                                  color=discord.Colour.blurple())
        elif old:

            if old[0][1]:
                embed = discord.Embed(title=f'Permissions updated for {after.name}',
                                      description=f'Lost permission(s) `{"`, `".join([perm[0].title() for perm in old])}`',
                                      color=discord.Color.red())
            else:
                embed = discord.Embed(title=f'Permissions updated for {after.name}',
                                      description=f'Gained permission(s) `{"`, `".join([perm[0].title() for perm in old])}`',
                                      color=discord.Color.green())
        else:
            return
        await before.guild.system_channel.send(content=old, embed=embed)

        '''
    @commands.Cog.listener()
    async def on_message(self, message):  # checking if someone someone said a blacklisted word
        if message.author == self.bot.user:
            return
        blacklist_words = message.guild.id['blacklist words']
        if blacklist_words:
            split_message = re.split("(?:(?:[^a-zA-Z]+')|(?:'[^a-zA-Z]+))|(?:[^a-zA-Z']+)",
                                     str(message.content).lower())
            if any(elem in split_message for elem in blacklist_words):
                await message.delete()
                await message.author.send(f'{message.author.mention} Your message "{message.content}" '
                                          f'has been removed as it contains a blacklisted word!',
                                          delete_after=5)
                await message.guild.system_channel.send(f'{message.author}, just said {message.content}, '
                                                        f'in {str(message.channel)}')'''


def setup(bot):
    bot.add_cog(Help(bot))
