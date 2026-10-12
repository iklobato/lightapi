"""YAML, async-engine and declared-behaviour-change scenarios."""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any

import httpx
from diff_validators import check_login
from harness import Recorder, bearer, client_for, memory_engine
from scenarios_sync import ADMIN, USER, Step, book_endpoint, crud_steps, play
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine

from lightapi import (
    Authentication,
    Cache,
    Field,
    FieldFilter,
    Filtering,
    IsAuthenticated,
    JWTAuthentication,
    LightApi,
    OrderingFilter,
    Pagination,
    RestEndpoint,
)

VALID_YAML = """
defaults:
  authentication: { backend: JWTAuthentication, permission: IsAuthenticated }
  pagination: { style: page_number, page_size: 2 }
auth:
  auth_path: /auth
  login_validator: diff_validators.check_login
middleware: [diff_validators.StampMiddleware]
endpoints:
  - route: /dfy-announcements
    fields:
      title: { type: str, min_length: 1, max_length: 20 }
      pinned: { type: bool, default: false }
      score: { type: int, optional: true }
    meta:
      methods: [GET, POST]
      authentication: { permission: AllowAny }
      filtering: { fields: [pinned], ordering: [title] }
  - route: /dfy-tickets
    fields:
      subject: { type: str, min_length: 1 }
      cost: { type: Decimal, decimal_places: 2, optional: true }
    meta:
      methods:
        GET: { authentication: { permission: AllowAny } }
        POST: { authentication: { permission: IsAuthenticated } }
        DELETE: { authentication: { permission: IsAdminUser } }
  - route: /api/v1/dfy-things
    fields:
      name: { type: str }
    meta:
      serializer: { fields: [id, name] }
      pagination: { style: cursor, page_size: 2 }
"""

INVALID_YAML = {
    "unknown-field-type": """
        endpoints:
          - route: /dfy-bad1
            fields: { a: { type: colour } }
    """,
    "unknown-class-name": """
        endpoints:
          - route: /dfy-bad2
            fields: { a: { type: str } }
            meta: { authentication: { backend: NoSuchBackend } }
    """,
    "unknown-dotted-class": """
        middleware: [no.such.module.Thing]
        endpoints: []
    """,
    "unknown-http-method": """
        endpoints:
          - route: /dfy-bad3
            fields: { a: { type: str } }
            meta: { methods: [GET, TELEPORT] }
    """,
    "validator-not-dotted": """
        auth: { login_validator: check_login }
        endpoints: []
    """,
    "validator-missing": """
        auth: { login_validator: diff_validators.nothing_here }
        endpoints: []
    """,
    "validator-async": """
        auth: { login_validator: diff_validators.async_login }
        endpoints: []
    """,
    "validator-wrong-arity": """
        auth: { login_validator: diff_validators.one_argument_login }
        endpoints: []
    """,
    "validator-not-callable": """
        auth: { login_validator: diff_validators.NOT_CALLABLE }
        endpoints: []
    """,
    "env-var-not-set": """
        database: { url: "${DFY_VARIABLE_THAT_IS_NOT_SET}" }
        endpoints: []
    """,
    "bad-mode": """
        mode: sideways
        endpoints: []
    """,
    "bad-pagination-style": """
        endpoints:
          - route: /dfy-bad4
            fields: { a: { type: str } }
            meta: { pagination: { style: spiral } }
    """,
}


def yaml_config(rec: Recorder, tmp_dir: str) -> None:
    config = Path(tmp_dir) / "valid.yaml"
    config.write_text(VALID_YAML, encoding="utf-8")
    app = LightApi.from_config(str(config), engine=memory_engine())
    client = client_for(app)
    user, admin = bearer(USER), bearer(ADMIN)
    steps: list[Step] = [
        ("announcements-anonymous", "GET", "/dfy-announcements", {}),
        (
            "announcements-create",
            "POST",
            "/dfy-announcements",
            {"json": {"title": "b"}},
        ),
        (
            "announcements-create-2",
            "POST",
            "/dfy-announcements",
            {"json": {"title": "a", "pinned": True}},
        ),
        (
            "announcements-create-3",
            "POST",
            "/dfy-announcements",
            {"json": {"title": "c", "score": 3}},
        ),
        (
            "announcements-too-long",
            "POST",
            "/dfy-announcements",
            {"json": {"title": "x" * 21}},
        ),
        ("announcements-page-1", "GET", "/dfy-announcements?ordering=title", {}),
        ("announcements-page-2", "GET", "/dfy-announcements?ordering=title&page=2", {}),
        ("announcements-filter", "GET", "/dfy-announcements?pinned=true", {}),
        ("announcements-put-not-allowed", "PUT", "/dfy-announcements/1", {"json": {}}),
        ("tickets-get-anonymous", "GET", "/dfy-tickets", {}),
        ("tickets-post-anonymous", "POST", "/dfy-tickets", {"json": {"subject": "s"}}),
        (
            "tickets-post-user",
            "POST",
            "/dfy-tickets",
            {"headers": user, "json": {"subject": "s", "cost": "1.50"}},
        ),
        ("tickets-delete-user", "DELETE", "/dfy-tickets/1", {"headers": user}),
        ("tickets-delete-admin", "DELETE", "/dfy-tickets/1", {"headers": admin}),
        ("tickets-patch-not-allowed", "PATCH", "/dfy-tickets/1", {"json": {}}),
        ("things-anonymous", "GET", "/api/v1/dfy-things", {}),
        (
            "things-create",
            "POST",
            "/api/v1/dfy-things",
            {"headers": user, "json": {"name": "n"}},
        ),
        ("things-list", "GET", "/api/v1/dfy-things", {"headers": user}),
        (
            "login",
            "POST",
            "/auth/login",
            {"json": {"username": "alice", "password": "secret"}},
        ),
    ]
    play(rec, "yaml", client, steps)
    rec.note(
        "yaml/endpoint-class-names",
        sorted(c.__name__ for c in app._endpoint_map.values()),
    )

    for label, document in INVALID_YAML.items():
        broken = Path(tmp_dir) / f"{label}.yaml"
        broken.write_text(textwrap.dedent(document), encoding="utf-8")
        try:
            LightApi.from_config(str(broken), engine=memory_engine())
            rec.note(f"yaml-invalid/{label}", "accepted")
        except Exception as error:
            rec.raised(f"yaml-invalid/{label}", error)


async def play_async(rec: Recorder, group: str, client: Any, steps: list[Step]) -> None:
    for label, method, url, kwargs in steps:
        rec.http(f"{group}/{label}", await client.request(method, url, **kwargs))


def async_client(app: Any) -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app.build_app(), raise_app_exceptions=False)
    return httpx.AsyncClient(transport=transport, base_url="http://testserver")


async def async_engine_scenarios(rec: Recorder, fake_redis: Any) -> None:
    background_log: list[str] = []

    class DfaArticle(RestEndpoint):
        title: str = Field(min_length=1)
        category: str = Field(min_length=1)

        class Meta:
            filtering = Filtering(
                backends=[FieldFilter, OrderingFilter],
                fields=["category"],
                ordering=["title"],
            )
            pagination = Pagination(style="page_number", page_size=2)

    class DfaEvent(RestEndpoint):
        name: str = Field(min_length=1)

        class Meta:
            pagination = Pagination(style="cursor", page_size=2)

    class DfaSecret(RestEndpoint):
        text: str = Field(min_length=1)

        class Meta:
            authentication = Authentication(JWTAuthentication, IsAuthenticated)

    class DfaOwned(RestEndpoint):
        name: str = Field(min_length=1)
        owner: str = Field(min_length=1)

        async def queryset(self, request: Any) -> Any:
            model = type(self)._model_class
            return select(model).where(
                model.owner == request.query_params.get("owner", "ana")
            )

    class DfaSyncQueryset(RestEndpoint):
        name: str = Field(min_length=1)

        def queryset(self, request: Any) -> Any:
            model = type(self)._model_class
            return select(model).order_by(model.name.desc())

    class DfaHooked(RestEndpoint):
        name: str = Field(min_length=1)

        async def post(self, request: Any) -> Any:
            import json

            response = await self._create_async(json.loads(await request.body()))
            if response.status_code == 201:
                self.background(background_log.append, "created")
            return response

        async def get(self, request: Any) -> Any:
            listed = await self._list_async(request)
            listed.headers["x-trace"] = "async-override"
            return listed

        async def put(self, request: Any) -> Any:
            import json

            pk = request.path_params["id"]
            return await self._update_async(json.loads(await request.body()), pk)

        async def delete(self, request: Any) -> Any:
            return await self._destroy_async(request, request.path_params["id"])

    engine = create_async_engine("sqlite+aiosqlite://")
    app = LightApi(engine=engine, login_validator=check_login)
    app.register(
        {
            "/dfabooks": book_endpoint("DfaBook"),
            "/dfaarticles": DfaArticle,
            "/dfaevents": DfaEvent,
            "/dfasecrets": DfaSecret,
            "/dfaowned": DfaOwned,
            "/dfasyncqs": DfaSyncQueryset,
            "/dfahooked": DfaHooked,
        }
    )
    async with async_client(app) as client:
        await play_async(rec, "async-crud", client, crud_steps("/dfabooks"))

        for title, category in (("b", "x"), ("a", "x"), ("c", "y")):
            await client.post(
                "/dfaarticles", json={"title": title, "category": category}
            )
        for query in ("", "?category=x", "?ordering=-title", "?page=2", "?page=9"):
            rec.http(
                f"async-filtering{query or '?none'}",
                await client.get(f"/dfaarticles{query}"),
            )

        for n in range(5):
            await client.post("/dfaevents", json={"name": f"e{n}"})
        url, hops = "/dfaevents", 0
        while url and hops < 5:
            page = rec.http(f"async-cursor/page-{hops}", await client.get(url))
            cursor = page.json().get("next") if page.status_code == 200 else None
            url, hops = (f"/dfaevents?cursor={cursor}" if cursor else None), hops + 1

        user = bearer(USER)
        secrets: list[Step] = [
            ("anonymous", "GET", "/dfasecrets", {}),
            ("user", "GET", "/dfasecrets", {"headers": user}),
            (
                "user-create",
                "POST",
                "/dfasecrets",
                {"headers": user, "json": {"text": "t"}},
            ),
            (
                "login",
                "POST",
                "/auth/login",
                {"json": {"username": "alice", "password": "secret"}},
            ),
        ]
        await play_async(rec, "async-auth", client, secrets)

        for name, owner in (("one", "ana"), ("two", "bia"), ("three", "ana")):
            await client.post("/dfaowned", json={"name": name, "owner": owner})
        rec.http("async-queryset/default-owner", await client.get("/dfaowned"))
        rec.http("async-queryset/other-owner", await client.get("/dfaowned?owner=bia"))
        for name in ("m", "z", "a"):
            await client.post("/dfasyncqs", json={"name": name})
        rec.http(
            "async-queryset/sync-queryset-on-async-app", await client.get("/dfasyncqs")
        )

        hooked: list[Step] = [
            ("post-override", "POST", "/dfahooked", {"json": {"name": "h"}}),
            ("post-override-invalid", "POST", "/dfahooked", {"json": {}}),
            ("get-override", "GET", "/dfahooked", {}),
            (
                "put-override",
                "PUT",
                "/dfahooked/1",
                {"json": {"name": "h2", "version": 1}},
            ),
            (
                "put-override-conflict",
                "PUT",
                "/dfahooked/1",
                {"json": {"name": "h3", "version": 1}},
            ),
            ("delete-override", "DELETE", "/dfahooked/1", {}),
            ("delete-override-again", "DELETE", "/dfahooked/1", {}),
        ]
        await play_async(rec, "async-overrides", client, hooked)
        rec.note("async-overrides/background-tasks-ran", list(background_log))

    await engine.dispose()
    await _async_engine_without_mode(rec)
    await _async_cache(rec, fake_redis)


async def _async_engine_without_mode(rec: Recorder) -> None:
    """An AsyncEngine alone: the README calls this a one-line swap."""

    class DfaPlain(RestEndpoint):
        name: str = Field(min_length=1)

    engine = create_async_engine("sqlite+aiosqlite://")
    app = LightApi(engine=engine)
    app.register({"/dfaplain": DfaPlain})
    async with async_client(app) as client:
        rec.http(
            "async-no-mode/create", await client.post("/dfaplain", json={"name": "x"})
        )
        rec.http("async-no-mode/list", await client.get("/dfaplain"))
    await engine.dispose()


async def _async_cache(rec: Recorder, fake_redis: Any) -> None:
    class DfaCached(RestEndpoint):
        name: str = Field(min_length=1)

        class Meta:
            cache = Cache(ttl=60)

    fake_redis.store.clear()
    engine = create_async_engine("sqlite+aiosqlite://")
    # No endpoint method is async here, so the mode has to be stated.
    app = LightApi(engine=engine, mode="async")
    app.register({"/dfacached": DfaCached})
    async with async_client(app) as client:
        await client.post("/dfacached", json={"name": "original"})
        rec.http("cache-async/first-get", await client.get("/dfacached"))
        rec.note("cache-async/keys-after-first-get", sorted(fake_redis.store))
        async with engine.begin() as connection:
            await connection.execute(
                text("UPDATE dfacacheds SET name = 'changed in the database'")
            )
        rec.http("cache-async/second-get", await client.get("/dfacached"))
        rec.http(
            "cache-async/post", await client.post("/dfacached", json={"name": "new"})
        )
        rec.note("cache-async/keys-after-write", sorted(fake_redis.store))
        rec.http("cache-async/get-after-write", await client.get("/dfacached"))
    await engine.dispose()


def declared_changes(rec: Recorder) -> None:
    """Steps that the CHANGELOG says behave differently now. See compare.py."""

    class DfSyncOverride(RestEndpoint):
        name: str = Field(min_length=1)

        def get(self, request: Any) -> Any:
            return {"served_by": "sync override"}

        def post(self, request: Any) -> Any:
            return self.create({"name": "from the override"})

    app = LightApi(engine=memory_engine())
    app.register({"/dfsyncoverride": DfSyncOverride})
    client = client_for(app)
    rec.http("changes/sync-override-get", client.get("/dfsyncoverride"))
    rec.http("changes/sync-override-get-detail", client.get("/dfsyncoverride/1"))
    rec.http(
        "changes/sync-override-post",
        client.post("/dfsyncoverride", json={"name": "sent"}),
    )

    class DirectoryBackend(JWTAuthentication):
        def validate_credentials(self, username: str, password: str) -> Any:
            return check_login(username, password)

    class DfDirectory(RestEndpoint):
        text: str = Field(min_length=1)

        class Meta:
            authentication = Authentication(DirectoryBackend, IsAuthenticated)

    subclassed = LightApi(engine=memory_engine())
    subclassed.register({"/dfdirectory": DfDirectory})
    client = client_for(subclassed)
    good = {"username": "alice", "password": "secret"}
    rec.http(
        "changes/login-with-subclass-backend", client.post("/auth/login", json=good)
    )
    rec.http(
        "changes/login-with-subclass-wrong-password",
        client.post("/auth/login", json={**good, "password": "x"}),
    )
    rec.http("changes/subclass-backend-still-guards", client.get("/dfdirectory"))
    rec.http(
        "changes/subclass-backend-accepts-token",
        client.get("/dfdirectory", headers=bearer(USER)),
    )
