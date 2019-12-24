import asyncio
import json
import os
import random
from datetime import datetime
import sys
import traceback

import discord
from discord.ext import commands, tasks

from Utils.checks import prefix, colour_good, colour_neutral, colour_bad
from Utils.formats import format_exec


class Listeners(commands.Cog):
    """Listeners for the bot"""

    def __init__(self, bot):
        self.bot = bot
        self.status.start()

    async def cog_check(self, ctx):
        return False

    @tasks.loop(minutes=5)
    async def status(self):
        status = random.choice([f'over {len(self.bot.guilds)} servers',
                                f'over {len(set(self.bot.get_all_members()))} members',
                                f'for =help'])
        activity = discord.Activity(name=status, type=discord.ActivityType.watching)
        await self.bot.change_presence(activity=activity)

    @status.after_loop
    async def after_my_task(self):
        if self.status.failed():
            import traceback
            traceback.print_exc()

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
        # ask the owner what features they want
        # load db get all members
        embed = discord.Embed(title=':white_check_mark: Server added!',
                              description='Thank you for adding me to your server!', color=discord.Colour.green())
        embed.set_footer(text=f'Joined at: {datetime.now().strftime("%c")}')
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

    # ban & kick -------------------------------------------------------------------------------------------------------

    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):
        embed = discord.Embed(title=user,
                              description=f'{user.name} - {user.id} was banned from {guild.name} - {guild.id}',
                              color=discord.Color.red())
        embed.set_footer(text=f'ID: {user.author.id} • {datetime.now().strftime("%c")}', icon_url=user.avatar_url)
        await guild.system_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_kick(self, guild, user):
        embed = discord.Embed(title=user,
                              description=f'{user.name}-{user.id} was kicked from {guild.name}-{guild.id}',
                              color=discord.Color.red())
        embed.set_footer(text=f'ID: {user.author.id} • {datetime.now().strftime("%c")}', icon_url=user.avatar_url)
        await guild.system_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        embed = discord.Embed(title='Member left', description=f'{member} just left {member.guild.name}',
                              color=discord.Color.red())
        embed.set_footer(text=f'ID: {member.id} • {datetime.now().strftime("%c")}', icon_url=member.avatar_url)
        await member.guild.system_channel.send(embed=embed)

    # message deletes --------------------------------------------------------------------------------------------------

    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload):
        message = payload.cached_message
        if message is None:
            channel = self.bot.get_guild(payload.channel_id)
            embed = discord.Embed(description=f'**Message deleted in: {channel.mention}**', color=discord.Color.red())
            embed.set_footer(text=f'{datetime.now().strftime("%c")}')
            return await channel.guild.system_channel.send(embed=embed)
        author = message.author
        if author.bot:
            return
        embed = discord.Embed(title='Message deleted', color=discord.Color.red())
        embed.add_field(name='Message from:', value=f'**{author.mention} deleted in {message.channel.mention}**')
        if message.content:
            embed.description = f'Content:\n>>> {message.content}'
        if message.attachments:
            if len(message.attachments) == 1:
                if message.attachments[0].filename.endswith(('.png', '.gif', '.webp,' '.jpg')):
                    embed.set_image(url=message.attachments[0].proxy_url)
                else:
                    embed.set_footer(text=f'ID: {message.author.id} • {datetime.now().strftime("%c")}',
                                     icon_url=author.avatar_url)
                    return await message.guild.system_channel.send(f'Deleted message included a non-image attachment, '
                                                                   f'that cannot be relocated although its name was '
                                                                   f'`{message.attachments[0].filename}`',
                                                                   embed=embed)
            elif len(message.attachments) > 1:
                embed.set_footer(text=f'ID: {message.author.id} • {datetime.now().strftime("%c")}',
                                 icon_url=author.avatar_url)
                names = [f.filename for f in message.attachments]
                for image in message.attachments:
                    if message.attachments[0].filename.endswith(('.png', '.gif', '.webp,' '.jpg')):
                        embed.set_image(url=image.proxy_url)
                        break
                embed.set_footer(text=f'ID: {message.author.id} • {datetime.now().strftime("%c")}',
                                 icon_url=author.avatar_url)
                return await message.guild.system_channel.send(f'Deleted message included multiple attachments, '
                                                               f'that cannot be found :( although there names were:\n'
                                                               f'`{"`, `".join(names)}`', embed=embed)

        embed.set_footer(text=f'ID: {message.author.id} • {datetime.now().strftime("%c")}', icon_url=author.avatar_url)
        await message.guild.system_channel.send(embed=embed)

    # guild creation ---------------------------------------------------------------------------------------------------

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        embed = discord.Embed(title=f'#{channel.name}', description=f'{channel.mention} - was just created',
                              color=discord.Color.green())
        embed.set_footer(text=f'ID: {channel.id} • {datetime.now().strftime("%c")}')
        await channel.guild.system_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        embed = discord.Embed(title=f'#{channel.name}', description=f'{channel.name} - was just deleted',
                              color=discord.Color.red())
        embed.set_footer(text=f'ID: {channel.id} • {datetime.now().strftime("%c")}')
        await channel.guild.system_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_role_create(self, role):
        embed = discord.Embed(title='Role created', description=f'New role {role.mention} created',
                              color=discord.Color.green())
        embed.set_footer(text=f'ID: {role.id} • {datetime.now().strftime("%c")}')
        await role.guild.system_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        embed = discord.Embed(title='Role deleted', description=f'Role {role.name} deleted',
                              color=discord.Color.green())
        embed.set_footer(text=f'ID: {role.id} • {datetime.now().strftime("%c")}')
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
            description = f'Lost the role{"" if len(gain) == 1 else "s"} {", ".join([role.mention for role in lost])}'
        elif gain:
            title = f'User {before.name}'
            description = f'Gained the role{"" if len(gain) == 1 else "s"} {", ".join([role.mention for role in gain])}'
        else:
            return
        embed = discord.Embed(title=title, description=description, color=discord.Color.green())
        embed.set_footer(text=f'ID: {before.id} • {datetime.now().strftime("%c")}', icon_url=before.avatar_url)
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
                embed = discord.Embed(title=f'Permission{"" if len(old) == 1 else "s"} updated for role {after.name}',
                                      description=f'Lost permission{"" if len(old) == 1 else "s"} `{"`, `".join([perm[0].title() for perm in old])}`',
                                      color=before.colour)
            else:
                embed = discord.Embed(title=f'Permission{"" if len(old) == 1 else "s"} updated for role {after.name}',
                                      description=f'Gained permission{"" if len(old) == 1 else "s"} `{"`, `".join([perm[0].title() for perm in old])}`',
                                      color=before.colour)
        else:
            return
        await before.guild.system_channel.send(embed=embed)

        '''
    @commands.Cog.listener()
    async def on_message(self, message):  # checking if someone someone said a blacklisted word TODO ADD A blacklisting command
        if message.author == self.bot.user:
            return
        blacklist_words = message.guild.id['blacklist words']
        if blacklist_words:
            split_message = re.split("(?:(?:[^a-zA-Z]+')|(?:'[^a-zA-Z]+))|(?:[^a-zA-Z']+)",
                                     str(message.content).lower())
            if any(word in split_message for word in blacklist_words):
                await message.delete()
                await message.author.send(f'{message.author.mention} Your message "{message.content}" '
                                          f'has been removed as it contains a blacklisted word!',
                                          delete_after=5)
                await message.guild.system_channel.send(f'{message.author}, just said {message.content}, '
                                                        f'in {str(message.channel)}')'''

    # error handler ----------------------------------------------------------------------------------------------------

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        """Command error handler"""
        if hasattr(ctx.command, 'on_error'):
            return

        ignored = (commands.CommandNotFound, commands.UserInputError, commands.CheckFailure)
        if isinstance(error, ignored):
            return
        elif isinstance(error, commands.MissingRequiredArgument):
            title = f'{ctx.command} is missing a required argument'
        elif isinstance(error, commands.CommandOnCooldown):
            if ctx.message.author.guild_permissions.manage_roles:
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
            title = f'{ctx.command} can not be used in Private Messages.'
        elif isinstance(error, commands.CommandInvokeError):
            title = 'This command has errored: please hang tight, whilst I try to fix this'
            embed = discord.Embed(title=f'Ignoring exception in command {ctx.command}',
                                  description=f'```py\n{discord.utils.escape_markdown(format_exec(error))}```',
                                  colour=discord.Colour.red())
            embed.set_author(name=f'{ctx.guild.name} - {ctx.guild.id}, used by {ctx.author.name} - {ctx.author.id}',
                             icon_url=ctx.author.avatar_url)
            try:
                await self.bot.get_channel(655093734525894666).send(embed=embed)
            except discord.HTTPException:
                raise error

        else:
            title = 'Unspecified error: please hang tight, whilst I try take a look at this'

        embed = discord.Embed(title=f':warning: **{title}**', color=discord.Colour.red())
        embed.add_field(name='Error message:', value=f'```py\n{error.__class__.__name__}: {error}\n```')
        await ctx.send(embed=embed, delete_after=180)
        traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)


def setup(bot):
    bot.add_cog(Listeners(bot))
