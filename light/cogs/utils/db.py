from __future__ import annotations

import functools
import inspect
from types import SimpleNamespace
from typing import (
    TYPE_CHECKING,
    Any,
    Iterable,
    Optional,
    Protocol,
    TypeVar,
    get_args,
    get_origin,
    runtime_checkable,
    Annotated,
    Callable,
    Coroutine,
)

from asyncpg import Connection, Record
from donphan import Column, MaybeAcquire, Table
from donphan.abc import FetchableMeta
from donphan.sqltype import SQLType, _defaults as DEFAULTS

globals().update(**{cls.__name__: cls for cls in DEFAULTS})

T = TypeVar("T", bound="Table")


def wrap_coro(func: Callable[..., Coroutine]) -> Callable[..., Coroutine]:
    @functools.wraps(func)
    async def wrapped(*args: Any, **kwargs: Any) -> Any:
        """Wrapper around returned async functions which makes asyncpg.Records types.SimpleNamespaces"""
        ret = await func(*args, **kwargs)
        if isinstance(ret, Record):
            return SimpleNamespace(**dict(ret))
        if isinstance(ret, Iterable):
            new_return = []
            for element in ret:
                if isinstance(element, Record):
                    element = SimpleNamespace(**dict(element))

                new_return.append(element)
            return new_return

        return ret

    return wrapped


@runtime_checkable
class AnnotatedAlias(Protocol):
    """Protocol version of typing._AnnotatedAlias so we don't get NameErrors from linters."""

    __origin__: type
    __metadata__: tuple[type, ...]


class AnnotatedTableMeta(FetchableMeta):
    """Add support for "dataclass" like tables with typing.Annotated columns.

    Example
    -------
    ```py
    class Entry(Table):
        id: int
        created_at: Annotated[datetime, Column(default='NOW()')]
    ```
    """

    def __new__(mcs, name: str, bases: tuple[type, ...], attrs: dict[str, Any], **kwargs: Any) -> type[Table]:
        annotations: dict[str, Any] = attrs.get("__annotations__", {})
        for name, type in annotations.items():
            sql_type = None
            if isinstance(type, str):
                type = new_value = eval(type)
                if isinstance(new_value, AnnotatedAlias):
                    if len(new_value.__metadata__) == 1:
                        sql_type = new_value.__metadata__[0]
                    else:
                        sql_type, column = new_value.__metadata__
                        attrs[name] = column
            annotations[name] = sql_type if sql_type is not None else type
            if not isinstance(annotations[name], SQLType):
                origin = get_origin(type)
                args = get_args(type)
                if origin:
                    annotations[name] = [*args] if issubclass(origin, list) else args[0]
                else:
                    annotations[name] = SQLType._from_python_type(type)

        return super().__new__(mcs, name, bases, attrs)

    def __getattribute__(cls, item: str) -> Any:
        if item == "__name__":
            return cls.__qualname__

        attr = super().__getattribute__(item)
        if inspect.iscoroutinefunction(attr):
            return wrap_coro(attr)

        return attr


class Table(Table, metaclass=AnnotatedTableMeta):
    @classmethod
    async def create_tables(cls, connection: Connection):
        async with MaybeAcquire(connection=connection) as connection:
            for table in cls.__subclasses__():
                await table.create(connection=connection, drop_if_exists=False)

    def __getattribute__(self, item: str) -> Any:
        attr = super().__getattribute__(item)
        if inspect.iscoroutinefunction(attr):
            return wrap_coro(attr)

        return attr

    if TYPE_CHECKING:
        # stubs to support above __getattribute__
        @classmethod
        async def fetch(
            cls: type[T],
            *,
            connection: Optional[Connection] = None,
            order_by: Optional[str] = None,
            limit: Optional[int] = None,
            **kwargs,
        ) -> list[T]:
            ...

        @classmethod
        async def fetchall(
            cls: type[T],
            *,
            connection: Optional[Connection] = None,
            order_by: Optional[str] = None,
            limit: Optional[int] = None,
        ) -> list[T]:
            ...

        @classmethod
        async def fetchrow(
            cls: type[T], *, connection: Optional[Connection] = None, order_by: Optional[str] = None, **kwargs: Any
        ) -> Optional[T]:
            ...

        @classmethod
        async def fetch_where(
            cls: type[T],
            where: str,
            *values: Any,
            connection: Optional[Connection] = None,
            order_by: Optional[str] = None,
            limit: Optional[int] = None,
        ) -> list[T]:
            ...

        @classmethod
        async def fetchrow_where(
            cls: type[T],
            where: str,
            *values: Any,
            connection: Optional[Connection] = None,
            order_by: Optional[str] = None,
        ) -> list[T]:
            ...

        @classmethod
        async def insert(
            cls: type[T],
            *,
            connection: Optional[Connection] = None,
            ignore_on_conflict: bool = False,
            update_on_conflict: Optional[Column] = None,
            returning: Optional[Iterable[Column]] = None,
            **kwargs,
        ) -> Optional[T]:
            ...

        @classmethod
        async def update_record(cls, record: T, *, connection: Connection = None, **kwargs) -> None:
            ...

        @classmethod
        async def delete_record(cls, record: T, *, connection: Connection = None):
            ...


class Config(Table):
    guild_id: Annotated[int, SQLType.BigInt(), Column(primary_key=True)]
    blacklisted: bool
    prefixes: list[str]
    logging_channel: Annotated[int, SQLType.BigInt()]
    logged_events: list[str]
