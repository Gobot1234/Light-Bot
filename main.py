import asyncio
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from traceback import print_exc

import aiohttp
import discord
from asyncpg import create_pool
from discord.ext import commands

import config
from Utils.context import Contexter
from Utils.formats import format_error

__version__ = '0.0.2'


def get_prefix(bot, message):
    if message.guild is None:
        prefixes = ['=', '']
    else:
        prefixes = bot.config_cache[message.guild.id]['prefixes']
    return commands.when_mentioned_or(*prefixes)(bot, message)


class Light(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=get_prefix, case_insensitive=True)
        self.first = True
        self.to_leave = []

        self.log = None
        self.db = None
        self.config_cache = {}
        self.owner_ids = {340869611903909888, 468518451728613408}
        self.session = None
        self.initial_extensions = None
        self.launch_time = 0

    async def get_context(self, message, *, cls=None):
        return await super().get_context(message, cls=cls or Contexter)

    def setup_logging(self):
        log_level = logging.WARNING
        format_string = '%(asctime)s : %(name)s - %(levelname)s | %(message)s'
        log_format = logging.Formatter(format_string)

        log_file = Path("logs", "bot.log")
        log_file.parent.mkdir(exist_ok=True)
        file_handler = logging.FileHandler(filename=f'logs/out--{datetime.now().strftime("%d-%m-%Y")}.log',
                                 encoding='utf-8', mode='w')
        file_handler.setFormatter(log_format)

        root_log = logging.getLogger()
        root_log.setLevel(log_level)
        root_log.addHandler(file_handler)

        logging.getLogger("discord").setLevel(logging.WARNING)
        logging.getLogger("websockets").setLevel(logging.WARNING)
        self.log = logging.getLogger('Light')
        self.log.info('Finished setting up logging')

    async def start(self):
        self.setup_logging()
        self.log.info('Setting up DB')
        try:
            self.db = await create_pool(database='postgres', user='postgres', password='DataBase', command_timeout=60)
        except Exception as e:
            self.log.exception(f'Could not set up PostgreSQL. Exiting...')
            self.log.exception(format_error(e))
            return await asyncio.sleep(120)
        else:
            configs = await self.db.fetch("""SELECT * FROM config;""")
            for guild in configs:
                if guild['blacklisted']:
                    self.to_leave.append(guild['guild_id'])
                    continue
                self.config_cache[guild['guild_id']] = {
                    "prefixes": guild['prefixes'],
                    "colour": guild['colour'],
                    "colour_bad": guild['colour_bad'],
                    "colour_good": guild['colour_good'],
                    "join_message": guild['join_message'],
                    "logging_channel": self.get_channel(guild['logging_channel']),
                    "logged_events": guild['logged_events']
                }

            self.log.info('Database fully setup')

        self.session = aiohttp.ClientSession()
        self.initial_extensions = [f[:-3] for f in os.listdir('Cogs') if os.path.isfile(os.path.join('Cogs', f))]
        print(f'Extensions to be loaded are {", ".join(self.initial_extensions)}')
        self.log.info(f'Extensions to be loaded are {", ".join(self.initial_extensions)}')

        for extension in self.initial_extensions:
            try:
                self.load_extension(f'Cogs.{extension}')
            except Exception as e:
                self.dispatch('extension_fail', extension, None, e, send=False)
                print(f'Failed to load extension {extension}. {e}', file=sys.stderr)
                print_exc()
            else:
                self.dispatch('extension_load', extension)
        self.load_extension('jishaku')

        self.launch_time = datetime.utcnow()
        try:
            await super().start(config.token)
        finally:
            print('Shutting Down')
            await self.close()

    async def on_command(self, ctx):
        message = \
            f'''
Author : "{ctx.author}" - {ctx.author.id}
Guild  : "{ctx.guild.name if ctx.guild else 'DMS'}" {f"- {ctx.guild.id}" if ctx.guild else ''}
Channel: "{ctx.channel.name if ctx.guild else 'DMS'}" {f"- {ctx.channel.id}" if ctx.guild else ''}
Message: "{ctx.message.clean_content}"'''
        self.log.debug(message)

    async def on_extension_load(self, extension):
        self.log.info(f'Loaded {extension} cog')

    async def on_extension_reload(self, extension):
        self.log.info(f'Reloaded {extension} cog')

    async def on_extension_fail(self, messageable, extension, error, send=True):
        self.log.error(f'Failed to load extension {extension}.')
        self.log.error(format_error(error))
        if send:
            await messageable.send(f'**`ERROR:`** `{extension}` ```py\n{format_error(error)}```')
        raise error

    async def on_ready(self):
        if self.first:
            for guild in self.to_leave:
                await self.get_guild(guild).leave()
            info = await self.application_info()
            self.owner = info.owner
            try:
                channel = self.get_channel(int(open('channel.txt', 'r').read()))
                os.remove('channel.txt')
            except FileNotFoundError:
                pass
            else:
                if channel:
                    deleted = 0
                    async for m in channel.history(limit=50):
                        if m.author == self.user and deleted < 2:
                            await m.delete()
                            deleted += 1
                        if m.author == self.owner and m.content == (f'=logout' or f'=restart'):
                            try:
                                await m.delete()
                            except discord.Forbidden:
                                pass
                    await channel.send('Finished restarting...', delete_after=10)
            print(f'Successfully logged in as {self.user.name} and booted...!')
            self.log.info(f'Successfully logged in as {self.user.name} and booted...!')
            self.first = False

    async def on_connect(self):
        print(f'Logging in as: {self.user.name} V.{__version__} - {self.user.id} -- '
              f'Version: {discord.__version__} of Discord.py')
        self.log.info(f'Logging in as: {self.user.name} V.{__version__} - {self.user.id}')
        self.log.info(f'Version: {discord.__version__} of Discord.py')

    async def close(self):
        self.log.info('About to close the DB')
        await self.db.close()
        self.log.info('About to close the ClientSession')
        await self.session.close()
        self.log.info('About to close the bot')
        await super().close()


if __name__ == '__main__':
    bot = Light()
    try:
        bot.loop.run_until_complete(bot.start())
    finally:
        bot.log.info('Finally shutdown')
        bot.log.info('Raising a System Exit')
        bot.loop.close()
        raise SystemExit
