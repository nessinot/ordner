# Ordner

## Wat is Ordner

Vroeger gingen afschriften, nota's, bonnetjes en andere belangrijke papieren in een ordner. Een map per jaar, een tabblad per onderwerp, en je wist dat alles er lag als je het nodig had. Ordner brengt die eenvoud terug: een digitale ordner voor je documenten.

Je uploadt een pdf of foto, controleert de titel en datum die Ordner uit de tekst heeft gelezen, en Ordner bewaart het document als gewone bestanden in `/share/ordner`. Elk document krijgt een eigen map met het origineel erin. De tekst van pdf's en foto's wordt gelezen (OCR) en als gewoon tekstbestand ernaast gezet, zodat je later op elk woord kunt zoeken. De gegevens over het document staan in één leesbaar `meta.md`.

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

## Uploaden

Uploaden gaat in twee stappen.

1. **Bestanden kiezen.** Kies een of meer pdf's of foto's; samen vormen ze één document. Minstens één bestand is verplicht. Na "Verder" leest Ordner de tekst van de bestanden (bij foto's en scans kan dat even duren; de pagina meldt "tekst lezen…").
2. **Gegevens controleren.** Je ziet de gekozen bestanden en een formulier dat al is ingevuld: de titel (de naam van het bedrijf of de instantie uit de tekst; leeg als er geen herkenbare naam in staat), de documentdatum (uit de tekst, anders vandaag; een label eronder zegt welke van de twee), en de tags (het documenttype, zoals `factuur`). De omschrijving is altijd leeg. Pas aan wat niet klopt en kies **Opslaan**. Let op de datum en de titel: samen bepalen ze de mapnaam, en die verandert daarna niet meer.

Tot je op Opslaan drukt wordt er niets bewaard. **Annuleren** gooit de gekozen bestanden weg; het tabblad sluiten of de add-on herstarten heeft hetzelfde effect. Een niet afgemaakte upload verloopt na een uur; kom je daarna terug, dan vraagt Ordner je de bestanden opnieuw te kiezen. Na Opslaan kom je op de documentpagina met de bevestiging "Opgeslagen".

Een bestand toevoegen aan een bestaand document doe je op de documentpagina.

## Documentdatum

In de tweede stap van het uploaden staat de documentdatum al ingevuld. Ordner leest daarvoor de tekst van het document en zoekt daarin naar een datum achter een van deze woorden, in deze volgorde: **factuurdatum**, **notadatum**, **orderdatum**, **dagtekening**, **datum**. Het woord mag met of zonder spatie geschreven zijn ("factuur datum") en er mag een dubbele punt achter staan. De datum staat direct achter het woord op dezelfde regel, of, zoals in tabellen op facturen, in dezelfde kolom op de regel eronder; "vervaldatum" of "betaaldatum" tellen niet mee. Herkende notaties: `12-03-2024`, `12/03/2024`, `12.03.2024`, `2024-03-12`, `12 maart 2024`, `12 mrt 2024` en een tweecijferig jaar. Staat er geen bruikbare datum in, dan wordt het de dag van uploaden.

De gevonden datum bepaalt ook de mapnaam, dus een oude factuur die je nu inscant komt in de juiste jaarmap terecht. Laat je de voorgestelde datum staan, dan onthoudt Ordner dat hij uit de tekst komt (of van de dag van uploaden, als er niets gevonden is); wijzig je hem, dan geldt hij als door jou ingevuld.

Op de documentpagina zie je achter de datum een label **datum uit tekst** of **datum van upload** als de datum niet door jou is ingevuld. Wijzig je de datum zelf, dan verdwijnt het label en wordt hij nooit meer automatisch aangepast. Documenten uit de inbox krijgen altijd op deze manier hun datum.

## Zoeken

Het startscherm toont de 20 nieuwste documenten. Staan er meer in het archief, dan zegt een regel onder de lijst hoeveel er in totaal zijn; oudere documenten vind je via het zoekveld.

Zoeken werkt op alle woorden tegelijk (elk woord moet voorkomen), zonder onderscheid in hoofdletters, over titel, omschrijving, tags, documentdatum, notities en de gelezen tekst van de bestanden. Een datum of jaartal (`2024`, `2024-03`) telt als zoekwoord, dus `energie 2024` vindt alleen energiedocumenten uit 2024. Bij meer dan 50 treffers worden de 50 nieuwste getoond; de kop noemt het echte aantal en onder de lijst staat een link **Toon alle** voor de volledige lijst. Meestal is een extra zoekwoord sneller.

Tags staan als labels in de resultatenlijst en op de documentpagina. Klik op een label om alle documenten met die tag te zien; de tag komt dan in het zoekveld in plaats van je vorige zoekopdracht. Een tag met een spatie (bijvoorbeeld `gemeente amsterdam`) zoekt op beide woorden.

Open je een document vanuit de resultaten, dan staat bovenaan de documentpagina **Terug naar zoekresultaten**; die brengt je terug bij dezelfde zoekopdracht, ook na opslaan of verwijderen. Vanuit het startscherm heet die link **Terug naar overzicht**.

## Inbox

Bestanden die je in `/share/ordner/_inbox/` zet worden automatisch opgenomen: elke vijf seconden kijkt Ordner of er een bestand ligt dat niet meer groeit (twee keer achter elkaar dezelfde grootte). Dan wordt er een nieuw document van gemaakt:

- titel = de naam van het bedrijf of de instantie uit de tekst (zie "Titel en tags uit de tekst"); is die niet te vinden, dan de bestandsnaam zonder extensie, waarbij `_` en `-` spaties worden;
- tags = het documenttype uit de tekst, bijvoorbeeld `factuur` of `polis`;
- documentdatum = de datum uit de tekst, anders vandaag (zie "Documentdatum");
- het bestand wordt verplaatst naar de nieuwe documentmap; is de tekst al gelezen, dan hoeft er geen OCR meer te draaien.

Handig voor scanners, e-mailregels of een gedeelde map op de telefoon. Controleer na opname de titel, tags en datum op de documentpagina; de naam uit de tekst is een gok, en bij een bankafschrift kan dat je eigen naam zijn.

## Titel en tags uit de tekst

Ordner probeert uit de gelezen tekst af te leiden van wie een document komt en wat voor document het is. Bij uploaden staan die als voorstel in het formulier van de tweede stap (onder de titel staat dan "voorstel uit het document"); de inbox gebruikt ze direct.

De **titel** is alleen de naam van de afzender, dus "Eneco Services B.V." of "Gemeente Amsterdam", nooit het soort document of een jaartal. Ordner kijkt in deze volgorde en neemt het eerste wat lukt:

1. Een titel die je al eerder in het archief hebt gebruikt en die letterlijk in de tekst voorkomt. Heb je eenmaal "Eneco" getypt, dan wordt dat bij de volgende Eneco-factuur herkend.
2. De naam achter "t.n.v." of "ten name van", zoals bij de betaalgegevens op een factuur.
3. De eerste regel met een rechtsvorm (B.V., N.V., VOF, U.A.) of een instantiewoord (Gemeente, Stichting, Vereniging, Waterschap, Provincie, Coöperatie, Ministerie, Belastingdienst, Bank, Verzekeraar, Ziekenhuis, Universiteit, Hogeschool).
4. Bij een korte tekst, zoals een kassabon, de eerste regel met tekst.

Bij een langere brief zonder zo'n aanknopingspunt blijft de titel leeg (bij uploaden: een leeg veld dat je zelf invult; in de inbox: de bestandsnaam), want de bovenste regel van een brief is meestal de ontvanger. Hoofdletters blijven zoals ze in de tekst staan.

De **tags** zijn de documenttypen die als kopje in de tekst staan: factuur, creditnota, offerte, polis, beschikking, nota, bon (ook kassabon), herinnering (ook betalingsherinnering), aanmaning, contract, overeenkomst, aanslag, jaaroverzicht, jaarafrekening en garantie (garantiebewijs). Het woord moet een regel of kolom beginnen ("Factuur nr. 123" telt, "Factuurdatum" of "deze factuur" niet).

De omschrijving wordt nooit automatisch ingevuld. Klopt een voorstel niet, pas het dan aan vóór het opslaan, of later op de documentpagina; de mapnaam verandert door een latere wijziging niet.

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
