"""Nur reale Hostwerte; Sensoren fehlen -> null."""

import math
import os
import platform
import time
from pathlib import Path


def power_status(
    supply: str | None, root: Path = Path("/sys/class/power_supply")
) -> dict:
    result = {
        "battery_percent": None,
        "voltage": None,
        "current": None,
        "charging": None,
        "source": None,
        "measured_at_unix": None,
    }
    if (
        not supply
        or not isinstance(supply, str)
        or "/" in supply
        or "\\" in supply
        or supply in {".", ".."}
    ):
        return result
    path = root / supply
    try:
        if (path / "type").read_text().strip() not in {"Battery", "UPS"}:
            return result
    except OSError:
        return result
    for filename, key, factor, low, high in (
        ("capacity", "battery_percent", 1, 0, 100),
        ("voltage_now", "voltage", 1e-6, 0, 100),
        ("current_now", "current", 1e-6, -100, 100),
    ):
        try:
            value = float((path / filename).read_text()) * factor
            if math.isfinite(value) and low <= value <= high:
                result[key] = value
        except (OSError, ValueError):
            pass
    try:
        status = (path / "status").read_text().strip()
        result["charging"] = (
            True
            if status == "Charging"
            else False
            if status in {"Discharging", "Not charging", "Full"}
            else None
        )
    except OSError:
        pass
    result["source"], result["measured_at_unix"] = (
        "linux-power-supply:" + supply,
        time.time(),
    )
    return result


def system_status(started: float) -> dict:
    result = {
        "os": platform.system(),
        "process_uptime_s": round(time.monotonic() - started, 1),
        "cpu_temp_c": None,
        "ram_available_mb": None,
        "ram_usage_percent": None,
        "hostname": platform.node(),
        "load_1m": None,
    }
    try:
        result["cpu_temp_c"] = (
            float(Path("/sys/class/thermal/thermal_zone0/temp").read_text()) / 1000
        )
    except (OSError, ValueError):
        pass
    try:
        total = None
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemTotal:"):
                total = int(line.split()[1]) / 1024
            if line.startswith("MemAvailable:"):
                result["ram_available_mb"] = round(int(line.split()[1]) / 1024)
        if total and result["ram_available_mb"] is not None:
            result["ram_usage_percent"] = round(
                100 * (1 - result["ram_available_mb"] / total), 1
            )
        result["load_1m"] = os.getloadavg()[0]
    except (OSError, ValueError, AttributeError):
        pass
    if platform.system() == "Windows":
        try:
            import ctypes

            class MemoryStatus(ctypes.Structure):
                _fields_ = [("length", ctypes.c_uint32), ("load", ctypes.c_uint32)] + [
                    (name, ctypes.c_uint64)
                    for name in (
                        "total",
                        "available",
                        "page_total",
                        "page_available",
                        "virtual_total",
                        "virtual_available",
                        "extended",
                    )
                ]

            memory = MemoryStatus()
            memory.length = ctypes.sizeof(memory)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory)):
                result["ram_usage_percent"] = memory.load
                result["ram_available_mb"] = round(memory.available / 1024**2)
        except (OSError, AttributeError):
            pass
    return result
