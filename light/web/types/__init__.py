from typing import Literal, TypedDict

from discord.types.user import PartialUser
from typing_extensions import NotRequired


class AccessTokenExchange(TypedDict):
    client_id: str
    client_secret: str
    grant_type: Literal["authorization_code"]
    code: str
    redirect_uri: str


class AccessTokenResponse(TypedDict):
    access_token: str
    token_type: str
    expires_in: int
    refresh_token: str
    scope: str


class RefreshTokenExchange(TypedDict):
    client_id: str
    client_secret: str
    grant_type: Literal["refresh_token"]
    refresh_token: str


class Connection(TypedDict):
    id: str
    name: str
    type: str  # steam
    revoked: NotRequired[bool]
    verified: bool
    friend_sync: bool
    show_activity: bool
    visibility: int
