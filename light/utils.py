import contextlib
from typing import Any, Protocol, TypeVar

C = TypeVar("C", bound="Closeable")


class Closeable(Protocol):
    async def close(self) -> Any:
        ...


@contextlib.asynccontextmanager
async def aclosing(value: C) -> C:
    try:
        yield value
    finally:
        await value.close()
