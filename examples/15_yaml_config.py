"""LightAPI Example 15 - YAML Configuration.

Demonstrates:
- LightApi.from_config() for declarative configuration
- YAML-based endpoint definition
- Authentication config in YAML
- Defaults applied to all endpoints

Notes:
    Uses SQLite by default — swap the `database.url` in the YAML
    below for a postgres URL to switch.

Run with:
    python examples/15_yaml_config.py

The equivalent YAML config is in examples/config.yaml
"""

import os
import tempfile

from lightapi import LightApi


def main():
    def simple_login_validator(username: str, password: str):
        if username == "admin" and password == "admin":
            return {"id": 1, "username": username}
        raise ValueError("Invalid credentials")

    yaml_content = """
database:
  url: "sqlite:///example_15_yaml.db"

defaults:
  authentication:
    permission: AllowAny

endpoints:
  - route: /books
    fields:
      title: { type: str, min_length: 1 }
      author: { type: str, min_length: 1 }
      price: { type: float, ge: 0 }
    meta:
      methods: [GET, POST, PUT, PATCH, DELETE]
      pagination:
        style: page_number
        page_size: 10

  - route: /authors
    fields:
      name: { type: str, min_length: 1 }
      bio: { type: str, optional: true }
    meta:
      methods: [GET, POST]
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml_content)
        config_path = f.name

    try:
        app = LightApi.from_config(config_path)
        print(f"Loaded config from {config_path}")
        print(f"Registered routes: {[r.path for r in app._routes]}")
        app.run(host="0.0.0.0", port=8000, debug=True)
    finally:
        os.unlink(config_path)


if __name__ == "__main__":
    main()
