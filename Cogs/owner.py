import asyncio
import importlib
from contextlib import redirect_stdout
from io import StringIO
from platform import python_version
from subprocess import getoutput, PIPE
from textwrap import indent
from time import perf_counter

import discord
import typing
from discord.ext import commands, buttons

from Utils.checks import is_mod
from Utils.formats import format_error
from Utils.converters import strip_code_block, get_colour


class Owner(commands.Cog):
    """These commands can only be used by the owner of the bot, or the guild owner"""

    def __init__(self, bot):
        self.bot = bot
        self.first = True
        self._last_result = None

    async def cog_check(self, ctx):
        if await ctx.bot.is_owner(ctx.author):
            return True
        elif ctx.guild:
            return is_mod()
        return False

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
            entries = ['\n'.join([f'{ctx.emoji.tick} `{r}`' for r in reloaded])]
            for f in failed:
                entries.append(f'{ctx.emoji.cross} `{f[0]}` - Failed\n```py\n{format_error(f[1])}```')
            reload = buttons.Paginator(
                title=f'Reloaded `{len(reloaded)}` cog{"s" if len(reloaded) != 1 else ""} {exc}',
                colour=get_colour(ctx), entries=entries, length=1
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
                    await ctx.send(f'**`SUCCESS`** {ctx.emoji.tick} `{extension}` has been loaded')

        except Exception as e:
            self.bot.dispatch('extension_fail', ctx, extension, e)
        else:
            await ctx.send(f'**`SUCCESS`** {ctx.emoji.tick} `{extension}` has been reloaded')

    @commands.command(name='eval', aliases=['e'])
    @commands.is_owner()
    async def _eval(self, ctx, *, body: str):
        """This will evaluate your code-block if type some python code.
        Input is interpreted as newline separated statements.
        If the last statement is an expression, if the last line is returnable it will be returned.

        Usable globals:
          - `ctx`: the invocation context
          - `bot`: the bot instance
          - `discord`: the discord module
          - `commands`: the discord.ext.commands module

        **Usage**
        `{prefix}eval` ```py
        await ctx.send('lol')```
        """
        async with ctx.typing():
            env = {
                'bot': self.bot,
                'ctx': ctx,
                'discord': discord,
                'commands': commands,
                'self': self,
                '_': self._last_result
            }

            env.update(globals())
            body = strip_code_block(body)
            stdout = StringIO()
            split = body.splitlines()
            previous_lines = ''.join(split[:-1]) if split[:-1] else ''
            last_line = ''.join(split[-1:])
            if not last_line.strip().startswith('return'):
                if not last_line.strip().startswith(('import', 'print')):
                    body = f'{previous_lines}\n{" " * (len(last_line) - len(last_line.lstrip()))}return {last_line}'
            to_compile = f'async def func():\n{indent(body, "  ")}'

            try:
                start = perf_counter()
                exec(to_compile, env)
            except Exception as e:
                end = perf_counter()
                timer = (end - start) * 1000
                await ctx.bool(False)
                embed = discord.Embed(
                    title=f'{ctx.emoji.cross} {e.__class__.__name__}',
                    description=f'```py\nTraceback (most recent call last):'
                                f'{"".join(format_error(e).split("exec(to_compile, env)", 1)[0])}```',
                    color=get_colour(ctx, 'colour_bad'))
                embed.set_footer(
                    text=f'Python: {python_version()} • Process took {timer:.2f} ms to run',
                    icon_url='https://www.python.org/static/apple-touch-icon-144x144-precomposed.png')
                return await ctx.send(embed=embed)
            func = env['func']
            try:
                with redirect_stdout(stdout):
                    ret = await self.bot.loop.create_task(asyncio.wait_for(func(), 60))
            except Exception as e:
                value = stdout.getvalue()
                end = perf_counter()
                timer = (end - start) * 1000
                error = format_error(e).split('ret = await self.bot.loop.create_task'
                                              '(asyncio.wait_for(func(), 60))', 1)[1]
                await ctx.bool(False)
                embed = discord.Embed(
                    title=f'{ctx.emoji.cross} {e.__class__.__name__}',
                    description=f'```py\nTraceback (most recent call last):{value}{error}```',
                    color=get_colour(ctx, 'colour_bad'))
                embed.set_footer(
                    text=f'Python: {python_version()} • Process took {timer:.2f} ms to run',
                    icon_url='https://www.python.org/static/apple-touch-icon-144x144-precomposed.png')
                return await ctx.send(embed=embed)
            else:
                value = stdout.getvalue()
                end = perf_counter()
                timer = (end - start) * 1000

                await ctx.bool(True)
                if isinstance(ret, discord.File):
                    await ctx.send(file=ret)
                elif isinstance(ret, discord.Embed):
                    await ctx.send(embed=ret)
                else:
                    if not isinstance(value, str):
                        # repr all non-strings
                        value = repr(value)

                    embed = discord.Embed(
                        title=f'Evaluation completed {ctx.author.display_name} {ctx.emoji.tick}',
                        color=get_colour(ctx, 'colour_good'))
                    if not ret:
                        if value:
                            embed.add_field(
                                name='Eval complete',
                                value=f'```py\n{value.replace(self.bot.http.token, "[token omitted]")}```')
                    else:
                        self._last_result = ret
                        embed.add_field(
                            name='Eval returned',
                            value=f'```py\n{ret.replace(self.bot.http.token, "[token omitted]")}```')
                    embed.set_footer(
                        text=f'Python: {python_version()} • Process took {timer:.2f} ms to run',
                        icon_url='https://www.python.org/static/apple-touch-icon-144x144-precomposed.png')
                    await ctx.send(embed=embed)

    @commands.command(aliases=['logout'])
    @commands.is_owner()
    async def restart(self, ctx):
        """Used to restart the bot"""
        await ctx.message.add_reaction(ctx.emoji.loading)
        await ctx.send(f'**Restarting the Bot** {ctx.author.mention}')
        open('channel.txt', 'w+').write(str(ctx.channel.id))
        await self.bot.close()

    @commands.group()
    @commands.is_owner()
    async def git(self, ctx):
        """Git commands for pushing/pulling to repos"""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @git.command()
    async def push(self, ctx, add_first: typing.Optional[bool], *, commit_msg='None given'):
        """Push changes to the GitHub repo"""
        errored = ('fatal', 'error')
        embed = discord.Embed(title='GitHub Commit & Push', description='', colour=get_colour(ctx))
        message = await ctx.send(embed=embed)
        await message.add_reaction(ctx.emoji.loading)
        if add_first:
            add = await self.bot.loop.run_in_executor(None, getoutput, 'git add .')
            if any([word in add.split() for word in errored]):
                await message.add_reaction(ctx.emoji.cross)
                await message.remove_reaction(ctx.emoji.loading, ctx.guild.me)
                embed.description += f'{ctx.emoji.cross} **Add result:**```js\n{add}```'
                return await message.edit(embed=embed)
            else:
                add = f'```js\n{add}```' if add else ''
                embed.description += f'{ctx.emoji.tick} **Add result:**{add}'
            await message.edit(embed=embed)

        commit = await self.bot.loop.run_in_executor(None, getoutput, f'git commit -m "{commit_msg}"')
        if any([word in commit.split() for word in errored]):
            await message.add_reaction(ctx.emoji.cross)
            await message.remove_reaction(ctx.emoji.loading, ctx.guild.me)
            embed.description = f'{ctx.emoji.cross} **Commit result:**```js\n{commit}```'
            return await message.edit(embed=embed)
        else:
            embed.description = f'{ctx.emoji.tick} **Commit result:**```js\n{commit}```'
        await message.edit(embed=embed)

        push = await self.bot.loop.run_in_executor(None, getoutput, 'git push')
        if any([word in push.split() for word in errored]):
            await message.add_reaction(ctx.emoji.cross)
            await message.remove_reaction(ctx.emoji.loading, ctx.guild.me)
            embed.description += f'\n{ctx.emoji.cross} **Push result:**```js\n{push}```'
            return await message.edit(embed=embed)
        else:
            await message.add_reaction(ctx.emoji.tick)
            embed.description += f'\n{ctx.emoji.tick} **Push result:**```js\n{push}```'

        await message.remove_reaction(ctx.emoji.loading, ctx.guild.me)
        await message.edit(embed=embed)

    @git.command()
    async def pull(self, ctx, hard: bool = False):
        """Pull any changes from the GitHub repo"""
        errored = ('fatal', 'error')
        embed = discord.Embed(title=f'GitHub {"Hard" if hard else ""} Pull', description='', colour=get_colour(ctx))
        message = await ctx.send(embed=embed)
        await message.add_reaction(ctx.emoji.loading)
        if hard:
            reset = await self.bot.loop.run_in_executor(None, getoutput, 'git reset --hard HEAD')
            if any([word in reset.split() for word in errored]):
                await message.add_reaction(ctx.emoji.cross)
                await message.remove_reaction(ctx.emoji.loading, ctx.guild.me)
                embed.description += f'\n{ctx.emoji.cross} **Reset result:**```js\n{reset}```'
                return await message.edit(embed=embed)
            else:
                embed.description += f'\n{ctx.emoji.tick} **Reset result:**```js\n{reset}```'
        pull = await self.bot.loop.run_in_executor(None, getoutput, 'git pull')
        if any([word in pull.split() for word in errored]):
            await message.add_reaction(ctx.emoji.cross)
            await message.remove_reaction(ctx.emoji.loading, ctx.guild.me)
            embed.description += f'\n{ctx.emoji.cross} **Pull result:**```js\n{pull}```'
            return await message.edit(embed=embed)
        else:
            await ctx.bool(True)
            embed.description += f'\n{ctx.emoji.tick} **Pull result:**```js\n{pull}```'
        await message.remove_reaction(ctx.emoji.loading, ctx.guild.me)
        await message.edit(embed=embed)


    @commands.command()
    @commands.is_owner()
    async def reloadutil(self, ctx, name: str):
        """Reload a Utils module"""
        try:
            module_name = importlib.import_module(f"Utils.{name}")
            importlib.reload(module_name)
        except ModuleNotFoundError:
            return await ctx.send(f'Couldn\'t find module named **{name}** in Utils.')
        except Exception as e:
            await ctx.send(f'Module **{name}** returned error and was not reloaded...\n```py\n{format_error(e)}```')
        else:
            await ctx.send(f"Reloaded module **{name}**")


def setup(bot):
    bot.add_cog(Owner(bot))
