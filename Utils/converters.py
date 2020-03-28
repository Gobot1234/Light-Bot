import re
from io import BytesIO
from typing import Optional, Union, List

import aiohttp
import discord
from discord.ext import commands

URL_REGEX = re.compile(r'(?:http[s]?://|www\.)(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*(),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+')


def get_colour(ctx: commands.Context = None, colour: str = 'colour', *,
               message: discord.Message = None, bot: commands.Bot = None) -> discord.Colour:
    """Get the relevant colour for the guild or in dms"""
    if message and bot:
        return bot.config_cache[message.guild.id][colour]
    else:
        if ctx.guild:
            return ctx.bot.config_cache[ctx.guild.id][colour]
        elif colour == 'good':
            return discord.Colour.green()
        elif colour == 'bad':
            return discord.Colour.red()
        else:
            return discord.Colour.blurple()


def strip_code_block(content) -> str:
    """Automatically removes code blocks from the code."""
    # remove ```py\n```
    if content.startswith('```') and content.endswith('```'):
        return '\n'.join(content.split('\n')[1:-1])

    # remove `foo`
    return content.strip('` \n')


class GuildConverter(commands.Converter):
    async def convert(self, ctx, argument) -> discord.Guild:
        if str(argument).isdigit():
            guild: discord.Guild = ctx.bot.get_guild(argument)
        else:
            guilds: List[discord.Guild] = [guild for guild in ctx.bot.guilds if guild.name == argument]
            if len(guilds) > 1:
                raise commands.BadArgument(f'Multiple guilds with that name found use its id instead')
            if guilds:
                return guilds[0]
            raise commands.BadArgument(f'Guild "{argument}" not found')

        if guild is None:
            raise commands.BadArgument(f'Guild "{argument}" not found')
        return guild


class ImageConverter(commands.Converter):
    async def convert(self, ctx, argument, to_file=True) -> Union[BytesIO, discord.File]:
        if isinstance(argument, discord.Attachment):
            return await argument.to_file()
        if URL_REGEX.match(argument):
            if not argument.startswith(('http', 'https')):
                argument = 'http://' + argument

            resp = await ctx.bot.session.get(argument)
            url = argument.strip('http://').strip('https://').split('?')[0]
            name, extension = re.findall(r'/(?P<name>(?:.*?))\.(?P<extension>(?:.*))', url)[0]
            filename = f'{name}.{extension}'
            try:
                bytes_io = BytesIO(await resp.read())
            except aiohttp.ContentTypeError:
                raise commands.BadArgument(f'No image was able to be found at "{argument}"')
            except aiohttp.ClientConnectorCertificateError:
                argument = 'https://' + argument[-7:]
                await self.convert(ctx, argument)
            else:
                if not to_file:
                    return bytes_ioi
                return discord.File(bytes_io, filename=filename)
        else:
            raise commands.BadArgument(f'Image "{argument}" is not in a recognised format')
