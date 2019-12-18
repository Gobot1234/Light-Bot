import asyncio
from contextlib import redirect_stdout
from datetime import datetime
from io import StringIO
from os import execv, remove
from platform import python_version
from sys import argv, executable, stderr
from traceback import print_exc
from textwrap import indent

import discord
from discord.ext import commands

from Utils.checks import is_guild_owner
from Utils.formats import format_exec


class Owner(commands.Cog):
    """These commands can only be used by the owner of the bot, or the guild owner"""

    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx):
        return ctx.guild is not None and ctx.author == ctx.guild.owner or ctx.author.id == ctx.bot.owner_id

    async def failed(self, ctx, extension, error):
        await ctx.send(f'**`ERROR:`** `{extension}` ```py\n{format_exec(error)}```')
        print(f'Failed to load extension {extension}.', file=stderr)
        print_exc(error)
        raise error

    async def cleanup_code(self, content):
        """Automatically removes code blocks from the code."""
        # remove ```py\n```
        if content.startswith('```') and content.endswith('```'):
            return '\n'.join(content.split('\n')[1:-1])

        # remove `foo`
        return content.strip('` \n')

    @commands.Cog.listener()
    async def on_ready(self):
        try:
            channel = int(open('channel.txt', 'r').read())
            await self.bot.get_channel(channel).purge(limit=2)
            await self.bot.get_channel(channel).send('Finished restarting...', delete_after=5)
            remove('channel.txt')
        except:
            pass
        print(f'\n\nLogged in as: {self.bot.user.name} - {self.bot.user.id}\nVersion: {discord.__version__} of Discord.py\n')
        print(self.bot.user.name, 'is fully loaded\nSuccessfully logged in and booted...!')

    @commands.command(aliases=['r'])
    @commands.is_owner()
    async def reload(self, ctx, *, extension):
        """You probably don't need to use this, however it can be used to reload a cog
        eg. `{prefix}reload staff`"""
        await ctx.trigger_typing()
        extension = extension.lower()
        if extension == 'all':
            reloaded = ''
            for extension in self.bot.initial_extensions:
                try:
                    self.bot.reload_extension(f'Cogs.{extension}')
                except commands.ExtensionNotLoaded:
                    try:
                        self.bot.load_extension(f'Cogs.{extension}')
                    except Exception as e:
                        await self.failed(ctx, extension, e)
                except Exception as e:
                    reloaded += f':x: `{extension}`\n'
                    await self.failed(ctx, extension, e)
                else:
                    reloaded += f':white_check_mark: `{extension}`\n'
            return await ctx.send(
                f'**`SUCCESS`** reloaded {len(self.bot.initial_extensions)} extensions \n{reloaded}')
        extension = f'Cogs.{extension}'
        try:
            self.bot.reload_extension(extension)
        except commands.ExtensionNotLoaded:
            if extension[-5] in self.bot.initial_extensions:
                try:
                    self.bot.load_extension(f'Cogs.{extension}')
                except Exception as e:
                    await self.failed(ctx, extension, e)
                else:
                    await ctx.send(f'**`SUCCESS`** :white_check_mark: `{extension}` has been reloaded')
        except Exception as e:
            await self.failed(ctx, extension, e)
        else:
            await ctx.send(f'**`SUCCESS`** :white_check_mark: `{extension}` has been reloaded')

    @commands.command(name='eval', aliases=['e'])
    @commands.is_owner()
    async def _eval(self, ctx, *, body: str):
        """This will evaluate your code-block if type some python code.
        Input is interpreted as newline separated statements.
        If the last statement is an expression, that is the return value.
        Usable globals:
          - `bot`: the bot instance
          - `discord`: the discord module
          - `commands`: the discord.ext.commands module
          - `ctx`: the invocation context
        eg. `{prefix}eval` ```py
        a = 1 + 2
        b = a * 2
        await ctx.send(a + b)```"""
        async with ctx.typing():
            self._env = {
                'bot': self.bot,
                'ctx': ctx,
                'commands': commands,
                'discord': discord,
                'self': self,
            }
            body = await self.cleanup_code(body)
            self._env.update(globals())

            stdout = StringIO()
            code = f'async def func():\n{indent(body, "    ")}'
            try:
                exec(code, self._env)
            except Exception as exc:
                await ctx.message.add_reaction('\U0000274c')
                embed = discord.Embed(title=f':x: {exc.__class__.__name__}',
                                      description=f'```py\n{format_exec(exc).split("File", 2)[2].lstrip()}```',
                                      color=discord.Colour.red())
                return await ctx.send(embed=embed)
            func = self._env['func']
            try:
                with redirect_stdout(stdout):
                    ret = await func()
            except Exception as exc:
                await ctx.message.add_reaction('\U0000274c')
                embed = discord.Embed(title=f':x: {exc.__class__.__name__}',
                                      color=discord.Colour.red())
                embed.description = f'```py\n{format_exec(exc).split("()", 1)[1].lstrip()}```'
                return await ctx.send(embed=embed)
            else:
                value = stdout.getvalue()
                await ctx.message.add_reaction('\u2705')

                if isinstance(ret, discord.File):
                    await ctx.send(file=ret)
                elif isinstance(ret, discord.Embed):
                    await ctx.send(embed=ret)
                else:
                    if not isinstance(value, str):
                        # repr all non-strings
                        value = repr(value)
                    embed = discord.Embed(description=f'Evaluation completed {ctx.author.mention} :white_check_mark:',
                                          color=discord.Colour.green())
                    if not ret:
                        self._last_result = ret
                        embed.add_field(name='Eval returned', value=f'```py\n{ret}{value}```')
                    embed.set_footer(text=f'Python {python_version()}',
                                     icon_url='https://www.python.org/static/apple-touch-icon-144x144-precomposed.png')
                    await ctx.send(embed=embed)

    @commands.command()
    @commands.is_owner()
    async def restart(self, ctx):
        """Used to restart the bot"""
        await ctx.send(f'**Restarting the Bot** {ctx.author.mention}, try not to use this often')
        open('channel.txt', 'w+').write(str(ctx.channel.id))
        execv(executable, ['python'] + argv)

    @commands.command()
    async def secret(self, ctx):
        await ctx.send(ctx.uptime)


def setup(bot):
    bot.add_cog(Owner(bot))
