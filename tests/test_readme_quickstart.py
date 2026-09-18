"""T6-01: the README Quick Start, extracted and run exactly as written.

Regenerates the script from the README on every run, so a doc edit that
breaks the example fails this test instead of going unnoticed. For the
release check against a real pip install of the wheel (not the working
tree editable install pytest normally runs against), see the test plan's
T6-01 command using tools/differential's environment-isolation pattern.
"""

import re
import subprocess
import sys
from pathlib import Path

README = Path(__file__).resolve().parents[1] / "README.md"


def _quickstart_source(db_path: Path) -> str:
    text = README.read_text(encoding="utf-8")
    match = re.search(r"## Quick Start\n\n```python\n(.*?)\n```", text, re.DOTALL)
    assert match, "README's Quick Start python block moved or changed shape"
    source = match.group(1)
    # A real file, like the README's own books.db, not in-memory: in-memory
    # sqlite defaults to SingletonThreadPool, a separate empty DB per thread,
    # and TestClient below may run requests on a different thread than the
    # one that just registered the table.
    source = source.replace('"sqlite:///books.db"', f'"sqlite:///{db_path}"')
    source = source.replace("if __name__ ==", "if False and __name__ ==")
    return source


def test_quickstart_source_runs_unmodified_and_serves_crud(tmp_path):
    script = tmp_path / "quickstart.py"
    script.write_text(
        _quickstart_source(tmp_path / "books.db")
        + """

from starlette.testclient import TestClient

client = TestClient(app.build_app())
created = client.post("/books", json={"title": "Clean Code", "author": "Robert Martin"})
assert created.status_code == 201, created.text
assert created.json()["title"] == "Clean Code"

listed = client.get("/books")
assert listed.status_code == 200
assert len(listed.json()["results"]) == 1
print("QUICKSTART_OK")
""",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(script)], capture_output=True, text=True, timeout=15
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "QUICKSTART_OK" in result.stdout
