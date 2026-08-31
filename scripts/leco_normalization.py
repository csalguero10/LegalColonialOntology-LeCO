#!/usr/bin/env python3
"""Shared normalization helpers for LeCO corpus migration/conversion."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import re
import unicodedata
import yaml


def _plain(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = re.sub(r"\s+", " ", value).strip().casefold()
    return value


def default_profile_path() -> Path:
    return Path(__file__).resolve().parents[1] / "mapping" / "office_normalization.yaml"


@lru_cache(maxsize=8)
def load_office_profile(path: str | None = None) -> dict:
    profile_path = Path(path) if path else default_profile_path()
    return yaml.safe_load(profile_path.read_text(encoding="utf-8"))


@lru_cache(maxsize=8)
def office_variant_index(path: str | None = None) -> dict[str, dict[str, str]]:
    profile = load_office_profile(path)
    index: dict[str, dict[str, str]] = {}
    for entry in profile.get("entries", []):
        target = entry["target"]
        preferred = entry.get("preferred_label", target)
        note = entry.get("note", "")
        variants = entry.get("variants", {})
        for variant, kind in variants.items():
            key = _plain(variant)
            if key in index and index[key]["target"] != target:
                raise ValueError(f"Office normalization collision for {variant!r}")
            index[key] = {
                "target": target,
                "preferred_label": preferred,
                "normalization_kind": str(kind),
                "note": note,
                "matched_variant": variant,
            }
    return index


def normalize_office(value: str, path: str | None = None) -> dict[str, str] | None:
    """Return normalization metadata without altering the source surface string."""
    return office_variant_index(path).get(_plain(value))


def office_type_local_name(value: str, path: str | None = None) -> str | None:
    result = normalize_office(value, path)
    return result["target"] if result else None


__all__ = [
    "normalize_office",
    "office_type_local_name",
    "load_office_profile",
    "office_variant_index",
]
