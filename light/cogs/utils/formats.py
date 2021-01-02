from traceback import format_exception
from typing import Sequence


def format_error(error: Exception, *, strip: bool = False) -> str:
    formatted = "".join(format_exception(type(error), error, error.__traceback__, limit=1))
    if strip:
        formatted = formatted.splitlines()
        formatted.pop(1)
        formatted.pop(1)
        return "\n".join(formatted)
    return formatted


def human_join(seq: Sequence[str], delimiter: str = ", ", final: str = "or") -> str:
    size = len(seq)
    if size == 0:
        return ""

    if size == 1:
        return seq[0]

    if size == 2:
        return f"{seq[0]} {final} {seq[1]}"

    return f"{delimiter.join(seq[:-1])} {final} {seq[-1]}"
