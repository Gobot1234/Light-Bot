import asyncio
import discord
from datetime import datetime, timedelta
from psutil import Process, virtual_memory, cpu_percent
from humanize import naturalsize
from discord import __version__ as d_version

from platform import python_version

from typing import Optional
from discord.ext import commands
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

    async def unmute_timer(self, time: int, member, ctx):
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

            embed = discord.Embed(title='Messages cleared',
                                  description=f'**The clear command was used in {ctx.channel.mention} by {ctx.author.mention} '
                                              f'to delete `{limit}` messages**',
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
    async def _remove_all(self, ctx, search: int = 100):
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

    #  mute ------------------------------------------------------------------------------------------------------------

    @commands.command()
    @commands.has_permissions(manage_roles=True)
    async def mute(self, ctx, members: commands.Greedy[discord.Member], *,
                   until: UserFriendlyTime(commands.clean_content)):
        """Mutes a user for a specific time"""
        muted = discord.utils.get(ctx.guild.roles, name='Muted')
        for member in members:
            if member == ctx.author or member.id == self.bot.user.id:
                return await ctx.send('Why would you do that???', delete_after=3)
            bot_delta = round(timedelta.total_seconds(until.dt - datetime.utcnow()))
            human_delta = human_timedelta(until.dt)
            await ctx.send(
                f'Muted `{member.display_name}`, for reason `{until.arg}`, they will be un-muted in `{human_delta}`')
            await member.add_roles(muted, reason=until.arg)
            await self.unmute_timer(bot_delta, member, ctx)

    @commands.command()
    @commands.has_permissions(manage_roles=True)
    async def unmute(self, ctx, members: commands.Greedy[discord.Member], *, reason='None given'):
        """Un-mutes a user"""
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
    async def ban(self, ctx, members: commands.Greedy[discord.Member], reason: Optional[str] = 'None given',
                  delete_days: Optional[int] = 0):
        """Ban users you need to be able to normally ban users to use this"""
        if ctx.author in members:
            return await ctx.channel.send('You cannot ban yourself, well you can try')
        for member in members:
            await member.send(f'You have been banned from {ctx.guild.name} for {reason}')
            await member.ban(delete_message_days=delete_days, reason=reason)
            await ctx.send(f'{member.mention} has been banned!')

    @commands.command()
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    async def unban(self, ctx, *users: commands.Greedy[discord.User]):
        """Unban a user you need to be able to normally ban users to use this"""
        for user in users:
            try:
                await ctx.guild.unban(user)
            except:
                await ctx.send(f'Member {user} wasn\'t found')
            else:
                await ctx.send(f'{user} has been unbanned!')
                try:
                    await user.send(f'You have been unbanned from {ctx.guild}, by {ctx.author}')
                except discord.Forbidden:
                    pass

    @commands.command()
    @commands.has_permissions(kick_members=True)
    @commands.bot_has_permissions(kick_members=True)
    async def kick(self, ctx, members: commands.Greedy[discord.Member], *, reason: str = 'None Given'):
        """Ban a user you need to be able to normally ban users to use this"""
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
