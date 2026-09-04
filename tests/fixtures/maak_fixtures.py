"""Maakt de testbestanden voor de e2e-lagen deterministisch aan (pakket 12).

Draaien: `python tests/fixtures/maak_fixtures.py`. Gebruikt alleen Pillow en pillow-heif.
De gegenereerde bestanden worden meegecommit; dit script is er om ze te kunnen reproduceren.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HIER = Path(__file__).resolve().parent

PDF_TEKST = "Ordner testdocument FACTUURNUMMER 20260903"
AFBEELDING_TEKST = "ORDNER SCANTEST BONNETJE"


def maak_tekst_pdf(doel: Path) -> None:
    """Minimale PDF 1.4 met echte tekstlaag (Helvetica), handmatig uitgeschreven inclusief xref."""
    stream = f"BT /F1 20 Tf 50 720 Td ({PDF_TEKST}) Tj ET".encode("ascii")
    objecten = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    uit = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for nummer, inhoud in enumerate(objecten, start=1):
        offsets.append(len(uit))
        uit += f"{nummer} 0 obj\n".encode("ascii") + inhoud + b"\nendobj\n"
    xref_start = len(uit)
    uit += f"xref\n0 {len(objecten) + 1}\n".encode("ascii")
    uit += b"0000000000 65535 f \n"
    for offset in offsets:
        uit += f"{offset:010d} 00000 n \n".encode("ascii")
    uit += f"trailer\n<< /Size {len(objecten) + 1} /Root 1 0 R >>\nstartxref\n{xref_start}\n%%EOF\n".encode("ascii")
    doel.write_bytes(bytes(uit))


def maak_afbeelding() -> Image.Image:
    """1200x400, wit, grote zwarte letters: groot en contrastrijk zodat Tesseract het zeker leest."""
    img = Image.new("RGB", (1200, 400), "white")
    tekenaar = ImageDraw.Draw(img)
    font = ImageFont.load_default(size=72)
    links, boven, rechts, onder = tekenaar.textbbox((0, 0), AFBEELDING_TEKST, font=font)
    x = (img.width - (rechts - links)) // 2 - links
    y = (img.height - (onder - boven)) // 2 - boven
    tekenaar.text((x, y), AFBEELDING_TEKST, fill="black", font=font)
    return img


def main() -> None:
    import pillow_heif

    pillow_heif.register_heif_opener()

    maak_tekst_pdf(HIER / "tekst.pdf")
    img = maak_afbeelding()
    img.save(HIER / "foto.png", optimize=True)
    img.save(HIER / "foto.jpg", quality=85)
    img.save(HIER / "foto.heic", quality=80)
    img.save(HIER / "scan.pdf")  # afbeelding-pdf zonder tekstlaag: het ocrmypdf-pad
    for naam in ("tekst.pdf", "foto.png", "foto.jpg", "foto.heic", "scan.pdf"):
        print(f"{naam}: {(HIER / naam).stat().st_size} bytes")


if __name__ == "__main__":
    main()
