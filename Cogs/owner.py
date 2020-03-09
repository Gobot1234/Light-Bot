import asyncio
import importlib
from contextlib import redirect_stdout
from io import StringIO
from os import remove
from platform import python_version
from subprocess import getoutput
from textwrap import indent
from time import perf_counter

import discord
from discord import Colour, Embed, File
from discord.ext import commands, buttons

from Utils.checks import is_guild_owner
from Utils.formats import format_error

__version__ = '0.0.2'


class Owner(commands.Cog):
    """These commands can only be used by the owner of the bot, or the guild owner"""

    def __init__(self, bot):
        self.bot = bot
        self.first = True

    async def __ainit__(self):
        info = await self.bot.application_info()
        self.bot.owner = info.owner
        try:
            channel = self.bot.get_channel(int(open('channel.txt', 'r').read()))
            remove('channel.txt')
        except FileNotFoundError:
            pass
        else:
            if channel:
                deleted = 0
                async for m in channel.history(limit=3):
                    if m.author == self.bot.user and deleted < 2:
                        await m.delete()
                        deleted += 1
                    if m.author == self.bot.owner and m.content == (f'=logout' or f'=restart'):
                        try:
                            await m.delete()
                        except discord.Forbidden:
                            pass
                await channel.send('Finished restarting...', delete_after=10)
        print(f'Successfully logged in as {self.bot.user.name} and booted...!')
        self.bot.log.info(f'Successfully logged in as {self.bot.user.name} and booted...!')

    async def cog_check(self, ctx):
        if ctx.author == ctx.bot.owner:
            return True
        elif ctx.guild:
            return is_guild_owner(ctx)
        return False

    def cleanup_code(self, content):
        """Automatically removes code blocks from the code."""
        # remove ```py\n```
        if content.startswith('```') and content.endswith('```'):
            return '\n'.join(content.split('\n')[1:-1])

        # remove `foo`
        return content.strip('` \n')

    @commands.Cog.listener()
    async def on_ready(self):
        if self.first:
            await self.__ainit__()
            self.first = False

    @commands.Cog.listener()
    async def on_connect(self):
        print(f'Logging in as: {self.bot.user.name} V.{__version__} - {self.bot.user.id} -- '
              f'Version: {discord.__version__} of Discord.py')
        self.bot.log.info(f'Logging in as: {self.bot.user.name} V.{__version__} - {self.bot.user.id}')
        self.bot.log.info(f'Version: {discord.__version__} of Discord.py')

    @commands.command(aliases=['r'])
    @commands.is_owner()
    async def reload(self, ctx, *, extension=None):
        """Reload an extension

        eg. `{prefix}reload staff`"""
        await ctx.trigger_typing()
        if extension is None:
            reloaded = []
            failed = []
            for extension in self.bot.initial_extensions:
                try:
                    self.bot.reload_extension(f'Cogs.{extension}')
                    self.bot.dispatch('extension_reload', extension)
                except commands.ExtensionNotLoaded:
                    try:
                        self.bot.load_extension(f'Cogs.{extension}')

                    except Exception as e:
                        self.bot.dispatch('extension_fail', ctx, extension, e, send=False)
                        failed.append((extension, e))

                    else:
                        self.bot.dispatch('extension_load', extension)
                        reloaded.append(extension)
                except Exception as e:
                    self.bot.dispatch('extension_fail', ctx, extension, e, send=False)
                    failed.append((extension, e))
                else:
                    self.bot.dispatch('extension_load', extension)
                    reloaded.append(extension)
            exc = f'\nFailed to load {len(failed)} cog{"s" if len(failed) > 1 else ""} ' \
                  f'(`{"`, `".join(fail[0] for fail in failed)}`)' if len(failed) > 0 else ""
            entries = ['\n'.join([f'<:tick:626829044134182923> `{r}`' for r in reloaded])]
            for f in failed:
                entries.append(f'<:goodcross:626829085682827266> `{f[0]}` - Failed\n```py\n{format_error(f[1])}```')
            reload = buttons.Paginator(
                title=f'Reloaded `{len(reloaded)}` cog{"s" if len(reloaded) > 1 else ""} {exc}',
                colour=discord.Colour.blurple(), entries=entries, length=1
            )
            return await reload.start(ctx)
        try:
            self.bot.reload_extension(f'Cogs.{extension}')
        except commands.ExtensionNotLoaded:
            if extension in self.bot.initial_extensions:
                try:
                    self.bot.load_extension(f'Cogs.{extension}')
                    self.bot.dispatch('extension_reload', extension)

                except Exception as e:
                    self.bot.dispatch('extension_fail', ctx, extension, e)
                else:
                    await ctx.send(f'**`SUCCESS`** <:tick:626829044134182923> `{extension}` has been loaded')

        except Exception as e:
            self.bot.dispatch('extension_fail', ctx, extension, e)
        else:
            await ctx.send(f'**`SUCCESS`** <:tick:626829044134182923> `{extension}` has been reloaded')

    @commands.command(name='eval', aliases=['e'])
    @commands.is_owner()
    async def _eval(self, ctx, *, body: str):
        """This will evaluate your code-block if type some python code.
        Input is interpreted as newline separated statements.
        If the last statement is an expression, that is the return value.
        Usable globals:
          - `discord`: the discord module
          - `bot`: the bot instance
          - `commands`: the discord.ext.commands module
          - `ctx`: the invocation context

        eg. `{prefix}eval` ```py
        await ctx.send('lol')```
        """
        async with ctx.typing():
            env = {
                'bot': self.bot,
                'ctx': ctx,
                'discord': discord,
                'commands': commands,
                'self': self,
            }

            env.update(globals())
            body = self.cleanup_code(body)
            stdout = StringIO()
            to_compile = f'async def func():\n{indent(body, "  ")}'

            try:
                start = perf_counter()
                exec(to_compile, env)
            except Exception as e:
                end = perf_counter()
                await ctx.message.add_reaction(':goodcross:626829085682827266')
                embed = Embed(title=f'<:goodcross:626829085682827266> {type(e).__name__}',
                              description=format_error(e), color=Colour.red())
                embed.set_footer(
                    text=f'Python: {python_version()} • Process took {round((end - start) * 1000, 2)} ms to run',
                    icon_url='https://www.python.org/static/apple-touch-icon-144x144-precomposed.png')
                return await ctx.send(embed=embed)
            func = env['func']
            try:
                with redirect_stdout(stdout):
                    ret = await asyncio.create_task(asyncio.wait_for(func(), 60, loop=self.bot.loop))
            except Exception as e:
                value = stdout.getvalue()
                end = perf_counter()

                await ctx.message.add_reaction(':goodcross:626829085682827266')
                embed = Embed(title=f'<:goodcross:626829085682827266> {type(e).__name__}',
                              description=f'{value}{format_error(e)}',
                              color=Colour.red())
                embed.set_footer(
                    text=f'Python: {python_version()} • Process took {round((end - start) * 1000, 2)} ms to run',
                    icon_url='https://www.python.org/static/apple-touch-icon-144x144-precomposed.png')
                return await ctx.send(embed=embed)
            else:
                value = stdout.getvalue()
                end = perf_counter()

                await ctx.message.add_reaction(':tick:626829044134182923')
                if isinstance(ret, File):
                    await ctx.send(file=ret)
                elif isinstance(ret, Embed):
                    await ctx.send(embed=ret)
                else:
                    if not isinstance(value, str):
                        # repr all non-strings
                        value = repr(value)

                    embed = Embed(title=f'Evaluation completed {ctx.author.display_name} <:tick:626829044134182923>',
                                  color=Colour.green())
                    if ret is None:
                        if value:
                            embed.add_field(name='Eval complete', value=f'```py\n{value}```')
                    else:
                        self._last_result = ret
                        embed.add_field(name='Eval returned', value=f'```py\n{value}{ret}```')
                    embed.set_footer(
                        text=f'Python: {python_version()} • Process took {round((end - start) * 1000, 2)} ms to run',
                        icon_url='https://www.python.org/static/apple-touch-icon-144x144-precomposed.png')
                    await ctx.send(embed=embed)

    @commands.command(aliases=['logout'])
    @commands.is_owner()
    async def restart(self, ctx):
        """Used to restart the bot"""
        await ctx.message.add_reaction('a:loading:661210169870516225')
        await ctx.send(f'**Restarting the Bot** {ctx.author.mention}')
        open('channel.txt', 'w+').write(str(ctx.channel.id))
        await self.bot.close()

    @commands.command()
    async def secret(self, ctx):
        await ctx.send(ctx.uptime)

    @commands.group()
    @commands.is_owner()
    async def git(self, ctx):
        """Git commands for pushing/pulling to repos"""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @git.command()
    async def push(self, ctx, version=f'V.{__version__}', *, commit_msg='None given'):
        """Push changes to the GitHub repo"""
        await ctx.message.add_reaction('<a:loading:661210169870516225>')
        add = await self.bot.loop.run_in_executor(None, getoutput, 'git add .')
        commit = await self.bot.loop.run_in_executor(None, getoutput, f'git commit -m "{version}" -m "{commit_msg}"')
        push = await self.bot.loop.run_in_executor(None, getoutput, 'git push')
        if 'error: failed' in push:
            await ctx.message.add_reaction(':goodcross:626829085682827266')
        else:
            await ctx.message.add_reaction(':tick:626829044134182923')
        out = buttons.Paginator(title=f'GitHub push output', colour=discord.Colour.blurple(), embed=True, timeout=90,
                                entries=[f'**Commit:** ```js\n{commit}```', f'**Push:** ```js\n{push}```'])
        await out.start(ctx)

    @git.command()
    async def pull(self, ctx):
        """Pull from the GitHub repo"""
        await ctx.message.add_reaction('<a:loading:661210169870516225>')
        reset = await self.bot.loop.run_in_executor(None, getoutput, 'git reset --hard HEAD')
        pull = await self.bot.loop.run_in_executor(None, getoutput, 'git pull')
        await ctx.message.add_reaction(':tick:626829044134182923')
        out = buttons.Paginator(title=f'GitHub pull output', colour=self.bot.color, embed=True, timeout=90,
                                entries=[f'**Reset:** ```js\n{reset}```', f'**Pull:** ```js\n{pull}```'])
        await out.start(ctx)

    @commands.command()
    @commands.is_owner()
    async def reloadutil(self, ctx, name: str):
        """Reload a Utils module"""
        try:
            module_name = importlib.import_module(f"Utils.{name}")
            importlib.reload(module_name)
        except ModuleNotFoundError:
            return await ctx.send(f'Couldn\'t find module named **{name}**')
        except Exception as e:
            await ctx.send(f'Module **{name}** returned error and was not reloaded...\n```py\n{format_error(e)}```')
        else:
            await ctx.send(f"Reloaded module **{name}**")


def setup(bot):
    bot.add_cog(Owner(bot))
