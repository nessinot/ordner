"""Routes van de webapp (pakket 08: zoeken, upload, bestand-serving; pakket 09: document, beheer, status; pakket 15b: tweestaps upload; pakket 16: dubbele bestanden; pakket 17: inbox wacht op een titel; pakket 18: beheertellers; pakket 19: prullenbak kijken en legen; pakket 20: prullenbak kijken in een document en terugzetten)."""

from __future__ import annotations

import asyncio
import logging
import mimetypes
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from starlette.datastructures import URL

from ordner.dubbel import Dubbel, sha256_van, sha256_van_bestand, zoek_dubbelen, zoek_dubbelen_van_hashes
from ordner.index import DocEntry, Index, Reconciler
from ordner.ingest import LeesTekst, Voorbereid, lees_vooraf, maak_document_uit_voorbereid
from ordner.meta import MetaFout, OcrStatus, is_extraheerbaar, schrijf_meta, txt_pad
from ordner.search import zoek
from ordner.storage import Archief, OngeldigPad, PrullenbakDocument, PrullenbakItem
from ordner.suggestie import Suggestie, stel_voor
from ordner.web.openstaand import OpenstaandeUpload, OpenstaandeUploads
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
    tags: list[str] = field(default_factory=list)  # klikbare labels, volgorde zoals in meta.md (pakket 15c)


def _soort(naam: str) -> str:
    """Weergavesoort van een bestand: "afbeelding" (jpg/png), "pdf" of "overig"."""
    ext = Path(naam).suffix.lower()
    return "afbeelding" if ext in _INLINE_AFBEELDING else "pdf" if ext == ".pdf" else "overig"


def _kaart_soort(bestanden: list[str]) -> str:
    """Soort van het eerste bestand; "overig" als er geen bestanden zijn."""
    return _soort(bestanden[0]) if bestanden else "overig"


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


def _reconciler(request: Request) -> Reconciler:
    return request.app.state.reconciler


def _redirect(
    request: Request,
    naam: str,
    melding: str | None = None,
    /,
    query: dict[str, str] | None = None,
    ongedaan: str | None = None,
    **path_params: str,
) -> RedirectResponse:
    """303-redirect via url_for (Ingress-prefix); pad zonder scheme/host. `query` (bv. de zoekopdracht) gaat mee.

    `ongedaan` is de prullenbaknaam waarmee de melding een knop Ongedaan maken krijgt (pakket 20).
    """
    url = request.url_for(naam, **path_params)
    if query:
        url = url.include_query_params(**{k: v for k, v in query.items() if v})
    if melding:
        url = url.include_query_params(m=melding)
    if ongedaan:
        url = url.include_query_params(ongedaan=ongedaan)
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
            tags = list(entry.meta.tags) if entry else []
            kaarten.append(
                Kaart(jaar, map, t.titel, t.documentdatum, t.omschrijving, ocr, t.snippet, t.bron, soort, tags)
            )
    else:
        docs = index.alle()
        totaal = len(docs)
        for entry in docs[:_RECENT]:
            jaar, map = _splits_rel(entry.rel)
            m = entry.meta
            kaarten.append(
                Kaart(jaar, map, m.titel, m.documentdatum, m.omschrijving, m.ocr, soort=_kaart_soort(m.bestanden), tags=list(m.tags))
            )
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
            # startpagina (zonder zoekterm): regel met het aantal inboxbestanden dat op een titel wacht (pakket 17)
            "inbox_wachtend": 0 if q else _reconciler(request).inbox_telling().wachtend,
        },
    )


# --- upload ---------------------------------------------------------------


_TOKEN_RE = re.compile(r"[A-Za-z0-9_-]{8,64}")
_UPLOAD_VERLOPEN = "Deze upload is verlopen; kies de bestanden opnieuw."
_DUBBEL_FOUT = "Niet opgeslagen: een bestand staat al in het archief."


def _openstaand(request: Request) -> OpenstaandeUploads:
    return request.app.state.openstaand


def _grootte(aantal: int) -> str:
    """Leesbare bestandsgrootte voor de bestandslijst op scherm 2 ("12 kB", "3,4 MB")."""
    if aantal < 1000:
        return f"{aantal} B"
    if aantal < 1_000_000:
        return f"{aantal / 1000:.0f} kB"
    return f"{aantal / 1_000_000:.1f}".replace(".", ",") + " MB"


@dataclass
class UploadBestand:
    """Eén bestand in de (niet wijzigbare) bestandslijst op scherm 2."""

    naam: str
    grootte: str


def _gegevens_context(upload: OpenstaandeUpload, fout: str = "", **velden: str) -> dict[str, object]:
    """Context voor scherm 2: bestandslijst en de voorgevulde velden; `velden` overschrijft de suggestie (bij 400)."""
    vb, sug = upload.voorbereid, upload.suggestie
    ctx: dict[str, object] = {
        "token": upload.token,
        "bestanden": [UploadBestand(naam, _grootte(len(data))) for naam, data in vb.bestanden],
        "titel": sug.titel,
        "omschrijving": "",
        "documentdatum": vb.documentdatum.isoformat(),
        "tags": ", ".join(sug.tags),
        "datumbron": vb.datumbron,
        "titelbron": sug.titelbron,
        "inbox_naam": upload.inbox_naam,  # pakket 17: herkomst en knoptekst op scherm 2
        "fout": fout,
    }
    ctx.update(velden)
    return ctx


def _haal_openstaand(request: Request, token: str) -> OpenstaandeUpload | None:
    """De openstaande upload bij `token`; 404 bij een misvormd token, None als onbekend of verlopen."""
    if not _TOKEN_RE.fullmatch(token):
        raise HTTPException(status_code=404, detail="Upload niet gevonden")
    return _openstaand(request).haal(token)


@router.get("/upload", name="upload")
async def upload_formulier(request: Request) -> Response:
    """Scherm 1: alleen bestanden kiezen."""
    return _templates(request).TemplateResponse(request, "upload.html", {"fout": ""})


@router.post("/upload")
async def upload(request: Request, bestanden: list[UploadFile] = File(default=[])) -> Response:
    """Scherm 1 ingezonden: tekst lezen, datum en suggesties bepalen, openstaande upload klaarzetten, door naar scherm 2.

    Er komt niets op schijf: geen map in het archief, niets in `_inbox/`. Andere formuliervelden
    (titel, datum, ...) worden genegeerd; die horen bij scherm 2.
    """
    uploads = [(f.filename, await f.read()) for f in bestanden if f.filename]
    if not uploads:
        ctx = {"fout": "Kies minstens één bestand."}
        return _templates(request).TemplateResponse(request, "upload.html", ctx, status_code=400)
    dubbelen = zoek_dubbelen(_index(request), uploads)
    if dubbelen:
        # Vóór het lezen van de tekst (pakket 16): hashen kost niets, OCR seconden. Niets komt op schijf
        # en er ontstaat geen openstaande upload; de hele upload wordt geweigerd, ook bij één dubbel.
        _log_dubbelen("upload geweigerd", dubbelen)
        ctx = {"fout": _DUBBEL_FOUT, "dubbelen": dubbelen}
        return _templates(request).TemplateResponse(request, "upload.html", ctx, status_code=409)

    bekende_titels = {e.meta.titel for e in _index(request).alle()}
    lees_tekst = _lees_tekst(request)

    def lees_en_stel_voor() -> tuple[Voorbereid, Suggestie]:
        vb = lees_vooraf(uploads, documentdatum=None, lees_tekst=lees_tekst)
        return vb, stel_voor(vb.tekst, bekende_titels)

    # Tekst lezen kan tientallen seconden duren (OCR): in een thread, zodat de event loop en de
    # status-polls van andere pagina's niet blokkeren. De store wordt alleen op de event loop aangeraakt.
    vb, sug = await asyncio.to_thread(lees_en_stel_voor)
    openstaand = _openstaand(request).maak(vb, sug)
    log.info(
        "upload ontvangen: %d bestand(en), datum %s (%s), titel %r (%s), tags %s; token %s",
        len(uploads), vb.documentdatum, vb.datumbron, sug.titel, sug.titelbron, sug.tags, openstaand.token,
    )
    return _redirect(request, "upload_gegevens", token=openstaand.token)


@router.get("/upload/{token}", name="upload_gegevens")
async def upload_gegevens(request: Request, token: str) -> Response:
    """Scherm 2: alle velden voorgevuld."""
    upload = _haal_openstaand(request, token)
    if upload is None:
        return _redirect(request, "upload", _UPLOAD_VERLOPEN)
    return _templates(request).TemplateResponse(request, "upload_gegevens.html", _gegevens_context(upload))


@router.post("/upload/{token}")
async def upload_opslaan(
    request: Request,
    token: str,
    titel: str = Form(""),
    omschrijving: str = Form(""),
    documentdatum: str = Form(""),
    tags: str = Form(""),
) -> Response:
    """Scherm 2 ingezonden: valideren, document aanmaken, openstaande upload weggooien."""
    upload = _haal_openstaand(request, token)
    if upload is None:
        return _redirect(request, "upload", _UPLOAD_VERLOPEN)
    titel = titel.strip()
    omschrijving = omschrijving.strip()
    documentdatum = documentdatum.strip()
    ingevuld = dict(titel=titel, omschrijving=omschrijving, documentdatum=documentdatum, tags=tags)

    def fout(melding: str) -> Response:
        ctx = _gegevens_context(upload, melding, **ingevuld)
        return _templates(request).TemplateResponse(request, "upload_gegevens.html", ctx, status_code=400)

    if not titel:
        return fout("Titel is verplicht.")
    try:
        datum = date.fromisoformat(documentdatum)
    except ValueError:
        return fout("Ongeldige documentdatum; gebruik JJJJ-MM-DD.")

    archief = _archief(request)
    vb = upload.voorbereid
    if upload.inbox_naam is not None:
        onderschept = _inbox_controle(request, upload)
        if onderschept is not None:
            return onderschept
    # Ongewijzigde datum: bron uit lees_vooraf (tekst/upload). Gewijzigd: bron gebruiker.
    gewijzigde_datum = None if datum == vb.documentdatum else datum
    # Eerst uit de store, dan pas aanmaken: een tweede verzoek met hetzelfde token (dubbelklik, twee tabs)
    # vindt niets meer en kan geen tweede document maken.
    _openstaand(request).verwijder(token)
    doc = await asyncio.to_thread(
        maak_document_uit_voorbereid,
        archief,
        titel,
        vb,
        omschrijving=omschrijving,
        tags=_splits_tags(tags),
        queue_fn=_queue(request).enqueue,
        documentdatum=gewijzigde_datum,
    )
    _index(request).herlaad(archief, doc)
    if upload.inbox_naam is not None:
        # Pas ná index.herlaad: de hash van het nieuwe document is dan bekend, zodat een poll die het
        # inboxbestand nu nog zou zien het als dubbel behandelt en nooit een tweede document maakt.
        _reconciler(request).verwijder_uit_inbox(upload.inbox_naam)
        log.info("inbox: %s via de inboxpagina opgenomen als %s", upload.inbox_naam, archief.relatief(doc))
    else:
        log.info("upload opgeslagen: %s (%d bestand(en))", archief.relatief(doc), len(vb.bestanden))

    jaar, map = _splits_rel(archief.relatief(doc))
    return _redirect(request, "document", "Opgeslagen", jaar=jaar, map=map)


def _inbox_controle(request: Request, upload: OpenstaandeUpload) -> Response | None:
    """Vóór het opslaan van een inboxbestand (pakket 17): is het intussen al opgenomen of verdwenen?

    De poll heeft het bestand tussen Opnemen en Opslaan normaal niet aangeraakt (reservering), maar
    de gebruiker kan het intussen via de upload hebben opgeslagen of via Samba hebben weggehaald.
    Geeft een redirect terug als er niets meer op te slaan valt, anders None.
    """
    naam = upload.inbox_naam
    assert naam is not None
    reconciler = _reconciler(request)
    treffer = _index(request).zoek_hash(sha256_van(upload.voorbereid.bestanden[0][1]))
    if treffer is not None:
        # Al in het archief: geen tweede document. Vrijgeven laat de poll het bestand (als het er nog
        # ligt) opnieuw beoordelen; die verplaatst het dan als dubbel naar _inbox/_dubbel/ (pakket 16).
        _openstaand(request).verwijder(upload.token)
        reconciler.geef_vrij(naam)
        entry, _ = treffer
        log.info("inbox: %s niet nogmaals opgeslagen, staat al in %s", naam, entry.rel)
        jaar, map = _splits_rel(entry.rel)
        return _redirect(request, "document", "Al opgenomen via de inbox", jaar=jaar, map=map)
    if not _archief(request).inbox_pad(naam).is_file():
        _openstaand(request).verwijder(upload.token)
        reconciler.geef_vrij(naam)
        log.info("inbox: %s niet opgeslagen, bestand ligt niet meer in de inbox", naam)
        return _redirect(request, "inbox", "Bestand is niet meer in de inbox")
    return None


@router.post("/upload/{token}/annuleer", name="upload_annuleer")
async def upload_annuleer(request: Request, token: str) -> Response:
    """Openstaande upload weggooien; er is niets op schijf gekomen. Uit de inbox: het bestand blijft daar liggen."""
    upload = _haal_openstaand(request, token)
    _openstaand(request).verwijder(token)
    if upload is not None and upload.inbox_naam is not None:
        _reconciler(request).geef_vrij(upload.inbox_naam)
        return _redirect(request, "inbox", "Teruggezet in de inbox")
    return _redirect(request, "upload", "Upload geannuleerd")


def _log_dubbelen(wat: str, dubbelen: list[Dubbel]) -> None:
    log.info("%s: %s", wat, "; ".join(f"{d.naam} staat al in {d.rel}/{d.bestand}" for d in dubbelen))


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


# --- inbox (pakket 17) ------------------------------------------------------


@dataclass
class InboxRegel:
    """Eén wachtend bestand op de inboxpagina."""

    naam: str
    grootte: str
    sinds: datetime


@router.get("/inbox", name="inbox")
async def inbox(request: Request) -> Response:
    """Inboxbestanden waarvoor de tekst geen afzender opleverde; per bestand een knop Opnemen."""
    regels = [InboxRegel(w.naam, _grootte(w.grootte), w.sinds) for w in _reconciler(request).wachtend()]
    ctx = {"wachtend": regels, "inbox_map": str(_archief(request).inbox_dir)}
    return _templates(request).TemplateResponse(request, "inbox.html", ctx)


@router.post("/inbox/opnemen", name="inbox_opnemen")
async def inbox_opnemen(request: Request, naam: str = Form("")) -> Response:
    """Eén inboxbestand naar scherm 2 van de upload: reserveren, tekst uit de sidecar, openstaande upload klaarzetten.

    Het bestand blijft in `_inbox/` liggen tot Opslaan; de reservering houdt de poll er intussen vanaf.
    """
    try:
        _archief(request).inbox_pad(naam)
    except OngeldigPad:
        raise HTTPException(status_code=404, detail="Bestand niet gevonden") from None
    reconciler = _reconciler(request)
    reconciler.reserveer(naam)  # vóór het lezen: een lopende poll mag het bestand nu niet meer opnemen
    try:
        # Normaal alleen de sidecar lezen; zonder sidecar kan dit OCR zijn, dus in een thread.
        vb, sug = await asyncio.to_thread(reconciler.bereid_inbox_voor, naam)
    except FileNotFoundError:
        reconciler.geef_vrij(naam)
        raise HTTPException(status_code=404, detail="Bestand niet gevonden") from None
    openstaand = _openstaand(request).maak(vb, sug, inbox_naam=naam)
    log.info(
        "inbox: %s opgenomen via de inboxpagina, datum %s (%s), tags %s; token %s",
        naam, vb.documentdatum, vb.datumbron, sug.tags, openstaand.token,
    )
    return _redirect(request, "upload_gegevens", token=openstaand.token)


# --- prullenbak (pakket 19) --------------------------------------------------


@dataclass
class PrullenbakRegel:
    """Eén item op de prullenbakpagina: een weggegooid document (map) of een los bestand."""

    naam: str
    is_map: bool
    titel: str
    documentdatum: date | None
    bestanden: int
    grootte: str  # geformatteerd via _grootte


def _prullenbak_regel(item: PrullenbakItem) -> PrullenbakRegel:
    return PrullenbakRegel(item.naam, item.is_map, item.titel, item.documentdatum, item.bestanden, _grootte(item.grootte))


@router.get("/prullenbak", name="prullenbak")
async def prullenbak(request: Request) -> Response:
    """Wat er in `_prullenbak/` staat, met per item een knop Definitief verwijderen en één knop Prullenbak legen."""
    archief = _archief(request)
    # De groottes vragen een recursieve walk over alle weggegooide mappen: in een thread.
    items = await asyncio.to_thread(archief.prullenbak_inhoud)
    ctx = {
        "items": [_prullenbak_regel(i) for i in items],
        "grootte": _grootte(sum(i.grootte for i in items)),
        "prullenbak_map": str(archief.trash_dir),
    }
    return _templates(request).TemplateResponse(request, "prullenbak.html", ctx)


@router.post("/prullenbak/verwijder", name="prullenbak_verwijder")
async def prullenbak_verwijder(request: Request, naam: str = Form("")) -> Response:
    """Eén item onomkeerbaar verwijderen; de padcontrole in `prullenbak_pad` is de enige verdediging vóór `rmtree`."""
    archief = _archief(request)
    try:
        archief.prullenbak_pad(naam)
    except OngeldigPad:
        raise HTTPException(status_code=404, detail="Niet gevonden in de prullenbak") from None
    try:
        await asyncio.to_thread(archief.verwijder_definitief, naam)
    except OngeldigPad:
        # Net weg (andere tab of Samba): niets te doen.
        raise HTTPException(status_code=404, detail="Niet gevonden in de prullenbak") from None
    except OSError as e:
        log.warning("prullenbak: %s kon niet worden verwijderd: %s", naam, e)
        return _redirect(request, "prullenbak", f"Verwijderen mislukt: {naam}")
    return _redirect(request, "prullenbak", "Definitief verwijderd")


@router.post("/prullenbak/leeg", name="prullenbak_leeg")
async def prullenbak_leeg(request: Request) -> Response:
    """Alles in de prullenbak onomkeerbaar verwijderen; `_prullenbak/` zelf blijft bestaan."""
    _verwijderd, mislukt = await asyncio.to_thread(_archief(request).leeg_prullenbak)
    if mislukt:
        melding = f"Prullenbak geleegd, {mislukt} item(s) konden niet worden verwijderd (zie het log)"
    else:
        melding = "Prullenbak geleegd"
    return _redirect(request, "prullenbak", melding)


# --- prullenbak: kijken in een document en terugzetten (pakket 20) -----------


def _prullenbak_item(request: Request, naam: str) -> PrullenbakDocument:
    """`PrullenbakDocument` voor een naam uit de URL of een formulier; 404 bij `OngeldigPad` (ook los bestand/symlink)."""
    try:
        return _archief(request).prullenbak_document(naam)
    except OngeldigPad:
        raise HTTPException(status_code=404, detail="Niet gevonden in de prullenbak") from None


def _prullenbak_document_pagina(
    request: Request, item: PrullenbakDocument, dubbelen: list[Dubbel] | None = None, status_code: int = 200
) -> Response:
    meta = item.meta
    bestanden = [Bestandsweergave(n, _soort(n), txt_pad(item.map / n).exists()) for n in item.bestanden]
    ctx = {
        "naam": item.naam,
        "meta": meta,
        "titel": meta.titel if meta is not None else item.naam,
        "bestanden": bestanden,
        "jaar": item.jaar,  # None -> geen knop Terugzetten
        "prullenbak_map": str(_archief(request).trash_dir),
        "dubbelen": dubbelen or [],
    }
    return _templates(request).TemplateResponse(request, "prullenbak_document.html", ctx, status_code=status_code)


@router.get("/prullenbak/{naam}", name="prullenbak_document")
async def prullenbak_document(request: Request, naam: str) -> Response:
    """Kijkpagina voor een weggegooid document: inhoud zoals op de documentpagina, knoppen Terugzetten en Definitief verwijderen."""
    item = await asyncio.to_thread(_prullenbak_item, request, naam)
    return _prullenbak_document_pagina(request, item)


@router.get("/prullenbak/{naam}/bekijk/{bestand}", name="prullenbak_bekijk")
async def prullenbak_bekijk(request: Request, naam: str, bestand: str) -> Response:
    item = _prullenbak_item(request, naam)
    try:
        _archief(request).prullenbak_bestand(naam, bestand)
    except OngeldigPad:
        raise HTTPException(status_code=404, detail="Bestand niet gevonden") from None
    return _bekijk_pagina(
        request,
        bestand,
        url=_pad_van(request.url_for("prullenbak_bestand", naam=naam, bestand=bestand)),
        terug_url=_pad_van(request.url_for("prullenbak_document", naam=naam)),
        terug_titel=item.meta.titel if item.meta is not None else item.naam,
    )


@router.get("/prullenbak/{naam}/bestand/{bestand}", name="prullenbak_bestand")
async def prullenbak_bestand(request: Request, naam: str, bestand: str) -> Response:
    try:
        pad = _archief(request).prullenbak_bestand(naam, bestand)
    except OngeldigPad:
        raise HTTPException(status_code=404, detail="Bestand niet gevonden") from None
    return FileResponse(
        pad,
        media_type=mimetypes.guess_type(bestand)[0] or "application/octet-stream",
        content_disposition_type="inline",
        filename=bestand,
    )


def _hashes_van(item: PrullenbakDocument) -> list[tuple[str, str]]:
    """(bestandsnaam, sha256) per bestand van de map: uit `meta.sha256`, anders van schijf; onleesbaar -> overgeslagen."""
    bekend = item.meta.sha256 if item.meta is not None else {}
    hashes: list[tuple[str, str]] = []
    for n in item.bestanden:
        h = bekend.get(n)
        if h is None:
            try:
                h = sha256_van_bestand(item.map / n)
            except OSError:
                continue
        hashes.append((n, h))
    return hashes


@router.post("/prullenbak/terugzetten", name="prullenbak_terugzetten")
async def prullenbak_terugzetten(request: Request, naam: str = Form("")) -> Response:
    """Zet een weggegooid document terug in de jaarmap; geweigerd (409) als een bestand al in een ander document staat."""
    item = await asyncio.to_thread(_prullenbak_item, request, naam)
    if item.jaar is None:
        raise HTTPException(status_code=404, detail="Niet terug te zetten: geen jaar bekend")
    archief = _archief(request)
    index = _index(request)
    dubbelen = zoek_dubbelen_van_hashes(index, await asyncio.to_thread(_hashes_van, item))
    if dubbelen:
        _log_dubbelen(f"terugzetten van {naam} geweigerd", dubbelen)
        return _prullenbak_document_pagina(request, item, dubbelen=dubbelen, status_code=409)
    try:
        doc = await asyncio.to_thread(archief.herstel_uit_prullenbak, naam)
    except OngeldigPad:
        raise HTTPException(status_code=404, detail="Niet gevonden in de prullenbak") from None
    try:
        entry = index.herlaad(archief, doc)
    except MetaFout:
        entry = None  # map zonder leesbare meta.md: de reconciler maakt er een en neemt hem dan op
    if entry is not None and entry.meta.ocr == "pending":
        queue = _queue(request)
        for n in entry.meta.bestanden:
            if is_extraheerbaar(n) and not txt_pad(doc / n).exists():
                queue.enqueue(doc, n)
    jaar, map = _splits_rel(archief.relatief(doc))
    return _redirect(request, "document", "Teruggezet", jaar=jaar, map=map)


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
        weergaven.append(Bestandsweergave(naam, _soort(naam), txt_pad(entry.map / naam).exists()))
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
    dubbelen: list[Dubbel] | None = None,
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
        "dubbelen": dubbelen or [],  # geweigerde bestanden bij toevoegen (pakket 16)
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
    herkomst = _herkomst(q, alles)
    uploads = [(f.filename, await f.read()) for f in bestanden]
    dubbelen = zoek_dubbelen(_index(request), [(n, d) for n, d in uploads if n])
    if dubbelen:
        # Ook een bestand dat al in ditzelfde document zit; één dubbel -> niets toegevoegd (pakket 16).
        _log_dubbelen(f"toevoegen aan {entry.rel} geweigerd", dubbelen)
        return _document_pagina(
            request, entry, jaar, map, status_code=409, herkomst=herkomst, dubbelen=dubbelen
        )
    aantal = _sla_bestanden_op(archief, _queue(request), entry.map, uploads)
    _index(request).herlaad(archief, entry.map)
    log.info("bestanden toegevoegd aan %s: %d", entry.rel, aantal)
    return _redirect(request, "document", "Toegevoegd", query=herkomst, jaar=jaar, map=map)


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
    doel = archief.naar_prullenbak(entry.map)
    _index(request).verwijder(rel)
    return _redirect(
        request, "zoeken", "Verplaatst naar prullenbak", query=_herkomst(q, alles), ongedaan=doel.name
    )


@router.get("/doc/{jaar}/{map}/bekijk/{naam}", name="bekijk")
async def bekijk(request: Request, jaar: str, map: str, naam: str) -> Response:
    """Kijkpagina voor één bestand: eigen kop met terugknop, het bestand (pdf/afbeelding) eronder.

    De "Open"-knop wijst hierheen en niet naar het kale bestand: in de HA-app vult een los geopend
    bestand het hele scherm zonder weg terug (iOS-webview). Hier blijft de navigatie van de app staan.
    """
    entry = _entry(request, jaar, map)
    try:
        pad = _archief(request).veilig_pad(jaar, map, naam)
    except OngeldigPad:
        raise HTTPException(status_code=404, detail="Bestand niet gevonden") from None
    if not pad.is_file():
        raise HTTPException(status_code=404, detail="Bestand niet gevonden")
    herkomst = _herkomst(request.query_params.get("q", ""), request.query_params.get("alles", ""))
    terug = request.url_for("document", jaar=jaar, map=map)
    if herkomst["q"]:
        terug = terug.include_query_params(**{k: v for k, v in herkomst.items() if v})
    return _bekijk_pagina(
        request,
        naam,
        url=_pad_van(request.url_for("bestand", jaar=jaar, map=map, naam=naam)),
        terug_url=_pad_van(terug),
        terug_titel=entry.meta.titel,
    )


def _pad_van(url: URL) -> str:
    """Pad plus query van een `url_for`-resultaat, zonder scheme/host (zoals de Jinja-global `url_for`)."""
    return url.path + (f"?{url.query}" if url.query else "")


def _bekijk_pagina(request: Request, naam: str, url: str, terug_url: str, terug_titel: str) -> Response:
    """`bekijk.html` voor een bestand in het archief of in de prullenbak (pakket 20)."""
    ctx = {"naam": naam, "soort": _soort(naam), "url": url, "terug_url": terug_url, "terug_titel": terug_titel}
    return _templates(request).TemplateResponse(request, "bekijk.html", ctx)


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
    inbox = _reconciler(request).inbox_telling()
    data: dict[str, object] = {
        "queue": queue.lengte,
        "bezig": sorted(queue.bezig),
        "reconcile_bezig": bool(request.app.state.reconcile_bezig),
        "tellingen": index.tellingen(),
        # pakket 18: tabel Inbox op de beheerpagina
        "inbox": {"totaal": inbox.totaal, "wachtend": inbox.wachtend, "dubbel": inbox.dubbel},
        # pakket 19: alleen het aantal (één iterdir plus de meta's), niet de grootte (recursieve walk)
        "prullenbak": {"aantal": len(_archief(request).prullenbak_inhoud(met_grootte=False))},
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
    archief = _archief(request)
    prullenbak = await asyncio.to_thread(archief.prullenbak_inhoud)  # met groottes: in een thread (pakket 19)
    ctx = {
        "tellingen": index.tellingen(),
        "queue": queue.lengte,
        "bezig": sorted(queue.bezig),
        "reconcile_bezig": bool(request.app.state.reconcile_bezig),
        "rapport": request.app.state.laatste_rapport,
        "interval_minuten": max(1, round(settings.reconcile_interval / 60)),
        # pakket 18: tabel Inbox (totaal / wacht op titel / dubbel)
        "inbox": _reconciler(request).inbox_telling(),
        "inbox_map": str(archief.inbox_dir),
        # pakket 19: tabel Prullenbak (aantal live via /api/status, grootte = stand bij het laden)
        "prullenbak_aantal": len(prullenbak),
        "prullenbak_grootte": _grootte(sum(i.grootte for i in prullenbak)),
        "prullenbak_map": str(archief.trash_dir),
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
