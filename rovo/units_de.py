"""Deterministische Einheitenumrechnung ohne Netzwerk oder ``eval``."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Unit:
    dimension: str
    factor: float
    offset: float = 0.0
    label: str = ""

    def base(self, value: float) -> float:
        return (value + self.offset) * self.factor

    def from_base(self, value: float) -> float:
        return value / self.factor - self.offset


def _u(dimension, factor, label, offset=0.0):
    return Unit(dimension, factor, offset, label)


UNITS = {
    "mm": _u("length", 0.001, "Millimeter"),
    "millimeter": _u("length", 0.001, "Millimeter"),
    "cm": _u("length", 0.01, "Zentimeter"),
    "zentimeter": _u("length", 0.01, "Zentimeter"),
    "m": _u("length", 1, "Meter"),
    "meter": _u("length", 1, "Meter"),
    "km": _u("length", 1000, "Kilometer"),
    "kilometer": _u("length", 1000, "Kilometer"),
    "zoll": _u("length", 0.0254, "Zoll"),
    "inch": _u("length", 0.0254, "Zoll"),
    "fuß": _u("length", 0.3048, "Fuß"),
    "foot": _u("length", 0.3048, "Fuß"),
    "meile": _u("length", 1609.344, "Meilen"),
    "meilen": _u("length", 1609.344, "Meilen"),
    "mg": _u("mass", 0.000001, "Milligramm"),
    "g": _u("mass", 0.001, "Gramm"),
    "gramm": _u("mass", 0.001, "Gramm"),
    "kg": _u("mass", 1, "Kilogramm"),
    "kilogramm": _u("mass", 1, "Kilogramm"),
    "pfund": _u("mass", 0.45359237, "Pfund"),
    "ml": _u("volume", 0.001, "Milliliter"),
    "milliliter": _u("volume", 0.001, "Milliliter"),
    "l": _u("volume", 1, "Liter"),
    "liter": _u("volume", 1, "Liter"),
    "sekunde": _u("time", 1, "Sekunden"),
    "sekunden": _u("time", 1, "Sekunden"),
    "minute": _u("time", 60, "Minuten"),
    "minuten": _u("time", 60, "Minuten"),
    "stunde": _u("time", 3600, "Stunden"),
    "stunden": _u("time", 3600, "Stunden"),
    "tag": _u("time", 86400, "Tage"),
    "tage": _u("time", 86400, "Tage"),
    "m/s": _u("speed", 1, "Meter pro Sekunde"),
    "km/h": _u("speed", 1 / 3.6, "Kilometer pro Stunde"),
    "mph": _u("speed", 0.44704, "Meilen pro Stunde"),
    "pa": _u("pressure", 1, "Pascal"),
    "hpa": _u("pressure", 100, "Hektopascal"),
    "bar": _u("pressure", 100000, "Bar"),
    "wh": _u("energy", 3600, "Wattstunden"),
    "kwh": _u("energy", 3600000, "Kilowattstunden"),
    "j": _u("energy", 1, "Joule"),
    "w": _u("power", 1, "Watt"),
    "kw": _u("power", 1000, "Kilowatt"),
    "byte": _u("data", 1, "Byte"),
    "kb": _u("data", 1000, "Kilobyte"),
    "mb": _u("data", 1000000, "Megabyte"),
    "gb": _u("data", 1000000000, "Gigabyte"),
    "kib": _u("data", 1024, "Kibibyte"),
    "mib": _u("data", 1048576, "Mebibyte"),
    "gib": _u("data", 1073741824, "Gibibyte"),
    "celsius": _u("temperature", 1, "Grad Celsius", 273.15),
    "fahrenheit": _u("temperature", 5 / 9, "Grad Fahrenheit", 459.67),
    "kelvin": _u("temperature", 1, "Kelvin"),
}


def convert(value: float, source: str, target: str) -> tuple[float, str]:
    left, right = UNITS.get(source.casefold()), UNITS.get(target.casefold())
    if not left or not right:
        raise ValueError("Diese Einheit kenne ich noch nicht.")
    if left.dimension != right.dimension:
        raise ValueError("Diese Einheiten gehören nicht zur gleichen Größe.")
    result = right.from_base(left.base(float(value)))
    if abs(result) > 1e18:
        raise ValueError("Das Umrechnungsergebnis ist zu groß.")
    return result, right.label
