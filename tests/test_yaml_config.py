"""Tests for YAML-based LightApi configuration (both legacy and declarative formats)."""
import os
import tempfile
import textwrap

import pytest
import yaml
from pydantic import ValidationError

from lightapi.exceptions import ConfigurationError
from lightapi.lightapi import LightApi
from lightapi.yaml_loader import LightAPIConfig, _resolve_name, load_config


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _write_yaml(content: str | dict) -> str:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        if isinstance(content, str):
            f.write(textwrap.dedent(content))
        else:
            yaml.dump(content, f)
        return f.name


def _from_str(content: str) -> LightApi:
    path = _write_yaml(content)
    try:
        return LightApi.from_config(path)
    finally:
        os.unlink(path)


# ─────────────────────────────────────────────────────────────────────────────
# Schema validation
# ─────────────────────────────────────────────────────────────────────────────

class TestSchemaValidation:
    def test_invalid_yaml_syntax_raises(self):
        path = _write_yaml("invalid: yaml: content: [")
        try:
            with pytest.raises(Exception):
                LightApi.from_config(path)
        finally:
            os.unlink(path)

    def test_endpoint_without_route_raises(self):
        # Direct model_validate raises pydantic ValidationError;
        # going through from_config wraps it as ConfigurationError.
        raw = {"database_url": "sqlite:///:memory:", "endpoints": [{"fields": {}}]}
        with pytest.raises(ValidationError):
            LightAPIConfig.model_validate(raw)

    def test_unknown_field_type_raises(self):
        raw = {
            "database_url": "sqlite:///:memory:",
            "endpoints": [
                {"route": "/x", "fields": {"foo": {"type": "nonsense"}}}
            ],
        }
        with pytest.raises(ValidationError):
            LightAPIConfig.model_validate(raw)

    def test_missing_env_var_raises(self):
        path = _write_yaml({"database_url": "${LIGHTAPI_DB_MISSING_XTEST}"})
        try:
            with pytest.raises(ConfigurationError, match="LIGHTAPI_DB_MISSING_XTEST"):
                LightApi.from_config(path)
        finally:
            os.unlink(path)


# ─────────────────────────────────────────────────────────────────────────────
# Legacy format
# ─────────────────────────────────────────────────────────────────────────────

class TestLegacyFormat:
    def test_flat_database_url(self):
        # Quotes are required: trailing colon in ':memory:' confuses YAML parsers
        app = _from_str('database_url: "sqlite:///:memory:"\n')
        assert app is not None

    def test_env_var_substitution(self, monkeypatch):
        monkeypatch.setenv("LIGHTAPI_TEST_DB_URL", "sqlite:///:memory:")
        app = _from_str("database_url: ${LIGHTAPI_TEST_DB_URL}\n")
        assert app is not None

    def test_cors_origins_passed_through(self):
        app = _from_str(
            'database_url: "sqlite:///:memory:"\ncors_origins:\n  - https://example.com\n'
        )
        assert app._cors_origins == ["https://example.com"]

    def test_legacy_class_import(self, tmp_path, monkeypatch):
        """endpoints[].class is resolved via importlib and registered."""
        module_src = textwrap.dedent(
            """\
            from lightapi.rest import RestEndpoint
            from lightapi.methods import HttpMethod

            class ToyEndpoint(RestEndpoint, HttpMethod.GET):
                name: str = "toy"
            """
        )
        pkg_dir = tmp_path / "toyapp"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text("")
        (pkg_dir / "endpoints.py").write_text(module_src)
        monkeypatch.syspath_prepend(str(tmp_path))

        cfg = yaml.dump(
            {
                "database_url": "sqlite:///:memory:",
                "endpoints": [
                    {"path": "/toys", "class": "toyapp.endpoints.ToyEndpoint"}
                ],
            }
        )
        app = _from_str(cfg)
        assert "/toys" in app._endpoint_map


# ─────────────────────────────────────────────────────────────────────────────
# New declarative format
# ─────────────────────────────────────────────────────────────────────────────

class TestDeclarativeFormat:
    def _route_cls(self, app: LightApi, route_path: str) -> type:
        """Retrieve the endpoint class registered under a given route path."""
        if route_path not in app._endpoint_map:
            raise KeyError(f"No route registered for '{route_path}'")
        return app._endpoint_map[route_path]

    def test_nested_database_block(self):
        app = _from_str(
            """\
            database:
              url: "sqlite:///:memory:"
            """
        )
        assert app is not None

    def test_dynamic_fields_create_endpoint_class(self):
        content = """\
            database_url: "sqlite:///:memory:"
            endpoints:
              - route: /articles
                fields:
                  title:   { type: str, max_length: 200 }
                  views:   { type: int }
                  active:  { type: bool, optional: true }
                meta:
                  methods: [GET, POST]
            """
        app = _from_str(content)
        assert "/articles" in app._endpoint_map

    def test_dynamic_fields_are_on_class_annotations(self):
        content = """\
            database_url: "sqlite:///:memory:"
            endpoints:
              - route: /items2
                fields:
                  title:   { type: str }
                  count:   { type: int }
                meta:
                  methods: [GET]
            """
        app = _from_str(content)
        cls = self._route_cls(app, "/items2")
        assert "title" in cls.__annotations__
        assert "count" in cls.__annotations__

    def test_defaults_applied_to_endpoint(self):
        """Defaults authentication should be present on the generated Meta."""
        content = """\
            database_url: "sqlite:///:memory:"
            defaults:
              authentication:
                backend: JWTAuthentication
                permission: IsAuthenticated
            endpoints:
              - route: /secure
                fields:
                  data: { type: str }
                meta:
                  methods: [GET]
            """
        app = _from_str(content)
        cls = self._route_cls(app, "/secure")
        meta = cls.Meta
        assert hasattr(meta, "authentication")
        from lightapi.auth import IsAuthenticated
        assert meta.authentication.permission is IsAuthenticated

    def test_endpoint_auth_overrides_defaults(self):
        content = """\
            database_url: "sqlite:///:memory:"
            defaults:
              authentication:
                backend: JWTAuthentication
                permission: IsAuthenticated
            endpoints:
              - route: /public
                fields:
                  msg: { type: str }
                meta:
                  methods: [GET]
                  authentication:
                    permission: AllowAny
            """
        app = _from_str(content)
        cls = self._route_cls(app, "/public")
        from lightapi.auth import AllowAny
        assert cls.Meta.authentication.permission is AllowAny

    def test_per_method_auth_in_meta(self):
        content = """\
            database_url: "sqlite:///:memory:"
            endpoints:
              - route: /itemsauth
                fields:
                  name: { type: str }
                meta:
                  methods:
                    GET:
                      authentication: { permission: AllowAny }
                    DELETE:
                      authentication: { permission: IsAdminUser }
                  authentication:
                    backend: JWTAuthentication
            """
        app = _from_str(content)
        cls = self._route_cls(app, "/itemsauth")
        from lightapi.auth import AllowAny, IsAdminUser
        perm = cls.Meta.authentication.permission
        assert isinstance(perm, dict)
        assert perm.get("GET") is AllowAny
        assert perm.get("DELETE") is IsAdminUser

    def test_filtering_config_auto_selects_backends(self):
        content = """\
            database_url: "sqlite:///:memory:"
            endpoints:
              - route: /posts
                fields:
                  title: { type: str }
                  published: { type: bool }
                meta:
                  methods: [GET]
                  filtering:
                    fields: [published]
                    ordering: [title]
            """
        app = _from_str(content)
        cls = self._route_cls(app, "/posts")
        from lightapi.filters import FieldFilter, OrderingFilter
        meta = cls.Meta
        assert hasattr(meta, "filtering")
        backends = meta.filtering.backends
        assert FieldFilter in backends
        assert OrderingFilter in backends

    def test_pagination_config_from_defaults(self):
        content = """\
            database_url: "sqlite:///:memory:"
            defaults:
              pagination:
                style: page_number
                page_size: 50
            endpoints:
              - route: /things
                fields:
                  label: { type: str }
                meta:
                  methods: [GET]
            """
        app = _from_str(content)
        cls = self._route_cls(app, "/things")
        meta = cls.Meta
        assert hasattr(meta, "pagination")
        assert meta.pagination.page_size == 50

    def test_reflect_endpoint_no_fields_needed(self):
        """reflect:true endpoint gets Meta.reflect=True on the generated class.

        We test the class builder directly because register() would attempt
        actual DB table inspection (requires a running engine).
        """
        from lightapi.yaml_loader import (
            DefaultsConfig,
            EndpointConfig,
            MetaConfig,
            _build_endpoint_class,
        )
        entry = EndpointConfig(route="/legacy", reflect=True, meta=MetaConfig())
        cls = _build_endpoint_class(entry, DefaultsConfig())
        assert cls.Meta.reflect is True

    def test_middleware_resolved_by_name(self):
        content = """\
            database_url: "sqlite:///:memory:"
            middleware: [CORSMiddleware]
            """
        app = _from_str(content)
        assert app is not None


# ─────────────────────────────────────────────────────────────────────────────
# _resolve_name utility
# ─────────────────────────────────────────────────────────────────────────────

class TestResolveName:
    def test_builtin_names_resolve(self):
        from lightapi.auth import IsAuthenticated
        assert _resolve_name("IsAuthenticated") is IsAuthenticated

    def test_dotted_path_resolves(self):
        cls = _resolve_name("lightapi.auth.AllowAny")
        from lightapi.auth import AllowAny
        assert cls is AllowAny

    def test_unknown_name_raises(self):
        with pytest.raises(ConfigurationError, match="Unknown class name"):
            _resolve_name("CompletlyUnknownClass")

    def test_bad_dotted_path_raises(self):
        with pytest.raises(ConfigurationError):
            _resolve_name("non.existent.module.Foo")
