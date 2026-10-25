> Aktueller Stand: Die übersichtliche Verbindungsseite unterstützt OpenAI, Claude, Gemini, OpenRouter, Mistral, Groq und Spotify. Keys und Modellauswahl werden je Anbieter auf dem Core gespeichert. [Einrichtung und Pi-Abnahme](docs/VERBINDUNGEN.md). Keine lokalen LLMs; STT/TTS bleiben lokal. Echte Anbieter-/Pi-Abnahme steht aus.

# ROVO – neues Programmpaket

Zur Orientierung: [Codestruktur und Entwicklungsprüfungen](docs/CODESTRUKTUR.md).

Node-RED verwendet jetzt **MQTT für Befehle/Status/Antworten**, die Kameravorschau
bleibt HTTP: [Einrichtung und Zugriffsschutz](docs/MQTT_UND_KAMERA.md).
Die ergänzten Zustandsdaten und Dashboard-Regler sind in
[Dashboard-Datenaustausch](docs/DASHBOARD_DATEN.md) beschrieben.

Dieses Paket setzt die vorliegende ROVO-Wissensbasis als getrennten neuen Entwicklungsstand um. Es enthält Python-Programme für den Raspberry Pi bzw. die lokale Simulation, Nano-ESP32-Firmware, einen importierbaren Node-RED-Dashboard-2.0-Flow und Tests. Sprache und Dokumentation sind Deutsch.

**Stand: 22.10.2026. Entwicklungsstand, noch keine am Roboter abgenommene Komplettsoftware.** Python-Simulations-/Mocktests und statische Paketprüfungen werden lokal ausgeführt. Firmware-Kompilierung und echte Hardwaretests bleiben offen. Der genaue Prüfstand steht in [ROVO_PROGRESS.md](ROVO_PROGRESS.md).

Neu: Spotify-Connect-Anbindung, getrennte Sprach-/Musiklautstärke, Sprechtempo,
Bewegungsprofile, begrenzte relative Winkel und Tracking-Rückkehr nach manuellen
Befehlen. Beispiele, Einrichtung und Grenzen: [Musik und Sprachsteuerung](docs/MUSIK_UND_STEUERUNG.md).

Optional vorbereitet: [WLAN-Einrichtung am Handy](docs/WLAN_EINRICHTUNG.md) mit
automatischem Einrichtungsnetz bei fehlender WLAN-Verbindung. Separater Wächter
und Dienstvorlage, standardmäßig aus; externes WiFi Connect und Pi-Abnahme erforderlich.

Weitere Ergänzungen: [freihändiger Dialog, LLM-Rolle mit Emotionen, Kopfgesten,
Aufmerksamkeitsblicke, Spiele und Wecker](docs/DIALOG_VERHALTEN_UND_SPIELE.md).
Automatische mechanische Kalibrierung bleibt ohne bestätigte Sensorik gesperrt;
Akkuwerte benötigen eine echte unterstützte Messquelle.

Bestätigte UPS: [Waveshare UPS HAT (E) am Pi 5](docs/UPS_HAT_E.md), mit optionalem
I²C-Leseadapter. Standardmäßig bleibt der Hardwarezugriff ausgeschaltet.

## Schnellstart ohne Roboter

Voraussetzung: Python 3.11 oder neuer. Die virtuelle Umgebung auf dem jeweiligen Zielsystem erstellen; eine kopierte `.venv` kann auf einen dort fehlenden Interpreter verweisen. Die jüngsten Windows-Prüfungen verwenden einen lokal vorhandenen Interpreter mit den Projektpaketen. Ältere Fortschrittseinträge ohne Laufzeittests beschreiben den damaligen Stand.

Im Projektverzeichnis mit vorhandenem Python:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m rovo cli
```

Die Basis benutzt nur die Python-Standardbibliothek; auf Windows installiert das Paket zusätzlich die Zeitzonendaten. Kein Modell, Cloudkonto oder Roboter ist für den Textdialog erforderlich.

Beispiele:

```text
Hallo Rovo
Was bedeutet Rovo?
Was ist fünfundzwanzig mal siebzehn?
Was ist 2 plus 3 mal 4?
Wie viel sind 20 Prozent von 150?
Wie spät ist es?
Timer auf zehn Sekunden
Wie lange läuft mein Timer noch?
Merk dir, dass ich Wasser trinken möchte
Zeig meine Notizen
Lösche meine letzte Notiz
Nein
Wie viel Akku hast du?
Nicht herunterfahren
/status
/quit
```

Für simulierte Bewegungen:

```powershell
.\.venv\Scripts\python.exe -m rovo cli --config config/simulation.json
```

Danach `Home`, `Schau nach links`, `Noch ein Stück`, `Stopp`. Die Winkel in `simulation.json` sind **synthetische Testwerte**, keine mechanische Kalibrierung. Mit dieser Datei wird kein Serial-Port geöffnet. `START_SIMULATION.cmd` startet denselben Modus.

Einzelprüfung:

```powershell
.\.venv\Scripts\python.exe -m rovo cli --text "Was ist 25 mal 17?"
.\.venv\Scripts\python.exe -m rovo diagnose
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Programme und Dateien

| Teil | Datei | Aufgabe |
| --- | --- | --- |
| Start und Lebenszyklus | `rovo/main.py` | CLI, HTTP-Dienst, Push-to-talk, Diagnose, Cleanup |
| Gemeinsamer Kern | `rovo/core.py` | Befehle, lokale Antworten, Fähigkeiten, Timer-Ereignisse |
| Sprachregeln | `rovo/intents.py` | Intents, Slots, Negation, Rückfragen |
| Mathematik | `rovo/math_de.py` | Zahlwörter, Präzedenz, Prozent, Wurzel, Potenzen |
| Konfiguration | `rovo/config.py` | Schema, Werteprüfung, atomare Speicherung |
| Datenhaltung | `rovo/storage.py` | SQLite-Notizen, Timer, Pause/Fortsetzen, Auslöse-Claim |
| Bewegung | `rovo/motion.py` | Alleinige Zielquelle, Grenzen, Stop, aktuelle Beobachtungen |
| Nano-Verbindung | `rovo/esp.py` | Simulator und exklusiver versionierter Serial-Link |
| Kamera | `rovo/vision.py` | OpenCV-Detektion, temporäre Track-IDs, Zielauswahl |
| Audio | `rovo/audio.py` | Piper-TTS, aplay, lokale mpv-Musik, Pause und Stopp |
| Spracheingabe | `rovo/voice.py` | Bewusst gestartete Aufnahme, Sprachende, lokale STT |
| Textmodell | `rovo/llm.py`, `rovo/cloud_providers.py` | Sechs Cloudanbieter mit lokal geprüftem Antwort-/Emotionsvertrag; kein lokales LLM |
| Verbindungen | `rovo/connections.py`, `rovo/spotify.py` | Dashboard-Einrichtung, private Speicherung, PKCE und Token-Erneuerung |
| Status | `rovo/telemetry.py` | Echte OS-Werte, sonst `null` |
| Dashboard-API | `rovo/api.py` | Token-geschützte Loopback-Bridge auf Port 1891 |
| Nano-Firmware | `esp32/rovo_esp32/` | Parser, Limits, PWM-Interpolation, Watchdog, TFT-Augen |
| Dashboard | `nodered/rovo_neu_flows.json` | Neun Seiten unter `/rovo`, MQTT-Anbindung an den Core |
| Dashboard-Vertrag | `rovo/dashboard.py` | Sichere Befehlsübersetzung und öffentliche Statusprojektion |
| Laufzeiteinstellungen | `rovo/settings.py` | Dauerhaft speichern, vorherigen Stand und Startvorgaben wiederherstellen |
| Bewegungsgrenzen | `rovo/calibration.py` | Softwaregrenzen innerhalb bestätigter mechanischer Grenzen prüfen |
| Sprachkatalog | `rovo/catalog.json`, `rovo/catalog.py` | 436 Formulierungen in 88 Gruppen; einzige Quelle für feste Synonyme und Wissensantworten |
| Personen | `rovo/people.py`, `rovo/face_backend.py` | Lokale YuNet/SFace-Profile, geführte Anmeldung, täglicher Gruß und freiwillige Profilthemen |
| Prüfungen | `tests/test_rovo.py` | Logik-/Mocktests, keine Hardwarezugriffe |
| Strukturprüfung | `scripts/check_static.ps1` | JSON, Flow-Verweise, sichere Defaults, Firmwaremerkmale |

## Ausführliche Anleitungen

- [Installation und Bedienung](docs/INSTALLATION.md)
- [Architektur, API und Serial-Protokoll](docs/ARCHITEKTUR_UND_API.md)
- [Firmware, Pins und Hardwarefreigabe](docs/FIRMWARE_UND_HARDWARE.md)
- [Node-RED importieren und absichern](nodered/README.md)
- [Geprüfter Stand und offene Funktionen](ROVO_PROGRESS.md)
- [Sprachkatalog und Personen einrichten](docs/SPRACHKATALOG_UND_PERSONEN.md)
- [Einstellungen, Display und Bewegungsgrenzen](docs/EINSTELLUNGEN.md)
- [Erweiterte Funktionen und sichere Inbetriebnahme](docs/ERWEITERTE_FUNKTIONEN.md)

## Sicherheitsverhalten

Der Standard startet in Simulation, im Safe Mode und ohne Kalibrierung. Reale Bewegung erfordert separat eine geprüfte Konfiguration, kompatible freigegebene Firmware und die Startparameter `--connect-serial --allow-motion`. Es gibt keinen automatischen Firmwareupload, Shutdown oder Home-Lauf beim Programmstart.

Die API bindet ausschließlich an `127.0.0.1`. Token und lokale Daten gehören nicht in Git. Das Dashboard besitzt keine Schlüsselverwaltung im Browser. Kameraaufnahmen und Mikrofon-Rohdaten werden standardmäßig nicht dauerhaft gespeichert oder an ein Sprachmodell geschickt.

## Noch nicht vollständig umgesetzt

Die aktuellen Implementierungen und Prüfgrenzen stehen in [ROVO_PROGRESS.md](ROVO_PROGRESS.md). Geräteabnahme, trainiertes Rovo-Wake-Word, vollständige Cloud-Mehrproviderverwaltung, wiederkehrende Wecker/Erinnerungen, Wetter/Smart Home, Objekterkennung und Tanzchoreografien bleiben offen. Personenidentifikation benötigt lokale Modelle und bewusst validierte Wiedererkennungsschwellen. Eine automatische mechanische Anschlagsuche ist ohne geeignete Rückmeldung gesperrt.
