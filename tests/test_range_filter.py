"""Tests for RangeFilter: inclusive ?<field>_min / ?<field>_max bounds."""

from datetime import date, datetime

import pytest
from sqlalchemy import Date, String, create_engine
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

from lightapi import Filtering, LightApi, RestEndpoint
from lightapi.exceptions import ConfigurationError
from lightapi.fields import Field as LField
from lightapi.filters import (
    FieldFilter,
    OrderingFilter,
    RangeFilter,
    _coerce_range_value,
)


class InventoryEndpoint(RestEndpoint):
    name: str = LField(min_length=1)
    category: str = LField(min_length=1)
    price: float = LField(ge=0)
    quantity: int = LField(ge=0)
    released_at: datetime = LField()

    class Meta:
        filtering = Filtering(
            backends=[FieldFilter, RangeFilter, OrderingFilter],
            fields=["category"],
            ordering=["price"],
            ranges=["price", "quantity", "released_at", "id"],
        )


class UnboundedEndpoint(RestEndpoint):
    """RangeFilter enabled as a backend but with no ranges whitelist."""

    price: float = LField(ge=0)

    class Meta:
        filtering = Filtering(backends=[RangeFilter])


ITEMS = [
    {"name": "Apple", "category": "fruit", "price": 1.0, "quantity": 10},
    {"name": "Banana", "category": "fruit", "price": 0.5, "quantity": 40},
    {"name": "Carrot", "category": "vegetable", "price": 0.8, "quantity": 25},
    {"name": "Dates", "category": "fruit", "price": 2.5, "quantity": 5},
    {"name": "Eggplant", "category": "vegetable", "price": 1.2, "quantity": 60},
]


@pytest.fixture(scope="module")
def client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    app_instance = LightApi(engine=engine)
    app_instance.register(
        {"/inventory": InventoryEndpoint, "/unbounded": UnboundedEndpoint}
    )
    c = TestClient(app_instance.build_app())

    for offset, item in enumerate(ITEMS):
        c.post(
            "/inventory",
            json={**item, "released_at": f"2026-0{offset + 1}-10T12:00:00"},
        )
    c.post("/unbounded", json={"price": 1.0})
    c.post("/unbounded", json={"price": 99.0})

    return c


def _names(response):
    return {row["name"] for row in response.json()["results"]}


class TestNumericRange:
    def test_min_only_returns_values_at_or_above_bound(self, client):
        resp = client.get("/inventory?price_min=1.0")

        assert resp.status_code == 200
        assert _names(resp) == {"Apple", "Dates", "Eggplant"}

    def test_max_only_returns_values_at_or_below_bound(self, client):
        resp = client.get("/inventory?price_max=1.0")

        assert resp.status_code == 200
        assert _names(resp) == {"Apple", "Banana", "Carrot"}

    def test_min_and_max_returns_values_inside_bounds(self, client):
        resp = client.get("/inventory?price_min=0.8&price_max=1.2")

        assert resp.status_code == 200
        assert _names(resp) == {"Apple", "Carrot", "Eggplant"}

    def test_integer_column_bounds_applied(self, client):
        resp = client.get("/inventory?quantity_min=10&quantity_max=40")

        assert resp.status_code == 200
        assert _names(resp) == {"Apple", "Banana", "Carrot"}

    def test_inverted_bounds_return_empty_results(self, client):
        resp = client.get("/inventory?price_min=2.0&price_max=1.0")

        assert resp.status_code == 200
        assert resp.json()["results"] == []


class TestDatetimeRange:
    def test_datetime_bounds_applied(self, client):
        resp = client.get(
            "/inventory?released_at_min=2026-02-01T00:00:00"
            "&released_at_max=2026-04-01T00:00:00"
        )

        assert resp.status_code == 200
        assert _names(resp) == {"Banana", "Carrot"}

    def test_datetime_min_is_inclusive(self, client):
        resp = client.get("/inventory?released_at_min=2026-05-10T12:00:00")

        assert resp.status_code == 200
        assert _names(resp) == {"Eggplant"}


class TestAutoInjectedColumns:
    def test_range_on_auto_injected_id_column(self, client):
        resp = client.get("/inventory?id_min=1&id_max=2")

        assert resp.status_code == 200
        assert _names(resp) == {"Apple", "Banana"}


class TestIgnoredParameters:
    def test_field_outside_ranges_whitelist_is_ignored(self, client):
        resp = client.get("/inventory?name_min=B")

        assert resp.status_code == 200
        assert len(resp.json()["results"]) == len(ITEMS)

    def test_unparseable_bound_is_ignored(self, client):
        resp = client.get("/inventory?price_min=cheap")

        assert resp.status_code == 200
        assert len(resp.json()["results"]) == len(ITEMS)

    def test_empty_bound_is_ignored(self, client):
        resp = client.get("/inventory?price_min=")

        assert resp.status_code == 200
        assert len(resp.json()["results"]) == len(ITEMS)

    def test_empty_ranges_whitelist_disables_backend(self, client):
        resp = client.get("/unbounded?price_min=50")

        assert resp.status_code == 200
        assert len(resp.json()["results"]) == 2


class TestComposition:
    def test_range_composes_with_field_filter(self, client):
        resp = client.get("/inventory?category=fruit&price_max=1.0")

        assert resp.status_code == 200
        assert _names(resp) == {"Apple", "Banana"}

    def test_range_composes_with_ordering(self, client):
        resp = client.get("/inventory?price_min=0.8&ordering=-price")

        prices = [row["price"] for row in resp.json()["results"]]
        assert prices == sorted(prices, reverse=True)


class TestConfigurationValidation:
    def test_unknown_field_in_ranges_raises(self):
        with pytest.raises(ConfigurationError, match="not a field on this endpoint"):

            class UnknownRangeEndpoint(RestEndpoint):
                price: float = LField(ge=0)

                class Meta:
                    filtering = Filtering(backends=[RangeFilter], ranges=["weight"])

    def test_unordered_column_type_in_ranges_raises(self):
        with pytest.raises(ConfigurationError, match="has no ordering"):

            class StringRangeEndpoint(RestEndpoint):
                name: str = LField(min_length=1)

                class Meta:
                    filtering = Filtering(backends=[RangeFilter], ranges=["name"])

    def test_valid_ranges_accepted(self):
        class ValidRangeEndpoint(RestEndpoint):
            price: float = LField(ge=0)

            class Meta:
                filtering = Filtering(backends=[RangeFilter], ranges=["price"])

        assert ValidRangeEndpoint._meta["filtering"].ranges == ["price"]


class TestCoerceRangeValue:
    class _Column:
        def __init__(self, col_type):
            self.type = col_type

    def test_date_column_parses_iso_date(self):
        col = self._Column(Date())

        assert _coerce_range_value(col, "2026-01-15") == date(2026, 1, 15)

    def test_unordered_column_returns_none(self):
        col = self._Column(String())

        assert _coerce_range_value(col, "abc") is None
