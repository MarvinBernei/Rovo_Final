"""Parser für variable Angaben und Sicherheitsregeln.

Feste Formulierungen, Synonyme und Wissensantworten stehen ausschließlich in
catalog.json. Dieser Code ergänzt nur Parametergrammatiken und Rückfragen.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .catalog import match as catalog_match
from .catalog import normalize
from .math_de import normalize_numbers


@dataclass
class Intent:
    name: str
    args: dict = field(default_factory=dict)


def parse(raw: str) -> Intent:
    # Nur einmal im Katalog suchen; Namen/Freitext behalten ihre Schreibweise.
    hit = catalog_match(raw)
    text = normalize(raw)
    if hit and (hit[0] in {"local.answer", "capabilities", "greeting"} or hit[2]):
        return Intent(hit[0], hit[1])
    if re.search(r"\b(nicht|kein|keine|keinen|niemals|ohne)\b", text):
        return Intent("negated")
    if re.search(r"\b(und|danach|anschließend)\b", text) and re.search(
        r"\b(schau|guck|dreh|lösch\w*|schalt\w*)\b", text
    ):
        return Intent(
            "clarify",
            {"reply": "Bitte nenne einen eindeutigen Gerätebefehl pro Anfrage."},
        )
    if hit:
        return Intent(hit[0], hit[1])

    # Bei Zahlen Satzzeichen erhalten: 1,5 darf nicht zu 1 5 werden.
    expression = re.sub(r"\s+", " ", raw.lower().strip().rstrip(".!?"))
    expression = re.sub(r"^(?:hey\s+)?rovo[, ]*", "", expression)
    expression = re.sub(r"^bitte\s+|\s+bitte$", "", expression)
    normalized = normalize_numbers(expression)
    if normalized in {
        "wie ist das wetter",
        "wie ist das wetter heute",
        "aktuelles wetter",
    }:
        return Intent("weather.current")

    conversion = re.fullmatch(
        r"(?:wie viel (?:sind|ist) |rechne )?(-?\d+(?:[.,]\d+)?)\s*([a-zäöüß/]+)\s+(?:in|zu)\s+([a-zäöüß/]+)(?: um)?",
        normalized,
    )
    if conversion:
        return Intent(
            "units.convert",
            {
                "value": float(conversion[1].replace(",", ".")),
                "source": conversion[2],
                "target": conversion[3],
            },
        )

    reminder = re.fullmatch(
        r"erinnere mich (täglich|werktags|am wochenende) um (\d{1,2})(?::| uhr\s*)(\d{1,2})? an (.+)",
        normalized,
    )
    if reminder:
        weekdays = (
            list(range(7))
            if reminder[1] == "täglich"
            else list(range(5))
            if reminder[1] == "werktags"
            else [5, 6]
        )
        return Intent(
            "reminder.add",
            {
                "text": reminder[4],
                "hour": int(reminder[2]),
                "minute": int(reminder[3] or 0),
                "weekdays": weekdays,
            },
        )
    if normalized in {"zeige meine erinnerungen", "welche erinnerungen habe ich"}:
        return Intent("reminder.list")

    alarm_change = re.fullmatch(
        r"(lösche|deaktiviere|aktiviere) (?:den )?wecker (\d+)", normalized
    )
    if alarm_change:
        return Intent(
            "alarm.change_index",
            {
                "index": int(alarm_change[2]),
                "action": {
                    "lösche": "delete",
                    "deaktiviere": "disable",
                    "aktiviere": "enable",
                }[alarm_change[1]],
            },
        )
    snooze = re.fullmatch(
        r"(?:schlummere|schlummern|wecker verschieben um) (\d+) minuten?", normalized
    )
    if snooze:
        return Intent("alarm.snooze", {"seconds": int(snooze[1]) * 60})

    alarm = re.fullmatch(
        r"(?:stell(?:e)? (?:einen |den )?wecker (?:auf |für )?|wecker auf |wecke mich (?:um )?)(\d{1,2})(?::| uhr\s*)(\d{1,2})?(?: (täglich|werktags|am wochenende))?",
        normalized,
    )
    if alarm:
        weekdays = (
            list(range(7))
            if alarm[3] == "täglich"
            else list(range(5))
            if alarm[3] == "werktags"
            else [5, 6]
            if alarm[3] == "am wochenende"
            else []
        )
        return Intent(
            "alarm.add",
            {"hour": int(alarm[1]), "minute": int(alarm[2] or 0), "weekdays": weekdays},
        )
    if "wecker" in text and re.match(r"(?:stell|weck|starte)", text):
        return Intent(
            "clarify",
            {
                "reply": "Für welche Uhrzeit? Zum Beispiel: Stelle einen Wecker auf sieben Uhr dreißig werktags."
            },
        )

    volume = re.fullmatch(
        r"(?:musiklautstärke|lautstärke) (?:auf )?(\d+)\s*(?:prozent|%)?", normalized
    )
    if volume:
        return Intent("music.volume", {"value": int(volume[1])})
    if re.fullmatch(
        r"(?:fahr|fahre|beweg dich|bewege dich) (?:nach )?(?:links|rechts|vorwärts|rückwärts|vor|zurück)",
        text,
    ):
        return Intent(
            "clarify",
            {
                "reply": "Ich kann nicht fahren. Ich kann meinen Kopf nach links, rechts, oben oder unten bewegen."
            },
        )

    # Freie Notiztexte sind Parameter, keine zweite Synonymliste.
    source = re.sub(r"^(?:hey\s+)?rovo[, ]*", "", raw.strip(), flags=re.I)
    source = re.sub(r"^bitte\s+", "", source, flags=re.I)
    note = re.match(r"(?:merk dir(?:,? dass)?|notiere)\s+", source, flags=re.I)
    if note:
        return Intent("notes.add", {"text": source[note.end() :]})
    if "timer" in text:
        duration = re.search(
            r"(\d+(?:\.\d+)?)\s*(sekunden?|minuten?|stunden?)", normalized
        )
        question = re.match(r"(?:wie|welche|was|wann)\b", text)
        change = re.search(r"\b(lösch\w*|stop\w*|paus\w*|beend\w*|fortsetzen)\b", text)
        start = (
            re.search(r"\b(stell\w*|starte?)\b", text)
            or re.match(r"^timer\b", text)
            or re.fullmatch(
                r"\d+(?:\.\d+)?\s*(?:sekunden?|minuten?|stunden?)\s+timer", normalized
            )
        )
        if duration and start and not question and not change:
            factor = (
                3600
                if duration[2].startswith("stunde")
                else 60
                if duration[2].startswith("minute")
                else 1
            )
            return Intent("timer.start", {"seconds": float(duration[1]) * factor})
        return Intent(
            "clarify",
            {
                "reply": "Wie lange soll der Timer laufen? Bitte nenne Zahl und Einheit; für Änderungen wähle einen eindeutigen Timerbefehl."
            },
        )

    # Variable Gradangaben. Feste Bewegungsformulierungen stammen aus dem Katalog.
    absolute = re.fullmatch(
        r"(?:bewege|stell) (pan|tilt) auf (\d+(?:\.\d+)?) grad", normalized
    )
    if absolute:
        return Intent("motion.axis", {"axis": absolute[1], "value": float(absolute[2])})
    if re.search(r"\b(schau|guck|sieh|dreh|bewege|grad|höher|runter)\b", text):
        direction = re.search(
            r"\b(links|rechts|oben|unten|hoch|runter|höher|tiefer)\b", text
        )
        value = re.search(r"(\d+(?:\.\d+)?)\s*grad", normalized)
        if direction and value:
            if (
                len(
                    re.findall(
                        r"\b(?:links|rechts|oben|unten|hoch|runter|höher|tiefer)\b",
                        text,
                    )
                )
                != 1
                or len(re.findall(r"\d+(?:\.\d+)?\s*grad", normalized)) != 1
            ):
                return Intent(
                    "clarify",
                    {"reply": "Bitte nenne genau einen Winkel und eine Richtung."},
                )
            axis = "pan" if direction[1] in {"links", "rechts"} else "tilt"
            sign = -1 if direction[1] in {"links", "oben", "hoch", "höher"} else 1
            return Intent(
                "motion.relative", {"axis": axis, "delta": sign * float(value[1])}
            )
    if re.search(
        r"\b(plus|minus|mal|geteilt|hoch|wurzel|prozent von)\b", expression
    ) or re.search(r"\d\s*[+*/^%-]", expression):
        return Intent("math.evaluate", {"expression": expression})
    # Nicht erkannte Gerätebefehle nicht in freie Wissensfragen umdeuten.
    if re.match(
        r"(?:schalt\w*|aktivier\w*|deaktivier\w*|lösch\w*|speicher\w*|spiel\w*|tanz\w*|setz\w*|starte|öffne|mach|schau|guck|sieh|dreh|folge|verfolg\w*|kalibrier\w*)\b",
        text,
    ):
        return Intent("unsupported_action")
    return Intent("unknown", {"text": raw})
