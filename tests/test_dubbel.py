from __future__ import annotations

import hashlib
from datetime import date
from pathlib import Path

from ordner.dubbel import Dubbel, sha256_van, sha256_van_bestand, zoek_dubbelen
from ordner.index import bouw_index
from ordner.storage import Archief


def test_sha256_van_en_van_bestand(tmp_path: Path) -> None:
    data = b"abc" * 1_000_000  # > 1 MiB: meerdere blokken
    pad = tmp_path / "groot.bin"
    pad.write_bytes(data)
    verwacht = hashlib.sha256(data).hexdigest()
    assert sha256_van(data) == verwacht
    assert sha256_van_bestand(pad) == verwacht
    assert sha256_van(b"") == hashlib.sha256(b"").hexdigest()


def test_zoek_dubbelen(archief: Archief) -> None:
    doc = archief.maak_document("Eneco", date(2026, 3, 1))
    archief.voeg_bestand_toe(doc, "factuur.pdf", b"%PDF eneco")
    index = bouw_index(archief)

    dubbelen = zoek_dubbelen(index, [("nieuw.pdf", b"%PDF nieuw"), ("kopie.pdf", b"%PDF eneco")])

    assert dubbelen == [Dubbel("kopie.pdf", "2026/2026-03-01_eneco", "factuur.pdf", "Eneco", date(2026, 3, 1))]
    assert dubbelen[0].jaar == "2026" and dubbelen[0].map == "2026-03-01_eneco"
    assert zoek_dubbelen(index, []) == []
    assert zoek_dubbelen(index, [("x.pdf", b"anders")]) == []
