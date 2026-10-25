# ROVO Neuaufbau – überprüfbarer Stand

Datum: 21.10.2026. Neues separates Programmpaket im Auftrag des Nutzers. **Kein Nachweis eines bereits laufenden Roboters.**

## Ausgangslage und Entscheidung

Gelesen wurden die acht vom Nutzer genannten Wissensbasisdateien. Die dortige Empfehlung, ausschließlich vorhandene Programme weiterzuentwickeln, wurde durch den ausdrücklichen Nutzerauftrag „die ganzen Programme neu“ für diesen separaten Entwicklungsstand ersetzt. Sicherheits- und Datenschutzanforderungen wurden in den neuen Entwurf übernommen.

Im Wissensbasisordner: ausschließlich Markdown. In den untersuchten Downloads-/Documents-Dateien: keine produktiven ROVO-Pythonprogramme, ESP32-Sketches oder historischen V5-JSON-Flows gefunden. CAD-Buildskripte in einem anderen Paket sind keine Roboterlaufzeit. Keine Raspberry-Pi-Verbindung bekannt. Pi-/Nano-/Kamera-/UPS-/Audiozustand: **UNBEKANNT**.

## Erzeugte Programme

| Bereich | Implementierung im Paket | Abnahmestand |
| --- | --- | --- |
| Python-Core und CLI | 16 Module, gemeinsame Befehlsvalidierung, lokale Antworten | Geschrieben; Laufzeittest offen |
| Konfiguration | Version 1, konservative Defaults, Werteprüfung, atomarer Schreibweg | Geschrieben; Unit-Tests offen |
| Rechner | Deutscher Zahlwort-/Präzedenzparser, Grenzen, kein eval | Geschrieben; Unit-Tests offen |
| Timer/Notizen | SQLite, Neustartspeicher, Pause/Resume/Cancel, Bestätigung | Geschrieben; Unit-Tests offen |
| Motion/Serial | FakeESP32, optionaler Serial-Link, Kalibriersperre, Stop, Handshake | Geschrieben; Mock-/Gerätetest offen |
| Nano-Firmware | Parser, Watchdog, LEDC-PWM, Smoothing, 16 TFT-Modi | Geschrieben; Build/Hardwaretest offen |
| Kamera | OpenCV-VideoCapture, Haar-Detection, temporäre Tracks, Zielauswahl | Geschrieben; Kameratest offen |
| Tracking | Aktuelle Beobachtung, Motion-Manager, manuelle Pause | Geschrieben; Integrationstest offen |
| Audio | Piper/aplay, mpv-IPC, Pause/Resume/Stop | Geschrieben; Audio-/Race-Tests offen |
| STT | Lokale Push-to-talk-Aufnahme, RMS-Sprachende, faster-whisper | Geschrieben; Mikrofontest offen |
| Lokales LLM | Ollama/LAN, nur Text, ohne Tools/Bilder | Geschrieben; Modelltest offen |
| HTTP-Bridge | Loopback, Bearer-Token, Bodylimit, kein CORS, gemeinsamer Eventloop | Geschrieben; HTTP-Laufzeittest offen |
| Node-RED | Import-JSON, sieben Seiten, eine Base, Command-/Statusbridge | Struktur geprüft; Import/Rendering offen |
| Installationsunterlagen | README, Installation, API, Firmware, Node-RED, Dienstvorlage | Dateien vorhanden |

## Tatsächlich ausgeführte Prüfungen

- Lokales Dateiinventar und Interpreter-/Werkzeugsuche ausgeführt.
- Kein nutzbarer Python-Interpreter gefunden; Windows verweist auf den Store-Alias. Kein Node.js, Git oder Arduino-CLI im abgefragten PATH gefunden.
- Genehmigter Download einer portablen Python-3.13.9-Testumgebung von python.org versucht. Firmennetz/FortiGuard blockiert den Download. Keine Umgehung und keine systemweite Installation.
- `scripts/check_static.ps1` ausgeführt: **139 statische Prüfungen bestanden**, Exitcode 0.
- Dabei JSON, eindeutige Node-IDs, sämtliche Node-RED-Verweise, sieben Seiten, eine Base, sichere Defaults, abgeschaltete Firmware-Servos, GPIO18/17 und fehlende delay-Aufrufe geprüft.
- 22 Python-Testmethoden mit positiven, negativen, Persistenz-, Sitzungs-, Timeout- und Mockfällen geschrieben. **Nicht ausgeführt.**

Statische Strukturprüfung ist kein Python-Syntaxtest und kein Beleg funktionierender Elektronik. Es wurde keine Testquote oder Erfolgsrate des Roboters behauptet.

## Nicht implementiert / noch offen

- Trainiertes Rovo-Wake-Word und durchgängiger mehrstufiger Audiodialog.
- Belastbare biometrische Personenidentifikation, Enrollment, Profilverwaltung und Duplikatprüfung.
- Picamera2-Adapter und Sensorprüfung für die tatsächliche CSI-Kamera.
- UPS-Treiber nach Bestimmung der exakten HAT-Variante.
- Spotify, Internetradio, Playlists und Beat-/Tanzsteuerung.
- Cloud-Mehrproviderverwaltung, OAuth, Kostenabrechnung und sichere Schlüsselverwaltung dafür.
- Wiederkehrende Wecker/Erinnerungen mit vollständiger DST-Policy.
- Freie Einheitenumrechnung, größere Wissenssammlung, Wetter, Smart Home, Objekterkennung und Raumscan.
- Historisches V5-Layout erhalten/migrieren, kompletter Kalibrierungsassistent, Komforteinstellungen und echter Livebild-Proxy im Dashboard.
- Prozessübergreifende Geräte-Locks, persistente Idempotenz, vollständiger Eventbus/Telemetry-Log und Kalibrierungs-Hashabgleich Pi↔Nano.

## Besondere technische Grenzen

- Erstes PWM-Aktivieren kann den Servo zur Home-Vorgabe fahren; ohne Positionsfeedback kein garantierter sanfter Übergang vom physischen Startwinkel.
- `ACK` ist Annahme; der Python-Link verarbeitet keine asynchronen DONE-Ereignisse. Keine Istpositionsmessung.
- Simple Track-ID-Zuordnung ist nicht identitätssicher und darf nicht für Enrollment genutzt werden.
- Kameratreiber können blockieren; echtes Timeout-/Cleanupverhalten noch zu messen.
- Timer-Claim verhindert erneute Auslösung, kann bei Prozess-/Stromausfall vor Ausgabe eine Meldung verlieren.
- Audioadapter und Nebenläufigkeit benötigen echte mpv-/Piper-Vertragstests. Fehlende Komponenten werden nicht als online dargestellt.
- Dienstvorlage startet nur Simulation; keinerlei Autostart eingerichtet.

## Nächste Abnahme

1. Auf einem Rechner mit Python die mitgelieferten Unit-Tests und compileall ausführen.
2. Firmware mit tatsächlichem Nano-ESP32-Boardpaket und Adafruit-Bibliotheken kompilieren.
3. Neuen Flow in einer gesicherten Node-RED-Testinstanz importieren; `_client`-Zuordnung und Offlineanzeige prüfen.
4. Reales Pi-/Hardwareinventar erheben, bestehende Programme sichern.
5. Erst nach getrennten Freigaben Display, Audio, Kamera und individuell kalibrierte Bewegung testen.

Die ursprüngliche Wissensbasis, historische Programme und laufende Dienste wurden nicht überschrieben. Keine Hardwarebewegung, kein Flashen, kein Shutdown und kein Systemdienststart wurden vorgenommen.

## 2026-10-21 – V5-Oberfläche an neuen Core angepasst

Die später vom Nutzer bereitgestellte Datei `Downloads/ROVO_V5_NodeRED.json` ersetzt die zuvor fehlende Referenz. Der Nutzer hat die Anpassung ausdrücklich beauftragt. Die vorherigen Aussagen „V5 nicht gefunden“ und „Layoutmigration offen“ beschreiben den damaligen Stand und sind durch diesen Eintrag überholt.

- Originaldatei unverändert erhalten; bytegleiche Kopie unter `nodered/ROVO_V5_original.json`. Bisheriger einfacher Flow unter `nodered/rovo_basis_vor_v5.json` gesichert.
- `nodered/rovo_neu_flows.json` nutzt jetzt alle neun V5-Seiten, Theme, CSS und Vorschauen unter `/rovo-v5`.
- Alte Test-/Integrationspfade und Host-Exec durch einen einzigen serverseitig authentifizierten RPC-Pfad ersetzt. Status stammt vom Core, Antworten bleiben clientgebunden.
- `rovo/v5.py` und `/rpc` in `rovo/api.py` ergänzen die Vertragsschicht. Geräteaktionen passieren den vorhandenen Core; `audio.stop` und ein lokaler Piper-Sprachtest ergänzt.
- Nicht unterstützte Speicherung von Kalibrierung, Grenzwerten, Cloudschlüsseln, Spotify und Personen blockiert. Originale UI-Vorschlagswerte nicht als Kalibrierung übernommen.
- Neue Tests: `tests/test_v5.py` (12 Methoden, noch nicht mit Python ausgeführt), `scripts/test_v5_bridge.mjs` und erweiterte Strukturprüfung. Generator: `scripts/adapt_v5.ps1`.
- Tatsächlich geprüft: Syntax der drei neuen Node-RED-Funktionen und aller neun Vue-Komponentenskripte in V8; **111 JavaScript-Vertragsprüfungen und 191 statische Prüfungen bestanden**. Theme und CSS unverändert, Original-/Backup-SHA256 identisch.
- Weiter offen: Python-Laufzeittests, echter Node-RED-Import, Vue-Rendering, Socket-Clientisolation unter realem Dashboard sowie Hardwaretests. Kein Dashboard deployt, kein Dienst gestartet und keine Aktuatoren bewegt.

## 2026-10-21 – Zentraler Sprachkatalog und lokale Personenfunktionen

Vom Nutzer beauftragt: eigene Sprachvarianten ergänzen und wirklich einbinden; freiwillige Personenanmeldung mit mehreren Ansichten; tägliche Namensbegrüßung; kleine persönliche Datenbank; Tracking zum vermutlich vordersten Gesicht.

- Vor Änderungen acht betroffene Dateien unter `.tools/before_people_catalog` gesichert. Keine produktive Installation oder reale Personendaten verändert.
- `rovo/catalog.json`: **433 Formulierungen in 87 Gruppen**. `catalog.py` lädt sie als Package-Ressource; `intents.py` nutzt Synonyme, Freitextslots und sichere Negationsausnahmen. Parameterparser bleiben erhalten. Metadaten sind keine Hardwarefreigabe.
- `people.py`: lokale SQLite-Profile, Merkmale und optionale Bild-BLOBs; Ziel-/Sitzungsbindung, separate Einwilligung, fünf geführte Posen, Qualitäts-/Diversitätsfilter, Duplikatcheck und atomarer Commit. Standard 200 Ansichten, konfigurierbar 25–500.
- `face_backend.py`: optionaler OpenCV-YuNet/SFace-Adapter mit lokalem Modellhash. Keine automatischen Downloads. Bei fehlenden Modellen fällt die Kamera auf Basisdetektion zurück.
- `vision.py`: Identifikation im selben Kamera-Worker, konservative Track-Zuordnung, keine Anmeldeaufnahmen bei mehreren Personen. Zielwahl jetzt größte plausible Gesichtsbox; kein Unknown-Bonus vor dem größeren Gesicht.
- `core.py`: Namens-/Einwilligungsdialog, neue API-Aktionen und lokale Profilfakten. Registrierung pausiert Tracking. Stopp/Privatsphäre/Kamerastopp verwerfen temporäre Anmeldung. Während des Anmeldedialogs kein Textmodell-Fallback.
- Einmal tägliche Namensbegrüßung wird in SQLite pro Person und lokalem Kalendertag gespeichert. Zusätzliche freiwillige Themen können nach separater Freigabe höchstens wöchentlich bei Begrüßungen aufgegriffen werden. Keine automatische Ableitung sensibler Eigenschaften.
- `nodered/people_panel.vue`, `v5.py`, Flowgenerator und generierter V5-Flow: Einwilligung mit Token/Checkbox, Fortschritt, vorhandene Profile bearbeiten/löschen und Themen ergänzen. V5-Theme/CSS und die übrigen Seiten bleiben erhalten.
- Dokumentation: `docs/SPRACHKATALOG_UND_PERSONEN.md`; Konfiguration in `config/default.json`; Katalog als Setuptools-Package-Daten registriert.
- Tests ergänzt/angepasst: insgesamt **50 Python-Testmethoden**, mit allen Katalogbeispielen als Unterfällen. Weiterhin **nicht ausgeführt**, da kein nutzbarer Python-Interpreter verfügbar ist.
- Tatsächlich ausgeführt: **721 statische Katalog-/Personenprüfungen**, **194 Strukturprüfungen**, **120 JavaScript-Vertragsprüfungen in V8**, Syntaxprüfung der drei Bridge- und neun Vue-Skripte. Diese Prüfungen ersetzen keine Python-/Modell-/Kameraabnahme.

Neue Grenzen / offene Abnahme:

- `people.enabled=false`, `recognition_verified=false`, `store_images=false` bleiben Standard. Es wurden keine Modelle installiert, keine Profile angelegt, keine Bilder aufgenommen und keine Aktuatoren bewegt.
- Wiedererkennungsschwellen, Mindestqualität und Landmark-Pose-Heuristik sind ungeprüfte Startwerte. Namen werden vor ausdrücklicher Validierung nicht automatisch ausgegeben. Keine Lebenderkennung oder Sicherheitsauthentifizierung.
- „Vorderste Person“ bedeutet größte plausible Box, nicht gemessene Tiefe. Kameraspiegelung, Mehrpersonenwechsel und Laufzeit auf dem echten Pi sind zu testen.
- Modellwechsel blockiert unkontrollierte Neuanmeldung zu inkompatiblen Altprofilen. Eine automatische Embedding-Migration ist nicht implementiert.
- Täglicher Gruß ist ein persistentes Ereignis; fehlender/defekter Lautsprecher kann die hörbare Ausgabe verhindern. SQLite-/Dateisystem-/externe Backups bleiben eine eigene Aufbewahrungsfrage.
- Wake Word, kompletter freihändiger Audiodialog, CSI-Adapter und sonstige bisher offene Funktionsbereiche bleiben offen. Die älteren Abschnitte „Personen nicht implementiert“ sind durch diesen Codeeintrag überholt, nicht durch eine Hardwareabnahme.

## 2026-10-21 – Doppelte Sprachdefinitionen zusammengeführt

- Nutzerhinweis bestätigt: Nach Einführen des Katalogs waren alte feste Satzlisten in `intents.py` verblieben. Vor Bereinigung vier Quelldateien unter `.tools/before_intent_cleanup` gesichert.
- Feste Formulierungen und Synonyme jetzt ausschließlich in `catalog.json`; Bestätigungswörter dorthin verschoben. Aktuell 436 Formulierungen in 88 Gruppen.
- `intents.py` führt einen einzigen Katalog-Lookup aus und enthält nur Ergebnisobjekt, Negations-/Mehrdeutigkeitsprüfung, variable Parametergrammatiken und kontrollierte Rückfragen/Fallbacks.
- Doppelte FAQ-Tabelle aus `core.py` entfernt. Feste Wissensantworten kommen aus dem Katalog; registrierte Aktionen und dynamische Ergebnisse bleiben im Core.
- Vier Regressionstests in `tests/test_catalog_routing.py` ergänzt: neue Formulierung allein durch Katalogdaten, ein Lookup pro Eingabe, Parameter/Dezimalkomma, Wissensantwort aus dem Katalog. Insgesamt 54 Python-Testmethoden, weiterhin mangels Interpreter nicht ausgeführt.
- Negativer Registrierungswunsch im bisherigen Test korrigiert: Der Katalog bricht die Anmeldung ausdrücklich ab (`cancel`), statt nur generisch `negated` zurückzugeben.
- Dokumentation aktualisiert. Die bisherigen ZIPs sind frühere Exportstände; die bereinigte aktuelle Fassung liegt im Projektordner.
- Tatsächlich ausgeführt: 730 statische Katalog-/Personenprüfungen und 194 Strukturprüfungen bestanden. Python-Laufzeittests bleiben offen.

## 2026-10-21 – Musik, Spracheinstellungen und begrenzte Kopfbewegungen

- Zentraler Katalog: 457 Formulierungen in 105 Gruppen. Unterstützte Formulierungen aus `unsupported_action` in echte Aktionen überführt. Keine parallelen Satzlisten eingeführt. Katalog umfasst Fragen UND Befehle; Parser und Matcher behalten ihre getrennten Aufgaben.
- Optionales `spotify.py`: offizielle Web-API, Titelsuche/erster Treffer, festes Connect-Gerät, Wiedergabe, Pause/Fortsetzen und Lautstärke. Nur nach explizitem Musikauftrag; Token aus Umgebung. Keine Installation, Anmeldung oder Netzwerk-Musikprobe durchgeführt. OAuth-Refresh, Playlistverwaltung und eigener Pi-Streamer fehlen noch.
- Audio-Manager koordiniert lokale Musik und Spotify. Sprachlautstärke über PCM-Skalierung getrennt von Musik; Piper-Tempo über `--length_scale`. Lautstärke/Tempo begrenzt und nur für die laufende Sitzung. Status enthält die neuen Werte.
- Relative Winkel an kalibrierten Endpunkten begrenzt. Richtungsbefehle ohne Winkel bewegen bis zum Endpunkt; ausdrücklich kleine Schritte bleiben drei Grad. Mehrere Winkel/Richtungen führen zur Rückfrage. Kein Fahrantrieb.
- Bei aktivem Tracking: manuelle Vorgabe pausiert Tracking, nach fünf Sekunden letzte Vorgabe Home, anschließend konservative Profilwartezeit und weiter mit frischen Kamerabildern. Ohne Tracking bleibt das Ziel bestehen. Stopp verwirft Rückkehr. Keine gemessene Home-Ankunft behauptet.
- `PROFILE` in Core/Serial/Firmware: Geschwindigkeit und Beschleunigung innerhalb kompilierter Grenzen verändern. Aktualisierte Firmware nötig; keine Firmware übertragen. Schneller kann nur zuvor reduzierte Werte bis zur Obergrenze wieder erhöhen.
- Herunterfahren/Neustart mit sitzungsgebundener Bestätigung für 20 Sekunden; Simulation führt keinen Systembefehl aus. Real zusätzlich Linux, Safe Mode aus und `--allow-power-actions`. Keine Systemaktion ausgeführt.
- Sieben neue Python-Testmethoden für Winkel/Negation, Endpunkte/Rückkehr, Stopp, Profile, Audiogrenzen, Spotify-Mocks und Systembestätigung. Insgesamt 61 Testmethoden vorhanden, weiterhin **nicht ausgeführt**: kein nutzbarer Python-Interpreter. Firmwarebuild und Geräteabnahme ebenfalls offen.
- Tatsächlich ausgeführt: **195 statische Strukturprüfungen** und **802 Katalog-/Personenprüfungen** bestanden. Keine neue JavaScript-Prüfung nötig, da Flowgenerator und Dashboard unverändert blieben. Die alten speziellen Spotify-/Einstellungsformulare bleiben gesperrt; neue Aktionen sind über Sprache, Chat und Core-API erreichbar.
- Anleitung: `docs/MUSIK_UND_STEUERUNG.md`. Aktuelle Fassung im Projektordner; ältere ZIP-Dateien und Referenzflows sind weiterhin historische Sicherungen.

## 2026-10-21 – WLAN-Einrichtungsportal vorbereitet

- Separater Linux-Wächter `rovo/network_setup.py`: nach 60 Sekunden ohne WLAN-Verbindung externes WiFi Connect starten; bekannte Verbindungen erhalten zunächst Zeit zur automatischen Verbindung. Kein Internet-Test als Hotspot-Auslöser.
- Standardmäßig `enabled=false`; ohne zusätzliches `--apply` weder Netzwerkabfrage noch Netzwerkänderung. Eigenständige Konfiguration `config/network_setup.json`, systemd-Vorlage `scripts/rovo-network.service`. Der Roboter-Core benötigt dadurch keine root-Rechte.
- Passwortgeschütztes Einrichtungsnetz `ROVO-Einrichtung`, Portal-Gateway `192.168.42.1`. Hotspot-Passwort aus separater root-Datei 0600, nicht aus JSON oder Prozessargumenten. Zugangsdaten zum Ziel-WLAN verbleiben bei WiFi Connect/NetworkManager. Kindprozess-Ausgaben werden nicht protokolliert.
- Instanzsperre, Verbindungsfrist, Inaktivitätslimit, Wiederholpause; unbekannter/fehlerhafter Zustand oder fremder aktiver AP führt nicht zur Netzwerkübernahme. Anleitung und Geräte-Abnahmefälle in `docs/WLAN_EINRICHTUNG.md`.
- WiFi Connect ist eine externe Voraussetzung und wurde nicht installiert oder gebündelt. Pi-5-/Pi-OS-Kompatibilität, Portal-Popup, DNS/DHCP, Verbindungswechsel und Aufräumen beim Dienstende sind nicht am Gerät nachgewiesen. Keine aktive Komplettfunktion auf diesem Windows-Rechner behauptet.
- Acht Python-Mocktests ergänzt; insgesamt 69 Testmethoden vorhanden, weiterhin mangels Python-Interpreter nicht ausgeführt.
- Tatsächlich ausgeführt: **26 neue statische WLAN-Vertragsprüfungen**, **196 Strukturprüfungen** und **802 Katalog-/Personenprüfungen** bestanden. Keine Netzwerkeinstellungen geändert, kein Dienst installiert und kein Hotspot gestartet.

## 2026-10-21 – Freihändiger Dialog, Persönlichkeit, Spiele und Gesten

- Bisheriger kurzer LLM-Systemprompt durch `persona_de.md` ersetzt. Rolle erklärt Aufbau, lokale Fähigkeiten, Grenzen, Einwilligung, unbekannte Messwerte und rein textliche Modellbefugnisse. Kleiner Laufzeitkontext ohne Bilder, Namen oder Gesichtsmerkmale wird ergänzt.
- Ollama-Antwortschema mit genau `reply` und einer von acht freigegebenen Emotionen. Lokale Validierung, keine Modellbefehle. `result.data.emotion` enthält die Antwortmimik. Ungültige Modellantworten werden abgewiesen. Weiterhin kein zusätzlicher Cloud-Provider und kein dauerhaftes Gesprächsgedächtnis.
- `expressions.py` regelt Displayprioritäten: Stopp/Fehler, manuelle Vorgaben, LISTENING, THINKING, Sprech-/Antwortmimik und Neutralzustand. Dashboard projiziert die zuletzt bestätigte Gesichtsvorgabe. Node-RED-Chat kann eingerichtete lokale TTS benutzen.
- Optional `voice --hands-free --wake-model ... --stt-model ...`: lokale Vosk-Anrede-Erkennung plus bestehendes Whisper-STT, keine Enter-Taste nötig, Halbduplex und begrenztes Folgefenster. Kein trainiertes Keyword-Modell, keine geprüfte Erkennungsqualität, kein Barge-in/Echocancelling. Vosk und Modelle wurden nicht installiert oder heruntergeladen.
- Lokale Aktivitäten: Zahlenraten mit Versuchsgrenze; Quiz mit fünf Fragen aus 20 Fragen und Erklärungen; sitzungsbezogene Stoppuhr mit Pause/Fortsetzung/Runden. SQLite-Wecker einmalig oder nach Wochentagen, Auflisten, nummerierte Änderung/Löschung, Schlummern. DST-Doppelminute pro Tag geschützt; kein Nachholen verpasster Wecker und kein Aufwecken eines ausgeschalteten Pi.
- Kopfgesten Nicken, Schütteln, Umschauen als begrenzte Sequenzen im bestehenden Motion Manager. Manuelle Bewegung und Stopp brechen ab, Tracking pausiert. Serial-Thread-Operationen bleiben auch beim Taskabbruch bis zum Abschluss geschützt.
- Optionale kurze Aufmerksamkeitsblicke bei Eingaben/Sprachaufnahme trotz deaktiviertem Dauertracking; standardmäßig aus. Kamera, Home und Bewegungsfreigabe vorausgesetzt. Größte Box ist keine Sprecherlokalisierung. Stopp/Privatsphäre und manuelle Bewegungen haben Vorrang.
- `telemetry.power_status`: echter Linux-power_supply-Leseadapter mit Einheitenumrechnung und unbekannten Teilwerten. Keine automatische I²C-Erkennung und kein behaupteter Waveshare-Treiber. Konkretes UPS-Modell ist noch offen.
- Automatische mechanische Kalibrierung **nicht implementiert**: keine bestätigte Rückmeldesensorik. Neuer Kalibrierstatus und ausdrücklich gesperrter Auto-Befehl, keine blinde Anschlagfahrt. Typangaben zu UPS und Positions-/Endsensoren beim Nutzer angefragt.
- Sprachkatalog jetzt **491 Formulierungen in 124 Gruppen**. Neue Einstellungen in Default-Konfiguration; neue Persona-/Quizdateien als Paketdaten registriert. Anleitung `docs/DIALOG_VERHALTEN_UND_SPIELE.md`.
- 19 Python-Testmethoden ergänzt, insgesamt **88 vorhanden**, weiterhin **nicht ausgeführt**, da hier kein nutzbarer Python-Interpreter verfügbar ist. Firmwarebuild, Mikrofon-/Modellabnahme und Geräteprüfungen bleiben offen.
- Tatsächlich ausgeführt: **121 Dialog-/Datenprüfungen**, **198 Strukturprüfungen**, **893 Katalog-/Personenprüfungen**, **26 WLAN-Vertragsprüfungen** bestanden, zusammen 1238 statische Prüfungen. Keine reale Aufnahme, Modellanfrage, Sensorabfrage, Bewegung oder Installation ausgeführt.

## 2026-10-21 – Bestätigte UPS HAT (E), Raspberry Pi 5

- Nutzer bestätigt UPS HAT (E). Aktuelle Waveshare-MCU-Registerdokumentation geprüft: Adresse 0x2D, Kennung 0x0A, Kommunikationsstatus und direkt gemeldete Akkuwerte. Nicht mit alten INA219-Beispielen gleichgesetzt.
- `ups_hat_e.py`: reiner Leseadapter mit optionalem smbus2, Gerätekennung, Kommunikationsprüfung, signed Stromumrechnung und echtem Prozentregister. Keine Steuerregister-Schreibzugriffe und keine automatische Abschaltung.
- Core, Akkufrage und Dashboard verwenden denselben überwachten Messstand. Abfrageintervall fünf Sekunden; Fehler/veraltete Daten bleiben unbekannt. Simulation öffnet keinen I²C-Bus. Default weiterhin sysfs ohne ausgewählte Quelle; separate Beispielkonfiguration vorhanden.
- Anleitung `docs/UPS_HAT_E.md`; reale Platinen-/Treiberabnahme offen. Keine Systeminstallation und kein I²C-Zugriff ausgeführt.
- Vier Python-Mocktests ergänzt; insgesamt 92 Testmethoden vorhanden, weiterhin nicht ausgeführt. Tatsächlich bestanden: 121 Dialog-, 199 Struktur-, 893 Katalog-/Personen- und 26 WLAN-Prüfungen sowie zusätzliche statische Kontrolle der UPS-Beispielkonfiguration und des Lese-/Simulationsschutzes.

## 2026-10-21 – Erste vollständige Python-Testausführung und Fehlerkorrekturen

- Inzwischen vorhandenen Python-Interpreter über `py --version` gefunden: Python 3.15.0. Projektlokale `.venv` erstellt und das Projekt samt deklarierter Windows-Abhängigkeit tzdata installiert. Keine Audio-, Kamera-, UPS- oder Modellabhängigkeiten installiert; kein Systemdienst geändert.
- Echter Parserfehler behoben: Casefold wandelte ß im Katalog in ss um, während der Vergleich mit dem Originaltext stattfand. Einheitliche Kleinschreibung erhält jetzt ß; Namen, Fragen und Formulierungen mit ß werden korrekt erkannt.
- „Lange nicht gesehen“ wird als explizite Begrüßung vor dem allgemeinen Negationsschutz behandelt. Der Negationsschutz für Geräteaktionen bleibt bestehen.
- Falsche Testerwartung für „Fahr nach links“ korrigiert: Der bestehende Intent `stationary` erklärt den fehlenden Fahrantrieb, statt eine unnötige Rückfrage auszulösen.
- Vollständigen Testlauf tatsächlich ausgeführt: `.venv/Scripts/python.exe -m unittest discover -s tests -q` → **92 Tests bestanden**, einschließlich aller 491 Katalogformulierungen als Unterfälle, Personenabläufen, Spielen, Weckern, Bewegungs-/Abbruchlogik und UPS-Mocks.
- Zusätzlich erneut **121 Dialog-, 199 Struktur-, 893 Katalog-/Personen- und 26 WLAN-Prüfungen bestanden**. Frühere Hinweise „Python-Tests nicht ausgeführt“ sind historisch und werden durch diesen Eintrag abgelöst.
- README und Arbeitsregeln auf den nachgewiesenen Teststand aktualisiert. Firmwarebuild und echte Pi-/Audio-/Kamera-/UPS-/WLAN-Tests bleiben offen. Keine echte Hardware oder Cloud-API angesprochen.

## 2026-10-21 – Quellcode aufgeteilt und einheitlich formatiert

- `core.py` enthält Ressourcenbesitz, Gateway, Status und Hintergrundaufgaben. Aktionsausführung nach `application/actions.py`, Dialogabläufe nach `application/dialogue.py` ausgelagert. Erlaubte Gateway-Befehle/Parameter zentral in `application/contracts.py`.
- Keine zusätzlichen Ressourceninstanzen und keine konkurrierenden Programme eingeführt. `Core.execute`, `Core.action`, `Core.text`, Modulstart und Dienstpfade bleiben erreichbar. Fachmodule und Paketdaten behalten ihre bisherigen Import-/Ressourcenpfade.
- Python-Quellcode und Tests durch Ruff einheitlich formatiert; unbenutzte Imports entfernt und Imports sortiert. Ruff 0.17.1 nur in der Projektumgebung installiert, als optionale `dev`-Abhängigkeit und mit Konfiguration in pyproject.toml hinterlegt.
- Statische Prüfungen folgen den ausgelagerten Zuständigkeiten, prüfen Python-Unterordner rekursiv und tolerieren reine Formatierungsunterschiede. Einmalige Refaktorierungsskripte entfernt. Historische Referenzflows/Sicherungen bleiben zur Reproduktion erhalten.
- Neue Übersicht `docs/CODESTRUKTUR.md`, README verlinkt sie.
- Tatsächlich ausgeführt: **92 Python-Tests bestanden**, Ruff-Import-/Fehlerprüfung bestanden, Formatprüfung für **38 Python-Dateien bestanden**. Zusätzlich 121 Dialog-, 203 Struktur-, 893 Katalog-/Personen- und 26 WLAN-Prüfungen bestanden. Keine Hardware- oder Netzwerkaktion ausgeführt.

## 2026-10-21 – Node-RED-Nachrichten auf MQTT, Kamera getrennt über HTTP

- `mqtt_bridge.py` bindet den vorhandenen V5-/Core-Vertrag an einen ausdrücklich aktivierten lokalen Broker. Separate Topics für command/reply/status/availability, QoS 1, Last Will, periodischer Status und clientgebundene Antworten.
- Befehle nie retained; explizite Prüfung von ID, Sitzung, Zeit und Verbindungsgeneration. Deduplizierung vor Ausführung, neue Generation bei Reconnect/Neustart, begrenzte aktive Aufträge und reservierte Stoppplätze. Keine automatische Wiederholung nach Timeout. Kein MQTT-Not-Aus-Versprechen.
- Node-RED-Flowgenerator und erzeugter Flow verwenden MQTT-Knoten für Daten/Befehle, Serverkontext für Korrelation und Fristenkontrolle. Alter HTTP-Befehlspfad entfernt; HTTP-APIs bleiben für andere lokale Clients vorhanden. Broker nur Loopback mit Zugangsdaten; optionale Paho-Abhängigkeit und Mosquitto-/ACL-Beispiele ergänzt, kein Broker installiert/gestartet.
- Kamera separat: Node-RED-HTTP-Proxy mit serverseitigem API-Token und bereinigten Antwortheadern, Kamera-Seite mit ungefähr einer JPEG-Abfrage pro Sekunde. Core verweigert Bilder auch ausdrücklich bei Privatsphäre oder ausgeschalteter Kamera. Kein Videostream und keine MQTT-Bilddaten. Node-RED-HTTP-Endpunkt muss vor Einsatz authentifiziert werden.
- Einrichtung und Grenzen in `docs/MQTT_UND_KAMERA.md`; README, Node-RED-Anleitung, Architektur und Codeübersicht aktualisiert. Referenzflows bleiben an den existierenden Originalpfaden; die zuvor abgebrochene Archivverschiebung wurde nicht ausgeführt.
- Tatsächlich ausgeführt: **97 Python-Tests bestanden**, darunter vier MQTT-Mocktests und ein lokaler HTTP-Test mit synthetischem JPEG für Token/Privatsphäre. **24 neue MQTT-/Kameraproxy-JavaScript-Prüfungen in V8 bestanden**, Syntax aller neun Vue-Skripte geprüft. Die bisherigen HTTP-Bridge-JavaScript-Tests wurden durch passende MQTT-Vertragstests ersetzt.
- Ruff-Prüfung und Formatprüfung für **40 Python-Dateien bestanden**. Statisch: 121 Dialog-, 220 Struktur-, 893 Katalog-/Personen- und 26 WLAN-Prüfungen bestanden. Echte MQTT-Broker-/Node-RED-/Kameraabnahme auf dem Pi bleibt offen. Keine echte Kamera, Serial-Verbindung oder UPS geöffnet.

## 2026-10-21 – Leere Dashboardseiten: FlowFuse-SFC-Kompatibilität korrigiert

- Installierten FlowFuse-Parser untersucht: Vue-Komponenten werden nur erkannt, wenn das Script aus genau einem ExportDefaultDeclaration besteht. Die bisher davor erzeugte `const rovoBridge`-Deklaration führte zur falschen Behandlung als freies JavaScript. Mixins gehören außerdem nicht zu den unterstützten Optionen. Vorherige reine JavaScript-/Vue-Syntaxprüfungen konnten diesen Integrationsfehler nicht erkennen.
- Generator ergänzt um `flatten_dashboard.cjs`: gemeinsame Daten, berechnete Werte, Watcher und Lebenszyklus-Hooks in einen einzigen Export überführen. Keine Mixin-Abhängigkeit im ausgegebenen Flow. Erneutes Generieren erfolgt zunächst in einer Zwischenablage, damit Fehler den bisherigen Export nicht ersetzen.
- `rovo_neu_flows.json` neu erzeugt. Aktive Benutzerdatei unter `.node-red` nicht überschrieben oder deployt; Benutzer muss den aktualisierten Export importieren.
- Tatsächlich ausgeführt: alle **neun Seiten** mit der lokal installierten Vue-Version auf FlowFuse-kompatiblen Aufbau, mounted/unmounted-Hooks und serverseitiges Offline-Rendering geprüft. **24 MQTT-JavaScript-Prüfungen**, **220 statische Strukturprüfungen** und **893 Katalog-/Personenprüfungen** bestanden. Keine Hardware oder Kamera geöffnet. Browser-/Node-RED-Interaktion nach Neuimport noch am laufenden Dashboard bestätigen.

## 2026-10-21 – Zweite Korrektur der weiterhin leeren Seiten

- Nutzer meldet weiterhin leere Seiten; importierte Komponenten mit dem aktuellen Projektstand verglichen. Neuimport war erfolgt, kein bloß veralteter Export.
- Zweiten Fehler reproduziert: Der erste Flatten-Schritt erzeugte JSON-ähnlich quotierte Optionsnamen. Der installierte FlowFuse-Parser liest an diesen Stellen nur AST-Identifier (`key.name`), keine String-Literale (`key.value`). Dadurch wurden data/computed/methods/watch/Hooks trotz gültigem Vue nicht übernommen.
- Generator gibt Options- und Watcher-Schlüssel jetzt als geprüfte unquotierte Identifier aus.
- Rendertest verwendet jetzt zusätzlich den **tatsächlich installierten FlowFuse-SFC-Parser**, statt die Komponente nur als allgemeines JavaScript auszuwerten. Vor Korrektur scheiterten alle neun Seiten mit fehlender data-Funktion; nach Korrektur bestehen alle neun Seiten einschließlich Start-Hooks und Offline-Rendering.
- `rovo_neu_flows.json` erneut erzeugt. 24 MQTT-JavaScript-Prüfungen und 220 statische Strukturprüfungen ebenfalls bestanden. Keine laufenden Benutzerflows überschrieben oder deployt. Sichtprüfung im Browser nach erneutem Import bleibt zu bestätigen.

## 2026-10-21 – Fehlende Dashboard-Laufzeitdaten und Rückbefehle ergänzt

- Regelmäßiger MQTT-Snapshot enthält jetzt `runtime` und öffentliche `config`: Bewegungs-Sollwerte/Profile, Audio-Lautstärken/Tempo/Quelle, tatsächliche Anrede-Modus-Freigabe, Displayvorgabe, Kamerazustand/Parameter, Blickoption, LLM-Aufrufe und Akkuquelle. Keine Zugangsdaten/Dateipfade ergänzt.
- Hostname und echte RAM-Auslastung über Linux-procfs beziehungsweise Windows-Systemdaten angebunden. Physischer Mikrofon-/Lautsprecherstatus bleibt unbekannt; Konfiguration ist kein Hardwaretest. Spotify meldet konfigurierte Zugangsdaten und lokalen Playerzustand statt pauschal „nicht verfügbar“, ohne dauerhaften Kontotest zu behaupten.
- Gateway und MQTT-Allowlist für vorhandene Laufzeitaktionen erweitert. Neue begrenzte Aktionen `audio.configure`, `motion.configure`, `camera.configure`; Validierung vor Änderung und bestehende Bewegungsfreigaben bleiben erhalten. Keine freien Konfigurationsschreibzugriffe.
- Sechs Dashboardseiten bekommen einen zusätzlichen Laufzeitbereich mit eindeutig beschrifteten Profil-, Audio-, Tracking- und Musikreglern. Snapshot-Watcher aktualisiert Status und Displaymimik automatisch; nicht bestätigte Reglereingaben bleiben beim Statusupdate erhalten. Alte nicht gleichwertige Prozent-/Kalibrier-/Kontoverwaltungsregler bleiben gesperrt.
- Aktionsantworten führen `ack.action` und `ack.data` zurück; Chatantworten zusätzlich `emotion`. Wecker-/Timer-/Notizaktionen transportieren damit ihre Ergebnisse, ohne neue vollständige Verwaltungsseiten zu behaupten.
- `docs/DASHBOARD_DATEN.md` ergänzt und Flow neu erzeugt. Aktive Benutzerinstallation nicht überschrieben.
- Tatsächlich ausgeführt: **103 Python-Tests bestanden**, einschließlich sechs neuer Feld-/Validierungs-/MQTT-Rundlauftests. **25 MQTT-JavaScript-Prüfungen bestanden**, alle **neun Seiten** mit installiertem FlowFuse-Parser, Hooks und Offline-Rendering geprüft, zusätzlich neun Seiten mit einem echten Simulations-Snapshot gerendert. Ruff und Formatprüfung für **41 Python-Dateien bestanden**. Statische Prüfungen: 220 Struktur- und 893 Katalog-/Personenprüfungen bestanden. Reale Geräte-/Brokerabnahme bleibt offen.


## 2026-10-21 ? Einstellungen, Display und gef?hrte Softwaregrenzen

- Neue Settings-Verwaltung: ausgew?hlte Audio-, Tracking-, Blick-, Bewegungsprofil- und Displayvorgaben atomar speichern, vorherigen g?ltigen Stand sichern, beim Start laden und best?tigt wiederherstellen. Keine Hardwarefreigaben oder Zugangsdaten; kein automatischer Bewegungsstart. Besch?digte Dateien werden abgewiesen.
- Dashboard-Systembereich mit Speichern/Wiederherstellen; Displaybereich mit 0?100-Helligkeitsvorgabe und Automatik/manuellem Gesicht/Aus. ESP32-Firmware unterst?tzt Farbhelligkeit und Abschalten der Beleuchtung bei 0; keine kontinuierliche Backlight-PWM und kein Messwert.
- Bewegungsseite mit gef?hrten 1?-Schritten und best?tigten Softwaregrenzen innerhalb bereits gepr?fter Ausgangsgrenzen. Home/Drehrichtung bleiben unver?ndert. Separate Persistenz in safe_limits.json, Wiederanlauf nur durch bewussten Bewegungsbefehl. Automatische mechanische Anschlagsuche ohne R?ckmeldung bleibt gesperrt.
- Aktive Module/Werkzeuge neutral benannt: dashboard.py, build_dashboard.ps1, test_dashboard_bridge.mjs; Dashboardpfad /rovo. Referenzdateien und interne Node-IDs bleiben f?r reproduzierbaren Aufbau und ersetzenden Import stabil. Keine laufenden Benutzerflows ?berschrieben/deployt.
- Anleitung docs/EINSTELLUNGEN.md erg?nzt. Tats?chlich ausgef?hrt: 108 Python-Tests, 25 MQTT-JavaScript-Pr?fungen und Rendering aller neun Seiten mit installiertem FlowFuse-Parser und echtem Simulations-Snapshot bestanden. Ruff und Formatpr?fung f?r 44 Python-Dateien bestanden; 222 statische Struktur- und 121 Dialogpr?fungen bestanden. Keine Firmware kompiliert/geflasht; keine mechanische Kalibrierung oder reale Ger?te-/Brokerabnahme durchgef?hrt.


## 2026-10-21 - Lokale LLMs entfernt

- Lokalen Ollama-/LAN-Netzwerkadapter entfernt. TextLLM ist nur noch ein nicht eingerichteter Anbieter-Vertrag ohne Netzwerkcode; alte aktivierte lokale Konfiguration kann keine Anfrage ausloesen. Persona und Antwort-/Emotionsvalidierung bleiben fuer einen spaeteren Cloud-Anbieter erhalten.
- Ollama aus der Dashboard-Anbieterauswahl entfernt, voreingestellten lokalen Anbieter entfernt und Nichtverfuegbarkeit von Cloud-Fallback sichtbar erklaert. Core meldet kein Modell als eingerichtet. STT/TTS und lokale Befehle bleiben erhalten. Flow neu erzeugt, nicht deployt.
- Installationsanleitung aktualisiert und bisherige LLM-Beschreibungen als historisch markiert. Bestehender Fallback-Vertragstest nutzt einen ausdruecklichen Mockanbieter. Zusaetzlicher Regressionstest prueft abgeschaltete alte lokale Konfiguration.
- Geprueft: bestehende 108 Python-Tests und separat ein neuer Regressionstest bestanden, 25 MQTT-JavaScript-Pruefungen und alle neun Dashboardseiten mit installiertem FlowFuse-Parser gerendert. Ruff/Format fuer 45 Python-Dateien und 222 Strukturpruefungen bestanden. Keine Netzwerkverbindung zu einem Modell, keine Hardwareaenderungen.

## 2026-10-22 – Spotify und OpenAI über Node-RED einrichten

- Neue Seite `nodered/connections_panel.vue` ersetzt die gesperrte Verbindungsvorschau. OpenAI-Key/Modell und ausdrückliche Textübermittlungsfreigabe speichern, Modell testen, deaktivieren oder bestätigt entfernen. Spotify-App speichern, PKCE-Link starten, vollständige Rückleitungsadresse einfügen, Geräte laden und festes Ziel auswählen. Kein zusätzlicher Callback-Listener und kein Client-Secret nötig. Der Rückleitungs-Code wird manuell aus der Browseradresse ins Dashboard übernommen.
- `connections.py` speichert die Verbindungen atomar unter `<Datenordner>/private/connections.json`; Linux-Zielrechte 0700/0600, Prüfung beschädigter/ungeschützter Dateien, keine Secret-Rückgabe und keine Ablage in Settings/Flow-Kontext. Die private Datei ist nicht zusätzlich verschlüsselt; Windows-ACLs und Backups bleiben lokal abzusichern. `private/` ist für Git ausgeschlossen.
- OpenAI-Adapter über festen HTTPS-Responses-Endpunkt mit `store=false`, striktem Antwort-/Emotionsschema, begrenzter Antwort und ohne Modell-Tools. Kein Standardmodell vorausgewählt und kein lokales LLM reaktiviert. Freie Texte benötigen gespeicherte Einwilligung; lokale Befehle und Privatsphäre behalten Vorrang. Modelltest kann API-Kosten verursachen. Andere Cloudanbieter sind nicht implementiert.
- Spotify erneuert Access-Tokens bei Bedarf, speichert rotierte Refresh-Tokens und verlangt nach widerrufener Freigabe eine neue Anmeldung. Anmeldezustand ist sitzungsgebunden, einmalig und zehn Minuten gültig; Abbruch/Stopp/Privatsphäre verwerfen ihn. Späte Ergebnisse nach Stopp oder Zugangsänderungen werden verworfen. Nach Neustart werden Zugang und Ziel ohne Netzwerkprobe oder automatische Wiedergabe geladen. Ein vorhandener Connect-Player bleibt Voraussetzung; kein Pi-Streamer installiert.
- MQTT-Allowlist und clientgebundene `integrations`-Antworten ergänzt. Passwort-/Code-Felder werden nach dem Senden geleert, Eingaben nicht im Flow-Kontext gespeichert und ungespeicherte Formularwerte nicht von periodischen Snapshots überschrieben. Verbindungsstatus enthält letzte Prüfzeit statt dauerhafter Onlinebehauptung. Bei fehlgeschlagener Spotify-Pause bleibt der Playerstatus `ERROR`; keine erfolgreiche Unterbrechung behauptet. Ausdrückliche Pause bleibt bei Privatsphäre möglich.
- Flow reproduzierbar neu erzeugt: **48 Knoten, neun Seiten**. Laufende Benutzerinstallation nicht überschrieben oder deployt. Einrichtung, Transport-/Dateischutz, Loopback-Rückleitungsablauf und Pi-Abnahme in `docs/VERBINDUNGEN.md`; README und betroffene technische Anleitungen aktualisiert.
- Tatsächlich ausgeführt: **131 Python-Simulations-/Mocktests bestanden** (22 neue Tests für Verbindungseinrichtung, Neustart, Einwilligung/Bestätigung, Offline-/HTTP-Fehler, PKCE/Sitzung/Replay/Ablauf, Refresh/Rotation/Widerruf, Abbruch, private Projektion und Speicherfehler). **69 MQTT-JavaScript-Prüfungen**, **18 Verbindungsformular-Prüfungen** und Rendering aller **neun Seiten** mit installiertem FlowFuse-Parser bestanden. Ruff-/Formatprüfung für **48 Python-Dateien**, **224 Struktur-, 122 Dialog-, 893 Katalog-/Personen- und 26 WLAN-Prüfungen bestanden**.
- Prüfungsumgebung: vorhandene `.venv` verweist inzwischen auf einen fehlenden Interpreter. Tests stattdessen mit lokalem **Python 3.13.17** und den Projektpaketen ausgeführt; die ersten Sandboxläufe scheiterten am Aufräumen temporärer Ordner, der vollständige Lauf außerhalb der Sandbox bestand. Keine echte Anbieteranfrage, Anmeldung, Kamera-/Serial-/Bewegungsaktion oder systemweite Installation durchgeführt. Echte Pi-/Browser-/Broker-/Spotify-/OpenAI-Abnahme, Arduino-Build und Geräteabnahme bleiben offen.

## 2026-10-22 – Verbindungsseite wieder im Kartenlayout, mehrere Cloudanbieter

- Nutzer meldete die neue Verbindungsseite als unübersichtlich und wünschte ausdrücklich wieder Modell- und Anbieterauswahl. Vorhandene Layoutklassen des ursprünglichen Dashboards wiederverwendet: KI-Konfiguration und eigene Modelle nebeneinander, Spotify darunter, kompakter Rückmeldungsbereich. Einrichtungshinweise, Zugang entfernen und Musik ausprobieren sind einklappbar. Den doppelten allgemeinen Laufzeitbereich auf dieser Seite entfernt; Theme/CSS bleiben erhalten.
- Cloudauswahl: OpenAI, Anthropic/Claude, Google/Gemini, OpenRouter, Mistral und Groq. `cloud_providers.py` enthält die festen HTTPS-Endpunkte, Authentifizierung, Anfrage-/Antwortformate. Alle Antworten unterliegen derselben lokalen Antwort-/Emotionsvalidierung; keine Gerätewerkzeuge, kein automatischer Modellwechsel. OpenAI nutzt Responses, Claude Messages, Gemini GenerateContent, die übrigen Chat Completions. Mistral/Groq nutzen JSON-Modus, die anderen Schema-Ausgaben. Nicht unterstützte Modelle werden mit Fehler abgewiesen.
- Pro Anbieter getrennte Keys und eigene Modelllisten. Die bisherige einzelne OpenAI-Konfiguration bleibt lesbar und wird beim Speichern übernommen. Ein leeres Key-Feld verwendet ausschließlich den Key des gewählten Anbieters. Anbieterwechsel im Formular löscht die Eingabe und verlangt neue Übermittlungsfreigabe; erst Speichern aktiviert die Auswahl. Entfernen betrifft das aktive Anbieterprofil; andere Profile bleiben erhalten. Lokale LLMs und beliebige eigene API-Endpunkte bleiben ausgeschlossen.
- `llm.models` lädt auf ausdrücklichen Auftrag die erste Ergebnisseite des Anbieters, begrenzt auf 500 gültige Modell-IDs; Google wird auf GenerateContent gefiltert. Neu eingegebener Key wird nach erfolgreichem Listenabruf privat gespeichert, ohne Text-KI zu aktivieren. Die Liste allein ist kein erfolgreicher Modelltest. `llm.add_model`/`llm.remove_model` verwalten bis zu 50 eigene IDs je Anbieter ohne Aktivierungsänderung. Passwörter werden nach dem Senden geleert und nie als Status ausgegeben.
- MQTT-Allowlist, Modellkatalog-Antworten und Formularverhalten ergänzt. Flow neu erzeugt: **48 Knoten, neun Seiten**. README, Einrichtung und technische Hinweise aktualisiert. Keine laufende Node-RED-Installation überschrieben oder deployt.
- Tatsächlich ausgeführt: **141 Python-Simulations-/Mocktests bestanden**, darunter zehn zusätzliche Tests für getrennte Anbieterkeys, Neustart/Migration, sechs Anfrage-/Antwortverträge, Modellkataloge, Key-Einrichtung ohne Aktivierung, Speichergrenzen, Fehlantworten und Abbruch. **81 MQTT-JavaScript- und 26 Formularprüfungen bestanden**; alle **neun Seiten** mit installiertem FlowFuse-Parser und Vue serverseitig gerendert. Ruff-/Formatprüfung für **49 Python-Dateien**, **225 Struktur- und 122 Dialogprüfungen bestanden**.
- Prüfgrenzen: keine echten Anbieter, Zugangsdaten oder Geräte verwendet. Browser-Sichtprüfung des neuen Layouts nach Import sowie echte Konto-/Pi-/Brokerabnahme bleiben offen; Arduino-Build und Geräteabnahme ebenfalls. Die früheren Einträge mit ausschließlich OpenAI beschreiben den vorherigen Stand.

## 2026-10-22 – Eigene Modellverwaltung entfernt

- Auf Nutzerwunsch „Eigene Modelle“, manuelle Modell-ID, Merken-/Entfernen-Schaltflächen und eigene Modelllisten aus der Verbindungsseite entfernt. Modelle werden aus der geladenen Anbieterliste gewählt; das gespeicherte Anbietermodell bleibt auswählbar. Rechts steht nun der kompakte Status „Aktive Verbindung“.
- `llm.add_model`/`llm.remove_model` aus Backend und MQTT-Allowlist entfernt; Aufträge dafür werden abgewiesen. Beim Speichern wird keine eigene Modellhistorie mehr ergänzt, alte Listen werden nicht mehr öffentlich ausgegeben. Bestehende private Dateien bleiben lesbar; keine gespeicherten Zugangsdaten verändert. Anleitung und Flow aktualisiert, nicht deployt.
- Tatsächlich ausgeführt: **141 Python-Simulations-/Mocktests**, **73 MQTT-JavaScript- und 26 Formularprüfungen bestanden**. Alle **neun Seiten** mit installiertem FlowFuse-Parser serverseitig gerendert; **225 Strukturprüfungen** und Ruff-/Formatprüfung für **49 Python-Dateien bestanden**. Keine echten Anbieter oder Geräte angesprochen. Browser-/Pi-/Kontoabnahme, Arduino-Build und Geräteabnahme bleiben offen.

## 2026-10-22 – Spotify-Geräteauswahl vereinfacht

- Manuelle Geräte-ID-Eingabe entfernt; die ID wird ausschließlich aus der Geräteauswahl übernommen. Technischen Hinweistext zu Player, PKCE und Tokens durch verständliche Bedienhinweise ersetzt. Bestätigung zum Trennen heißt nun „Ja, Spotify-Einrichtung auf Rovo löschen“; der Text erklärt Neueinrichtung und Fortbestand von Konto/Abo. Keine gespeicherten Zugangsdaten geändert.
- Anleitung aktualisiert und Flow neu erzeugt, nicht deployt. Tatsächlich ausgeführt: **26 Formularprüfungen**, Rendering aller **neun Seiten** mit installiertem FlowFuse-Parser und **225 Strukturprüfungen bestanden**. Backend unverändert; Python-Tests nicht erneut ausgeführt, zuletzt **141 bestanden**. Echte Browser-/Pi-/Kontoabnahme, Arduino-Build und Geräteabnahme bleiben offen.
## 2026-10-22 – Erweiterungspaket begonnen: Kamera, Spotify, Erinnerung, Messverträge

- Direkter Picamera2-Quelladapter ergänzt; Auswahl bleibt standardmäßig `opencv`, keine Kamera geöffnet und kein Pi-Paket installiert.
- Spotify-Core um Ergebnislisten, URI-/Playlistwiedergabe, Warteschlange und Shuffle erweitert. Node-RED-Allowlist und erzeugter Flow aktualisiert; keine echte Spotify-Anfrage ausgeführt und kein Player installiert.
- Wiederkehrende Erinnerungen mit lokaler Zeitzone und Einmal-pro-Kalendertag-Regel sowie lokale dimensionsgeprüfte Einheitenumrechnung ergänzt. Wetteradapter verwendet bei ausdrücklicher Konfiguration ausschließlich den festen Open-Meteo-Endpunkt; keine Wetteranfrage ausgeführt.
- Optionaler lokaler openWakeWord-ONNX-Adapter ergänzt. Kein Rovo-Modell trainiert, heruntergeladen oder am Mikrofon geprüft. Halbduplex bleibt bestehen; geprüfte Echounterdrückung/Barge-in benötigt weiterhin einen realen AEC-Audioweg.
- Serial-Fähigkeitsabfrage, Kalibrierungs-ID-Abgleich und optionaler echter Analog-Positionsvertrag ergänzt. Firmware meldet nur bei ausdrücklich aktivierter Sensorik Messwerte; ohne Sensor bleibt die Position unbekannt. Display-Backlight nutzt einen separaten PWM-Kanal. Firmware wurde nicht kompiliert oder geflasht.
- Optionale aktive Kopfbewegungs-Challenge für Lebendprüfung ergänzt. Sie ist keine zertifizierte Anti-Spoofing- oder Zugangskontrolle und wurde nicht mit echten Bildern geprüft.
- Noch offen: Smart-Home-Zentrale, lokales Objektmodell, motorischer Raumscan, Spotify-Playerinstallation, echtes Wake-Word-Training, AEC/Barge-in sowie sämtliche Pi-/Sensor-/Firmwareabnahmen.
- Tatsächlich ausgeführt: **145 Python-Simulations-/Mocktests**, **73 MQTT-JavaScript-Prüfungen**, **26 Verbindungsformular-Prüfungen**, Rendering aller **neun Seiten**, Ruff-/Formatprüfung für **53 Python-Dateien** und **227 statische Strukturprüfungen bestanden**. Dashboard neu erzeugt (**48 Knoten, neun Seiten**). Der erste Sandboxlauf scheiterte ausschließlich an Windows-Rechten für temporäre Testordner; der vollständige Lauf außerhalb der Dateisandbox bestand.

