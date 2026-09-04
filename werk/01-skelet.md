# Pakket 01 — Skelet

> **Agent-prompt:** Lees `werk/00-contract.md` en `werk/01-skelet.md`. Voer pakket 01 uit. Draai `pytest`. Commit met bericht `pakket 01: skelet`. Vink af in `werk/STATUS.md`.

**Doel:** een werkende repo waarin elk volgend pakket direct `pytest` kan draaien.

**Lees eerst:** `werk/00-contract.md`.
**Vereist:** niets.

## Maakt

- `pyproject.toml` — pytest-config: `[tool.pytest.ini_options]` met `testpaths = ["tests"]` en `asyncio_mode = "auto"`.
- `requirements.txt` — `fastapi`, `uvicorn[standard]`, `jinja2`, `python-multipart`, `pyyaml`, `pillow`, `pillow-heif`.
- `requirements-dev.txt` — `-r requirements.txt`, `pytest`, `pytest-asyncio`, `httpx`.
- `.gitignore` — `.venv/`, `data/`, `__pycache__/`, `*.pyc`, `.pytest_cache/`.
- `ordner/__init__.py` (leeg), `ordner/web/__init__.py` (leeg).
- `ordner/config.py` — volledig volgens contract.
- Lege modules met alleen een docstring: `ordner/slug.py`, `meta.py`, `storage.py`, `extract.py`, `index.py`, `search.py`, `worker.py`.
- `tests/conftest.py` — alleen de `mock_cmd`-fixture (de `archief`- en `client`-fixtures komen in pakket 03 en 08).
- `tests/test_config.py`.
- `CLAUDE.md`, `IDEAS.md`, `README.md`.

## Specificatie

- `Settings.from_env()` leest `ORDNER_DATA`, `ORDNER_OCR_TALEN`, `ORDNER_OCR_PARALLEL`, `ORDNER_RECONCILE_INTERVAL`, `ORDNER_INBOX_INTERVAL`. Ongeldige ints → `ValueError` met de variabelenaam in de melding. `data_root` altijd `.resolve()`.
- `mock_cmd`-fixture: klasse `CmdMock` met
  - `register(naam: str, rc: int = 0, stdout: bytes = b"", stderr: bytes = b"", handler=None)`;
  - `calls: list[list[str]]`;
  - `async def __call__(self, args: list[str], timeout: float = 600) -> tuple[int, bytes, bytes]` die matcht op `Path(args[0]).name` (zonder `.exe`); als `handler` gezet is → `handler(args)` retourneert `(rc, stdout, stderr)`; anders de geregistreerde waarden.
  - Ongeregistreerd commando → raise. Omdat `extract.py` nu nog leeg is: probeer `from ordner.extract import ExtractieFout` en val terug op een lokale `class ExtractieFout(Exception)` als de import faalt. Vanaf pakket 04 gooit hij dus automatisch de echte.
  - De fixture doet `monkeypatch.setattr("ordner.extract.run_cmd", mock, raising=False)` en geeft `mock` terug.
- `CLAUDE.md`: korte inleiding (wat Ordner is), de ontwerpbeslissingen-tabel uit het contract, "niet in v1", conventies (ingekort), en: "Werkpakketten en het bindende interface-contract staan in `werk/`. Houd het klein; ideeën gaan naar `IDEAS.md`."
- `IDEAS.md` seed (één regel per idee):
  - MCP-server (FastMCP) met `zoek_documenten`, `lees_document`, `bewerk_metadata`
  - Claude-geassisteerd titelen van inbox-documenten
  - Submap in `_inbox/` = één document met meerdere bestanden
  - "Alles opnieuw OCR'en"-knop
  - Tag-overzicht
  - SQLite FTS5 als de in-memory index te groot wordt (>5000 documenten)
  - Prullenbak legen / terugzetten
  - PDF/A-kopie met tekstlaag bewaren naast het origineel
- `README.md` (kort, wordt in pakket 10 uitgebreid): wat het is, lokaal draaien, tests draaien.

## Tests

- `from_env` zonder env-vars → defaults, `data_root` is absoluut.
- `from_env` met alle vijf env-vars gezet → waarden overgenomen.
- `ORDNER_OCR_PARALLEL=abc` → `ValueError` met `ORDNER_OCR_PARALLEL` in de melding.

## Klaar als

- `python -m venv .venv` aangemaakt en `pip install -r requirements-dev.txt` geslaagd.
- `pytest` groen.
- Commit `pakket 01: skelet`.

## Buiten scope

Alle domeincode (slug, meta, storage, …).
