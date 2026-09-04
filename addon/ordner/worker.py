"""OCR-queue en achtergrondlussen (pakket 07)."""

from __future__ import annotations

import asyncio
import logging
import os
import threading
from pathlib import Path

from ordner.config import META_NAAM, Settings
from ordner.extract import ExtractieFout, extract_bestand
from ordner.index import Index, Reconciler
from ordner.meta import MetaFout, bepaal_ocr_status, lees_meta, schrijf_meta, txt_pad
from ordner.storage import Archief

log = logging.getLogger(__name__)

Key = tuple[str, str]  # (rel, naam)


def _schrijf_txt(pad: Path, tekst: str) -> None:
    """Schrijft OCR-tekst atomic via een tempbestand in dezelfde map."""
    doel = txt_pad(pad)
    tmp = doel.with_name("." + doel.name + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(tekst)
    os.replace(tmp, doel)


class OcrQueue:
    """Wachtrij van (documentmap, bestandsnaam) die door `ocr_parallel` consumers wordt verwerkt."""

    def __init__(self, archief: Archief, index: Index, settings: Settings) -> None:
        self.archief = archief
        self.index = index
        self.settings = settings
        self._queue: asyncio.Queue[tuple[Path, str]] = asyncio.Queue()
        self._gepland: set[Key] = set()
        self.bezig: set[Key] = set()
        self._tasks: list[asyncio.Task[None]] = []
        self._loop: asyncio.AbstractEventLoop | None = None
        self._loop_thread_id: int | None = None

    def _key(self, doc: Path, naam: str) -> Key:
        return (self.archief.relatief(doc), naam)

    def enqueue(self, doc: Path, naam: str) -> None:
        """Idempotent; veilig aan te roepen vanuit een andere thread (asyncio.to_thread)."""
        key = self._key(doc, naam)
        if key in self._gepland:
            return
        self._gepland.add(key)
        item = (doc, naam)
        if self._loop is not None and threading.get_ident() != self._loop_thread_id:
            self._loop.call_soon_threadsafe(self._queue.put_nowait, item)
        else:
            self._queue.put_nowait(item)

    async def start(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._loop_thread_id = threading.get_ident()
        aantal = max(1, self.settings.ocr_parallel)
        self._tasks = [asyncio.create_task(self._consumer(), name=f"ocr-{i}") for i in range(aantal)]
        log.info("OCR-queue gestart met %d consumer(s)", aantal)

    async def stop(self) -> None:
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks = []

    @property
    def lengte(self) -> int:
        return self._queue.qsize()

    async def _consumer(self) -> None:
        while True:
            doc, naam = await self._queue.get()
            try:
                await self._verwerk(doc, naam)
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001 - de consumer moet blijven draaien
                log.exception("onverwachte fout bij OCR van %s/%s", doc, naam)
            finally:
                self._queue.task_done()

    async def _verwerk(self, doc: Path, naam: str) -> None:
        key = self._key(doc, naam)
        self.bezig.add(key)
        try:
            pad = doc / naam
            if not (doc / META_NAAM).exists() or not pad.exists():
                log.info("OCR overgeslagen, bestand of meta.md weg: %s/%s", key[0], naam)
                return
            try:
                tekst = await extract_bestand(pad, self.settings.ocr_talen)
                _schrijf_txt(pad, tekst)
                meta = lees_meta(doc)
                meta.ocr = bepaal_ocr_status(doc, meta)
                schrijf_meta(doc, meta)
                log.info("OCR klaar: %s/%s (%d tekens)", key[0], naam, len(tekst))
            except ExtractieFout as e:
                log.warning("OCR mislukt voor %s/%s: %s", key[0], naam, e)
                meta = lees_meta(doc)
                meta.ocr = "failed"
                schrijf_meta(doc, meta)
        finally:
            try:
                self.index.herlaad(self.archief, doc)
            except MetaFout as e:
                log.warning("index niet herladen voor %s: %s", key[0], e)
            self.bezig.discard(key)
            self._gepland.discard(key)


async def _wacht(stop: asyncio.Event, seconden: float) -> None:
    try:
        await asyncio.wait_for(stop.wait(), timeout=seconden)
    except asyncio.TimeoutError:
        pass


async def reconcile_lus(
    reconciler: Reconciler, queue: OcrQueue, settings: Settings, stop: asyncio.Event
) -> None:
    """Draait de reconciler direct bij start en daarna elke `reconcile_interval` s."""
    while not stop.is_set():
        try:
            rapport = await asyncio.to_thread(reconciler.run)
            log.info("reconcile klaar: %s (queue: %d)", rapport, queue.lengte)
        except Exception:  # noqa: BLE001 - de lus moet blijven draaien
            log.exception("reconcile mislukt")
        await _wacht(stop, settings.reconcile_interval)


async def inbox_lus(
    reconciler: Reconciler, queue: OcrQueue, settings: Settings, stop: asyncio.Event
) -> None:
    """Pollt de inbox elke `inbox_interval` s; de eerste poll pas na het interval."""
    while not stop.is_set():
        await _wacht(stop, settings.inbox_interval)
        if stop.is_set():
            break
        try:
            aangemaakt = await asyncio.to_thread(reconciler.verwerk_inbox)
            if aangemaakt:
                log.info("inbox: %d document(en) aangemaakt (queue: %d)", len(aangemaakt), queue.lengte)
        except Exception:  # noqa: BLE001 - de lus moet blijven draaien
            log.exception("inbox verwerken mislukt")
