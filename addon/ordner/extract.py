"""Tekstextractie en OCR via externe tools (pakket 04).

Alle subprocess-aanroepen lopen via `run_cmd`; tests vervangen uitsluitend die
functie. De overige functies roepen `run_cmd` altijd via de module-globale naam
aan, zodat monkeypatchen werkt.
"""

from __future__ import annotations

import asyncio
import logging
import re
import tempfile
from pathlib import Path

log = logging.getLogger(__name__)

MIN_TEKENS_PER_PAGINA = 50
AFBEELDINGEN = {".jpg", ".jpeg", ".png", ".heic"}


class ExtractieFout(Exception):
    """Extractie van een bestand is mislukt of onmogelijk."""


async def run_cmd(args: list[str], timeout: float = 600) -> tuple[int, bytes, bytes]:
    """Enige subprocess-ingang: voert `args` uit en geeft (rc, stdout, stderr) terug."""
    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError as e:
        raise ExtractieFout(f"programma niet gevonden: {args[0]}") from e
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout)
    except asyncio.TimeoutError as e:
        proc.kill()
        await proc.wait()
        raise ExtractieFout(f"timeout na {timeout}s: {args[0]}") from e
    return proc.returncode or 0, stdout, stderr


def _normaliseer(tekst: str) -> str:
    """Regeleinden en paginascheiders normaliseren, trailing whitespace en lege-regel-runs inkorten."""
    tekst = tekst.replace("\r\n", "\n").replace("\f", "\n")
    regels = [regel.rstrip() for regel in tekst.split("\n")]
    tekst = "\n".join(regels)
    # meer dan twee lege regels achter elkaar (>= 4 newlines) -> precies twee lege regels
    return re.sub(r"\n{4,}", "\n\n\n", tekst)


def _decode(data: bytes) -> str:
    return data.decode("utf-8", "replace")


async def _paginas(pad: Path) -> int:
    rc, out, _ = await run_cmd(["pdfinfo", str(pad)])
    if rc != 0:
        return 1
    m = re.search(r"^Pages:\s+(\d+)", _decode(out), re.M)
    return int(m.group(1)) if m else 1


async def extract_pdf(pad: Path, talen: str) -> str:
    """Tekstlaag via pdftotext; te weinig tekst per pagina -> OCR via ocrmypdf-sidecar."""
    paginas = await _paginas(pad)

    rc, out, _ = await run_cmd(["pdftotext", "-layout", str(pad), "-"])
    tekst = _normaliseer(_decode(out)) if rc == 0 else ""
    if len(tekst.strip()) >= MIN_TEKENS_PER_PAGINA * paginas:
        return tekst

    log.info("te weinig tekstlaag in %s (%d pagina's), OCR via ocrmypdf", pad.name, paginas)
    with tempfile.TemporaryDirectory() as tmp:
        sidecar = Path(tmp) / "tekst.txt"
        uit = Path(tmp) / "uit.pdf"
        rc, _, err = await run_cmd(
            ["ocrmypdf", "--force-ocr", "-l", talen, "--sidecar", str(sidecar), str(pad), str(uit)]
        )
        if rc != 0:
            raise ExtractieFout(f"ocrmypdf faalde ({rc}): {_decode(err[-500:]).strip()}")
        if not sidecar.is_file():
            raise ExtractieFout(f"ocrmypdf leverde geen sidecar op voor {pad.name}")
        return _normaliseer(sidecar.read_text("utf-8", errors="replace"))


def _heic_naar_jpg(pad: Path, tmpdir: Path) -> Path:
    """Zet een .heic om naar een tijdelijke .jpg (tesseract kan geen heic lezen)."""
    import pillow_heif
    from PIL import Image

    pillow_heif.register_heif_opener()
    doel = tmpdir / (pad.stem + ".jpg")
    Image.open(pad).convert("RGB").save(doel, quality=90)
    return doel


async def extract_afbeelding(pad: Path, talen: str) -> str:
    """OCR van een afbeelding via tesseract; .heic wordt eerst naar .jpg omgezet."""
    with tempfile.TemporaryDirectory() as tmp:
        bron = _heic_naar_jpg(pad, Path(tmp)) if pad.suffix.lower() == ".heic" else pad
        rc, out, err = await run_cmd(["tesseract", str(bron), "-", "-l", talen])
        if rc != 0:
            raise ExtractieFout(f"tesseract faalde ({rc}): {_decode(err[-500:]).strip()}")
        return _normaliseer(_decode(out))


async def extract_bestand(pad: Path, talen: str) -> str:
    """Dispatch op extensie; niet-extraheerbare bestanden geven ExtractieFout."""
    ext = pad.suffix.lower()
    if ext == ".pdf":
        return await extract_pdf(pad, talen)
    if ext in AFBEELDINGEN:
        return await extract_afbeelding(pad, talen)
    raise ExtractieFout(f"niet extraheerbaar: {pad.name}")
