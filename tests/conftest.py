"""Gedeelde pytest-fixtures voor Ordner."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterator

import pytest
from fastapi.testclient import TestClient

from ordner.storage import Archief

try:
    from ordner.extract import ExtractieFout
except ImportError:  # extract.py is nog leeg tot pakket 04

    class ExtractieFout(Exception):  # type: ignore[no-redef]
        """Tijdelijke vervanger tot ordner.extract de echte definieert."""


Handler = Callable[[list[str]], tuple[int, bytes, bytes]]


@dataclass
class _Registratie:
    rc: int = 0
    stdout: bytes = b""
    stderr: bytes = b""
    handler: Handler | None = None


@dataclass
class CmdMock:
    """Vervanger voor ordner.extract.run_cmd in tests."""

    calls: list[list[str]] = field(default_factory=list)
    _registraties: dict[str, _Registratie] = field(default_factory=dict)

    def register(
        self,
        naam: str,
        rc: int = 0,
        stdout: bytes = b"",
        stderr: bytes = b"",
        handler: Handler | None = None,
    ) -> None:
        self._registraties[naam] = _Registratie(rc, stdout, stderr, handler)

    async def __call__(self, args: list[str], timeout: float = 600) -> tuple[int, bytes, bytes]:
        self.calls.append(list(args))
        naam = Path(args[0]).name
        if naam.lower().endswith(".exe"):
            naam = naam[:-4]
        reg = self._registraties.get(naam)
        if reg is None:
            raise ExtractieFout(f"niet-geregistreerd commando in test: {naam!r}")
        if reg.handler is not None:
            return reg.handler(list(args))
        return reg.rc, reg.stdout, reg.stderr


@pytest.fixture
def mock_cmd(monkeypatch: pytest.MonkeyPatch) -> CmdMock:
    mock = CmdMock()
    monkeypatch.setattr("ordner.extract.run_cmd", mock, raising=False)
    return mock


@pytest.fixture
def archief(tmp_path: Path) -> Archief:
    return Archief(tmp_path / "archief")


@pytest.fixture
def client(tmp_path: Path, mock_cmd: CmdMock) -> Iterator[TestClient]:
    """TestClient met draaiende lifespan (index, OCR-queue, lussen) en gemockte OCR-tools."""
    from ordner.config import Settings
    from ordner.web.app import create_app

    mock_cmd.register("pdfinfo", stdout=b"Pages: 1")
    mock_cmd.register("pdftotext", stdout=b"x" * 100)
    mock_cmd.register("tesseract", stdout=b"tekst")
    app = create_app(Settings(data_root=tmp_path / "archief", reconcile_interval=3600, inbox_interval=3600))
    with TestClient(app) as c:
        yield c
