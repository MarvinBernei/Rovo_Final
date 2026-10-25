# Musik und Einstellungen per Sprache

`catalog.json` ist der zentrale deutsche Intent-Katalog für Befehle UND Fragen.
`catalog.py` liest und vergleicht seine Daten. `intents.py` ergänzt variable Zahlen,
Negationsschutz und Rückfragen. Das sind drei Aufgaben, keine drei konkurrierenden
Programme. Neue feste Synonyme nur im JSON eintragen. Eine unscharfe Klangähnlichkeit
löst weiterhin keine Geräteaktion aus.

## Beispiele

- `Spiele ein Lied von ABBA`, `Spiele das Lied Dancing Queen von ABBA`: erster Spotify-Suchtreffer.
- `Spiele auf Spotify ...`: ausdrücklich Spotify. Freie Liedwünsche nutzen ebenfalls Spotify.
- `Musik lauter`, `Musik leiser`: Schritte von zehn Prozentpunkten.
- `Lautstärke auf 40 Prozent`: absolute Musiklautstärke 0–100.
- `Sprich lauter`, `sprich leiser`: separate Sprachlautstärke, zehn Prozentpunkte.
- `Sprich langsamer`, `sprich schneller`: Piper-Sprechtempo, begrenzt auf Faktor 0,5–1,5.
- `Bewege dich langsamer`, `bewege dich schneller`: begrenzte Zielgeschwindigkeit.
- `Bewege dich sanfter`, `bewege dich direkter`: begrenzte Beschleunigung.
- `10 Grad nach links`, `20 Grad nach rechts`, `3 Grad nach oben`, `40 Grad nach unten`.
- `Fahr herunter`, `starte dich neu`: Rückfrage, dann frische Bestätigung innerhalb von 20 Sekunden.

Einstellungen gelten für die laufende Sitzung. Musik- und Sprachlautstärke sind
getrennt; die Hardware-Mixerlautstärke wird nicht verändert. Sprache wird durch
Skalieren der lokalen 16-Bit-WAV-Datei leiser gestellt. Tempo nutzt Pipers
`--length_scale`; die installierte Piper-Version muss diesen Parameter unterstützen.

## Spotify einrichten

Die Implementierung nutzt die offizielle HTTPS-Web-API mit Python-Standardbibliothek.
Eine mögliche umfangreichere OAuth-Bibliothek ist Spotipy; sie ist hier nicht notwendig
und nicht installiert. Einrichtung über [Dashboard-Verbindungen](VERBINDUNGEN.md).

1. Client-ID und passende Redirect-URI im Dashboard speichern.
2. PKCE-Anmeldung starten, Freigabe erteilen, vollständige Rückleitungsadresse einfügen
   und Anmeldung abschließen. Scopes: `user-modify-playback-state` und `user-read-playback-state`.
3. Geräte laden und ein laufendes Spotify-Connect-Gerät ausdrücklich als Ziel speichern.
   Kein automatischer Wechsel zu einem anderen Gerät. Spotify-Konto-/Premium- und
   Development-Mode-Berechtigungen bleiben Voraussetzungen.

Tokens werden privat auf dem Core gespeichert und vor weiteren Anfragen automatisch
erneuert. Bei widerrufener/abgelaufener Freigabe erneut anmelden. Der ältere Weg über
`ROVO_SPOTIFY_ACCESS_TOKEN`/`ROVO_SPOTIFY_DEVICE_ID` bleibt ohne Dashboard-Einrichtung
als kurzlebige Alternative möglich; er hat keinen Refresh. Nach bewusstem Entfernen
im Dashboard wird dieser Umgebungsweg nicht automatisch reaktiviert.
Keine Tokens in Katalog, Konfiguration, Screenshots oder Logs schreiben.

Die API steuert einen existierenden Player. Sie erzeugt auf dem Pi keinen
Spotify-Audioplayer. Das Web Playback SDK erzeugt einen Player im Browser;
eine separate Connect-Lösung auf dem Pi muss bei Bedarf eingerichtet werden.
Nicht jedes Gerät erlaubt Lautstärkesteuerung. Fehler bleiben Fehler, kein
automatisches Ausweichen auf fremde Geräte. `Musik stoppen` pausiert Spotify;
Spotify hat hier keinen eigenen Stop-Endpunkt.

Titelsuche wählt ausdrücklich den ersten Suchtreffer und liefert dessen Titel
und Interpreten im API-Ergebnis. Rückfragen bei mehreren Treffern, Playlists,
Warteschlange und Shuffle sind noch nicht implementiert. Für einen Kontowechsel die
Verbindung bestätigt entfernen und neu anmelden.

Offizielle Grundlagen:
- https://developer.spotify.com/documentation/web-api/reference/start-a-users-playback
- https://developer.spotify.com/documentation/web-api/reference/set-volume-for-users-playback
- https://developer.spotify.com/documentation/web-api/concepts/quota-modes
- https://developer.spotify.com/documentation/web-playback-sdk
- https://github.com/OHF-Voice/piper1-gpl

## Kopfbewegung und Systemaktionen

ROVO hat keinen Fahrantrieb. Relative Winkel werden an den kalibrierten Endpunkten
begrenzt. Absolute Winkel außerhalb der Grenzen werden weiterhin zurückgewiesen.
`Schau nach links/rechts/oben/unten` führt bis zum jeweiligen Endpunkt.
`Ein Stück` und `etwas höher/tiefer` bleiben kleine Schritte von drei Grad.
Vor relativen Bewegungen muss eine Sollposition durch Home bekannt sein.

War Tracking aktiv, pausiert es während manueller Vorgaben. Fünf Sekunden nach
der letzten manuellen Vorgabe wird Home angefordert. Danach folgt eine konservative
Wartezeit für das Bewegungsprofil, bevor frische Kamerabilder wieder steuern.
Ohne Tracking bleibt die Sollposition bestehen. Stopp verwirft die Rückkehr.
Home ist kein gemessener Positionsnachweis; echte Ankunftssensoren fehlen.

`PROFILE` erweitert das Serial-Protokoll. Dafür ist die aktualisierte Firmware
erforderlich; alte Firmware weist den Befehl ab. Laufzeitwerte überschreiten nie
die kompilierten Maximalwerte. Der Core begrenzt zusätzlich auf 20 Grad/s und
40 Grad/s². Schneller ist erst nach vorheriger Reduktion möglich. Es wurde keine
Firmware übertragen und keine Mechanik bewegt.

Herunterfahren/Neustarten wird in Simulation nur gemeldet. Real braucht es Linux,
`safe_mode=false`, Startoption `--allow-power-actions`, frische Sprachbestätigung
und passende lokale systemd-Rechte. Kein beliebiger Shellbefehl. Andere Eingaben
verwerfen die Bestätigung. Kein System wurde während der Entwicklung heruntergefahren.
