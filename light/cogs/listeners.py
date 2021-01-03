from __future__ import annotations

import traceback
from random import choice
from typing import Literal, Optional,  TYPE_CHECKING

import asyncpg
import discord
from discord.ext import commands, tasks

from .utils.context import Context
from .utils.db import Config
from .utils.formats import format_error

if TYPE_CHECKING:
    from .. import Light


class Listeners(commands.Cog):
    """Listeners for the bot"""

    def __init__(self, bot: Light):
        self.bot = bot
        self.status.start()

    async def cog_check(self, ctx):
        return False

    @tasks.loop(minutes=60)
    async def status(self):
        status = choice(
            [
                f"over {len(self.bot.guilds)} servers",
                f"over {len(set(self.bot.get_all_members()))} members",
                f"for =help",
            ]
        )
        activity = discord.Activity(name=status, type=discord.ActivityType.watching)
        await self.bot.change_presence(activity=activity)

    @status.before_loop
    async def wait_for_ready_status(self):
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild) -> None:
        record = await Config.fetchrow(guild_id=guild.id)
        if record is not None and record.blacklisted:
            self.bot.log.info(f"Leaving {guild.name!r} - {guild.id} as it is a blacklisted guild")
            await guild.leave()
        else:
            record = await Config.insert(
                guild_id=guild.id, blacklisted=False, prefixes=["="], logging_channel=None, logged_events=[],
            )
        self.bot.config_cache[record.guild_id] = dict(record.original)

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild) -> None:
        if not (await Config.fetchrow(guild_id=guild.id)).blacklisted:
            await Config.delete(guild_id=guild.id)
            self.bot.config_cache.pop(guild.id)
            self.bot.log.info(f"Leaving guild {guild.name} - {guild.id}")

    def log_for(
        self, guild_id: int, *events: Literal["member_ban", "member_join", "member_kick"]
    ) -> Optional[discord.TextChannel]:
        for event in events:
            if event in self.bot.config_cache[guild_id]["logged_events"]:
                return self.bot.get_channel(self.bot.config_cache[guild_id]["logging_channel"])

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if channel := self.log_for(member.guild.id, "member_join"):
            await channel.send(f"{member.display_name} just joined")

    # ban & kick -------------------------------------------------------------------------------------------------------

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User):
        if channel := self.log_for(guild.id, "member_ban"):
            await channel.send(f"{user.display_name} just got banned")

    @commands.Cog.listener()
    async def on_member_kick(self, guild: discord.Guild, user: discord.User):
        if channel := self.log_for(guild.id, "member_kick"):
            await channel.send(f"{user.display_name} just got kicked")

    """
    @commands.Cog.listener()
    async def on_member_remove(self, member):
        if "member_leave" in self.bot.config_cache[member.guild.id]["logged_events"]:
            embed = discord.Embed(
                title="Member left", description=f"{member} just left {member.guild.name}", color=discord.Color.red()
            )
            embed.set_footer(text=f'ID: {member.id} • {datetime.now().strftime("%c")}', icon_url=member.avatar_url)
            await self.bot.config_cache[member.guild.id]["logging_channel"].send(embed=embed)

    # message deletes --------------------------------------------------------------------------------------------------

    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload):
        channel = None
        message = payload.cached_message
        if message is None:
            channel = self.bot.get_channel(payload.channel_id)
        if message.channel or channel:
            guild = message.guild or channel.guild
            if "message_deletes" in self.bot.config_cache[guild.id]["logged_events"]:
                if message is None:
                    embed = discord.Embed(
                        description=f"**Message deleted in: {channel.mention}**",
                        color=ctx.get_colour(colour="bad_colour", message=message, bot=self.bot),
                    )
                    embed.set_footer(text=f'{datetime.now().strftime("%c")}')
                    return await self.bot.config_cache[guild.id]["logging_channel"].send(embed=embed)

                if message.author.bot:
                    return
                embed = discord.Embed(title="Message deleted", color=discord.Color.red())
                embed.add_field(
                    name="Message from:", value=f"**{message.author.mention} deleted in {message.channel.mention}**"
                )
                if message.content:
                    embed.description = f"Content:\n>>> {message.content}"
                if message.attachments:
                    if len(message.attachments) == 1:
                        if message.attachments[0].filename.endswith((".png", ".gif", ".webp,.jpg")):
                            embed.set_image(url=message.attachments[0].proxy_url)
                        else:
                            embed.set_footer(
                                text=f'ID: {message.author.id} • {datetime.now().strftime("%c")}',
                                icon_url=message.author.avatar_url,
                            )
                            return await message.guild.system_channel.send(
                                "Deleted message included a non-image attachment, "
                                "that cannot be relocated although its name was "
                                f"`{message.attachments[0].filename}`",
                                embed=embed,
                            )
                    elif len(message.attachments) > 1:
                        embed.set_footer(
                            text=f'ID: {message.author.id} • {datetime.now().strftime("%c")}',
                            icon_url=message.author.avatar_url,
                        )
                        names = [f.filename for f in message.attachments]
                        for image in message.attachments:
                            if message.attachments[0].filename.endswith((".png", ".gif", ".webp,.jpg")):
                                embed.set_image(url=image.proxy_url)
                                break
                        embed.set_footer(
                            text=f'ID: {message.author.id} • {datetime.now().strftime("%c")}',
                            icon_url=message.author.avatar_url,
                        )
                        return await message.guild.system_channel.send(
                            "Deleted message included multiple attachments, "
                            "that cannot be found :( although there names were:\n"
                            f'`{"`, `".join(names)}`',
                            embed=embed,
                        )

                embed.set_footer(
                    text=f'ID: {message.id} • {datetime.now().strftime("%c")}', icon_url=message.author.avatar_url
                )
                await self.bot.config_cache[guild.id]["logging_channel"].send(embed=embed)

    # guild creation ---------------------------------------------------------------------------------------------------

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        if "channel_updates" in self.bot.config_cache[channel.guild.id]["logged_events"]:
            embed = discord.Embed(
                title=f"#{channel.name}",
                description=f"{channel.mention} - was just created",
                color=discord.Color.green(),
            )
            embed.set_footer(text=f'ID: {channel.id} • {datetime.now().strftime("%c")}')
            await self.bot.config_cache[channel.guild.id]["logging_channel"].send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        if "channel_updates" in self.bot.config_cache[channel.guild.id]["logged_events"]:
            embed = discord.Embed(
                title=f"#{channel.name}", description=f"{channel.name} - was just deleted", color=discord.Color.red()
            )
            embed.set_footer(text=f'ID: {channel.id} • {datetime.now().strftime("%c")}')
            await self.bot.config_cache[channel.guild.id]["logging_channel"].send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_role_create(self, role):
        if "roles_updates" in self.bot.config_cache[role.guild.id]["logged_events"]:
            embed = discord.Embed(
                title="Role created", description=f"New role {role.mention} created", color=discord.Color.green()
            )
            embed.set_footer(text=f'ID: {role.id} • {datetime.now().strftime("%c")}')
            await self.bot.config_cache[role.guild.id]["logging_channel"].send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        if "roles_updates" in self.bot.config_cache[role.guild.id]["logged_events"]:
            embed = discord.Embed(
                title="Role deleted", description=f"Role {role.name} deleted", color=discord.Color.green()
            )
            embed.set_footer(text=f'ID: {role.id} • {datetime.now().strftime("%c")}')
            await self.bot.config_cache[role.guild.id]["logging_channel"].send(embed=embed)

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        if "name_update" in self.bot.config_cache[before.guild.id]["logged_events"]:
            gain = [role for role in after.roles if role not in before.roles]
            lost = [role for role in before.roles if role not in after.roles]
            if before.display_name != after.display_name:
                title = f"{before.name}'s nickname was changed"
                description = f"Before it was `{before.display_name}`, now it is `{after.display_name}`"
            elif lost:
                title = f"User {before.name}"
                description = (
                    f'Lost the role{"" if len(gain) == 1 else "s"} {", ".join([role.mention for role in lost])}'
                )
            elif gain:
                title = f"User {before.name}"
                description = (
                    f'Gained the role{"" if len(gain) == 1 else "s"} {", ".join([role.mention for role in gain])}'
                )
            else:
                return
            embed = discord.Embed(title=title, description=description, color=discord.Color.green())
            embed.set_footer(text=f'ID: {before.id} • {datetime.now().strftime("%c")}', icon_url=before.avatar_url)
            await self.bot.config_cache[before.guild.id]["logging_channel"].send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_role_update(self, before, after):
        if "role_updates" in self.bot.config_cache[before.guild.id]["logged_events"]:
            old = [perm for perm in before.permissions if perm not in after.permissions]
            if before.name != after.name:
                embed = discord.Embed(
                    title=f"Role name for {before.name} changed",
                    description=f"Before it was `{before.name}`, now it is `{after.name}`",
                    color=discord.Colour.blurple(),
                )
            elif old:
                if old[0][1]:
                    embed = discord.Embed(
                        title=f'Permission{"" if len(old) == 1 else "s"} updated for role {after.name}',
                        description=(
                            f'Lost permission{"" if len(old) == 1 else "s"} '
                            f'`{"`, `".join([perm[0].title() for perm in old])}`'
                        ),
                        color=before.colour,
                    )
                else:
                    embed = discord.Embed(
                        title=f'Permission{"" if len(old) == 1 else "s"} updated for role {after.name}',
                        description=(
                            f'Gained permission{"" if len(old) == 1 else "s"} '
                            f'`{"`, `".join([perm[0].title() for perm in old])}`'
                        ),
                        color=before.colour,
                    )
            else:
                return
            await self.bot.config_cache[before.guild.id]["logging_channel"].send(embed=embed)
    """
    # error handler ----------------------------------------------------------------------------------------------------

    @commands.Cog.listener()
    async def on_command_error(self, ctx: Context, error: commands.CommandError):
        """Command error handler"""
        raise error

        if hasattr(ctx.command, "on_error"):
            return
        error = getattr(error, "original", error)
        if isinstance(error, (commands.CommandNotFound, commands.CheckFailure)):
            return
        elif isinstance(error, commands.MissingRequiredArgument):
            title = f"{ctx.command} is missing a required argument {error.param}"
        elif isinstance(error, commands.CommandOnCooldown):
            if ctx.guild and ctx.author.guild_permissions.manage_roles:
                return await ctx.reinvoke()
            title = f"{ctx.command} is on cooldown"
        elif isinstance(error, commands.BadArgument):
            title = "Bad argument"
        elif isinstance(error, commands.NotOwner):
            title = "You are not the owner of the bot"
        elif isinstance(error, commands.MissingPermissions):
            title = f"You do not have the necessarily permissions to run {ctx.command}"
        elif isinstance(error, commands.BotMissingPermissions):
            title = "The bot is missing permissions to perform that command"
        elif isinstance(error, commands.DisabledCommand):
            title = f"{ctx.command} has been disabled."
        elif isinstance(error, commands.NoPrivateMessage):
            title = f"{ctx.command} can not be used in Private Messages"
        elif isinstance(error, discord.Forbidden):
            title = "Forbidden - Discord says no"
        elif isinstance(error, commands.CommandInvokeError):
            title = "This command errored: please hang tight, whilst I try to fix this"
            embed = discord.Embed(
                title=f"Ignoring exception in command {ctx.command}",
                description=f"```py\n{discord.utils.escape_markdown(format_exec(error))}```",
                colour=discord.Colour.red(),
            )
            embed.set_author(
                name=(
                    f'Command {ctx.command} {f"{ctx.guild.name} - {ctx.guild.id}," if ctx.guild else ""} used by '
                    f"{ctx.author.name} - {ctx.author.id}"
                ),
                icon_url=ctx.author.avatar_url,
            )
            try:
                await self.bot.get_channel(655093734525894666).send(embed=embed)
            except discord.HTTPException:
                raise error

        else:
            title = "Unspecified error: please hang tight, whilst I try take a look at this"
            embed = discord.Embed(
                title=f"Ignoring exception in command {ctx.command}",
                description=f"```py\n{discord.utils.escape_markdown(format_error(error))}```",
                colour=discord.Colour.red(),
            )
            embed.set_author(
                name=(
                    f'Command {ctx.command} {f"{ctx.guild.name} - {ctx.guild.id}," if ctx.guild else ""} used by '
                    f"{ctx.author.name} - {ctx.author.id}"
                ),
                icon_url=ctx.author.avatar_url,
            )
            try:
                await self.bot.get_channel(655093734525894666).send(embed=embed)
            except discord.HTTPException:
                raise error

        embed = discord.Embed(title=f":warning: **{title}**", color=discord.Colour.red())
        embed.add_field(name="Error message:", value=f"```py\n{type(error).__name__}: {error}\n```")
        self.bot.log.error("An error", exc_info=error)


def setup(bot):
    bot.add_cog(Listeners(bot))
