# -*- coding: utf-8 -*-

import discord
from discord.ext import commands, menus


class InfoPaginator(menus.MenuPages):
    """The base for all scrolling paginators"""

    @menus.button("ℹ", skip_if=menus.MenuPages._skip_double_triangle_buttons, position=menus.Last(5))
    async def show_info(self, payload):
        """Shows this message"""
        embed = discord.Embed(title="Help with this message")
        docs: list[tuple[discord.PartialEmoji, str]] = [
            (button.emoji, button.action.__doc__) for button in self.buttons.values()
        ]
        docs = "\n".join(f"{button} - {doc.title()}" for button, doc in docs)
        embed.description = f"What do the buttons do?:\n{docs}"
        return await self.message.edit(embed=embed)


class TextPaginator(InfoPaginator):
    """For paginating code blocks in an embed"""

    def __init__(self, *, text, title, python=True, **kwargs):
        super().__init__(title=title, entries=[text], per_page=1985, **kwargs)
        self.paginator = commands.Paginator(
            prefix=f'{kwargs.get("prefix", "```")}py' if python else kwargs.get("prefix", "```"),
            suffix=kwargs.get("suffix", "```"),
        )
        for line in text.splitlines():
            self.paginator.add_line(line)
        self.pages = [page for page in self.paginator.pages]

    async def send_initial_message(self, ctx, channel):
        return await ctx.send(embed=await self.invoke(0))

    @menus.button("⏹")
    async def _stop(self, payload):
        """Deletes this message"""
        return await self.message.delete()

    async def invoke(self, page):
        embed = discord.Embed(title=self.title, description=self.pages[page], colour=self.colour)
        if self.author and self.author_icon_url:
            embed.set_author(name=self.author, icon_url=self.author_icon_url)
        elif self.author:
            embed.set_author(name=self.author)
        if self.footer and self.footer_icon_url:
            embed.set_footer(text=self.footer, icon_url=self.footer_icon_url)
        elif self.footer:
            embed.set_footer(text=self.footer)
        if self.thumbnail:
            embed.set_thumbnail(url=self.thumbnail)
        return embed
