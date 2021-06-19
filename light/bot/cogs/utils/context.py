from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord import HTTPException, PartialEmoji
from discord.ext import commands
from discord.ext.commands.view import StringView
from steam import HTTPException, User

from light.db import SteamUser

if TYPE_CHECKING:
    from light import Light


class Context(commands.Context):
    bot: Light
    view: StringView

    class emoji:
        online = PartialEmoji(name="online", id=659012420735467540)
        idle = PartialEmoji(name="idle", id=659012420672421888)
        dnd = PartialEmoji(name="dnd", id=659012419296952350)
        offline = PartialEmoji(name="offline", id=659012420273963008)

        tick = PartialEmoji(name="tick", id=688829439659737095)
        cross = PartialEmoji(name="cross", id=688829441123942416)

        discord = PartialEmoji(name="discord", id=626486432793493540)
        steam = PartialEmoji(name="steam", id=622621553800249364)
        dpy = PartialEmoji(name="dpy", id=622794044547792926)
        python = PartialEmoji(name="python", id=622621989474926622)
        postgres = PartialEmoji(name="postgres", id=689210432031817750)

        text = PartialEmoji(name="textchannel", id=661376810214359041)
        voice = PartialEmoji(name="voicechannel", id=661376810650435624)

        loading = PartialEmoji(name="loading", id=661210169870516225, animated=True)
        eq = PartialEmoji(name="eq", id=688741356524404914, animated=True)

        cpu = PartialEmoji(name="cpu", id=622621524418887680)
        ram = PartialEmoji(name="ram", id=689212498544820301)

    class colour:
        steam = discord.Colour(0x00ADEE)

    async def bool(self, value: bool) -> None:
        try:
            await self.message.add_reaction(self.emoji.tick if value else self.emoji.cross)
        except HTTPException:
            pass

    @property
    async def user(self) -> User | None:
        """The command invoker's steam account, if applicable"""
        user = await SteamUser.fetch_row(id=self.author.id)
        if user is None:
            await self.send("A helpful message about how to get this to work")
            return
        try:
            return self.bot.client.get_user(user.id64) or await self.bot.client.fetch_user(user.id64)
        except HTTPException:
            await self.send("Your account is private or steam is down")  # could actually use steam stats to tell :)
