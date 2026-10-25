"""Geprüfte Softwaregrenzen innerhalb der bereits bestätigten Hardwarehülle."""

from .config import number


def validate_limits(candidate, hardware):
    if not isinstance(candidate, dict) or set(candidate) != {"pan", "tilt"}:
        raise ValueError("Pan- und Tilt-Grenzen erforderlich.")
    result = {}
    for axis in ("pan", "tilt"):
        values, ceiling = candidate[axis], hardware[axis]
        if not isinstance(values, dict) or set(values) != {
            "min",
            "max",
            "home",
            "direction",
        }:
            raise ValueError("Unvollständige Achsgrenzen.")
        if ceiling["min"] is None or ceiling["max"] is None:
            raise ValueError(
                "Zuerst Hardwaregrenzen und Servoausrichtung außerhalb der UI bestätigen."
            )
        low = number(values["min"], ceiling["min"], ceiling["max"])
        high = number(values["max"], ceiling["min"], ceiling["max"])
        number(values["home"], low, high)
        if type(values["direction"]) is not int:
            raise ValueError("Achsrichtung muss ganzzahlig sein.")
        if (
            not low < high
            or values["home"] != ceiling["home"]
            or values["direction"] != ceiling["direction"]
            or not low <= values["home"] <= high
        ):
            raise ValueError(
                "Grenzen dürfen nur innerhalb der Hardwarehülle liegen; Home und Richtung bleiben unverändert."
            )
        result[axis] = dict(values)
    return result
