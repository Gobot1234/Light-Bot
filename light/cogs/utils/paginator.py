# -*- coding: utf-8 -*-

from typing import Any

import discord
from discord.ext import commands, menus


class InfoPaginator(menus.MenuPages):
    """Adds a "What do these buttons do?" button to a menu."""

    @menus.button("ℹ", skip_if=menus.MenuPages._skip_double_triangle_buttons, position=menus.Last())
    async def show_info(self, payload: discord.RawReactionActionEvent):
        """Shows this message"""
        embed = discord.Embed(title="Help with this message")
        docs: list[tuple[discord.PartialEmoji, str]] = [
            (button.emoji, button.action.__doc__) for button in self.buttons.values()
        ]
        docs = "\n".join(f"{button} - {doc.title()}" for button, doc in docs)
        embed.description = f"What do the buttons do?:\n{docs}"
        return await self.message.edit(embed=embed)


class TextPaginator(menus.MenuPages):
    """For paginating code blocks in an embed."""

    def __init__(self, *, text: str, title: str, **kwargs: Any):
        self.paginator = commands.Paginator(
            prefix=kwargs.get("prefix", "```"),
            suffix=kwargs.get("suffix", "```"),
            max_size=1985,
        )
        for line in text.splitlines():
            self.paginator.add_line(line)
        entries = [
            discord.Embed(title=title, description=page, colour=kwargs.get("colour")) for page in self.paginator.pages
        ]
        super().__init__(menus.ListPageSource(entries, per_page=1), delete_message_after=True, **kwargs)
