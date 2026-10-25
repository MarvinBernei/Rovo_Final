"""Lokale Spiele, monotone Stoppuhr und persistente Wecker."""

from __future__ import annotations

import datetime as dt
import json
import random
import re
import time
import uuid
from importlib.resources import files
from zoneinfo import ZoneInfo


class Activities:
    def __init__(self, store, timezone: str):
        self.store, self.zone = store, ZoneInfo(timezone)
        self.games, self.watches = {}, {}
        store.db.execute("""CREATE TABLE IF NOT EXISTS alarms(id TEXT PRIMARY KEY, label TEXT NOT NULL,
                         hour INTEGER NOT NULL, minute INTEGER NOT NULL, weekdays TEXT NOT NULL,
                         enabled INTEGER NOT NULL, last_day TEXT)""")
        store.db.execute("""CREATE TABLE IF NOT EXISTS reminders(id TEXT PRIMARY KEY, text TEXT NOT NULL,
                         hour INTEGER NOT NULL, minute INTEGER NOT NULL, weekdays TEXT NOT NULL,
                         enabled INTEGER NOT NULL, last_day TEXT)""")
        store.db.commit()

    def game(self, action: str, session: str) -> str:
        if action == "cancel":
            self.games.pop(session, None)
            return "Spiel beendet."
        if action == "numbers":
            self.games[session] = {
                "type": "numbers",
                "secret": random.randint(1, 100),
                "tries": 0,
                "until": time.monotonic() + 600,
            }
            return "Ich denke an eine Zahl von 1 bis 100. Welche Zahl vermutest du? Sage Spiel beenden zum Abbrechen."
        if action == "quiz":
            questions = json.loads(
                files("rovo").joinpath("quiz.json").read_text(encoding="utf-8")
            )
            random.shuffle(questions)
            self.games[session] = {
                "type": "quiz",
                "questions": questions[:5],
                "index": 0,
                "score": 0,
                "until": time.monotonic() + 600,
            }
            return "Fünf Quizfragen. " + self.question(self.games[session])
        raise ValueError("Unbekanntes Spiel.")

    @staticmethod
    def question(game):
        item = game["questions"][game["index"]]
        return (
            item["question"]
            + " "
            + " ".join(
                f"{i + 1}: {answer}." for i, answer in enumerate(item["options"])
            )
        )

    def answer(self, session: str, text: str) -> str | None:
        from .catalog import normalize
        from .math_de import normalize_numbers

        game = self.games.get(session)
        if not game:
            return None
        if game["until"] < time.monotonic():
            self.games.pop(session)
            return "Das Spiel ist wegen längerer Pause beendet."
        value = normalize_numbers(normalize(text))
        value = re.sub(
            r"^(?:antwort|ich tippe auf|ich schätze|die zahl ist)\s+", "", value
        )
        if game["type"] == "numbers":
            if not value.isdigit():
                return None
            number = int(value)
            if not 1 <= number <= 100:
                return "Bitte eine Zahl zwischen 1 und 100 nennen."
            game["tries"] += 1
            if number == game["secret"]:
                self.games.pop(session)
                return (
                    f"Richtig! Du hast die Zahl in {game['tries']} Versuchen gefunden."
                )
            if game["tries"] >= 15:
                self.games.pop(session)
                return f"Die Zahl war {game['secret']}. Die Runde ist beendet."
            return (
                "Meine Zahl ist größer."
                if number < game["secret"]
                else "Meine Zahl ist kleiner."
            )
        item = game["questions"][game["index"]]
        choices = [normalize(option) for option in item["options"]]
        if value in {"1", "2", "3"}:
            selected = int(value) - 1
        elif normalize(text) in choices:
            selected = choices.index(normalize(text))
        else:
            return None
        correct = selected == item["answer"]
        game["score"] += int(correct)
        reply = (
            "Richtig. "
            if correct
            else "Die richtige Antwort ist " + item["options"][item["answer"]] + ". "
        ) + item["explanation"]
        game["index"] += 1
        if game["index"] >= len(game["questions"]):
            self.games.pop(session)
            return reply + f" Du hast {game['score']} von fünf Punkten erreicht."
        return reply + " Nächste Frage: " + self.question(game)

    def stopwatch(self, action: str, session: str) -> dict:
        now = time.monotonic()
        watch = self.watches.setdefault(
            session, {"elapsed": 0.0, "started": None, "laps": []}
        )
        if action == "reset":
            watch.update(elapsed=0.0, started=None, laps=[])
        elif action == "start":
            if watch["started"] is None:
                watch["started"] = now
        elif action == "pause":
            if watch["started"] is not None:
                watch["elapsed"] += now - watch["started"]
                watch["started"] = None
        elif action not in {"status", "lap"}:
            raise ValueError("Unbekannte Stoppuhraktion.")
        elapsed = watch["elapsed"] + (
            now - watch["started"] if watch["started"] is not None else 0
        )
        if action == "lap":
            watch["laps"] = (watch["laps"] + [round(elapsed, 2)])[-50:]
        return {
            "elapsed_seconds": round(elapsed, 2),
            "running": watch["started"] is not None,
            "laps": watch["laps"].copy(),
        }

    def alarm_add(
        self, hour: int, minute: int, weekdays: list[int], label: str = "Wecker"
    ) -> str:
        if (
            type(hour) is not int
            or type(minute) is not int
            or not 0 <= hour <= 23
            or not 0 <= minute <= 59
        ):
            raise ValueError("Ungültige Weckzeit.")
        if (
            not isinstance(weekdays, list)
            or any(type(day) is not int or not 0 <= day <= 6 for day in weekdays)
            or len(set(weekdays)) != len(weekdays)
        ):
            raise ValueError("Ungültige Wochentage.")
        ident = uuid.uuid4().hex
        with self.store.db:
            self.store.db.execute(
                "INSERT INTO alarms VALUES(?,?,?,?,?,?,NULL)",
                (ident, str(label)[:100], hour, minute, json.dumps(weekdays), 1),
            )
        return ident

    def alarms(self):
        return [
            dict(row)
            for row in self.store.db.execute(
                "SELECT * FROM alarms ORDER BY hour,minute"
            )
        ]

    def alarm_change(self, ident: str, action: str):
        if not isinstance(ident, str):
            raise ValueError("Wecker-ID erforderlich.")
        with self.store.db:
            if action == "delete":
                result = self.store.db.execute(
                    "DELETE FROM alarms WHERE id=?", (ident,)
                )
            elif action in {"enable", "disable"}:
                result = self.store.db.execute(
                    "UPDATE alarms SET enabled=? WHERE id=?",
                    (int(action == "enable"), ident),
                )
            else:
                raise ValueError("Unbekannte Weckeraktion.")
        if not result.rowcount:
            raise ValueError("Wecker nicht gefunden.")

    def due(self, now=None):
        now = now or dt.datetime.now(self.zone)
        day, fired = now.date().isoformat(), []
        with self.store.db:
            for alarm in self.alarms():
                weekdays = json.loads(alarm["weekdays"])
                if (
                    not alarm["enabled"]
                    or alarm["last_day"] == day
                    or (weekdays and now.weekday() not in weekdays)
                ):
                    continue
                if (alarm["hour"], alarm["minute"]) != (now.hour, now.minute):
                    continue
                self.store.db.execute(
                    "UPDATE alarms SET last_day=?,enabled=? WHERE id=?",
                    (day, int(bool(weekdays)), alarm["id"]),
                )
                fired.append(alarm)
        return fired

    def reminder_add(
        self, text: str, hour: int, minute: int, weekdays: list[int]
    ) -> str:
        if not isinstance(text, str) or not 1 <= len(text.strip()) <= 300:
            raise ValueError("Erinnerungstext muss 1 bis 300 Zeichen enthalten.")
        if (
            type(hour) is not int
            or type(minute) is not int
            or not 0 <= hour <= 23
            or not 0 <= minute <= 59
        ):
            raise ValueError("Ungültige Erinnerungszeit.")
        if not isinstance(weekdays, list) or any(
            type(day) is not int or not 0 <= day <= 6 for day in weekdays
        ):
            raise ValueError("Ungültige Erinnerungstage.")
        ident = uuid.uuid4().hex
        with self.store.db:
            self.store.db.execute(
                "INSERT INTO reminders VALUES(?,?,?,?,?,?,NULL)",
                (
                    ident,
                    text.strip(),
                    hour,
                    minute,
                    json.dumps(sorted(set(weekdays))),
                    1,
                ),
            )
        return ident

    def reminders(self):
        return [
            dict(row)
            for row in self.store.db.execute(
                "SELECT * FROM reminders ORDER BY hour,minute"
            )
        ]

    def reminder_change(self, ident: str, action: str) -> None:
        if not isinstance(ident, str):
            raise ValueError("Erinnerungs-ID erforderlich.")
        with self.store.db:
            if action == "delete":
                result = self.store.db.execute(
                    "DELETE FROM reminders WHERE id=?", (ident,)
                )
            elif action in {"enable", "disable"}:
                result = self.store.db.execute(
                    "UPDATE reminders SET enabled=? WHERE id=?",
                    (int(action == "enable"), ident),
                )
            else:
                raise ValueError("Unbekannte Erinnerungsaktion.")
        if not result.rowcount:
            raise ValueError("Erinnerung nicht gefunden.")

    def reminders_due(self, now=None):
        now = now or dt.datetime.now(self.zone)
        day, fired = now.date().isoformat(), []
        with self.store.db:
            for reminder in self.reminders():
                weekdays = json.loads(reminder["weekdays"])
                if not reminder["enabled"] or reminder["last_day"] == day:
                    continue
                if weekdays and now.weekday() not in weekdays:
                    continue
                if (reminder["hour"], reminder["minute"]) != (now.hour, now.minute):
                    continue
                self.store.db.execute(
                    "UPDATE reminders SET last_day=?,enabled=? WHERE id=?",
                    (day, int(bool(weekdays)), reminder["id"]),
                )
                fired.append(reminder)
        return fired
