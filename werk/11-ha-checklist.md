# Pakket 11 — HA-checklist (handmatig, kort)

Alles wat met een browser of Docker te testen is, zit in pakket 12 en draait automatisch. Wat overblijft heeft een echte Home Assistant-installatie of een echte telefoon nodig. Dit voert Bas zelf uit, ná pakket 13.

**Vereist:** pakket 13 gecommit en gepusht, repo publiek; bij voorkeur `pytest -m container` groen (anders test je de container-laag hier voor het eerst).

## Home Assistant

1. [x] Instellingen › Add-ons › Add-on store › ⋮ › Repositories › `https://github.com/nessinot/ordner` toevoegen → sectie "Ordner" → Installeren. Build duurt enkele minuten.
2. [x] Starten; log toont een reconcile-rapport en `Uvicorn running`, geen tracebacks. "Toon in zijbalk" aan → menu-item "Ordner" opent de zoekpagina en de nav-links werken onder het echte Ingress-token.
3. [x] HA-backup maken → `/share/ordner` zit erin. (Niet apart gecontroleerd; `/share` zit standaard in een HA-backup. Van de lijst, 2026-09-05.)

## Telefoon (HA-app)

4. [ ] **Nog te doen.** Uploaden → foto uit de fotorol (HEIC) → titel → Opslaan. Voortgangsbalk zichtbaar, landt op de documentpagina, wordt vanzelf `done`.
5. [x] **iOS: pdf inline** — beantwoord op 2026-09-05 (releases 0.9.1 en 0.9.2): de Open-link zonder `target=_blank` werkt in de HA-app; sinds 0.9.2 opent hij een kijkpagina met terugknop. Android-webview kan geen pdf tonen en downloadt hem; daarvoor staat een losse link onder het lege vlak.
6. [x] Afbeelding inline zichtbaar; zoeken vanaf de telefoon werkt.

## Samba (optioneel, ter bevestiging)

7. [ ] **Nog te doen.** `/share/ordner/JJJJ/…` is leesbaar in de Verkenner: `meta.md`, origineel, `.txt`. Een bestand in `_inbox/` droppen vanaf de pc: met een herkenbare afzender in de tekst verschijnt het binnen ~10 s als document; zonder afzender verschijnt het op de pagina Inbox (regel op het startscherm) en staat de gelezen tekst in `_inbox/.tekst/` (sinds 0.11.0, pakket 17). Opnemen → titel → Opslaan; controleer dat bestand en sidecar daarna weg zijn.

## Stand (2026-09-05)

Afgevinkt met Bas: 1, 2, 3, 5, 6, 8. Open: 4 (HEIC-upload vanaf de telefoon) en 7 (Samba en inbox-drop met de wachtende inbox van 0.11.0).

## Afronding

8. [x] Bevindingen → `IDEAS.md` of nieuw werkpakket; `werk/STATUS.md` afvinken.
