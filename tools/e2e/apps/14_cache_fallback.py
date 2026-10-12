"""e2e app for scenario 14: Meta.cache with no Redis behind it."""

import os

from sqlalchemy import create_engine

from lightapi import Cache, Field, LightApi, RestEndpoint


class Report(RestEndpoint):
    title: str = Field(min_length=1)

    class Meta:
        table = "e2e14_reports"
        cache = Cache(ttl=5)


def main() -> None:
    app = LightApi(engine=create_engine(os.environ["E2E_DB_URL"]))
    app.register({"/reports": Report})
    app.run(host="127.0.0.1", port=int(os.environ["E2E_PORT"]))


if __name__ == "__main__":
    main()
