from enum import Enum
from http import HTTPStatus
from typing import Final

from starlette.responses import JSONResponse

from lightapi.exceptions import ConfigurationError


# ─────────────────────────────────────────────────────────────────────────
# Execution mode (sync Engine or AsyncEngine)
# ─────────────────────────────────────────────────────────────────────────
class ExecutionMode(str, Enum):
    SYNC = "sync"
    ASYNC = "async"

    @classmethod
    def from_user(cls, mode: "str | None") -> "ExecutionMode":
        """The mode named by LightApi(mode=...); 'sync' when none is given."""
        if mode is None:
            return cls.SYNC
        try:
            return cls(mode)
        except ValueError:
            raise ConfigurationError(
                f"mode must be 'sync' or 'async', got '{mode}'"
            ) from None


# ─────────────────────────────────────────────────────────────────────────
# Response Keys
# ─────────────────────────────────────────────────────────────────────────
class ResponseKey(str, Enum):
    DETAIL = "detail"
    RESULTS = "results"
    TOKEN = "token"
    USER = "user"
    COUNT = "count"
    PAGES = "pages"
    NEXT = "next"
    PREVIOUS = "previous"


# ─────────────────────────────────────────────────────────────────────────
# HTTP verbs (lightapi.HttpMethod is the public marker namespace, not this)
# ─────────────────────────────────────────────────────────────────────────
class HttpVerb(str, Enum):
    """A request method. Compare `request.method == HttpVerb.GET`; never format it."""

    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"
    OPTIONS = "OPTIONS"

    @classmethod
    def of(cls, method: str) -> "HttpVerb | None":
        """The verb for a request method; None for one the API never serves (HEAD)."""
        try:
            return cls(method)
        except ValueError:
            return None


CRUD_VERBS: Final = frozenset(
    {HttpVerb.GET, HttpVerb.POST, HttpVerb.PUT, HttpVerb.PATCH, HttpVerb.DELETE}
)


# ─────────────────────────────────────────────────────────────────────────
# Error replies with a fixed text (status, detail, extra headers)
# ─────────────────────────────────────────────────────────────────────────
class ApiError(Enum):
    NOT_FOUND = (HTTPStatus.NOT_FOUND, "not found")
    VERSION_CONFLICT = (HTTPStatus.CONFLICT, "version conflict")
    AUTHENTICATION_REQUIRED = (
        HTTPStatus.UNAUTHORIZED,
        "Authentication required",
        {"WWW-Authenticate": "Bearer"},
    )
    INSUFFICIENT_PERMISSIONS = (HTTPStatus.FORBIDDEN, "Insufficient permissions")
    INVALID_CREDENTIALS = (HTTPStatus.UNAUTHORIZED, "Invalid credentials")
    LOGIN_METHOD_NOT_ALLOWED = (
        HTTPStatus.METHOD_NOT_ALLOWED,
        "method not allowed",
        {"Allow": HttpVerb.POST.value},
    )

    def __init__(
        self, status: HTTPStatus, detail: str, headers: "dict[str, str] | None" = None
    ) -> None:
        self.status = status
        self.detail = detail
        self.headers = headers

    def response(self) -> JSONResponse:
        return JSONResponse(
            {ResponseKey.DETAIL: self.detail},
            status_code=self.status,
            headers=self.headers,
        )

    @staticmethod
    def validation_failed(errors: object) -> JSONResponse:
        """The 422 reply; `errors` is pydantic's error list or one built like it."""
        return JSONResponse(
            {ResponseKey.DETAIL: errors}, status_code=HTTPStatus.UNPROCESSABLE_ENTITY
        )


# ─────────────────────────────────────────────────────────────────────────
# Table reflection (Meta.reflect)
# ─────────────────────────────────────────────────────────────────────────
class TableReflection(str, Enum):
    """Map the endpoint onto an existing table instead of generating one.

    PARTIAL also keeps the fields the endpoint declares itself.
    """

    FULL = "full"
    PARTIAL = "partial"

    @classmethod
    def from_meta(cls, value: object) -> "TableReflection | None":
        """Meta.reflect takes True, False, "full" or "partial"; None: no reflection."""
        if value is None or value is False:
            return None
        if value is True:
            return cls.FULL
        try:
            return cls(value)
        except ValueError:
            raise ConfigurationError(
                f"Meta.reflect must be True, False, 'full' or 'partial', got {value!r}."
            ) from None


# ─────────────────────────────────────────────────────────────────────────
# Pagination
# ─────────────────────────────────────────────────────────────────────────
DEFAULT_PAGE_SIZE = 20
PAGE_PARAM = "page"
CURSOR_PARAM = "cursor"

# ─────────────────────────────────────────────────────────────────────────
# Auto Fields (consolidated)
# ─────────────────────────────────────────────────────────────────────────
AUTO_FIELDS = frozenset({"id", "created_at", "updated_at", "version"})


# ─────────────────────────────────────────────────────────────────────────
# Auth / JWT
# ─────────────────────────────────────────────────────────────────────────
class JwtAlgorithm(str, Enum):
    """Signing algorithms PyJWT accepts here; the value is what PyJWT receives."""

    HS256 = "HS256"
    HS384 = "HS384"
    HS512 = "HS512"
    RS256 = "RS256"
    RS384 = "RS384"
    RS512 = "RS512"
    ES256 = "ES256"
    ES384 = "ES384"
    ES512 = "ES512"

    @classmethod
    def validated(cls, name: str) -> str:
        """The name as PyJWT takes it; ConfigurationError for an unknown one."""
        try:
            return cls(name).value
        except ValueError:
            raise ConfigurationError(
                f"Invalid JWT algorithm '{name}'. "
                f"Valid algorithms are: {sorted(valid.value for valid in cls)}"
            ) from None


DEFAULT_JWT_ALGORITHM = JwtAlgorithm.HS256.value
DEFAULT_JWT_EXPIRATION = 3600  # seconds

# ─────────────────────────────────────────────────────────────────────────
# Cache
# ─────────────────────────────────────────────────────────────────────────
DEFAULT_REDIS_URL = "redis://localhost:6379/0"
DEFAULT_CACHE_TTL = 60  # seconds
