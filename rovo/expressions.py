"""Ein Display-Besitzer: Betriebszustand, Antwortmimik und manuelle Vorgaben."""

import time

from .esp import FACES

EMOTIONS = frozenset(
    {"NEUTRAL", "HAPPY", "CURIOUS", "SAD", "SURPRISED", "CONFUSED", "LAUGHING", "LOVE"}
)


def emotion_for(intent: str, ok: bool = True) -> str:
    if not ok:
        return "CONFUSED"
    if intent in {"greeting", "thanks", "people.enroll.confirm"}:
        return "HAPPY"
    if intent == "fun.joke":
        return "LAUGHING"
    if intent in {"clarify", "people.enroll", "people.name"}:
        return "CURIOUS"
    return "NEUTRAL"


class Expressions:
    def __init__(self, esp):
        self.esp = esp
        self.states = {}
        self.last, self.sent = None, 0.0
        self.brightness = 100
        self.mode = "automatic"
        self.manual_face = "NEUTRAL"
        self.applied_brightness = 100

    def set(self, key: str, face: str, priority: int = 10, seconds: float = 8):
        if face not in FACES:
            raise ValueError("Unbekannte Displaymimik.")
        self.states[key] = (priority, time.monotonic() + seconds, face)

    def clear(self, key: str):
        self.states.pop(key, None)

    def reset(self):
        self.states.clear()
        self.set("stop", "NEUTRAL", 100, 2)

    async def tick(self):
        now = time.monotonic()
        self.states = {
            key: value for key, value in self.states.items() if value[1] > now
        }
        face = max(self.states.values(), default=(0, 0, "NEUTRAL"))[2]
        if self.mode == "manual" and not any(
            state[0] >= 90 for state in self.states.values()
        ):
            face = self.manual_face
        target_brightness = 0 if self.mode == "off" else self.brightness
        if self.esp.connected and target_brightness != self.applied_brightness:
            await self.esp.command("BRIGHTNESS", target_brightness)
            self.applied_brightness = target_brightness
        if self.esp.connected and (face != self.last or now - self.sent > 6):
            await self.esp.command("FACE", face)
            self.last, self.sent = face, now
