> Aktueller Stand: Sechs Cloudanbieter und Spotify sind im Dashboard einrichtbar. [Einrichtung](VERBINDUNGEN.md). Keine lokalen LLMs; STT/TTS bleiben lokal.

# Orientierung im Quellcode

## Start und Anwendungsabläufe

```text
rovo/
  __main__.py           Einstieg für python -m rovo
  main.py               CLI, Server und Sprachmodus starten
  core.py               Ressourcen, Gateway, Status und Hintergrundaufgaben
  application/
    contracts.py        Erlaubte API-Befehle mit exakten Parametern
    actions.py          Geräte- und Verwaltungsaktionen ausführen
    dialogue.py         Spracheingaben, Bestätigungen und Antwortauswahl
```

Alle Abläufe verwenden dieselbe Core-Instanz. Die ausgelagerten Funktionen erhalten
sie ausdrücklich als Parameter und erzeugen keine zusätzlichen Gerätebesitzer.
Typimporte verwenden `TYPE_CHECKING`, um zyklische Laufzeitimporte zu vermeiden.
Die bisherigen Schnittstellen `Core.execute`, `Core.action` und `Core.text` bleiben bestehen.

## Fachmodule

| Aufgabe | Dateien |
|---|---|
| Sprachabsichten | `catalog.json` als zentrale Daten, `catalog.py` als Matcher, `intents.py` als Parameterparser |
| Sprache und Musik | `voice.py`, `audio.py`, `spotify.py` |
| LLM und Rolle | `llm.py`, `persona_de.md` |
| Anbieter und private Speicherung | `connections.py`, `cloud_http.py`, `spotify.py`; Dashboard: `nodered/connections_panel.vue` |
| Bewegung und Display | `motion.py`, `esp.py`, `expressions.py` |
| Kamera und Personen | `vision.py`, `face_backend.py`, `people.py` |
| Lokale Aktivitäten | `activities.py`, `quiz.json`, `math_de.py`, `storage.py` |
| Messwerte | `telemetry.py`, `ups_hat_e.py` |
| Konfiguration und Netzwerk | `config.py`, eigenständiger `network_setup.py` |
| Schnittstellen | `mqtt_bridge.py` für Nachrichten, `api.py` für HTTP/Kamera, `dashboard.py` für den Dashboard-Vertrag |

Die kleineren Fachmodule bleiben direkt im Paket. Weitere Unterordner würden hier
vor allem zusätzliche Importwege erzeugen. Daten bleiben neben ihren Paketmodulen,
damit auch eine installierte Version sie über `importlib.resources` findet.

## Projektordner

- `config/`: Referenz- und Beispielkonfigurationen; eigene Werte in `local.json`.
- `esp32/`: Firmware und mechanisch zu bestätigende Hardwaregrenzen.
- `nodered/`: aktueller Flow, Generator-Eingaben und historische Referenzflows.
- `scripts/`: Flowgenerator, statische Prüfungen und Dienstvorlagen.
- `tests/`: Python-Tests mit Simulationen, Mocks und temporären Dateien.
- `docs/`: Einrichtung und Funktionsgrenzen.
- `.tools/`: ignorierte historische Sicherungen; kein Teil der Laufzeit.

Referenzflows und Sicherungen wurden erhalten: Sie werden für Reproduktion oder
Vergleich gebraucht. Die einmaligen Refaktorierungsskripte wurden nach Anwendung entfernt.

## Einheitlicher Stil und Prüfung

Ruff ist als optionales Entwicklungswerkzeug unter `.[dev]` hinterlegt. Formatierung
und Import-/Fehlerprüfungen sind in `pyproject.toml` festgelegt:

```powershell
.\.venv\Scripts\python.exe -m ruff check rovo tests
.\.venv\Scripts\python.exe -m ruff format rovo tests --check
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
```

Änderungen an Ordnern müssen auch die statischen Prüfskripte berücksichtigen.
`check_static.ps1` prüft Python-Dateien einschließlich Unterordnern. Textbasierte
Vertragsprüfungen tolerieren reine Änderungen an Leerzeichen und Zeilenumbrüchen.
