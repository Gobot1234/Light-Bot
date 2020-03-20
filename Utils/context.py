from discord import HTTPException, PartialEmoji
from discord.ext import commands


# TODO add get_colour to here

class Contexter(commands.Context):
    """This allows the bot to use these as extended attributes of ctx
    eg.

    ctx.emoji.online
    or
    await ctx.tick.bool(value)
    """

    class Emoji:
        online = PartialEmoji(name='online', id=659012420735467540)
        idle = PartialEmoji(name='idle', id=659012420672421888)
        dnd = PartialEmoji(name='dnd', id=659012419296952350)
        offline = PartialEmoji(name='offline', id=659012420273963008)

        tick = PartialEmoji(name='tick', id=688829439659737095)
        cross = PartialEmoji(name='cross', id=688829441123942416)

        discord = PartialEmoji(name='discord', id=626486432793493540)
        dpy = PartialEmoji(name='dpy', id=622794044547792926)
        python = PartialEmoji(name='python', id=622621989474926622)
        postgres = PartialEmoji(name='postgres', id=689210432031817750)

        text = PartialEmoji(name='textchannel', id=661376810214359041)
        voice = PartialEmoji(name='voicechannel', id=661376810650435624)

        loading = PartialEmoji(name='loading', id=661210169870516225, animated=True)
        eq = PartialEmoji(name='eq', id=688741356524404914, animated=True)

        cpu = PartialEmoji(name='cpu', id=622621524418887680)
        ram = PartialEmoji(name='ram', id=689212498544820301)

    emoji = Emoji()

    async def bool(self, value):
        try:
            await self.message.add_reaction(self.emoji.tick if value else self.emoji.cross)
        except HTTPException:
            pass

