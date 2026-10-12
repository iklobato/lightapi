"""e2e app for scenario 15: optimistic locking under ten parallel writers."""

import os

from sqlalchemy import create_engine

from lightapi import Field, LightApi, RestEndpoint


class Counter(RestEndpoint):
    label: str = Field(min_length=1)
    hits: int = Field(default=0)

    class Meta:
        table = "e2e15_counters"


def main() -> None:
    app = LightApi(engine=create_engine(os.environ["E2E_DB_URL"]))
    app.register({"/counters": Counter})
    app.run(host="127.0.0.1", port=int(os.environ["E2E_PORT"]))


if __name__ == "__main__":
    main()
