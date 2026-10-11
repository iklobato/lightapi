"""e2e app for scenario 03: HttpMethod mixins and Serializer forms."""

import os
from typing import ClassVar

from sqlalchemy import create_engine

from lightapi import Field, HttpMethod, LightApi, RestEndpoint, Serializer


class ReadOnlyNote(RestEndpoint, HttpMethod.GET):
    text: str = Field(min_length=1)

    class Meta:
        table = "e2e03_notes"


class Event(RestEndpoint, HttpMethod.GET, HttpMethod.POST):
    name: str = Field(min_length=1)

    class Meta:
        table = "e2e03_events"


class PublicUser(RestEndpoint):
    name: str = Field(min_length=1)
    email: str = Field(min_length=1)
    secret: str = Field(min_length=1)

    class Meta:
        table = "e2e03_users"
        serializer = Serializer(fields=["id", "name", "email"])


class Order(RestEndpoint):
    name: str = Field(min_length=1)
    tag: str = Field(default="")

    class Meta:
        table = "e2e03_orders"
        serializer = Serializer(read=["id", "name", "tag"], write=["id", "name"])


class NameOnly(Serializer):
    read: ClassVar[list[str]] = ["id", "name"]
    write: ClassVar[list[str]] = ["id", "name"]


class Alpha(RestEndpoint):
    name: str = Field(min_length=1)
    extra: str = Field(default="")

    class Meta:
        table = "e2e03_alpha"
        serializer = NameOnly


class Beta(RestEndpoint):
    name: str = Field(min_length=1)
    extra: str = Field(default="")

    class Meta:
        table = "e2e03_beta"
        serializer = NameOnly


def main() -> None:
    app = LightApi(engine=create_engine(os.environ["E2E_DB_URL"]))
    app.register(
        {
            "/notes": ReadOnlyNote,
            "/events": Event,
            "/users": PublicUser,
            "/orders": Order,
            "/alpha": Alpha,
            "/beta": Beta,
        }
    )
    app.run(host="127.0.0.1", port=int(os.environ["E2E_PORT"]))


if __name__ == "__main__":
    main()
