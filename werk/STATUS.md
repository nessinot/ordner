# Status werkpakketten

Vink af zodra het pakket gecommit is. Noteer afwijkingen of open punten kort achter de regel.

- [x] 01 skelet
- [x] 02 meta en slug — `uploaddatum` expliciet gequoteerd (PyYAML quotet `JJJJ-MM-DDTHH:MM` niet vanzelf)
- [x] 03 storage
- [x] 04 extract
- [x] 05 index en reconciler — een `.txt` dat al in `bestanden` staat (bewust geüpload) wordt bij de sync behouden; onbekende `.txt`'s gelden als OCR-tekst
- [x] 06 search
- [x] 07 worker — `.txt` wordt geschreven via `.<naam>.txt.tmp` in dezelfde map; een documentmap die vóór verwerking verdwijnt blijft in de index tot de reconciler hem opruimt
- [x] 08 web basis — Jinja-global `url_for` levert paden (met Ingress-prefix) i.p.v. absolute URL's; titel-validatie geeft 400 i.p.v. 422; `beheer.html` als placeholder aangemaakt
- [x] 09 web document en beheer — `data-status-url` staat op `<body>` in `base.html` (elke pagina); verwijder-confirm op de knop, werkt zonder JS; beheerknop `disabled` zolang de reconcile loopt; fout in handmatige reconcile wordt gelogd en zet `reconcile_bezig` terug
- [x] 10 add-on en docs — `url` in `config.yaml` wijst naar de echte remote (`nessinot/ordner`); `.gitattributes` forceert LF voor `run.sh`, `Dockerfile` en `*.yaml`; `.dockerignore` houdt `data/`, `tests/`, `werk/` en `.venv/` uit de build-context
- [x] 12 end-to-end — browser-laag groen (10 tests, zonder OCR-tools dus `failed`-pad); container-laag nog niet gedraaid: draai `pytest -m container` zodra Docker beschikbaar is. Fixture-pdf gebruikt 20pt i.p.v. 24pt (24pt liep over de paginarand). `pythonpath = ["."]` in `pyproject.toml` zodat `tests.e2e.conftest` importeerbaar is
- [x] 13 add-on-repository — installeren via GitHub-URL i.p.v. Samba (keuze 2026-09-04). Add-on en package naar `addon/`, `repository.yaml` in de root; `pythonpath = ["addon", "."]` (absolute `tests.e2e.conftest`-imports blijven werken). Container-laag nog steeds geskipt (geen Docker). Repo is publiek en de add-on installeert vanuit de store
- [ ] 11 HA-checklist (handmatig, na 13)

## Releases na de werkpakketten

- 0.3.0 (2026-09-04): Ingress-fix voor static files; UI in Drive-stijl
- 0.4.0 (2026-09-04): zoeklijst eerlijk afgekapt. Startscherm toont de 20 nieuwste met voetnoot "De 20 nieuwste van N documenten"; zoeken toont het echte totaal, kapt af op 50 en biedt "Toon alle N" (`?alles=1`). `zoek()` heeft geen `limiet` meer
- 0.4.1 (2026-09-04): terugknop op de documentpagina. De zoekopdracht (`q`, `alles`) reist mee in de documentlink en als verborgen veld in de formulieren; redirects na opslaan/OCR/toevoegen/verwijderen behouden hem (`_redirect(..., query=...)`)
