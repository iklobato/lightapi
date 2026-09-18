"""The API that the README, docs and examples teach must keep working.

tests/data/public_api.json was recorded from the published package by
tools/differential/snapshot_public_api.py. A name may gain an optional
parameter; it may not disappear, lose a parameter, or start requiring one.
"""

import importlib
import inspect
import json
from pathlib import Path

import pytest

SNAPSHOT = json.loads(
    (Path(__file__).parent / "data" / "public_api.json").read_text(encoding="utf-8")
)
IGNORED_PARAMETERS = {"self", "cls", "mcs"}
VARIADIC = {"VAR_POSITIONAL", "VAR_KEYWORD"}


def _current_parameters(qualified_name: str) -> list[list]:
    owner_name, _, member_name = qualified_name.partition(".")
    for module_name, name in SNAPSHOT["imports"]:
        if name != owner_name:
            continue
        obj = getattr(importlib.import_module(module_name), name)
        if member_name:
            obj = inspect.getattr_static(obj, member_name)
            obj = getattr(obj, "__func__", obj)
        return [
            [p.name, p.kind.name, p.default is not inspect.Parameter.empty]
            for p in inspect.signature(obj).parameters.values()
            if p.name not in IGNORED_PARAMETERS
        ]
    raise AssertionError(f"{owner_name} is not importable any more")


@pytest.mark.parametrize(("module_name", "name"), SNAPSHOT["imports"])
def test_documented_name_still_imports(module_name, name):
    module = importlib.import_module(module_name)

    assert hasattr(module, name), f"from {module_name} import {name} broke"


@pytest.mark.parametrize("qualified_name", sorted(SNAPSHOT["signatures"]))
def test_documented_signature_is_still_accepted(qualified_name):
    recorded = SNAPSHOT["signatures"][qualified_name]

    current = _current_parameters(qualified_name)

    # Every recorded parameter is still there, in the same place and kind, and
    # one that was optional did not become required.
    for position, (name, kind, had_default) in enumerate(recorded):
        assert position < len(current), f"{qualified_name} lost '{name}'"
        current_name, current_kind, has_default = current[position]
        assert (current_name, current_kind) == (name, kind)
        assert has_default or not had_default, f"'{name}' became required"
    # Anything added after them must be optional, or old calls would break.
    for name, kind, has_default in current[len(recorded) :]:
        assert has_default or kind in VARIADIC, f"new required parameter '{name}'"
