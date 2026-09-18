"""Run every scenario against whichever lightapi is installed and save what it did.

    # the published version
    uv run --no-project --isolated --python 3.12 \\
        --with "lightapi[async]==0.1.29" --with httpx \\
        python tools/differential/record.py /tmp/run-a.json

    # a wheel built from the working tree (uv build)
    uv run --no-project --isolated --python 3.12 \\
        --with "lightapi[async] @ file://$PWD/dist/lightapi-0.1.27-py3-none-any.whl" \\
        --with httpx python tools/differential/record.py /tmp/run-b.json

    python tools/differential/compare.py /tmp/run-a.json /tmp/run-b.json

Recording the same version twice must give identical files. Do that first:
it is what proves a later difference comes from the code and not from the run.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
import warnings
from importlib import metadata
from pathlib import Path

from harness import JWT_SECRET, Recorder, install_fake_redis


def main(output: str) -> None:
    warnings.simplefilter("ignore")
    os.environ["LIGHTAPI_JWT_SECRET"] = JWT_SECRET
    fake_redis = install_fake_redis()

    import scenarios_more
    import scenarios_sync

    import lightapi

    repo = Path(__file__).resolve().parents[2]
    if repo in Path(lightapi.__file__).resolve().parents:
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

    recording = {"lightapi": metadata.version("lightapi"), "steps": rec.steps}
    Path(output).write_text(json.dumps(recording, indent=1), encoding="utf-8")
    print(f"lightapi {recording['lightapi']}: {len(rec.steps)} steps -> {output}")


if __name__ == "__main__":
    main(sys.argv[1])
