from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from ordner.config import META_NAAM
from ordner.index import Index, Reconciler, bouw_index
from ordner.meta import lees_meta, schrijf_meta
from ordner.storage import Archief

DATUM = date(2026, 3, 1)


class Queue:
    """Verzamelt queue_fn-aanroepen."""

    def __init__(self) -> None:
        self.calls: list[tuple[Path, str]] = []

    def __call__(self, doc: Path, naam: str) -> None:
        self.calls.append((doc, naam))


@pytest.fixture
def queue() -> Queue:
    return Queue()


@pytest.fixture
def reconciler(archief: Archief, queue: Queue) -> Reconciler:
    return Reconciler(archief, bouw_index(archief), queue)


def _doc(archief: Archief, titel: str = "Factuur", datum: date = DATUM, *bestanden: str) -> Path:
    doc = archief.maak_document(titel, datum)
    for naam in bestanden:
        archief.voeg_bestand_toe(doc, naam, b"x")
    return doc


def _zet_ocr(doc: Path, status: str) -> None:
    meta = lees_meta(doc)
    meta.ocr = status  # type: ignore[assignment]
    schrijf_meta(doc, meta)


# --- Index / bouw_index ---------------------------------------------------


def test_bouw_index_met_en_zonder_txt(archief: Archief) -> None:
    met = _doc(archief, "Met", DATUM, "a.pdf")
    (met / "a.pdf.txt").write_text("tekst van a", encoding="utf-8")
    zonder = _doc(archief, "Zonder", DATUM, "b.pdf")

    index = bouw_index(archief)
    assert set(index.docs) == {archief.relatief(met), archief.relatief(zonder)}
    assert index.docs[archief.relatief(met)].teksten == {"a.pdf": "tekst van a"}
    assert index.docs[archief.relatief(zonder)].teksten == {}
    entry = index.docs[archief.relatief(met)]
    assert entry.map == met and entry.meta.titel == "Met"


def test_bouw_index_slaat_kapotte_meta_over(archief: Archief) -> None:
    goed = _doc(archief, "Goed")
    kapot = archief.root / "2026" / "2026-01-01_kapot"
    kapot.mkdir(parents=True)
    (kapot / META_NAAM).write_text("titel: geen frontmatter\n", encoding="utf-8")

    index = bouw_index(archief)
    assert list(index.docs) == [archief.relatief(goed)]


def test_alle_sorteert_datum_desc_dan_rel_desc(archief: Archief) -> None:
    oud = _doc(archief, "Oud", date(2025, 1, 1))
    a = _doc(archief, "A", date(2026, 5, 5))
    b = _doc(archief, "B", date(2026, 5, 5))
    index = bouw_index(archief)
    assert [e.map for e in index.alle()] == [b, a, oud]


def test_tellingen(archief: Archief) -> None:
    _doc(archief, "Done", DATUM, "a.docx")
    _doc(archief, "Pending", DATUM, "a.pdf")
    failed = _doc(archief, "Failed", DATUM, "b.pdf")
    _zet_ocr(failed, "failed")
    assert bouw_index(archief).tellingen() == {"totaal": 3, "pending": 1, "done": 1, "failed": 1}
    assert Index().tellingen() == {"totaal": 0, "pending": 0, "done": 0, "failed": 0}


def test_verwijder(archief: Archief) -> None:
    doc = _doc(archief)
    index = bouw_index(archief)
    index.verwijder(archief.relatief(doc))
    index.verwijder("bestaat/niet")
    assert index.docs == {}


def test_zoek_hash_volgt_herlaad_en_verwijder(archief: Archief) -> None:
    import hashlib

    doc = _doc(archief, "Factuur", DATUM, "a.pdf")
    index = bouw_index(archief)
    h = hashlib.sha256(b"x").hexdigest()
    treffer = index.zoek_hash(h)
    assert treffer is not None
    assert treffer[0].rel == archief.relatief(doc) and treffer[1] == "a.pdf"
    assert index.zoek_hash("0" * 64) is None
    # bestand weg + herlaad -> hash weg
    (doc / "a.pdf").unlink()
    meta = lees_meta(doc)
    meta.bestanden = []
    meta.sha256 = {}
    schrijf_meta(doc, meta)
    index.herlaad(archief, doc)
    assert index.zoek_hash(h) is None
    archief.voeg_bestand_toe(doc, "b.pdf", b"x")
    index.herlaad(archief, doc)
    assert index.zoek_hash(h) is not None
    index.verwijder(archief.relatief(doc))
    assert index.zoek_hash(h) is None


# --- Reconciler: sync ------------------------------------------------------


def test_reconcile_nieuw_bestand_via_samba(archief: Archief, reconciler: Reconciler, queue: Queue) -> None:
    doc = _doc(archief)
    (doc / "scan.pdf").write_bytes(b"%PDF")

    rapport = reconciler.run()

    meta = lees_meta(doc)
    assert meta.bestanden == ["scan.pdf"]
    assert meta.ocr == "pending"
    assert queue.calls == [(doc, "scan.pdf")]
    assert rapport.gesynchroniseerd == 1
    assert rapport.gequeued == 1
    assert rapport.documenten == 1
    assert reconciler.index.docs[archief.relatief(doc)].meta.bestanden == ["scan.pdf"]


def test_reconcile_verwijderd_bestand(archief: Archief, reconciler: Reconciler, queue: Queue) -> None:
    doc = _doc(archief, "Factuur", DATUM, "a.pdf", "b.docx")
    (doc / "a.pdf").unlink()

    rapport = reconciler.run()

    meta = lees_meta(doc)
    assert meta.bestanden == ["b.docx"]
    assert meta.ocr == "done"
    assert queue.calls == []
    assert rapport.gesynchroniseerd == 1


def test_reconcile_behoudt_volgorde_en_geupload_txt(archief: Archief, reconciler: Reconciler) -> None:
    doc = _doc(archief, "Factuur", DATUM, "b.pdf", "notities.txt", "a.pdf")
    (doc / "b.pdf.txt").write_text("ocr", encoding="utf-8")
    (doc / "a.pdf.txt").write_text("ocr", encoding="utf-8")
    (doc / "los.txt").write_text("onbekend", encoding="utf-8")  # niet in bestanden -> als OCR-tekst genegeerd
    (doc / "nieuw.png").write_bytes(b"x")

    reconciler.run()

    assert lees_meta(doc).bestanden == ["b.pdf", "notities.txt", "a.pdf", "nieuw.png"]


def test_reconcile_vult_ontbrekende_sha256_en_ruimt_verweesde_op(archief: Archief, reconciler: Reconciler) -> None:
    import hashlib

    doc = _doc(archief, "Factuur", DATUM, "a.pdf")
    (doc / "scan.jpg").write_bytes(b"jpg")  # via Samba: geen hash
    meta = lees_meta(doc)
    meta.sha256 = {"weg.pdf": "0" * 64}  # oude meta.md: a.pdf zonder hash, plus een verweesde hash
    schrijf_meta(doc, meta)

    rapport = reconciler.run()

    meta = lees_meta(doc)
    assert meta.bestanden == ["a.pdf", "scan.jpg"]
    assert meta.sha256 == {"a.pdf": hashlib.sha256(b"x").hexdigest(), "scan.jpg": hashlib.sha256(b"jpg").hexdigest()}
    assert rapport.gehasht == 2
    assert reconciler.index.zoek_hash(hashlib.sha256(b"jpg").hexdigest()) is not None
    # tweede ronde: niets te hashen, niets geschreven
    mtime = (doc / META_NAAM).stat().st_mtime_ns
    rapport = reconciler.run()
    assert rapport.gehasht == 0
    assert (doc / META_NAAM).stat().st_mtime_ns == mtime


def test_reconcile_ongewijzigd_schrijft_niet(archief: Archief, reconciler: Reconciler, queue: Queue) -> None:
    doc = _doc(archief, "Factuur", DATUM, "a.docx")
    voor = (doc / META_NAAM).read_text(encoding="utf-8")
    mtime = (doc / META_NAAM).stat().st_mtime_ns

    rapport = reconciler.run()

    assert (doc / META_NAAM).read_text(encoding="utf-8") == voor
    assert (doc / META_NAAM).stat().st_mtime_ns == mtime
    assert rapport.gesynchroniseerd == 0 and rapport.gequeued == 0 and rapport.documenten == 1


def test_reconcile_pending_wordt_done_na_txt(archief: Archief, reconciler: Reconciler, queue: Queue) -> None:
    doc = _doc(archief, "Factuur", DATUM, "a.pdf")
    assert lees_meta(doc).ocr == "pending"
    (doc / "a.pdf.txt").write_text("klaar", encoding="utf-8")

    reconciler.run()

    assert lees_meta(doc).ocr == "done"
    assert queue.calls == []
    assert reconciler.index.docs[archief.relatief(doc)].teksten == {"a.pdf": "klaar"}


def test_reconcile_failed_niet_opnieuw(archief: Archief, reconciler: Reconciler, queue: Queue) -> None:
    doc = _doc(archief, "Factuur", DATUM, "a.pdf")
    _zet_ocr(doc, "failed")

    rapport = reconciler.run()

    assert lees_meta(doc).ocr == "failed"
    assert queue.calls == []
    assert rapport.gequeued == 0


def test_reconcile_kapotte_meta_overgeslagen(archief: Archief, reconciler: Reconciler) -> None:
    kapot = archief.root / "2026" / "2026-01-01_kapot"
    kapot.mkdir(parents=True)
    (kapot / META_NAAM).write_text("geen frontmatter\n", encoding="utf-8")
    (kapot / "a.pdf").write_bytes(b"x")

    rapport = reconciler.run()

    assert rapport.documenten == 0
    assert (kapot / META_NAAM).read_text(encoding="utf-8") == "geen frontmatter\n"


# --- Reconciler: mappen zonder meta.md --------------------------------------


def test_reconcile_maakt_meta_met_datumprefix(archief: Archief, reconciler: Reconciler, queue: Queue) -> None:
    map = archief.root / "2025" / "2025-05-01_oude_factuur"
    map.mkdir(parents=True)
    (map / "x.pdf").write_bytes(b"%PDF")

    rapport = reconciler.run()

    meta = lees_meta(map)
    assert meta.titel == "oude factuur"
    assert meta.documentdatum == date(2025, 5, 1)
    assert meta.bestanden == ["x.pdf"]
    assert meta.ocr == "pending"
    assert meta.uploaddatum.second == 0 and meta.uploaddatum.microsecond == 0
    assert rapport.meta_aangemaakt == 1
    assert rapport.gesynchroniseerd == 1
    assert queue.calls == [(map, "x.pdf")]
    assert "2025/2025-05-01_oude_factuur" in reconciler.index.docs


def test_reconcile_maakt_meta_zonder_datumprefix(archief: Archief, reconciler: Reconciler) -> None:
    map = archief.root / "2024" / "Bonnetjes-AH"
    map.mkdir(parents=True)
    (map / "bon.jpg").write_bytes(b"x")

    reconciler.run()

    meta = lees_meta(map)
    assert meta.titel == "Bonnetjes AH"
    assert meta.documentdatum == date.today()


def test_reconcile_maakt_geen_meta_voor_lege_of_speciale_mappen(archief: Archief, reconciler: Reconciler) -> None:
    for extra in ("2026/2026-01-01_leeg", "2026/_intern", "2026/.stil", "abcd/2026-01-01_x", "_prullenbak/2026-01-01_weg"):
        (archief.root / extra).mkdir(parents=True, exist_ok=True)
    for extra in ("2026/_intern", "2026/.stil", "abcd/2026-01-01_x", "_prullenbak/2026-01-01_weg"):
        (archief.root / extra / "a.pdf").write_bytes(b"x")
    (archief.inbox_dir / "b.pdf").write_bytes(b"x")

    rapport = reconciler.run()

    assert rapport.meta_aangemaakt == 0
    assert rapport.documenten == 0
    assert not list(archief.root.rglob(META_NAAM))


def test_reconcile_verdwenen_document_uit_index(archief: Archief, reconciler: Reconciler) -> None:
    doc = _doc(archief)
    reconciler.run()
    rel = archief.relatief(doc)
    assert rel in reconciler.index.docs

    archief.naar_prullenbak(doc)
    reconciler.run()

    assert rel not in reconciler.index.docs


# --- Reconciler: inbox -----------------------------------------------------


def test_inbox_stabiel_na_twee_polls(archief: Archief, reconciler: Reconciler, queue: Queue) -> None:
    (archief.inbox_dir / "WOZ_beschikking-2026.pdf").write_bytes(b"%PDF")

    assert reconciler.verwerk_inbox() == []
    assert (archief.inbox_dir / "WOZ_beschikking-2026.pdf").exists()
    assert queue.calls == []

    docs = reconciler.verwerk_inbox()

    assert len(docs) == 1
    doc = docs[0]
    assert doc.parent == archief.root / str(date.today().year)
    assert doc.name == f"{date.today():%Y-%m-%d}_woz-beschikking-2026"
    meta = lees_meta(doc)
    assert meta.titel == "WOZ beschikking 2026"
    assert meta.documentdatum == date.today()
    assert meta.bestanden == ["WOZ_beschikking-2026.pdf"]
    assert (doc / "WOZ_beschikking-2026.pdf").read_bytes() == b"%PDF"
    assert list(archief.inbox_dir.iterdir()) == []
    assert queue.calls == [(doc, "WOZ_beschikking-2026.pdf")]
    assert archief.relatief(doc) in reconciler.index.docs
    assert reconciler._inbox_groottes == {}


def test_inbox_met_tekstlezer_haalt_datum_uit_tekst(archief: Archief, queue: Queue) -> None:
    def lees(pad: Path) -> str | None:
        # korte tekst zonder naam: de titel blijft de bestandsnaam (pakket 15a)
        return "Factuurdatum: 15-06-2023\n12,50" if pad.suffix == ".pdf" else None

    reconciler = Reconciler(archief, bouw_index(archief), queue, lees_tekst=lees)
    (archief.inbox_dir / "energie.pdf").write_bytes(b"%PDF")
    (archief.inbox_dir / "bon.jpg").write_bytes(b"jpg")
    reconciler.verwerk_inbox()
    docs = reconciler.verwerk_inbox()
    assert [d.name for d in docs] == [f"{date.today():%Y-%m-%d}_bon", "2023-06-15_energie"]

    energie = lees_meta(docs[1])
    assert energie.documentdatum == date(2023, 6, 15)
    assert energie.datumbron == "tekst"
    assert energie.ocr == "done"
    assert (docs[1] / "energie.pdf.txt").read_text(encoding="utf-8").startswith("Factuurdatum")
    bon = lees_meta(docs[0])
    assert bon.datumbron == "upload"
    assert bon.ocr == "pending"  # lezen mislukt -> naar de queue, worker probeert het opnieuw
    assert queue.calls == [(docs[0], "bon.jpg")]
    assert list(archief.inbox_dir.iterdir()) == []
    assert all(archief.relatief(d) in reconciler.index.docs for d in docs)


def test_inbox_titel_en_tags_uit_tekst(archief: Archief, queue: Queue) -> None:
    """Pakket 15a: de titel komt uit de tekst (hier de rechtsvorm), het documenttype wordt een tag."""

    def lees(pad: Path) -> str | None:
        return "Eneco B.V.        Factuur\nFactuurnummer 123\nFactuurdatum: 01-02-2024\n" + "regel\n" * 30

    reconciler = Reconciler(archief, bouw_index(archief), queue, lees_tekst=lees)
    (archief.inbox_dir / "scan_0001.pdf").write_bytes(b"%PDF")
    reconciler.verwerk_inbox()
    docs = reconciler.verwerk_inbox()
    assert [d.name for d in docs] == ["2024-02-01_eneco-b-v"]
    meta = lees_meta(docs[0])
    assert meta.titel == "Eneco B.V."
    assert meta.tags == ["factuur"]
    assert meta.datumbron == "tekst"
    assert meta.bestanden == ["scan_0001.pdf"]
    assert queue.calls == []


def test_inbox_bekende_titel_uit_index_wint(archief: Archief, queue: Queue) -> None:
    _doc(archief, "Gemeente Utrecht", DATUM)

    def lees(pad: Path) -> str | None:
        return "Aanslag\nGEMEENTE UTRECHT\nBelastingen B.V.\n" + "regel\n" * 30

    reconciler = Reconciler(archief, bouw_index(archief), queue, lees_tekst=lees)
    (archief.inbox_dir / "x.pdf").write_bytes(b"%PDF")
    reconciler.verwerk_inbox()
    docs = reconciler.verwerk_inbox()
    meta = lees_meta(docs[0])
    assert meta.titel == "Gemeente Utrecht"  # de archieftitel zoals getypt, niet de hoofdletters uit de tekst
    assert meta.tags == ["aanslag"]


def test_inbox_zonder_treffer_houdt_bestandsnaam(archief: Archief, queue: Queue) -> None:
    def lees(pad: Path) -> str | None:
        return "Geachte heer,\n" + "lopende tekst zonder afzender\n" * 30

    reconciler = Reconciler(archief, bouw_index(archief), queue, lees_tekst=lees)
    (archief.inbox_dir / "brief_van-2024.pdf").write_bytes(b"%PDF")
    reconciler.verwerk_inbox()
    docs = reconciler.verwerk_inbox()
    meta = lees_meta(docs[0])
    assert meta.titel == "brief van 2024"
    assert meta.tags == []


def test_inbox_dubbel_naar_dubbelmap(archief: Archief, reconciler: Reconciler, queue: Queue) -> None:
    doc = _doc(archief, "Eneco", DATUM, "factuur.pdf")  # inhoud b"x"
    reconciler.index.herlaad(archief, doc)
    (archief.inbox_dir / "kopie.pdf").write_bytes(b"x")
    (archief.inbox_dir / "nieuw.pdf").write_bytes(b"nieuw")
    reconciler.verwerk_inbox()
    docs = reconciler.verwerk_inbox()

    assert [d.name for d in docs] == [f"{date.today():%Y-%m-%d}_nieuw"]
    assert not (archief.inbox_dir / "kopie.pdf").exists()
    assert (archief.inbox_dir / "_dubbel" / "kopie.pdf").read_bytes() == b"x"
    assert len(archief.documentmappen()) == 2
    assert queue.calls == [(docs[0], "nieuw.pdf")]
    assert reconciler._inbox_groottes == {}
    # nog een keer dezelfde naam -> tijdstempel-achtervoegsel, niets overschreven
    (archief.inbox_dir / "kopie.pdf").write_bytes(b"x")
    reconciler.verwerk_inbox()
    assert reconciler.verwerk_inbox() == []
    namen = sorted(p.name for p in (archief.inbox_dir / "_dubbel").iterdir())
    assert len(namen) == 2 and namen[0] == "kopie.pdf" and namen[1].startswith("kopie.pdf_")
    # de _dubbel-map zelf wordt niet als inboxbestand gezien
    assert reconciler.verwerk_inbox() == []


def test_inbox_groeiend_bestand_wacht(archief: Archief, reconciler: Reconciler) -> None:
    pad = archief.inbox_dir / "scan.pdf"
    pad.write_bytes(b"1")
    assert reconciler.verwerk_inbox() == []
    pad.write_bytes(b"12")
    assert reconciler.verwerk_inbox() == []
    pad.write_bytes(b"123")
    assert reconciler.verwerk_inbox() == []
    assert pad.exists()
    assert reconciler.verwerk_inbox() != []
    assert not pad.exists()


def test_inbox_docx_niet_gequeued(archief: Archief, reconciler: Reconciler, queue: Queue) -> None:
    (archief.inbox_dir / "brief.docx").write_bytes(b"x")
    reconciler.verwerk_inbox()
    docs = reconciler.verwerk_inbox()

    assert len(docs) == 1
    assert lees_meta(docs[0]).bestanden == ["brief.docx"]
    assert lees_meta(docs[0]).ocr == "done"
    assert queue.calls == []


def test_inbox_via_run_en_opruimen_groottes(archief: Archief, reconciler: Reconciler) -> None:
    pad = archief.inbox_dir / "a.pdf"
    pad.write_bytes(b"x")
    (archief.inbox_dir / ".verborgen").write_bytes(b"x")
    (archief.inbox_dir / "submap").mkdir()

    assert reconciler.run().inbox_verwerkt == 0
    assert pad in reconciler._inbox_groottes
    pad.unlink()
    assert reconciler.run().inbox_verwerkt == 0
    assert reconciler._inbox_groottes == {}
    assert (archief.inbox_dir / ".verborgen").exists()


def test_inbox_fout_blokkeert_rest_niet(archief: Archief, reconciler: Reconciler, monkeypatch: pytest.MonkeyPatch) -> None:
    (archief.inbox_dir / "kapot.pdf").write_bytes(b"x")
    (archief.inbox_dir / "goed.pdf").write_bytes(b"y")  # andere inhoud: gelijke bytes zouden een dubbel zijn (pakket 16)
    reconciler.verwerk_inbox()

    origineel = archief.voeg_bestand_toe

    def faal(doc: Path, naam: str, data: bytes) -> str:
        if naam == "kapot.pdf":
            raise OSError("schijf vol")
        return origineel(doc, naam, data)

    monkeypatch.setattr(archief, "voeg_bestand_toe", faal)
    docs = reconciler.verwerk_inbox()

    assert len(docs) == 1
    assert lees_meta(docs[0]).bestanden == ["goed.pdf"]
    assert not (archief.inbox_dir / "goed.pdf").exists()
    assert (archief.inbox_dir / "kapot.pdf").exists()
