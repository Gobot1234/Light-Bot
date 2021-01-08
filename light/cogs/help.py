from __future__ import annotations

import difflib
from typing import TYPE_CHECKING

import discord
from discord.ext import commands, menus

from .utils.context import Context
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

    def format_help(self, string: str) -> str:
        return string.format(clean_prefix=self.clean_prefix, bot_mention=self.context.bot.user.mention,)

    async def send_bot_help(self, mapping: dict[commands.Cog, list[commands.Command]]) -> None:
        entries = []
        for cog, commands in mapping.items():
            if await self.filter_commands(commands):
                name = getattr(cog, "qualified_name", "No Category")
                embed = discord.Embed(title=f"{name}'s commands", colour=self.COLOUR)
                value = "\n".join(f"**{c.name}**: {self.format_help(c.short_doc)}" for c in commands)
                if cog and cog.description:
                    value = f"{cog.description}\n\n{value}"

                embed.add_field(name="\u200b", value=value)

                embed.set_footer(text=self.get_ending_note())
                entries.append(embed)
        source = menus.ListPageSource(entries, per_page=1)
        source.format_page = lambda menu, page: page
        await InfoPaginator(source, delete_message_after=True).start(self.context)

    async def send_cog_help(self, cog: commands.Cog):
        embed = discord.Embed(title=f"{cog.qualified_name} Commands", colour=self.COLOUR)
        if cog.description:
            embed.description = self.format_help(self.format_help(cog.description))

        filtered = await self.filter_commands(cog.get_commands(), sort=True)
        for command in filtered:
            embed.add_field(
                name=self.get_command_signature(command),
                value=self.format_help(command.short_doc) or "...",
                inline=False,
            )

        embed.set_footer(text=self.get_ending_note())
        await self.get_destination().send(embed=embed)

    async def send_command_help(self, command: commands.Command) -> None:
        embed = discord.Embed(title=command.qualified_name, colour=self.COLOUR)
        if command.help:
            embed.description = command.help.format(clean_prefix=self.clean_prefix)

        if isinstance(command, commands.Group):
            filtered = await self.filter_commands(command.commands, sort=True)
            for command in filtered:
                embed.add_field(
                    name=self.get_command_signature(command),
                    value=self.format_help(command.short_doc) or "...",
                    inline=False,
                )

        embed.set_footer(text=self.get_ending_note())
        await self.get_destination().send(embed=embed)

    send_group_help = send_command_help

    async def send_error_message(self, error: Exception):
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


def setup(bot: Light) -> None:
    bot._original_help_command = bot.help_command
    bot.help_command = EmbedHelpCommand()


def teardown(bot: Light) -> None:
    bot.help_command = bot._original_help_command  # noqa
