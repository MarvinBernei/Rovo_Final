"""Startpunkte: Text-CLI, lokale API, Push-to-talk, gefahrlose Diagnose."""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import os
import signal
import sys
from pathlib import Path

from . import __version__
from .config import load
from .core import Core
from .esp import FakeESP32, SerialESP32


async def run(args: argparse.Namespace) -> None:
    config = load(Path(args.config) if args.config else None)
    if args.mode == "diagnose":
        import platform
        import shutil

        print(
            json.dumps(
                {
                    "rovo": __version__,
                    "python": platform.python_version(),
                    "system": platform.system(),
                    "safe_mode": config["safe_mode"],
                    "simulation": config["simulation"],
                    "serial_opened": False,
                    "programs": {
                        name: bool(shutil.which(name))
                        for name in (
                            "piper",
                            "mpv",
                            "aplay",
                            "arecord",
                            "node-red",
                            "arduino-cli",
                        )
                    },
                },
                indent=2,
            )
        )
        return
    if args.connect_serial:
        if config["simulation"] or not config["serial_port"]:
            raise ValueError(
                "Serial benötigt simulation=false und einen konfigurierten Port."
            )
        esp = SerialESP32(config["serial_port"])
        await esp.connect()
    else:
        if not config["simulation"]:
            raise ValueError("simulation=false erfordert explizites --connect-serial.")
        esp = FakeESP32()
    core = Core(
        config,
        Path(args.data),
        esp=esp,
        live_authorized=args.allow_motion,
        power_authorized=args.allow_power_actions,
    )
    tick = asyncio.create_task(core.tick())
    mqtt_bridge = mqtt_task = None
    heartbeat = None
    if not esp.simulated:

        async def keepalive():
            while not core.closed:
                try:
                    await esp.command("PING")
                except (OSError, TimeoutError, ValueError):
                    await core.motion.stop()
                    return
                await asyncio.sleep(0.2)

        heartbeat = asyncio.create_task(keepalive())
    print(
        f"ROVO {__version__} | {'SIMULATION' if esp.simulated else 'SERIAL'} | Safe Mode: {config['safe_mode']}"
    )
    try:
        if config["mqtt"]["enabled"]:
            from .mqtt_bridge import MQTTBridge

            mqtt_bridge = MQTTBridge(core, config["mqtt"])
            mqtt_bridge.start()
            mqtt_task = asyncio.create_task(mqtt_bridge.run())
        if args.mode == "serve":
            from .api import start_server

            server = start_server(core, asyncio.get_running_loop())
            server_task = asyncio.create_task(
                asyncio.to_thread(server.serve_forever, 0.2)
            )
            print(f"Lokale API: http://127.0.0.1:{config['api']['port']}/api/v1/status")
            done = asyncio.Event()
            if os.name == "posix":
                asyncio.get_running_loop().add_signal_handler(signal.SIGTERM, done.set)
            try:
                await done.wait()
            finally:
                await asyncio.to_thread(server.shutdown)
                await server_task
                server.server_close()
        else:
            voice = None
            if args.mode == "voice":
                from .voice import Voice

                if not args.stt_model:
                    raise ValueError(
                        "--stt-model benötigt ein vorhandenes lokales Modellverzeichnis."
                    )
                voice = await asyncio.to_thread(Voice, args.stt_model, args.microphone)
                if args.hands_free:
                    if not args.wake_model:
                        raise ValueError(
                            "--hands-free benötigt --wake-model mit einem lokalen deutschen Vosk-Modell."
                        )
                    await asyncio.to_thread(voice.configure_wake, args.wake_model)
                    core.wakeword_online = True
                    if config["camera"]["enabled"]:
                        await core.camera.start()
                    await voice.dialogue(core)
                    return
            if args.text:
                result = await core.execute(
                    {"type": "text", "args": {"text": args.text}}
                )
                print(json.dumps(result, ensure_ascii=False, indent=2))
            else:
                print(
                    "Text eingeben; /status zeigt Zustand, /quit beendet. Voice: Enter startet eine Aufnahme."
                )
                while True:
                    try:
                        text = await asyncio.to_thread(input, "Du> ")
                    except EOFError:
                        break
                    if text.strip() == "/quit":
                        break
                    if text.strip() == "/status":
                        print(json.dumps(core.status(), ensure_ascii=False, indent=2))
                        continue
                    if voice and not text.strip():
                        try:
                            text = await voice.listen(core)
                        except (OSError, ValueError) as exc:
                            print(str(exc))
                            continue
                        print("Erkannt:", text)
                    result = await core.execute(
                        {"type": "text", "args": {"text": text}}
                    )
                    print("Rovo>", result["spoken_reply"])
                    if result["ok"] and result["intent"] not in {
                        "stop",
                        "audio.stop",
                        "privacy.enable",
                    }:
                        core.background_speech(result["spoken_reply"])
    finally:
        if mqtt_task:
            mqtt_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await mqtt_task
        if mqtt_bridge:
            await mqtt_bridge.close()
        tick.cancel()
        if heartbeat:
            heartbeat.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await heartbeat
        with contextlib.suppress(asyncio.CancelledError):
            await tick
        await core.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="ROVO – lokal, sicher und modular")
    parser.add_argument(
        "mode", nargs="?", default="cli", choices=("cli", "serve", "voice", "diagnose")
    )
    parser.add_argument("--config")
    parser.add_argument("--data", default="data")
    parser.add_argument("--text", help="Einzelne Texteingabe testen")
    parser.add_argument(
        "--connect-serial",
        action="store_true",
        help="Öffnet ausdrücklich den Nano-Port (möglicher Reset)",
    )
    parser.add_argument(
        "--allow-motion",
        action="store_true",
        help="Explizite Startfreigabe für bereits kalibrierte reale Mechanik",
    )
    parser.add_argument("--stt-model")
    parser.add_argument(
        "--hands-free",
        action="store_true",
        help="Lokale Anrede-Erkennung und freihändiger Halbduplexdialog im Voice-Modus",
    )
    parser.add_argument(
        "--wake-model", help="Vorhandenes deutsches Vosk-Modellverzeichnis"
    )
    parser.add_argument(
        "--allow-power-actions",
        action="store_true",
        help="Erlaubt bestätigtes Herunterfahren/Neustarten auf Linux",
    )
    parser.add_argument("--microphone", help="Stabiler sounddevice-Gerätename")
    args = parser.parse_args()
    try:
        asyncio.run(run(args))
    except KeyboardInterrupt:
        pass
    except (ValueError, OSError, ImportError) as exc:
        print("Start fehlgeschlagen:", str(exc), file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
