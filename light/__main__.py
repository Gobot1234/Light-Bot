import click

from light import Light


@click.command()
def main() -> None:
    bot = Light()
    bot.run()


if __name__ == "__main__":
    main()
