"""e2e app for scenario 04: JWT login, permissions per method, extra claims."""

import os

from sqlalchemy import create_engine
from validators import check_login

from lightapi import (
    AllowAny,
    Authentication,
    Field,
    IsAdminUser,
    IsAuthenticated,
    JWTAuthentication,
    LightApi,
    RestEndpoint,
)


class Secret(RestEndpoint):
    text: str = Field(min_length=1)

    class Meta:
        table = "e2e04_secrets"
        authentication = Authentication(
            backend=JWTAuthentication,
            permission=IsAuthenticated,
            jwt_expiration=120,
            jwt_extra_claims=["is_admin"],
        )


class AdminOnly(RestEndpoint):
    text: str = Field(min_length=1)

    class Meta:
        table = "e2e04_admin"
        authentication = Authentication(
            backend=JWTAuthentication, permission=IsAdminUser
        )


class Mixed(RestEndpoint):
    text: str = Field(min_length=1)

    class Meta:
        table = "e2e04_mixed"
        authentication = Authentication(
            backend=JWTAuthentication,
            permission={
                "GET": AllowAny,
                "POST": IsAuthenticated,
                "DELETE": IsAdminUser,
            },
        )


def main() -> None:
    # Secret first: the login route builds its tokens with the first JWT backend,
    # so jwt_expiration and jwt_extra_claims are the ones the token shows.
    app = LightApi(
        engine=create_engine(os.environ["E2E_DB_URL"]), login_validator=check_login
    )
    app.register({"/secrets": Secret, "/admin": AdminOnly, "/mixed": Mixed})
    app.run(host="127.0.0.1", port=int(os.environ["E2E_PORT"]))


if __name__ == "__main__":
    main()
