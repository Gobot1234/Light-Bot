import asyncio
import discord
from datetime import datetime, timedelta

import typing
from psutil import Process

from typing import Optional
from discord.ext import commands, buttons
from collections import Counter

from Utils.time import UserFriendlyTime, human_timedelta
from Utils.checks import prefix


class Staff(commands.Cog):
    """These commands can only be used by people who already have the discord permissions to do so.
    Please also note that the bot also requires these permissions to perform these commands
    **Manage Messages permission is needed for:** - clear
    **Ban Users permission is needed for:** - ban, unban
    **Kick Members permission is needed for:** - kick
    **Manage Roles permission is needed for:**  - mute, unmute"""

    def __init__(self, bot):
        self.bot = bot
        self.process = Process()

    async def cog_check(self, ctx):

        return ctx.author.guild_permissions.ban_members or ctx.author.guild_permissions.kick_members \
               or ctx.author.guild_permissions.manage_roles or ctx.author.permissions_in(ctx.channel).manage_messages

    async def unmute_timer(self, ctx, member, time: float):
        await asyncio.sleep(time)
        await member.remove_roles(discord.utils.get(member.guild.roles, name='Muted'))
        await ctx.send(f'Un-muted member {member.display_name}')

    async def do_removal(self, ctx, limit, predicate, *, before=None, after=None):
        if limit > 2000:
            return await ctx.send(f'Too many messages to search given ({limit}/2000)')

        if before is None:
            before = ctx.message
        else:
            before = discord.Object(id=before)

        if after is not None:
            after = discord.Object(id=after)

        try:
            deleted = await ctx.channel.purge(limit=limit, before=before, after=after, check=predicate)
        except discord.Forbidden:
            return await ctx.send('I do not have permissions to delete messages.')
        except discord.HTTPException as e:
            return await ctx.send(f'Error: {e} (try a smaller search?)')
        spammers = Counter(m.author.display_name for m in deleted)
        deleted = len(deleted)
        messages = [f'Successfully removed `{deleted}` message{" " if deleted == 1 else "s"}']
        if deleted:
            messages.append('')
            spammers = sorted(spammers.items(), key=lambda t: t[1], reverse=True)
            messages.extend(f'**{name}**: {count}' for name, count in spammers)

            to_send = '\n'.join(messages)
            nl = '\n'

            embed = discord.Embed(title='Messages cleared',
                                  description=f'**The clear command was used in {ctx.channel.mention} by {ctx.author.mention}** '
                                              f'to delete `{limit}` message{"" if deleted == 1 else "s"} from:\n'
                                              f'{f"{nl}".join(f"**{name}**: {count}" for name, count in spammers)}',
                                  color=discord.Color.blue())
            embed.set_footer(text=str(datetime.now())[:-5], icon_url=ctx.author.avatar_url)
            await ctx.guild.system_channel.send(embed=embed)
            await ctx.send(to_send, delete_after=10)
        else:
            await ctx.send('No messages found or deleted')

    async def get_uptime(self):
        delta_uptime = datetime.utcnow() - self.bot.launch_time
        hours, remainder = divmod(int(delta_uptime.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        days, hours = divmod(hours, 24)
        return f'`{days}d, {hours}h, {minutes}m, {seconds}s`'

    # clear ------------------------------------------------------------------------------------------------------------

    @commands.group(aliases=['purge', 'delete'])
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    async def clear(self, ctx):
        """Clear messages from chat of a specified type

        Stolen from <@80528701850124288> thanks R.Danny"""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @clear.command(name='all')
    async def _remove_all(self, ctx, search: int = 10):
        """Removes all messages."""
        if search >= 100:
            search = 100
        await self.do_removal(ctx, search, lambda e: True)

    @clear.command()
    async def embeds(self, ctx, search: int = 100):
        """Removes messages that have embeds in them."""
        await self.do_removal(ctx, search, lambda e: len(e.embeds))

    @clear.command()
    async def files(self, ctx, search: int = 100):
        """Removes messages that have attachments in them."""
        await self.do_removal(ctx, search, lambda e: len(e.attachments))

    @clear.command()
    async def images(self, ctx, search: int = 100):
        """Removes messages that have embeds or attachments."""
        await self.do_removal(ctx, search, lambda e: len(e.embeds) or len(e.attachments))

    @clear.command()
    async def user(self, ctx, member: discord.Member, search: int = 100):
        """Removes all messages by the member."""
        await self.do_removal(ctx, search, lambda e: e.author == member)

    @clear.command()
    async def contains(self, ctx, *, substr: str):
        """Removes all messages containing a substring.
        The substring must be at least 3 characters long.
        """
        if len(substr) < 3:
            await ctx.send('The substring length must be at least 3 characters.')
        else:
            await self.do_removal(ctx, 100, lambda e: substr in e.content)

    @clear.command()
    async def bot(self, ctx, search=100):
        """Cleans up the bot's messages from the channel.
        If a search number is specified, it searches that many messages to delete.
        You must have Manage Messages permission to use this.
        """
        await self.do_removal(ctx, search, lambda e: e.author == ctx.guild.me)

    #  mute ------------------------------------------------------------------------------------------------------------

    @commands.group(invoke_without_command=True, aliases=['muted'])
    @commands.has_permissions(manage_roles=True)
    async def mute(self, ctx, members: commands.Greedy[discord.Member], *, until: UserFriendlyTime(commands.clean_content)):
        """
        Mute a user for a specific time

        The input can be any direct date (e.g. YYYY-MM-DD) or a human
        readable offset. Examples:

        - "next thursday at 3pm they are spamming"
        - "they mentioned @​everyone tomorrow"
        - "in 3 days mention spamming"
        - "2d none needed"

        Times are in UTC.s
        """
        muted = discord.utils.get(ctx.guild.roles, name='Muted')
        if muted is None:
            muted = await ctx.guild.create_role(name='Muted', colour=0x2f3136,
                                                reason='Created automatically as no muted role was found')
        for member in members:
            if member == (ctx.author or self.bot.user):
                return await ctx.send('Why would you do that???', delete_after=3)
            bot_delta = timedelta.total_seconds(until.dt - datetime.utcnow())
            human_delta = human_timedelta(until.dt)
            await ctx.send(
                f'Muted `{member.display_name}`, for reason `{until.arg}`, they will be un-muted in `{human_delta}`')
            await member.add_roles(muted, reason=until.arg)
            for channel in ctx.guild.channels:
                await channel.set_permissions(muted, read_messages=True, send_messages=False, add_reactions=False)
            await self.unmute_timer(ctx, member, bot_delta)

    @mute.command(name='list')
    async def mutelist(self, ctx):
        """Get a list of the currently muted members the reason for their mute and how long they will be muted for"""
        # todo add time until they are unmuted and sort by that along with the reason
        muted = discord.utils.get(ctx.guild.roles, name='Muted')
        muted_list = [member for member in ctx.guild.members if muted in member.roles]
        paginator = buttons.Paginator(title=f'{len(muted_list)} Muted member{"s" if len(muted_list) > 1 else ""}',
                                      colour=discord.Colour.blurple(), length=5,
                                      entries=[f'{i}. {e}' for i, e in enumerate(muted_list, start=1)])
        await paginator.start(ctx)

    @commands.command()
    @commands.has_permissions(manage_roles=True)
    async def unmute(self, ctx, members: commands.Greedy[discord.Member], *, reason='None given'):
        """Un-mute users"""
        role = discord.utils.get(ctx.guild.roles, name='Muted')
        for member in members:
            if role not in member.roles:
                await ctx.send('They weren\'t muted in the first place')
            else:
                await member.remove_roles(discord.utils.get(member.guild.roles, name='Muted'), reason=reason)
                await ctx.send(f'Un-muted {member.display_name}, for reason \"{reason}\"')

    #  ban -------------------------------------------------------------------------------------------------------------

    @commands.command()
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    async def ban(self, ctx, members: commands.Greedy[discord.Member], reason: Optional[str] = 'None given', delete_days: Optional[int] = 0):
        """Ban users you need to be able to normally ban users to use this"""
        if ctx.author in members:
            return await ctx.channel.send('You cannot ban yourself, well you can try')
        for member in members:
            try:
                await member.send(f'You have been banned from {ctx.guild.name} for {reason}')
            except discord.Forbidden:
                pass
            await member.ban(delete_message_days=delete_days, reason=reason)
            await ctx.send(f'{member.mention} has been banned!')

    @commands.command()
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    async def unban(self, ctx, users: commands.Greedy[typing.Union[discord.User, int, str]]):
        """
        Unban a user you need to be able to normally ban users to use this command.

        You can use either an ID or a name with the discriminator eg.
        `{prefix}unban Gobot1234#2435`
        or
        `{prefix}unban 340869611903909888`
        """
        bans = await ctx.guild.bans()
        for user in users:
            if isinstance(user, discord.User):  # check if the user is still cached or in another server
                try:
                    await ctx.guild.unban(user)
                except discord.NotFound:
                    raise commands.UserInputError(f'User {user} not found? Double check your ID or name '
                                                  f'again or perhaps they aren\'t banned')

                else:
                    await ctx.send(f'{user.mention} has been unbanned!')
                    try:
                        await user.send(f'You have been unbanned from {ctx.guild}, by {ctx.author}')
                    except discord.Forbidden:
                        pass
            else:
                if user.isdigit():  # check if its an id makes things simpler
                    try:
                        await ctx.guild.unban(discord.Object(user))
                    except discord.Forbidden:
                        raise commands.UserInputError(f'User {user} not found? Double check your ID or name '
                                                      f'again or perhaps they aren\'t banned')
                    else:
                        await ctx.send(f'<@{user}> has been unbanned!')
                else:
                    for reason, banned_user in bans:
                        if banned_user == user:
                            await ctx.guild.unban(banned_user)
                            await ctx.send(f'{banned_user.mention} has been unbanned!')
                            try:
                                await banned_user.send(f'You have been unbanned from {ctx.guild}, by {ctx.author}')
                            except discord.Forbidden:
                                pass
                            break
                    raise commands.UserInputError(f'User {user} not found? Double check your ID or name '
                                                  f'again or perhaps they aren\'t banned')

    @commands.command()
    @commands.has_permissions(kick_members=True)
    @commands.bot_has_permissions(ban_members=True)
    async def softban(self, ctx, members: commands.Greedy[discord.Member], *, reason: str = 'None given'):
        """Softban a user - ban & then unban them straight after requires kick members permission"""
        if ctx.author in members:
            return await ctx.channel.send('You cannot ban yourself, well you can try')
        for member in members:
            try:
                await member.send(f'You have been softbanned from {ctx.guild.name} - '
                                  f'you may rejoin but be warned you may be on a warning for {reason}')
            except discord.Forbidden:
                pass
            await member.ban(reason=reason)
            await ctx.guild.unban(member)
            await ctx.send(f'{member.mention} has been softbanned!')

    @commands.command()
    @commands.has_permissions(kick_members=True)
    @commands.bot_has_permissions(kick_members=True)
    async def kick(self, ctx, members: commands.Greedy[discord.Member], *, reason: str = 'None Given'):
        """Kick a user you need to be able to normally ban users to use this"""
        if ctx.author in members:
            return await ctx.channel.send('You cannot kick yourself, well you can try')
        for member in members:
            try:
                await member.send(f'You have been kicked from {ctx.guild}, by {ctx.author} for "{reason}"')
            except discord.Forbidden:
                pass
            await ctx.send(f'{member.mention} has been kicked!')
            await member.kick(reason=f'"{reason}", by {ctx.author} at {datetime.now()}')


def setup(bot):
    bot.add_cog(Staff(bot))
