from __future__ import annotations

import sys
from collections.abc import Callable, Iterable
from typing import TYPE_CHECKING, Any, Optional, TypeVar

from asyncpg import Record
from donphan import Column, SQLType, Table as DonphanTable
from donphan._selectable import OrderBy

T = TypeVar("T", bound="Table")


class DotRecord(Record):
    """Provide dot access to Records."""

    __slots__ = ()

    def __getattr__(self, name: str) -> Any:
        return self[name]

    def __setattr__(self, name: str, value: Any) -> None:
        self[name] = value


class Table(DonphanTable):
    def __init_subclass__(cls) -> None:
        for name, annotation in tuple(cls.__annotations__.items()):
            if isinstance(annotation, str):
                annotation = eval(annotation, sys.modules[cls.__module__].__dict__)

            cls.__annotations__[name] = Column[annotation]

            if (default := getattr(cls, name, None)) and not isinstance(default, Column):
                value = Column(default=default)
            else:
                value = Column()

            setattr(cls, name, value)

        super().__init_subclass__()

    if TYPE_CHECKING:

        @classmethod
        async def fetch(
            cls: type[T],
            *,
            limit: Optional[int] = None,
            order_by: Optional[OrderBy] = None,
            **values: Any,
        ) -> list[T]:
            ...

        @classmethod
        async def fetch_row(
            cls: type[T],
            *,
            order_by: Optional[OrderBy] = None,
            **values: Any,
        ) -> Optional[T]:
            ...

        @classmethod
        async def fetch_where(
            cls: type[T],
            where: str,
            *values: Any,
            limit: Optional[int] = None,
            order_by: OrderBy | str | None = None,
        ) -> list[T]:
            ...

        @classmethod
        async def fetch_row_where(
            cls: type[T],
            where: str,
            *values: Any,
            order_by: OrderBy | str | None = None,
        ) -> list[T]:
            ...

        @classmethod
        async def insert(
            cls: type[T],
            *,
            ignore_on_conflict: bool = False,
            update_on_conflict: Optional[Column] = None,
            returning: str | Iterable[Column] | None = None,
            **values: Any,
        ) -> Optional[T]:
            ...


if TYPE_CHECKING:  # linter bad
    S = TypeVar("S")

    class SQLType(SQLType[S]):
        from datetime import date, datetime, timedelta
        from decimal import Decimal
        from ipaddress import IPv4Address, IPv4Network, IPv6Address, IPv6Network
        from uuid import UUID

        Integer = SmallInt = BigInt = Serial = int
        Float = DoublePrecision = float
        Numeric = Decimal
        Money = Character = Text = str
        CharacterVarying = str | Callable[[int], str]
        Bytea = bytes
        Timestamp = datetime
        Date = date
        Interval = timedelta
        Boolean = bool
        CIDR = IPv4Network | IPv6Network
        Inet = IPv4Address | IPv6Address
        MACAddr = str
        UUID = UUID
        JSON = JSONB = dict[str, Any]
