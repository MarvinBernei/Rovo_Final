"""Versionierter deutscher Sprachkatalog: Synonyme und Slots, keine freie Toolwahl."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from importlib.resources import files

SAFE_NEGATIONS = {
    "stop",
    "cancel",
    "tracking.disable",
    "camera.disable",
    "privacy.enable",
    "llm.disable",
}


def normalize(text: str, fold: bool = True) -> str:
    text = re.sub(r"[,.!?;:]", " ", text.lower() if fold else text)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"^(?:hey\s+)?rovo\s*", "", text, flags=re.I)
    text = re.sub(r"\s+rovo$", "", text, flags=re.I)
    text = re.sub(r"^bitte\s+|\s+bitte$", "", text, flags=re.I)
    return text.strip()


@lru_cache(maxsize=1)
def entries() -> list[dict]:
    document = json.loads(
        files("rovo").joinpath("catalog.json").read_text(encoding="utf-8")
    )
    if document.get("schema_version") != 1:
        raise ValueError("Unbekannte Sprachkatalogversion.")
    seen: set[str] = set()
    for entry in document["intents"]:
        if entry["negation_safe"] and entry["intent"] not in SAFE_NEGATIONS:
            raise ValueError("Unzulässige Negationsausnahme im Sprachkatalog.")
        for phrase in entry["phrases"]:
            phrase = normalize(phrase)
            if phrase in seen:
                raise ValueError("Doppelte Sprachformulierung im Katalog: " + phrase)
            seen.add(phrase)
    return document["intents"]


def match(text: str, safe_only: bool = False) -> tuple[str, dict, bool] | None:
    value = normalize(text, fold=False)
    for entry in entries():
        if safe_only and not entry["negation_safe"]:
            continue
        for phrase in entry["phrases"]:
            template = normalize(phrase)
            pattern = re.escape(template)
            # Ausschließlich benannte, begrenzte Freitextslots. Winkel/Zeit parsern separat.
            for slot in ("name", "fact", "topic", "query"):
                pattern = pattern.replace(
                    re.escape("{" + slot + "}"), f"(?P<{slot}>.{{1,120}})"
                )
            found = re.fullmatch(pattern, value, flags=re.I)
            if found:
                slots = found.groupdict()
                if slots:
                    raw = re.sub(r"\s+", " ", text.strip().rstrip(".!?"))
                    raw = re.sub(r"^(?:hey\s+)?rovo[, ]*", "", raw, flags=re.I)
                    raw = re.sub(r"^bitte\s+|\s+bitte$", "", raw, flags=re.I)
                    original = re.fullmatch(pattern, raw, flags=re.I)
                    if original:
                        slots = original.groupdict()
                return (
                    entry["intent"],
                    {**entry["args"], **slots},
                    entry["negation_safe"],
                )
    return None


def answer(text: str) -> str | None:
    hit = match(text)
    return hit[1].get("reply") if hit and hit[0] == "local.answer" else None
