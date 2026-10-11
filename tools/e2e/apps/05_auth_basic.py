"""e2e app for scenario 05: BasicAuthentication with its own validate_credentials."""

import os

from sqlalchemy import create_engine
from validators import check_login

from lightapi import (
    Authentication,
    BasicAuthentication,
    Field,
    IsAuthenticated,
    LightApi,
    RestEndpoint,
)


class E2EBasic(BasicAuthentication):
    def validate_credentials(self, username: str, password: str) -> dict | None:
        return check_login(username, password)


class Ledger(RestEndpoint):
    entry: str = Field(min_length=1)

    class Meta:
        table = "e2e05_ledger"
        authentication = Authentication(backend=E2EBasic, permission=IsAuthenticated)


def main() -> None:
    # No login_validator on the app: the subclass's validate_credentials is what
    # the guard and the login route must call.
    app = LightApi(engine=create_engine(os.environ["E2E_DB_URL"]))
    app.register({"/ledger": Ledger})
    app.run(host="127.0.0.1", port=int(os.environ["E2E_PORT"]))


if __name__ == "__main__":
    main()
