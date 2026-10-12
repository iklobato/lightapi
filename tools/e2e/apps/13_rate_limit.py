"""e2e app for scenario 13: the login route is rate limited, CRUD routes are not."""

import os

from sqlalchemy import create_engine
from validators import check_login

from lightapi import (
    Authentication,
    Field,
    IsAuthenticated,
    JWTAuthentication,
    LightApi,
    RateLimiter,
    RestEndpoint,
)


class Secret(RestEndpoint):
    text: str = Field(min_length=1)

    class Meta:
        table = "e2e13_secrets"
        authentication = Authentication(
            backend=JWTAuthentication, permission=IsAuthenticated
        )


class Public(RestEndpoint):
    text: str = Field(min_length=1)

    class Meta:
        table = "e2e13_public"


def main() -> None:
    app = LightApi(
        engine=create_engine(os.environ["E2E_DB_URL"]),
        login_validator=check_login,
        rate_limiter=RateLimiter(requests_per_minute=3),
    )
    app.register({"/secrets": Secret, "/public": Public})
    app.run(host="127.0.0.1", port=int(os.environ["E2E_PORT"]))


if __name__ == "__main__":
    main()
