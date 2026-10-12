"""Sync-engine scenarios of the differential run, one function per feature area."""

from __future__ import annotations

import datetime
import time
import uuid
from decimal import Decimal
from typing import Any, Optional

import jwt
from diff_validators import check_login, exploding_login
from harness import JWT_SECRET, Recorder, bearer, client_for, memory_engine
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    MetaData,
    Numeric,
    String,
    Table,
    Text,
    create_engine,
    select,
    text,
)

from lightapi import (
    AllowAny,
    Authentication,
    BasicAuthentication,
    Cache,
    Field,
    FieldFilter,
    Filtering,
    HttpMethod,
    IsAdminUser,
    IsAuthenticated,
    JWTAuthentication,
    LightApi,
    Middleware,
    OrderingFilter,
    Pagination,
    RestEndpoint,
    SearchFilter,
    Serializer,
)
from lightapi.core import CORSMiddleware

Step = tuple[str, str, str, dict[str, Any]]
FIXED_UID = "6f1c1f0a-5f0e-4c3b-9d2a-0c7e8f9a1b2c"
BASIC_ALICE = {"Authorization": "Basic YWxpY2U6c2VjcmV0"}  # alice:secret
BASIC_WRONG = {"Authorization": "Basic YWxpY2U6d3Jvbmc="}  # alice:wrong
BASIC_BROKEN = {"Authorization": "Basic !!!not-base64!!!"}
USER = {"sub": "alice", "is_admin": False}
ADMIN = {"sub": "root", "is_admin": True}


def play(rec: Recorder, group: str, client: Any, steps: list[Step]) -> None:
    for label, method, url, kwargs in steps:
        rec.http(f"{group}/{label}", client.request(method, url, **kwargs))


def book_endpoint(name: str) -> type:
    """A fresh endpoint class: a class can only be mapped to one table."""
    namespace = {
        "__module__": __name__,
        "__annotations__": {
            "title": str,
            "pages": int,
            "price": Decimal,
            "rating": Optional[float],
            "in_print": bool,
            "published": Optional[datetime.datetime],
            "uid": Optional[uuid.UUID],
        },
        "title": Field(min_length=1, max_length=50),
        "pages": Field(ge=1),
        "price": Field(decimal_places=2),
        "rating": Field(default=None),
        "in_print": Field(default=True),
        "published": Field(default=None),
        "uid": Field(default=None),
    }
    return type(name, (RestEndpoint,), namespace)


def crud_steps(route: str) -> list[Step]:
    full = {
        "title": "Dune",
        "pages": 412,
        "price": "9.99",
        "rating": 4.5,
        "in_print": False,
        "published": "1965-08-01T00:00:00",
        "uid": FIXED_UID,
    }
    one = f"{route}/1"
    return [
        ("list-empty", "GET", route, {}),
        ("create-full", "POST", route, {"json": full}),
        (
            "create-minimal",
            "POST",
            route,
            {"json": {"title": "B", "pages": 1, "price": 1}},
        ),
        ("create-missing-field", "POST", route, {"json": {"title": "x"}}),
        ("create-wrong-type", "POST", route, {"json": {**full, "pages": "many"}}),
        ("create-too-long", "POST", route, {"json": {**full, "title": "x" * 51}}),
        ("create-below-minimum", "POST", route, {"json": {**full, "pages": 0}}),
        ("create-extra-field", "POST", route, {"json": {**full, "colour": "red"}}),
        (
            "create-auto-field",
            "POST",
            route,
            {"json": {**full, "id": 99, "version": 7}},
        ),
        ("create-not-json", "POST", route, {"content": b"{not json"}),
        ("create-empty-body", "POST", route, {}),
        ("list-after-create", "GET", route, {}),
        ("retrieve", "GET", one, {}),
        ("retrieve-missing", "GET", f"{route}/999", {}),
        ("retrieve-not-int", "GET", f"{route}/abc", {}),
        ("put-without-version", "PUT", one, {"json": full}),
        ("put-stale-version", "PUT", one, {"json": {**full, "version": 9}}),
        ("put-ok", "PUT", one, {"json": {**full, "title": "Dune II", "version": 1}}),
        ("put-missing-field", "PUT", one, {"json": {"title": "x", "version": 2}}),
        ("put-missing-row", "PUT", f"{route}/999", {"json": {**full, "version": 1}}),
        ("patch-one-field", "PATCH", one, {"json": {"pages": 500, "version": 2}}),
        ("patch-null-nullable", "PATCH", one, {"json": {"rating": None, "version": 3}}),
        ("patch-null-required", "PATCH", one, {"json": {"title": None, "version": 4}}),
        ("patch-wrong-type", "PATCH", one, {"json": {"pages": "x", "version": 5}}),
        ("patch-stale-version", "PATCH", one, {"json": {"pages": 1, "version": 1}}),
        ("patch-missing-row", "PATCH", f"{route}/999", {"json": {"version": 1}}),
        ("retrieve-after-updates", "GET", one, {}),
        ("head-collection", "HEAD", route, {}),
        ("options-collection", "OPTIONS", route, {}),
        ("post-on-detail", "POST", one, {"json": full}),
        ("delete-on-collection", "DELETE", route, {}),
        ("trailing-slash", "GET", f"{route}/", {"follow_redirects": False}),
        ("delete", "DELETE", one, {}),
        ("delete-again", "DELETE", one, {}),
        ("list-after-delete", "GET", route, {}),
    ]


def crud(rec: Recorder, tmp_dir: str) -> None:
    app = LightApi(engine=memory_engine())
    app.register({"/dfbooks": book_endpoint("DfBook")})
    client = client_for(app)
    play(rec, "crud-memory", client, crud_steps("/dfbooks"))
    play(
        rec,
        "crud-memory",
        client,
        [("healthz", "GET", "/healthz", {}), ("unknown-route", "GET", "/nope", {})],
    )

    # A file database gets a real connection pool, which is the engine kind
    # whose sync CRUD the refactor moved to a worker thread.
    pooled = LightApi(engine=create_engine(f"sqlite:///{tmp_dir}/pooled.db"))
    pooled.register({"/dfpooledbooks": book_endpoint("DfPooledBook")})
    play(rec, "crud-pooled", client_for(pooled), crud_steps("/dfpooledbooks"))


def allowed_methods(rec: Recorder) -> None:
    class DfReadOnly(RestEndpoint, HttpMethod.GET):
        name: str = Field(min_length=1)

    class DfNoDelete(RestEndpoint, HttpMethod.GET, HttpMethod.POST, HttpMethod.PUT):
        name: str = Field(min_length=1)

    app = LightApi(engine=memory_engine())
    app.register({"/dfreadonly": DfReadOnly, "/dfnodelete": DfNoDelete})
    play(
        rec,
        "methods",
        client_for(app),
        [
            ("read-only-get", "GET", "/dfreadonly", {}),
            ("read-only-post", "POST", "/dfreadonly", {"json": {"name": "x"}}),
            ("read-only-head", "HEAD", "/dfreadonly", {}),
            ("read-only-detail-put", "PUT", "/dfreadonly/1", {"json": {}}),
            ("no-delete-post", "POST", "/dfnodelete", {"json": {"name": "x"}}),
            ("no-delete-delete", "DELETE", "/dfnodelete/1", {}),
            ("no-delete-patch", "PATCH", "/dfnodelete/1", {"json": {"version": 1}}),
            (
                "no-delete-put",
                "PUT",
                "/dfnodelete/1",
                {"json": {"name": "y", "version": 1}},
            ),
        ],
    )


def serializers(rec: Recorder) -> None:
    class PublicView(Serializer):
        read = ["id", "name", "version"]
        write = ["id"]

    def endpoint(name: str, serializer: Any) -> type:
        meta = type("Meta", (), {"serializer": serializer})
        namespace = {
            "__module__": __name__,
            "__annotations__": {"name": str, "secret": Optional[str]},
            "name": Field(min_length=1),
            "secret": Field(default=None),
            "Meta": meta,
        }
        return type(name, (RestEndpoint,), namespace)

    routes = {
        "/dfser-all": endpoint("DfSerAll", Serializer()),
        "/dfser-fields": endpoint("DfSerFields", Serializer(fields=["id", "name"])),
        "/dfser-split": endpoint(
            "DfSerSplit",
            Serializer(read=["id", "name", "secret"], write=["id", "version"]),
        ),
        "/dfser-subclass": endpoint("DfSerSubclass", PublicView),
    }
    app = LightApi(engine=memory_engine())
    app.register(routes)
    client = client_for(app)
    body = {"name": "visible", "secret": "hidden"}
    for route in routes:
        play(
            rec,
            f"serializer{route}",
            client,
            [
                ("create", "POST", route, {"json": body}),
                ("list", "GET", route, {}),
                ("retrieve", "GET", f"{route}/1", {}),
                ("put", "PUT", f"{route}/1", {"json": {**body, "version": 1}}),
            ],
        )


def filtering_and_pagination(rec: Recorder) -> None:
    class DfArticle(RestEndpoint):
        title: str = Field(min_length=1)
        body: str = Field(min_length=1)
        category: str = Field(min_length=1)
        published: bool = Field(default=False)
        views: int = Field(default=0)

        class Meta:
            filtering = Filtering(
                backends=[FieldFilter, SearchFilter, OrderingFilter],
                fields=["category", "published", "views"],
                search=["title", "body"],
                ordering=["title", "views"],
            )
            pagination = Pagination(style="page_number", page_size=3)

    class DfEvent(RestEndpoint):
        name: str = Field(min_length=1)

        class Meta:
            pagination = Pagination(style="cursor", page_size=3)

    class DfUnordered(RestEndpoint):
        name: str = Field(min_length=1)

        class Meta:
            filtering = Filtering(backends=[OrderingFilter])

    app = LightApi(engine=memory_engine())
    app.register(
        {"/dfarticles": DfArticle, "/dfevents": DfEvent, "/dfunordered": DfUnordered}
    )
    client = client_for(app)
    rows = [
        ("python tips", "use 100% of it", "tech", True, 30),
        ("a_b testing", "split traffic", "tech", False, 10),
        ("axb testing", "not the same", "tech", True, 20),
        ("gardening", "plant python beans", "home", True, 5),
        ("50% off", "sale of the year", "shop", False, 50),
        ("cooking", "low heat", "home", False, 15),
        ("travel", "pack light", "life", True, 25),
        ("zebra facts", "stripes", "life", False, 1),
    ]
    for title, body, category, published, views in rows:
        client.post(
            "/dfarticles",
            json={
                "title": title,
                "body": body,
                "category": category,
                "published": published,
                "views": views,
            },
        )
    queries = [
        "",
        "?category=tech",
        "?published=true",
        "?published=0",
        "?views=10",
        "?views=ten",
        "?title=gardening",
        "?category=tech&published=true",
        "?search=python",
        "?search=100%25",
        "?search=a_b",
        "?search=",
        "?ordering=-views",
        "?ordering=title,-views",
        "?ordering=body",
        "?ordering=-views&page=2",
        "?page=2",
        "?page=3",
        "?page=0",
        "?page=99",
        "?page=abc",
        "?page=2&category=tech",
    ]
    for query in queries:
        rec.http(
            f"filtering/articles{query or '?none'}", client.get(f"/dfarticles{query}")
        )

    for n in range(7):
        client.post("/dfevents", json={"name": f"event-{n}"})
    url, hops = "/dfevents", 0
    while url and hops < 6:
        page = rec.http(f"cursor/page-{hops}", client.get(url))
        cursor = page.json().get("next") if page.status_code == 200 else None
        url, hops = (f"/dfevents?cursor={cursor}" if cursor else None), hops + 1
    rec.http("cursor/garbage", client.get("/dfevents?cursor=%%%"))

    for name in ("b", "a", "c"):
        client.post("/dfunordered", json={"name": name})
    rec.http("ordering/no-whitelist", client.get("/dfunordered?ordering=-name"))


def auth_endpoints() -> dict[str, type]:
    def endpoint(name: str, authentication: Authentication) -> type:
        meta = type("Meta", (), {"authentication": authentication})
        namespace = {
            "__module__": __name__,
            "__annotations__": {"text": str},
            "text": Field(min_length=1),
            "Meta": meta,
        }
        return type(name, (RestEndpoint,), namespace)

    jwt_, basic = JWTAuthentication, BasicAuthentication
    per_method = {"GET": AllowAny, "POST": IsAuthenticated, "DELETE": IsAdminUser}
    return {
        "/dfjwt": endpoint("DfJwt", Authentication(jwt_, IsAuthenticated)),
        "/dfadmin": endpoint("DfAdmin", Authentication(jwt_, IsAdminUser)),
        "/dfbasic": endpoint("DfBasic", Authentication(basic, IsAuthenticated)),
        "/dfpublic": endpoint("DfPublic", Authentication(jwt_, AllowAny)),
        "/dfpermethod": endpoint("DfPerMethod", Authentication(jwt_, per_method)),
        "/dfbackendonly": endpoint("DfBackendOnly", Authentication(jwt_)),
        "/dfpermissiononly": endpoint(
            "DfPermissionOnly", Authentication(permission=IsAuthenticated)
        ),
    }


def authentication(rec: Recorder) -> None:
    app = LightApi(engine=memory_engine(), login_validator=check_login)
    app.register(auth_endpoints())
    client = client_for(app)
    user, admin = bearer(USER), bearer(ADMIN)
    expired = bearer(USER, expiration=-10)
    forged = {
        "Authorization": "Bearer "
        + jwt.encode({"sub": "mallory"}, "another-secret", algorithm="HS256")
    }
    note = {"json": {"text": "hello"}}
    steps: list[Step] = [
        ("jwt-anonymous", "GET", "/dfjwt", {}),
        ("jwt-garbage", "GET", "/dfjwt", {"headers": {"Authorization": "Bearer x"}}),
        ("jwt-wrong-scheme", "GET", "/dfjwt", {"headers": BASIC_ALICE}),
        ("jwt-expired", "GET", "/dfjwt", {"headers": expired}),
        ("jwt-forged", "GET", "/dfjwt", {"headers": forged}),
        ("jwt-user", "GET", "/dfjwt", {"headers": user}),
        ("jwt-user-create", "POST", "/dfjwt", {"headers": user, **note}),
        ("admin-as-user", "GET", "/dfadmin", {"headers": user}),
        ("admin-as-admin", "GET", "/dfadmin", {"headers": admin}),
        ("admin-anonymous", "GET", "/dfadmin", {}),
        ("basic-anonymous", "GET", "/dfbasic", {}),
        ("basic-valid", "GET", "/dfbasic", {"headers": BASIC_ALICE}),
        ("basic-wrong-password", "GET", "/dfbasic", {"headers": BASIC_WRONG}),
        ("basic-malformed", "GET", "/dfbasic", {"headers": BASIC_BROKEN}),
        ("basic-with-bearer", "GET", "/dfbasic", {"headers": user}),
        ("public-anonymous", "GET", "/dfpublic", {}),
        ("public-anonymous-create", "POST", "/dfpublic", note),
        ("per-method-get-anonymous", "GET", "/dfpermethod", {}),
        ("per-method-post-anonymous", "POST", "/dfpermethod", note),
        ("per-method-post-user", "POST", "/dfpermethod", {"headers": user, **note}),
        ("per-method-delete-user", "DELETE", "/dfpermethod/1", {"headers": user}),
        ("per-method-delete-admin", "DELETE", "/dfpermethod/1", {"headers": admin}),
        ("per-method-put-anonymous", "PUT", "/dfpermethod/1", {"json": {}}),
        ("backend-only-anonymous", "GET", "/dfbackendonly", {}),
        ("backend-only-user", "GET", "/dfbackendonly", {"headers": user}),
        ("permission-only-anonymous", "GET", "/dfpermissiononly", {}),
        ("permission-only-user", "GET", "/dfpermissiononly", {"headers": user}),
    ]
    play(rec, "auth", client, steps)

    good = {"username": "alice", "password": "secret"}
    login: list[Step] = [
        ("login-json", "POST", "/auth/login", {"json": good}),
        ("token-json", "POST", "/auth/token", {"json": good}),
        (
            "login-wrong-password",
            "POST",
            "/auth/login",
            {"json": {**good, "password": "x"}},
        ),
        (
            "login-unknown-user",
            "POST",
            "/auth/login",
            {"json": {**good, "username": "x"}},
        ),
        ("login-missing-password", "POST", "/auth/login", {"json": {"username": "a"}}),
        (
            "login-empty-username",
            "POST",
            "/auth/login",
            {"json": {**good, "username": ""}},
        ),
        ("login-empty-body", "POST", "/auth/login", {}),
        ("login-not-json", "POST", "/auth/login", {"content": b"user=alice"}),
        ("login-basic-header", "POST", "/auth/login", {"headers": BASIC_ALICE}),
        ("login-basic-wrong", "POST", "/auth/login", {"headers": BASIC_WRONG}),
        ("login-basic-malformed", "POST", "/auth/login", {"headers": BASIC_BROKEN}),
        ("login-get", "GET", "/auth/login", {}),
    ]
    play(rec, "login", client, login)
    issued = client.post("/auth/login", json={"username": "root", "password": "toor"})
    claims = jwt.decode(issued.json()["token"], JWT_SECRET, algorithms=["HS256"])
    rec.note("login/token-claims", sorted(claims))
    rec.note("login/token-minutes", round((claims["exp"] - time.time()) / 60))
    reuse = {"Authorization": f"Bearer {issued.json()['token']}"}
    rec.http("login/issued-token-works", client.get("/dfadmin", headers=reuse))


def login_variants(rec: Recorder) -> None:
    def protected(name: str, authentication: Authentication) -> type:
        meta = type("Meta", (), {"authentication": authentication})
        namespace = {
            "__module__": __name__,
            "__annotations__": {"text": str},
            "Meta": meta,
        }
        return type(name, (RestEndpoint,), namespace)

    good = {"username": "alice", "password": "secret"}

    claims_app = LightApi(engine=memory_engine(), login_validator=check_login)
    claims_auth = Authentication(
        JWTAuthentication,
        IsAuthenticated,
        jwt_expiration=300,
        jwt_extra_claims=["role", "absent"],
    )
    claims_app.register({"/dfclaims": protected("DfClaims", claims_auth)})
    issued = client_for(claims_app).post("/auth/login", json=good)
    rec.http("login-claims/login", issued)
    claims = jwt.decode(issued.json()["token"], JWT_SECRET, algorithms=["HS256"])
    rec.note("login-claims/token-claims", sorted(claims))
    rec.note("login-claims/token-minutes", round((claims["exp"] - time.time()) / 60))

    rooted = LightApi(
        engine=memory_engine(), login_validator=check_login, auth_path="/"
    )
    rooted.register(
        {"/dfrooted": protected("DfRooted", Authentication(JWTAuthentication))}
    )
    client = client_for(rooted)
    rec.http("login-root-path/login", client.post("/login", json=good))
    rec.http("login-root-path/old-path", client.post("/auth/login", json=good))

    basic_app = LightApi(engine=memory_engine(), login_validator=check_login)
    basic_auth = Authentication(BasicAuthentication, IsAuthenticated)
    basic_app.register({"/dfbasiconly": protected("DfBasicOnly", basic_auth)})
    rec.http(
        "login-basic-app/login", client_for(basic_app).post("/auth/login", json=good)
    )

    no_auth = LightApi(engine=memory_engine(), login_validator=check_login)
    no_auth.register(
        {"/dfopen": protected("DfOpen", Authentication(permission=AllowAny))}
    )
    rec.http(
        "login-no-backend/login", client_for(no_auth).post("/auth/login", json=good)
    )

    broken = LightApi(engine=memory_engine(), login_validator=exploding_login)
    broken.register(
        {"/dfbroken": protected("DfBroken", Authentication(JWTAuthentication))}
    )
    rec.http(
        "login-validator-raises/login",
        client_for(broken).post("/auth/login", json=good),
    )

    limited = LightApi(
        engine=memory_engine(),
        login_validator=check_login,
        rate_limiter={"requests_per_minute": 2},
    )
    limited.register(
        {"/dflimited": protected("DfLimited", Authentication(JWTAuthentication))}
    )
    client = client_for(limited)
    for attempt in range(4):
        rec.http(
            f"login-rate-limit/attempt-{attempt}", client.post("/auth/login", json=good)
        )


def middleware(rec: Recorder) -> None:
    calls: list[str] = []

    class TraceOuter(Middleware):
        def process(self, request: Any, response: Any) -> Any:
            calls.append("outer-pre" if response is None else "outer-post")
            return response

    class TraceInnerAsync(Middleware):
        async def process(self, request: Any, response: Any) -> Any:
            calls.append("inner-pre" if response is None else "inner-post")
            if response is not None:
                response.headers["x-trace"] = "inner"
            return response

    class Blocker(Middleware):
        def process(self, request: Any, response: Any) -> Any:
            if response is None and request.headers.get("x-block"):
                from starlette.responses import JSONResponse

                return JSONResponse({"detail": "blocked"}, status_code=403)
            return response

    class DfTraced(RestEndpoint):
        name: str = Field(min_length=1)

    app = LightApi(
        engine=memory_engine(), middlewares=[TraceOuter, TraceInnerAsync, Blocker]
    )
    app.register({"/dftraced": DfTraced})
    client = client_for(app)
    rec.http("middleware/get", client.get("/dftraced"))
    rec.note("middleware/get-calls", list(calls))
    calls.clear()
    rec.http("middleware/blocked", client.post("/dftraced", headers={"x-block": "1"}))
    rec.note("middleware/blocked-calls", list(calls))
    rec.http("middleware/healthz-is-not-wrapped", client.get("/healthz"))

    class DfCors(RestEndpoint):
        name: str = Field(min_length=1)

    origin = {"Origin": "https://app.example.com"}
    preflight = {**origin, "Access-Control-Request-Method": "POST"}
    starlette_cors = LightApi(
        engine=memory_engine(), cors_origins=["https://app.example.com"]
    )
    starlette_cors.register({"/dfcors": DfCors})
    client = client_for(starlette_cors)
    rec.http("cors-origins/preflight", client.options("/dfcors", headers=preflight))
    rec.http("cors-origins/get", client.get("/dfcors", headers=origin))
    rec.http(
        "cors-origins/other-origin",
        client.get("/dfcors", headers={"Origin": "https://x.io"}),
    )

    class DfOwnCors(RestEndpoint):
        name: str = Field(min_length=1)

    own_cors = LightApi(engine=memory_engine(), middlewares=[CORSMiddleware])
    own_cors.register({"/dfowncors": DfOwnCors})
    client = client_for(own_cors)
    rec.http("cors-middleware/get", client.get("/dfowncors", headers=origin))
    rec.http("cors-middleware/post", client.post("/dfowncors", json={"name": "x"}))
    rec.http("cors-middleware/not-found", client.get("/dfowncors/9"))
    rec.http("cors-middleware/delete", client.delete("/dfowncors/1"))


def reflection(rec: Recorder) -> None:
    engine = memory_engine()
    legacy = MetaData()
    for name in ("df_legacy", "df_partial"):
        Table(
            name,
            legacy,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("label", String(40), nullable=False),
            Column("notes", Text, nullable=True),
            Column("amount", Numeric(10, 2), nullable=True),
            Column("ratio", Float, nullable=True),
            Column("active", Boolean, nullable=True),
            Column("created_at", DateTime),
            Column("updated_at", DateTime),
            Column("version", Integer, nullable=False, default=1),
        )
    legacy.create_all(engine)

    class DfLegacy(RestEndpoint):
        class Meta:
            reflect = True
            table = "df_legacy"

    class DfPartial(RestEndpoint):
        notes: Optional[str] = Field(default=None)

        class Meta:
            reflect = "partial"
            table = "df_partial"

    class DfGhost(RestEndpoint):
        class Meta:
            reflect = True
            table = "df_does_not_exist"

    app = LightApi(engine=engine)
    app.register({"/dflegacy": DfLegacy, "/dfpartial": DfPartial})
    client = client_for(app)
    row = {
        "label": "first",
        "notes": "n",
        "amount": "12.50",
        "ratio": 0.5,
        "active": True,
    }
    for route in ("/dflegacy", "/dfpartial"):
        play(
            rec,
            f"reflection{route}",
            client,
            [
                ("create", "POST", route, {"json": row}),
                ("create-missing-required", "POST", route, {"json": {"notes": "x"}}),
                (
                    "create-wrong-type",
                    "POST",
                    route,
                    {"json": {**row, "amount": "abc"}},
                ),
                ("list", "GET", route, {}),
                (
                    "patch",
                    "PATCH",
                    f"{route}/1",
                    {"json": {"notes": None, "version": 1}},
                ),
                (
                    "put",
                    "PUT",
                    f"{route}/1",
                    {"json": {**row, "label": "second", "version": 2}},
                ),
                ("delete", "DELETE", f"{route}/1", {}),
            ],
        )
    try:
        LightApi(engine=engine).register({"/dfghost": DfGhost})
    except Exception as error:
        rec.raised("reflection/missing-table", error)


def custom_queryset(rec: Recorder) -> None:
    class DfTask(RestEndpoint):
        name: str = Field(min_length=1)
        done: bool = Field(default=False)

        def queryset(self, request: Any) -> Any:
            model = type(self)._model_class
            return (
                select(model).where(model.done.is_(False)).order_by(model.name.desc())
            )

    app = LightApi(engine=memory_engine())
    app.register({"/dftasks": DfTask})
    client = client_for(app)
    for name, done in (("a", False), ("b", True), ("c", False)):
        client.post("/dftasks", json={"name": name, "done": done})
    rec.http("queryset/list-filters-and-orders", client.get("/dftasks"))
    rec.http("queryset/retrieve-ignores-queryset", client.get("/dftasks/2"))


def response_cache(rec: Recorder, fake_redis: Any) -> None:
    class DfCached(RestEndpoint):
        name: str = Field(min_length=1)

        class Meta:
            cache = Cache(ttl=60)

    engine = memory_engine()
    app = LightApi(engine=engine)
    app.register({"/dfcached": DfCached})
    client = client_for(app)
    client.post("/dfcached", json={"name": "original"})

    def change_row_behind_the_cache() -> None:
        with engine.begin() as connection:
            connection.execute(
                text("UPDATE dfcacheds SET name = 'changed in the database'")
            )

    rec.http("cache-sync/first-get-misses", client.get("/dfcached"))
    rec.note("cache-sync/keys-after-first-get", sorted(fake_redis.store))
    change_row_behind_the_cache()
    rec.http("cache-sync/second-get-is-served-from-cache", client.get("/dfcached"))
    rec.http("cache-sync/other-query-string-misses", client.get("/dfcached?x=1"))
    rec.http("cache-sync/detail-get", client.get("/dfcached/1"))
    rec.note("cache-sync/keys-before-write", sorted(fake_redis.store))
    rec.http(
        "cache-sync/post-invalidates", client.post("/dfcached", json={"name": "new"})
    )
    rec.note("cache-sync/keys-after-write", sorted(fake_redis.store))
    rec.http("cache-sync/get-after-write", client.get("/dfcached"))
    rec.http("cache-sync/not-found-is-not-cached", client.get("/dfcached/99"))
    rec.note("cache-sync/keys-at-end", sorted(fake_redis.store))


def schema_ddl(rec: Recorder) -> None:
    """Every table the run created, as each dialect would create it."""
    from sqlalchemy.dialects import postgresql, sqlite
    from sqlalchemy.schema import CreateIndex, CreateTable

    probe = LightApi(engine=memory_engine())
    metadata = probe._session_manager.metadata
    for dialect_name, dialect in (
        ("sqlite", sqlite.dialect()),
        ("postgresql", postgresql.dialect()),
    ):
        for table in sorted(metadata.tables.values(), key=lambda t: t.name):
            ddl = str(CreateTable(table).compile(dialect=dialect)).strip()
            rec.note(f"ddl/{dialect_name}/{table.name}", ddl)
            for index in sorted(table.indexes, key=lambda i: i.name or ""):
                created = str(CreateIndex(index).compile(dialect=dialect)).strip()
                rec.note(f"ddl/{dialect_name}/{table.name}/index/{index.name}", created)


def run(rec: Recorder, tmp_dir: str, fake_redis: Any) -> None:
    crud(rec, tmp_dir)
    allowed_methods(rec)
    serializers(rec)
    filtering_and_pagination(rec)
    authentication(rec)
    login_variants(rec)
    middleware(rec)
    reflection(rec)
    custom_queryset(rec)
    response_cache(rec, fake_redis)
