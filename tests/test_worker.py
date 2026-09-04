from __future__ import annotations

import asyncio
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING

from ordner.config import Settings
from ordner.index import Index, ReconcileRapport
from ordner.meta import lees_meta
from ordner.storage import Archief
from ordner.worker import OcrQueue, inbox_lus, reconcile_lus

if TYPE_CHECKING:
    from tests.conftest import CmdMock


def _settings(archief: Archief, **kw: object) -> Settings:
    return Settings(data_root=archief.root, **kw)  # type: ignore[arg-type]


def _document_met_pdf(archief: Archief, naam: str = "a.pdf") -> Path:
    doc = archief.maak_document("Factuur", date(2026, 9, 3))
    archief.voeg_bestand_toe(doc, naam, b"%PDF")
    return doc


def _queue(archief: Archief, **kw: object) -> tuple[OcrQueue, Index]:
    index = Index()
    for map in archief.documentmappen():
        index.herlaad(archief, map)
    return OcrQueue(archief, index, _settings(archief, **kw)), index


def _programmas(mock: CmdMock) -> list[str]:
    return [call[0] for call in mock.calls]


# --- OcrQueue -------------------------------------------------------------


async def test_verwerkt_pdf_en_werkt_meta_en_index_bij(mock_cmd: CmdMock, archief: Archief) -> None:
    mock_cmd.register("pdfinfo", stdout=b"Pages: 1")
    mock_cmd.register("pdftotext", stdout=b"x" * 100)
    doc = _document_met_pdf(archief)
    assert lees_meta(doc).ocr == "pending"
    queue, index = _queue(archief)
    rel = archief.relatief(doc)

    queue.enqueue(doc, "a.pdf")
    assert queue.lengte == 1
    await queue.start()
    await queue._queue.join()

    assert (doc / "a.pdf.txt").read_text(encoding="utf-8") == "x" * 100
    assert lees_meta(doc).ocr == "done"
    assert index.docs[rel].meta.ocr == "done"
    assert index.docs[rel].teksten["a.pdf"] == "x" * 100
    assert queue.bezig == set()
    assert queue.lengte == 0
    assert not list(doc.glob("*.tmp"))
    await queue.stop()


async def test_extractie_mislukt_geeft_failed(mock_cmd: CmdMock, archief: Archief) -> None:
    mock_cmd.register("pdfinfo", stdout=b"Pages: 1")
    mock_cmd.register("pdftotext", rc=1)
    mock_cmd.register("ocrmypdf", rc=1, stderr=b"kapot")
    doc = _document_met_pdf(archief)
    queue, index = _queue(archief)

    queue.enqueue(doc, "a.pdf")
    await queue.start()
    await queue._queue.join()
    await queue.stop()

    assert lees_meta(doc).ocr == "failed"
    assert not (doc / "a.pdf.txt").exists()
    assert index.docs[archief.relatief(doc)].meta.ocr == "failed"
    assert queue.bezig == set()


async def test_enqueue_is_idempotent(mock_cmd: CmdMock, archief: Archief) -> None:
    mock_cmd.register("pdfinfo", stdout=b"Pages: 1")
    mock_cmd.register("pdftotext", stdout=b"x" * 100)
    doc = _document_met_pdf(archief)
    queue, _ = _queue(archief)

    queue.enqueue(doc, "a.pdf")
    queue.enqueue(doc, "a.pdf")
    assert queue.lengte == 1
    await queue.start()
    await queue._queue.join()
    await queue.stop()

    assert _programmas(mock_cmd).count("pdftotext") == 1


async def test_na_verwerking_opnieuw_enqueue_mogelijk(mock_cmd: CmdMock, archief: Archief) -> None:
    mock_cmd.register("pdfinfo", stdout=b"Pages: 1")
    mock_cmd.register("pdftotext", stdout=b"x" * 100)
    doc = _document_met_pdf(archief)
    queue, _ = _queue(archief)
    await queue.start()

    queue.enqueue(doc, "a.pdf")
    await queue._queue.join()
    queue.enqueue(doc, "a.pdf")  # bv. na "OCR opnieuw"
    await queue._queue.join()
    await queue.stop()

    assert _programmas(mock_cmd).count("pdftotext") == 2


async def test_enqueue_vanuit_andere_thread(mock_cmd: CmdMock, archief: Archief) -> None:
    mock_cmd.register("pdfinfo", stdout=b"Pages: 1")
    mock_cmd.register("pdftotext", stdout=b"x" * 100)
    doc = _document_met_pdf(archief)
    queue, _ = _queue(archief)
    await queue.start()

    await asyncio.to_thread(lambda: queue.enqueue(doc, "a.pdf"))
    await asyncio.wait_for(queue._queue.join(), timeout=5)
    await queue.stop()

    assert (doc / "a.pdf.txt").exists()
    assert lees_meta(doc).ocr == "done"


async def test_bestand_weg_voor_verwerking(mock_cmd: CmdMock, archief: Archief) -> None:
    mock_cmd.register("pdfinfo", stdout=b"Pages: 1")
    mock_cmd.register("pdftotext", stdout=b"x" * 100)
    doc = _document_met_pdf(archief)
    queue, _ = _queue(archief)

    queue.enqueue(doc, "a.pdf")
    (doc / "a.pdf").unlink()
    await queue.start()
    await queue._queue.join()
    await queue.stop()

    assert mock_cmd.calls == []
    assert queue.bezig == set()
    assert not (doc / "a.pdf.txt").exists()


async def test_map_weg_voor_verwerking(mock_cmd: CmdMock, archief: Archief) -> None:
    doc = _document_met_pdf(archief)
    queue, index = _queue(archief)
    rel = archief.relatief(doc)

    queue.enqueue(doc, "a.pdf")
    archief.naar_prullenbak(doc)
    await queue.start()
    await queue._queue.join()
    await queue.stop()

    assert mock_cmd.calls == []
    assert queue.bezig == set()
    assert rel in index.docs  # opruimen uit de index is de taak van de reconciler


async def test_meerdere_bestanden_pas_done_als_alles_klaar(mock_cmd: CmdMock, archief: Archief) -> None:
    mock_cmd.register("pdfinfo", stdout=b"Pages: 1")
    mock_cmd.register("pdftotext", stdout=b"x" * 100)
    mock_cmd.register("tesseract", stdout=b"foto")
    doc = archief.maak_document("Twee", date(2026, 1, 1))
    archief.voeg_bestand_toe(doc, "a.pdf", b"%PDF")
    archief.voeg_bestand_toe(doc, "b.png", b"")
    archief.voeg_bestand_toe(doc, "c.docx", b"")
    queue, index = _queue(archief, ocr_parallel=2)

    queue.enqueue(doc, "a.pdf")
    queue.enqueue(doc, "b.png")
    await queue.start()
    await queue._queue.join()
    await queue.stop()

    assert lees_meta(doc).ocr == "done"
    assert index.docs[archief.relatief(doc)].teksten == {"a.pdf": "x" * 100, "b.png": "foto"}


async def test_consumer_overleeft_onverwachte_fout(
    mock_cmd: CmdMock, archief: Archief, monkeypatch
) -> None:
    mock_cmd.register("pdfinfo", stdout=b"Pages: 1")
    mock_cmd.register("pdftotext", stdout=b"x" * 100)
    doc = archief.maak_document("Twee", date(2026, 1, 1))
    archief.voeg_bestand_toe(doc, "a.pdf", b"%PDF")
    archief.voeg_bestand_toe(doc, "b.pdf", b"%PDF")
    queue, _ = _queue(archief, ocr_parallel=1)

    origineel = queue._verwerk

    async def kapot(d: Path, naam: str) -> None:
        if naam == "a.pdf":
            raise RuntimeError("boem")
        await origineel(d, naam)

    monkeypatch.setattr(queue, "_verwerk", kapot)
    queue.enqueue(doc, "a.pdf")
    queue.enqueue(doc, "b.pdf")
    await queue.start()
    await asyncio.wait_for(queue._queue.join(), timeout=5)
    await queue.stop()

    assert (doc / "b.pdf.txt").exists()
    assert not queue._tasks


async def test_stop_zonder_start(archief: Archief) -> None:
    queue, _ = _queue(archief)
    await queue.stop()
    assert queue.lengte == 0


# --- lussen ---------------------------------------------------------------


class _FakeReconciler:
    def __init__(self) -> None:
        self.runs = 0
        self.inbox_polls = 0

    def run(self) -> ReconcileRapport:
        self.runs += 1
        return ReconcileRapport()

    def verwerk_inbox(self) -> list[Path]:
        self.inbox_polls += 1
        return []


async def test_reconcile_lus_draait_direct_en_stopt(archief: Archief) -> None:
    fake = _FakeReconciler()
    queue, _ = _queue(archief, reconcile_interval=1)
    stop = asyncio.Event()

    async def zet_stop() -> None:
        await asyncio.sleep(0.2)
        stop.set()

    asyncio.create_task(zet_stop())
    await asyncio.wait_for(
        reconcile_lus(fake, queue, queue.settings, stop),  # type: ignore[arg-type]
        timeout=2,
    )
    assert fake.runs >= 1


async def test_reconcile_lus_overleeft_fout(archief: Archief) -> None:
    class Kapot(_FakeReconciler):
        def run(self) -> ReconcileRapport:
            self.runs += 1
            raise RuntimeError("boem")

    fake = Kapot()
    queue, _ = _queue(archief, reconcile_interval=1)
    stop = asyncio.Event()
    asyncio.get_running_loop().call_later(0.2, stop.set)
    await asyncio.wait_for(reconcile_lus(fake, queue, queue.settings, stop), timeout=2)  # type: ignore[arg-type]
    assert fake.runs == 1


async def test_inbox_lus_pollt_na_interval(archief: Archief) -> None:
    fake = _FakeReconciler()
    queue, _ = _queue(archief, inbox_interval=1)
    stop = asyncio.Event()

    asyncio.get_running_loop().call_later(0.2, stop.set)
    await asyncio.wait_for(inbox_lus(fake, queue, queue.settings, stop), timeout=2)  # type: ignore[arg-type]
    assert fake.inbox_polls == 0  # eerste poll pas na het interval; stop kwam eerder


async def test_inbox_lus_pollt_wel_bij_lange_looptijd(archief: Archief, monkeypatch) -> None:
    fake = _FakeReconciler()
    queue, _ = _queue(archief, inbox_interval=1)
    stop = asyncio.Event()

    async def snel_wachten(evt: asyncio.Event, seconden: float) -> None:
        try:
            await asyncio.wait_for(evt.wait(), timeout=0.05)
        except asyncio.TimeoutError:
            pass

    monkeypatch.setattr("ordner.worker._wacht", snel_wachten)
    asyncio.get_running_loop().call_later(0.3, stop.set)
    await asyncio.wait_for(inbox_lus(fake, queue, queue.settings, stop), timeout=2)  # type: ignore[arg-type]
    assert fake.inbox_polls >= 2
