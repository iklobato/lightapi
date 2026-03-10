"""Tests for YAML-based LightApi configuration (declarative format)."""

import os
import tempfile
import textwrap

import pytest
import yaml
from pydantic import ValidationError

from lightapi.exceptions import ConfigurationError
from lightapi.lightapi import LightApi
from lightapi.yaml_loader import LightAPIConfig, _resolve_name

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


def _dummy_login_validator(username: str, password: str):
    return None


def _from_str(content: str, login_validator=None) -> LightApi:
    path = _write_yaml(content)
    try:
        # Pass login_validator when YAML uses JWT or Basic auth (required by LightApi)
        needs_validator = (
            "JWTAuthentication" in content or "BasicAuthentication" in content
        )
        if needs_validator and login_validator is None:
            login_validator = _dummy_login_validator
        return LightApi.from_config(path, login_validator=login_validator)
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
        raw = {"database": {"url": "sqlite:///:memory:"}, "endpoints": [{"fields": {}}]}
        with pytest.raises(ValidationError):
            LightAPIConfig.model_validate(raw)

    def test_unknown_field_type_raises(self):
        raw = {
            "database": {"url": "sqlite:///:memory:"},
            "endpoints": [{"route": "/x", "fields": {"foo": {"type": "nonsense"}}}],
        }
        with pytest.raises(ValidationError):
            LightAPIConfig.model_validate(raw)

    def test_missing_env_var_raises(self):
        path = _write_yaml({"database": {"url": "${LIGHTAPI_DB_MISSING_XTEST}"}})
        try:
            with pytest.raises(ConfigurationError, match="LIGHTAPI_DB_MISSING_XTEST"):
                LightApi.from_config(path)
        finally:
            os.unlink(path)


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
            database:
              url: "sqlite:///:memory:"
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
            database:
              url: "sqlite:///:memory:"
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
            database:
              url: "sqlite:///:memory:"
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
            database:
              url: "sqlite:///:memory:"
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
            database:
              url: "sqlite:///:memory:"
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
            database:
              url: "sqlite:///:memory:"
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
            database:
              url: "sqlite:///:memory:"
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
            database:
              url: "sqlite:///:memory:"
            middleware: [CORSMiddleware]
            """
        app = _from_str(content)
        assert app is not None

    def test_from_config_kwargs_override_yaml(self):
        """LightApi.from_config(path, engine=custom_engine) uses custom engine."""
        from sqlalchemy import create_engine
        from sqlalchemy.pool import StaticPool

        content = """\
            database:
              url: "sqlite:///other.db"
            endpoints:
              - route: /items
                fields:
                  name: { type: str }
                meta:
                  methods: [GET]
            """
        path = _write_yaml(content)
        try:
            custom_engine = create_engine(
                "sqlite:///:memory:",
                connect_args={"check_same_thread": False},
                poolclass=StaticPool,
            )
            app = LightApi.from_config(path, engine=custom_engine)
            assert app._engine is custom_engine
        finally:
            os.unlink(path)


# ─────────────────────────────────────────────────────────────────────────────
# Auth/login YAML configuration
# ─────────────────────────────────────────────────────────────────────────────


class TestYamlAuthConfig:
    def test_auth_path_from_yaml(self):
        """auth.auth_path in YAML configures login/token route prefix."""
        os.environ["LIGHTAPI_JWT_SECRET"] = "test-secret"
        content = """\
            database:
              url: "sqlite:///:memory:"
            auth:
              auth_path: /api/auth
            defaults:
              authentication:
                backend: JWTAuthentication
                permission: IsAuthenticated
            endpoints:
              - route: /x
                fields:
                  data: { type: str }
                meta:
                  methods: [GET]
            """
        app = _from_str(content)
        from starlette.testclient import TestClient

        client = TestClient(app.build_app())
        resp = client.post(
            "/api/auth/login",
            json={"username": "a", "password": "b"},
        )
        assert resp.status_code in (200, 401)

    def test_login_validator_dotted_path_from_yaml(self):
        """auth.login_validator as dotted path resolves to callable."""
        os.environ["LIGHTAPI_JWT_SECRET"] = "test-secret"
        content = """\
            database:
              url: "sqlite:///:memory:"
            auth:
              login_validator: tests.test_yaml_config._dummy_login_validator
            defaults:
              authentication:
                backend: JWTAuthentication
                permission: IsAuthenticated
            endpoints:
              - route: /x
                fields:
                  data: { type: str }
                meta:
                  methods: [GET]
            """
        app = _from_str(content)
        assert app._login_validator is _dummy_login_validator

    def test_jwt_expiration_from_defaults(self):
        """defaults.authentication.jwt_expiration flows to Meta."""
        content = """\
            database:
              url: "sqlite:///:memory:"
            defaults:
              authentication:
                backend: JWTAuthentication
                permission: IsAuthenticated
                jwt_expiration: 300
            endpoints:
              - route: /x
                fields:
                  data: { type: str }
                meta:
                  methods: [GET]
            """
        app = _from_str(content)
        cls = app._endpoint_map["/x"]
        assert cls.Meta.authentication.jwt_expiration == 300

    def test_jwt_extra_claims_from_defaults(self):
        """defaults.authentication.jwt_extra_claims flows to Meta."""
        content = """\
            database:
              url: "sqlite:///:memory:"
            defaults:
              authentication:
                backend: JWTAuthentication
                permission: IsAuthenticated
                jwt_extra_claims: [sub, email]
            endpoints:
              - route: /x
                fields:
                  data: { type: str }
                meta:
                  methods: [GET]
            """
        app = _from_str(content)
        cls = app._endpoint_map["/x"]
        assert cls.Meta.authentication.jwt_extra_claims == ["sub", "email"]

    def test_basic_authentication_from_yaml(self):
        """BasicAuthentication can be specified as backend in YAML."""
        content = """\
            database:
              url: "sqlite:///:memory:"
            defaults:
              authentication:
                backend: BasicAuthentication
                permission: IsAuthenticated
            endpoints:
              - route: /items
                fields:
                  name: { type: str }
                meta:
                  methods: [GET]
            """
        app = _from_str(content)
        from lightapi.auth import BasicAuthentication

        cls = app._endpoint_map["/items"]
        assert cls.Meta.authentication.backend is BasicAuthentication

    def test_login_validator_invalid_dotted_path_raises(self):
        """Invalid login_validator dotted path raises ConfigurationError."""
        os.environ["LIGHTAPI_JWT_SECRET"] = "test-secret"
        content = """\
            database:
              url: "sqlite:///:memory:"
            auth:
              login_validator: non.existent.module.foo
            defaults:
              authentication:
                backend: JWTAuthentication
                permission: IsAuthenticated
            endpoints:
              - route: /x
                fields:
                  data: { type: str }
                meta:
                  methods: [GET]
            """
        path = _write_yaml(content)
        try:
            with pytest.raises(ConfigurationError, match="login_validator"):
                LightApi.from_config(path)
        finally:
            os.unlink(path)


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
