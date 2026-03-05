"""Tests for US9: YAML-based LightApi configuration."""
import os
import tempfile

import pytest
import yaml

from lightapi.lightapi import LightApi


class TestFromConfig:
    def test_from_config_invalid_yaml_raises(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            f.write("invalid: yaml: content: [")
            path = f.name
        try:
            with pytest.raises(Exception):
                LightApi.from_config(path)
        finally:
            os.unlink(path)

    def test_from_config_missing_env_var_raises(self):
        cfg = {"database_url": "${LIGHTAPI_DB_MISSING_XTEST}"}
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            yaml.dump(cfg, f)
            path = f.name
        try:
            with pytest.raises(Exception, match="LIGHTAPI_DB_MISSING_XTEST"):
                LightApi.from_config(path)
        finally:
            os.unlink(path)

    def test_from_config_valid_sqlite_url(self):
        cfg = {"database_url": "sqlite:///:memory:"}
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            yaml.dump(cfg, f)
            path = f.name
        try:
            app = LightApi.from_config(path)
            assert app is not None
        finally:
            os.unlink(path)

    def test_from_config_env_var_substitution(self, monkeypatch):
        monkeypatch.setenv("LIGHTAPI_TEST_DB_URL", "sqlite:///:memory:")
        cfg = {"database_url": "${LIGHTAPI_TEST_DB_URL}"}
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            yaml.dump(cfg, f)
            path = f.name
        try:
            app = LightApi.from_config(path)
            assert app is not None
        finally:
            os.unlink(path)

    def test_from_config_with_cors_origins(self):
        cfg = {
            "database_url": "sqlite:///:memory:",
            "cors_origins": ["https://example.com"],
        }
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            yaml.dump(cfg, f)
            path = f.name
        try:
            app = LightApi.from_config(path)
            assert app._cors_origins == ["https://example.com"]
        finally:
            os.unlink(path)
