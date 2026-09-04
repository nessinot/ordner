# Ordner

## Wat is Ordner

Vroeger gingen afschriften, nota's, bonnetjes en andere belangrijke papieren in een ordner. Een map per jaar, een tabblad per onderwerp, en je wist dat alles er lag als je het nodig had. Ordner brengt die eenvoud terug: een digitale ordner voor je documenten.

Je uploadt een pdf of foto, geeft een titel en datum, en Ordner bewaart het document als gewone bestanden in `/share/ordner`. Elk document krijgt een eigen map met het origineel erin. De tekst van pdf's en foto's wordt gelezen (OCR) en als gewoon tekstbestand ernaast gezet, zodat je later op elk woord kunt zoeken. De gegevens over het document staan in één leesbaar `meta.md`.

Kernprincipe: **de bestanden op schijf zijn de waarheid**. Er is geen database, niets om te ontcijferen. Alles wat Ordner weet staat in mappen en tekstbestanden die je ook zonder de add-on kunt lezen, kopiëren en back-uppen, bijvoorbeeld via Samba of de Verkenner.

## Mapstructuur

Per document één map, gegroepeerd per jaar. De mapnaam is de documentdatum plus een korte versie van de titel:

```
/share/ordner/
  _inbox/                          # hier bestanden droppen om ze automatisch op te nemen
  _prullenbak/                     # verwijderde documenten
  2026/
    2026-03-01_woz-beschikking-2026/
      meta.md                      # titel, datum, tags, bestandslijst, notities
      beschikking.pdf              # het origineel, ongewijzigd
      beschikking.pdf.txt          # de gelezen tekst van beschikking.pdf
      foto.heic
      foto.heic.txt
```

De mapnaam wordt bij aanmaak bepaald en daarna **nooit meer hernoemd**, ook niet als je later de titel of datum aanpast. Zo blijven links, back-ups en Samba-snelkoppelingen geldig. De actuele titel en datum staan altijd in `meta.md`.

Bij elk origineel (`factuur.pdf`, `bon.jpg`) hoort een tekstbestand met dezelfde naam plus `.txt` (`factuur.pdf.txt`). Dat is de tekst waarop gezocht wordt. Bestanden met een andere extensie (bijvoorbeeld `.docx` of `.eml`) worden wel bewaard en in de bestandslijst opgenomen, maar er wordt geen tekst uit gelezen.

## `meta.md` uitgelegd

```markdown
---
titel: WOZ-beschikking 2026
omschrijving: Gemeente, waarde peildatum 1-1-2025
documentdatum: 2026-03-01
uploaddatum: '2026-09-03T14:12'
tags: [woz, gemeente]
bestanden: [beschikking.pdf, foto.heic]
ocr: done
datumbron: gebruiker
---
Eventuele eigen notities. Deze tekst wordt meegezocht.
```

| Veld | Betekenis |
|---|---|
| `titel` | Verplicht. Wordt getoond in de lijst en meegezocht. |
| `omschrijving` | Korte toelichting, één regel. Meegezocht. |
| `documentdatum` | Verplicht, `JJJJ-MM-DD`. Datum van het document zelf, niet van het uploaden. Bepaalt de sortering. |
| `uploaddatum` | Wanneer het document is aangemaakt. Informatief. |
| `tags` | Lijst met trefwoorden. Meegezocht. |
| `bestanden` | De originelen in deze map. Wordt door Ordner bijgehouden; bestanden die je via Samba toevoegt worden bij de volgende verversing opgenomen. |
| `ocr` | `pending` (tekst wordt nog gelezen), `done` (klaar) of `failed` (mislukt, zie hieronder). |
| `datumbron` | Waar de documentdatum vandaan komt: `gebruiker` (zelf ingevuld of later gewijzigd), `tekst` (uit het document gelezen) of `upload` (geen datum gevonden, dag van uploaden). Zie "Documentdatum". |

Alles onder de tweede `---` is vrije tekst voor eigen notities en wordt meegezocht.

Je mag `meta.md` zelf bewerken in een teksteditor. Houd de drie streepjes en de veldnamen intact. Een map zonder `meta.md` krijgt er bij de volgende verversing automatisch een, met de mapnaam als titel.

## Documentdatum

Vul je bij het uploaden een datum in, dan is dat de documentdatum. Laat je het veld leeg, dan leest Ordner eerst de tekst van het document en zoekt daarin naar een datum achter een van deze woorden, in deze volgorde: **factuurdatum**, **notadatum**, **orderdatum**, **dagtekening**, **datum**. Het woord mag met of zonder spatie geschreven zijn ("factuur datum") en er mag een dubbele punt achter staan. De datum staat direct achter het woord op dezelfde regel, of, zoals in tabellen op facturen, in dezelfde kolom op de regel eronder; "vervaldatum" of "betaaldatum" tellen niet mee. Herkende notaties: `12-03-2024`, `12/03/2024`, `12.03.2024`, `2024-03-12`, `12 maart 2024`, `12 mrt 2024` en een tweecijferig jaar. Staat er geen bruikbare datum in, dan wordt het de dag van uploaden.

De gevonden datum bepaalt ook de mapnaam, dus een oude factuur die je nu inscant komt in de juiste jaarmap terecht. Omdat de tekst hiervoor eerst gelezen moet worden, duurt opslaan zonder datum bij foto's en scans wat langer; de uploadpagina meldt "tekst lezen…".

Op de documentpagina zie je achter de datum een label **datum uit tekst** of **datum van upload** als de datum niet door jou is ingevuld. Wijzig je de datum zelf, dan verdwijnt het label en wordt hij nooit meer automatisch aangepast. Documenten uit de inbox krijgen altijd op deze manier hun datum.

## Zoeken

Het startscherm toont de 20 nieuwste documenten. Staan er meer in het archief, dan zegt een regel onder de lijst hoeveel er in totaal zijn; oudere documenten vind je via het zoekveld.

Zoeken werkt op alle woorden tegelijk (elk woord moet voorkomen), zonder onderscheid in hoofdletters, over titel, omschrijving, tags, documentdatum, notities en de gelezen tekst van de bestanden. Een datum of jaartal (`2024`, `2024-03`) telt als zoekwoord, dus `energie 2024` vindt alleen energiedocumenten uit 2024. Bij meer dan 50 treffers worden de 50 nieuwste getoond; de kop noemt het echte aantal en onder de lijst staat een link **Toon alle** voor de volledige lijst. Meestal is een extra zoekwoord sneller.

Open je een document vanuit de resultaten, dan staat bovenaan de documentpagina **Terug naar zoekresultaten**; die brengt je terug bij dezelfde zoekopdracht, ook na opslaan of verwijderen. Vanuit het startscherm heet die link **Terug naar overzicht**.

## Inbox

Bestanden die je in `/share/ordner/_inbox/` zet worden automatisch opgenomen: elke vijf seconden kijkt Ordner of er een bestand ligt dat niet meer groeit (twee keer achter elkaar dezelfde grootte). Dan wordt er een nieuw document van gemaakt:

- titel = bestandsnaam zonder extensie, waarbij `_` en `-` spaties worden;
- documentdatum = vandaag;
- het bestand wordt verplaatst naar de nieuwe documentmap en de OCR start.

Handig voor scanners, e-mailregels of een gedeelde map op de telefoon. Pas na opname de titel en datum aan op de documentpagina.

## Prullenbak

"Verwijderen" op de documentpagina verplaatst de hele documentmap naar `/share/ordner/_prullenbak/`. Er wordt niets echt gewist. Terugzetten doe je door de map met Samba of de Verkenner terug te verplaatsen naar de juiste jaarmap en daarna "Cache verversen" te gebruiken op de beheerpagina. Definitief opruimen doe je door de map uit `_prullenbak` te verwijderen.

## Beheerpagina

De beheerpagina toont tellingen (totaal, OCR klaar, wacht, mislukt), wat er nu in de wachtrij staat en het rapport van de laatste verversing.

De knop **Cache verversen en ontbrekende tekst extraheren** doet in één keer:

1. alle documentmappen opnieuw inlezen in het geheugen;
2. de bestandslijst in `meta.md` gelijktrekken met wat er echt in de map staat;
3. voor elk pdf- of afbeeldingsbestand zonder `.txt` de tekst laten lezen;
4. `meta.md` aanmaken voor mappen die er geen hebben;
5. de inbox verwerken.

Dit gebeurt automatisch bij het starten van de add-on en daarna elke `reconcile_interval` seconden (standaard vijf minuten). Gebruik de knop als je iets via Samba hebt gewijzigd en niet wilt wachten.

## Opties

| Optie | Standaard | Betekenis |
|---|---|---|
| `ocr_talen` | `nld+eng` | Talen voor Tesseract, gescheiden door `+`. Alleen `nld` en `eng` zijn in de add-on geïnstalleerd. |
| `ocr_parallel` | `2` | Hoeveel bestanden tegelijk gelezen worden. Verhogen op een snelle machine, verlagen als de add-on te veel geheugen gebruikt. |
| `reconcile_interval` | `300` | Seconden tussen automatische verversingen. |

Na een wijziging de add-on herstarten.

## Als OCR faalt

Krijgt een document de status `failed`, dan is de tekst van minstens één bestand niet gelezen. Oorzaken: een beschadigde of met wachtwoord beveiligde pdf, een te grote afbeelding, of een time-out (tien minuten per bestand). Details staan in het add-on-log.

Wat je kunt doen:

- **OCR opnieuw** op de documentpagina: verwijdert de bestaande `.txt`-bestanden van dat document, zet de status op `pending` en plaatst alle bestanden opnieuw in de wachtrij.
- **`.txt` handmatig plaatsen**: zet zelf een tekstbestand naast het origineel met de naam `<bestandsnaam>.txt` (bijvoorbeeld `factuur.pdf.txt`). Bij de volgende verversing wordt het opgepikt en telt het document als `done`. Zo kun je ook tekst toevoegen voor bestanden die Ordner niet zelf kan lezen.
- **Status resetten**: `ocr: failed` in `meta.md` wijzigen in `ocr: pending` heeft hetzelfde effect als "OCR opnieuw", maar dan zonder de bestaande `.txt`-bestanden te verwijderen.

Een document met status `failed` wordt door de automatische verversing met rust gelaten, zodat een kapot bestand niet elke vijf minuten opnieuw geprobeerd wordt.

## Backup

Het hele archief staat in `/share/ordner`. De map `/share` zit standaard in een Home Assistant-backup, dus Ordner heeft geen eigen back-upmechanisme nodig. Omdat het gewone bestanden zijn, kun je de map ook los kopiëren of met een ander programma synchroniseren. De add-on zelf bewaart niets buiten deze map.
