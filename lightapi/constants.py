from enum import Enum
from typing import Final

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
DEFAULT_JWT_ALGORITHM = "HS256"
DEFAULT_JWT_EXPIRATION = 3600  # seconds
VALID_JWT_ALGORITHMS = frozenset(
    {
        "HS256",
        "HS384",
        "HS512",
        "RS256",
        "RS384",
        "RS512",
        "ES256",
        "ES384",
        "ES512",
    }
)

# ─────────────────────────────────────────────────────────────────────────
# Cache
# ─────────────────────────────────────────────────────────────────────────
DEFAULT_REDIS_URL = "redis://localhost:6379/0"
DEFAULT_CACHE_TTL = 60  # seconds
