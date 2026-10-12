"""Record the public API that the README, docs and examples tell users to import.

Run it against a released version to produce the snapshot that
tests/test_public_api.py checks the working tree against:

    uv run --no-project --isolated --python 3.12 \\
        --with "lightapi[async]==0.1.29" \\
        python tools/differential/snapshot_public_api.py > tests/data/public_api.json

Only names that really import in the running version are recorded, so a doc
snippet that was already broken does not become a requirement.
"""

from __future__ import annotations

import importlib
import inspect
import json
import re
import sys
from importlib import metadata
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
SOURCES = ("README.md", "docs", "examples")

# Underscore members that the docs tell users to call (README "Built-in async
# CRUD helpers", docs/advanced/async.md, docs/api-reference/pagination.md).
DOCUMENTED_PRIVATE = {
    "RestEndpoint": (
        "_list_async",
        "_retrieve_async",
        "_create_async",
        "_update_async",
        "_destroy_async",
        "_get_async_engine",
    ),
}

_IMPORT = re.compile(
    r"^\s*from\s+(lightapi[\w.]*)\s+import\s+(\([^)]*\)|[^\n]+)", re.MULTILINE
)


def documented_imports() -> set[tuple[str, str]]:
    pairs: set[tuple[str, str]] = set()
    for source in SOURCES:
        path = REPO / source
        files = [path] if path.is_file() else sorted(path.rglob("*"))
        for file in files:
            if file.suffix in {".md", ".py"}:
                pairs |= _imports_in(file.read_text(encoding="utf-8"))
    return pairs


def _imports_in(text: str) -> set[tuple[str, str]]:
    pairs = set()
    for module, names in _IMPORT.findall(text):
        for chunk in names.strip("()").split(","):
            name = chunk.split("#")[0].split(" as ")[0].strip()
            if name.isidentifier():
                pairs.add((module, name))
    return pairs


def _parameters(callable_: Any) -> list[list[Any]] | None:
    try:
        signature = inspect.signature(callable_)
    except (TypeError, ValueError):
        return None
    return [
        [p.name, p.kind.name, p.default is not inspect.Parameter.empty]
        for p in signature.parameters.values()
        if p.name not in {"self", "cls", "mcs"}
    ]


def _own(member: Any) -> bool:
    return (getattr(member, "__module__", "") or "").startswith("lightapi")


def signatures_of(name: str, obj: Any) -> dict[str, list[list[Any]]]:
    found: dict[str, list[list[Any]]] = {}
    if inspect.isclass(obj):
        wanted = [m for m in vars(obj) if not m.startswith("_")]
        wanted += ["__init__", *DOCUMENTED_PRIVATE.get(name, ())]
        for member_name in wanted:
            member = inspect.getattr_static(obj, member_name, None)
            member = getattr(member, "__func__", member)
            if inspect.isfunction(member) and _own(member):
                found[f"{name}.{member_name}"] = _parameters(member) or []
    elif inspect.isfunction(obj) and _own(obj):
        found[name] = _parameters(obj) or []
    return found


def snapshot() -> dict[str, Any]:
    imports, signatures = [], {}
    for module_name, name in sorted(documented_imports()):
        try:
            obj = getattr(importlib.import_module(module_name), name)
        except (ImportError, AttributeError):
            continue
        imports.append([module_name, name])
        signatures.update(signatures_of(name, obj))

    import lightapi

    in_repo = REPO in Path(lightapi.__file__).resolve().parents
    origin = "working tree" if in_repo else "installed package"
    return {
        "recorded_from": f"lightapi {metadata.version('lightapi')} ({origin})",
        "imports": imports,
        "signatures": dict(sorted(signatures.items())),
    }


if __name__ == "__main__":
    json.dump(snapshot(), sys.stdout, indent=2)
    sys.stdout.write("\n")
