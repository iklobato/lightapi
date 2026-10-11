"""e2e app for scenario 08: static, sync and async queryset hooks on one async app."""

import os

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine
from starlette.requests import Request

from lightapi import Field, LightApi, RestEndpoint


class StaticArticle(RestEndpoint):
    title: str = Field(min_length=1)
    published: bool = Field(default=False)

    class Meta:
        table = "e2e08_static"


class SyncArticle(RestEndpoint):
    title: str = Field(min_length=1)
    published: bool = Field(default=False)

    class Meta:
        table = "e2e08_sync"

    def queryset(self, request: Request):
        model = type(self)._model_class
        return select(model).where(model.published.is_(True))


class AsyncArticle(RestEndpoint):
    title: str = Field(min_length=1)
    published: bool = Field(default=False)
    words: int = Field(default=0)

    class Meta:
        table = "e2e08_async"

    async def queryset(self, request: Request):
        model = type(self)._model_class
        stmt = select(model).where(model.published.is_(True))
        minimum = request.query_params.get("min_words")
        if minimum is not None:
            stmt = stmt.where(model.words >= int(minimum))
        return stmt


def main() -> None:
    app = LightApi(engine=create_async_engine(os.environ["E2E_DB_URL"]), mode="async")
    app.register(
        {"/static": StaticArticle, "/sync": SyncArticle, "/async": AsyncArticle}
    )
    # The static form needs the mapped class, which exists only after register().
    StaticArticle.queryset = select(StaticArticle._model_class).where(
        StaticArticle._model_class.published.is_(True)
    )
    app.run(host="127.0.0.1", port=int(os.environ["E2E_PORT"]))


if __name__ == "__main__":
    main()
