from __future__ import annotations

import functools
import inspect
from types import SimpleNamespace
from typing import (
    Any,
    Protocol,
    runtime_checkable,
    TYPE_CHECKING,
    Iterable,
    Optional,
    TypeVar,
)

from asyncpg import Connection, Record
from donphan import Table, MaybeAcquire, Column
from donphan.abc import FetchableMeta
from donphan.sqltype import _defaults as DEFAULTS, SQLType

globals().update(**{cls.__name__: cls for cls in DEFAULTS})
T = TypeVar("T", bound="Table")


@runtime_checkable
class AnnotatedAlias(Protocol):
    __origin__: type
    __metadata__: tuple[type, ...]


class AnnotatedFetchableMeta(FetchableMeta):
    """Add support for "dataclass" like tables with typing.Annotated columns.

    Examples
    --------
    ```py
    class Entry(Table):
        id: int
        created_at: Annotated[datetime, Column(default='NOW()')]
    ```
    """

    def __new__(mcs, name: str, bases: tuple[type, ...], attrs: dict[str, Any], **kwargs: Any) -> Table:
        annotations: dict[str, str] = attrs.get("__annotations__", {})
        for name, type in annotations.items():
            if isinstance(type, str):
                type = new_value = eval(type)
                if isinstance(new_value, AnnotatedAlias):
                    new_value = new_value.__metadata__[0]

                    attrs[name] = new_value
                annotations[name] = new_value
            if not isinstance(type, SQLType):
                if isinstance(type, AnnotatedAlias):
                    type = type.__origin__
                annotations[name] = SQLType._from_python_type(type)

        return super().__new__(mcs, name, bases, attrs)


class Table(Table, metaclass=AnnotatedFetchableMeta):
    @classmethod
    async def create_tables(cls, connection: Connection):
        async with MaybeAcquire(connection=connection) as connection:
            for table in cls.__subclasses__():
                await table.create(connection=connection)

    def __getattribute__(self, item: str) -> Any:
        attr = super().__getattribute__(item)
        if inspect.iscoroutinefunction(attr):

            @functools.wraps(attr)
            async def wrapped(*args: Any, **kwargs: Any) -> Any:
                ret = await attr(*args, **kwargs)
                if isinstance(ret, Record):  # not a fan
                    return SimpleNamespace(**ret.items(), original=ret)
                return ret
            return wrapped

        return attr

    if TYPE_CHECKING:

        @classmethod
        async def fetch(
            cls: type[T],
            *,
            connection: Optional[Connection] = None,
            order_by: Optional[str] = None,
            limit: Optional[int] = None,
            **kwargs
        ) -> list[T]:
            ...

        @classmethod
        async def fetchall(
            cls: type[T],
            *,
            connection: Optional[Connection] = None,
            order_by: Optional[str] = None,
            limit: Optional[int] = None
        ) -> list[T]:
            ...

        @classmethod
        async def fetchrow(
            cls: type[T], *, connection: Optional[Connection] = None, order_by: Optional[str] = None, **kwargs
        ) -> Optional[T]:
            ...

        @classmethod
        async def fetch_where(
            cls: type[T],
            where: str,
            *values,
            connection: Optional[Connection] = None,
            order_by: Optional[str] = None,
            limit: Optional[int] = None
        ) -> list[T]:
            ...

        @classmethod
        async def fetchrow_where(
            cls: type[T], where: str, *values, connection: Optional[Connection] = None, order_by: Optional[str] = None
        ) -> list[T]:
            ...

        @classmethod
        async def insert(
            cls: type[T],
            *,
            connection: Connection = None,
            ignore_on_conflict: bool = False,
            update_on_conflict: Optional[Column] = None,
            returning: Optional[Iterable[Column]] = None,
            **kwargs
        ) -> Optional[T]:
            ...

        @classmethod
        async def update_record(cls, record: T, *, connection: Connection = None, **kwargs) -> None:
            ...

        @classmethod
        async def delete_record(cls, record: T, *, connection: Connection = None):
            ...


class Config(Table):
    guild_id: int
    blacklisted: bool
    prefixes: list[str]
    logging_channel: int
    logged_events: list[str]
