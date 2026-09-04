from __future__ import annotations

from pathlib import Path

import pytest

from ordner.config import Settings

ENV_VARS = [
    "ORDNER_DATA",
    "ORDNER_OCR_TALEN",
    "ORDNER_OCR_PARALLEL",
    "ORDNER_RECONCILE_INTERVAL",
    "ORDNER_INBOX_INTERVAL",
]


@pytest.fixture(autouse=True)
def schone_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for naam in ENV_VARS:
        monkeypatch.delenv(naam, raising=False)


def test_from_env_defaults() -> None:
    s = Settings.from_env()
    assert s.data_root.is_absolute()
    assert s.data_root == Path("./data").resolve()
    assert s.ocr_talen == "nld+eng"
    assert s.ocr_parallel == 2
    assert s.reconcile_interval == 300
    assert s.inbox_interval == 5


def test_from_env_alles_gezet(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ORDNER_DATA", str(tmp_path / "archief"))
    monkeypatch.setenv("ORDNER_OCR_TALEN", "deu")
    monkeypatch.setenv("ORDNER_OCR_PARALLEL", "4")
    monkeypatch.setenv("ORDNER_RECONCILE_INTERVAL", "60")
    monkeypatch.setenv("ORDNER_INBOX_INTERVAL", "9")
    s = Settings.from_env()
    assert s.data_root == (tmp_path / "archief").resolve()
    assert s.ocr_talen == "deu"
    assert s.ocr_parallel == 4
    assert s.reconcile_interval == 60
    assert s.inbox_interval == 9


def test_from_env_ongeldige_int(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ORDNER_OCR_PARALLEL", "abc")
    with pytest.raises(ValueError, match="ORDNER_OCR_PARALLEL"):
        Settings.from_env()
