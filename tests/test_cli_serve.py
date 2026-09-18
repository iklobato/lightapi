"""T4-01, T4-02, T4-03: the `lightapi serve` command and `python -m lightapi`,
run as real subprocesses against the container's example config."""

import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

import pytest

EXAMPLE_CONFIG = "docker/lightapi.example.yaml"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_up(base_url: str, timeout: float = 15.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            urllib.request.urlopen(f"{base_url}/healthz", timeout=1).read()
            return True
        except Exception:
            time.sleep(0.2)
    return False


def _get(url: str) -> tuple[int, bytes]:
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


@pytest.fixture
def real_server(tmp_path):
    """Starts a subprocess with the given argv and env, tears it down after."""
    procs: list[subprocess.Popen] = []

    def start(argv: list[str], env_overrides: dict) -> tuple[subprocess.Popen, str]:
        port = _free_port()
        env = {
            **os.environ,
            "LIGHTAPI_HOST": "127.0.0.1",
            "LIGHTAPI_PORT": str(port),
            "DATABASE_URL": f"sqlite:///{tmp_path}/t401.db",
            **env_overrides,
        }
        proc = subprocess.Popen(
            argv, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
        )
        procs.append(proc)
        return proc, f"http://127.0.0.1:{port}"

    yield start

    for proc in procs:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


def test_lightapi_serve_console_script(real_server):
    proc, base = real_server(
        [sys.executable, "-m", "lightapi", "serve"],
        {"LIGHTAPI_CONFIG": EXAMPLE_CONFIG},
    )

    up = _wait_up(base)
    assert up, proc.stdout.read() if proc.poll() is not None else "server timed out"

    healthz_status, _ = _get(f"{base}/healthz")
    books_status, books_body = _get(f"{base}/books")
    assert healthz_status == 200
    assert books_status == 200
    assert b"results" in books_body


def test_python_dash_m_lightapi_defaults_to_serve(real_server):
    proc, base = real_server(
        [sys.executable, "-m", "lightapi"], {"LIGHTAPI_CONFIG": EXAMPLE_CONFIG}
    )

    up = _wait_up(base)
    assert up, proc.stdout.read() if proc.poll() is not None else "server timed out"
    status, _ = _get(f"{base}/healthz")
    assert status == 200


def test_missing_lightapi_config_exits_nonzero_with_a_clear_message():
    env = {k: v for k, v in os.environ.items() if k != "LIGHTAPI_CONFIG"}

    result = subprocess.run(
        [sys.executable, "-m", "lightapi", "serve"],
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode != 0
    assert "LIGHTAPI_CONFIG" in (result.stdout + result.stderr)


def test_invalid_port_exits_nonzero_with_a_clear_message():
    env = {
        **os.environ,
        "LIGHTAPI_CONFIG": EXAMPLE_CONFIG,
        "LIGHTAPI_PORT": "not-a-number",
        "DATABASE_URL": "sqlite://",
    }

    result = subprocess.run(
        [sys.executable, "-m", "lightapi", "serve"],
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode != 0
    assert "LIGHTAPI_PORT" in (result.stdout + result.stderr)


def test_unknown_subcommand_exits_nonzero():
    result = subprocess.run(
        [sys.executable, "-m", "lightapi", "dance"],
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode != 0
    assert "dance" in (result.stdout + result.stderr)
