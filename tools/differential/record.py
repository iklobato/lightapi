"""Run every scenario against whichever lightapi is installed and save what it did.

Install each version into a venv of its own. Do NOT use `uv run --with
<local wheel>`: a rebuilt wheel keeps its file name and version, and uv then
reuses the environment it made for the previous build, so the run silently
tests old code.

    # A: the published version
    uv venv /tmp/la-a --python 3.12
    uv pip install -p /tmp/la-a "lightapi[async]==0.1.29" httpx
    /tmp/la-a/bin/python tools/differential/record.py /tmp/run-a.json

    # B: a wheel built from the working tree
    uv build
    uv venv /tmp/la-b --python 3.12
    uv pip install -p /tmp/la-b --no-cache --reinstall \\
        "lightapi[async] @ file://$PWD/dist/lightapi-0.1.27-py3-none-any.whl" httpx
    /tmp/la-b/bin/python tools/differential/record.py /tmp/run-b.json

    python tools/differential/compare.py /tmp/run-a.json /tmp/run-b.json

Recording the same version twice must give identical files. Do that first:
it is what proves a later difference comes from the code and not from the run.
Each recording carries a fingerprint of the installed source; if B's
fingerprint did not change after a rebuild, B is stale.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sys
import tempfile
import warnings
from importlib import metadata
from pathlib import Path

from harness import JWT_SECRET, Recorder, install_fake_redis


def source_fingerprint(package_dir: Path) -> str:
    digest = hashlib.sha256()
    for source in sorted(package_dir.rglob("*.py")):
        digest.update(source.relative_to(package_dir).as_posix().encode())
        digest.update(source.read_bytes())
    return digest.hexdigest()[:12]


def main(output: str) -> None:
    warnings.simplefilter("ignore")
    os.environ["LIGHTAPI_JWT_SECRET"] = JWT_SECRET
    fake_redis = install_fake_redis()

    import scenarios_more
    import scenarios_sync

    import lightapi

    package_dir = Path(lightapi.__file__).resolve().parent
    repo = Path(__file__).resolve().parents[2]
    if repo in package_dir.parents:
        raise SystemExit(
            "lightapi was imported from the working tree. Install a wheel or a "
            "release instead, so the run tests what users would get."
        )

    rec = Recorder()
    with tempfile.TemporaryDirectory() as tmp_dir:
        scenarios_sync.run(rec, tmp_dir, fake_redis)
        scenarios_more.yaml_config(rec, tmp_dir)
        scenarios_more.declared_changes(rec)
        asyncio.run(scenarios_more.async_engine_scenarios(rec, fake_redis))
        # Last, so it sees every table the scenarios above created.
        scenarios_sync.schema_ddl(rec)

    recording = {
        "lightapi": metadata.version("lightapi"),
        "fingerprint": source_fingerprint(package_dir),
        "steps": rec.steps,
    }
    Path(output).write_text(json.dumps(recording, indent=1), encoding="utf-8")
    print(
        f"lightapi {recording['lightapi']} (source {recording['fingerprint']}): "
        f"{len(rec.steps)} steps -> {output}"
    )


if __name__ == "__main__":
    main(sys.argv[1])
