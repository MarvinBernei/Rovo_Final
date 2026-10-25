> Aktueller Stand: Optionales Cloud-Textmodell über [Dashboard-Verbindungen](VERBINDUNGEN.md). Keine lokalen LLMs; STT/TTS bleiben lokal. Echte Anbieter-/Pi-Abnahme bleibt offen.

# Freihändiger Dialog, Mimik und lokale Aktivitäten

## Lokale Anrede und Dialog

Optionaler Start mit vorhandenen lokalen Modellen:

```bash
python -m rovo voice --hands-free --wake-model /pfad/zum/deutschen-vosk-modell --stt-model /pfad/zum/faster-whisper-modell --config config/local.json
```

Die Python-Zusätze `voice` und `wake` müssen in der vorhandenen virtuellen Umgebung
installiert sein, etwa über `pip install -e '.[voice,wake]'`. Hier wurde nichts installiert.
Die Modelle müssen separat lokal vorhanden sein. Es erfolgt kein automatischer Download.
Vosk übernimmt kontinuierliche lokale Anrede-Erkennung; faster-whisper die anschließende
freie Sprache. Das ist ein sprachbasierter Wake-Detektor, kein eigens trainiertes
Keyword-Modell. Quelle: [Vosk API](https://github.com/alphacep/vosk-api).

Ablauf: **„Hey Rovo“ sagen, kurz warten → ROVO sagt „Ja?“ → Frage sprechen → Antwort**.
Auch „Hallo Rovo“ und die Erkennungsvarianten „Robo/Rowo/Ro wo“ sind hinterlegt.
Vosk muss diese Anrede mit dem konkreten deutschen Modell tatsächlich transkribieren
können; ein unbekanntes Wort lässt sich nicht allein durch Python-Code zuverlässig machen.
Aufnahmen für die freie Sprache werden bei Stille beendet und sind auf zehn Sekunden begrenzt.
Für Folgefragen gibt es ein Fenster von maximal 15 Sekunden, das bei Stille wieder endet.
Quizantworten, Name und Einwilligung verwenden denselben Dialogkanal.

Wake-Erkennung und freie Aufnahme besitzen das Mikrofon nacheinander. Während der
normalen Antwort wird keine weitere Frage aufgenommen; Hintergrund-Sprachausgabe
verwirft Wake-Ergebnisse beziehungsweise bricht eine laufende Aufnahme ab. Es gibt
**keine Echoauslöschung und kein sprachliches Unterbrechen einer laufenden Antwort**.
Musik, Raumhall, Lautsprecherposition und Vosk-Aussprache sind am Gerät zu prüfen.
Es wird kein Erfolgsversprechen für „Hey Rovo“ abgegeben.

Privatsphäre sperrt weitere Mikrofonaufnahmen. Das Aufheben muss außerhalb dieses
gesperrten Sprachkanals erfolgen; der freihändige Modus startet aktuell keinen
zusätzlichen API-Server. Push-to-talk bleibt über den bisherigen Voice-Modus verfügbar.

## Mimik und LLM-Rolle

Die vollständige Rolle steht in `rovo/persona_de.md`: Bedeutung und Aufbau von ROVO,
stationäre Mechanik, tatsächliche lokale Funktionen, Umgang mit unbekannten Messwerten,
Einwilligung, Grenzen der Personenerkennung und ehrliche Aussagen über Aktionen.
Zusätzlich erhält das Modell einen kleinen aktuellen Kontext aus Fähigkeiten,
Simulation/Safe Mode, Kamera-/Trackingzustand und verfügbaren Akkuwerten.
Keine Gesichtsmerkmale, Bilder, Namen oder Profilinhalte werden dafür übermittelt.

Der OpenAI-Adapter fordert ein JSON-Schema an und prüft die Antwort lokal:

```json
{"reply":"Das ist eine spannende Frage. Was möchtest du darüber wissen?","emotion":"CURIOUS"}
```

Nur `reply` wird gesprochen. `emotion` erscheint in `result.data.emotion` und steuert
die Displaymimik. Unbekannte Emotionen, zusätzliche Aktionsfelder oder ungültiges
JSON werden abgewiesen. Quelle: [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses).
Ein älteres Modell/Backend ohne passende Schema-Ausgabe benötigt Anpassung; es wird
kein ungeprüfter Text als Hardwareauftrag interpretiert. Cloudzugriff benötigt eine
ausdrückliche Freigabe im Dashboard. Kein dauerhaftes Gesprächsgedächtnis.

| Auslöser | Display |
|---|---|
| Sprachaufnahme | LISTENING |
| Warten auf das Textmodell | THINKING |
| Sachliche Antwort wird gesprochen | TALKING |
| Begrüßung, Dank | HAPPY |
| Lokale Rückfrage | CURIOUS |
| Witz | LAUGHING |
| Fehler | Kurz ERROR, Antwortdaten CONFUSED |
| LLM-Antwort | NEUTRAL, HAPPY, CURIOUS, SAD, SURPRISED, CONFUSED, LAUGHING oder LOVE |
| Stopp / Privatsphäre | NEUTRAL mit kurzer Vorrangzeit |
| Manuelle Gesichtswahl | Acht Sekunden Vorrang vor normalen Dialogzuständen |

Fehler und Stopp haben Vorrang vor manueller Mimik, diese vor Zuhören, Nachdenken
und Antwortmimik. Zustände laufen zeitlich aus. Ein Hintergrundtick sendet das
gewählte Gesicht an denselben Serial-Besitzer. Das Dashboard zeigt die zuletzt
bestätigte Gesichtsvorgabe; es misst das physische Display nicht zurück.
Node-RED-Chatantworten können nun ebenfalls die eingerichtete lokale TTS benutzen.

## Aufmerksamkeitsblicke ohne Dauertracking

`Aufmerksamkeitsblicke an` oder `Schau mich beim Reden gelegentlich an` schaltet die
Funktion für die Sitzung ein. `Aufmerksamkeitsblicke aus` schaltet sie ab. Alternativ:

```json
{"behavior":{"social_gaze":true,"gaze_seconds":1.5,"gaze_interval_seconds":8}}
```

Bei einer Eingabe beziehungsweise dem Beginn einer Sprachaufnahme darf ROVO für
1,5 Sekunden auf die größte erkannte Gesichtsbox reagieren, frühestens alle acht
Sekunden. Das identifiziert nicht zuverlässig die tatsächlich sprechende Person.
Es ist keine Erkennung von Gefühlen oder Blickkontakt im menschlichen Sinn.

Voraussetzungen: bereits eingeschaltete Kamera, bestätigte Bewegungsfreigabe,
Kalibrierung, bekannte Sollposition durch Home und keine aktive Gesichtsanmeldung.
Kamera und Mechanik werden durch diese Option nicht ungefragt eingeschaltet.
Manuelle Vorgaben und Bewegungssequenzen haben Vorrang. Stopp und Privatsphäre
sperren weitere Blickbewegungen; zum Wiederaufnehmen ist eine bewusste Bewegung nötig.
Wird Dauertracking bei eingeschalteter Blickoption deaktiviert, wird Home angefordert;
danach sind kurze Blicke möglich. Ohne Blickoption bleibt der bisherige Tracking-Stopp.

## Kopfgesten

`Nicke`, `Schüttel den Kopf`, `Schau dich um` starten kleine vordefinierte Folgen
um die aktuelle Sollposition. Alle Zwischenziele werden an den kalibrierten Grenzen
begrenzt. Abschließend wird die Ausgangs-Sollposition angefordert.
Keine eigene Servo-Verbindung, keine parallelen Trackingbewegungen, keine automatische
Erweiterung des Bewegungsradius. Direkte manuelle Vorgaben und Stopp brechen die Folge ab.
Wartezeiten beruhen auf dem Profil; es gibt keinen gemessenen Ankunftsnachweis.

## Spiele und Stoppuhr

- `Starte ein Wissensquiz`: fünf zufällige Fragen aus derzeit 20 lokalen Fragen,
  jeweils drei Antworten, Auswertung und Erklärung, abschließend Punktestand.
  Antworten als Zahl, „Antwort zwei“ oder vollständige Antwortoption.
- `Spielen wir Zahlenraten`: Zahl zwischen 1 und 100, Hinweise größer/kleiner,
  maximal 15 Versuche. „Ich tippe auf zweiundvierzig“ ist ebenfalls möglich.
- `Spiel beenden` beendet die eigene Runde. Spiele sind je Dialogsitzung getrennt
  und enden nach zehn Minuten. Bekannte Gerätebefehle bleiben währenddessen erreichbar.
- `Starte eine Stoppuhr`, `Pausiere die Stoppuhr`, `Stoppuhr fortsetzen`,
  `Stoppuhr Runde`, `Wie lange läuft die Stoppuhr`, `Stoppuhr zurücksetzen`.
  Stoppuhren nutzen eine monotone Uhr und bleiben pro Sitzung bis zum Prozessende.

Noch keine Quizkategorien, Schwierigkeitsstufen, Multiplayer oder unbegrenzte KI-Fragen.

## Wecker

- `Stelle einen Wecker auf sieben Uhr dreißig` – einmal beim nächsten Auftreten
  dieser Uhrzeit während des Betriebs.
- `Stelle einen Wecker auf 7 Uhr 30 werktags`, alternativ `täglich` oder `am Wochenende`.
- `Welche Wecker sind eingestellt` – listet Uhrzeiten mit Nummern auf.
- `Deaktiviere Wecker zwei`, `Aktiviere Wecker zwei`, `Lösche Wecker zwei`.
  Die Nummer bezieht sich auf die aktuelle Liste; eine alleinige ID ist über die API möglich.
- `Schlummere fünf Minuten` verschiebt einen in den letzten zehn Minuten ausgelösten
  Wecker um 1–60 Minuten; ein weiterer Schlummer-Timer entsteht erst nach erneutem Klingeln.

Wecker liegen in SQLite. Zeitzone ist die konfigurierte Zone, standardmäßig Europe/Berlin.
Wiederholte Minuten beim Wechsel zur Winterzeit lösen pro lokalem Tag höchstens einmal
aus. Eine beim Wechsel zur Sommerzeit übersprungene Uhrzeit wird nicht nachgeholt.
Verpasste Wecker bei ausgeschaltetem Prozess werden nicht nachträglich abgespielt.
Ein ausgeschalteter Pi wird nicht aufgeweckt. Es gibt derzeit eine Sprachmeldung,
keinen endlos wiederholten Klingelton. TTS und laufender Core sind dafür erforderlich.

## Akku und automatische Kalibrierung

`power.supply` kann den **bestätigten** Linux-power_supply-Namen einer tatsächlich
unterstützten Batterie/UPS enthalten. Der Adapter liest `capacity`, `voltage_now`,
`current_now` und `status` aus `/sys/class/power_supply/<Name>`; Mikrovolt/Mikroampere
werden in Volt/Ampere umgerechnet. Fehlende Teilwerte bleiben unbekannt.
Quelle: [Linux Power Supply ABI](https://github.com/torvalds/linux/blob/master/Documentation/ABI/testing/sysfs-class-power).

Für das inzwischen vom Nutzer bestätigte Waveshare UPS HAT (E) gibt es zusätzlich
den [MCU-I²C-Adapter](UPS_HAT_E.md). Dieser liest auch den direkt gemeldeten Akkustand.
Andere HATs benötigen weiterhin eine passende Schnittstelle. Es werden keine
Prozentwerte aus einer angenommenen Akkuspannung berechnet.

`Kalibrierstatus` zeigt den bisherigen Zustand. `Kalibriere deinen Kopf` wird ohne
bestätigte Positions-/Endsensoren ausdrücklich zurückgewiesen. Standardservos liefern
dem vorhandenen Programm keine Positions- oder Anschlagrückmeldung. Eine blinde
Anschlagfahrt oder Stromschwelle ohne mechanische/elektrische Abnahme ist nicht enthalten.
**Automatische mechanische Kalibrierung ist deshalb noch nicht implementiert.**

## Prüfung

Python-Mocktests decken Spielabläufe, Wecker, Stoppuhr, strukturierte Modellantworten,
Mimikprioritäten, Bewegungsabbruch, Blicksperren und synthetische sysfs-Messdateien ab.
Sie sind in dieser Sitzung nicht ausgeführt worden. Mikrofon-/Modellqualität,
gleichzeitige Last auf dem Pi, echte Bewegungen und Sensorwerte brauchen Geräteabnahme.
