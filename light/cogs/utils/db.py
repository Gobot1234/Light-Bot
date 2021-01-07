from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Annotated,
    Any,
    Callable,
    Iterable,
    Literal,
    Optional,
    Union,
    TypeVar,
    get_args,
    get_origin,
)

from asyncpg import Connection, Record
from donphan import Column, MaybeAcquire, Table as DonphanTable, SQLType
from donphan.abc import FetchableMeta


T = TypeVar("T", bound="Table")

if TYPE_CHECKING:
    from datetime import datetime, date, timedelta
    from decimal import Decimal
    from ipaddress import IPv4Address, IPv4Network, IPv6Address, IPv6Network
    from uuid import UUID

    SQLType.Integer = SQLType.SmallInt = SQLType.BigInt = SQLType.Serial = int
    SQLType.Float = SQLType.DoublePrecision = float
    SQLType.Numeric = Decimal
    SQLType.Money = SQLType.Character = SQLType.Text = str
    SQLType.CharacterVarying = Union[str, Callable[[int], str]]
    SQLType.Bytea = bytes
    SQLType.Timestamp = datetime
    SQLType.Date = date
    SQLType.Interval = timedelta
    SQLType.Boolean = bool
    SQLType.CIDR = Union[IPv4Network, IPv6Network]
    SQLType.Inet = Union[IPv4Address, IPv6Address]
    SQLType.MACAddr = str
    SQLType.UUID = UUID
    SQLType.JSON = SQLType.JSONB = dict


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
                type = eval(type)
                if get_origin(type) is Annotated:
                    attrs[name] = type.__metadata__[0]
                    sql_type = type.__origin__
            annotations[name] = sql_type if sql_type is not None else type

            if (origin := get_origin(type)) and issubclass(origin or object, Iterable):
                annotations[name] = [*get_args(type)]

        return super().__new__(mcs, name, bases, attrs)

    def __getattribute__(cls, item: str) -> Any:
        return super().__getattribute__("__qualname__" if item == "__name__" else item)


class Table(DonphanTable, metaclass=AnnotatedTableMeta):
    """Allows for dot access to field names, main reason for this is type checking.

    TypedDicts aren't an option here as they cause base class issues.
    """

    def __init__(self, *, record: Record, **kwargs: Any):
        for name, attr in kwargs.items():
            setattr(self, name, attr)
        self.record = record

    def __repr__(self) -> str:
        return (
            f"<{self.__class__.__name__} {' '.join(f'{name}={getattr(self, name)}' for name in self.__annotations__)}>"
        )

    @classmethod
    async def create_tables(cls, connection: Connection):
        async with MaybeAcquire(connection=connection) as connection:
            for table in cls.__subclasses__():
                await table.create(connection=connection, drop_if_exists=False)

    @classmethod
    async def fetch(cls: type[T], *, order_by: Optional[str] = None, limit: Optional[int] = None, **kwargs) -> list[T]:
        return [
            cls(**dict(record), record=record)
            for record in await super().fetch(order_by=order_by, limit=limit, **kwargs)
        ]

    @classmethod
    async def fetchall(cls: type[T], *, order_by: Optional[str] = None, limit: Optional[int] = None) -> list[T]:
        return [cls(**dict(record), record=record) for record in await super().fetchall(order_by=order_by, limit=limit)]

    @classmethod
    async def fetchrow(cls: type[T], *, order_by: Optional[str] = None, **kwargs: Any) -> Optional[T]:
        if (record := await super().fetchrow(order_by=order_by, **kwargs)) is not None:
            return cls(**dict(record), record=record)

    @classmethod
    async def fetch_where(
        cls: type[T], where: str, *values: Any, order_by: Optional[str] = None, limit: Optional[int] = None
    ) -> list[T]:
        return [
            cls(**dict(record), record=record)
            for record in await super().fetch_where(where, *values, order_by=order_by, limit=limit)
        ]

    @classmethod
    async def fetchrow_where(cls: type[T], where: str, *values: Any, order_by: Optional[str] = None) -> list[T]:
        return [
            cls(**dict(record), record=record)
            for record in await super().fetchrow_where(where, *values, order_by=order_by)
        ]

    @classmethod
    async def insert(
        cls: type[T],
        *,
        ignore_on_conflict: bool = False,
        update_on_conflict: Optional[Column] = None,
        returning: Optional[Union[Literal["*"], Iterable[Column]]] = None,
        **kwargs: Any,
    ) -> Optional[T]:
        if returning == "*":  # short hand for return all
            returning = (getattr(cls, name) for name in cls.__annotations__)
        record = await super().insert(
            ignore_on_conflict=ignore_on_conflict,
            update_on_conflict=update_on_conflict,
            returning=returning,
            **kwargs,
        )
        if record is not None:
            return cls(**dict(record), record=record)

    async def update_record(self, **kwargs: Any) -> None:
        await super().update_record(self.record, **kwargs)

    async def delete_record(self) -> None:
        kwargs = {key: value for key, value in self.record.items() if key in self.__annotations__}
        await super().delete(**kwargs)  # just using delete_record raises an AttributeError if you remove columns


class Config(Table):
    guild_id: Annotated[SQLType.BigInt, Column(primary_key=True)]
    blacklisted: bool
    prefixes: set[str]
