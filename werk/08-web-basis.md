# Pakket 08 — Web basis

> **Agent-prompt:** Lees `werk/00-contract.md` en `werk/08-web-basis.md`. Voer pakket 08 uit. Draai `pytest`. Commit met bericht `pakket 08: web basis`. Vink af in `werk/STATUS.md`.

**Doel:** FastAPI-app met Ingress-ondersteuning, zoekpagina, uploadpagina en bestand-serving.

**Lees eerst:** `werk/00-contract.md` (Ontwerpbeslissing "Web", Interface `web/app.py`, tabel Routenamen, Testfixtures `client`).
**Vereist:** pakketten 06 en 07.

## Maakt

- `ordner/web/app.py`, `ordner/web/routes.py`
- `ordner/web/templates/base.html`, `zoeken.html`, `upload.html`, en een minimale `document.html` (placeholder; wordt in 09 vervangen)
- `ordner/web/static/style.css`, `ordner/web/static/app.js`
- `tests/test_web.py`
- `client`-fixture in `tests/conftest.py`

## Specificatie

### `create_app(settings=None)`
- `settings = settings or Settings.from_env()`.
- `archief = Archief(settings.data_root)`; `index = Index()` (leeg; gevuld in lifespan); `queue = OcrQueue(archief, index, settings)`; `reconciler = Reconciler(archief, index, queue.enqueue)`.
- Lifespan (`@asynccontextmanager`): `index.docs.update(bouw_index(archief).docs)` (of vervang de index — maar houd één instantie die overal gedeeld is; simpelst: `bouw_index` levert de index en je maakt queue/reconciler pas dáárna in de lifespan, en zet alles op `app.state`). `await queue.start()`; `stop = asyncio.Event()`; tasks voor `reconcile_lus` en `inbox_lus`; `yield`; `stop.set()`; tasks cancelen/awaiten; `await queue.stop()`.
- `app.state.settings / archief / index / queue / reconciler / laatste_rapport (None) / reconcile_bezig (False)`.
- `Jinja2Templates(directory=<package>/web/templates)`; `app.mount("/static", StaticFiles(directory=<package>/web/static), name="static")`.
- Routes uit `routes.py` via een `APIRouter` includen.

### Ingress-middleware
```python
@app.middleware("http")
async def ingress(request, call_next):
    prefix = request.headers.get("X-Ingress-Path", "").rstrip("/")
    if prefix:
        request.scope["root_path"] = prefix
    return await call_next(request)
```
Templates gebruiken **uitsluitend** `request.url_for("naam", ...)` voor links, form-actions en static (`request.url_for("static", path="style.css")`). Nooit een hardcoded `/...`. Redirects in routes ook via `url_for` (`RedirectResponse(str(request.url_for(...)), status_code=303)`).

### Templates
- `base.html`: `<!doctype html>`, `<meta name="viewport" content="width=device-width, initial-scale=1">`, `<title>Ordner</title>`, stylesheet, nav met links Zoeken · Uploaden · Beheer (beheer-link mag in 08 al naar `url_for("beheer")` wijzen; maak dan in 08 een placeholder-route `beheer` die alleen "komt in pakket 09" toont), `<main>{% block content %}{% endblock %}</main>`, flash-melding: als query-param `m` aanwezig → `<p class="melding">{{ m }}</p>`; script-tag voor `app.js` onderaan.
- `zoeken.html`: zoekformulier (`GET`, input `q`, `type="search"`, autofocus), resultatenlijst. Zonder `q`: kop "Recent" met `index.alle()[:20]`. Per kaart: titel (link naar `document`), documentdatum, omschrijving, en bij zoekresultaat: snippet + `<small>bron</small>`; badge als `ocr != "done"`.
- `upload.html`: `POST`, `enctype="multipart/form-data"`: `bestanden` (`type="file"`, `multiple`, `accept="image/*,application/pdf"`, **geen** `capture`), `titel` (required), `omschrijving` (textarea), `documentdatum` (`type="date"`, default vandaag), `tags` (tekst, komma-gescheiden). `<progress hidden>`. Foutmelding-slot.
- `document.html` (placeholder): titel, datum, lijst van bestanden met link naar `bestand`. Wordt in 09 volledig.

### CSS (`style.css`)
Systeemfont-stack, `max-width: 48rem; margin: auto; padding: 1rem`, inputs/buttons `font-size: 16px` (voorkomt iOS-zoom), `min-height: 44px` voor knoppen en links in de nav, eenvoudige kaart (`border, border-radius, padding`), `.badge`, `.melding`. Geen externe assets.

### Routes
- `GET /` (`zoeken`): `q = request.query_params.get("q", "").strip()`; `q` → `zoek(index, q)`; anders `index.alle()[:20]`. Render.
- `GET /upload` (`upload`): formulier.
- `POST /upload`: `bestanden: list[UploadFile] = File(default=[])`, `titel: str = Form(...)`, `omschrijving: str = Form("")`, `documentdatum: str = Form("")`, `tags: str = Form("")`. Validatie: titel gestript niet leeg, anders formulier opnieuw met melding en status 400; datum leeg → vandaag, ongeldig → 400. `tags` splitsen op komma, strippen, lege weg. `doc = archief.maak_document(...)`; per upload met niet-lege filename: `naam = archief.voeg_bestand_toe(doc, f.filename, await f.read())`; `if is_extraheerbaar(naam): queue.enqueue(doc, naam)`. `index.herlaad(archief, doc)`. `303` naar `url_for("document", jaar=..., map=...)` met `?m=Opgeslagen`.
- `GET /doc/{jaar}/{map}` (`document`): `archief.veilig_pad(jaar, map)` → `OngeldigPad` → 404; entry uit `index.docs` (of `index.herlaad` als hij ontbreekt maar de map bestaat). Placeholder-render.
- `GET /doc/{jaar}/{map}/bestand/{naam}` (`bestand`): `veilig_pad(jaar, map, naam)` → `FileResponse(pad, media_type=mimetypes.guess_type(naam)[0] or "application/octet-stream", content_disposition_type="inline", filename=naam)`; `OngeldigPad` → 404.
- `GET /beheer` (`beheer`): placeholder.

### `app.js`
```js
document.addEventListener("DOMContentLoaded", () => {
  const form = document.querySelector("form[data-upload]");
  if (!form || !window.XMLHttpRequest) return;
  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const bar = form.querySelector("progress"); bar.hidden = false;
    const xhr = new XMLHttpRequest();
    xhr.open("POST", form.action);
    xhr.upload.onprogress = (ev) => { if (ev.lengthComputable) { bar.max = ev.total; bar.value = ev.loaded; } };
    xhr.onload = () => { if (xhr.responseURL) window.location = xhr.responseURL; else form.submit(); };
    xhr.onerror = () => form.submit();
    xhr.send(new FormData(form));
  });
});
```
Het uploadformulier krijgt `data-upload`. Zonder JS werkt de normale POST + 303.

### `client`-fixture
```python
@pytest.fixture
def client(tmp_path, mock_cmd):
    mock_cmd.register("pdfinfo", stdout=b"Pages: 1")
    mock_cmd.register("pdftotext", stdout=b"x" * 100)
    mock_cmd.register("tesseract", stdout=b"tekst")
    app = create_app(Settings(data_root=tmp_path / "archief", reconcile_interval=3600, inbox_interval=3600))
    with TestClient(app) as c:
        yield c
```

## Tests

- `GET /` → 200, bevat "Ordner".
- `POST /upload` zonder titel → 400.
- `POST /upload` met `titel=Test`, `documentdatum=2026-03-01`, één pdf → 303; `Location` bevat `/doc/2026/2026-03-01_test`; map bestaat; `meta.md` heeft `ocr: pending` direct na de upload (of `done` als de queue al klaar is — test daarom op: bestand aanwezig in `bestanden`, en na `client.app.state.queue._queue.join()` (via `asyncio.run` of `anyio`; eenvoudiger: poll max 2 s tot `.txt` bestaat) is `a.pdf.txt` aanwezig).
- Met header `X-Ingress-Path: /api/hassio_ingress/abc`: `GET /` → alle `href="` en `action="` en de stylesheet-link beginnen met `/api/hassio_ingress/abc/`.
- Na upload: `GET /?q=test` toont de titel.
- `GET /doc/2026/2026-03-01_test/bestand/a.pdf` → 200, `content-disposition` bevat `inline`, body = geüploade bytes.
- `GET /doc/2026/../x/bestand/a.pdf` → 404 (TestClient normaliseert mogelijk; test dan ook `map="..%5C.."` en een niet-bestaande map).
- `GET /doc/2026/nietbestaand` → 404.

## Buiten scope

Volledige documentpagina, beheer, status-API (09).
