import typer

from light import Light

app = typer.Typer()


@app.command()
def main() -> None:
    bot = Light()
    bot.run()


if __name__ == "__main__":
    app()
