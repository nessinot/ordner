# Pakket 10 — Add-on en docs

> **Agent-prompt:** Lees `werk/00-contract.md` en `werk/10-addon-en-docs.md`. Voer pakket 10 uit. Draai `pytest`. Commit met bericht `pakket 10: add-on en docs`. Vink af in `werk/STATUS.md`.

**Doel:** installeerbaar als lokale Home Assistant add-on; documentatie compleet.

**Lees eerst:** `werk/00-contract.md` (Ontwerpbeslissing "Base image", Repo-structuur).
**Vereist:** pakket 09.

## Maakt / wijzigt

- `config.yaml`, `build.yaml`, `Dockerfile`, `run.sh`
- `DOCS.md` (nieuw), `README.md` (uitbreiden), `CLAUDE.md` (bijwerken waar nodig)

## Specificatie

### `config.yaml`
```yaml
name: Ordner
version: "0.1.0"
slug: ordner
description: Minimale digitale archiefkast voor privédocumenten
url: https://github.com/<placeholder>/ordner
arch:
  - amd64
  - aarch64
init: false
ingress: true
ingress_port: 8099
panel_icon: mdi:archive
panel_title: Ordner
map:
  - share:rw
options:
  ocr_talen: "nld+eng"
  ocr_parallel: 2
  reconcile_interval: 300
schema:
  ocr_talen: str
  ocr_parallel: int(1,8)
  reconcile_interval: int(30,86400)
```

### `build.yaml`
```yaml
build_from:
  amd64: ghcr.io/home-assistant/amd64-base-debian:bookworm
  aarch64: ghcr.io/home-assistant/aarch64-base-debian:bookworm
```

### `Dockerfile`
```dockerfile
ARG BUILD_FROM
FROM $BUILD_FROM
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      python3 python3-venv ocrmypdf tesseract-ocr-nld tesseract-ocr-eng poppler-utils libheif1 \
 && rm -rf /var/lib/apt/lists/*
RUN python3 -m venv /opt/venv
COPY requirements.txt /tmp/requirements.txt
RUN /opt/venv/bin/pip install --no-cache-dir -r /tmp/requirements.txt
WORKDIR /app
COPY ordner/ /app/ordner/
COPY run.sh /run.sh
RUN chmod a+x /run.sh
CMD ["/run.sh"]
```
Let op: `ocrmypdf` uit apt trekt zijn eigen Python-afhankelijkheden als systeempakketten binnen; dat staat los van de venv. Dat is de bedoeling — we roepen `ocrmypdf` als commando aan.

### `run.sh`
```bash
#!/usr/bin/with-contenv bashio
export ORDNER_DATA=/share/ordner
export ORDNER_OCR_TALEN="$(bashio::config 'ocr_talen')"
export ORDNER_OCR_PARALLEL="$(bashio::config 'ocr_parallel')"
export ORDNER_RECONCILE_INTERVAL="$(bashio::config 'reconcile_interval')"
bashio::log.info "Ordner start, archief in ${ORDNER_DATA}"
exec /opt/venv/bin/uvicorn ordner.web.app:app --host 0.0.0.0 --port 8099 --proxy-headers --forwarded-allow-ips "*"
```
Zorg dat het bestand LF-regeleinden heeft (voeg `run.sh text eol=lf` toe aan een `.gitattributes`), anders faalt de shebang in de container.

### `DOCS.md` (add-on-tab "Documentatie")
Secties: Wat is Ordner · Mapstructuur (met voorbeeld) · `meta.md` uitgelegd (velden, dat je hem zelf mag bewerken) · Inbox (`/share/ordner/_inbox`) · Prullenbak · Beheerpagina (wat de knop doet, wanneer nodig) · Opties (`ocr_talen`, `ocr_parallel`, `reconcile_interval`) · Als OCR faalt (status `failed`, wat te doen: "OCR opnieuw", `.txt` handmatig plaatsen) · Backup (zit in `/share`, dus in HA-backups).

### `README.md`
Secties: Wat · Installatie als lokale add-on (via Samba de repo naar `/addons/ordner` kopiëren → Instellingen › Add-ons › Add-on store › ⋮ › Controleren op updates › "Local add-ons" › Ordner › Installeren) · Lokaal ontwikkelen (venv, `ORDNER_DATA=./data uvicorn ordner.web.app:app --reload`, PowerShell-variant) · Tests (`pytest`) · Structuur (korte verwijzing naar `CLAUDE.md` en `werk/`).

### `CLAUDE.md`
Controleer dat de tabel nog klopt met wat gebouwd is; voeg toe hoe je lokaal en in de add-on draait.

## Klaar als

- `pytest` groen.
- `config.yaml` is geldige YAML met de velden hierboven (parse hem in een kleine test `tests/test_addon_config.py`: `yaml.safe_load`, controleer `slug == "ordner"`, `ingress is True`, `ingress_port == 8099`, `"share:rw" in map`, en dat elke key in `options` ook in `schema` staat).
- `run.sh` heeft LF-regeleinden (test: bestand bevat geen `\r`).
- De Docker-build zelf wordt in pakket 12 (container-laag) gebouwd en getest; hier niet.
- Commit `pakket 10: add-on en docs`.

## Buiten scope

Installatie op HA zelf (pakket 11, handmatig).
