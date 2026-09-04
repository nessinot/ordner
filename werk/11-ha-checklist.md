# Pakket 11 — HA-checklist (handmatig, kort)

Alles wat met een browser of Docker te testen is, zit in pakket 12 en draait automatisch. Wat overblijft heeft een echte Home Assistant-installatie of een echte telefoon nodig. Dit voert Bas zelf uit, ná pakket 13.

**Vereist:** pakket 13 gecommit en gepusht, repo publiek; bij voorkeur `pytest -m container` groen (anders test je de container-laag hier voor het eerst).

## Home Assistant

1. [ ] Instellingen › Add-ons › Add-on store › ⋮ › Repositories › `https://github.com/nessinot/ordner` toevoegen → sectie "Ordner" → Installeren. Build duurt enkele minuten.
2. [ ] Starten; log toont een reconcile-rapport en `Uvicorn running`, geen tracebacks. "Toon in zijbalk" aan → menu-item "Ordner" opent de zoekpagina en de nav-links werken onder het echte Ingress-token.
3. [ ] HA-backup maken → `/share/ordner` zit erin.

## Telefoon (HA-app)

4. [ ] Uploaden → foto uit de fotorol (HEIC) → titel → Opslaan. Voortgangsbalk zichtbaar, landt op de documentpagina, wordt vanzelf `done`.
5. [ ] **iOS: pdf inline** — toont `<object>` de pdf in de HA-app-webview? Zo niet: werkt de "Open"-link? Resultaat noteren in `IDEAS.md` als inline niet werkt (bekend zwak punt).
6. [ ] Afbeelding inline zichtbaar; zoeken vanaf de telefoon werkt.

## Samba (optioneel, ter bevestiging)

7. [ ] `/share/ordner/JJJJ/…` is leesbaar in de Verkenner: `meta.md`, origineel, `.txt`. Een bestand in `_inbox/` droppen vanaf de pc verschijnt binnen ~10 s in de UI.

## Afronding

8. [ ] Bevindingen → `IDEAS.md` of nieuw werkpakket; `werk/STATUS.md` afvinken.
