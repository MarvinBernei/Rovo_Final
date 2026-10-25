"""Ein Ausgabe-Manager für lokale Piper-TTS und Musik über mpv-IPC."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
import tempfile
import wave
from array import array
from pathlib import Path


class Audio:
    def __init__(self, config: dict) -> None:
        self.config = config
        self.speech: asyncio.subprocess.Process | None = None
        self.music: asyncio.subprocess.Process | None = None
        self.lock = asyncio.Lock()
        self.generation = 0
        self.volume = 30
        self.speech_volume = 70
        self.speech_rate = 1.0
        from .spotify import Spotify

        self.spotify = Spotify()
        self.last_reply: str | None = None
        self.directory = tempfile.TemporaryDirectory(prefix="rovo-audio-")
        self.socket = str(Path(self.directory.name) / "mpv.sock")
        self.music_state = "STOPPED"

    @property
    def available(self) -> bool:
        voice = self.config.get("voice")
        return bool(
            self.config["enabled"]
            and voice
            and Path(voice).is_file()
            and shutil.which(self.config["piper"])
            and shutil.which("aplay")
        )

    async def _ipc(self, *command: object) -> None:
        if self.music is None or self.music.returncode is not None:
            raise ValueError("Keine Musik aktiv.")
        reader, writer = await asyncio.wait_for(
            asyncio.open_unix_connection(self.socket), 1
        )
        try:
            writer.write((json.dumps({"command": command}) + "\n").encode())
            await writer.drain()
            result = json.loads(await asyncio.wait_for(reader.readline(), 1))
            if result.get("error") != "success":
                raise ValueError("Player hat den Befehl abgewiesen.")
        finally:
            writer.close()
            await writer.wait_closed()

    async def play(self, path: str, media_root: Path) -> None:
        if not isinstance(path, str):
            raise ValueError("Dateipfad muss Text sein.")
        if not shutil.which("mpv") or os.name != "posix":
            raise ValueError(
                "Lokaler mpv-Player ist auf diesem System nicht verfügbar."
            )
        target, root = Path(path).resolve(), media_root.resolve()
        if (
            not target.is_relative_to(root)
            or not target.is_file()
            or target.suffix.lower() not in {".mp3", ".wav", ".ogg", ".flac"}
        ):
            raise ValueError(
                "Nur vorhandene Audiodateien innerhalb data/music sind erlaubt."
            )
        await self.stop_music()
        self.music = await asyncio.create_subprocess_exec(
            "mpv",
            "--no-video",
            "--idle=no",
            "--input-ipc-server=" + self.socket,
            "--volume=" + str(self.volume),
            "--",
            str(target),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        for _ in range(20):
            if Path(self.socket).exists():
                self.music_state = "PLAYING"
                return
            if self.music.returncode is not None:
                break
            await asyncio.sleep(0.05)
        await self.stop_music()
        raise ValueError("Musikplayer konnte nicht starten.")

    async def pause(self, paused: bool) -> None:
        if self.spotify.active:
            await self.spotify.pause(paused)
        else:
            await self._ipc("set_property", "pause", paused)
        self.music_state = "PAUSED" if paused else "PLAYING"

    async def set_volume(self, value: int) -> None:
        from .config import number

        number(value, 0, 100)
        if type(value) is not int:
            raise ValueError("Ganzzahliger Prozentwert erforderlich.")
        if self.music is not None and self.music.returncode is None:
            await self._ipc("set_property", "volume", value)
        if self.spotify.active:
            await self.spotify.volume(value)
        self.volume = value

    async def play_spotify(self, query: str) -> dict:
        await self.stop_music()
        generation = self.generation
        result = await self.spotify.play(query)
        if generation != self.generation:
            await self.spotify.pause(True)
            self.spotify.active = False
            raise ValueError("Spotify-Start wurde zwischenzeitlich abgebrochen.")
        self.music_state = "PLAYING"
        return result

    def speech_settings(self, volume_delta: int = 0, rate_factor: float = 1) -> dict:
        from .config import number

        number(volume_delta, -100, 100)
        number(rate_factor, 0.5, 2)
        self.speech_volume = max(0, min(100, self.speech_volume + volume_delta))
        self.speech_rate = max(0.5, min(1.5, self.speech_rate * rate_factor))
        return {
            "speech_volume_percent": self.speech_volume,
            "speech_rate": self.speech_rate,
        }

    def scale_speech(self, output: Path) -> None:
        with wave.open(str(output), "rb") as source:
            params, raw = source.getparams(), source.readframes(source.getnframes())
        if params.sampwidth != 2 or params.comptype != "NONE":
            raise ValueError("Sprachlautstärke erfordert unkomprimiertes 16-Bit-PCM.")
        samples = array("h")
        samples.frombytes(raw)
        if sys.byteorder != "little":
            samples.byteswap()
        factor = self.speech_volume / 100
        for index, sample in enumerate(samples):
            samples[index] = round(sample * factor)
        if sys.byteorder != "little":
            samples.byteswap()
        with wave.open(str(output), "wb") as target:
            target.setparams(params)
            target.writeframes(samples.tobytes())

    async def speak(self, text: str) -> bool:
        self.last_reply = text
        if not self.available:
            return False
        generation = self.generation
        async with self.lock:
            if generation != self.generation:
                return False
            resume = self.music_state == "PLAYING"
            if resume:
                await self.pause(True)
            output = Path(self.directory.name) / "speech.wav"
            try:
                self.speech = await asyncio.create_subprocess_exec(
                    self.config["piper"],
                    "--model",
                    self.config["voice"],
                    "--output_file",
                    str(output),
                    "--length_scale",
                    str(1 / self.speech_rate),
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                await asyncio.wait_for(
                    self.speech.communicate(text[:4000].encode("utf-8")), 30
                )
                if self.speech.returncode != 0 or generation != self.generation:
                    return False
                self.scale_speech(output)
                self.speech = await asyncio.create_subprocess_exec(
                    "aplay",
                    "-q",
                    "-D",
                    self.config["output_device"],
                    str(output),
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                await asyncio.wait_for(self.speech.wait(), 90)
                return self.speech.returncode == 0
            finally:
                await self._terminate(self.speech)
                self.speech = None
                output.unlink(missing_ok=True)
                if (
                    resume
                    and generation == self.generation
                    and self.music_state == "PAUSED"
                ):
                    try:
                        await self.pause(False)
                    except (OSError, ValueError, TimeoutError):
                        self.music_state = "ERROR"

    @staticmethod
    async def _terminate(process) -> None:
        if process is not None and process.returncode is None:
            try:
                process.terminate()
            except ProcessLookupError:
                return
            try:
                await asyncio.wait_for(process.wait(), 1)
            except TimeoutError:
                process.kill()
                await process.wait()

    async def stop_music(self) -> None:
        self.generation += (
            1  # Stop darf nicht durch verspätetes Resume aufgehoben werden.
        )
        self.music_state = "STOPPED"
        await self._terminate(self.music)
        self.music = None
        Path(self.socket).unlink(missing_ok=True)
        if self.spotify.active:
            try:
                await self.spotify.pause(True)
            except (ValueError, OSError, TimeoutError):
                self.music_state = "ERROR"
                raise
            else:
                self.spotify.active = False

    async def stop(self) -> None:
        self.generation += 1
        await self._terminate(self.speech)
        await self.stop_music()

    async def close(self) -> None:
        try:
            await self.stop()
        finally:
            self.directory.cleanup()
