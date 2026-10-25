# Waveshare UPS HAT (E) am Raspberry Pi 5

Das vom Nutzer genannte Modell ist im Projekt dokumentiert. Der neue Adapter
`ups_hat_e.py` verwendet die aktuelle dokumentierte MCU-Schnittstelle, prüft die
Gerätekennung und liest Akkuspannung, vorzeichenbehafteten Strom, direkt gemeldeten
Akkustand sowie Lade-/Versorgungsstatus. Er schätzt keine Prozentwerte aus Spannung.
Teildefekte Messchip-Kommunikation lässt die betreffenden Werte unbekannt.

Quelle: [Hersteller-Registerhandbuch](https://docs.waveshare.com/UPS-HAT-E-Tutorials-Register).
Adresse standardmäßig `0x2D` (dezimal 45), Bus 1. Die tatsächlich vorhandene
Platinenversion muss diese Schnittstelle bereitstellen; ältere INA219-Beispiele
werden nicht automatisch als kompatibel behandelt.

Auf dem Pi I²C und Benutzerrechte prüfen und `smbus2` in der vorhandenen Umgebung
bereitstellen (`pip install -e '.[ups]'`). Die Werte aus
`config/ups_hat_e.example.json` in die eigene Konfiguration übernehmen.
Standard und Simulation bleiben unverändert. Erst bei `simulation=false` mit
ausdrücklich gewähltem UPS-Treiber wird alle fünf Sekunden gelesen.
Der bestehende Startablauf verlangt für den realen Roboter weiterhin `--connect-serial`.

Status, Dashboard und die Frage „Wie viel Akku hast du?“ verwenden dieselben Werte.
Fehler oder länger als zehn Sekunden alte Daten liefern unbekannte Werte.
Der Zeitstempel ist die lokale Lesezeit, kein unabhängiger Messzeitstempel des HAT.

Keine Schreibzugriffe auf Steuerregister, keine Abschaltfunktion und kein Ändern
von Ladeparametern, Watchdog oder Boot-Konfiguration. Es wurden keine I²C-Abfragen
auf diesem Rechner ausgeführt. Python-Mocktests und echte Geräteabnahme stehen aus.
