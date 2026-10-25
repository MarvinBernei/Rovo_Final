# Node-RED über MQTT, Kameravorschau über HTTP

Der aktuelle Flow `nodered/rovo_neu_flows.json` benutzt MQTT für V5-Befehle,
korrelierte Antworten und regelmäßige Statusmeldungen. Nur das Kamerabild verwendet
einen HTTP-Proxy. Die bisherigen lokalen HTTP-APIs bleiben für Diagnose/andere Clients
vorhanden; der Dashboard-Befehlspfad verwendet sie nicht parallel als Fallback.

| Topic | Richtung | Inhalt | Retained |
|---|---|---|---|
| `rovo/v1/command` | Node-RED → Core | ID, Verbindungsgeneration, Sitzung, Zeit, Aktion, Daten | Nein |
| `rovo/v1/reply` | Core → Node-RED | ID, Generation und V5-Antwort | Nein |
| `rovo/v1/status` | Core → Node-RED | Dashboard-Snapshot alle zwei Sekunden | Nein |
| `rovo/v1/availability` | Core → Node-RED | Onlinezustand, Generation; Last Will bei Abbruch | Ja |

QoS 1 kann Duplikate liefern; der Core sperrt schon gesehene Auftrags-IDs vor der
Ausführung. Deduplizierung ist begrenzt und nicht persistent. Retained-Befehle,
falsche Generationen und mehr als 30 Sekunden alte Aufträge werden verworfen.
Jeder Core-Neustart und Broker-Reconnect erzeugt eine neue Generation. Alte
Bewegungsaufträge werden dadurch nicht nach einer Wiederverbindung nachgeholt.
Während fehlender Statusmeldungen blockiert das Dashboard neue Aufträge nach
6,5 Sekunden. Antwortfristen laufen nach 30 Sekunden ab, ohne automatische Wiederholung.
Ein Timeout beweist nicht, dass die Aktion nicht ausgeführt wurde: Zustand prüfen.
Antworten werden nur an den ursprünglich anfragenden Dashboard-Client zurückgeführt.

Die MQTT-Bridge verwendet den vorhandenen Core und seine Befehlsprüfung. Sie öffnet
keine eigene Kamera, Audio- oder Serial-Verbindung. Maximal 16 aktive Aufträge;
vier Plätze sind für Stopp reserviert. MQTT ist kein Not-Aus und kein Echtzeitbus.
Der Firmware-Watchdog bleibt erforderlich.

## Vorbereitung auf dem Pi

1. Einen lokalen MQTT-Broker, beispielsweise Mosquitto, bewusst installieren und
   einrichten. Die Vorlage `config/mosquitto-rovo.example.conf` bindet ausschließlich
   Loopback und verlangt Anmeldung. Die ACL-Vorlage trennt Core und Node-RED.
   Bestehende Listener vorher prüfen; keine zweite konkurrierende Konfiguration starten.
2. Zwei eigene Zugangsdaten mit dem Broker-Verwaltungswerkzeug anlegen. Passwörter
   nicht in den Flowexport oder Git schreiben. Beispiele enthalten keine Passwörter.
3. In der Projektumgebung `pip install -e '.[mqtt]'` ausführen und die Einstellungen
   aus `config/mqtt.example.json` in die lokale Core-Konfiguration übernehmen.
4. Im Core-Prozess `ROVO_MQTT_USER=rovo-core` und `ROVO_MQTT_PASSWORD` lokal setzen.
   Für den Kamera-HTTP-Pfad weiterhin einen mindestens 32 Zeichen langen
   `ROVO_API_TOKEN` im Core- und Node-RED-Prozess setzen.
5. Den Core einmal mit `python -m rovo serve --config config/local.json` starten.
   Keine zusätzliche Instanz desselben Roboters für MQTT starten. Die Bridge wird
   bei aktivierter Konfiguration zusammen mit dem Core gestartet und beendet.
6. Den erzeugten Flow nach Sicherung des bisherigen Dashboards importieren.
   Im Broker-Konfigurationsknoten Zugangsdaten für `rovo-nodered` hinterlegen.
   Brokeradresse im aktuellen Paket: `127.0.0.1:1883`. Erst nach Kontrolle deployen.

Core und Node-RED müssen hierfür auf demselben Pi laufen. Der Python-Adapter lehnt
externe Broker ab. Für einen späteren separaten Broker sind TLS, ACLs und eine
bewusst erweiterte Konfiguration nötig. Es wird kein öffentlicher Testbroker verwendet.
Der Transport basiert auf [Eclipse Paho MQTT 2.x](https://eclipse.dev/paho/clients/python/docs/).

## Kamera

Die Kamera-Seite zeigt bei laufender Kamera und frischem Core-Status ungefähr ein
JPEG pro Sekunde. Browser → `/rovo/camera.jpg` auf Node-RED → geschütztes
`/api/v1/camera.jpg` auf dem Core. Der API-Token bleibt serverseitig und wird aus
Antwortheadern entfernt. Kein Base64-Bild auf MQTT, kein Videoarchiv und kein
zusätzlicher Kamerabesitzer. Veraltete, ausgeschaltete oder private Bilder werden
vom Core zurückgewiesen. Die Vorschau ist kein flüssiger MJPEG-/WebRTC-Stream.

**Den Node-RED-HTTP-Endpunkt mit `httpNodeAuth` oder einem authentifizierenden
Reverse Proxy schützen.** Editor-Login allein schützt `/rovo/camera.jpg` nicht.
Die Vorlage richtet keine Konten automatisch ein. Der Pfad erwartet standardmäßige
Node-RED-HTTP-Wurzeln; bei eigenem URL-Präfix anpassen. Bei HTTP-Fehlern wird kein
altes Bild als aktueller Messwert ausgegeben.

Status und Antworten können Texte, Ereignisse und Personenverwaltungsdaten enthalten.
Der Broker ist deshalb ausschließlich lokal mit den vorgesehenen ACLs zu betreiben.
Nur Erreichbarkeit wird retained veröffentlicht; keine Bilder, Profile oder Dialogtexte.
Brokerprotokollierung und externe Backups sind separat zu konfigurieren.

## Prüfstand

Mocktests prüfen Korrelation, Duplikate, retained/veraltete Befehle, Reconnect-Generationen
und die Trennung der Bilddaten. JavaScript-Vertragstests prüfen Dashboard-Rückführung,
Timeouts und den tokenbereinigten Kameraproxy. Ein echter Broker-/Node-RED-/Kamera-Test
auf dem Pi ist noch erforderlich; es wurde hier kein Broker installiert oder gestartet.
