from enum import Enum


# ─────────────────────────────────────────────────────────────────────────
# HTTP Status Codes
# ─────────────────────────────────────────────────────────────────────────
class HTTPStatus(int, Enum):
    OK = 200
    CREATED = 201
    NO_CONTENT = 204
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    METHOD_NOT_ALLOWED = 405
    CONFLICT = 409
    UNPROCESSABLE_ENTITY = 422
    TOO_MANY_REQUESTS = 429


# ─────────────────────────────────────────────────────────────────────────
# Response Keys
# ─────────────────────────────────────────────────────────────────────────
RESPONSE_KEY_DETAIL = "detail"
RESPONSE_KEY_RESULTS = "results"
RESPONSE_KEY_TOKEN = "token"
RESPONSE_KEY_USER = "user"
RESPONSE_KEY_COUNT = "count"
RESPONSE_KEY_PAGES = "pages"
RESPONSE_KEY_NEXT = "next"
RESPONSE_KEY_PREVIOUS = "previous"

# ─────────────────────────────────────────────────────────────────────────
# Pagination
# ─────────────────────────────────────────────────────────────────────────
DEFAULT_PAGE_SIZE = 20
PAGE_PARAM = "page"
CURSOR_PARAM = "cursor"
VALID_PAGINATION_STYLES = ("page_number", "cursor")

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
