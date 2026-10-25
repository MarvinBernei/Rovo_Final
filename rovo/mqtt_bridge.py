"""Lokale MQTT-Bridge zum bestehenden Dashboard-Gateway; keine zweite Hardwaresteuerung."""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
import uuid

from .dashboard import execute, projection


class MQTTBridge:
    def __init__(self, core, config):
        self.core, self.config = core, config
        self.boot_id = uuid.uuid4().hex
        self.client = None
        self.tasks = set()
        self.seen = {}
        self.connected = False
        self.closing = False

    def publish(self, suffix, value, retain=False):
        return self.client.publish(
            self.config["prefix"] + "/" + suffix,
            json.dumps(value, ensure_ascii=False, allow_nan=False),
            qos=1,
            retain=retain,
        )

    async def handle(self, value, retained=False):
        if (
            retained
            or not isinstance(value, dict)
            or set(value) != {"id", "boot_id", "session", "issued_at", "action", "data"}
        ):
            return
        ident, session = value["id"], value["session"]
        if not isinstance(ident, str) or not re.fullmatch(
            r"[A-Za-z0-9_-]{1,80}", ident
        ):
            return
        if not isinstance(session, str) or not re.fullmatch(
            r"[A-Za-z0-9_-]{1,128}", session
        ):
            return
        issued = value["issued_at"]
        if (
            type(issued) not in (int, float)
            or not -5 <= time.time() - issued <= 30
            or value["boot_id"] != self.boot_id
        ):
            return
        now = time.monotonic()
        self.seen = {
            key: stamp for key, stamp in self.seen.items() if now - stamp < 120
        }
        if ident in self.seen or len(self.seen) >= 1024:
            return
        self.seen[ident] = (
            now  # Vor dem ersten await gegen doppelte QoS-1-Zustellung sperren.
        )
        try:
            result = await execute(
                self.core,
                {"action": value["action"], "data": value["data"]},
                session=session,
            )
        except Exception:
            result = {
                "ok": False,
                "message": "MQTT-Auftrag fehlgeschlagen; lokale Diagnose erforderlich.",
            }
        if self.connected:
            self.publish(
                "reply", {"id": ident, "boot_id": self.boot_id, "result": result}
            )

    def receive(self, value, retained):
        if self.closing or not self.connected or len(self.tasks) >= 16:
            return
        if len(self.tasks) >= 12 and (
            not isinstance(value, dict) or value.get("action") != "motion.stop"
        ):
            return
        task = asyncio.create_task(self.handle(value, retained))
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

    def start(self):
        import paho.mqtt.client as mqtt

        user, password = (
            os.environ.get("ROVO_MQTT_USER"),
            os.environ.get("ROVO_MQTT_PASSWORD"),
        )
        if not user or not password:
            raise ValueError("ROVO_MQTT_USER und ROVO_MQTT_PASSWORD fehlen.")
        loop = asyncio.get_running_loop()
        client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id="rovo-core-" + self.boot_id[:12],
            clean_session=True,
        )
        self.client = client
        client.username_pw_set(user, password)
        client.max_queued_messages_set(64)
        client.reconnect_delay_set(1, 15)
        client.will_set(
            self.config["prefix"] + "/availability",
            json.dumps({"online": False, "boot_id": self.boot_id}),
            qos=1,
            retain=True,
        )

        def connected(client, userdata, flags, reason_code, properties):
            if reason_code.is_failure:
                return
            client.subscribe(self.config["prefix"] + "/command", qos=1)
            loop.call_soon_threadsafe(self.on_connected)

        def disconnected(client, userdata, flags, reason_code, properties):
            loop.call_soon_threadsafe(setattr, self, "connected", False)

        def message(client, userdata, msg):
            if (
                msg.topic != self.config["prefix"] + "/command"
                or len(msg.payload) > 16384
            ):
                return
            try:
                value = json.loads(msg.payload)
            except (ValueError, UnicodeError):
                return
            loop.call_soon_threadsafe(self.receive, value, msg.retain)

        client.on_connect, client.on_disconnect, client.on_message = (
            connected,
            disconnected,
            message,
        )
        client.connect_async(self.config["host"], self.config["port"], keepalive=15)
        client.loop_start()

    def on_connected(self):
        if self.closing:
            return
        self.boot_id = uuid.uuid4().hex  # Auch beim Reconnect alte Befehle sperren.
        self.connected = True
        self.publish(
            "availability", {"online": True, "boot_id": self.boot_id}, retain=True
        )

    async def run(self):
        while not self.closing:
            if self.connected:
                # Keine Profile, Namen, Texte oder Bilder als dauerhaft gespeicherte Topics.
                self.publish(
                    "status",
                    {
                        "boot_id": self.boot_id,
                        "snapshot": projection(self.core)["snapshot"],
                    },
                )
            await asyncio.sleep(2)

    async def close(self):
        self.closing = True
        for task in list(self.tasks):
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        if self.client:
            if self.connected:
                info = self.publish(
                    "availability",
                    {"online": False, "boot_id": self.boot_id},
                    retain=True,
                )
                try:
                    await asyncio.to_thread(info.wait_for_publish, 2)
                except (RuntimeError, ValueError):
                    pass
            await asyncio.to_thread(self.client.disconnect)
            await asyncio.to_thread(self.client.loop_stop)
