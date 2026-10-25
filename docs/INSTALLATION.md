# Installation und Bedienung

## 1. Was tatsächlich vorgefunden wurde

Der vom Nutzer genannte Ordner enthält acht Markdown-Dokumente. In Downloads und Documents wurden keine zugehörigen produktiven ROVO-Pythonprogramme, Nano-Sketches oder V5-Flowexports gefunden. Gefundene Python-Dateien im separaten CAD-Paket gehören zur Gehäuseerstellung, nicht zum Roboterbetrieb. Ein Raspberry Pi ist in dieser Sitzung nicht verbunden; Adresse, Dienste, Sensoren und geflashte Firmware wurden deshalb nicht geprüft.

Der Neuaufbau liegt separat unter `Downloads/ROVO_Neuaufbau`. Die ursprüngliche Wissensbasis und CAD-Dateien wurden nicht verändert.

## 2. Raspberry Pi vorbereiten

Die folgenden Befehle sind Anleitungen zur späteren manuellen Ausführung. Sie wurden hier nicht auf einem Pi ausgeführt.

Vor Änderungen OS, Arbeitsspeicher, vorhandene Python-/Node-RED-Dienste und Projektverzeichnisse prüfen. Keine zweite Core-Instanz mit derselben Kamera oder demselben Nano-Port starten. Bestehende Programme und Node-RED-Flows vorher sichern.

Mit vorhandenem Python und venv-Unterstützung:

```bash
cd ~/rovo
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m rovo diagnose
.venv/bin/python -m rovo cli
```

Benötigte Betriebssystempakete nicht blind nachinstallieren. Fehlende `venv`-, ALSA-, Kamera- und Compiler-Komponenten anhand des echten Raspberry-Pi-OS bestimmen. Für den Textbetrieb sind keine externen Pythonpakete nötig. Unter Linux stammen Zeitzonendaten gewöhnlich aus dem Betriebssystem.

## 3. Textmodell

Die lokale Ollama-Anbindung wurde entfernt. Alte llm-Konfigurationsfelder
aktivieren keinen lokalen Modellzugriff mehr. Ein Cloudanbieter lässt sich jetzt über das Dashboard
einrichten: [Verbindungen](VERBINDUNGEN.md). Standardmäßig bleibt Cloudzugriff aus.
Lokale Befehle, Wissensantworten, STT und TTS bleiben erhalten.

## 4. Lokale Sprachausgabe

Voraussetzungen: geprüfter ALSA-Ausgang, vorhandenes Piper-Programm und eine lokal vorhandene deutsche Stimme inklusive ihrer Modelldateien. Stimme und Binärdatei werden nicht mitgeliefert. Beim Modellbezug dessen Lizenz beachten.

```json
{
  "audio": {
    "enabled": true,
    "piper": "/ABSOLUTER/PFAD/ZU/piper",
    "voice": "/ABSOLUTER/PFAD/ZUR/deutschen-stimme.onnx",
    "output_device": "default"
  }
}
```

Piper erzeugt eine temporäre WAV-Datei. `aplay` spielt sie ab; anschließend wird sie entfernt. Alle Antworten verwenden denselben Pfad. Die Sprachlautstärke wird am realen ALSA-Mixer eingestellt. `music.volume` verändert nur die mpv-Musiklautstärke und wird nicht als Lautstärke des Lautsprechers ausgegeben.

Sprachausgabe wird im CLI im Hintergrund gestartet, damit die Befehlsannahme weiterläuft. Der reine HTTP-Chat liefert zunächst Text; er startet keine automatische TTS. Timer können über den zentralen Scheduler TTS auslösen.

## 5. Lokale Spracheingabe

```bash
.venv/bin/python -m pip install -e '.[voice]'
.venv/bin/python -m rovo voice --config config/local.json \
  --stt-model /ABSOLUTER/PFAD/ZUM/faster-whisper-modell
```

In der Konsole Enter drücken, dann sprechen. Zehn Sekunden Aufnahmegrenze; nach erkannter Sprache beendet ungefähr 0,8 Sekunden Stille die Aufnahme. Die RMS-Schwelle ist ein einfacher Startwert und keine unter realer Musik geprüfte VAD-Qualität. Die STT verwendet ein vorhandenes lokales faster-whisper-Modell, CPU/int8, zwei Threads und Deutsch.

Optional mit `--microphone "GERÄTENAME"` ein geprüftes Eingabegerät auswählen. Eine Kartennummer aus der historischen Dokumentation ist keine stabile Gerätekennung.

**Wake Word ist nicht implementiert.** Es wird weder ein trainiertes Rovo-Modell noch eine permanente Mikrofonüberwachung behauptet. Push-to-talk ist der vorhandene, bewusste Aktivierungsweg. Ein durchgängiger 20-Sekunden-Audiodialog mit Wake/VAD-Unterbrechung ist noch offen; die 20 Sekunden gelten momentan für Rückfragen zu Bewegungsfortsetzung und Notizlöschung.

## 6. Kamera und Tracking

```bash
.venv/bin/python -m pip install -e '.[vision]'
```

Die Basisimplementierung verwendet OpenCV `VideoCapture` und einen frontalen Haar-Detektor. Optional ist inzwischen ein YuNet-/SFace-Backend mit lokaler Personenverwaltung ergänzt; Einrichtung und Grenzen stehen in `SPRACHKATALOG_UND_PERSONEN.md`. CSI-Kameras auf Raspberry Pi OS benötigen je nach Treiber weiterhin einen Picamera2-Adapter. Eine USB-/V4L2-kompatible Kamera kann über `camera.index` gewählt werden.

Kamera startet nur nach `Aktiviere deine Kamera` bzw. `camera.enable`. Die Kamera liest und detektiert in einem Worker; alle Verbraucher erhalten dessen jüngstes Ergebnis. Tracking benötigt zusätzlich Kalibrierung und eine zuvor ausdrücklich angeforderte Sollposition. Keine Bewegung beginnt allein durch das Einschalten der Kamera.

Im Haar-Basisbetrieb sind temporäre Track-IDs keine belastbare Identität und reichen nicht für Enrollment. Das neue SFace-Backend ergänzt Merkmalskontinuität, eindeutige Zielzuordnung und Einpersonenprüfung; nur dieser zusätzliche Pfad ermöglicht die geführte Anmeldung. Auch er muss bei Kreuzungen und Personwechseln am Gerät geprüft werden. Veraltete Beobachtungen werden verworfen. Ein blockierender Kameratreiber kann trotz Worker das Beenden verzögern.

## 7. Lokale Musik

Voraussetzung ist ein vorhandener mpv-Player unter Linux. Audiodateien unter `data/music` speichern. Der Core lässt nur vorhandene MP3-, WAV-, OGG- und FLAC-Dateien innerhalb dieses Verzeichnisses zu. Keine beliebigen URLs oder Shellbefehle.

API-Beispiel:

```json
{"type":"music.play","args":{"path":"/home/rovo/rovo/data/music/beispiel.mp3"}}
```

Weitere Aktionen: `music.pause`, `music.resume`, `music.stop`, `music.volume` mit `{"value":30}`. TTS pausiert aktive Musik und setzt sie nur bei unverändertem Auftragszustand fort. Ein Stopp verhindert verspätetes automatisches Resume. Spotify-Titelsuche und Connect-Steuerung sind optional über [Verbindungen](VERBINDUNGEN.md) einrichtbar; Playlistverwaltung bleibt offen.

## 8. Timer und Notizen

SQLite liegt standardmäßig unter `data/rovo.sqlite3`. Andere Speicherorte mit `--data PFAD`. Notizen und Timer bleiben beim Neustart bestehen. Timerpause, Fortsetzen und Abbruch sind über API möglich. Sprachbefehle wählen nur dann selbst einen Timer, wenn genau einer aktiv ist.

Der Scheduler markiert fällige Timer transaktional als ausgelöst, bevor er ein Ereignis veröffentlicht. Das verhindert Doppelmeldungen beim erneuten Poll. Ein Stromausfall nach dem Claim und vor der Ausgabe kann jedoch eine Benachrichtigung verlieren. Es gibt keinen Anspruch auf garantiert genau einmal hörbare Alarmierung. Änderungen der Systemuhr beeinflussen die gespeicherten UTC-Epochenzeiten.

Löschen der letzten Notiz verlangt eine frische, sitzungsgebundene Bestätigung. `Nein`, ein anderer Befehl oder 20 Sekunden Ablauf verwerfen sie. Rückfragen enthalten keine Hardwarefreigabe. Die Sprachregeln sind konservative Regeln, kein vollständiges deutsches Sprachverständnis.

## 9. Tests und Diagnose

```bash
.venv/bin/python -m compileall -q rovo tests
.venv/bin/python -m unittest discover -s tests -v
```

Unter Windows zusätzlich:

```powershell
.\scripts\check_static.ps1
```

Die Tests verwenden ausschließlich FakeESP32, synthetische Gesichtsboxen, temporäre SQLite-Datenbanken und Text. Sie öffnen weder Kamera noch Serial oder Mikrofon. Firmware separat kompilieren. Danach erst schrittweise freigegebene Gerätetests durchführen.

## 10. Späterer systemd-Betrieb

`scripts/rovo.service` ist eine Vorlage mit absichtlich anzupassenden Benutzer-/Pfadangaben. Sie startet die Simulation ohne Hardwarefreigabe. Vor Installation: manuellen stabilen Start, sauberes Stoppen, Token-Dateirechte und API-Verhalten prüfen. Es wurde kein Dienst installiert oder aktiviert.

Nicht gleichzeitig mehrere CLI-/Voice-/Server-Instanzen auf reale Hardware starten. Der Single-owner-Vertrag gilt innerhalb eines Core-Prozesses; eine betriebssystemweite Geräte-Lockdatei ist noch nicht implementiert.
