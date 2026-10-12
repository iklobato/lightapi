"""e2e app for scenario 09: sync and async middleware, short-circuit, CORS."""

import os

from sqlalchemy.ext.asyncio import create_async_engine
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from lightapi import Field, LightApi, Middleware, RestEndpoint


class Stamp(Middleware):
    def process(self, request: Request, response: Response | None) -> Response | None:
        if response is None:
            print("hook pre:stamp", flush=True)
            return None
        response.headers["x-e2e-stamp"] = "yes"
        print("hook post:stamp", flush=True)
        return response


class Trace(Middleware):
    async def process(
        self, request: Request, response: Response | None
    ) -> Response | None:
        print("hook pre:trace" if response is None else "hook post:trace", flush=True)
        return response


class Teapot(Middleware):
    def process(self, request: Request, response: Response | None) -> Response | None:
        if response is None and request.headers.get("x-teapot"):
            return JSONResponse({"detail": "teapot"}, status_code=418)
        return response


class Item(RestEndpoint):
    name: str = Field(min_length=1)

    class Meta:
        table = "e2e09_items"


def main() -> None:
    app = LightApi(
        engine=create_async_engine(os.environ["E2E_DB_URL"]),
        mode="async",
        middlewares=[Stamp, Trace, Teapot],
        cors_origins=["http://e2e.local"],
    )
    app.register({"/items": Item})
    app.run(host="127.0.0.1", port=int(os.environ["E2E_PORT"]))


if __name__ == "__main__":
    main()
