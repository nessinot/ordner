from __future__ import annotations

import pytest

from ordner.slug import maak_slug


@pytest.mark.parametrize(
    ("invoer", "verwacht"),
    [
        ("WOZ-beschikking 2026", "woz-beschikking-2026"),
        ("Café Zürich — bon", "cafe-zurich-bon"),
        ("   ", "document"),
        ("", "document"),
        ("!!!", "document"),
        ("--Factuur--", "factuur"),
        ("Foo   bar___baz", "foo-bar-baz"),
    ],
)
def test_maak_slug_voorbeelden(invoer: str, verwacht: str) -> None:
    assert maak_slug(invoer) == verwacht


def test_maak_slug_afkappen() -> None:
    slug = maak_slug("a" * 80)
    assert len(slug) == 60
    assert slug == "a" * 60


def test_maak_slug_afkappen_eindigt_niet_op_streepje() -> None:
    slug = maak_slug("x" * 59 + " y")
    assert len(slug) <= 60
    assert not slug.endswith("-")
    assert slug == "x" * 59
