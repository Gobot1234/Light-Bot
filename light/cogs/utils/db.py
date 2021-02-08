from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Annotated,
    Any,
    Callable,
    Iterable,
    Literal,
    Optional,
    TypeVar,
    Union,
    get_args,
    get_origin,
)

from asyncpg import Connection, Record
from donphan import Column, MaybeAcquire, SQLType, Table as DonphanTable
from donphan.abc import FetchableMeta

T = TypeVar("T", bound="Table")

if TYPE_CHECKING:
    from datetime import date, datetime, timedelta
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
    SQLType.JSON = SQLType.JSONB = dict[str, Any]


class DotRecord(Record):
    """Provide dot access to Records."""

    __slots__ = ()

    def __getattr__(self, name: str) -> Any:
        return self[name]


class AnnotatedTableMeta(FetchableMeta):
    """Add support for "dataclass" like tables with typing.Annotated columns.

    Example
    -------
    .. code-block:: python3

        class Entry(Table):
            id: int
            created_at: Annotated[datetime, Column(default="NOW()")]
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

        return super().__new__(mcs, name, bases, attrs, **kwargs)

    def __getattribute__(cls, item: str) -> Any:
        return super().__getattribute__(
            "__qualname__" if item == "__name__" else item
        )  # I manage to mess up __name__ somehow I cba figuring out what's actually up atm.


class Table(DonphanTable, metaclass=AnnotatedTableMeta):
    """Allows for dot access to field names, main reason for this is type checking."""

    @classmethod
    async def create_tables(cls, connection: Connection) -> None:
        async with MaybeAcquire(connection) as connection:
            for table in cls.__subclasses__():
                await table.create(connection=connection, drop_if_exists=False)

    if TYPE_CHECKING:

        @classmethod
        async def fetch(
            cls: type[T], *, order_by: Optional[str] = None, limit: Optional[int] = None, **kwargs
        ) -> list[T]:
            ...

        @classmethod
        async def fetchall(cls: type[T], *, order_by: Optional[str] = None, limit: Optional[int] = None) -> list[T]:
            ...

        @classmethod
        async def fetchrow(cls: type[T], *, order_by: Optional[str] = None, **kwargs: Any) -> Optional[T]:
            ...

        @classmethod
        async def fetch_where(
            cls: type[T], where: str, *values: Any, order_by: Optional[str] = None, limit: Optional[int] = None
        ) -> list[T]:
            ...

        @classmethod
        async def fetchrow_where(cls: type[T], where: str, *values: Any, order_by: Optional[str] = None) -> list[T]:
            ...

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

        return await super().insert(
            ignore_on_conflict=ignore_on_conflict,
            update_on_conflict=update_on_conflict,
            returning=returning,
            **kwargs,
        )


class Config(Table):
    guild_id: Annotated[SQLType.BigInt, Column(primary_key=True)]
    blacklisted: bool
    prefixes: list[str]
