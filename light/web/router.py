from __future__ import annotations

import dataclasses
from collections.abc import Callable, Coroutine
from types import FunctionType
from typing import TYPE_CHECKING

from fastapi.responses import RedirectResponse
from fastapi.routing import APIRoute, Request as OldRequest, Response
from jinja2 import Template
from typing_extensions import ParamSpec

if TYPE_CHECKING:
    from light.web import App

P = ParamSpec("P")


class Request(OldRequest):
    app: App

    @property
    def template(self) -> Template:
        return self.app.env.get_template(f"{self['endpoint'].__name__}.j2")

    @property
    def home(self) -> RedirectResponse:
        return RedirectResponse(self.base_url)


class Route(APIRoute):
    def get_route_handler(self) -> Callable[[OldRequest], Coroutine[None, None, Response]]:
        original_route_handler = super().get_route_handler()

        async def custom_route_handler(request: OldRequest) -> Response:
            request = Request(request.scope, request.receive)
            return await original_route_handler(request)

        return custom_route_handler


@dataclasses.dataclass
class route:
    method: str
    path: list[str] = dataclasses.field(default_factory=list)

    @classmethod
    @property
    def get(cls):
        return cls("GET")

    @classmethod
    @property
    def post(cls):
        return cls("POST")

    def __truediv__(self, other: str):
        self.path.append(other)
        return self

    def __call__(self, endpoint: FunctionType) -> APIRoute:
        endpoint.path = f"/{'/'.join(self.path)}"
        endpoint.method = self.method
        return endpoint
