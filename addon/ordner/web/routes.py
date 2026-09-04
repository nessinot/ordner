"""Routes van de webapp (pakket 08: zoeken, upload, bestand-serving; pakket 09: document, beheer, status)."""

from __future__ import annotations

import asyncio
import logging
import mimetypes
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from ordner.index import DocEntry, Index, Reconciler
from ordner.ingest import LeesTekst, maak_document_uit_bestanden
from ordner.meta import MetaFout, OcrStatus, is_extraheerbaar, schrijf_meta, txt_pad
from ordner.search import zoek
from ordner.storage import Archief, OngeldigPad
from ordner.worker import OcrQueue

log = logging.getLogger(__name__)

router = APIRouter()

_RECENT = 20  # startscherm zonder zoekterm: de nieuwste N documenten
_MAX_TREFFERS = 50  # zoekresultaten worden hierop afgekapt, tenzij ?alles=1


@dataclass
class Kaart:
    """Eén regel in de resultatenlijst; gedeelde vorm voor 'Recent' en zoekresultaten."""

    jaar: str
    map: str
    titel: str
    documentdatum: date
    omschrijving: str
    ocr: OcrStatus
    snippet: str = ""
    bron: str = ""
    soort: str = "overig"  # "pdf", "afbeelding" of "overig": bepaalt het icoon in de lijst


def _kaart_soort(bestanden: list[str]) -> str:
    """Soort van het eerste bestand; "overig" als er geen bestanden zijn."""
    for naam in bestanden[:1]:
        ext = Path(naam).suffix.lower()
        return "afbeelding" if ext in _INLINE_AFBEELDING else "pdf" if ext == ".pdf" else "overig"
    return "overig"


def _splits_rel(rel: str) -> tuple[str, str]:
    jaar, _, map = rel.partition("/")
    return jaar, map


def _templates(request: Request) -> Jinja2Templates:
    return request.app.state.templates


def _archief(request: Request) -> Archief:
    return request.app.state.archief


def _index(request: Request) -> Index:
    return request.app.state.index


def _queue(request: Request) -> OcrQueue:
    return request.app.state.queue


def _lees_tekst(request: Request) -> LeesTekst | None:
    return getattr(request.app.state, "lees_tekst", None)


def _redirect(
    request: Request,
    naam: str,
    melding: str | None = None,
    /,
    query: dict[str, str] | None = None,
    **path_params: str,
) -> RedirectResponse:
    """303-redirect via url_for (Ingress-prefix); pad zonder scheme/host. `query` (bv. de zoekopdracht) gaat mee."""
    url = request.url_for(naam, **path_params)
    if query:
        url = url.include_query_params(**{k: v for k, v in query.items() if v})
    if melding:
        url = url.include_query_params(m=melding)
    doel = url.path + (f"?{url.query}" if url.query else "")
    return RedirectResponse(doel, status_code=303)


def _entry(request: Request, jaar: str, map: str) -> DocEntry:
    """DocEntry voor een documentmap; 404 bij onveilig/onbestaand pad of ongeldige meta.md."""
    archief = _archief(request)
    try:
        pad = archief.veilig_pad(jaar, map)
    except OngeldigPad:
        raise HTTPException(status_code=404, detail="Document niet gevonden") from None
    index = _index(request)
    rel = archief.relatief(pad)
    entry = index.docs.get(rel)
    if entry is None:
        try:
            entry = index.herlaad(archief, pad)
        except MetaFout:
            raise HTTPException(status_code=404, detail="Document niet gevonden") from None
    return entry


# --- zoeken ---------------------------------------------------------------


@router.get("/", name="zoeken")
async def zoeken(request: Request) -> Response:
    index = _index(request)
    q = request.query_params.get("q", "").strip()
    alles = request.query_params.get("alles") == "1"
    kaarten: list[Kaart] = []
    totaal = 0  # aantal treffers vóór afkappen (zoeken) of documenten in het archief (recent)
    if q:
        treffers = zoek(index, q)
        totaal = len(treffers)
        if not alles:
            treffers = treffers[:_MAX_TREFFERS]
        for t in treffers:
            jaar, map = _splits_rel(t.rel)
            entry = index.docs.get(t.rel)
            ocr: OcrStatus = entry.meta.ocr if entry else "done"
            soort = _kaart_soort(entry.meta.bestanden) if entry else "overig"
            kaarten.append(
                Kaart(jaar, map, t.titel, t.documentdatum, t.omschrijving, ocr, t.snippet, t.bron, soort)
            )
    else:
        docs = index.alle()
        totaal = len(docs)
        for entry in docs[:_RECENT]:
            jaar, map = _splits_rel(entry.rel)
            m = entry.meta
            kaarten.append(Kaart(jaar, map, m.titel, m.documentdatum, m.omschrijving, m.ocr, soort=_kaart_soort(m.bestanden)))
    return _templates(request).TemplateResponse(
        request,
        "zoeken.html",
        {
            "q": q,
            "alles": alles,
            "kaarten": kaarten,
            "totaal": totaal,
            "afgekapt": len(kaarten) < totaal,
            "tellingen": index.tellingen(),
        },
    )


# --- upload ---------------------------------------------------------------


def _upload_context(**velden: str) -> dict[str, str]:
    ctx = {"titel": "", "omschrijving": "", "documentdatum": "", "tags": "", "fout": ""}
    ctx.update(velden)
    return ctx


@router.get("/upload", name="upload")
async def upload_formulier(request: Request) -> Response:
    return _templates(request).TemplateResponse(request, "upload.html", _upload_context())


@router.post("/upload")
async def upload(
    request: Request,
    bestanden: list[UploadFile] = File(default=[]),
    titel: str = Form(""),
    omschrijving: str = Form(""),
    documentdatum: str = Form(""),
    tags: str = Form(""),
) -> Response:
    titel = titel.strip()
    omschrijving = omschrijving.strip()
    documentdatum = documentdatum.strip()
    ingevuld = dict(titel=titel, omschrijving=omschrijving, documentdatum=documentdatum, tags=tags)

    def fout(melding: str) -> Response:
        ctx = _upload_context(**ingevuld, fout=melding)
        return _templates(request).TemplateResponse(request, "upload.html", ctx, status_code=400)

    if not titel:
        return fout("Titel is verplicht.")
    datum: date | None = None
    if documentdatum:
        try:
            datum = date.fromisoformat(documentdatum)
        except ValueError:
            return fout("Ongeldige documentdatum; gebruik JJJJ-MM-DD.")
    taglijst = _splits_tags(tags)

    archief = _archief(request)
    uploads = [(f.filename, await f.read()) for f in bestanden if f.filename]
    # Zonder datum wordt de tekst eerst gelezen (OCR kan tientallen seconden duren): in een thread,
    # zodat de event loop en de status-polls van andere pagina's niet blokkeren.
    doc = await asyncio.to_thread(
        maak_document_uit_bestanden,
        archief,
        titel,
        uploads,
        documentdatum=datum,
        omschrijving=omschrijving,
        tags=taglijst,
        lees_tekst=_lees_tekst(request),
        queue_fn=_queue(request).enqueue,
    )
    _index(request).herlaad(archief, doc)
    log.info("upload: %s (%d bestand(en))", archief.relatief(doc), len(uploads))

    jaar, map = _splits_rel(archief.relatief(doc))
    return _redirect(request, "document", "Opgeslagen", jaar=jaar, map=map)


def _splits_tags(tags: str) -> list[str]:
    return [t.strip() for t in tags.split(",") if t.strip()]


def _sla_bestanden_op(
    archief: Archief, queue: OcrQueue, doc: Path, uploads: list[tuple[str | None, bytes]]
) -> int:
    """Schrijft uploads naar de documentmap en queued extraheerbare bestanden; geeft het aantal terug."""
    aantal = 0
    for bestandsnaam, data in uploads:
        if not bestandsnaam:
            continue
        naam = archief.voeg_bestand_toe(doc, bestandsnaam, data)
        aantal += 1
        if is_extraheerbaar(naam):
            queue.enqueue(doc, naam)
    return aantal


# --- document -------------------------------------------------------------

_INLINE_AFBEELDING = {".jpg", ".jpeg", ".png"}


@dataclass
class Bestandsweergave:
    """Eén bestand op de documentpagina: hoe het inline getoond wordt en of er OCR-tekst is."""

    naam: str
    soort: str  # "afbeelding", "pdf" of "overig"
    tekst_aanwezig: bool


def _bestandsweergaven(entry: DocEntry) -> list[Bestandsweergave]:
    weergaven: list[Bestandsweergave] = []
    for naam in entry.meta.bestanden:
        ext = Path(naam).suffix.lower()
        soort = "afbeelding" if ext in _INLINE_AFBEELDING else "pdf" if ext == ".pdf" else "overig"
        weergaven.append(Bestandsweergave(naam, soort, txt_pad(entry.map / naam).exists()))
    return weergaven


def _herkomst(q: str, alles: str) -> dict[str, str]:
    """Zoekopdracht waarmee de gebruiker bij het document kwam; reist mee in URL's en formulieren voor de terugknop."""
    q = q.strip()
    return {"q": q, "alles": "1" if q and alles == "1" else ""}


def _document_pagina(
    request: Request,
    entry: DocEntry,
    jaar: str,
    map: str,
    fout: str = "",
    status_code: int = 200,
    herkomst: dict[str, str] | None = None,
) -> Response:
    ctx = {
        "entry": entry,
        "meta": entry.meta,
        "rel": entry.rel,
        "jaar": jaar,
        "map": map,
        "bestanden": _bestandsweergaven(entry),
        "fout": fout,
        "herkomst": herkomst or _herkomst("", ""),
    }
    return _templates(request).TemplateResponse(request, "document.html", ctx, status_code=status_code)


@router.get("/doc/{jaar}/{map}", name="document")
async def document(request: Request, jaar: str, map: str) -> Response:
    entry = _entry(request, jaar, map)
    herkomst = _herkomst(request.query_params.get("q", ""), request.query_params.get("alles", ""))
    return _document_pagina(request, entry, jaar, map, herkomst=herkomst)


@router.post("/doc/{jaar}/{map}/meta", name="document_meta")
async def document_meta(
    request: Request,
    jaar: str,
    map: str,
    titel: str = Form(""),
    omschrijving: str = Form(""),
    documentdatum: str = Form(""),
    tags: str = Form(""),
    q: str = Form(""),
    alles: str = Form(""),
) -> Response:
    entry = _entry(request, jaar, map)
    herkomst = _herkomst(q, alles)
    titel = titel.strip()
    if not titel:
        return _document_pagina(
            request, entry, jaar, map, fout="Titel is verplicht.", status_code=400, herkomst=herkomst
        )
    try:
        datum = date.fromisoformat(documentdatum.strip())
    except ValueError:
        fout = "Ongeldige documentdatum; gebruik JJJJ-MM-DD."
        return _document_pagina(request, entry, jaar, map, fout=fout, status_code=400, herkomst=herkomst)
    meta = entry.meta
    meta.titel = titel
    meta.omschrijving = omschrijving.strip()
    if datum != meta.documentdatum:
        meta.datumbron = "gebruiker"  # een bewust gewijzigde datum wordt nooit meer automatisch overschreven
    meta.documentdatum = datum
    meta.tags = _splits_tags(tags)
    schrijf_meta(entry.map, meta)  # de map wordt nooit hernoemd
    _index(request).herlaad(_archief(request), entry.map)
    log.info("meta bijgewerkt: %s", entry.rel)
    return _redirect(request, "document", "Opgeslagen", query=herkomst, jaar=jaar, map=map)


@router.post("/doc/{jaar}/{map}/bestanden", name="document_bestanden")
async def document_bestanden(
    request: Request,
    jaar: str,
    map: str,
    bestanden: list[UploadFile] = File(default=[]),
    q: str = Form(""),
    alles: str = Form(""),
) -> Response:
    entry = _entry(request, jaar, map)
    archief = _archief(request)
    uploads = [(f.filename, await f.read()) for f in bestanden]
    aantal = _sla_bestanden_op(archief, _queue(request), entry.map, uploads)
    _index(request).herlaad(archief, entry.map)
    log.info("bestanden toegevoegd aan %s: %d", entry.rel, aantal)
    return _redirect(request, "document", "Toegevoegd", query=_herkomst(q, alles), jaar=jaar, map=map)


@router.post("/doc/{jaar}/{map}/ocr", name="document_ocr")
async def document_ocr(
    request: Request, jaar: str, map: str, q: str = Form(""), alles: str = Form("")
) -> Response:
    entry = _entry(request, jaar, map)
    queue = _queue(request)
    meta = entry.meta
    extraheerbaar = [naam for naam in meta.bestanden if is_extraheerbaar(naam)]
    for naam in extraheerbaar:
        txt = txt_pad(entry.map / naam)
        if txt.exists():
            txt.unlink()
    meta.ocr = "pending" if extraheerbaar else "done"
    schrijf_meta(entry.map, meta)
    for naam in extraheerbaar:
        queue.enqueue(entry.map, naam)
    _index(request).herlaad(_archief(request), entry.map)
    log.info("OCR opnieuw gestart voor %s (%d bestand(en))", entry.rel, len(extraheerbaar))
    return _redirect(request, "document", "OCR gestart", query=_herkomst(q, alles), jaar=jaar, map=map)


@router.post("/doc/{jaar}/{map}/verwijder", name="document_verwijder")
async def document_verwijder(
    request: Request, jaar: str, map: str, q: str = Form(""), alles: str = Form("")
) -> Response:
    entry = _entry(request, jaar, map)
    archief = _archief(request)
    rel = archief.relatief(entry.map)
    archief.naar_prullenbak(entry.map)
    _index(request).verwijder(rel)
    return _redirect(request, "zoeken", "Verplaatst naar prullenbak", query=_herkomst(q, alles))


@router.get("/doc/{jaar}/{map}/bestand/{naam}", name="bestand")
async def bestand(request: Request, jaar: str, map: str, naam: str) -> Response:
    try:
        pad = _archief(request).veilig_pad(jaar, map, naam)
    except OngeldigPad:
        raise HTTPException(status_code=404, detail="Bestand niet gevonden") from None
    if not pad.is_file():
        raise HTTPException(status_code=404, detail="Bestand niet gevonden")
    return FileResponse(
        pad,
        media_type=mimetypes.guess_type(naam)[0] or "application/octet-stream",
        content_disposition_type="inline",
        filename=naam,
    )


# --- status-API -----------------------------------------------------------


@router.get("/api/status", name="status")
async def status(request: Request) -> Response:
    index = _index(request)
    queue = _queue(request)
    data: dict[str, object] = {
        "queue": queue.lengte,
        "bezig": sorted(queue.bezig),
        "reconcile_bezig": bool(request.app.state.reconcile_bezig),
        "tellingen": index.tellingen(),
    }
    rel = request.query_params.get("rel")
    if rel is not None:
        entry = index.docs.get(rel)
        data["ocr"] = entry.meta.ocr if entry else None
    return JSONResponse(data)


# --- beheer ---------------------------------------------------------------


@router.get("/beheer", name="beheer")
async def beheer(request: Request) -> Response:
    index = _index(request)
    queue = _queue(request)
    settings = request.app.state.settings
    ctx = {
        "tellingen": index.tellingen(),
        "queue": queue.lengte,
        "bezig": sorted(queue.bezig),
        "reconcile_bezig": bool(request.app.state.reconcile_bezig),
        "rapport": request.app.state.laatste_rapport,
        "interval_minuten": max(1, round(settings.reconcile_interval / 60)),
    }
    return _templates(request).TemplateResponse(request, "beheer.html", ctx)


@router.post("/beheer/reconcile", name="beheer_reconcile")
async def beheer_reconcile(request: Request) -> Response:
    app = request.app
    if app.state.reconcile_bezig:
        return _redirect(request, "beheer", "Al bezig")
    reconciler: Reconciler = app.state.reconciler
    app.state.reconcile_bezig = True

    async def _run() -> None:
        try:
            app.state.laatste_rapport = await asyncio.to_thread(reconciler.run)
        except Exception:  # noqa: BLE001 - fout loggen; de app blijft draaien
            log.exception("handmatige reconcile mislukt")
        finally:
            app.state.reconcile_bezig = False

    # Referentie bewaren zodat de task niet weggegarbaged wordt.
    app.state.reconcile_task = asyncio.create_task(_run(), name="reconcile-handmatig")
    return _redirect(request, "beheer", "Gestart")
