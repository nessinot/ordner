"""Controle van de add-on-bestanden (pakket 10) en de add-on-repository (pakket 13)."""

from __future__ import annotations

from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
ROOT = REPO / "addon"


def test_config_yaml() -> None:
    config = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    assert config["slug"] == "ordner"
    assert config["ingress"] is True
    assert config["ingress_port"] == 8099
    assert "share:rw" in config["map"]
    assert set(config["options"]) <= set(config["schema"])


def test_build_yaml() -> None:
    build = yaml.safe_load((ROOT / "build.yaml").read_text(encoding="utf-8"))
    config = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    assert set(build["build_from"]) == set(config["arch"])


def test_run_sh_lf() -> None:
    inhoud = (ROOT / "run.sh").read_bytes()
    assert b"\r" not in inhoud
    assert inhoud.startswith(b"#!/usr/bin/with-contenv bashio\n")
    assert b"ORDNER_DATA=/share/ordner" in inhoud


def test_repository_yaml() -> None:
    repo = yaml.safe_load((REPO / "repository.yaml").read_text(encoding="utf-8"))
    assert repo["name"]
    assert repo["url"].startswith("https://")
    assert (ROOT / "config.yaml").is_file()
