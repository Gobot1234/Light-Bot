from __future__ import annotations

import asyncio
import contextlib
import dataclasses
import datetime
import inspect
import secrets
import uuid
from typing import TYPE_CHECKING, Any, Protocol

import aiohttp
import discord
import jinja2
from asyncpg import Pool
from discord import http
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.background import BackgroundTask

from light.db import SteamUser

from .router import Request, Route, route
from .types import AccessTokenExchange, AccessTokenResponse, Connection, PartialUser

if TYPE_CHECKING:
    from ..bot import Light

app: App


class App(FastAPI):
    def __init__(self, db: Pool, bot: Light, **extra: Any):
        super().__init__(**extra)
        self.routes.clear()  # don't want docs etc.
        self.router.route_class = Route
        self.db = db
        self.bot = bot
        self.session = aiohttp.ClientSession()
        self.env = jinja2.Environment(
            loader=jinja2.PackageLoader("web"),
            enable_async=True,
        )
        for _, route in inspect.getmembers(self, predicate=lambda r: hasattr(r, "path")):
            getattr(self, route.method.lower())(route.path)(route)

    async def close(self) -> None:
        await self.session.close()

    @route.get / ""  # fmt: skip
    async def index(self, request: Request):
        user = None
        if session_id := request.cookies.get("session_id"):
            session_id = uuid.UUID(session_id)
            record = await SteamUser.fetch_row(session_id=session_id)
            # if discord.utils.utcnow() > record.expires:
            #     asyncio.create_task(self.refresh_token(session_id))
            with contextlib.suppress(discord.HTTPException):
                user = self.bot.get_user(record.id) or await self.bot.fetch_user(record.id)
        content = await request.template.render_async(user=user)

        return HTMLResponse(content)

    @route.get / "login"  # fmt: skip
    async def login(self, request: Request):
        state = secrets.token_urlsafe(20)
        url = discord.utils.oauth_url(
            client_id=str(self.bot.user.id),
            redirect_uri=f"{request.base_url}{self.login_success.path[1:]}",
            scopes=["identify", "connections"],
        )
        resp = RedirectResponse(f"{url}&state={state}")
        resp.set_cookie("state", state)
        return resp

    @route.get / "login" / "success"  # fmt: skip
    async def login_success(self, request: Request):
        if request.cookies["state"] != request.query_params["state"]:
            return

        data: AccessTokenExchange = {
            "client_id": str(self.bot.user.id),
            "client_secret": self.bot.client_secret,
            "grant_type": "authorization_code",
            "code": request.query_params["code"],
            "redirect_uri": f"{request.base_url}{self.login_success.path[1:]}",
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        resp = await self.session.post(f"{http.Route.BASE}/oauth2/token", data=data, headers=headers)
        data: AccessTokenResponse = await resp.json()
        token = data["access_token"]

        headers = {"Authorization": f"{data['token_type']} {token}"}
        me, connections = await asyncio.gather(
            self.session.get(f"{http.Route.BASE}/users/@me", headers=headers),
            self.session.get(f"{http.Route.BASE}/users/@me/connections", headers=headers),
        )
        user: PartialUser = await me.json()
        connections: list[Connection] = await connections.json()

        connections = [connection for connection in connections if connection.get("type") == "steam"]
        if not connections:
            return HTMLResponse("<h1>You have no connected steam accounts</h1>")

        session_id = uuid.uuid4()
        kwargs = {
            "id": int(user["id"]),
            "access_token": token,
            "refresh_token": data["refresh_token"],
            "expires": discord.utils.utcnow() + datetime.timedelta(seconds=data["expires_in"]),
            "session_id": session_id,
        }

        if len(connections) != 1:  # let them pick which account they want to register
            routes = self.routes.copy()
            event = asyncio.Event()

            # is this utter garbage?
            @self.post(f"/register/{session_id}")
            async def wait_for_post(request: Request):
                assert request.cookies["session_id"] == str(session_id)
                form = await request.form()
                id64 = int(form["user"])
                assert id64 in [user.id64 for user in users]
                await SteamUser.insert(id64=id64, **kwargs)
                event.set()
                self.routes.remove(route)
                return request.home

            route = [r for r in self.routes if r not in routes][0]
            users: list[PartialUser] = [
                # await self.bot.client.fetch_user(connection["id"]) or
                PrivateUser(
                    name=connection["name"],
                    id64=int(connection["id"]),
                )
                for connection in connections
            ]
            resp = HTMLResponse(
                await request.template.render_async(session_id=session_id, users=users),
                background=BackgroundTask(event.wait),
            )
        else:
            await SteamUser.insert(id64=int(connections[0]["id"]), **kwargs)
            resp = request.home
        resp.set_cookie("session_id", str(session_id))
        return resp

    @route.get / "logout"  # fmt: skip
    async def logout(self, request: Request):
        session_id = request.cookies.get("session_id")
        resp = request.home
        if session_id:
            await SteamUser.delete(session_id=session_id)
            resp.delete_cookie("session_id")
        return resp

    # TODO: profile route to select your default steam account again? or should that be on discord once we have a token?
    # maybe both?

    async def refresh_token(self, session_id: uuid.UUID) -> str:
        record = await SteamUser.fetch_row(sesion_id=session_id)
        data = {
            "client_id": self.bot.user.id,
            "client_secret": self.bot.client_secret,
            "grant_type": "refresh_token",
            "refresh_token": record.refresh_token,
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        resp = await self.session.post(f"{http.Route.BASE}/oauth2/token", data=data, headers=headers)
        data: AccessTokenResponse = await resp.json()

        record.access_token = data["access_token"]
        record.refresh_token = data["refresh_token"]
        record.expires = discord.utils.utcnow() + datetime.timedelta(seconds=data["expires_in"])

        await SteamUser.update_record(record)  # type: ignore


async def setup(db: Pool, bot: Light) -> App:
    global app
    app = App(db, bot)
    return app


class PartialUser(Protocol):
    name: str
    id64: int
    avatar_url: str


@dataclasses.dataclass
class PrivateUser(PartialUser):
    __annotations__ = PartialUser.__annotations__

    avatar_url = (
        "https://steamcdn-a.akamaihd.net/steamcommunity/public/images/avatars/"
        "fe/fef49e7fa7e1997310d705b2a6158ff8dc1cdfeb_full.jpg"  # default avatar hash
    )
