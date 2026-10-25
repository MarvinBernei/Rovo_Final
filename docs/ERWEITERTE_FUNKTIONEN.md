# Erweiterte Funktionen und sichere Inbetriebnahme

## Kamera

`camera.backend` kann `opencv` oder `picamera2` sein. Der Picamera2-Adapter besitzt
die CSI-Kamera und liefert BGR-Frames an dieselbe Erkennungs- und Trackingpipeline.
Er lädt Picamera2 nur bei ausdrücklicher Auswahl; das Raspberry-Pi-OS-Systempaket
wurde hier nicht installiert. Breite und Höhe stehen in `camera.width` und
`camera.height`.

## Trainiertes Wake Word

`voice --hands-free --wake-model /pfad/rovo.onnx` lädt ein vorhandenes lokales
openWakeWord-ONNX. Ein Verzeichnispfad verwendet weiterhin Vosk. ROVO lädt kein
Modell automatisch herunter. Das konkrete deutsche Rovo-Modell muss mit Stimmen,
Mikrofon, Raumgeräuschen und schwierigen Negativbeispielen trainiert und am Pi
validiert werden. Die optionale Abhängigkeit heißt `wake-trained`.

Das vorhandene Gespräch ist freihändig, aber weiterhin halbduplex: Während Piper
spricht, besitzt die Sprachausgabe den Audioweg und die Aufnahme wird nicht als
allgemeines Barge-in geöffnet. Sichere Echounterdrückung benötigt einen am Pi
geprüften AEC-Audiokanal. Ohne diesen würde die eigene Lautsprecherausgabe das
Wake Word oder Stopps fälschlich auslösen können.

## Positionsrückmeldung und Kalibrierungs-ID

Reale Bewegung verlangt jetzt dieselbe `motion.calibration_id` im Pi-Profil und
`ROVO_CALIBRATION_ID` in `calibration.h`. Die Firmware liefert über `INFO` ihre
Fähigkeiten. Unterschiedliche IDs sperren Bewegung.

`ROVO_ENABLE_POSITION_FEEDBACK` bleibt ab Werk `0`. Nur mit tatsächlich
angeschlossenen und getrennt kalibrierten Analog-Positionssensoren dürfen Pins und
ADC-Grenzen gesetzt und die Option aktiviert werden. Erst dann liefert `POSITION`
gemessene Pan-/Tiltwerte. Interpolierte Firmwarewerte werden nicht als Messung
ausgegeben.

## Spotify

Der Core unterstützt neben dem ersten Suchtreffer nun eine Ergebnisliste für Titel
und Playlists, die bewusste Wiedergabe einer Spotify-URI, Titelwarteschlange und
Shuffle. Die Befehle heißen `music.spotify.search`, `music.spotify.play_uri`,
`music.spotify.queue` und `music.spotify.shuffle`. Ein Connect-Player bleibt nötig.
ROVO installiert keinen Spotify-Client und enthält keine Spotify-Zugangsdaten.

## Erinnerungen, Einheiten und Wetter

Wiederkehrende Erinnerungen werden wie Wecker in lokaler Wandzeit gespeichert und
pro lokalem Kalendertag höchstens einmal ausgelöst. Beispiel:
`Erinnere mich täglich um 20 Uhr an mein Medikament`. Dadurch wird auch bei der
Zeitumstellung nicht zweimal am selben lokalen Tag ausgelöst. Nicht vorhandene
lokale Uhrzeiten beim Sprung auf Sommerzeit werden nicht nachträglich erfunden.

Die Einheitenumrechnung arbeitet lokal und dimensionsgeprüft, unter anderem für
Länge, Masse, Volumen, Zeit, Geschwindigkeit, Druck, Energie, Leistung, Datenmenge
und Temperatur. Beispiel: `Wie viel sind 32 Fahrenheit in Celsius?`

Wetter ist standardmäßig aus. Nach bewusster Konfiguration von Breiten-/Längengrad
fragt `Wie ist das Wetter?` ausschließlich den festen Open-Meteo-Endpunkt ab. Der
konfigurierte Standort wird dabei an diesen Dienst übertragen.

## Lebendprüfung

Eine optionale aktive Kopfbewegungs-Challenge fordert eine zufällige Reihenfolge aus
links, rechts und geradeaus. Mit `people.liveness_required=true` bleibt eine sonst
bekannte Identität bis zur frischen Challenge unsicher. Das erschwert ein einzelnes
Foto, ist aber keine zertifizierte Anti-Spoofing- oder Zugangskontrolle; Video-Replay,
Masken und reale Schwellen müssen gesondert geprüft werden.

## Noch nicht abgeschlossen

Smart-Home-Steuerung, allgemeine Objekterkennung und ein motorischer Raumscan sind
noch nicht angebunden. Dafür fehlen die konkrete Smart-Home-Zentrale, ein freigegebenes
lokales Objektmodell und eine am Gerät bestätigte Scanbewegung. Ebenso fehlen ein
installierter Spotify-Connect-Player sowie ein trainiertes Rovo-Modell und ein
geprüfter AEC-Audioweg. Diese Punkte werden nicht durch Platzhalter als verfügbar
gemeldet.
