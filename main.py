import asyncio
import discord

from asyncpg import create_pool
from os import listdir
from os.path import isfile, join
from sys import stderr, exit
from traceback import print_exc
from datetime import datetime
import config
from discord.ext.commands import Bot, when_mentioned_or
from logging import getLogger, DEBUG, Formatter, FileHandler, StreamHandler, ERROR
# import jishaku

from Utils.paginator import Paginator


def get_prefix(bot, message):
    """A callable Prefix for our bot"""
    # Check to see if we are outside of a guild. e.g DM's etc.
    if message.guild is None:
        prefixes = ['=', '']
    else:
        prefixes = bot.config_cache[message.guild.id]['prefixes']
    return when_mentioned_or(*prefixes)(bot, message)


class Light(Bot):
    def __init__(self):
        self.bot = super().__init__(command_prefix=get_prefix, case_insensitive=True)

    def run(self, bot):
        bot.initial_extensions = [f[:-3] for f in listdir('Cogs') if isfile(join('Cogs', f))]
        print(f'Extensions to be loaded are {", ".join(bot.initial_extensions)}')
        bot.log.info(f'Extensions to be loaded are {", ".join(bot.initial_extensions)}')
        for extension in bot.initial_extensions:
            try:
                bot.load_extension(f'Cogs.{extension}')
            except Exception as e:
                print(f'Failed to load extension {extension}. {e}', file=stderr)
                print_exc()
        # bot.load_extension('jishaku')
        bot.launch_time = datetime.utcnow()
        super().run(config.token)

    async def get_context(self, message, *, cls=None):
        return await super().get_context(message, cls=cls or Paginator)

    async def on_command(self, ctx):
        ctx.bot.log.info(f'{ctx.author} - {ctx.author.id} {f"| {ctx.guild.name} - {ctx.guild.id}" if ctx.guild else ""} | '
                     f'"{ctx.message.clean_content}"')


def setup_logging(bot):
    bot.log = getLogger('Light')
    bot.log.setLevel(DEBUG)
    fh = FileHandler(filename=f'out--{datetime.now().strftime("%d-%m-%Y")}.log', encoding='utf-8', mode='w')
    fh.setLevel(DEBUG)
    ch = StreamHandler()
    ch.setLevel(ERROR)
    formatter = Formatter('%(asctime)s : %(name)s - %(levelname)s | %(message)s')
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)
    bot.log.addHandler(fh)
    bot.log.addHandler(ch)
    bot.log.info('Finished setting up logging')


async def start_db(bot):
    try:  # https://gist.github.com/jegfish/cfc7b22e72426f5ced6f87caa6920fd6
        bot.log.info('Setting up DB')
        bot.db = await create_pool(database='postgres', user='postgres', password='DataBase', command_timeout=60)
    except:
        bot.log.exception(f'Could not set up PostgreSQL. Exiting...')
        await asyncio.sleep(120)
        exit()
    else:
        bot.config_cache = {}
        configs = await bot.db.fetch("""SELECT * FROM config;""")
        for guild in configs:
            if guild['blacklisted']:
                return bot.get_guild(guild['guild_id']).leave()
            bot.config_cache[guild['guild_id']] = {
                "prefixes": guild['prefixes'],
                "colour": guild['colour'],
                "colour_bad": guild['colour_bad'],
                "colour_good": guild['colour_good'],
                "join_message": guild['join_message'],
                "logging_channel": bot.get_channel(guild['logging_channel']),
                "logged_events": guild['logged_events']
            }

        bot.log.info('Database fully setup')


def run_bot(bot):
    setup_logging(bot)
    bot.loop.run_until_complete(start_db(bot))
    bot.launch_time = datetime.utcnow()
    bot.log.info(f'Logging in as {bot.user}')
    try:
        bot.run(bot)
    except (KeyboardInterrupt, RuntimeError) as e:
        bot.loop.run_until_complete(shutdown(bot))
    finally:
        print('Shutting down')
        bot.log.info('Finally shutdown')
        bot.log.info('Raising a System Exit')
        exit()


# add a client session and description idk

async def shutdown(bot):
    bot.log.info('About to close the DB')
    await bot.db.close()
    bot.log.info('About to close the ClientSession')
    await bot.session.close()
    bot.log.info('About to close the bot')
    await bot.logout()


if __name__ == '__main__':
    bot = Light()
    run_bot(bot)
