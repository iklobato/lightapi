"""Tests for US6: Custom queryset override."""

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.pool import StaticPool
from starlette.requests import Request
from starlette.testclient import TestClient

from lightapi import LightApi, RestEndpoint
from lightapi.fields import Field as LField


class ArticleEndpoint(RestEndpoint):
    title: str = LField(min_length=1)
    published: bool = LField()

    def queryset(self, request: Request):
        cls = type(self)
        return select(cls._model_class).where(cls._model_class.published.is_(True))


@pytest.fixture(scope="module")
def client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    app_instance = LightApi(engine=engine)
    app_instance.register({"/articles": ArticleEndpoint})
    app = app_instance.build_app()
    c = TestClient(app)

    c.post("/articles", json={"title": "Draft", "published": False})
    c.post("/articles", json={"title": "Live Article", "published": True})
    c.post("/articles", json={"title": "Another Draft", "published": False})
    c.post("/articles", json={"title": "Live 2", "published": True})

    return c


class TestCustomQueryset:
    def test_list_only_returns_published(self, client):
        resp = client.get("/articles")
        assert resp.status_code == 200
        results = resp.json()["results"]
        assert all(r["published"] is True for r in results)
        assert len(results) == 2

    def test_unpublished_not_in_list(self, client):
        resp = client.get("/articles")
        titles = [r["title"] for r in resp.json()["results"]]
        assert "Draft" not in titles
        assert "Another Draft" not in titles

    def test_retrieve_bypasses_queryset(self, client):
        # retrieve() uses sa_select(cls._model_class) directly, not queryset
        draft_resp = client.post(
            "/articles", json={"title": "Direct Draft", "published": False}
        )
        draft_id = draft_resp.json()["id"]
        resp = client.get(f"/articles/{draft_id}")
        assert resp.status_code == 200
        assert resp.json()["published"] is False

    def test_static_queryset_class_attr(self):
        """Static queryset as class attribute filters results."""

        class StaticArticleEndpoint(RestEndpoint):
            title: str = LField(min_length=1)
            published: bool = LField()

        # Set queryset after class creation (static class attr)
        StaticArticleEndpoint.queryset = select(
            StaticArticleEndpoint._model_class
        ).where(StaticArticleEndpoint._model_class.published.is_(True))

        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        app = LightApi(engine=engine)
        app.register({"/static_articles": StaticArticleEndpoint})
        c = TestClient(app.build_app())
        c.post("/static_articles", json={"title": "Draft", "published": False})
        c.post("/static_articles", json={"title": "Live", "published": True})
        resp = c.get("/static_articles")
        assert resp.status_code == 200
        results = resp.json()["results"]
        assert len(results) == 1
        assert results[0]["title"] == "Live"

    def test_queryset_composes_with_filter(self, client):
        """Queryset filter + FieldFilter both applied when filtering configured."""
        from lightapi import Filtering, LightApi
        from lightapi.filters import FieldFilter

        class FilteredArticleEndpoint(RestEndpoint):
            title: str = LField(min_length=1)
            published: bool = LField()
            category: str = LField(min_length=1)

            def queryset(self, request: Request):
                cls = type(self)
                return select(cls._model_class).where(
                    cls._model_class.published.is_(True)
                )

            class Meta:
                filtering = Filtering(backends=[FieldFilter], fields=["category"])

        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        app = LightApi(engine=engine)
        app.register({"/filtered_articles": FilteredArticleEndpoint})
        c = TestClient(app.build_app())
        c.post(
            "/filtered_articles",
            json={"title": "Draft A", "published": False, "category": "x"},
        )
        c.post(
            "/filtered_articles",
            json={"title": "Live A", "published": True, "category": "x"},
        )
        c.post(
            "/filtered_articles",
            json={"title": "Live B", "published": True, "category": "y"},
        )
        resp = c.get("/filtered_articles?category=x")
        assert resp.status_code == 200
        results = resp.json()["results"]
        assert len(results) == 1
        assert results[0]["title"] == "Live A"
        assert results[0]["category"] == "x"
