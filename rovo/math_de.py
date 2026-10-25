"""Deutsche Zahlwörter und begrenzter Pratt-Parser ohne eval/exec."""

from __future__ import annotations

import math
import re

SMALL = dict(
    zip(
        (
            "null",
            "eins",
            "zwei",
            "drei",
            "vier",
            "fünf",
            "sechs",
            "sieben",
            "acht",
            "neun",
            "zehn",
            "elf",
            "zwölf",
            "dreizehn",
            "vierzehn",
            "fünfzehn",
            "sechzehn",
            "siebzehn",
            "achtzehn",
            "neunzehn",
        ),
        range(20),
    )
)
SMALL.update({"ein": 1, "eine": 1})
TENS = {
    "zwanzig": 20,
    "dreißig": 30,
    "vierzig": 40,
    "fünfzig": 50,
    "sechzig": 60,
    "siebzig": 70,
    "achtzig": 80,
    "neunzig": 90,
}


def word_number(word: str) -> int | None:
    if word in SMALL:
        return SMALL[word]
    if word in TENS:
        return TENS[word]
    for scale, value in (("tausend", 1000), ("hundert", 100)):
        if scale in word:
            left, right = word.split(scale, 1)
            a, b = word_number(left) if left else 1, word_number(right) if right else 0
            if a is not None and b is not None and 0 < a < 1000 and 0 <= b < value:
                return a * value + b
    for tens, value in TENS.items():
        suffix = "und" + tens
        if word.endswith(suffix) and word[: -len(suffix)] in SMALL:
            units = SMALL[word[: -len(suffix)]]
            if 1 <= units <= 9:
                return value + units
    return None


def normalize_numbers(text: str) -> str:
    def replace(match: re.Match) -> str:
        n = word_number(match.group())
        return str(n) if n is not None else match.group()

    text = re.sub(r"[a-zäöüß]+", replace, text.lower())
    text = re.sub(
        r"(\d+)\s+komma\s+((?:\d\s+)*\d)(?!\d)",
        lambda m: m[1] + "." + m[2].replace(" ", ""),
        text,
    )
    return re.sub(r"(?<=\d),(?=\d)", ".", text)


def evaluate(text: str) -> float:
    text = normalize_numbers(text.lower().strip().rstrip("?!"))
    text = re.sub(
        r"^(?:rovo[, ]+)?(?:was (?:ist|sind)|wie viel (?:ist|sind)|berechne|rechne)\s+",
        "",
        text,
    )
    text = (
        text.replace("die wurzel aus", "sqrt ")
        .replace("wurzel aus", "sqrt ")
        .replace("√", "sqrt ")
    )
    for old, new in (
        ("geteilt durch", "/"),
        ("multipliziert mit", "*"),
        ("prozent von", "%"),
        ("plus", "+"),
        ("minus", "-"),
        ("mal", "*"),
        ("hoch", "^"),
        ("×", "*"),
        ("÷", "/"),
        ("**", "^"),
    ):
        text = text.replace(old, new)
    text = text.replace("% von", "%")
    if len(text) > 256:
        raise ValueError("Der Ausdruck ist zu lang.")
    tokens = re.findall(r"sqrt|\d+(?:\.\d+)?|[()+*/^%\-]", text)
    if "".join(tokens) != re.sub(r"\s", "", text) or not tokens or len(tokens) > 100:
        raise ValueError("Diese Rechnung ist nicht eindeutig lesbar.")
    index = 0

    def bounded(value: float) -> float:
        if isinstance(value, complex) or not math.isfinite(value) or abs(value) > 1e15:
            raise ValueError("Das Ergebnis liegt außerhalb des erlaubten Bereichs.")
        return value

    def expression(min_bp: int = 0, depth: int = 0) -> float:
        nonlocal index
        if depth > 20 or index >= len(tokens):
            raise ValueError("Unvollständiger oder zu verschachtelter Ausdruck.")
        token = tokens[index]
        index += 1
        if token == "(":
            left = expression(0, depth + 1)
            if index >= len(tokens) or tokens[index] != ")":
                raise ValueError("Schließende Klammer fehlt.")
            index += 1
        elif token in ("-", "+", "sqrt"):
            val = expression(29, depth + 1)
            left = (
                math.sqrt(val) if token == "sqrt" else (-val if token == "-" else val)
            )
        else:
            try:
                left = bounded(float(token))
            except ValueError as exc:
                raise ValueError("Zahl erwartet.") from exc
        while index < len(tokens) and tokens[index] != ")":
            op = tokens[index]
            if op not in ("+", "-", "*", "/", "^", "%"):
                raise ValueError("Operator erwartet.")
            bp = {"+": 10, "-": 10, "*": 20, "/": 20, "%": 20, "^": 30}[op]
            if bp < min_bp:
                break
            index += 1
            right = expression(bp if op == "^" else bp + 1, depth + 1)
            if op == "^" and (abs(right) > 12 or abs(left) > 1e6):
                raise ValueError("Diese Potenz ist zu groß.")
            if op == "+":
                left += right
            elif op == "-":
                left -= right
            elif op == "*":
                left *= right
            elif op == "/":
                left /= right
            elif op == "%":
                left = left * right / 100
            else:
                left = left**right
            bounded(left)
        return bounded(left)

    try:
        result = expression()
        if index != len(tokens):
            raise ValueError("Unerwartete Eingabe am Ende.")
        return result
    except ZeroDivisionError as exc:
        raise ValueError("Durch null kann ich nicht teilen.") from exc
    except (OverflowError, RecursionError) as exc:
        raise ValueError("Diese Rechnung ist zu groß.") from exc


def format_number(value: float) -> str:
    return f"{value:.12g}".replace(".", ",")
