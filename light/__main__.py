import asyncio

import typer
import uvicorn

from light.bot import Light
from light.db import setup as db_setup
from light.web import App

app = typer.Typer()


@app.command()
async def main() -> None:
    db = await db_setup()

    bot = Light(db)

    web_app = App(db, bot)
    config = uvicorn.Config(web_app)
    server = uvicorn.Server(config)
    server.install_signal_handlers = lambda *args, **kwargs: None  # if it uses signal handlers everything breaks

    await asyncio.gather(start_bot(bot), start_server(server))


async def start_bot(bot: Light) -> None:
    try:
        await bot.start()
    finally:
        if not bot.is_closed():
            await bot.close()


async def start_server(server: uvicorn.Server) -> None:
    try:
        await server.serve()
    finally:
        await server.config.app.close()
        await server.shutdown()


if __name__ == "__main__":
    try:
        import uvloop
    except ModuleNotFoundError:
        pass
    else:
        uvloop.install()

    try:
        asyncio.run(app(standalone_mode=False), debug=True)
    except KeyboardInterrupt:
        pass
