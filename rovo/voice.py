"""Lokale Push-to-talk-Aufnahme mit RMS-Sprachende und faster-whisper.

Kein Wake-Word-Ersatz: Aufnahme wird ausdrücklich mit Enter gestartet.
Rohdaten bleiben im RAM. Nur ein InputStream, keine dauerhafte Audiodatei.
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from pathlib import Path


class Voice:
    def __init__(self, model_path: str, device=None, threshold: float = 0.015) -> None:
        if not Path(model_path).is_dir():
            raise ValueError("Lokales faster-whisper-Modellverzeichnis fehlt.")
        from faster_whisper import WhisperModel

        self.model = WhisperModel(
            model_path,
            device="cpu",
            compute_type="int8",
            cpu_threads=2,
            local_files_only=True,
        )
        self.device, self.threshold = device, threshold
        self.wake_model = None
        self.wake_engine = None
        self.wake_threshold = 0.5

    def configure_wake(self, model_path: str) -> None:
        path = Path(model_path)
        if path.is_file() and path.suffix.lower() == ".onnx":
            from openwakeword.model import Model

            self.wake_model = Model(
                wakeword_models=[str(path)], inference_framework="onnx"
            )
            self.wake_engine = "openwakeword"
        elif path.is_dir():
            from vosk import Model

            self.wake_model = Model(model_path)
            self.wake_engine = "vosk"
        else:
            raise ValueError("Lokales Vosk-Verzeichnis oder Wake-Word-ONNX fehlt.")

    @staticmethod
    def wake_phrase(text: str) -> bool:
        return bool(
            re.fullmatch(
                r"(?:hey|hallo)\s+(?:rovo|robo|rowo|ro wo)", text.strip().lower()
            )
        )

    def wait_wake(self, core) -> bool:
        import sounddevice as sd

        if not self.wake_model:
            raise ValueError("Anrede-Modell nicht eingerichtet.")
        if self.wake_engine == "vosk":
            from vosk import KaldiRecognizer

            recognizer = KaldiRecognizer(self.wake_model, 16000)
        else:
            recognizer = None
        # Ein Mikrofoneigentümer: Wake und STT laufen strikt nacheinander.
        with sd.RawInputStream(
            samplerate=16000,
            blocksize=4000,
            device=self.device,
            dtype="int16",
            channels=1,
        ) as stream:
            while not core.closed and not core.privacy:
                audio, overflow = stream.read(4000)
                if overflow:
                    continue
                if (
                    core.audio.speech is not None
                    and core.audio.speech.returncode is None
                ):
                    if recognizer:
                        recognizer.Reset()
                    continue
                if self.wake_engine == "openwakeword":
                    import numpy as np

                    scores = self.wake_model.predict(
                        np.frombuffer(bytes(audio), dtype=np.int16)
                    )
                    if (
                        scores
                        and max(float(score) for score in scores.values())
                        >= self.wake_threshold
                    ):
                        return True
                elif recognizer.AcceptWaveform(bytes(audio)):
                    if self.wake_phrase(
                        json.loads(recognizer.Result()).get("text", "")
                    ):
                        return True
        return False

    def record(self, core) -> object:
        import numpy as np
        import sounddevice as sd

        frames, voice_seen, silence_since = [], False, None
        sample_rate, chunk = 16000, 1600
        deadline = time.monotonic() + 10
        with sd.InputStream(
            samplerate=sample_rate,
            channels=1,
            dtype="float32",
            device=self.device,
            blocksize=chunk,
        ) as stream:
            while time.monotonic() < deadline:
                if core.privacy:
                    raise ValueError("Aufnahme durch Privatsphäre abgebrochen.")
                if core.closed or (
                    core.audio.speech is not None
                    and core.audio.speech.returncode is None
                ):
                    raise ValueError(
                        "Aufnahme durch Audioausgabe oder Beenden abgebrochen."
                    )
                frame, overflow = stream.read(chunk)
                if overflow:
                    raise ValueError("Mikrofonpuffer übergelaufen.")
                frames.append(frame[:, 0].copy())
                active = float(np.sqrt(np.mean(frame**2))) >= self.threshold
                if active:
                    voice_seen, silence_since = True, None
                elif voice_seen:
                    silence_since = silence_since or time.monotonic()
                    if time.monotonic() - silence_since > 0.8:
                        break
                elif len(frames) > 30:
                    raise ValueError("Keine Sprache erkannt.")
        if not voice_seen:
            raise ValueError("Keine Sprache erkannt.")
        return np.concatenate(frames)

    async def listen(self, core) -> str:
        if core.privacy:
            raise ValueError("Mikrofon ist durch Privatsphäre gesperrt.")
        # Musik bewusst pausieren; Sprachausgabe vor Aufnahme beenden.
        resume = core.audio.music_state == "PLAYING"
        if resume:
            await core.audio.pause(True)
        generation = core.audio.generation
        await core.audio._terminate(core.audio.speech)
        try:
            core.attend()
            core.expressions.set("listening", "LISTENING", 60, 15)
            audio = await asyncio.to_thread(self.record, core)

            def transcribe() -> str:
                segments, _ = self.model.transcribe(
                    audio, language="de", beam_size=1, vad_filter=True
                )
                return " ".join(segment.text.strip() for segment in segments)

            text = await asyncio.to_thread(transcribe)
            return "" if core.privacy else text
        finally:
            core.expressions.clear("listening")
            if (
                resume
                and generation == core.audio.generation
                and core.audio.music_state == "PAUSED"
                and not core.privacy
            ):
                await core.audio.pause(False)

    async def dialogue(self, core) -> None:
        """Halbduplex: Anrede, Frage, Antwort, begrenztes Folgefenster; kein Mikrofon bei TTS."""
        follow_until = 0.0
        while not core.closed:
            if core.privacy:
                await asyncio.sleep(0.3)
                continue
            try:
                if time.monotonic() >= follow_until:
                    print("Warte auf Hey Rovo …", flush=True)
                    if not await asyncio.to_thread(self.wait_wake, core):
                        continue
                    core.expressions.set("listening", "LISTENING", 60, 15)
                    await core.audio.speak("Ja?")
                text = await self.listen(core)
                if not text.strip():
                    follow_until = 0
                    continue
                result = await core.execute(
                    {"type": "text", "args": {"text": text}}, session="hands-free"
                )
                print("Rovo>", result["spoken_reply"], flush=True)
                if result["intent"] not in {"stop", "audio.stop", "privacy.enable"}:
                    face = result["data"].get("emotion", "NEUTRAL")
                    core.expressions.set(
                        "speech", "TALKING" if face == "NEUTRAL" else face, 40, 120
                    )
                    try:
                        await core.audio.speak(result["spoken_reply"])
                    finally:
                        core.expressions.clear("speech")
                    follow_until = time.monotonic() + 15
                else:
                    follow_until = 0
            except (ValueError, OSError, TimeoutError):
                follow_until = 0
                core.expressions.clear("listening")
                await asyncio.sleep(0.5)
