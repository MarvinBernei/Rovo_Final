"""Lokale, einwilligungsgebundene Personenprofile und geführtes Enrollment.

Keine Bilder/Embeddings an LLMs. Datenbankzugriffe ausschließlich im Core-Loop.
Automatisches Anbieten ist keine automatische Registrierung.
"""

from __future__ import annotations

import datetime as dt
import json
import math
import re
import time
import uuid
from dataclasses import dataclass
from zoneinfo import ZoneInfo

POSES = ("front", "left", "right", "up", "down")
GUIDANCE = {
    "front": "Bitte schau gerade in die Kamera und bewege deinen Kopf ganz leicht.",
    "left": "Bitte drehe deinen eigenen Kopf langsam etwas nach links.",
    "right": "Bitte drehe deinen eigenen Kopf langsam etwas nach rechts.",
    "up": "Bitte hebe dein Kinn ein wenig und schau etwas nach oben.",
    "down": "Bitte senke dein Kinn ein wenig und schau etwas nach unten.",
}


def unit(vector) -> tuple[float, ...]:
    if not isinstance(vector, (list, tuple)) or not 2 <= len(vector) <= 1024:
        raise ValueError("Ungültiger Merkmalsvektor.")
    if any(type(v) not in (int, float) or not math.isfinite(v) for v in vector):
        raise ValueError("Ungültige Gesichtsmerkmale.")
    norm = math.sqrt(sum(v * v for v in vector))
    if norm < 1e-8:
        raise ValueError("Leerer Merkmalsvektor.")
    return tuple(v / norm for v in vector)


def similarity(a, b) -> float:
    if len(a) != len(b):
        return -1.0
    return sum(x * y for x, y in zip(a, b))


@dataclass(frozen=True)
class Observation:
    track_id: int
    feature: tuple[float, ...]
    timestamp: float
    yaw: float = 0.0  # Landmark-Proxys, keine gemessenen Winkel.
    pitch: float = 0.45
    sharpness: float = 100.0
    brightness: float = 120.0
    face_pixels: float = 120.0
    image: bytes | None = (
        None  # Optionaler ausgerichteter Gesichtsausschnitt, nur im RAM.
    )
    fingerprint: int = 0

    @property
    def good(self) -> bool:
        return (
            self.face_pixels >= 80
            and self.sharpness >= 60
            and 35 <= self.brightness <= 225
            and all(
                math.isfinite(v)
                for v in (
                    self.yaw,
                    self.pitch,
                    self.sharpness,
                    self.brightness,
                    self.face_pixels,
                )
            )
        )


class People:
    def __init__(
        self, store, config: dict, timezone: str, emit, pause_tracking
    ) -> None:
        self.db, self.config, self.timezone = store.db, config, timezone
        self.emit, self.pause_tracking = emit, pause_tracking
        self.model_id: str | None = None
        self.online = False
        self.incompatible_profiles = False
        self.observations: dict[int, Observation] = {}
        self.identities: dict[int, tuple[str, str | None]] = {}
        self.stable: dict[int, tuple[str, int, float]] = {}
        self.gallery: dict[str, list[tuple[float, ...]]] = {}
        self.target_id: int | None = None
        self.job: dict | None = None
        self.last_offer = -1e9
        self.snooze_until = 0.0
        self.liveness: dict | None = None
        self.db.executescript("""
          PRAGMA foreign_keys=ON;
          CREATE TABLE IF NOT EXISTS persons(
            id TEXT PRIMARY KEY, name TEXT NOT NULL, info TEXT NOT NULL DEFAULT '',
            notes TEXT NOT NULL DEFAULT '', model_id TEXT NOT NULL, consent_at TEXT NOT NULL,
            store_images INTEGER NOT NULL, created_at TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS face_samples(
            person_id TEXT NOT NULL REFERENCES persons(id) ON DELETE CASCADE,
            pose TEXT NOT NULL, feature TEXT NOT NULL, image BLOB);
          CREATE TABLE IF NOT EXISTS person_facts(
            id TEXT PRIMARY KEY, person_id TEXT NOT NULL REFERENCES persons(id) ON DELETE CASCADE,
            topic TEXT NOT NULL, text TEXT NOT NULL, greeting INTEGER NOT NULL DEFAULT 0,
            last_used_day TEXT);
          CREATE TABLE IF NOT EXISTS greetings(
            person_id TEXT NOT NULL REFERENCES persons(id) ON DELETE CASCADE,
            day TEXT NOT NULL, PRIMARY KEY(person_id,day));
        """)

    def activate(self, model_id: str) -> None:
        self.model_id, self.online = model_id, True
        self.reload()

    def reload(self) -> None:
        self.gallery = {}
        self.incompatible_profiles = bool(
            self.db.execute(
                "SELECT 1 FROM persons WHERE model_id<>? LIMIT 1", (self.model_id,)
            ).fetchone()
        )
        buckets: dict[tuple[str, str], list[tuple[float, ...]]] = {}
        rows = self.db.execute(
            "SELECT s.person_id,s.pose,s.feature FROM face_samples s JOIN persons p ON p.id=s.person_id WHERE p.model_id=?",
            (self.model_id,),
        )
        for row in rows:
            vector = unit(json.loads(row["feature"]))
            buckets.setdefault((row["person_id"], row["pose"]), []).append(vector)
        for (person, _), vectors in buckets.items():
            mean = unit([sum(values) for values in zip(*vectors)])
            self.gallery.setdefault(person, []).append(mean)

    def profiles(self) -> list[dict]:
        return [
            dict(row)
            for row in self.db.execute("""SELECT p.id,p.name,p.info,p.notes,p.model_id,p.consent_at,
          p.store_images,COUNT(s.person_id) AS sample_count,SUM(s.image IS NOT NULL) AS image_count
          FROM persons p LEFT JOIN face_samples s ON s.person_id=p.id GROUP BY p.id ORDER BY p.name""")
        ]

    def classify(self, obs: Observation) -> tuple[str, str | None]:
        if not obs.good:
            return "UNCERTAIN", None
        scores = sorted(
            (
                (max(similarity(obs.feature, v) for v in vectors), ident)
                for ident, vectors in self.gallery.items()
            ),
            reverse=True,
        )
        if not scores or scores[0][0] < self.config["unknown_threshold"]:
            if self.incompatible_profiles:
                return "UNCERTAIN", None
            return "UNKNOWN", None
        if (
            self.config["recognition_verified"]
            and scores[0][0] >= self.config["known_threshold"]
            and (
                len(scores) == 1
                or scores[0][0] - scores[1][0] >= self.config["match_margin"]
            )
        ):
            return "KNOWN", scores[0][1]
        return "UNCERTAIN", None

    def observe(
        self,
        observations: list[Observation],
        target_id: int | None,
        now: float | None = None,
    ) -> None:
        if not self.online:
            return
        now = time.monotonic() if now is None else now
        self.observations = {
            o.track_id: o for o in observations if 0 <= now - o.timestamp < 0.75
        }
        self.target_id = target_id
        self._observe_liveness(target_id, now)
        self.identities = {}
        for track in list(self.stable):
            if track not in self.observations:
                self.stable.pop(track)
        for track, obs in self.observations.items():
            state, person = self.classify(obs)
            key = state + ":" + (person or "")
            old, count, since = self.stable.get(track, ("", 0, now))
            count, since = (count + 1, since) if old == key else (1, now)
            self.stable[track] = (key, count, since)
            stable = count >= 5 and now - since >= 1
            self.identities[track] = (state, person) if stable else ("UNCERTAIN", None)
            if (
                self.config["liveness_required"]
                and self.identities[track][0] == "KNOWN"
                and not self.liveness_verified(track, now)
            ):
                self.identities[track] = ("UNCERTAIN", None)
        if self.job and self.job["state"] == "CAPTURING":
            self._capture(now)
            return
        if self.job:
            if now > self.job["deadline"]:
                self.cancel("Anmeldung wegen Zeitüberschreitung abgebrochen.")
            return
        state, person = self.identities.get(target_id, ("UNCERTAIN", None))
        # Keine Namensausgabe bei Mehrdeutigkeit; Angebote ausschließlich bei genau einer Person.
        if (
            state == "KNOWN"
            and person
            and self.config["greet_daily"]
            and now >= self.snooze_until
        ):
            self.greet(person)
        elif (
            state == "UNKNOWN"
            and len(self.observations) == 1
            and self.config["offer_enrollment"]
            and now >= self.snooze_until
            and now - self.last_offer >= 180
            and now - self.stable[target_id][2] >= 3
        ):
            self.last_offer = now
            self.job = {
                "state": "WAIT_NAME",
                "track_id": target_id,
                "deadline": now + 60,
                "session": None,
            }
            self.emit(
                "Hallo! Ich habe für dich noch kein sicheres Profil gefunden. Wie heißt du? Wenn du möchtest, kann ich mir danach mit deiner Erlaubnis dein Gesicht lokal merken.",
                "people.offer",
            )

    def request_liveness(self) -> dict:
        if not self.online or self.target_id not in self.observations:
            raise ValueError(
                "Für die Lebendprüfung muss genau eine Person sichtbar sein."
            )
        if len(self.observations) != 1:
            raise ValueError("Lebendprüfung benötigt genau eine Person im Bild.")
        import random

        sequence = random.choice(
            (["left", "right", "front"], ["right", "left", "front"])
        )
        now = time.monotonic()
        self.liveness = {
            "track_id": self.target_id,
            "sequence": sequence,
            "index": 0,
            "deadline": now + self.config["liveness_timeout_seconds"],
            "verified_until": 0.0,
        }
        return self.liveness_status()

    def _observe_liveness(self, target_id: int | None, now: float) -> None:
        job = self.liveness
        if not job or job["verified_until"] > now:
            return
        if now > job["deadline"] or target_id != job["track_id"]:
            self.liveness = None
            return
        obs = self.observations.get(target_id)
        if not obs:
            return
        expected = job["sequence"][job["index"]]
        matched = (
            (expected == "left" and obs.yaw <= -0.18)
            or (expected == "right" and obs.yaw >= 0.18)
            or (expected == "front" and abs(obs.yaw) <= 0.08)
        )
        if matched:
            job["index"] += 1
            if job["index"] == len(job["sequence"]):
                job["verified_until"] = now + 60

    def liveness_verified(self, track_id: int, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        return bool(
            self.liveness
            and self.liveness["track_id"] == track_id
            and self.liveness["verified_until"] > now
        )

    def liveness_status(self) -> dict:
        now = time.monotonic()
        job = self.liveness
        if not job:
            return {"state": "IDLE", "required": self.config["liveness_required"]}
        verified = job["verified_until"] > now
        return {
            "state": "VERIFIED" if verified else "CHALLENGE",
            "required": self.config["liveness_required"],
            "next": None if verified else job["sequence"][job["index"]],
            "expires_in_s": max(
                0,
                (job["verified_until"] if verified else job["deadline"]) - now,
            ),
        }

    def _fresh_target(self, track: int | None = None) -> Observation:
        now = time.monotonic()
        if not self.online or len(self.observations) != 1:
            raise ValueError(
                "Für die Anmeldung muss genau eine Person eindeutig vor der Kamera sein."
            )
        obs = next(iter(self.observations.values()))
        if track is not None and obs.track_id != track:
            raise ValueError(
                "Die ursprüngliche Zielperson ist nicht mehr eindeutig im Bild."
            )
        if not 0 <= now - obs.timestamp <= 0.75 or not obs.good:
            raise ValueError(
                "Bitte gut beleuchtet und deutlich vor die Kamera schauen."
            )
        return obs

    def request(self, name: str, session: str, store_images: bool = False) -> dict:
        if (
            not isinstance(name, str)
            or not 1 <= len(name.strip()) <= 60
            or not re.fullmatch(r"[\wÄÖÜäöüß '\-]+", name.strip())
        ):
            raise ValueError(
                "Bitte einen kurzen Anzeigenamen ohne Sonderbefehle nennen."
            )
        if type(store_images) is not bool:
            raise ValueError("Bildspeicherung muss ausdrücklich an oder aus sein.")
        if self.job and self.job["state"] not in {"WAIT_NAME"}:
            raise ValueError("Es läuft bereits eine Anmeldung. Zuerst abbrechen.")
        if self.job and self.job.get("session") not in {None, session}:
            raise ValueError("Die Anmeldung gehört zu einer anderen Sitzung.")
        obs = self._fresh_target(self.job["track_id"] if self.job else None)
        if self.incompatible_profiles:
            raise ValueError(
                "Vorhandene Profile verwenden ein anderes Gesichtsmodell. Zuerst eine bewusste Migration planen."
            )
        if self.identities.get(obs.track_id, ("UNCERTAIN", None))[0] != "UNKNOWN":
            raise ValueError(
                "Identität noch unsicher oder bereits bekannt. Kein neues Profil angelegt."
            )
        if self.db.execute("SELECT COUNT(*) FROM persons").fetchone()[0] >= 100:
            raise ValueError("Profilgrenze erreicht.")
        self.pause_tracking()
        self.job = {
            "state": "WAIT_CONSENT",
            "name": name.strip(),
            "track_id": obs.track_id,
            "session": session,
            "token": uuid.uuid4().hex,
            "deadline": time.monotonic() + 60,
            "reference": obs.feature,
            "store_images": store_images,
        }
        question = (
            f"Hallo {name.strip()}! Darf ich dein Gesicht zur späteren Wiedererkennung lokal speichern? "
            + (
                "Dabei werden auch die ausgewählten Gesichtsbilder dauerhaft lokal gespeichert. "
                if store_images
                else "Gesichtsbilder werden nicht dauerhaft gespeichert, nur lokale Merkmale. "
            )
            + "Bitte bestätige ausdrücklich oder sage Nein."
        )
        return {
            "message": question,
            "confirmation_token": self.job["token"],
            "state": "WAIT_CONSENT",
        }

    def consent(self, session: str, token: str, approved: bool) -> dict:
        job = self.job
        if (
            not job
            or job["state"] != "WAIT_CONSENT"
            or job["session"] != session
            or job["token"] != token
            or time.monotonic() > job["deadline"]
        ):
            raise ValueError("Keine passende aktuelle Einwilligungsanfrage.")
        if type(approved) is not bool:
            raise ValueError("Ausdrückliche Ja-/Nein-Einwilligung erforderlich.")
        if not approved:
            self.cancel()
            return {
                "message": "Keine Gesichtsmerkmale oder Bilder gespeichert.",
                "state": "CANCELLED",
            }
        obs = self._fresh_target(job["track_id"])
        if similarity(obs.feature, job["reference"]) < 0.65:
            self.cancel()
            raise ValueError(
                "Zielperson nicht mehr sicher zugeordnet. Anmeldung abgebrochen."
            )
        job.update(
            state="CAPTURING",
            deadline=time.monotonic() + 300,
            samples=[],
            pose_index=0,
            consent_at=dt.datetime.now(dt.timezone.utc).isoformat(),
            last_sample=0.0,
            last_fingerprint=None,
            baseline_pitch=obs.pitch,
            last_prompt=0.0,
        )
        self.emit(GUIDANCE["front"], "people.guidance")
        return {
            "message": "Einwilligung erfasst. " + GUIDANCE["front"],
            "state": "CAPTURING",
        }

    def _capture(self, now: float) -> None:
        job = self.job
        if now > job["deadline"]:
            self.cancel("Anmeldung abgelaufen. Temporäre Aufnahmen verworfen.")
            return
        try:
            obs = self._fresh_target(job["track_id"])
        except ValueError:
            if now - job["last_prompt"] > 8:
                job["last_prompt"] = now
                self.emit(
                    "Bitte bleibe allein und gut sichtbar vor der Kamera. Die Aufnahme ist pausiert.",
                    "people.guidance",
                )
            return
        if similarity(obs.feature, job["reference"]) < 0.65:
            self.cancel(
                "Personenzuordnung unsicher. Anmeldung ohne Speicherung abgebrochen."
            )
            return
        pose = POSES[job["pose_index"]]
        pitch_delta = obs.pitch - job["baseline_pitch"]
        correct = {
            "front": abs(obs.yaw) < 0.12 and abs(pitch_delta) < 0.12,
            "left": obs.yaw > 0.12,
            "right": obs.yaw < -0.12,
            "up": pitch_delta < -0.10 and abs(obs.yaw) < 0.2,
            "down": pitch_delta > 0.10 and abs(obs.yaw) < 0.2,
        }[pose]
        diverse = (
            job["last_fingerprint"] is None
            or (obs.fingerprint ^ job["last_fingerprint"]).bit_count() >= 2
        )
        if not correct or now - job["last_sample"] < 0.35 or not diverse:
            return
        if job["store_images"] and not obs.image:
            return
        job["samples"].append(
            (pose, obs.feature, obs.image if job["store_images"] else None)
        )
        job["last_sample"], job["last_fingerprint"] = now, obs.fingerprint
        count = sum(sample[0] == pose for sample in job["samples"])
        if count < self.config["samples_per_pose"]:
            return
        job["pose_index"] += 1
        job["last_fingerprint"] = None
        if job["pose_index"] < len(POSES):
            self.emit(GUIDANCE[POSES[job["pose_index"]]], "people.guidance")
        else:
            self._commit()

    def _commit(self) -> None:
        job = self.job
        vectors = [sample[1] for sample in job["samples"]]
        mean = unit([sum(items) for items in zip(*vectors)])
        if any(
            max(similarity(mean, vector) for vector in existing)
            >= self.config["known_threshold"]
            for existing in self.gallery.values()
        ):
            self.cancel(
                "Es gibt möglicherweise bereits ein passendes Profil. Bitte vorhandene Profile prüfen; kein Doppelprofil angelegt."
            )
            return
        ident = uuid.uuid4().hex
        with self.db:
            self.db.execute(
                "INSERT INTO persons(id,name,model_id,consent_at,store_images,created_at) VALUES(?,?,?,?,?,?)",
                (
                    ident,
                    job["name"],
                    self.model_id,
                    job["consent_at"],
                    int(job["store_images"]),
                    job["consent_at"],
                ),
            )
            self.db.executemany(
                "INSERT INTO face_samples(person_id,pose,feature,image) VALUES(?,?,?,?)",
                [
                    (ident, pose, json.dumps(feature), image)
                    for pose, feature, image in job["samples"]
                ],
            )
        name = job["name"]
        self.job = None
        self.reload()
        self.emit(
            f"Danke {name}, dein lokales Profil wurde angelegt. Die Wiedererkennungsqualität muss am Gerät geprüft werden.",
            "people.enrolled",
        )

    def cancel(self, message: str | None = None) -> None:
        self.job = None  # Unbestätigte Namen und temporäre Bilder/Merkmale freigeben.
        self.snooze_until = time.monotonic() + 300
        if message:
            self.emit(message, "people.cancelled")

    def suspend(self) -> None:
        self.cancel()
        self.liveness = None
        self.online = False
        self.observations.clear()
        self.identities.clear()
        self.stable.clear()
        self.target_id = None

    def current_person(self) -> str:
        obs = self._fresh_target()
        state, person = self.identities.get(obs.track_id, ("UNCERTAIN", None))
        if state != "KNOWN" or not person:
            raise ValueError("Ich kann dich gerade keiner Person sicher zuordnen.")
        return person

    def greet(self, ident: str) -> None:
        day = dt.datetime.now(ZoneInfo(self.timezone)).date().isoformat()
        with self.db:
            claimed = self.db.execute(
                "INSERT OR IGNORE INTO greetings VALUES(?,?)", (ident, day)
            ).rowcount
        if not claimed:
            return
        person = self.db.execute(
            "SELECT name FROM persons WHERE id=?", (ident,)
        ).fetchone()
        if not person:
            return
        text = f"Hallo {person['name']}, schön dich heute zu sehen!"
        # Nur ausdrücklich für Begrüßungen freigegebene Themen, höchstens einmal pro Woche.
        facts = self.db.execute(
            "SELECT * FROM person_facts WHERE person_id=? AND greeting=1 ORDER BY COALESCE(last_used_day,'')",
            (ident,),
        ).fetchall()
        for fact in facts:
            if (
                not fact["last_used_day"]
                or (
                    dt.date.fromisoformat(day)
                    - dt.date.fromisoformat(fact["last_used_day"])
                ).days
                >= 7
            ):
                text += f" Wie läuft es mit deinem Thema {fact['topic']}?"
                with self.db:
                    self.db.execute(
                        "UPDATE person_facts SET last_used_day=? WHERE id=?",
                        (day, fact["id"]),
                    )
                break
        self.emit(text, "people.greeting")

    def facts(self, ident: str) -> list[dict]:
        return [
            dict(row)
            for row in self.db.execute(
                "SELECT id,topic,text,greeting FROM person_facts WHERE person_id=?",
                (ident,),
            )
        ]

    def add_fact(
        self, ident: str, topic: str, text: str, greeting: bool = False
    ) -> str:
        if not isinstance(ident, str):
            raise ValueError("Personen-ID erforderlich.")
        if not self.db.execute(
            "SELECT id FROM persons WHERE id=?", (ident,)
        ).fetchone():
            raise ValueError("Profil nicht gefunden.")
        if (
            not isinstance(topic, str)
            or not 1 <= len(topic.strip()) <= 60
            or not isinstance(text, str)
            or not 1 <= len(text.strip()) <= 500
            or type(greeting) is not bool
        ):
            raise ValueError(
                "Kurzes Thema und ausdrücklich mitgeteilten Profiltext angeben."
            )
        ident_fact = uuid.uuid4().hex
        with self.db:
            self.db.execute(
                "INSERT INTO person_facts(id,person_id,topic,text,greeting) VALUES(?,?,?,?,?)",
                (ident_fact, ident, topic.strip(), text.strip(), int(greeting)),
            )
        return ident_fact

    def update(self, ident: str, name: str, info: str = "", notes: str = "") -> None:
        if (
            any(not isinstance(v, str) for v in (ident, name, info, notes))
            or not 1 <= len(name.strip()) <= 60
            or len(info) > 500
            or len(notes) > 1000
        ):
            raise ValueError("Ungültige Profildaten.")
        with self.db:
            if not self.db.execute(
                "UPDATE persons SET name=?,info=?,notes=? WHERE id=?",
                (name.strip(), info, notes, ident),
            ).rowcount:
                raise ValueError(
                    "Nur bestehende, eingewilligte Gesichtsprofile bearbeiten. Für neue Profile Anmeldung starten."
                )

    def delete(self, ident: str, confirmed: bool) -> None:
        if confirmed is not True or not isinstance(ident, str):
            raise ValueError(
                "Profil-ID und ausdrückliche Löschbestätigung erforderlich."
            )
        with self.db:
            if not self.db.execute("DELETE FROM persons WHERE id=?", (ident,)).rowcount:
                raise ValueError("Profil nicht gefunden.")
        self.identities.clear()
        self.stable.clear()
        self.cancel()
        self.reload()

    def status(self) -> dict:
        job = self.job
        return {
            "online": self.online,
            "verified": self.config["recognition_verified"],
            "model_id": self.model_id,
            "profile_count": len(self.profiles()),
            "liveness": self.liveness_status(),
            "enrollment": {
                "state": job["state"],
                "accepted": len(job.get("samples", [])),
                "target": self.config["samples_per_pose"] * 5,
                "pose": POSES[min(job.get("pose_index", 0), 4)],
            }
            if job
            else {"state": "IDLE"},
        }
