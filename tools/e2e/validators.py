"""Login validators the e2e apps and YAML documents use (PYTHONPATH=tools/e2e)."""

USERS = {
    "admin": ("secret", {"sub": "1", "username": "admin", "is_admin": True}),
    "user": ("password", {"sub": "2", "username": "user", "is_admin": False}),
}


def check_login(username: str, password: str) -> dict | None:
    known = USERS.get(username)
    if known is None or known[0] != password:
        return None
    return known[1]
