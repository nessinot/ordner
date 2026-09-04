# Pakket 15c — Tags als klikbare labels

> **Agent-prompt:** Lees `werk/00-contract.md` en `werk/15c-tags-als-labels.md`. Bouw alleen wat hieronder staat, draai `pytest`, bump de versie naar 0.7.0 met release notes in `addon/CHANGELOG.md`, commit als `pakket 15c: tags als labels` en vink af in `werk/STATUS.md`. Pas daarna 15a.

**Doel:** Tags zijn nu alleen zichtbaar op de documentpagina, als stille badges. Ze worden afgeronde labels in de resultatenlijst én op de documentpagina, en klikken op een label zoekt op dat woord. Daarmee krijgen de tags die 15a en 15b straks automatisch voorstellen (documenttype: factuur, polis, …) direct nut als filter.

**Lees eerst:** `werk/00-contract.md` (Zoeken, Routenamen), `addon/ordner/web/routes.py` (`Kaart`, route `zoeken`), `addon/ordner/web/templates/zoeken.html`, `document.html`, `addon/ordner/web/static/style.css` (secties `kaarten` en `badges`).

## Beslissingen (afgestemd met Bas op 2026-09-04)

1. **Waar.** Labels staan in elke kaart van de resultatenlijst (startscherm "Recent" én zoekresultaten) en op de documentpagina onder de titel, waar ze nu al als badges staan. Volgorde zoals in `meta.md`.
2. **Klikken = zoeken op dat woord.** Een label is een link naar `url_for('zoeken')?q=<tag>`. De tag vervangt de huidige zoekopdracht; niet toevoegen aan de bestaande query. Een tag met een spatie ("gemeente amsterdam") werkt vanzelf als AND-zoekopdracht. Vanaf de documentpagina geldt hetzelfde; de terugknop van het volgende document wijst dan naar die tag-zoekopdracht (bestaand `herkomst`-mechanisme, geen extra werk).
3. **Geen geneste links.** De kaartrij is nu één `<a class="rij">`; een link erin is ongeldige HTML. De rij wordt een `div.rij` waarin alleen de titel een `<a>` is die via een `::after`-overlay de hele kaart klikbaar houdt (stretched link; `.kaart` heeft al `position: relative`). De tag-labels en de snippet liggen met `position: relative; z-index` boven de overlay, zodat een klik op een label naar de zoekopdracht gaat en een klik ergens anders in de kaart naar het document. Gedragswijziging: ook de snippet wordt daarmee klikbaar (opent het document); dat is gewenst.
4. **Plaats in de kaart.** Op brede schermen (bestaande media query in `style.css`) een eigen kolom rechts, vóór de datum: grid `auto 1fr auto auto`. Op smalle schermen wrappen de labels onder de titel/omschrijving in de tekstkolom. Eén element `span.tags` met daarin `a.badge.badge-tag`; de CSS-positie doet de rest. Veel tags mogen wrappen; niet afkappen.
5. **Uiterlijk.** De bestaande `.badge-tag`-stijl (`--actief`-tint) blijft; als link krijgt hij `text-decoration: none` en een hover-toestand (iets donkerder tint). Geen icoon, geen `#`.
6. **Geen tagbeheer.** Geen tag-overzicht, geen hernoemen, geen telling per tag; dat blijft `IDEAS.md`. Ook geen normalisatie van hoofdletters: het label toont de tag zoals hij in `meta.md` staat, en de zoekopdracht is toch hoofdletterongevoelig.
7. **Interface.** `Kaart` krijgt een veld `tags: list[str]` (default lege lijst), gevuld uit `entry.meta.tags`; `search.Treffer` verandert niet (de route heeft de `DocEntry` al bij de hand). Geen contractwijziging behalve dat veld; noteren onder "Wijzigingen op het contract".

## Maakt / wijzigt

- `web/routes.py`: `Kaart.tags`, vullen in beide takken van `zoeken`.
- `web/templates/zoeken.html`: `div.rij` met `a.titel` als stretched link, `span.tags` met labels-als-links, snippet buiten de link maar in de kaart.
- `web/templates/document.html`: bestaande `p.badges` → labels worden links naar `url_for('zoeken')?q=…`.
- `web/static/style.css`: stretched link (`.kaart .titel a::after`), z-index voor `.tags` en `.snippet`, gridkolom op breed scherm, hover voor `a.badge-tag`.
- Tests (`tests/test_web.py`): label in het zoekresultaat met `href` naar `?q=<tag>` (urlencoded, met en zonder Ingress-prefix); label op de documentpagina; kaart zonder tags heeft geen `span.tags`; geen `<a` binnen `<a` (eenvoudige regex-check op de HTML van de zoekpagina).
- e2e (`tests/e2e/test_browser.py`): in `test_zoeken` (of een nieuwe test) op een label klikken en controleren dat het zoekveld de tag bevat en het document in de lijst staat. Alleen als de bestaande e2e-opzet dat zonder gedoe toelaat; anders noteren in `STATUS.md`.
- Docs: `addon/DOCS.md` sectie "Zoeken" (één alinea: klik op een tag om erop te zoeken), `addon/CHANGELOG.md` 0.7.0, `addon/config.yaml` version 0.7.0, `werk/STATUS.md` (afvinken + Releases-regel), `werk/00-contract.md` (Wijzigingen: `Kaart.tags`).

## Let op

- **Ingress:** de tag-links via de Jinja-global `url_for('zoeken')` + `?q=`, nooit een hardgecodeerd `/?q=`; `test_ingress_prefix_in_alle_links` moet blijven slagen.
- **Urlencoding:** `{{ tag|urlencode }}` in de href, de tekst van het label ongecodeerd.
- **Toegankelijkheid:** de stretched link mag de titel-link niet onleesbaar maken voor screenreaders; de `<a>` bevat de titeltekst zelf, niet een leeg element.

## Bekende beperkingen / vervolg

- Klik op een tag vervangt de zoekopdracht. Combineren ("huidige zoekopdracht + tag") is later één wijziging in de href.
- Geen tag-overzicht (welke tags bestaan, hoe vaak). Blijft in `IDEAS.md`.
