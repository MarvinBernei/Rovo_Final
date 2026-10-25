"""Optionale Wetterabfrage über einen festen Open-Meteo-Endpunkt."""

from urllib.parse import urlencode

from .cloud_http import request_json

DESCRIPTIONS = {
    0: "klar",
    1: "überwiegend klar",
    2: "teilweise bewölkt",
    3: "bewölkt",
    45: "neblig",
    48: "neblig",
    51: "leichter Nieselregen",
    53: "Nieselregen",
    55: "starker Nieselregen",
    61: "leichter Regen",
    63: "Regen",
    65: "starker Regen",
    71: "leichter Schneefall",
    73: "Schneefall",
    75: "starker Schneefall",
    80: "leichte Regenschauer",
    81: "Regenschauer",
    82: "starke Regenschauer",
    95: "Gewitter",
    96: "Gewitter mit Hagel",
    99: "starkes Gewitter mit Hagel",
}


class Weather:
    def __init__(self, config: dict) -> None:
        self.config = config

    async def current(self) -> dict:
        if not self.config["enabled"]:
            raise ValueError("Wetter ist nicht eingerichtet.")
        query = urlencode(
            {
                "latitude": self.config["latitude"],
                "longitude": self.config["longitude"],
                "current": "temperature_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m",
                "timezone": "auto",
            }
        )
        result = await request_json(
            "GET", "https://api.open-meteo.com/v1/forecast?" + query
        )
        current = result.get("current", {})
        required = (
            "temperature_2m",
            "apparent_temperature",
            "precipitation",
            "weather_code",
            "wind_speed_10m",
        )
        if not isinstance(current, dict) or any(
            type(current.get(key)) not in (int, float) for key in required
        ):
            raise ValueError(
                "Wetterdienst hat keine vollständigen aktuellen Werte geliefert."
            )
        return {
            "location": self.config["label"],
            "temperature_c": float(current["temperature_2m"]),
            "apparent_temperature_c": float(current["apparent_temperature"]),
            "precipitation_mm": float(current["precipitation"]),
            "wind_kmh": float(current["wind_speed_10m"]),
            "description": DESCRIPTIONS.get(
                int(current["weather_code"]), "unbekannte Wetterlage"
            ),
        }
