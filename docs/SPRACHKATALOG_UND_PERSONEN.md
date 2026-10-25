# Sprachkatalog, Personenidentifikation und geführte Anmeldung

## Implementierung und tatsächlicher Prüfstand

Der vorherige Stand hatte nur Face Detection und Tracking. Neu sind ein zentraler Sprachkatalog, ein optionaler YuNet/SFace-Adapter, lokale Personenprofile, geführte Anmeldung, tägliche Begrüßung und ausdrücklich gespeicherte Gesprächsthemen. Es wurde keine echte Person aufgenommen und keine Kamera eingeschaltet.

Python-Laufzeit- und Modelltests sind auf diesem Rechner weiterhin nicht möglich: Es fehlt ein nutzbarer Python-Interpreter. Der vorhandene Python-Testsatz ist deshalb eine auszuführende Abnahme, kein Beleg bereits gemessener Erkennungsqualität. Kamera, Optik, Licht, Pose-Heuristik und Schwellen müssen am echten Pi geprüft werden.

## 1. Sprachkatalog bearbeiten

Datei: `rovo/catalog.json`. Der Katalog enthält **436 Formulierungen in 88 Gruppen** einschließlich Bestätigungsformulierungen. Mehrere Gruppen können denselben Intent mit anderen Argumenten verwenden, zum Beispiel verschiedene Gesichtsausdrücke oder FAQ-Antworten. Die Gruppenzahl bedeutet daher nicht ebenso viele unterschiedliche Hardwarefunktionen.

Jede Gruppe enthält:

```json
{
  "intent": "tracking.enable",
  "phrases": ["schau mich an", "sieh zu mir", "guck mal zu mir"],
  "args": {},
  "risk": "medium",
  "negation_safe": false,
  "requires": ["camera", "motion.calibrated"],
  "negative_examples": ["nicht schau mich an"]
}
```

Der Katalog wird beim Routing tatsächlich geladen; er ist keine lose Beispielsammlung. `catalog.py` normalisiert Groß-/Kleinschreibung, Satzzeichen und äußeres „Bitte“/„Rovo“. Namen und Freitextslots behalten nach Möglichkeit ihre ursprüngliche Schreibweise. Änderungen werden nach Neustart des Core wirksam.

`intents.py` enthält keine zweite Liste fester Sätze mehr: Es sucht einmal im Katalog, prüft Negation/Mehrdeutigkeit und ergänzt nur die Parametergrammatiken für Winkel, Timer, Notizen und Rechenausdrücke. Auch die frühere kleine FAQ-Tabelle aus `core.py` ist entfernt. Neue feste Sätze oder Wissensantworten werden ausschließlich in `catalog.json` gepflegt. Ein neuer Aktionstyp braucht weiterhin einen geprüften Handler in `core.py`.

Beispiel: „Schau nach links“ wird vollständig im Katalog zugeordnet. Bei „Schau fünf Grad nach links“ extrahiert der Parser die variable Gradzahl. `core.py` führt die registrierte Absicht aus. Die `requires`-Liste dokumentiert Voraussetzungen; deren verbindliche Prüfung erfolgt im Handler/Motion Manager. Metadaten allein erteilen keine Freigabe.

Beispiele für dieselbe Trackingaktion: „Schau mich an“, „Sieh zu mir“, „Guck mal zu mir“, „Folge mir“ und „Verfolge mein Gesicht“. „Verfolge mich nicht mehr“ deaktiviert Tracking; „Schau nicht nach links“ führt keine Bewegung aus.

Es gibt kein freies Fuzzy-Ausführen ähnlich klingender Hardwarebefehle. Ein Hörfehler löst nicht allein wegen Textähnlichkeit eine Bewegung aus. „Ganz nach links“ ist auch weiterhin keine ungeprüfte Fahrt an einen historischen Winkel. Nicht implementierte Funktionen werden als nicht eingerichtet beantwortet.

## 2. Wo Personen gespeichert werden

Standardmäßig in **`data/rovo.sqlite3`**. `--data PFAD` ändert den Speicherort. Die Daten bleiben lokal und sind nicht verschlüsselt; Verzeichnis und Backups entsprechend auf das eigene Benutzerkonto beschränken.

| Tabelle | Inhalt |
| --- | --- |
| `persons` | ID, Anzeigename, bewusst eingetragene Informationen/Notizen, Modellkennung, Einwilligungszeit, Bildspeicherwahl |
| `face_samples` | Zugeordnete Pose, Merkmalsvektor und optional JPEG-Gesichtsausschnitt als SQLite-BLOB |
| `person_facts` | Freiwillig mitgeteilte Themen/Fakten und Freigabe für gelegentliche Begrüßungsfragen |
| `greetings` | Person und lokales Kalenderdatum zur Vermeidung wiederholter Begrüßung |

Es gibt keine unkontrollierten Bildordner mit Namen im Dateipfad. Gespeicherte Bilder liegen innerhalb der Datenbank. Standardmäßig werden **keine** Trainingsbilder dauerhaft aufbewahrt. Bei ausdrücklicher Bildfreigabe werden nur die ausgewählten ausgerichteten Gesichtsausschnitte gespeichert, keine komplette Videoaufnahme.

Temporäre Bilder und Merkmale liegen vor Abschluss im Arbeitsspeicher. Vor Einwilligung werden keine Samples oder Namen als Personenprofil in die Datenbank geschrieben. Abbruch verwirft die temporäre Anmeldung. Aktive Live-Detektion/Identifikation benötigt kurzlebige Merkmale im RAM.

## 3. Modelle bewusst einrichten

Die optionalen OpenCV-Abhängigkeiten bleiben unter `.[vision]`. Zusätzlich werden lokal vorhandene ONNX-Modelle für **YuNet** und **SFace** benötigt. Die Programme laden keine Modelle ungefragt herunter.

Modellquellen und API-Vertrag: [OpenCV-Tutorial](https://docs.opencv.org/4.10.0/d0/dd4/tutorial_dnn_face.html), [YuNet im OpenCV Zoo](https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet), [SFace im OpenCV Zoo](https://github.com/opencv/opencv_zoo/tree/main/models/face_recognition_sface). Modelllizenzen und passende Versionen vor dem manuellen Bezug prüfen.

Beispiel für `config/local.json`:

```json
{
  "people": {
    "enabled": true,
    "detector_model": "/ABSOLUTER/PFAD/face_detection_yunet.onnx",
    "recognizer_model": "/ABSOLUTER/PFAD/face_recognition_sface.onnx",
    "recognition_verified": false,
    "known_threshold": 0.55,
    "unknown_threshold": 0.30,
    "match_margin": 0.08,
    "samples_per_pose": 40,
    "store_images": false,
    "offer_enrollment": true,
    "greet_daily": true
  }
}
```

Die angegebenen Schwellen sind konservative, **noch nicht an deinem Aufbau validierte Startwerte**. Sie sind keine garantierte Fehlerquote. Ein Modell mit beispielsweise ähnlicher Person, Foto, wechselnder Beleuchtung oder starker Pose kann sich irren. Es gibt keine Lebenderkennung; die Funktion ist keine Zugangskontrolle.

`recognition_verified=false` verhindert Namensausgabe und Namensbegrüßung. Erst nach eigenen Positiv-/Negativtests und bewusster Anpassung der Schwellen auf `true` setzen. Enrollment kann zuvor bereits ein freiwilliges Profil erfassen. Ein schreibgeschützter Status ist kein Modell-Verbindungstest.

Die Modellkennung enthält den SHA256 der SFace-Datei. Profile anderer Modellversionen werden nicht stillschweigend verglichen oder erneut automatisch angelegt; bei Modellwechsel muss die Migration bewusst geplant werden.

Wenn Modelle fehlen, kann die Basisdetektion weiterlaufen. Die Identifikation meldet dann nicht verfügbar. CSI-/Picamera2-Unterstützung bleibt weiterhin ein gesonderter Adapter; diese Erweiterung verwendet denselben vorhandenen OpenCV-Kameradienst.

## 4. Anmeldeablauf

1. Kamera bewusst starten. Für Enrollment muss das lokale Identifikationsbackend geladen sein.
2. Ein stabil unbekanntes, hochwertiges Gesicht kann nach einigen Sekunden eine **Anfrage** auslösen: „Wie heißt du? … mit deiner Erlaubnis …“. Unsichere Treffer bekommen kein neues Profil.
3. Name per Text/STT, zum Beispiel „Ich heiße Max“, oder im Personenbereich eingeben. Ein kurzer alleinstehender Name wird nur während der konkreten Namensrückfrage angenommen.
4. Rovo stellt eine eigene Einwilligungsfrage. Sie nennt, ob auch Gesichtsbilder gespeichert werden. Bestätigung gehört zur konkreten Sitzung und Zielperson; im Dashboard zusätzlich zu einem frischen Token. Gültigkeit 60 Sekunden.
5. Erst nach Zustimmung beginnt die Aufnahme. Tracking pausiert; Rovo fährt keine Trainingsposen selbst an. **Die Person dreht ihren Kopf.**
6. Geführte Ansichten: vorne, links, rechts, oben, unten. Standard: je 40 akzeptierte Samples, insgesamt 200; konfigurierbar je 5–100, also 25–500 insgesamt.
7. Qualität: ausreichende Größe, Licht, Schärfe, passende Landmark-Pose, Mindestabstand zwischen Samples und veränderte Bildstruktur. Zweihundert identische Frames zählen nicht als gute Anmeldung.
8. Mehrere Personen oder Zielverlust pausieren die Erfassung. Eine unsichere Merkmalszuordnung bricht ab. Die Kamera tauscht das Anmeldeziel nicht stillschweigend aus.
9. Vor Commit erfolgt ein lokaler Duplikatvergleich. Erst danach werden Profil und Samples gemeinsam transaktional gespeichert.

Die Posenprüfung verwendet Landmark-Verhältnisse, keine vermessenen 3D-Kopfwinkel. Spiegelung, Kameraausrichtung und Schwellen sind am realen Bild zu prüfen. Die Registrierung läuft spätestens nach fünf Minuten ab, anstatt unvollständige Profile als Erfolg zu speichern.

„Nein“, „Abbrechen“, „Stopp“, Privatsphäre und Kamerastopp beenden die temporäre Anmeldung. Nach Abbruch gibt es eine Ansprechpause, damit Rovo nicht sofort erneut nach einer Registrierung fragt.

## 5. Wiedererkennung und Begrüßung

Identitätszustände: `KNOWN`, `UNKNOWN`, `UNCERTAIN`. Name erst nach mehreren stabilen Beobachtungen über mindestens eine Sekunde und validierter Konfiguration. Niedrige Bildqualität, enge Konkurrenz zwischen zwei Profilen oder fehlende Modellvalidierung bleiben unsicher.

Für einen sicheren Treffer wird in `greetings` das lokale Datum der konfigurierten Zeitzone gespeichert, standardmäßig Europe/Berlin. So entsteht die Namensbegrüßung nur einmal pro Person und Tag, auch nach einem Core-Neustart. Der Datenbankeintrag bestätigt das erzeugte Begrüßungsereignis, nicht, dass ein Lautsprecher tatsächlich hörbar war.

## 6. Kleine persönliche Wissensbasis

Es werden keine privaten Eigenschaften automatisch aus Bildern oder Gesprächen abgeleitet. Zusätzliche Fakten entstehen bewusst:

- Im Personenbereich ein vorhandenes Profil auswählen und Informationen/Notizen bearbeiten.
- Ein Thema wie „Modellbau“ und den ausdrücklich mitgeteilten Text erfassen.
- Optional erlauben, dieses Thema bei Begrüßungen aufzugreifen. Rovo fragt dann höchstens einmal pro Woche zu einem freigegebenen Thema nach.
- Per Sprache: „Merk dir über mich, dass ich Modellautos baue.“ Das verlangt genau eine aktuell sicher erkannte Person und aktiviert keine automatische Begrüßungsfrage.
- „Was weißt du über mich?“ oder „Was weißt du über mein Thema Modellbau?“ liest die lokalen Fakten der eindeutig erkannten Person.

Profile, Bilder, Embeddings und Profilfakten werden nicht an den Textmodell-Fallback angehängt. Es gibt keine versteckte Chatverlaufsanalyse und kein unkontrolliertes Profilwachstum aus jeder Unterhaltung.

## 7. Tracking bei mehreren Gesichtern

Der Zielwähler bevorzugt die **größte plausible Gesichtsbox**. Eine deutlich größere neue Box verdrängt ein bisheriges Ziel sofort; bei nahezu gleicher Größe verhindert etwas Hysterese ständiges Wechseln. Unbekannte Personen bekommen keinen Sondervorrang vor einem größeren Gesicht.

Das ist eine Heuristik für „vermutlich vorderste Person“, keine gemessene Entfernung. Unterschiedliche Kopfgröße, Objektiv und Neigung beeinflussen die Box. Tracking funktioniert grundsätzlich unabhängig von einer Personenidentifikation; eine unbekannte Person kann verfolgt werden, ohne ein Profil anzulegen.

## 8. Neue API-Aktionen

Alle über das bestehende authentifizierte Core-Gateway:

| Aktion | Argumente |
| --- | --- |
| `people.list`, `people.status`, `people.enroll.cancel` | `{}` |
| `people.enroll.request` | `name`, `store_images` als bool |
| `people.enroll.confirm` | `token`, `consent` als bool, gleiche Sitzung |
| `people.update` | `id`, `name`, `info`, `notes` |
| `people.delete` | `id`, `confirm: true` |
| `people.fact.add` | `id`, `topic`, `text`, `greeting` als bool |
| `people.facts` | `id` |

V5 `people.save` übersetzt auf `people.update`; ein leeres neues Profil wird darüber nicht angelegt. Neue Personen entstehen nur durch Enrollment. Die V5-Personenseite enthält die Einwilligungsstufe und Fortschrittsanzeige, Profilbearbeitung, Themen und bestätigtes Löschen.

Löschen entfernt aktive Profilzeilen einschließlich Samples, Fakten und Begrüßungsdaten. SQLite-WAL, freigegebene Seiten, Dateisystem-Snapshots und externe Backups sind keine garantierte forensische Löschung; deren Aufbewahrung muss separat geregelt werden.

## 9. Abnahme

```text
python -m unittest discover -s tests -v
python -m compileall -q rovo tests
node scripts/test_dashboard_bridge.mjs
```

Unter Windows außerdem `scripts/check_static.ps1` und `scripts/check_people_catalog.ps1`. Die Python-Tests enthalten alle 436 Katalogbeispiele sowie synthetische Einwilligungs-, Qualitäts-, Duplikat-, Lösch-, Tagesbegrüßungs- und Mehrpersonentests. `test_catalog_routing.py` prüft zusätzlich, dass neue feste Formulierungen allein durch Katalogdaten ergänzt werden können und keine alte Satzliste im Parser einspringt. Kamerabilder, reale Namen, ONNX-Modelle und echte Hardware werden dafür nicht benötigt.
