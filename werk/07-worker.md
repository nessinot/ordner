# Pakket 07 — Worker

> **Agent-prompt:** Lees `werk/00-contract.md` en `werk/07-worker.md`. Voer pakket 07 uit. Draai `pytest`. Commit met bericht `pakket 07: worker`. Vink af in `werk/STATUS.md`.

**Doel:** OCR-wachtrij en achtergrondlussen.

**Lees eerst:** `werk/00-contract.md` (Interface `worker.py`, `extract.py`, `index.py`).
**Vereist:** pakketten 04 en 05.

## Maakt

- `ordner/worker.py`
- `tests/test_worker.py`

## Specificatie

### `OcrQueue(archief, index, settings)`
- Intern: `self._queue: asyncio.Queue[tuple[Path, str]]`, `self._gepland: set[tuple[str, str]]` (key = `(archief.relatief(doc), naam)`), `self.bezig: set[tuple[str, str]]`, `self._tasks: list[asyncio.Task]`, `self._loop: asyncio.AbstractEventLoop | None`.
- `enqueue(doc, naam)`:
  - key berekenen; als key in `_gepland` → return (idempotent).
  - `_gepland.add(key)`.
  - Als `self._loop` gezet is en de huidige thread niet de loop-thread is (`threading.get_ident() != self._loop_thread_id`): `self._loop.call_soon_threadsafe(self._queue.put_nowait, (doc, naam))`; anders `self._queue.put_nowait(...)`.
  - Vóór `start()` mag `enqueue` ook al: items gaan gewoon in de queue (die is bij `__init__` aangemaakt; maak hem aan zonder loop-argument, dat is in Python ≥ 3.10 toegestaan).
- `start()`: `self._loop = asyncio.get_running_loop()`, `self._loop_thread_id = threading.get_ident()`; maak `settings.ocr_parallel` tasks met `asyncio.create_task(self._consumer())`.
- `stop()`: cancel alle tasks, `await asyncio.gather(*tasks, return_exceptions=True)`.
- `lengte`: `self._queue.qsize()`.
- `_consumer()`: `while True: doc, naam = await self._queue.get(); try: await self._verwerk(doc, naam) finally: self._queue.task_done()`.
- `_verwerk(doc, naam)`:
  1. `key = (archief.relatief(doc), naam)`; `bezig.add(key)`.
  2. `pad = doc / naam`; als `doc / META_NAAM` of `pad` niet bestaat → log en klaar (finally-blok ruimt op).
  3. `try: tekst = await extract_bestand(pad, settings.ocr_talen)`; schrijf `txt_pad(pad)` atomic (`.tmp` + `os.replace`, utf-8); `meta = lees_meta(doc)`; `meta.ocr = bepaal_ocr_status(doc, meta)`; `schrijf_meta`.
  4. `except ExtractieFout as e`: `log.warning(...)`; `meta = lees_meta(doc)`; `meta.ocr = "failed"`; `schrijf_meta`.
  5. `finally`: `index.herlaad(archief, doc)` (in `try/except MetaFout` — map kan intussen weg zijn); `bezig.discard(key)`; `_gepland.discard(key)`.
  - Onverwachte exceptions loggen met `log.exception` en niet laten escaleren (de consumer moet blijven draaien).

### `reconcile_lus(reconciler, queue, settings, stop)`
```
while not stop.is_set():
    try: rapport = await asyncio.to_thread(reconciler.run); log.info(rapport)
    except Exception: log.exception("reconcile mislukt")
    try: await asyncio.wait_for(stop.wait(), timeout=settings.reconcile_interval)
    except asyncio.TimeoutError: pass
```
(De eerste run gebeurt dus direct bij start.)

### `inbox_lus(reconciler, queue, settings, stop)`
Zelfde patroon met `reconciler.verwerk_inbox` en `settings.inbox_interval`; eerste poll na `inbox_interval` s (niet direct — de reconcile-lus doet de eerste inbox-verwerking al).

## Tests (asyncio, `mock_cmd`, `archief`)

- Document met `a.pdf`; `mock_cmd.register("pdfinfo", stdout=b"Pages: 1")`, `mock_cmd.register("pdftotext", stdout=b"x"*100)`; `queue.enqueue(doc, "a.pdf")`; `await queue.start()`; `await queue._queue.join()`; → `a.pdf.txt` bestaat met de tekst, `meta.ocr == "done"`, `index.docs[rel].teksten["a.pdf"]` gevuld, `bezig` leeg. `await queue.stop()`.
- `pdftotext` rc 1 en `ocrmypdf` rc 1 → `meta.ocr == "failed"`, geen `.txt`.
- Twee keer `enqueue` van hetzelfde bestand → `mock_cmd.calls` bevat `pdftotext` precies één keer.
- `enqueue` vanuit `await asyncio.to_thread(lambda: queue.enqueue(doc, "a.pdf"))` nadat `start()` is aangeroepen → wordt verwerkt.
- Bestand verwijderd vóór verwerking → geen exception, `bezig` leeg.
- `reconcile_lus` met `reconcile_interval=1` en een `stop`-event dat na 0.2 s gezet wordt → lus eindigt binnen 2 s en `reconciler.run` is minstens één keer aangeroepen (gebruik een fake reconciler met een teller).

## Buiten scope

Web (08).
