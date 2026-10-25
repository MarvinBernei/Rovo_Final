# Einstellungen, Display und Bewegungsgrenzen

Im Dashboard unter `http://localhost:1880/rovo/overview` stehen auf der Systemseite
„Einstellungen speichern“ und eine bestätigungspflichtige Wiederherstellung bereit.
Gespeichert werden Sprach-/Musiklautstärke, Sprechtempo, Tracking-Totzone und Verstärkung,
gelegentlicher Blickkontakt, Bewegungsprofil und Displayvorgaben.

Im konfigurierten Datenordner liegen `settings.json` und der vorherige gültige Stand
`settings.previous.json`. Beim Start wird der gespeicherte Stand automatisch geladen;
ungültige Dateien werden abgewiesen und im Status gemeldet. Ohne Datenordner ist kein
dauerhaftes Speichern möglich. Die Wiederherstellung wählt gespeicherten Stand,
vorherigen Stand oder Startvorgaben. Vorher Musik stoppen; Bewegungen werden angehalten.
Anschließend bei Bedarf speichern. Eine Wiederherstellung löst keine Bewegung aus.
Zugangsdaten, Hardwarefreigaben und Kalibrierbestätigung gehören nicht in diese Dateien.

Auf der Displayseite gibt es Helligkeit 0–100 und drei Modi: automatische Mimik,
manuell ausgewähltes Gesicht und ausgeschaltet. Sicherheitsausdrücke haben Vorrang
vor einer manuellen Mimik. Die aktualisierte ESP32-Firmware unterstützt `BRIGHTNESS`:
Farben werden abgedunkelt, bei 0 wird die Hintergrundbeleuchtung abgeschaltet.
Dies ist keine kontinuierliche PWM-Regelung der Hintergrundbeleuchtung und kein
gemessener Helligkeitswert. Die Firmware wurde hier weder kompiliert noch geflasht.

Auf der Bewegungsseite gibt es geführte 1°-Schritte, Home und bestätigungspflichtige
Softwaregrenzen für Pan/Tilt. Reale Bewegung benötigt weiterhin separat freigegebene
Hardware, passende Firmware und bestätigte Ausgangskalibrierung. Neue Grenzen müssen
innerhalb der geprüften Ausgangsgrenzen liegen und Home enthalten. Home und Drehrichtung
können hier nicht geändert werden. Die Firmware besitzt zusätzlich eigene Grenzen.
Die Softwaregrenzen werden separat in `safe_limits.json` gespeichert und beim Start
erneut geprüft; die allgemeine Einstellungswiederherstellung verändert sie nicht.

Ohne Istwinkel-, Strom- oder Endschaltersensorik ist keine sichere automatische
Anschlagsuche möglich. Ein ACK bestätigt nur einen angenommenen Befehl. Nach Änderung
der Grenzen bleibt Bewegung gestoppt, bis bewusst ein neuer Bewegungsbefehl erfolgt.

Aktive Module und Werkzeuge heißen jetzt `rovo/dashboard.py`,
`scripts/build_dashboard.ps1` und `scripts/test_dashboard_bridge.mjs`.
Die ursprünglichen Referenzdateien und internen Node-IDs behalten ihre Namen, damit
Sicherungen vergleichbar bleiben und ein Import vorhandene Knoten ersetzen kann.
Den neuen Flow importieren, vorhandene Knoten ersetzen und deployen; Core neu starten.
