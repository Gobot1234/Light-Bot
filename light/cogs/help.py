from __future__ import annotations

import difflib
from typing import TYPE_CHECKING

import discord
from discord.ext import commands, menus
from humanize import naturaltime

from .utils.context import Context
from .utils.formats import human_join
from .utils.paginator import InfoPaginator

if TYPE_CHECKING:
    from .. import Light


class EmbedHelpCommand(commands.HelpCommand):
    context: Context
    COLOUR = discord.Colour.blurple()

    def get_ending_note(self) -> str:
        return f"Use {self.clean_prefix}{self.invoked_with} [command] for more info on a command."

    def get_command_signature(self, command: commands.Command) -> str:
        return f"{command.qualified_name} {command.signature}"

    async def send_bot_help(self, mapping: dict[commands.Cog, list[commands.Command]]) -> None:
        entries = []
        for cog, commands in mapping.items():
            if await self.filter_commands(commands):
                name = getattr(cog, "qualified_name", "No Category")
                embed = discord.Embed(title=f"{name}'s commands", colour=self.COLOUR)
                value = "\n".join(f"**{c.name}**: {c.short_doc}" for c in commands)
                if cog and cog.description:
                    value = f"{cog.description}\n\n{value}"

                embed.add_field(name="\u200b", value=value)

                embed.set_footer(text=self.get_ending_note())
                entries.append(embed)
        source = menus.ListPageSource(entries, per_page=1)
        source.format_page = lambda menu, page: page
        await InfoPaginator(source).start(self.context)

    async def send_cog_help(self, cog):
        embed = discord.Embed(title=f"{cog.qualified_name} Commands", colour=self.COLOUR)
        if cog.description:
            embed.description = cog.description

        filtered = await self.filter_commands(cog.get_commands(), sort=True)
        for command in filtered:
            embed.add_field(name=self.get_command_signature(command), value=command.short_doc or "...", inline=False)

        embed.set_footer(text=self.get_ending_note())
        await self.get_destination().send(embed=embed)

    async def send_command_help(self, command: commands.Command) -> None:
        embed = discord.Embed(title=command.qualified_name, colour=self.COLOUR)
        if command.help:
            embed.description = command.help

        if isinstance(command, commands.Group):
            filtered = await self.filter_commands(command.commands, sort=True)
            for command in filtered:
                embed.add_field(
                    name=self.get_command_signature(command), value=command.short_doc or "...", inline=False
                )

        embed.set_footer(text=self.get_ending_note())
        await self.get_destination().send(embed=embed)

    send_group_help = send_command_help

    async def send_error_message(self, error):
        ...

    async def command_not_found(self, string: str) -> None:
        ctx = self.context
        command_names = [command.name for command in ctx.bot.commands]
        close_commands = difflib.get_close_matches(string, command_names, n=2, cutoff=0.75)
        joined = "\n".join(f"`{command}`" for command in close_commands)

        embed = discord.Embed(
            title="Error!",
            description=(
                f"**Error 404:** Command or category {string!r} not found\nPerhaps you meant:\n{joined}"
                if joined
                else f"**Error 404:** Command or category {string!r} not found"
            ),
            colour=discord.Colour.red(),
        )
        await self.get_destination().send(embed=embed)


class Help(commands.Cog):
    """Need help? Try these with <@630008145162272778> help <command>"""

    def __init__(self, bot: Light):
        self.bot = bot
        self._original_help_command = bot.help_command
        bot.help_command = EmbedHelpCommand()
        bot.help_command.cog = self

    def cog_unload(self) -> None:
        self.bot.help_command = self._original_help_command

    @commands.command()
    async def avatar(self, ctx, member: discord.Member = None):
        """Get a member's avatar with links to download/view in higher quality"""
        member = member or ctx.author
        embed = discord.Embed(
            title=f"{member.display_name}'s avatar",
            description=(
                f"[PNG]({member.avatar_url_as(format='png')}) | "
                f"[JPEG]({member.avatar_url_as(format='jpg')}) | "
                f"[WEBP]({member.avatar_url_as(format='webp')})"
            ),
            colour=discord.Colour.blurple(),
        )
        if member.is_avatar_animated():
            embed.description = f"{embed.description} | [GIF]({member.avatar_url_as(format='gif')})"
        embed.set_author(name=member.display_name, icon_url=member.avatar_url)
        embed.set_image(url=member.avatar_url_as(format="gif" if member.is_avatar_animated() else "png"))
        await ctx.send(embed=embed)

    @commands.command(aliases=["member"])
    async def user(self, ctx: Context, user: discord.User = None):
        """Simple user info"""
        user = user or ctx.author

        key_to_emoji = {
            emoji_name: getattr(ctx.emoji, emoji_name) for emoji_name in ("online", "idle", "dnd", "offline")
        }

        embed = discord.Embed(title=f"Info on {user}", colour=user.colour)
        embed.set_author(name=user.display_name, icon_url=user.avatar_url)
        embed.set_thumbnail(url=user.avatar_url)
        embed.add_field(name="ID:", value=user.id)
        embed.add_field(name=f"{user.display_name} created their account:", value=naturaltime(user.created_at))

        if isinstance(user, discord.Member):
            embed.add_field(name=f"{user.display_name} joined this guild:", value=naturaltime(user.joined_at))

            if user.premium_since:
                embed.add_field(
                    name=f"{user.display_name} has been boosting since:", value=naturaltime(user.premium_since)
                )

            embed.add_field(
                name=f"Roles ({len(user.roles) - 1})",
                value=human_join([role.mention for role in reversed(user.roles[1:])], final="and",)
                if user.roles[1:]
                else "None",
            )
            embed.add_field(
                name="Status:",
                value=(
                    f"{key_to_emoji[str(user.status)]} "
                    f'{str(user.status).title().replace("Dnd", "Do Not Disturb")}\n'
                ),
            )
        await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(Help(bot))
