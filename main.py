import asyncio
from asyncpg import create_pool
from os import listdir
from os.path import isfile, join
from sys import stderr
from traceback import print_exc
from datetime import datetime
import config
from discord.ext.commands import Bot, when_mentioned_or
from logging import getLogger, DEBUG, Formatter, FileHandler
#import jishaku

from Utils.paginator import Paginator

cogs_dir = "Cogs"


def get_prefix(bot, message):
    """A callable Prefix for our bot. This could be edited to allow per server prefixes."""
    #prefixes = bot.prefixes[message.guild.id]
    prefix = '='
    # Check to see if we are outside of a guild. e.g DM's etc.
    if message.guild is None:
        return ''
    return when_mentioned_or(prefix)(bot, message)


class EpicBot(Bot):
    def __init__(self):
        bot = super().__init__(command_prefix=get_prefix, case_insensitive=True)
        self.bot = bot

    def run(self, bot):
        bot.initial_extensions = [f[:-3] for f in listdir(cogs_dir) if isfile(join(cogs_dir, f))]
        # getting the cog files in the "Cogs" folder and removing the none .py ones
        print(f'Extensions to be loaded are {bot.initial_extensions}')
        for extension in bot.initial_extensions:
            try:
                bot.load_extension(f'Cogs.{extension}')
            except Exception as e:
                print(f'Failed to load extension {extension}. {e}', file=stderr)
                print_exc()
        #bot.load_extension('jishaku')
        bot.launch_time = datetime.utcnow()
        super().run(config.token)

    async def on_message(self, message):
        ctx = await self.get_context(message, cls=Paginator)
        await self.invoke(ctx)


def run_bot():
    bot = EpicBot()
    '''
    try: #https://gist.github.com/jegfish/cfc7b22e72426f5ced6f87caa6920fd6
        bot.pool = bot.loop.run_until_complete(create_pool(database='postgres', user='postgres', password=config.DBPassword, command_timeout=60))
    except Exception as e:
        bot.log.exception('Could not set up PostgreSQL. Exiting.')
        raise SystemExit
    '''
    bot.run(bot)


if __name__ == '__main__':
    bot = EpicBot()
    bot.log = getLogger()
    bot.log.setLevel(DEBUG)
    handler = FileHandler(filename=f'out--{datetime.now().strftime("%d-%m-%Y-%H:%S")}.log', encoding='utf-8', mode='w')
    handler.setFormatter(Formatter('%(asctime)s :  %(levelname)s : %(name)s | %(message)s'))
    bot.log.addHandler(handler)
    run_bot()
