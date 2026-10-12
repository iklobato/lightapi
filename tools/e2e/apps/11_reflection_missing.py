"""e2e app for scenario 11: reflecting a table that does not exist refuses to start."""

import os

from sqlalchemy import create_engine

from lightapi import LightApi, RestEndpoint


class Ghost(RestEndpoint):
    class Meta:
        table = "e2e11_ghost"
        reflect = True


def main() -> None:
    app = LightApi(engine=create_engine(os.environ["E2E_DB_URL"]))
    app.register({"/ghost": Ghost})
    app.run(host="127.0.0.1", port=int(os.environ["E2E_PORT"]))


if __name__ == "__main__":
    main()
