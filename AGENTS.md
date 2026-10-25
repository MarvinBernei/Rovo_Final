# Arbeitsregeln für diesen neuen Entwicklungsstand

Der Nutzer hat ausdrücklich einen Neuaufbau der ROVO-Programme beauftragt. Dieses Paket liegt getrennt von der ursprünglichen Wissensbasis. Vor späteren Änderungen README, ROVO_PROGRESS und die einschlägige technische Anleitung lesen.

- Deutsch für Bedienung und Dokumentation.
- Simulation und Safe Mode bleiben Standard; keine historischen Winkel zur realen Kalibrierung erklären.
- Keine realen Bewegungen, Serial-Portöffnungen, Firmwareuploads oder systemweiten Änderungen ohne Freigabe.
- Pro Core nur ein Besitzer für Kamera, Serial, Bewegung und Audio.
- Keine Secrets, Rohaufnahmen oder biometrischen Daten in Git, Antworten oder Logs.
- Fehlende Sensorwerte bleiben unbekannt; ACK/DONE nicht als gemessene Position ausgeben.
- Negationen, Abbruch, Grenzwerte, Offline-Betrieb und Bestätigungsablauf testen.
- Fortschrittsdokument nur mit tatsächlich ausgeführten Prüfungen ergänzen.
- Prüfstand anhand der jüngsten Einträge in ROVO_PROGRESS.md berichten. Lokale Python-Simulations-/Mocktests sind inzwischen ausgeführt; Arduino-Build und Geräteabnahme bleiben offen. Nur tatsächlich ausgeführte Prüfungen als bestanden melden.
