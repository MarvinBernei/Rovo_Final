# Ergänzter Datenaustausch mit dem Dashboard

Der alle zwei Sekunden veröffentlichte MQTT-Snapshot enthält jetzt zusätzlich
`runtime` und die öffentliche `config`. Die Daten kommen aus derselben Core-Instanz,
die auch Sprachbefehle verarbeitet. Änderungen sind beim nächsten Status sichtbar.

| Bereich | Core → Dashboard | Dashboard → Core |
|---|---|---|
| Bewegung | Pan-/Tilt-Sollwinkel, Geschwindigkeit °/s, Beschleunigung °/s², Rückkehrstatus | Profil ändern, Home, Winkel, Stopp, Gesten |
| Display | Zuletzt bestätigte Gesichtsvorgabe, auch automatische LLM-Mimik | Manuelle Gesichtswahl |
| Audio | Sprachlautstärke, Sprechtempo, Musiklautstärke, Playerzustand/Quelle, TTS-Konfiguration und Anrede-Modus | Getrennte Lautstärken und Tempo übernehmen, Sprachtest, Audio stoppen |
| Kamera | Online, Tracking, Gesichterzahl, Framealter, Totzone und Verstärkung | Kamera/Tracking an/aus, Totzone/Verstärkung und Aufmerksamkeitsblicke ändern |
| Spotify | App-/Ziel-ID, eingerichteter Zugang, Zeitpunkt letzter erfolgreicher Geräteabfrage, Quelle und lokaler Playerzustand | App speichern, PKCE-Anmeldung, Geräte laden/auswählen, bestätigt entfernen; Musiksteuerung |
| Text-KI | Anbieter/Modell, Key vorhanden, aktiviert, Zeitpunkt letzter erfolgreicher Antwort | Anbieter-Key und Modellauswahl speichern, Modell und Einwilligung speichern, kostenpflichtiger Modelltest, bestätigt entfernen |
| System/UPS | Hostname, RAM-Auslastung, Temperatur, Laufzeit und vorhandene Akkuwerte | Diagnose über Status, keine beliebigen Systembefehle |

Auf Bewegung, Audio, Kamera, Display, Verbindungen und System gibt es einen ergänzten
Bereich **Core-Laufzeitdaten und Steuerung**. Dort sind Regler mit den tatsächlichen
Einheiten angebunden. Die historischen Prozentregler für Geschwindigkeit/Glättung
bleiben deaktiviert, weil sie nicht dieselben Einheiten wie das Firmwareprofil haben.
Nicht gespeicherte Eingaben in den neuen Reglern werden nicht bei jedem Status überschrieben.
Erst eine bestätigte Antwort gibt die automatische Aktualisierung wieder frei.

Weitere unterstützte Gateway-Aktionen wie Wecker, Timer, Notizen, Stoppuhr und Spiele
können über MQTT verwendet werden. Ergebnisse stehen in der Dashboard-Nachricht unter
`ack.data`, die Aktion unter `ack.action`; Chatantworten enthalten zusätzlich `emotion`.
Hierfür wurde keine zusätzliche vollständige Verwaltungsseite für jede Funktion gebaut.

Einstellungen lassen sich im neuen Systembereich dauerhaft speichern und wiederherstellen;
Details stehen in [EINSTELLUNGEN.md](EINSTELLUNGEN.md). Sprachlautstärke/Tempo wirken
auf die nächste erzeugte Ausgabe. Displaymodi und bestätigte Softwaregrenzen sind
über eigene neue Steuerelemente angebunden. Die getrennte Seite **Verbindungen** richtet
Sechs Cloudanbieter und Spotify ein; siehe [Verbindungen](VERBINDUNGEN.md). Keys/Tokens werden nie
zurückgeliefert. `integrations`-Antworten enthalten clientgebunden `action`, `status` und
`data` (Anmeldelink oder Geräteliste), aber keine Zugangsdaten.

Unbekannt bleibt unbekannt: tatsächliche Mikrofon-/Lautsprecherfunktion, Servo-Istwinkel,
physische Displayhelligkeit und ein dauerhaft geprüfter Spotify-Kontozustand werden
nicht aus einem konfigurierten Modul abgeleitet. System-RAM wird über Linux-procfs oder
Windows-Systemwerte gelesen; fehlende Sensorwerte bleiben leer.

Nach Aktualisierung den neuen `nodered/rovo_neu_flows.json` importieren, vorhandene
ROVO-Knoten ersetzen, deployen und das Dashboard neu laden. Der laufende Core muss
ebenfalls die neue Fassung verwenden. Zugriffsschutz und Brokereinrichtung bleiben
wie in [MQTT_UND_KAMERA.md](MQTT_UND_KAMERA.md) beschrieben.
