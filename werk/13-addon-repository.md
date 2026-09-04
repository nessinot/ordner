# Pakket 13 — Add-on-repository

> **Agent-prompt:** Lees `werk/00-contract.md` en `werk/13-addon-repository.md`. Voer pakket 13 uit. Draai `pytest` en `pytest -m e2e`. Commit met bericht `pakket 13: add-on-repository`. Vink af in `werk/STATUS.md`. Push niet zelf; Bas pusht en zet de repo publiek.

**Doel:** Ordner installeren en updaten via de Add-on store met de GitHub-URL, in plaats van de repo via Samba naar `/addons/ordner` te kopiëren. Home Assistant haalt de add-on dan zelf op; een update is een push plus versiebump.

**Lees eerst:** `werk/00-contract.md` (Repo-structuur), `README.md`, `tests/e2e/conftest.py` (fixture `container`).
**Vereist:** pakket 12.

## Waarom herstructureren

De Supervisor accepteert een git-repository alleen als *add-on-repository*: `repository.yaml` in de root en elke add-on in een eigen submap met daarin `config.yaml`. De Docker-build-context is die submap, dus het Python-package moet erin staan. De huidige layout (add-on-bestanden in de repo-root) werkt alleen voor `/addons/<map>` via Samba.

## Nieuwe repo-structuur

```
ordner/                        # repo-root = add-on-repository
  repository.yaml
  README.md CLAUDE.md IDEAS.md
  pyproject.toml requirements-dev.txt .gitignore .gitattributes
  werk/  tests/  data/
  addon/                       # de add-on; dit is de Docker-build-context
    config.yaml build.yaml Dockerfile run.sh .dockerignore
    DOCS.md                    # tabblad "Documentatie" in de add-on
    requirements.txt
    ordner/                    # Python-package (ongewijzigd verplaatst)
```

`repository.yaml`:
```yaml
name: Ordner
url: https://github.com/nessinot/ordner
maintainer: nessinot
```

## Maakt / wijzigt

- `git mv` van `config.yaml build.yaml Dockerfile run.sh .dockerignore DOCS.md requirements.txt ordner/` naar `addon/`. Inhoud ongewijzigd; `Dockerfile`-paden (`COPY requirements.txt`, `COPY ordner/`, `COPY run.sh`) blijven relatief aan de context en kloppen dus nog.
- `repository.yaml` (nieuw, root).
- `requirements-dev.txt`: `-r addon/requirements.txt`.
- `pyproject.toml`: `pythonpath = ["addon"]` (was `"."`) zodat `import ordner` in tests blijft werken; `tests.e2e.conftest`-imports vervangen door relatieve imports (`from .conftest import …`) of `pythonpath = ["addon", "."]`.
- `tests/test_addon_config.py`: `ROOT` → `ROOT / "addon"`; extra test: `repository.yaml` parseert, heeft `name` en `url`, en `addon/config.yaml` bestaat.
- `tests/e2e/conftest.py`: `docker build`-context `REPO / "addon"`; uvicorn starten met `--app-dir addon`.
- `.gitattributes`: patronen zonder pad (`run.sh`, `Dockerfile`, `*.yaml`) matchen al in submappen; controleren, niets aan te passen tenzij er paden in staan.
- `README.md`: installatiesectie herschrijven (zie onder); dev-commando's met `--app-dir addon`.
- `CLAUDE.md`: tabelregel "Naam" en sectie "Draaien" bijwerken; `werk/00-contract.md` Repo-structuur vervangen door de nieuwe en een regel onder "Wijzigingen op het contract".
- `werk/11-ha-checklist.md`: stap 1 vervangen door "repository toevoegen".

## Installatie (nieuwe tekst voor `README.md`)

1. Instellingen › Add-ons › Add-on store › ⋮ (rechtsboven) › **Repositories** › `https://github.com/nessinot/ordner` toevoegen.
2. De sectie "Ordner" verschijnt in de store (zo nodig ⋮ › Controleren op updates). Open **Ordner** › Installeren. De build draait op de HA-machine en duurt de eerste keer enkele minuten.
3. Starten, **Toon in zijbalk** aan. Archief in `/share/ordner`.

Updaten: `version` in `addon/config.yaml` ophogen, committen, pushen; in HA ⋮ › Controleren op updates → knop **Update** bij Ordner. Zonder versiebump ziet HA geen update.

Voorwaarde: de GitHub-repo moet **publiek** zijn; de Supervisor kent geen credentials.

## Lokaal draaien na de verhuizing

```powershell
$env:ORDNER_DATA = "./data"
uvicorn --app-dir addon ordner.web.app:app --reload
```

## Klaar als

- `pytest` groen, `pytest -m e2e` groen (server-fixture met `--app-dir addon`), `pytest -m container` geskipt of groen.
- `python -c "import yaml; yaml.safe_load(open('repository.yaml'))"` slaagt; `addon/config.yaml` valideert via `tests/test_addon_config.py`.
- `git status` schoon, één commit `pakket 13: add-on-repository`.
- Daarna handmatig (Bas): repo publiek zetten, `git push -u origin main`, dan `werk/11-ha-checklist.md`.

## Buiten scope

Publiceren van een voorgebouwd image (`image:` in `config.yaml` + GitHub Actions); HA bouwt lokaal. Idee → `IDEAS.md` als de build op de mini-pc te lang duurt.
