"""Lokale Kamera-Detection; Target-Auswahl und stale-frame-Schutz getrennt testbar.

Optionale YuNet/SFace-Identifikation nutzt denselben Kamera-Worker.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, replace

from .people import Observation, similarity


@dataclass(frozen=True)
class Face:
    track_id: int
    x: float
    y: float
    width: float
    height: float
    identity: str = "UNCERTAIN"
    person_id: str | None = None
    feature: tuple[float, ...] = ()

    @property
    def area(self) -> float:
        return self.width * self.height


class TargetSelector:
    def __init__(self) -> None:
        self.current: int | None = None
        self.since = 0.0

    def choose(self, faces: list[Face], now: float) -> Face | None:
        plausible = [
            f
            for f in faces
            if 0 < f.width <= 1
            and 0 < f.height <= 1
            and 0 <= f.x <= 1
            and 0 <= f.y <= 1
        ]
        if not plausible:
            self.current = None
            return None
        largest = max(plausible, key=lambda f: f.area)
        best = largest  # Größte plausible Gesichtsbox = Nähe-Heuristik, keine Tiefenmessung.
        current = next((f for f in plausible if f.track_id == self.current), None)
        if current and current.area >= best.area * 0.95:
            return current
        if best.track_id != self.current:
            self.current, self.since = best.track_id, now
        return best


class Camera:
    def __init__(self, config: dict, motion, people=None) -> None:
        self.config, self.motion = config, motion
        self.capture = None
        self.detector = None
        self.online = False
        self.updated: float | None = None
        self.faces: list[Face] = []
        self.jpeg: bytes | None = None
        self.selector = TargetSelector()
        self.task: asyncio.Task | None = None
        self.error: str | None = None
        self.next_id = 1
        self.people = people
        self.backend = None

    async def start(self) -> None:
        if self.task:
            return
        import cv2

        from .camera_source import open_camera

        self.capture = await asyncio.to_thread(open_camera, self.config)
        self.detector = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )
        if self.people and self.people.config["enabled"]:
            try:
                from .face_backend import FaceBackend

                self.backend = await asyncio.to_thread(FaceBackend, self.people.config)
                self.people.activate(self.backend.model_id)
            except (ValueError, OSError, AttributeError, cv2.error):
                self.backend = None
                self.people.suspend()
                self.error = "Personenmodelle fehlen oder konnten nicht geladen werden. Nur Gesichtsdetektion verfügbar."
        self.online = True
        self.task = asyncio.create_task(self._run())

    def _read(self):
        import cv2

        image = self.capture.read()
        timestamp = time.monotonic()
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        detections = (
            self.backend.detect(image)
            if self.backend
            else [
                (box, None)
                for box in self.detector.detectMultiScale(
                    gray, 1.2, 5, minSize=(35, 35)
                )
            ]
        )
        height, width = gray.shape
        previous, used, faces, observations = self.faces, set(), [], []
        for (x, y, w, h), values in detections:
            cx, cy = float(x + w / 2) / width, float(y + h / 2) / height
            matches = [
                f
                for f in previous
                if f.track_id not in used
                and abs(f.x - cx) + abs(f.y - cy) < 0.15
                and (
                    values is None
                    or (f.feature and similarity(f.feature, values["feature"]) >= 0.65)
                )
            ]
            if len(matches) > 1:
                matches = []  # Keine Anmeldung auf unklar weitergereichter Track-ID.
            if matches:
                ident = min(
                    matches, key=lambda f: abs(f.x - cx) + abs(f.y - cy)
                ).track_id
            else:
                ident = self.next_id
                self.next_id += 1
            used.add(ident)
            faces.append(
                Face(
                    ident,
                    cx,
                    cy,
                    float(w) / width,
                    float(h) / height,
                    feature=values["feature"] if values else (),
                )
            )
            if values:
                observations.append(
                    Observation(track_id=ident, timestamp=timestamp, **values)
                )
        ok, jpeg = cv2.imencode(".jpg", image)
        return faces, jpeg.tobytes() if ok else None, timestamp, observations

    async def _run(self) -> None:
        try:
            while self.online:
                (
                    self.faces,
                    self.jpeg,
                    self.updated,
                    observations,
                ) = await asyncio.to_thread(self._read)
                if not self.online:
                    break
                target = self.selector.choose(self.faces, self.updated)
                if self.people and self.backend:
                    self.people.observe(
                        observations, target.track_id if target else None
                    )
                    self.faces = [
                        replace(
                            face,
                            identity=self.people.identities.get(
                                face.track_id, ("UNCERTAIN", None)
                            )[0],
                            person_id=self.people.identities.get(
                                face.track_id, ("UNCERTAIN", None)
                            )[1],
                        )
                        for face in self.faces
                    ]
                if (
                    target
                    and (
                        self.motion.tracking
                        or time.monotonic() < self.motion.social_until
                    )
                    and self.motion.pan is not None
                    and self.motion.tilt is not None
                ):
                    dx, dy = (target.x - 0.5) * 2, (target.y - 0.5) * 2
                    dz, gain = self.config["deadzone"], self.config["gain"]
                    config = self.motion.config["motion"]
                    pan = self.motion.pan + (
                        dx * gain * config["pan"]["direction"] if abs(dx) > dz else 0
                    )
                    tilt = self.motion.tilt + (
                        dy * gain * config["tilt"]["direction"] if abs(dy) > dz else 0
                    )
                    pan = max(config["pan"]["min"], min(config["pan"]["max"], pan))
                    tilt = max(config["tilt"]["min"], min(config["tilt"]["max"], tilt))
                    try:
                        await self.motion.move(
                            pan,
                            tilt,
                            "tracking" if self.motion.tracking else "social",
                            self.updated,
                        )
                    except (ValueError, OSError, TimeoutError):
                        pass
                await asyncio.sleep(0.25 if self.backend else 0.08)
        except Exception:
            self.error = (
                "Kameraverarbeitung fehlgeschlagen. Lokale Diagnose erforderlich."
            )
        finally:
            self.online = False
            self.faces, self.jpeg, self.updated = [], None, None
            self.motion.tracking = False
            if self.people:
                self.people.suspend()

    async def stop(self) -> None:
        self.online = False
        self.motion.tracking = False
        if self.task:
            await self.task
            self.task = None
        if self.capture is not None:
            await asyncio.to_thread(self.capture.close)
            self.capture = None
        self.faces, self.jpeg, self.updated = [], None, None
        self.backend = None
        if self.people:
            self.people.suspend()

    def status(self) -> dict:
        fresh = (
            self.online
            and self.updated is not None
            and time.monotonic() - self.updated < 1
        )
        return {
            "camera_online": self.online,
            "backend": self.config["backend"],
            "tracking": self.motion.tracking,
            "face_count": len(self.faces) if fresh else None,
            "error": self.error,
            "identification": (
                "verified"
                if self.people.config["recognition_verified"]
                else "not_validated"
            )
            if self.people and self.people.online
            else "unavailable",
            "frame_age_s": time.monotonic() - self.updated
            if self.updated is not None
            else None,
        }
