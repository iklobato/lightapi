import base64
import datetime
import json
import os
import sqlite3
import tempfile
import time

import pytest
import yaml
from aiohttp import web
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Computed,
    Date,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    LargeBinary,
    MetaData,
    PrimaryKeyConstraint,
    String,
    Table,
    Text,
    UniqueConstraint,
    create_engine,
    text,
)
from sqlalchemy.pool import NullPool

from lightapi.lightapi import LightApi


@pytest.fixture
def temp_db():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as db_file:
        db_path = db_file.name
    yield db_path
    os.remove(db_path)


@pytest.fixture
def make_config():
    def _make(config_dict):
        config_fd, config_path = tempfile.mkstemp(suffix=".yaml")
        with os.fdopen(config_fd, "w") as f:
            yaml.dump(config_dict, f)
        return config_path

    return _make


@pytest.fixture
def temp_db_and_config():
    import os
    import tempfile

    import yaml
    from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine
    from sqlalchemy.pool import NullPool

    db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_path = db_file.name
    db_file.close()
    engine = create_engine(f"sqlite:///{db_path}", poolclass=NullPool)
    metadata = MetaData()
    Table(
        "users",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("name", String, nullable=False),
        Column("email", String, nullable=False, unique=True),
    )
    Table(
        "posts",
        metadata,
        Column("post_id", Integer, primary_key=True),
        Column("user_id", Integer),
        Column("content", String),
    )
    metadata.create_all(engine)
    config = {
        "database_url": f"sqlite:///{db_path}",
        "tables": [{"name": "users", "crud": ["get", "post", "put", "delete", "patch"]}],
    }
    config_fd, config_path = tempfile.mkstemp(suffix=".yaml")
    with os.fdopen(config_fd, "w") as f:
        yaml.dump(config, f)
    yield (f"sqlite:///{db_path}", config_path)
    os.remove(db_path)
    os.remove(config_path)


class TestFromConfigExtensive:
    def setup_users_and_posts(self, db_path):
        engine = create_engine(f"sqlite:///{db_path}", poolclass=NullPool)
        metadata = MetaData()
        Table(
            "users",
            metadata,
            Column("id", Integer, primary_key=True),
            Column("name", String, nullable=False),
            Column("email", String, nullable=False, unique=True),
        )
        Table(
            "posts",
            metadata,
            Column("post_id", Integer, primary_key=True),
            Column("user_id", Integer),
            Column("content", String),
        )
        metadata.create_all(engine)
        return engine

    @pytest.mark.asyncio
    async def test_multiple_tables_and_crud_combinations(self, temp_db, make_config):
        engine = self.setup_users_and_posts(temp_db)
        config = {
            "database_url": f"sqlite:///{temp_db}",
            "tables": [
                {"name": "users", "crud": ["get", "post", "put", "delete", "patch"]},
                {"name": "posts", "crud": ["get", "post"]},
            ],
        }
        config_path = make_config(config)
        os.environ["DATABASE_URL"] = f"sqlite:///{temp_db}"
        api = LightApi.from_config(config_path, engine=engine)
        app = api.app
        from aiohttp.test_utils import TestClient, TestServer

        async with TestClient(TestServer(app)) as client:
            # Users table: full CRUD
            resp = await client.post("/users/", json={"name": "Bob", "email": "bob@example.com"})
            assert resp.status == 201
            user = await resp.json()
            user_id = user["id"]
            # GET all users
            resp = await client.get("/users/")
            assert resp.status == 200
            users = await resp.json()
            assert any(u["name"] == "Bob" for u in users)
            # PATCH user
            resp = await client.patch(f"/users/{user_id}", json={"name": "Bobby"})
            assert resp.status == 200
            user = await resp.json()
            assert user["name"] == "Bobby"
            # DELETE user
            resp = await client.delete(f"/users/{user_id}")
            assert resp.status == 204
            # GET by id after delete
            resp = await client.get(f"/users/{user_id}")
            assert resp.status == 404
            # Posts table: only GET/POST
            resp = await client.post("/posts/", json={"user_id": 1, "content": "Hello"})
            assert resp.status == 201
            post = await resp.json()
            post_id = post["post_id"]
            resp = await client.get("/posts/")
            assert resp.status == 200
            posts = await resp.json()
            assert any(p["content"] == "Hello" for p in posts)
            # PUT/DELETE not allowed
            resp = await client.put(f"/posts/{post_id}", json={"content": "Updated"})
            assert resp.status == 405 or resp.status == 404
            resp = await client.delete(f"/posts/{post_id}")
            assert resp.status == 405 or resp.status == 404
        os.remove(config_path)

    def test_table_not_in_db_raises(self, temp_db, make_config):
        config = {
            "database_url": f"sqlite:///{temp_db}",
            "tables": [{"name": "not_a_table", "crud": ["get"]}],
        }
        config_path = make_config(config)
        with pytest.raises(ValueError, match="not_a_table"):
            LightApi.from_config(config_path)
        os.remove(config_path)

    def test_table_with_no_pk_raises(self, temp_db, make_config):
        engine = create_engine(f"sqlite:///{temp_db}", poolclass=NullPool)
        metadata = MetaData()
        Table("nopk", metadata, Column("foo", String))
        metadata.create_all(engine)
        config = {
            "database_url": f"sqlite:///{temp_db}",
            "tables": [{"name": "nopk", "crud": ["get"]}],
        }
        config_path = make_config(config)
        with pytest.raises(ValueError, match="no primary key"):
            LightApi.from_config(config_path)
        os.remove(config_path)

    def test_table_with_composite_pk(self, temp_db, make_config):
        engine = create_engine(f"sqlite:///{temp_db}", poolclass=NullPool)
        metadata = MetaData()
        Table(
            "composite",
            metadata,
            Column("a", Integer),
            Column("b", Integer),
            PrimaryKeyConstraint("a", "b"),
        )
        metadata.create_all(engine)
        config = {
            "database_url": f"sqlite:///{temp_db}",
            "tables": [{"name": "composite", "crud": ["get", "post"]}],
        }
        config_path = make_config(config)
        os.environ["DATABASE_URL"] = f"sqlite:///{temp_db}"
        api = LightApi.from_config(config_path)
        app = api.app
        from aiohttp.test_utils import TestClient, TestServer

        async def run():
            async with TestClient(TestServer(app)) as client:
                # POST
                resp = await client.post("/composite/", json={"a": 1, "b": 2})
                assert resp.status == 201
                row = await resp.json()
                assert row["a"] == 1 and row["b"] == 2
                # GET all
                resp = await client.get("/composite/")
                assert resp.status == 200
                rows = await resp.json()
                assert any(r["a"] == 1 and r["b"] == 2 for r in rows)

        import asyncio

        asyncio.get_event_loop().run_until_complete(run())
        os.remove(config_path)

    @pytest.mark.asyncio
    async def test_get_empty_table(self, temp_db, make_config):
        engine = create_engine(f"sqlite:///{temp_db}", poolclass=NullPool)
        metadata = MetaData()
        Table(
            "emptytable",
            metadata,
            Column("id", Integer, primary_key=True),
            Column("foo", String),
        )
        metadata.create_all(engine)
        config = {
            "database_url": f"sqlite:///{temp_db}",
            "tables": [{"name": "emptytable", "crud": ["get"]}],
        }
        config_path = make_config(config)
        os.environ["DATABASE_URL"] = f"sqlite:///{temp_db}"
        api = LightApi.from_config(config_path)
        app = api.app
        from aiohttp.test_utils import TestClient, TestServer

        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/emptytable/")
            assert resp.status == 200
            rows = await resp.json()
            assert rows == []
        os.remove(config_path)

    @pytest.mark.asyncio
    async def test_unique_constraint_violation(self, temp_db, make_config):
        engine = create_engine(f"sqlite:///{temp_db}", poolclass=NullPool)
        metadata = MetaData()
        Table(
            "uniq",
            metadata,
            Column("id", Integer, primary_key=True),
            Column("foo", String, unique=True),
        )
        metadata.create_all(engine)
        config = {
            "database_url": f"sqlite:///{temp_db}",
            "tables": [{"name": "uniq", "crud": ["get", "post"]}],
        }
        config_path = make_config(config)
        os.environ["DATABASE_URL"] = f"sqlite:///{temp_db}"
        api = LightApi.from_config(config_path)
        app = api.app
        from aiohttp.test_utils import TestClient, TestServer

        async with TestClient(TestServer(app)) as client:
            resp = await client.post("/uniq/", json={"id": 1, "foo": "bar"})
            assert resp.status == 201
            resp = await client.post("/uniq/", json={"id": 2, "foo": "bar"})
            assert resp.status in (400, 409)
        os.remove(config_path)

    @pytest.mark.asyncio
    async def test_patch_put_delete_on_nonexistent_row(self, temp_db, make_config):
        engine = create_engine(f"sqlite:///{temp_db}", poolclass=NullPool)
        metadata = MetaData()
        Table(
            "testpk",
            metadata,
            Column("id", Integer, primary_key=True),
            Column("foo", String),
        )
        metadata.create_all(engine)
        config = {
            "database_url": f"sqlite:///{temp_db}",
            "tables": [{"name": "testpk", "crud": ["get", "put", "patch", "delete"]}],
        }
        config_path = make_config(config)
        os.environ["DATABASE_URL"] = f"sqlite:///{temp_db}"
        api = LightApi.from_config(config_path)
        app = api.app
        from aiohttp.test_utils import TestClient, TestServer

        async with TestClient(TestServer(app)) as client:
            # PATCH non-existent
            resp = await client.patch("/testpk/999", json={"foo": "bar"})
            assert resp.status == 404
            # PUT non-existent
            resp = await client.put("/testpk/999", json={"foo": "bar"})
            assert resp.status == 404
            # DELETE non-existent
            resp = await client.delete("/testpk/999")
            assert resp.status == 404
        os.remove(config_path)

    @pytest.mark.asyncio
    async def test_complex_table_types_and_defaults(self, temp_db, make_config):
        engine = create_engine(f"sqlite:///{temp_db}", poolclass=NullPool)
        metadata = MetaData()
        Table(
            "complex",
            metadata,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("name", String, nullable=False),
            Column("age", Integer, server_default=text("30")),
            Column("score", Float),
            Column("is_active", Boolean, server_default=text("1")),
            Column("created_at", DateTime, server_default=text("CURRENT_TIMESTAMP")),
            Column("updated_at", DateTime),
            Column("notes", String),
            Column("extra", String, server_default=text("foo")),
            UniqueConstraint("name"),
        )
        metadata.create_all(engine)
        config = {
            "database_url": f"sqlite:///{temp_db}",
            "tables": [{"name": "complex", "crud": ["get", "post", "put", "patch", "delete"]}],
        }
        config_path = make_config(config)
        os.environ["DATABASE_URL"] = f"sqlite:///{temp_db}"
        api = LightApi.from_config(config_path)
        app = api.app
        from aiohttp.test_utils import TestClient, TestServer

        async with TestClient(TestServer(app)) as client:
            # POST with only required fields
            resp = await client.post("/complex/", json={"name": "Alpha"})
            assert resp.status == 201
            row = await resp.json()
            assert row["name"] == "Alpha"
            assert row["age"] == 30  # default
            assert row["is_active"] in (1, True)
            assert row["extra"] == "foo"
            assert row["notes"] is None
            assert row["score"] is None
            assert row["created_at"]  # should be set
            id1 = row["id"]

            # POST with all fields
            now = datetime.datetime.now().isoformat()
            resp = await client.post(
                "/complex/",
                json={
                    "name": "Beta",
                    "age": 40,
                    "score": 99.5,
                    "is_active": 0,
                    "created_at": "2022-01-01",
                    "updated_at": now,
                    "notes": "test",
                    "extra": "custom",
                },
            )
            if resp.status != 201:
                print("POST /complex/ error:", await resp.text())
            assert resp.status == 201
            row2 = await resp.json()
            assert row2["name"] == "Beta"
            assert row2["age"] == 40
            assert row2["score"] == 99.5
            assert row2["is_active"] in (0, False)
            assert row2["created_at"].startswith("2022-01-01")
            assert row2["updated_at"].startswith(now[:10])
            assert row2["notes"] == "test"
            assert row2["extra"] == "custom"
            id2 = row2["id"]

            # GET all
            resp = await client.get("/complex/")
            assert resp.status == 200
            rows = await resp.json()
            assert len(rows) == 2

            # GET by id
            resp = await client.get(f"/complex/{id1}")
            assert resp.status == 200
            row = await resp.json()
            assert row["name"] == "Alpha"

            # PUT update
            resp = await client.put(f"/complex/{id1}", json={"name": "Alpha2", "age": 50})
            assert resp.status == 200
            row = await resp.json()
            assert row["name"] == "Alpha2"
            assert row["age"] == 50

            # PATCH update
            resp = await client.patch(f"/complex/{id2}", json={"notes": "patched"})
            assert resp.status == 200
            row = await resp.json()
            assert row["notes"] == "patched"

            # DELETE
            resp = await client.delete(f"/complex/{id1}")
            assert resp.status == 204
            resp = await client.get(f"/complex/{id1}")
            assert resp.status == 404
        os.remove(config_path)

    @pytest.mark.asyncio
    async def test_foreign_key_relationships(self, temp_db, make_config):
        engine = create_engine(f"sqlite:///{temp_db}", poolclass=NullPool)
        metadata = MetaData()
        Table(
            "authors",
            metadata,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("name", String, nullable=False, unique=True),
        )
        Table(
            "books",
            metadata,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("author_id", Integer, ForeignKey("authors.id"), nullable=False),
            Column("title", String, nullable=False),
            ForeignKeyConstraint(["author_id"], ["authors.id"], ondelete="CASCADE"),
        )
        metadata.create_all(engine)
        config = {
            "database_url": f"sqlite:///{temp_db}",
            "tables": [
                {"name": "authors", "crud": ["get", "post", "delete"]},
                {"name": "books", "crud": ["get", "post", "delete"]},
            ],
        }
        config_path = make_config(config)
        os.environ["DATABASE_URL"] = f"sqlite:///{temp_db}"
        api = LightApi.from_config(config_path)
        app = api.app
        from aiohttp.test_utils import TestClient, TestServer

        async with TestClient(TestServer(app)) as client:
            # Create author
            resp = await client.post("/authors/", json={"name": "Tolkien"})
            assert resp.status == 201
            author = await resp.json()
            author_id = author["id"]
            # Create book for author
            resp = await client.post("/books/", json={"author_id": author_id, "title": "LOTR"})
            assert resp.status == 201
            book = await resp.json()
            # Try to create book with invalid author_id
            resp = await client.post("/books/", json={"author_id": 999, "title": "Ghost"})
            assert resp.status in (400, 409)
            # Delete author, book should be deleted (cascade)
            resp = await client.delete(f"/authors/{author_id}")
            assert resp.status == 204
            resp = await client.get(f'/books/{book["id"]}')
            assert resp.status == 404
        os.remove(config_path)

    @pytest.mark.asyncio
    async def test_self_referential_fk_tree(self, temp_db, make_config):
        engine = create_engine(f"sqlite:///{temp_db}", poolclass=NullPool)
        metadata = MetaData()
        Table(
            "categories",
            metadata,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("name", String, nullable=False),
            Column("parent_id", Integer, ForeignKey("categories.id", ondelete="CASCADE")),
        )
        metadata.create_all(engine)
        config = {
            "database_url": f"sqlite:///{temp_db}",
            "tables": [{"name": "categories", "crud": ["get", "post", "patch"]}],
        }
        config_path = make_config(config)
        os.environ["DATABASE_URL"] = f"sqlite:///{temp_db}"
        api = LightApi.from_config(config_path)
        app = api.app
        from aiohttp.test_utils import TestClient, TestServer

        async with TestClient(TestServer(app)) as client:
            # Create root
            resp = await client.post("/categories/", json={"name": "Root"})
            assert resp.status == 201
            root = await resp.json()
            # Create child
            resp = await client.post("/categories/", json={"name": "Child", "parent_id": root["id"]})
            assert resp.status == 201
            child = await resp.json()
            # Patch child to move under non-existent parent
            resp = await client.patch(f'/categories/{child["id"]}', json={"parent_id": 999})
            assert resp.status in (400, 409)
        os.remove(config_path)

    @pytest.mark.asyncio
    async def test_check_constraint(self, temp_db, make_config):
        engine = create_engine(f"sqlite:///{temp_db}", poolclass=NullPool)
        metadata = MetaData()
        Table(
            "scores",
            metadata,
            Column("id", Integer, primary_key=True),
            Column("value", Integer, CheckConstraint("value >= 0 AND value <= 100")),
        )
        metadata.create_all(engine)
        config = {
            "database_url": f"sqlite:///{temp_db}",
            "tables": [{"name": "scores", "crud": ["get", "post"]}],
        }
        config_path = make_config(config)
        os.environ["DATABASE_URL"] = f"sqlite:///{temp_db}"
        api = LightApi.from_config(config_path)
        app = api.app
        from aiohttp.test_utils import TestClient, TestServer

        async with TestClient(TestServer(app)) as client:
            # Valid
            resp = await client.post("/scores/", json={"id": 1, "value": 50})
            assert resp.status == 201
            # Invalid
            resp = await client.post("/scores/", json={"id": 2, "value": 200})
            assert resp.status in (400, 409)
        os.remove(config_path)

    @pytest.mark.asyncio
    async def test_default_expression_timestamp(self, temp_db, make_config):
        engine = create_engine(f"sqlite:///{temp_db}", poolclass=NullPool)
        metadata = MetaData()
        Table(
            "logs",
            metadata,
            Column("id", Integer, primary_key=True),
            Column("message", String),
            Column("created_at", DateTime, server_default=text("CURRENT_TIMESTAMP")),
        )
        metadata.create_all(engine)
        config = {
            "database_url": f"sqlite:///{temp_db}",
            "tables": [{"name": "logs", "crud": ["get", "post"]}],
        }
        config_path = make_config(config)
        os.environ["DATABASE_URL"] = f"sqlite:///{temp_db}"
        api = LightApi.from_config(config_path)
        app = api.app
        from aiohttp.test_utils import TestClient, TestServer

        async with TestClient(TestServer(app)) as client:
            resp = await client.post("/logs/", json={"id": 1, "message": "hello"})
            assert resp.status == 201
            log = await resp.json()
            assert log["created_at"]
        os.remove(config_path)

    @pytest.mark.asyncio
    async def test_multiple_unique_constraints(self, temp_db, make_config):
        engine = create_engine(f"sqlite:///{temp_db}", poolclass=NullPool)
        metadata = MetaData()
        Table(
            "people",
            metadata,
            Column("id", Integer, primary_key=True),
            Column("email", String),
            Column("username", String),
            UniqueConstraint("email"),
            UniqueConstraint("username"),
        )
        metadata.create_all(engine)
        config = {
            "database_url": f"sqlite:///{temp_db}",
            "tables": [{"name": "people", "crud": ["get", "post"]}],
        }
        config_path = make_config(config)
        os.environ["DATABASE_URL"] = f"sqlite:///{temp_db}"
        api = LightApi.from_config(config_path)
        app = api.app
        from aiohttp.test_utils import TestClient, TestServer

        async with TestClient(TestServer(app)) as client:
            resp = await client.post("/people/", json={"id": 1, "email": "a@b.com", "username": "bob"})
            assert resp.status == 201
            # Duplicate email
            resp = await client.post("/people/", json={"id": 2, "email": "a@b.com", "username": "alice"})
            assert resp.status in (400, 409)
            # Duplicate username
            resp = await client.post("/people/", json={"id": 3, "email": "c@d.com", "username": "bob"})
            assert resp.status in (400, 409)
        os.remove(config_path)

    @pytest.mark.asyncio
    async def test_nullable_and_not_null_columns(self, temp_db, make_config):
        engine = create_engine(f"sqlite:///{temp_db}", poolclass=NullPool)
        metadata = MetaData()
        Table(
            "things",
            metadata,
            Column("id", Integer, primary_key=True),
            Column("required", String, nullable=False),
            Column("optional", String),
            Column("with_default", String, server_default=text("foo")),
        )
        metadata.create_all(engine)
        config = {
            "database_url": f"sqlite:///{temp_db}",
            "tables": [{"name": "things", "crud": ["get", "post"]}],
        }
        config_path = make_config(config)
        os.environ["DATABASE_URL"] = f"sqlite:///{temp_db}"
        api = LightApi.from_config(config_path)
        app = api.app
        from aiohttp.test_utils import TestClient, TestServer

        async with TestClient(TestServer(app)) as client:
            # Only required
            resp = await client.post("/things/", json={"id": 1, "required": "yes"})
            assert resp.status == 201
            thing = await resp.json()
            assert thing["with_default"] == "foo"
            assert thing["optional"] is None
            # All fields
            resp = await client.post(
                "/things/",
                json={
                    "id": 2,
                    "required": "ok",
                    "optional": "maybe",
                    "with_default": "bar",
                },
            )
            assert resp.status == 201
            thing = await resp.json()
            assert thing["with_default"] == "bar"
            assert thing["optional"] == "maybe"
            # Missing required
            resp = await client.post("/things/", json={"id": 3})
            assert resp.status in (400, 409)
        os.remove(config_path)

    @pytest.mark.asyncio
    async def test_json_column(self, temp_db, make_config):
        engine = create_engine(f"sqlite:///{temp_db}", poolclass=NullPool)
        metadata = MetaData()
        Table(
            "docs",
            metadata,
            Column("id", Integer, primary_key=True),
            Column("data", String),
        )
        metadata.create_all(engine)
        config = {
            "database_url": f"sqlite:///{temp_db}",
            "tables": [{"name": "docs", "crud": ["get", "post"]}],
        }
        config_path = make_config(config)
        os.environ["DATABASE_URL"] = f"sqlite:///{temp_db}"
        api = LightApi.from_config(config_path)
        app = api.app
        from aiohttp.test_utils import TestClient, TestServer

        async with TestClient(TestServer(app)) as client:
            # Store JSON as string
            doc = {"foo": [1, 2, 3], "bar": {"baz": True}}
            resp = await client.post("/docs/", json={"id": 1, "data": json.dumps(doc)})
            assert resp.status == 201
            row = await resp.json()
            assert json.loads(row["data"]) == doc
        os.remove(config_path)

    @pytest.mark.asyncio
    async def test_multilevel_fk_cascade(self, temp_db, make_config):
        engine = create_engine(f"sqlite:///{temp_db}", poolclass=NullPool)
        metadata = MetaData()
        Table(
            "grandparent",
            metadata,
            Column("id", Integer, primary_key=True),
            Column("name", String),
        )
        Table(
            "parent",
            metadata,
            Column("id", Integer, primary_key=True),
            Column(
                "grandparent_id",
                Integer,
                ForeignKey("grandparent.id", ondelete="CASCADE"),
            ),
            Column("name", String),
            ForeignKeyConstraint(["grandparent_id"], ["grandparent.id"], ondelete="CASCADE"),
        )
        Table(
            "child",
            metadata,
            Column("id", Integer, primary_key=True),
            Column("parent_id", Integer, ForeignKey("parent.id", ondelete="CASCADE")),
            Column("name", String),
            ForeignKeyConstraint(["parent_id"], ["parent.id"], ondelete="CASCADE"),
        )
        metadata.create_all(engine)
        config = {
            "database_url": f"sqlite:///{temp_db}",
            "tables": [
                {"name": "grandparent", "crud": ["get", "post", "delete"]},
                {"name": "parent", "crud": ["get", "post", "delete"]},
                {"name": "child", "crud": ["get", "post", "delete"]},
            ],
        }
        config_path = make_config(config)
        os.environ["DATABASE_URL"] = f"sqlite:///{temp_db}"
        api = LightApi.from_config(config_path)
        app = api.app
        from aiohttp.test_utils import TestClient, TestServer

        async with TestClient(TestServer(app)) as client:
            resp = await client.post("/grandparent/", json={"id": 1, "name": "GP"})
            assert resp.status == 201
            resp = await client.post("/parent/", json={"id": 1, "grandparent_id": 1, "name": "P"})
            assert resp.status == 201
            resp = await client.post("/child/", json={"id": 1, "parent_id": 1, "name": "C"})
            assert resp.status == 201
            # Delete grandparent, all should be gone
            resp = await client.delete("/grandparent/1")
            assert resp.status == 204
            resp = await client.get("/parent/1")
            assert resp.status == 404
            resp = await client.get("/child/1")
            assert resp.status == 404
        os.remove(config_path)

    @pytest.mark.asyncio
    async def test_partial_unique_constraint(self, temp_db, make_config):
        engine = create_engine(f"sqlite:///{temp_db}", poolclass=NullPool)
        metadata = MetaData()
        Table(
            "emails",
            metadata,
            Column("id", Integer, primary_key=True),
            Column("email", String, unique=True),
        )
        metadata.create_all(engine)
        config = {
            "database_url": f"sqlite:///{temp_db}",
            "tables": [{"name": "emails", "crud": ["get", "post"]}],
        }
        config_path = make_config(config)
        os.environ["DATABASE_URL"] = f"sqlite:///{temp_db}"
        api = LightApi.from_config(config_path)
        app = api.app
        from aiohttp.test_utils import TestClient, TestServer

        async with TestClient(TestServer(app)) as client:
            resp = await client.post("/emails/", json={"id": 1, "email": "a@b.com"})
            assert resp.status == 201
            resp = await client.post("/emails/", json={"id": 2, "email": None})
            assert resp.status == 201
            resp = await client.post("/emails/", json={"id": 3, "email": None})
            assert resp.status == 201
            resp = await client.post("/emails/", json={"id": 4, "email": "a@b.com"})
            assert resp.status in (400, 409)
        os.remove(config_path)

    @pytest.mark.asyncio
    async def test_generated_virtual_column(self, temp_db, make_config):
        engine = create_engine(f"sqlite:///{temp_db}", poolclass=NullPool)
        metadata = MetaData()
        try:
            Table(
                "gen",
                metadata,
                Column("id", Integer, primary_key=True),
                Column("a", Integer),
                Column("b", Integer),
                Column("sum", Integer, Computed("a + b")),
            )
            metadata.create_all(engine)
            supports_generated = True
        except Exception:
            supports_generated = False
        config = {
            "database_url": f"sqlite:///{temp_db}",
            "tables": [{"name": "gen", "crud": ["get", "post"]}],
        }
        config_path = make_config(config)
        os.environ["DATABASE_URL"] = f"sqlite:///{temp_db}"
        api = LightApi.from_config(config_path)
        app = api.app
        from aiohttp.test_utils import TestClient, TestServer

        async with TestClient(TestServer(app)) as client:
            resp = await client.post("/gen/", json={"id": 1, "a": 2, "b": 3})
            assert resp.status == 201
            row = await resp.json()
            assert row["sum"] == 5
        os.remove(config_path)

    @pytest.mark.asyncio
    async def test_trigger_audit_log(self, temp_db, make_config):
        engine = create_engine(f"sqlite:///{temp_db}", poolclass=NullPool)
        metadata = MetaData()
        Table(
            "main",
            metadata,
            Column("id", Integer, primary_key=True),
            Column("val", String),
        )
        Table(
            "audit",
            metadata,
            Column("id", Integer, primary_key=True),
            Column("main_id", Integer, ForeignKey("main.id")),
            Column("action", String),
        )
        metadata.create_all(engine)
        # Create the trigger for audit log
        with engine.connect() as conn:
            conn.execute(
                text(
                    """
                CREATE TRIGGER IF NOT EXISTS audit_insert AFTER INSERT ON main
                BEGIN
                    INSERT INTO audit (main_id, action) VALUES (NEW.id, 'insert');
                END;
            """
                )
            )
        config = {
            "database_url": f"sqlite:///{temp_db}",
            "tables": [
                {"name": "main", "crud": ["get", "post"]},
                {"name": "audit", "crud": ["get"]},
            ],
        }
        config_path = make_config(config)
        os.environ["DATABASE_URL"] = f"sqlite:///{temp_db}"
        api = LightApi.from_config(config_path)
        app = api.app
        from aiohttp.test_utils import TestClient, TestServer

        async with TestClient(TestServer(app)) as client:
            resp = await client.post("/main/", json={"id": 1, "val": "foo"})
            assert resp.status == 201
            resp = await client.get("/audit/")
            assert resp.status == 200
            logs = await resp.json()
            assert any(l["main_id"] == 1 and l["action"] == "insert" for l in logs)
        os.remove(config_path)

    @pytest.mark.asyncio
    async def test_many_to_many_relationship(self, temp_db, make_config):
        engine = create_engine(f"sqlite:///{temp_db}", poolclass=NullPool)
        metadata = MetaData()
        Table(
            "students",
            metadata,
            Column("id", Integer, primary_key=True),
            Column("name", String),
        )
        Table(
            "courses",
            metadata,
            Column("id", Integer, primary_key=True),
            Column("title", String),
        )
        Table(
            "enrollments",
            metadata,
            Column("student_id", Integer),
            Column("course_id", Integer),
            PrimaryKeyConstraint("student_id", "course_id"),
            ForeignKeyConstraint(["student_id"], ["students.id"]),
            ForeignKeyConstraint(["course_id"], ["courses.id"]),
        )
        metadata.create_all(engine)
        config = {
            "database_url": f"sqlite:///{temp_db}",
            "tables": [
                {"name": "students", "crud": ["get", "post"]},
                {"name": "courses", "crud": ["get", "post"]},
                {"name": "enrollments", "crud": ["get", "post", "delete"]},
            ],
        }
        config_path = make_config(config)
        os.environ["DATABASE_URL"] = f"sqlite:///{temp_db}"
        api = LightApi.from_config(config_path)
        app = api.app
        from aiohttp.test_utils import TestClient, TestServer

        async with TestClient(TestServer(app)) as client:
            resp = await client.post("/students/", json={"id": 1, "name": "Alice"})
            assert resp.status == 201
            resp = await client.post("/courses/", json={"id": 1, "title": "Math"})
            assert resp.status == 201
            resp = await client.post("/enrollments/", json={"student_id": 1, "course_id": 1})
            assert resp.status == 201
            # Try duplicate enrollment
            resp = await client.post("/enrollments/", json={"student_id": 1, "course_id": 1})
            assert resp.status in (400, 409)
            # Delete enrollment
            resp = await client.delete("/enrollments/1")  # Should 404 (no single PK), but test for robustness
        os.remove(config_path)

    @pytest.mark.asyncio
    async def test_composite_foreign_key(self, temp_db, make_config):
        engine = create_engine(f"sqlite:///{temp_db}", poolclass=NullPool)
        metadata = MetaData()
        Table(
            "refd",
            metadata,
            Column("a", Integer),
            Column("b", Integer),
            PrimaryKeyConstraint("a", "b"),
        )
        Table(
            "ref",
            metadata,
            Column("id", Integer, primary_key=True),
            Column("a", Integer),
            Column("b", Integer),
            ForeignKeyConstraint(["a", "b"], ["refd.a", "refd.b"]),
        )
        metadata.create_all(engine)
        config = {
            "database_url": f"sqlite:///{temp_db}",
            "tables": [
                {"name": "refd", "crud": ["get", "post"]},
                {"name": "ref", "crud": ["get", "post"]},
            ],
        }
        config_path = make_config(config)
        os.environ["DATABASE_URL"] = f"sqlite:///{temp_db}"
        api = LightApi.from_config(config_path)
        app = api.app
        from aiohttp.test_utils import TestClient, TestServer

        async with TestClient(TestServer(app)) as client:
            resp = await client.post("/refd/", json={"a": 1, "b": 2})
            assert resp.status == 201
            resp = await client.post("/ref/", json={"id": 1, "a": 1, "b": 2})
            assert resp.status == 201
            # Invalid composite FK
            resp = await client.post("/ref/", json={"id": 2, "a": 9, "b": 9})
            assert resp.status in (400, 409)
        os.remove(config_path)

    @pytest.mark.asyncio
    async def test_enum_like_check_constraint(self, temp_db, make_config):
        engine = create_engine(f"sqlite:///{temp_db}", poolclass=NullPool)
        metadata = MetaData()
        Table(
            "pets",
            metadata,
            Column("id", Integer, primary_key=True),
            Column("type", String, CheckConstraint("type IN ('dog','cat','bird')")),
        )
        metadata.create_all(engine)
        config = {
            "database_url": f"sqlite:///{temp_db}",
            "tables": [{"name": "pets", "crud": ["get", "post"]}],
        }
        config_path = make_config(config)
        os.environ["DATABASE_URL"] = f"sqlite:///{temp_db}"
        api = LightApi.from_config(config_path)
        app = api.app
        from aiohttp.test_utils import TestClient, TestServer

        async with TestClient(TestServer(app)) as client:
            resp = await client.post("/pets/", json={"id": 1, "type": "dog"})
            assert resp.status == 201
            resp = await client.post("/pets/", json={"id": 2, "type": "cat"})
            assert resp.status == 201
            resp = await client.post("/pets/", json={"id": 3, "type": "fish"})
            assert resp.status in (400, 409)
        os.remove(config_path)

    @pytest.mark.asyncio
    async def test_multiple_datetime_columns(self, temp_db, make_config):
        engine = create_engine(f"sqlite:///{temp_db}", poolclass=NullPool)
        metadata = MetaData()
        Table(
            "events",
            metadata,
            Column("id", Integer, primary_key=True),
            Column("start", DateTime, server_default=text("CURRENT_TIMESTAMP")),
            Column("end", DateTime),
            Column("created", Date, server_default=text("'2020-01-01'")),
        )
        metadata.create_all(engine)
        config = {
            "database_url": f"sqlite:///{temp_db}",
            "tables": [{"name": "events", "crud": ["get", "post", "patch"]}],
        }
        config_path = make_config(config)
        os.environ["DATABASE_URL"] = f"sqlite:///{temp_db}"
        api = LightApi.from_config(config_path)
        app = api.app
        from aiohttp.test_utils import TestClient, TestServer

        async with TestClient(TestServer(app)) as client:
            resp = await client.post("/events/", json={"id": 1, "end": "2025-01-01T12:00:00"})
            if resp.status != 201:
                print("POST /events/ error:", await resp.text())
            assert resp.status == 201
            row = await resp.json()
            assert row["start"]
            if not row["created"]:
                print("DEBUG: row returned:", row)
            assert row["created"]
            # Patch end
            resp = await client.patch("/events/1", json={"end": "2025-01-02T12:00:00"})
            if resp.status != 200:
                print("PATCH /events/1 error:", await resp.text())
            assert resp.status == 200
            row = await resp.json()
            assert row["end"] == "2025-01-02T12:00:00"
        os.remove(config_path)

    @pytest.mark.asyncio
    async def test_multiple_fks_to_same_table(self, temp_db, make_config):
        engine = create_engine(f"sqlite:///{temp_db}", poolclass=NullPool)
        metadata = MetaData()
        Table(
            "users",
            metadata,
            Column("id", Integer, primary_key=True),
            Column("name", String),
        )
        Table(
            "tasks",
            metadata,
            Column("id", Integer, primary_key=True),
            Column("user_id", Integer),
            Column("manager_id", Integer),
            ForeignKeyConstraint(["user_id"], ["users.id"]),
            ForeignKeyConstraint(["manager_id"], ["users.id"]),
        )
        metadata.create_all(engine)
        config = {
            "database_url": f"sqlite:///{temp_db}",
            "tables": [
                {"name": "users", "crud": ["get", "post"]},
                {"name": "tasks", "crud": ["get", "post"]},
            ],
        }
        config_path = make_config(config)
        os.environ["DATABASE_URL"] = f"sqlite:///{temp_db}"
        api = LightApi.from_config(config_path)
        app = api.app
        from aiohttp.test_utils import TestClient, TestServer

        async with TestClient(TestServer(app)) as client:
            resp = await client.post("/users/", json={"id": 1, "name": "A"})
            assert resp.status == 201
            resp = await client.post("/users/", json={"id": 2, "name": "B"})
            assert resp.status == 201
            resp = await client.post("/tasks/", json={"id": 1, "user_id": 1, "manager_id": 2})
            assert resp.status == 201
            row = await resp.json()
            assert row["user_id"] == 1 and row["manager_id"] == 2
        os.remove(config_path)


@pytest.fixture
def aiohttp_client():
    from aiohttp.test_utils import TestClient, TestServer, loop_context

    def factory(app):
        with loop_context() as loop:
            server = TestServer(app)
            client = TestClient(server)
            loop.run_until_complete(client.start_server())
            yield client
            loop.run_until_complete(client.close())

    return factory


class TestFromConfig:
    @pytest.mark.asyncio
    async def test_reflect_and_crud(self, temp_db_and_config):
        db_url, config_path = temp_db_and_config
        os.environ["DATABASE_URL"] = db_url
        api = LightApi.from_config(config_path)
        app = api.app
        from aiohttp.test_utils import TestClient, TestServer

        async with TestClient(TestServer(app)) as client:
            # POST (create)
            resp = await client.post("/users/", json={"name": "Alice", "email": "alice@example.com"})
            assert resp.status == 201
            data = await resp.json()
            assert data["name"] == "Alice"
            assert data["email"] == "alice@example.com"

            # GET all
            resp = await client.get("/users/")
            assert resp.status == 200
            users = await resp.json()
            assert any(u["name"] == "Alice" for u in users)

            # GET by id
            user_id = data["id"]
            resp = await client.get(f"/users/{user_id}")
            assert resp.status == 200
            user = await resp.json()
            assert user["name"] == "Alice"

            # PUT (update)
            resp = await client.put(
                f"/users/{user_id}",
                json={"name": "Alice2", "email": "alice2@example.com"},
            )
            assert resp.status == 200
            user = await resp.json()
            assert user["name"] == "Alice2"

            # PATCH (partial update)
            resp = await client.patch(f"/users/{user_id}", json={"name": "Alice3"})
            assert resp.status == 200
            user = await resp.json()
            assert user["name"] == "Alice3"

            # DELETE
            resp = await client.delete(f"/users/{user_id}")
            assert resp.status == 204

            # GET by id after delete
            resp = await client.get(f"/users/{user_id}")
            assert resp.status == 404
