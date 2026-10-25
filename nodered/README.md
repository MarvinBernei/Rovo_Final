# ROVO Control Center V5 am neuen Python-Core

`rovo_neu_flows.json` verwendet jetzt die vom Nutzer bereitgestellte **ROVO_V5_NodeRED.json** als Oberfläche. Alle neun Seiten, Theme, CSS, Kopf-/Augenvorschauen und Seitenpfade bleiben erhalten. Die Basis-URL ist **`/rovo`**.

Der aktuelle Dashboard-Befehlspfad verwendet MQTT; Status und Antworten kommen ebenfalls über MQTT zurück. Kamerabilder laufen getrennt über HTTP. Einrichtung und Zugriffsschutz stehen in [MQTT und Kamera](../docs/MQTT_UND_KAMERA.md). Ältere HTTP-Installationshinweise weiter unten gelten für die weiterhin vorhandene Diagnose-API.

## Dateien

Bei sichtbaren, aber leeren Seiten: den aktuellen Projektflow erneut importieren.
Der Generator erzeugt nun für FlowFuse genau einen `export default` je Komponente,
ohne vorgelagerte Mixin-Deklaration. Anschließend deployen und den Browser mit
Strg+F5 neu laden. Die bestehende Node-RED-Installation wird vom Generator nicht überschrieben.
Die Optionsnamen (`data`, `computed`, `methods`, `watch`) bleiben dabei unquotiert:
Die installierte FlowFuse-Version erkennt dort keine JSON-Stringschlüssel.

Für erneutes Generieren muss Node.js verfügbar sein (`ROVO_NODE_EXE` kann einen
absoluten Pfad vorgeben). `flatten_dashboard.cjs` verwendet Acorn/ESCodeGen aus der
Node-RED-Installation; bei anderem Benutzerverzeichnis `ROVO_NODE_RED_DIR` setzen.
`node scripts/test_dashboard_render.cjs` prüft die neun Komponenten mit der lokal
installierten Vue-Version auf FlowFuse-Struktur, Start-Hooks und Offline-Rendering.

| Datei | Zweck |
| --- | --- |
| `rovo_neu_flows.json` | Angepasster Gesamtflow zum Importieren |
| `ROVO_V5_original.json` | Unveränderte, bytegleiche Sicherung der Nutzerdatei |
| `rovo_basis_vor_v5.json` | Sicherung des vorherigen vereinfachten Dashboards |
| `../scripts/build_dashboard.ps1` | Reproduzierbarer Generator aus dem Original |
| `../scripts/test_dashboard_bridge.mjs` | JavaScript-Vertragstests |

Sicherungsflows **nicht zusätzlich importieren**: Sie enthalten überlappende IDs bzw. UI-Pfade.

## Einrichtung

1. Tatsächlich laufende Node-RED-Flows exportieren und sichern. Die lokale Originaldatei ersetzt kein Backup der laufenden Instanz.
2. Benötigt wird **@flowfuse/node-red-dashboard** (Dashboard 2.0).
3. Python-Core und Node-RED-Prozess benötigen dasselbe `ROVO_API_TOKEN` mit mindestens 32 Zeichen, ausschließlich als serverseitige Umgebungsvariable.
4. Aktualisierten Core zunächst in Simulation starten: `python -m rovo serve --config config/default.json`.
5. Alte ROVO-Test-/Telemetrie-/Integrationsflows nach Backup deaktivieren oder entfernen. Der bisherige separate Dienst auf Port 1891 darf nicht gleichzeitig mit dem neuen Core denselben Port belegen.
6. **Nur `rovo_neu_flows.json` importieren.** Es enthält die V5-Oberfläche und den neuen Tab „ROVO · V5 an Python-Core“. UI-IDs werden wiederverwendet: Im Importdialog keine zweite Kopie mit neuen IDs neben dem alten Dashboard anlegen. Für einen sauberen Import nach Backup die alten ROVO-Tabs einschließlich unbenutzter Konfigurationsknoten entfernen und diesen Gesamtflow importieren.
7. Genau eine aktive UI-Base `/rovo` prüfen. „Include Client Data“ und „Accept Client Data“ für `ui-template` sind im Export gesetzt.
8. Nach Kontrolle deployen und `http://NODE_RED_HOST:1880/rovo/overview` öffnen, wenn 1880 der tatsächliche Node-RED-Port ist.

Core und Node-RED laufen für diese Konfiguration auf demselben Rechner. `127.0.0.1:1891` bezeichnet den Node-RED-Host. Dashboard und Editor separat authentifizieren; für LAN-Zugriff TLS vorsehen.

Grundlage für die clientgebundene Ausgabe ist die offizielle [FlowFuse-Implementierung](https://github.com/FlowFuse/node-red-dashboard/blob/main/nodes/config/ui_base.js): `includeClientData` und `acceptsClientConfig` steuern die Weitergabe bzw. Auswertung von `_client`.

## Verbundene Funktionen

| V5-Funktion | Neuer Weg |
| --- | --- |
| Chat | Lokaler Core-Router, optional im Dashboard eingerichtetes Cloud-Textmodell |
| Verbindungen | Anbieter-Key und Modellauswahl, Spotify-PKCE-Anmeldung, Geräteauswahl, Tests und private Speicherung auf dem Core |
| Status | Core-Abfrage alle zwei Sekunden, unbekannte Werte bleiben leer |
| Home / Position / Stopp | Motion Manager mit Kalibrierungs- und Freigabesperren |
| Kamera-Schalter | Sofortige Core-Anfrage für Start/Stopp |
| Tracking-Schalter | Zentraler Trackingpfad; benötigt Kamera und bekannte Sollposition |
| Gesichtsausdruck | V5-Emotionsname auf Firmwaremodus abgebildet |
| Audio stoppen | Zentraler Audio-Manager |
| Sprachtest | Lokale Piper-TTS; bei fehlender Einrichtung ausdrücklicher Fehler |
| Einstellungen lesen | Tatsächliche Core-Konfiguration ohne Geheimnisse |

Der Sprachtest ersetzt den bisherigen Testton durch einen kurzen festen Satz. Der V5-Chat liefert Text; automatisches Vorlesen ist noch nicht über die V5-Einstellungen konfigurierbar.

## Noch schreibgeschützt

Die historischen Prozentregler für Speed/Smoothing und ungeprüfte Grenzerweiterungen bleiben gesperrt. Für unterstützte Audio-, Display-, Tracking- und Bewegungswerte gibt es zusätzliche Laufzeitregler und eine Settings-Verwaltung. Die Seite **Verbindungen** ist jetzt vollständig an die begrenzten Cloud-/Spotify-Verwaltungsaktionen angebunden; [Einrichtung](../docs/VERBINDUNGEN.md).

**Erweiterung Personen:** Die Personenseite enthält inzwischen eine geführte Anmeldung mit Name, optionaler Bildspeicherung, frischer Einwilligungsabfrage und Pose-Fortschritt. Vorhandene Profile können bearbeitet, um freiwillige Themen ergänzt oder bestätigt gelöscht werden. Dafür sind lokale Modelle und die Einrichtung aus [SPRACHKATALOG_UND_PERSONEN.md](../docs/SPRACHKATALOG_UND_PERSONEN.md) erforderlich. Die ursprüngliche einfache Personen-Vorschau wurde im bestehenden Seitenlayout durch `people_panel.vue` ersetzt; Theme, CSS und die übrigen V5-Seiten bleiben erhalten.

Alte V5-Winkel und UI-Bestätigungen werden nicht als Hardwarekalibrierung übernommen. Positionsanfragen senden nur Pan/Tilt; das Firmware-Bewegungsprofil bleibt maßgeblich. Kamera-HTTP-Proxy und OpenAI-Anbindung sind implementiert; echte Pi-/Anbieterabnahme bleibt offen. Enrollment ist noch nicht an echten Kamerabildern abgenommen.

`connections_panel.vue` ersetzt die bisher gesperrte Verbindungsvorschau. Eingaben werden einmalig an den Core gesendet und sofort aus Passwortfeldern gelöscht. Keine Speicherung im Flow-Kontext, kein lokaler Browser-Speicher und keine Wiederholung beim Refresh. Credentials des alten Dienstes werden weder gelesen, migriert noch gelöscht.

## Status und Sicherheit

Jede Seite zeigt eine Core-Verbindungsanzeige. Nach acht Sekunden ohne frischen Status erscheint offline/veraltet. Simulation ist ausdrücklich markiert; FakeESP32 zählt nicht als angeschlossener Nano. Vorschauen bleiben als Darstellung erkennbar.

Befehlsantworten gehen über `_client` an den auslösenden Browser. Periodischer Gerätestatus wird geteilt. Token und HTTP-Header gelangen nicht in die UI. Keine Debug-Nodes mit vollständigen Requests ergänzen.

UI-Templates haben `passthru=false`, `storeOutMessages=false` und `resendOnRefresh=false`: keine Befehlsrückkopplung und keine Wiederholung beim Seitenaufbau. Ein persistenter Idempotenzspeicher fehlt weiterhin.

## Prüfstand

Der aktuelle ausgeführte Prüfstand steht in [ROVO_PROGRESS.md](../ROVO_PROGRESS.md). `test_dashboard_bridge.mjs` prüft MQTT-Routing und clientgebundene Verwaltungsantworten; `test_connections_panel.cjs` prüft das generierte Verbindungsformular einschließlich geleerter Key-/Code-Felder und erhaltener ungespeicherter Eingaben.

Python-Simulations-/Mocktests sowie Rendering aller neun Seiten mit dem installierten FlowFuse-Parser werden lokal ausgeführt. Echter Pi-Import, Browser-/Socket-Verhalten, Kontozugriff und Hardware bleiben zusätzlich abzunehmen.
