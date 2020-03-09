import asyncio
from datetime import datetime
from logging import getLogger, DEBUG, Formatter, FileHandler, StreamHandler, ERROR
from os import listdir
from os.path import isfile, join
from sys import stderr
from traceback import print_exc

import aiohttp
from asyncpg import create_pool
from discord.ext import commands

import config
from Utils.formats import format_error


# import jishaku

def get_prefix(bot, message):
    if message.guild is None:
        prefixes = ['=', '']
    else:
        prefixes = bot.config_cache[message.guild.id]['prefixes']
    return commands.when_mentioned_or(*prefixes)(bot, message)


class Light(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=get_prefix, case_insensitive=True)

    def setup_logging(self):
        self.log = getLogger('Light')
        self.log.setLevel(DEBUG)
        fh = FileHandler(filename=f'out--{datetime.now().strftime("%d-%m-%Y")}.log', encoding='utf-8', mode='w')
        fh.setLevel(DEBUG)
        ch = StreamHandler()
        ch.setLevel(ERROR)
        formatter = Formatter('%(asctime)s : %(name)s - %(levelname)s | %(message)s')
        fh.setFormatter(formatter)
        ch.setFormatter(formatter)
        self.log.addHandler(fh)
        self.log.addHandler(ch)
        self.log.info('Finished setting up logging')

    async def start(self):
        self.setup_logging()
        await self.start_db()
        self.session = aiohttp.ClientSession()

        self.initial_extensions = [f[:-3] for f in listdir('Cogs') if isfile(join('Cogs', f))]
        print(f'Extensions to be loaded are {", ".join(self.initial_extensions)}')
        self.log.info(f'Extensions to be loaded are {", ".join(self.initial_extensions)}')

        for extension in self.initial_extensions:
            try:
                self.load_extension(f'Cogs.{extension}')
            except Exception as e:
                self.dispatch('extension_fail', extension, None, send=False)
                print(f'Failed to load extension {extension}. {e}', file=stderr)
                print_exc()
            else:
                self.dispatch('extension_load', extension)
        # self.load_extension('jishaku')

        self.launch_time = datetime.utcnow()
        try:
            await super().start(config.token)
        finally:
            print('Shutting Down')
            await self.shutdown()

    async def on_command(self, ctx):
        self.log.info(
            f'''
            Author : "{ctx.author}" - "{ctx.author.id}"\n
            Guild  : "{ctx.guild.name if ctx.guild else 'DMS'}" - {f"{ctx.guild.id}" if ctx.guild else ''}\n
            Channel: "{ctx.channel.name if ctx.guild else 'DMS'}" - {f"{ctx.channel.id}" if ctx.guild else ''}\n
            Message: "{ctx.message.clean_content}"
            '''
        )

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

    async def start_db(self):
        try:
            self.log.info('Setting up DB')
            self.db = await create_pool(database='postgres', user='postgres', password='DataBase', command_timeout=60)
        except Exception as e:
            self.log.exception(f'Could not set up PostgreSQL. Exiting...')
            self.log.exception(format_error(e))
            await asyncio.sleep(120)
            raise SystemExit
        else:
            self.config_cache = {}
            configs = await self.db.fetch("""SELECT * FROM config;""")
            for guild in configs:
                if guild['blacklisted']:
                    return self.get_guild(guild['guild_id']).leave()
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

    async def shutdown(self):
        self.log.info('About to close the DB')
        await self.db.close()
        self.log.info('About to close the ClientSession')
        await self.session.close()
        self.log.info('About to close the bot')
        await self.logout()


if __name__ == '__main__':
    bot = Light()
    try:
        bot.loop.run_until_complete(bot.start())
    finally:
        bot.log.info('Finally shutdown')
        bot.log.info('Raising a System Exit')
        bot.loop.close()
        raise SystemExit
