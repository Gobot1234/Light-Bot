from typing import TypeVar

import discord
from discord.ext import menus

T = TypeVar("T")

class InfoPaginator(menus.MenuPages[T]):
    """Adds a "What do these buttons do?" button to a menu."""

    @menus.button("ℹ", skip_if=menus.MenuPages._skip_double_triangle_buttons, position=menus.Last())
    async def show_info(self, payload: discord.RawReactionActionEvent):
        """Shows this message"""
        embed = discord.Embed(title="Help with this message")
        docs = [(button.emoji, button.action.__doc__) for button in self.buttons.values()]
        docs = "\n".join(f"{button} - {doc.title()}" for button, doc in docs)
        embed.description = f"What do the buttons do?:\n{docs}"
        return await self.message.edit(embed=embed)
