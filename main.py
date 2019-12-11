from asyncpg import create_pool
from os import listdir
from os.path import isfile, join
from sys import stderr
from traceback import print_exc
from datetime import datetime

import config
from discord.ext.commands import Bot, when_mentioned_or
import jishaku

cogs_dir = "Cogs"

# async def run():
    # bot.pg_con = await create_pool(database='postgres', user='postgres', password=config.DBPassword)


def get_prefix(bot, message):
    """A callable Prefix for our bot. This could be edited to allow per server prefixes."""

    # Notice how you can use spaces in prefixes. Try to keep them simple though. lul
    prefixes = ['=']

    # Check to see if we are outside of a guild. e.g DM's etc.
    if message.guild is None:
        # Only allow '' or ! to be used in DMs
        return ''
    return when_mentioned_or(*prefixes)(bot, message)


bot = Bot(command_prefix=get_prefix, case_insensitive=True,
          description='**Epic Bot = best bot**\nWhen using command with args, `<>` indicates a required argument and '
                      '`[]` indicates an optional argument.\nDon\'t however type these around your arguments')

bot.initial_extensions = [f[:-3] for f in listdir(cogs_dir) if isfile(join(cogs_dir, f))]
# getting the cog files in the "Cogs" folder and removing the none .py ones

if __name__ == '__main__':
    print(f'Extensions to be loaded are {bot.initial_extensions}')
    for extension in bot.initial_extensions:
        try:
            bot.load_extension(f'Cogs.{extension}')
        except Exception as e:
            print(f'Failed to load extension {extension}.', file=stderr)
            print_exc()
    bot.load_extension('jishaku')
    bot.launch_time = datetime.utcnow()

bot.run(config.Token)
