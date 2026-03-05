"""Tests for US8: Database reflection (Meta.reflect)."""
import pytest
from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

from lightapi import LightApi, RestEndpoint
from lightapi.exceptions import ConfigurationError
from lightapi.fields import Field as LField


def _make_engine_with_table(table_name: str = "legacytable"):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    meta = MetaData()
    Table(
        table_name,
        meta,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("title", String, nullable=False),
        Column("author", String, nullable=True),
    )
    meta.create_all(engine)
    return engine


class TestFullReflection:
    def test_reflect_existing_table(self):
        engine = _make_engine_with_table("legacytable")

        class LegacyEndpoint(RestEndpoint):
            class Meta:
                reflect = True
                table = "legacytable"

        from lightapi._registry import set_engine
        set_engine(engine)

        app_instance = LightApi(engine=engine)
        app_instance.register({"/legacy": LegacyEndpoint})
        app = app_instance.build_app()
        client = TestClient(app)

        resp = client.get("/legacy")
        assert resp.status_code == 200
        assert "results" in resp.json()

    def test_reflect_missing_table_raises(self):
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

        class NoSuchEndpoint(RestEndpoint):
            class Meta:
                reflect = True
                table = "nonexistent_xyz_table"

        app_instance = LightApi(engine=engine)
        with pytest.raises(ConfigurationError, match="does not exist"):
            app_instance.register({"/nosuch": NoSuchEndpoint})
