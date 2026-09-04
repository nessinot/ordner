"""Fixtures voor de e2e-lagen (pakket 12): lokale uvicorn voor de browser-laag, Docker-image voor de container-laag."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import httpx
import pytest

REPO = Path(__file__).resolve().parent.parent.parent
FIXTURES = REPO / "tests" / "fixtures"

BROWSER_PORT = 8765
CONTAINER_PORT = 18099
CONTAINER_NAAM = "ordner-e2e"
CONTAINER_IMAGE = "ordner-e2e"
BUILD_FROM = "ghcr.io/home-assistant/amd64-base-debian:bookworm"


def wacht_op_http(url: str, timeout: float, proces: subprocess.Popen[bytes] | None = None) -> None:
    """Wacht tot `GET url` 200 geeft; faalt met een leesbare melding als het proces eerder stopt."""
    deadline = time.monotonic() + timeout
    laatste: str = "geen antwoord"
    while time.monotonic() < deadline:
        if proces is not None and proces.poll() is not None:
            raise RuntimeError(f"server stopte voortijdig met code {proces.returncode}")
        try:
            r = httpx.get(url, timeout=2)
            if r.status_code == 200:
                return
            laatste = f"status {r.status_code}"
        except httpx.HTTPError as e:
            laatste = repr(e)
        time.sleep(0.25)
    raise RuntimeError(f"{url} niet bereikbaar binnen {timeout:.0f} s ({laatste})")


@dataclass(frozen=True)
class Server:
    url: str
    archief: Path


@pytest.fixture(scope="session")
def ocr_beschikbaar() -> bool:
    return bool(shutil.which("tesseract") and shutil.which("pdftotext"))


@pytest.fixture(scope="session")
def server(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Server]:
    """Echte uvicorn in een subprocess met een lege archiefmap; inbox pollt elke seconde."""
    archief = tmp_path_factory.mktemp("archief")
    env = dict(os.environ)
    env.update(
        ORDNER_DATA=str(archief),
        ORDNER_INBOX_INTERVAL="1",
        ORDNER_RECONCILE_INTERVAL="3600",
    )
    proces = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "--app-dir", "addon", "ordner.web.app:app", "--port", str(BROWSER_PORT), "--log-level", "warning"],
        cwd=REPO,
        env=env,
    )
    url = f"http://127.0.0.1:{BROWSER_PORT}"
    try:
        wacht_op_http(url + "/", timeout=20, proces=proces)
        yield Server(url, archief)
    finally:
        proces.terminate()
        try:
            proces.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proces.kill()
            proces.wait()


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args: dict[str, object]) -> dict[str, object]:
    """Mobiele viewport: de add-on wordt vooral vanaf de telefoon gebruikt."""
    return {
        **browser_context_args,
        "viewport": {"width": 390, "height": 844},
        "is_mobile": True,
        "has_touch": True,
    }


# --- container-laag -------------------------------------------------------


@dataclass(frozen=True)
class Container:
    url: str
    share: Path


def _docker(*args: str, timeout: float = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["docker", *args], capture_output=True, text=True, timeout=timeout, check=False)


@pytest.fixture(scope="session")
def container(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Container]:
    """Bouwt het add-on-image en start het met een gemounte archiefmap; skipt zonder docker."""
    if shutil.which("docker") is None:
        pytest.skip("docker niet gevonden")

    build = _docker(
        "build", "--build-arg", f"BUILD_FROM={BUILD_FROM}", "-t", CONTAINER_IMAGE, str(REPO / "addon"), timeout=15 * 60
    )
    if build.returncode != 0:
        pytest.fail(f"docker build mislukt:\n{build.stdout}\n{build.stderr}")

    basis = tmp_path_factory.mktemp("container")
    share = basis / "share"
    data = basis / "data"
    share.mkdir()
    data.mkdir()
    (data / "options.json").write_text(
        '{"ocr_talen": "nld+eng", "ocr_parallel": 2, "reconcile_interval": 3600}\n', encoding="utf-8"
    )

    # Vooraf een pending document neerzetten: test "pending wordt na start opgepakt".
    pending = share / "2025" / "2025-01-01_pending-test"
    pending.mkdir(parents=True)
    shutil.copy(FIXTURES / "foto.png", pending / "foto.png")
    (pending / "meta.md").write_text(
        "---\n"
        "titel: Pending test\n"
        "documentdatum: 2025-01-01\n"
        "uploaddatum: '2025-01-01T12:00'\n"
        "tags: []\n"
        "bestanden: [foto.png]\n"
        "ocr: pending\n"
        "---\n",
        encoding="utf-8",
    )

    _docker("rm", "-f", CONTAINER_NAAM)
    run = _docker(
        "run", "-d", "--rm", "--name", CONTAINER_NAAM,
        "-p", f"{CONTAINER_PORT}:8099",
        "-v", f"{share.resolve()}:/share/ordner",  # absolute (Windows-)paden; Docker Desktop vertaalt ze
        "-v", f"{data.resolve()}:/data",
        CONTAINER_IMAGE,
    )
    if run.returncode != 0:
        pytest.fail(f"docker run mislukt:\n{run.stdout}\n{run.stderr}")

    url = f"http://127.0.0.1:{CONTAINER_PORT}"
    try:
        try:
            wacht_op_http(url + "/", timeout=60)
        except RuntimeError as e:
            logs = _docker("logs", CONTAINER_NAAM)
            pytest.fail(f"{e}\n--- docker logs ---\n{logs.stdout}\n{logs.stderr}")
        yield Container(url, share)
    finally:
        _docker("stop", CONTAINER_NAAM)
