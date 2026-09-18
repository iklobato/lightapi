"""Compare two recordings made by record.py.

Exit status 0 means every difference is one the CHANGELOG declares.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

# step id (or prefix ending in "/") -> why the two versions are allowed to differ
ALLOWED = {
    "changes/sync-override-": (
        "A plain `def get/post` override used to be ignored; it is served now."
    ),
    "changes/login-with-subclass-backend": (
        "/auth/login now calls validate_credentials() of the endpoint's backend."
    ),
    "cache-async/": (
        "Meta.cache was ignored on async engines; GETs are cached and writes "
        "invalidate now."
    ),
}


def _reason(step_id: str) -> str | None:
    for prefix, reason in ALLOWED.items():
        if step_id == prefix or step_id.startswith(prefix):
            return reason
    return None


def _load(path: str) -> tuple[str, dict[str, Any]]:
    recording = json.loads(Path(path).read_text(encoding="utf-8"))
    steps = {step["id"]: step for step in recording["steps"]}
    if len(steps) != len(recording["steps"]):
        raise SystemExit(f"{path}: step ids are not unique")
    return recording["lightapi"], steps


def _describe(step: dict[str, Any] | None) -> str:
    if step is None:
        return "    (step missing)"
    if "value" in step:
        return f"    value: {step['value']}"
    return (
        f"    status: {step['status']}\n"
        f"    headers: {step['headers']}\n"
        f"    body: {step['body'][:600]}"
    )


def main(path_a: str, path_b: str) -> int:
    version_a, steps_a = _load(path_a)
    version_b, steps_b = _load(path_b)
    same, allowed, unexpected = 0, [], []
    for step_id in sorted(steps_a.keys() | steps_b.keys()):
        a, b = steps_a.get(step_id), steps_b.get(step_id)
        if a == b:
            same += 1
        elif _reason(step_id):
            allowed.append(step_id)
        else:
            unexpected.append(step_id)

    print(f"A = lightapi {version_a} ({len(steps_a)} steps)")
    print(f"B = lightapi {version_b} ({len(steps_b)} steps)")
    print(f"identical: {same}")
    print(f"different, declared in the CHANGELOG: {len(allowed)}")
    for step_id in allowed:
        print(f"  {step_id}: {_reason(step_id)}")
    print(f"different, NOT declared: {len(unexpected)}")
    for step_id in unexpected:
        print(f"\n  {step_id}")
        print("   A:")
        print(_describe(steps_a.get(step_id)))
        print("   B:")
        print(_describe(steps_b.get(step_id)))
    return 1 if unexpected else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
