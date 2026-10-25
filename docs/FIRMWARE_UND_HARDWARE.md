# Nano-ESP32-Firmware und Hardwarefreigabe

## 1. Lieferzustand

`esp32/rovo_esp32/rovo_esp32.ino` ist ein neuer Arduino-Sketch. `calibration.h` schaltet Servos und Kalibrierung standardmäßig aus. Booten initialisiert nur Serial und Display. Kein HOME-Befehl, kein PWM-Attach und kein automatischer Motorlauf.

Der Sketch wurde hier nicht kompiliert: Arduino-CLI/Boardpaket und Bibliotheken wurden nicht vorgefunden. Es wurde kein Nano angeschlossen oder geflasht. Vor Verwendung erst mit dem tatsächlich installierten Nano-ESP32-Boardpaket kompilieren.

## 2. Board und Bibliotheken

In Arduino IDE das Board **Arduino Nano ESP32** wählen. Benötigt werden Adafruit GFX und Adafruit ST7735 and ST7789 Library samt deren Abhängigkeiten. Keine ESP32Servo-Bibliothek nötig: die Servo-PWM verwendet den ESP-IDF-LEDC-Treiber direkt und damit explizite GPIO-Nummern.

Die tatsächlich verwendeten Board-/Bibliotheksversionen nach erfolgreichem Build festhalten. Eine angeblich getestete Versionskombination wurde hier nicht erfunden.

Bei vorhandener Arduino CLI zunächst die richtige FQBN aus `arduino-cli board listall` ermitteln. Danach ausschließlich kompilieren:

```text
arduino-cli compile --fqbn TATSAECHLICHE_NANO_ESP32_FQBN esp32/rovo_esp32
```

Dies ist ein Muster mit Platzhalter, kein direkt ausführbarer Uploadbefehl. Flashen erst nach ausdrücklicher Freigabe und Sicherung des bisherigen Sketches.

## 3. Pins

| Signal | Nano-Anschluss |
| --- | --- |
| Pan-Signal | echter GPIO18, entspricht Nano D9 |
| Tilt-Signal | echter GPIO17, entspricht Nano D8 |
| TFT CS | D10 |
| TFT DC | D6 |
| TFT RST | D5 |
| TFT BL | D4 |
| TFT SCK | D13 |
| TFT MOSI | D11 |
| TFT MISO | unbenutzt |

Arduino unterscheidet bei diesem Board Arduino- und GPIO-Nummerierung. Die Labels `D10` usw. funktionieren laut [offizieller Arduino-Pintabelle](https://support.arduino.cc/hc/en-us/articles/10483225565980-Select-pin-numbering-for-Nano-ESP32-in-Arduino-IDE) in beiden Modi. Die Servo-Pins werden hier direkt als ESP-IDF-GPIO konfiguriert. **GPIO18 ist nicht Arduino-Pinnummer 18.**

Display: ST7789, Initialisierung `170 × 320`, Rotation 1 für Landscape. Das entspricht dem Initialisierungsmuster der [Adafruit-Bibliothek](https://github.com/adafruit/Adafruit-ST7735-Library/blob/master/examples/graphicstest_st7789/graphicstest_st7789.ino). Sichtbare Offsets und konkrete Displayvariante am Gerät prüfen. Backlight wird im Entwurf binär eingeschaltet; dimmbares Backlight-PWM ist nicht implementiert.

## 4. Was der Sketch macht

- Begrenzter serieller Zeilenparser, finite Zahlen und exakte Argumentzahl.
- Versionierter Handshake, Auftrags-IDs, ACK/ERR/DONE.
- Zweite Grenzprüfung im Mikrocontroller.
- Nicht blockierende Schleife mit begrenztem Serial-Budget.
- Servo-Takt etwa 20 ms, Geschwindigkeits- und Beschleunigungsbegrenzung.
- Watchdog ohne automatische Home-Fahrt.
- Augenanimation mit einem partiellen 260×100-Pixel-Canvas im 320×170-Display.
- 16 registrierte Gesichtsausdrücke, zeitweiliges Zurücksetzen nach acht Sekunden.

Die Ausdrucksanimationen sind eine erste grafische Umsetzung. Es gibt keine gemessene Bildrate, kein phonemgenaues Mundbild und keine TFT-Live-Telemetrie. Eine absichtliche BLINK-/WINK-Auswahl bleibt im aktuellen Entwurf bis zum Ausdruckstimeout aktiv. Das lässt sich später in ein einmaliges Animationsevent aufteilen.

## 5. Kalibrierung nicht überspringen

Vor realer Bewegung müssen tatsächliche Servo-Typen, Spannungsversorgung, mechanische Grenzen, Kabelschlaufen, Achsrichtungen, Home-Winkel und erlaubte Pulsweiten bekannt sein. Historische MG996R-/MG90S-Werte und UI-Presets sind keine Messung.

In `calibration.h` sind alle Werte bewusst ungültig bzw. deaktiviert. Der Compile-Schalter `ROVO_ENABLE_SERVOS=1` lässt sich nur mit `ROVO_CALIBRATED=1` und plausiblen, individuell eingetragenen Werten bauen. Die statischen Assertions prüfen Zahlenbereiche, nicht reale Mechanik oder Versorgung.

Die erste Bewegung nach dem Start muss genau der konfigurierten Home-Anforderung entsprechen. Beim erstmaligen PWM-Aktivieren ist die physische Position unbekannt; ein Positionsservo kann dabei zum Home-Sollwert fahren. Software kann diesen ersten Stellimpuls ohne Positionssensor nicht als sicher langsamen Übergang garantieren. Deshalb den ersten Test ausdrücklich freigeben, Mechanik entlasten und einen geeigneten physischen Abschaltweg bereithalten.

Es gibt keine behauptete Not-Aus-Hardware. Der Software-STOP hält nur die interne Interpolation an. Ob der Servo seine Position hält, sich wegen Last bewegt oder bei Spannungsverlust absinkt, hängt von der echten Anlage ab.

## 6. Pi-Seite freigeben

Die spätere lokale Konfiguration muss `simulation=false`, `safe_mode=false`, einen stabilen USB-Gerätepfad und exakt passende bestätigte Pan-/Tilt-Grenzen enthalten. Richtungen jeweils `1` oder `-1`. Die Winkel und Pulsweiten werden nicht aus dem Dashboard übernommen.

Nur nach persönlicher Hardwarefreigabe starten:

```bash
.venv/bin/python -m rovo cli --config config/local.json --connect-serial --allow-motion
```

Das Öffnen des Ports kann den Nano zurücksetzen. Der Start selbst sendet keinen HOME-Auftrag. Erst ein bewusstes `Home` fordert die Home-Zielposition an. Wenn die Firmware noch im gelieferten gesperrten Zustand ist, antwortet sie `UNCALIBRATED`.

Die Kalibrierung ist auf Pi und Nano getrennt hinterlegt; die Gleichheit muss vor Freigabe geprüft werden. Ein automatischer Kalibrierungs-Hashvergleich ist noch nicht vorhanden. Unterschiedliche Grenzen können zu abgewiesenen Befehlen führen und dürfen nicht durch großzügigere Defaultwerte umgangen werden.

## 7. Prüfablauf

1. Python-Mocktests und Firmware-Build erfolgreich durchführen.
2. Firmware mit Servoausgängen aus auf Display/Parser prüfen, nach Uploadfreigabe.
3. Verdrahtung, Strombudget, gemeinsame Signalmasse und mechanische Freigängigkeit prüfen.
4. Individuelle Limits und Pulsweiten dokumentieren; Pi und Firmware abgleichen.
5. Erst nach ausdrücklicher Bewegungsfreigabe kleinste Schritte testen.
6. STOP, USB-Abziehen, Watchdog, Grenzverletzung und Neustart prüfen.
7. Kamera-/Audio-/Trackinglast gemeinsam messen.

In diesem Paket wurde keiner dieser Hardwaretests als bestanden markiert.
