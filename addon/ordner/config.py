"""Instellingen van Ordner, gelezen uit omgevingsvariabelen."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

INBOX_DIR = "_inbox"
TRASH_DIR = "_prullenbak"
META_NAAM = "meta.md"
EXTRAHEERBAAR = {".pdf", ".jpg", ".jpeg", ".png", ".heic"}


def _lees_int(naam: str, default: int) -> int:
    waarde = os.environ.get(naam)
    if waarde is None or waarde.strip() == "":
        return default
    try:
        return int(waarde)
    except ValueError as e:
        raise ValueError(f"{naam} moet een geheel getal zijn, kreeg {waarde!r}") from e


@dataclass(frozen=True)
class Settings:
    data_root: Path
    ocr_talen: str = "nld+eng"
    ocr_parallel: int = 2
    reconcile_interval: int = 300
    inbox_interval: int = 5

    @classmethod
    def from_env(cls) -> Settings:
        data_root = Path(os.environ.get("ORDNER_DATA") or "./data").resolve()
        return cls(
            data_root=data_root,
            ocr_talen=os.environ.get("ORDNER_OCR_TALEN") or "nld+eng",
            ocr_parallel=_lees_int("ORDNER_OCR_PARALLEL", 2),
            reconcile_interval=_lees_int("ORDNER_RECONCILE_INTERVAL", 300),
            inbox_interval=_lees_int("ORDNER_INBOX_INTERVAL", 5),
        )
