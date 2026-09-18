"""T6-03: doc pages that changed during the refactor, extracted and run.

Every ```python fence in the ten changed pages is at least ast.parse()d, so a
doc edit that breaks a code sample's syntax fails this test. Fences that are
illustrative fragments (a bare signature, a call with type-hinted keyword
args) are expected to fail that parse and are listed in KNOWN_FRAGMENTS so a
NEW syntax break elsewhere still fails loudly. The handful of fences that are
complete, self-contained scripts are additionally executed as real
subprocesses/pytest runs. Two of them (the async testing examples in
async.md and middleware.md) are pinned as REPRODUCING a known pre-existing
bug (B19, see test_async_testing_fixture_pattern_hits_the_known_table_creation_bug)
rather than asserted to pass, since they deterministically hit it.

The README's "Custom authentication" snippet (subclassing JWTAuthentication
with async validate_credentials calling out to a DB) is pseudocode — it calls
an undefined `self.get_user_from_db` — and is exercised for real instead by
tests/test_login_backend_subclass.py's AsyncCredentialsBackend, which follows
the exact same pattern with a real (stub) lookup.
"""

import ast
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

CHANGED_DOC_PAGES = [
    "docs/tutorial/responses.md",
    "docs/tutorial/endpoints.md",
    "docs/tutorial/requests.md",
    "docs/api-reference/rest.md",
    "docs/api-reference/pagination.md",
    "docs/api-reference/core.md",
    "docs/advanced/async.md",
    "docs/advanced/authentication.md",
    "docs/advanced/caching.md",
    "docs/advanced/middleware.md",
]

# (page, 0-based index of the ```python fence on that page) that are known,
# intentional illustrative fragments, not standalone Python.
KNOWN_FRAGMENTS = {
    ("docs/tutorial/endpoints.md", 6),
    ("docs/tutorial/requests.md", 0),
    ("docs/tutorial/requests.md", 1),
    ("docs/api-reference/pagination.md", 1),
    ("docs/api-reference/core.md", 1),
    ("docs/advanced/async.md", 0),
    ("docs/advanced/async.md", 1),
    ("docs/advanced/caching.md", 2),
}


def _python_fences(page: str) -> list[str]:
    text = (ROOT / page).read_text(encoding="utf-8")
    return re.findall(r"```python\n(.*?)```", text, re.DOTALL)


def _fence_under_heading(page: str, heading: str) -> str:
    text = (ROOT / page).read_text(encoding="utf-8")
    pattern = re.escape(heading) + r"\n(?:.*?\n)*?```python\n(.*?)```"
    match = re.search(pattern, text, re.DOTALL)
    assert match, f"heading {heading!r} or its python fence moved in {page}"
    return match.group(1)


@pytest.mark.parametrize("page", CHANGED_DOC_PAGES)
def test_every_python_fence_parses_or_is_a_known_fragment(page):
    failures = []
    for index, block in enumerate(_python_fences(page)):
        try:
            ast.parse(block)
        except SyntaxError as exc:
            if (page, index) not in KNOWN_FRAGMENTS:
                failures.append(f"fence #{index}: {exc}")
    assert not failures, f"{page}: unexpected syntax errors: {failures}"


def _run_script(script_path: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(script_path)], capture_output=True, text=True, timeout=15
    )


def _run_as_pytest(
    tmp_path: Path, script_name: str, source: str
) -> subprocess.CompletedProcess:
    # docs/advanced/async.md documents this exact pytest.ini as a prerequisite
    # for its async examples (asyncio_mode = auto); a bare subprocess in a tmp
    # dir has no such config, so ship it alongside the extracted script.
    (tmp_path / "pytest.ini").write_text(
        "[pytest]\nasyncio_mode = auto\n", encoding="utf-8"
    )
    script = tmp_path / script_name
    script.write_text(source, encoding="utf-8")
    return subprocess.run(
        [sys.executable, "-m", "pytest", str(script), "-q"],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=tmp_path,
    )


def test_async_testing_fixture_pattern_hits_the_known_table_creation_bug(tmp_path):
    """The doc's own async testing fixture (pytest_asyncio.fixture building the
    app while a loop is already running) triggers the pre-existing table
    creation bug: LightApi._create_tables() runs asyncio.run() in a worker
    thread when a loop is already running (lightapi/lightapi.py:284-291),
    which for aiosqlite checks out a connection bound to that dead thread's
    loop into the engine's own pool. Every later async ORM call on the real
    loop then fails with MissingGreenlet ("greenlet_spawn has not been
    called"), and the exception during create_all is itself swallowed to a
    warning log (lightapi.py:300-301), so the example silently serves against
    an app whose tables were never really created. Confirmed via the same
    root cause as tests/integration/test_postgres_async.py's B19 finding —
    not a new bug, but this is the first place it's shown to affect the
    docs' own recommended testing pattern verbatim, not just Postgres.
    """
    source = _fence_under_heading("docs/advanced/async.md", "**Fixture pattern**:")
    result = _run_as_pytest(tmp_path, "test_async_full_example.py", source)

    assert result.returncode != 0
    assert "MissingGreenlet" in result.stdout or "_run_ddl_visitor" in result.stdout


def test_middleware_example_hits_the_same_known_table_creation_bug(tmp_path):
    """Same root cause as test_async_testing_fixture_pattern_hits_the_known_table_creation_bug
    above: docs/advanced/middleware.md's own testing example reuses the async
    fixture pattern from docs/advanced/async.md and hits B19 the same way."""
    source = _fence_under_heading(
        "docs/advanced/middleware.md", "## Accessing Middleware Inside Tests"
    )
    result = _run_as_pytest(tmp_path, "test_middleware_example.py", source)

    assert result.returncode != 0
    assert "MissingGreenlet" in result.stdout or "_run_ddl_visitor" in result.stdout


def test_authentication_complete_example_builds_and_serves(tmp_path):
    source = _fence_under_heading(
        "docs/advanced/authentication.md", "## Complete Example"
    )
    db_path = tmp_path / "app.db"
    source = source.replace('"sqlite:///app.db"', f'"sqlite:///{db_path}"')
    source = source.replace("app.run()", "")

    script = tmp_path / "auth_example.py"
    script.write_text(
        source
        + """

from starlette.testclient import TestClient

client = TestClient(app.build_app())

unauthenticated = client.get("/users")
assert unauthenticated.status_code == 200, unauthenticated.text

denied = client.post("/users", json={"username": "abc", "email": "a@b.com"})
assert denied.status_code == 401, denied.text

print("AUTH_EXAMPLE_OK")
""",
        encoding="utf-8",
    )

    result = _run_script(script)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "AUTH_EXAMPLE_OK" in result.stdout
