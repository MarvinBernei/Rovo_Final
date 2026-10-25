"""Waveshare UPS HAT (E), MCU 0x2d: ausschließlich Messregister lesen.

Registerquelle: https://docs.waveshare.com/UPS-HAT-E-Tutorials-Register
"""

import asyncio
import time

from .telemetry import power_status


def read_measurements(bus, address=0x2D):
    if bus.read_byte_data(address, 0x00) != 0x0A:
        raise ValueError("UPS-HAT-E-Kennung stimmt nicht.")
    flags = bus.read_byte_data(address, 0x03)
    status = bus.read_byte_data(address, 0x02)
    result = power_status(None)

    def word(register, signed=False):
        data = bus.read_i2c_block_data(address, register, 2)
        if len(data) != 2:
            raise ValueError("Unvollständige UPS-Messung.")
        value = data[0] | data[1] << 8
        return value - 65536 if signed and value >= 32768 else value

    if flags & 2:
        voltage, current, percent = (
            word(0x20) / 1000,
            word(0x22, True) / 1000,
            word(0x24),
        )
        if not 0 < voltage <= 25 or not -50 <= current <= 50 or not 0 <= percent <= 100:
            raise ValueError("UPS-Messwerte außerhalb plausibler Grenzen.")
        result.update(voltage=voltage, current=current, battery_percent=percent)
    if flags & 1:
        result.update(
            charging=bool(status & 0x80),
            external_power=bool(status & 0x20),
            vbus_voltage=word(0x10) / 1000,
            vbus_current=word(0x12, True) / 1000,
        )
    if not flags & 3:
        raise ValueError("UPS meldet Kommunikationsfehler zu den Messchips.")
    result.update(source="waveshare-ups-hat-e", measured_at_unix=time.time())
    return result


def read_device(bus_number, address):
    from smbus2 import SMBus

    with SMBus(bus_number) as bus:
        return read_measurements(bus, address)


class PowerMonitor:
    def __init__(self, config, simulation):
        self.config, self.simulation = config, simulation
        self.cached, self.next_poll = power_status(None), 0.0

    def snapshot(self):
        if self.config["driver"] == "sysfs":
            return power_status(self.config["supply"])
        if self.simulation:
            return power_status(None)
        if time.time() - (self.cached["measured_at_unix"] or 0) > 10:
            return power_status(None)
        return dict(self.cached)

    async def poll(self):
        if (
            self.simulation
            or self.config["driver"] != "waveshare-ups-hat-e"
            or time.monotonic() < self.next_poll
        ):
            return
        self.next_poll = time.monotonic() + 5
        try:
            self.cached = await asyncio.to_thread(
                read_device, self.config["i2c_bus"], self.config["i2c_address"]
            )
        except (OSError, ValueError, ImportError):
            self.cached = power_status(None)
