# Pakket 04 — Extract

> **Agent-prompt:** Lees `werk/00-contract.md` en `werk/04-extract.md`. Voer pakket 04 uit. Draai `pytest`. Commit met bericht `pakket 04: extract`. Vink af in `werk/STATUS.md`.

**Doel:** tekstextractie met fallback, volledig testbaar zonder OCR-tools.

**Lees eerst:** `werk/00-contract.md` (Ontwerpbeslissingen "Extractie", Interface `extract.py`, Testfixtures `mock_cmd`).
**Vereist:** pakket 01 (gebruikt `mock_cmd`). Onafhankelijk van 02/03.

## Maakt

- `ordner/extract.py`
- `tests/test_extract.py`

## Specificatie

### `run_cmd(args, timeout=600)`
- `asyncio.create_subprocess_exec(*args, stdout=PIPE, stderr=PIPE)`.
- `stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout)`.
- `asyncio.TimeoutError` → `proc.kill()`, `await proc.wait()`, raise `ExtractieFout(f"timeout na {timeout}s: {args[0]}")`.
- `FileNotFoundError` → `ExtractieFout(f"programma niet gevonden: {args[0]}")`.
- Geeft `(proc.returncode, stdout, stderr)` terug. Roept géén andere functie uit deze module aan (zodat mocken volstaat).

Alle andere functies roepen subprocesses uitsluitend aan via de module-globale naam `run_cmd` (dus `await run_cmd([...])`, niet via een lokale referentie), zodat `monkeypatch.setattr("ordner.extract.run_cmd", ...)` werkt.

### `extract_pdf(pad, talen)`
1. `rc, out, _ = await run_cmd(["pdfinfo", str(pad)])`; pagina's via `re.search(r"^Pages:\s+(\d+)", out.decode("utf-8", "replace"), re.M)`; niet gevonden of rc ≠ 0 → 1.
2. `rc, out, err = await run_cmd(["pdftotext", "-layout", str(pad), "-"])`; rc ≠ 0 → tekst `""` (niet falen; fallback probeert OCR).
3. `tekst = _normaliseer(out.decode("utf-8", "replace"))`.
4. Als `len(tekst.strip()) >= 50 * paginas` → return `tekst`.
5. Anders in `tempfile.TemporaryDirectory()`: `sidecar = tmp/"tekst.txt"`, `uit = tmp/"uit.pdf"`; `await run_cmd(["ocrmypdf", "--force-ocr", "-l", talen, "--sidecar", str(sidecar), str(pad), str(uit)])`; rc ≠ 0 → `ExtractieFout(f"ocrmypdf faalde ({rc}): {err[-500:].decode(...)}")`; sidecar ontbreekt → `ExtractieFout`; return `_normaliseer(sidecar.read_text("utf-8", errors="replace"))`.

### `extract_afbeelding(pad, talen)`
- `.heic` (case-insensitive): `bron = _heic_naar_jpg(pad, tmpdir)` — module-functie die `pillow_heif.register_heif_opener()` aanroept en `Image.open(pad).convert("RGB").save(tmp / (pad.stem + ".jpg"), quality=90)` doet; geeft het jpg-pad terug. Anders `bron = pad`.
- `rc, out, err = await run_cmd(["tesseract", str(bron), "-", "-l", talen])`; rc ≠ 0 → `ExtractieFout`.
- return `_normaliseer(out.decode("utf-8", "replace"))`.

### `extract_bestand(pad, talen)`
Dispatch op `pad.suffix.lower()`: `.pdf` → `extract_pdf`; `.jpg .jpeg .png .heic` → `extract_afbeelding`; anders `ExtractieFout(f"niet extraheerbaar: {pad.name}")`.

### `_normaliseer(tekst)`
`\r\n` → `\n`, `\f` → `\n`, trailing whitespace per regel strippen, meer dan twee lege regels achter elkaar → twee.

## Tests (alle met `mock_cmd`, behalve de laatste)

- pdf met `pdfinfo` `Pages: 2` en `pdftotext` 200 tekens → resultaat = die tekst, geen `ocrmypdf` in `mock_cmd.calls`.
- pdf met `Pages: 3` en 100 tekens → `ocrmypdf` aangeroepen; args bevatten `--force-ocr`, `-l nld+eng` en `--sidecar`; handler schrijft de sidecar (haal het pad uit `args[args.index("--sidecar") + 1]`); resultaat = sidecar-tekst.
- `pdfinfo` zonder `Pages:`-regel → drempel 50: 60 tekens → geen OCR.
- `ocrmypdf` rc 1 → `ExtractieFout` met stderr-fragment in de melding.
- `pdftotext` rc 1 → geen exception, OCR-fallback wordt geprobeerd.
- jpg → `tesseract` aangeroepen met `-l nld+eng` en `-` als output; resultaat = stdout.
- heic → monkeypatch `ordner.extract._heic_naar_jpg` naar een functie die een leeg `.jpg` aanmaakt; controleer dat `tesseract` een `.jpg`-pad kreeg.
- `_normaliseer`: `\r\n` en `\f`.
- Onbekende extensie → `ExtractieFout`.
- Echt (zonder mock): `await run_cmd(["ordner-bestaat-niet-xyz"])` → `ExtractieFout` met "niet gevonden".

## Buiten scope

Wachtrij, `.txt` schrijven, statusbeheer (pakket 07).
