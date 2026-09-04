"""FastAPI-app met Ingress-ondersteuning en achtergrondtaken (pakket 08)."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from jinja2 import pass_context

from ordner.config import Settings
from ordner.index import Index, Reconciler, bouw_index
from ordner.ingest import maak_tekstlezer
from ordner.storage import Archief
from ordner.web.openstaand import OpenstaandeUploads
from ordner.web.routes import router
from ordner.worker import OcrQueue, inbox_lus, reconcile_lus

log = logging.getLogger(__name__)

_WEB_DIR = Path(__file__).parent
TEMPLATES_DIR = _WEB_DIR / "templates"
STATIC_DIR = _WEB_DIR / "static"


def url_pad(request: Request, naam: str, /, **path_params: str) -> str:
    """Pad (zonder scheme/host) voor een route, inclusief het Ingress-prefix uit root_path."""
    return request.url_for(naam, **path_params).path


def maak_templates() -> Jinja2Templates:
    """Jinja2-omgeving waarin `url_for(naam, ...)` een pad met Ingress-prefix oplevert."""
    templates = Jinja2Templates(directory=TEMPLATES_DIR)

    def url_for(context: dict[str, object], naam: str, /, **path_params: str) -> str:
        request = context["request"]
        assert isinstance(request, Request)
        return url_pad(request, naam, **path_params)

    templates.env.globals["url_for"] = pass_context(url_for)
    return templates


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    archief = Archief(settings.data_root)
    index = Index()  # leeg; gevuld in de lifespan, één instantie die overal gedeeld wordt
    queue = OcrQueue(archief, index, settings)
    lees_tekst = maak_tekstlezer(settings.ocr_talen)
    reconciler = Reconciler(archief, index, queue.enqueue, lees_tekst=lees_tekst)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        index.docs.update(bouw_index(archief).docs)
        log.info("index gebouwd: %d document(en) in %s", len(index.docs), archief.root)
        await queue.start()
        stop = asyncio.Event()
        tasks = [
            asyncio.create_task(reconcile_lus(reconciler, queue, settings, stop), name="reconcile"),
            asyncio.create_task(inbox_lus(reconciler, queue, settings, stop), name="inbox"),
        ]
        try:
            yield
        finally:
            stop.set()
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            await queue.stop()

    app = FastAPI(title="Ordner", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.settings = settings
    app.state.archief = archief
    app.state.index = index
    app.state.queue = queue
    app.state.lees_tekst = lees_tekst
    app.state.reconciler = reconciler
    app.state.laatste_rapport = None
    app.state.reconcile_bezig = False
    app.state.templates = maak_templates()
    app.state.openstaand = OpenstaandeUploads()  # tweestaps upload (15b): alleen geheugen, weg bij herstart

    @app.middleware("http")
    async def ingress(request: Request, call_next):  # type: ignore[no-untyped-def]
        prefix = request.headers.get("X-Ingress-Path", "").rstrip("/")
        if prefix:
            # Starlette verwacht dat `path` het root_path bevat; anders kan de
            # static-mount het prefix niet afstrippen en geeft hij 404.
            request.scope["root_path"] = prefix
            pad = request.scope["path"]
            if not pad.startswith(prefix + "/") and pad != prefix:
                request.scope["path"] = prefix + pad
        return await call_next(request)

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    app.include_router(router)
    return app


app = create_app()
