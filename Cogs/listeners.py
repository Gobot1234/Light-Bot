import re
from datetime import datetime
from random import choice

import asyncpg
import discord
import unidecode
from discord.ext import commands, tasks

from Utils.converters import get_colour
from Utils.formats import format_error, format_exec


class Listeners(commands.Cog):
    """Listeners for the bot"""

    def __init__(self, bot):
        self.bot = bot
        self.status.start()
        self.bot.blacklist_words = []

    async def cog_check(self, ctx):
        return False

    @tasks.loop(minutes=60)
    async def status(self):
        status = choice([f'over {len(self.bot.guilds)} servers',
                         f'over {len(set(self.bot.get_all_members()))} members',
                         f'for =help'])
        activity = discord.Activity(name=status, type=discord.ActivityType.watching)
        await self.bot.change_presence(activity=activity)

    @status.before_loop
    async def wait_for_ready_status(self):
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        # load db check if they have a voice role get its name or change perms or log it
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
        # TODO ask the owner what features they want
        try:
            blacklisted = await self.bot.db.fetch(
                """
                SELECT blacklisted FROM config
                WHERE guild_id = $1;
                """, guild.id
            )
        except asyncpg.UndefinedColumnError:
            await self.bot.db.execute(
                """
                INSERT INTO config(
                    guild_id, blacklisted,
                    prefixes, colour,
                    colour_bad, colour_good,
                    join_message, logging_channel,
                    logged_events
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                """, guild.id, False, ['='], discord.Colour.blurple().value,
                discord.Colour.red().value, discord.Colour.green().value, None, None, []
            )
            self.bot.config_cache[guild.id] = {
                "blacklisted": False,
                "prefixes": ['='],
                "colour": discord.Colour.blurple(),
                "colour_bad": discord.Colour.red(),
                "colour_good": discord.Colour.green(),
                "join_message": None,
                "logging_channel": None,
                "logged_events": []
            }

        else:
            if blacklisted is True:
                self.bot.log.info(f'Leaving "{guild.name}" - "{guild.id}" as it is a blacklisted guild')
                return await guild.leave()
        embed = discord.Embed(title='<:tick:688829439659737095> Server added!',
                              description='Thank you for adding me to your server!\n'
                                          'Type `=help` to view my commands', color=discord.Colour.green())
        embed.set_footer(text='Joined').timestamp = datetime.now()
        m = None
        for channel in guild.text_channels:
            try:
                m = await channel.send(embed=embed)
            except discord.Forbidden:
                continue
            else:
                return
        if not isinstance(m, discord.Message):
            perms = {
                "view_audit_log": True,
                "manage_roles": True,
                "manage_channels": True,
                "kick_members": True,
                "ban_members": True,
                "change_nickname": True,
                "manage_nicknames": True,
                "send_messages": True,
                "manage_messages": True,
                "embed_links": True,
                "attach_files": True,
                "read_message_history": True,
                "use_external_emojis": True,
                "connect": True,
                "speak": True
            }
            discord_perms = discord.Permissions(**perms)
            pretty_perms = [f'• {perm_name.replace("_", " ").title()}' for perm_name, value in list(perms.items())]
            pretty_perms.insert(0, '**General**\n')
            pretty_perms.insert(8, '\n**Text Channels**\n')
            pretty_perms.insert(15, '\n**Voice Permissions**\n')
            pretty_perms = '\n'.join(pretty_perms)

            embed.add_field(name=f'I cannot send messages in {guild}. '
                                 f'Please can I have these permissions:',
                            value=f'{pretty_perms}\n\n'
                                  f'Or re-invite me with the link [here]'
                                  f'({discord.utils.oauth_url(self.bot.user.id, discord_perms, guild)})')
            try:
                await guild.owner.send(embed=embed)
            except discord.Forbidden:
                return
        await self.bot.owner.send(self.bot.config_cache)

    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        await self.bot.db.execute(
            """
            DELETE FROM config
            WHERE guild_id = $1;
            """, guild.id
        )
        self.bot.config_cache.pop(guild.id)
        self.bot.log.info(f'Leaving guild {guild.name} - {guild.id}')

    @commands.Cog.listener()
    async def on_member_join(self, member):
        """
        {member} - The user's name
        {server} - The server name
        {@member} - Mentions the user
        #channel - Mention a channel the normal way
        """
        # TODO check if a member joined before check if they want autoroling after leaving

        guild_settings = self.bot.config_cache[member.guild.id]

        if guild_settings['join_message']:
            msg = guild_settings['join_message'] \
                .replace('{{member}}', member.name).replace('{{@member}}', member.mention) \
                .replace('{{server}}', member.guild.name)
            await member.send(msg)

        # role_list = guild_settings['member role list'][m_id]
        '''
        if m_id in role_list:  # add back their old roles if there are any in the users.json
            reason = f'Adding back old roles as requested by {member.guild.owner}'
            role_list = role_list[m_id]
            for role in role_list:
                await member.edit(discord.utils.get(member.guild.roles, name=role), reason=reason)
        elif guild_settings['auto roling']:
            role = guild_settings['auto_roling']
            reason = f'Autoroled as requested by {member.guild.owner}'
            await member.add_roles(discord.utils.get(member.guild.roles, name=role), reason=reason)'''

    # ban & kick -------------------------------------------------------------------------------------------------------

    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):
        if 'member_ban' in self.bot.config_cache[guild.id]['logged_events']:
            embed = discord.Embed(title=user,
                                  description=f'{user} - {user.id} was banned from {guild} - {guild.id}',
                                  color=discord.Color.red())
            embed.set_footer(text=f'ID: {user.id} • {datetime.now().strftime("%c")}', icon_url=user.avatar_url)
            await self.bot.config_cache[user.guild.id]['logging_channel'].send(embed=embed)

    @commands.Cog.listener()
    async def on_member_kick(self, guild, user):
        if 'member_kick' in self.bot.config_cache[guild.id]['logged_events']:
            embed = discord.Embed(title=user,
                                  description=f'{user}-{user.id} was kicked from {guild} - {guild.id}',
                                  color=discord.Color.red())
            embed.set_footer(text=f'ID: {user.id} • {datetime.now().strftime("%c")}', icon_url=user.avatar_url)
            await self.bot.config_cache[user.guild.id]['logging_channel'].send(embed=embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        if 'member_leave' in self.bot.config_cache[member.guild.id]['logged_events']:
            embed = discord.Embed(title='Member left', description=f'{member} just left {member.guild.name}',
                                  color=discord.Color.red())
            embed.set_footer(text=f'ID: {member.id} • {datetime.now().strftime("%c")}', icon_url=member.avatar_url)
            await self.bot.config_cache[member.guild.id]['logging_channel'].send(embed=embed)

    # message deletes --------------------------------------------------------------------------------------------------

    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload):
        channel = None
        message = payload.cached_message
        if message is None:
            channel = self.bot.get_channel(payload.channel_id)
        if message.channel or channel:
            guild = message.guild or channel.guild
            if 'message_deletes' in self.bot.config_cache[guild.id]['logged_events']:
                if message is None:
                    embed = discord.Embed(description=f'**Message deleted in: {channel.mention}**',
                                          color=get_colour(colour='bad_colour', message=message, bot=self.bot))
                    embed.set_footer(text=f'{datetime.now().strftime("%c")}')
                    return await self.bot.config_cache[guild.id]['logging_channel'].send(embed=embed)

                if message.author.bot:
                    return
                embed = discord.Embed(title='Message deleted', color=discord.Color.red())
                embed.add_field(name='Message from:',
                                value=f'**{message.author.mention} deleted in {message.channel.mention}**')
                if message.content:
                    embed.description = f'Content:\n>>> {message.content}'
                if message.attachments:
                    if len(message.attachments) == 1:
                        if message.attachments[0].filename.endswith(('.png', '.gif', '.webp,' '.jpg')):
                            embed.set_image(url=message.attachments[0].proxy_url)
                        else:
                            embed.set_footer(text=f'ID: {message.author.id} • {datetime.now().strftime("%c")}',
                                             icon_url=message.author.avatar_url)
                            return await message.guild.system_channel.send(
                                f'Deleted message included a non-image attachment, '
                                f'that cannot be relocated although its name was '
                                f'`{message.attachments[0].filename}`',
                                embed=embed)
                    elif len(message.attachments) > 1:
                        embed.set_footer(text=f'ID: {message.author.id} • {datetime.now().strftime("%c")}',
                                         icon_url=message.author.avatar_url)
                        names = [f.filename for f in message.attachments]
                        for image in message.attachments:
                            if message.attachments[0].filename.endswith(('.png', '.gif', '.webp,' '.jpg')):
                                embed.set_image(url=image.proxy_url)
                                break
                        embed.set_footer(text=f'ID: {message.author.id} • {datetime.now().strftime("%c")}',
                                         icon_url=message.author.avatar_url)
                        return await message.guild.system_channel.send(
                            f'Deleted message included multiple attachments, '
                            f'that cannot be found :( although there names were:\n'
                            f'`{"`, `".join(names)}`', embed=embed)

                embed.set_footer(text=f'ID: {message.id} • {datetime.now().strftime("%c")}',
                                 icon_url=message.author.avatar_url)
                await self.bot.config_cache[guild.id]['logging_channel'].send(embed=embed)

    # guild creation ---------------------------------------------------------------------------------------------------

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        if 'channel_updates' in self.bot.config_cache[channel.guild.id]['logged_events']:
            embed = discord.Embed(title=f'#{channel.name}', description=f'{channel.mention} - was just created',
                                  color=discord.Color.green())
            embed.set_footer(text=f'ID: {channel.id} • {datetime.now().strftime("%c")}')
            await self.bot.config_cache[channel.guild.id]['logging_channel'].send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        if 'channel_updates' in self.bot.config_cache[channel.guild.id]['logged_events']:
            embed = discord.Embed(title=f'#{channel.name}', description=f'{channel.name} - was just deleted',
                                  color=discord.Color.red())
            embed.set_footer(text=f'ID: {channel.id} • {datetime.now().strftime("%c")}')
            await self.bot.config_cache[channel.guild.id]['logging_channel'].send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_role_create(self, role):
        if 'roles_updates' in self.bot.config_cache[role.guild.id]['logged_events']:
            embed = discord.Embed(title='Role created', description=f'New role {role.mention} created',
                                  color=discord.Color.green())
            embed.set_footer(text=f'ID: {role.id} • {datetime.now().strftime("%c")}')
            await self.bot.config_cache[role.guild.id]['logging_channel'].send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        if 'roles_updates' in self.bot.config_cache[role.guild.id]['logged_events']:
            embed = discord.Embed(title='Role deleted', description=f'Role {role.name} deleted',
                                  color=discord.Color.green())
            embed.set_footer(text=f'ID: {role.id} • {datetime.now().strftime("%c")}')
            await self.bot.config_cache[role.guild.id]['logging_channel'].send(embed=embed)

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        if 'name_update' in self.bot.config_cache[before.guild.id]['logged_events']:
            gain = [role for role in after.roles if role not in before.roles]
            lost = [role for role in before.roles if role not in after.roles]
            if before.display_name != after.display_name:
                title = f'{before.name}\'s nickname was changed'
                description = f'Before it was `{before.display_name}`, now it is `{after.display_name}`'
            elif lost:
                title = f'User {before.name}'
                description = f'Lost the role{"" if len(gain) == 1 else "s"} {", ".join([role.mention for role in lost])}'
            elif gain:
                title = f'User {before.name}'
                description = f'Gained the role{"" if len(gain) == 1 else "s"} {", ".join([role.mention for role in gain])}'
            else:
                return
            embed = discord.Embed(title=title, description=description, color=discord.Color.green())
            embed.set_footer(text=f'ID: {before.id} • {datetime.now().strftime("%c")}', icon_url=before.avatar_url)
            await self.bot.config_cache[before.guild.id]['logging_channel'].send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_role_update(self, before, after):
        if 'role_updates' in self.bot.config_cache[before.guild.id]['logged_events']:
            old = [perm for perm in before.permissions if perm not in after.permissions]
            if before.name != after.name:
                embed = discord.Embed(title=f'Role name for {before.name} changed',
                                      description=f'Before it was `{before.name}`, now it is `{after.name}`',
                                      color=discord.Colour.blurple())
            elif old:
                if old[0][1]:
                    embed = discord.Embed(
                        title=f'Permission{"" if len(old) == 1 else "s"} updated for role {after.name}',
                        description=f'Lost permission{"" if len(old) == 1 else "s"} '
                                    f'`{"`, `".join([perm[0].title() for perm in old])}`',
                        color=before.colour)
                else:
                    embed = discord.Embed(
                        title=f'Permission{"" if len(old) == 1 else "s"} updated for role {after.name}',
                        description=f'Gained permission{"" if len(old) == 1 else "s"} '
                                    f'`{"`, `".join([perm[0].title() for perm in old])}`',
                        color=before.colour)
            else:
                return
            await self.bot.config_cache[before.guild.id]['logging_channel'].send(embed=embed)

    @commands.Cog.listener()
    async def on_message(self, message):
        # checking if someone someone said a blacklisted word
        # TODO add A blacklisting command and different levels of splitting
        if message.author.bot or message.guild is None:
            return
        if self.bot.config_cache[message.guild.id]['logged_events']:
            split_message = re.split("(?:(?:[^a-zA-Z0-9]+)|(?:'[^a-zA-Z0-9]+))|(?:[^a-zA-Z0-9]+)",
                                     # split at non alpha-numeric characters
                                     unidecode.unidecode(message.content.lower()))  # normalise unicode
            rejoined = ''.join(split_message)
            matched = re.search(f'({"|".join(self.bot.config_cache[message.guild.id]["logged_events"])})+', rejoined)
            if matched:
                await message.delete()
                matched = list(matched.groups())
                embed = discord.Embed(
                    title=f'{message.author} your message has been removed as it contains a blacklisted word!',
                    description=f'Content:\n>>> {message.content}', colour=discord.Colour.red())
                embed.add_field(name=f'Matched word{"s" if len(matched) > 1 else ""}:', value=', '.join(matched))
                await message.author.send(embed=embed)
                embed = discord.Embed(
                    title=f'{message.author} just said something blacklisted in #{message.channel}!',
                    description=f'Content:\n>>> {message.content}', colour=discord.Colour.red())
                embed.add_field(name=f'Matched word{"s" if len(matched) > 1 else ""}:', value=', '.join(matched))
                await self.bot.config_cache[message.guild.id]['logging_channel'].send(embed=embed)

    # error handler ----------------------------------------------------------------------------------------------------

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        """Command error handler"""
        if hasattr(ctx.command, 'on_error'):
            return
        error = getattr(error, 'original', error)
        ignored = (commands.CommandNotFound, commands.CheckFailure)
        if isinstance(error, ignored):
            return
        elif isinstance(error, commands.MissingRequiredArgument):
            title = f'{ctx.command} is missing a required argument {error.param}'
        elif isinstance(error, commands.CommandOnCooldown):
            if ctx.guild:
                if ctx.author.guild_permissions.manage_roles:
                    return await ctx.reinvoke()
            title = f'{ctx.command} is on cooldown'
        elif isinstance(error, commands.BadArgument):
            title = 'Bad argument'
        elif isinstance(error, commands.NotOwner):
            title = 'You are not the owner of the bot'
        elif isinstance(error, commands.MissingPermissions):
            title = f'You do not have the necessarily permissions to run {ctx.command}'
        elif isinstance(error, commands.BotMissingPermissions):
            title = 'The bot is missing permissions to perform that command'
        elif isinstance(error, commands.DisabledCommand):
            title = f'{ctx.command} has been disabled.'
        elif isinstance(error, commands.NoPrivateMessage):
            title = f'{ctx.command} can not be used in Private Messages'
        elif isinstance(error, discord.Forbidden):
            title = 'Forbidden - Discord says no'
        elif isinstance(error, commands.CommandInvokeError):
            title = 'This command errored: please hang tight, whilst I try to fix this'
            embed = discord.Embed(title=f'Ignoring exception in command {ctx.command}',
                                  description=f'```py\n{discord.utils.escape_markdown(format_exec(error))}```',
                                  colour=discord.Colour.red())
            embed.set_author(
                name=f'Command {ctx.command} {f"{ctx.guild.name} - {ctx.guild.id}," if ctx.guild else ""} used by '
                     f'{ctx.author.name} - {ctx.author.id}',
                icon_url=ctx.author.avatar_url)
            try:
                await self.bot.get_channel(655093734525894666).send(embed=embed)
            except discord.HTTPException:
                raise error

        else:
            title = 'Unspecified error: please hang tight, whilst I try take a look at this'
            embed = discord.Embed(title=f'Ignoring exception in command {ctx.command}',
                                  description=f'```py\n{discord.utils.escape_markdown(format_exec(error))}```',
                                  colour=discord.Colour.red())
            embed.set_author(
                name=f'Command {ctx.command} {f"{ctx.guild.name} - {ctx.guild.id}," if ctx.guild else ""} used by '
                     f'{ctx.author.name} - {ctx.author.id}',
                icon_url=ctx.author.avatar_url)
            try:
                await self.bot.get_channel(655093734525894666).send(embed=embed)
            except discord.HTTPException:
                raise error

        embed = discord.Embed(title=f':warning: **{title}**', color=discord.Colour.red())
        embed.add_field(name='Error message:', value=f'```py\n{type(error).__name__}: {error}\n```')
        await ctx.send(embed=embed, delete_after=180)
        self.bot.log.warning(format_error(error))


def setup(bot):
    bot.add_cog(Listeners(bot))
