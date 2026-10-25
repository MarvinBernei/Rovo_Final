# Spotify und Text-KI im Dashboard einrichten

Die Seite **Verbindungen** richtet den laufenden Python-Core ein. Der neue Flow und
der aktualisierte Core müssen auf demselben Pi laufen. Der Core benötigt einen
beschreibbaren, dauerhaft gleichen Datenordner (`--data`, Standard `data`).
Zugangsdaten früherer Programme werden nicht übernommen.

## Aktualisierung auf dem Pi

1. Projektdateien auf den Pi übernehmen und den vorhandenen Core neu starten.
   Dieselbe Umgebung, Konfiguration und denselben Datenordner weiterverwenden.
   Keine zweite Core-Instanz starten. Die Cloudadapter brauchen keine zusätzlichen
   Python-Pakete; MQTT benötigt weiterhin die dokumentierte Paho-Abhängigkeit.
2. Bestehenden Node-RED-Flow sichern. `nodered/rovo_neu_flows.json` mit Ersetzen der
   vorhandenen ROVO-Knoten importieren, prüfen, deployen und das Dashboard neu laden.
3. Authentifiziertes Dashboard öffnen und auf einen frischen Core-Status warten.
   Broker, ACLs und Zugangsschutz gemäß [MQTT und Kamera](MQTT_UND_KAMERA.md) einrichten.
   Für Eingaben von anderen Rechnern HTTPS verwenden. Keine Request-Debugnodes oder
   Nachrichtenaufzeichnung einschalten: Eingaben werden einmalig über den lokalen,
   authentifizierten MQTT-Befehlspfad übertragen und sind niemals retained.

Der Export wurde erzeugt, aber hier weder auf einem Pi installiert noch in einer
laufenden Node-RED-Instanz deployt. Simulation und Safe Mode bleiben aktiv.

## Cloudanbieter und Modelle

1. OpenAI, Anthropic/Claude, Google/Gemini, OpenRouter, Mistral oder Groq auswählen.
   Den API-Key dieses Anbieters eingeben. **Key speichern & Modelle laden** ruft die
   Modellliste ab und speichert den Key bei erfolgreicher Abfrage, ohne Text-KI zu aktivieren.
   Der Modelltest ist der Nachweis, dass Zugang und ausgewähltes Modell zusammen funktionieren.
2. Ein Modell aus der geladenen Anbieterliste auswählen.
   Listenabruf zeigt bis zu 500 IDs der ersten Anbieter-Ergebnisseite;
   sie ist nicht zwingend vollständig und kann ungeeignete Modelle enthalten.
   Danach die Übermittlung freier Texte erlauben und „Dieses Modell für Rovo aktivieren“ wählen.
   **Speichern** sendet noch keine Modellfrage. Das Passwortfeld wird sofort geleert.
   Ein leeres Key-Feld behält nur den gespeicherten Key des ausgewählten Anbieters.
   Keys werden nicht zwischen Anbietern übernommen. Ein neuer Wert ersetzt den Key.
3. **Modell testen** sendet einen festen kurzen Testtext und prüft eine echte Antwort
   mit zulässiger Emotion. Dabei können API-Kosten entstehen. Ein gespeicherter Key
   allein gilt nicht als erfolgreich geprüfte Verbindung.
4. Danach verwenden freie Fragen aus Chat und Sprache diesen Anbieter. Bekannte lokale
   Befehle werden zuerst verarbeitet. Kein Kamerabild, Gesichtsmerkmal oder Profil wird
   als Kontext übertragen. Freie Texte selbst können persönliche Angaben enthalten.

Die sechs Anbieter verwenden feste HTTPS-Endpunkte. Keine beliebigen URLs, kein Ollama
und kein automatisches Wechseln zu anderen Anbietern oder Modellen. Anbieterwechsel
im Formular leert den eingegebenen Key und verlangt eine neue Übermittlungsfreigabe;
erst **Modell & Zugang speichern** ändert den aktiven Anbieter. Der Bereich rechts
zeigt die aktive Verbindung. Eigene Modelllisten und manuelle Modell-IDs werden
im Dashboard nicht mehr angeboten. Vorhandene Anbieterzugänge bleiben erhalten.
Antworten werden lokal auf genau `reply`/`emotion` geprüft, ohne Gerätewerkzeuge.
OpenAI nutzt Responses mit `store=false`, Claude Messages mit JSON-Schema, Gemini
GenerateContent mit JSON-Schema, OpenRouter Chat Completions mit Schema und ohne
Modellfallback. Mistral und Groq nutzen JSON-Modus mit derselben lokalen Validierung.
Nicht jedes Modell unterstützt diese Formate; dann scheitert der Modelltest eindeutig.
`store=false` ist keine Zusage über sämtliche Aufbewahrungsregeln der Anbieter.
Privatsphäre blockiert neue Modellanfragen. Stopp/Verbindungsänderungen verwerfen
verspätete Antworten; bereits übermittelte Anfragen lassen sich nicht zurückholen.

„Dieses Modell für Rovo aktivieren“ abwählen und speichern deaktiviert Text-KI dauerhaft.
Der Sprachbefehl zum Deaktivieren wirkt nur für die Sitzung.
**Aktiven Zugang entfernen** ist im aufklappbaren Bereich, verlangt Bestätigung und
löscht nur das aktive Anbieterprofil samt Key. Andere Anbieterprofile bleiben bestehen.

Grundlagen: [OpenAI](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses),
[Claude](https://platform.claude.com/docs/en/build-with-claude/structured-outputs),
[Gemini](https://ai.google.dev/gemini-api/docs/generate-content/structured-output),
[OpenRouter](https://openrouter.ai/docs/guides/features/structured-outputs),
[Mistral](https://docs.mistral.ai/studio/conversations/structured-output/json_mode),
[Groq](https://console.groq.com/docs/structured-outputs).

## Spotify

1. Eine Spotify-Developer-App anlegen und die Client-ID eintragen. Für die
   Playersteuerung ist ein berechtigtes Spotify-Konto erforderlich; Premium und
   aktuelle Development-Mode-/Nutzerbeschränkungen beim Anbieter prüfen.
2. Dieselbe Redirect-URI **exakt** in der Spotify-App und im Dashboard eintragen.
   Beispiel: `http://127.0.0.1:8888/callback`. Spotify erlaubt HTTP nur für explizite
   Loopback-IP-Adressen; `localhost` oder eine unverschlüsselte Pi-LAN-Adresse sind
   ungeeignet. Alternativ eine eigene HTTPS-Rückleitungsadresse verwenden.
   **App speichern** drücken.
3. **Mit Spotify verbinden**, den angezeigten Link in einem neuen Tab öffnen und Spotify
   die Freigaben für Wiedergabestatus und Wiedergabesteuerung erteilen.
   Der Ablauf verwendet PKCE und benötigt kein Client-Secret.
4. Die vollständige Rückleitungsadresse aus der Adresszeile kopieren. Beim
   Loopback-Beispiel darf „Seite nicht erreichbar“ erscheinen: ROVO startet dort
   keinen Listener. Entscheidend ist die Adresse mit `code` und `state`.
   Im weiterhin geöffneten Dashboard einfügen und **Anmeldung abschließen** drücken.
   Nicht hier im Chat oder in Logs teilen. Das Feld wird nach dem Senden geleert.
   Die Anmeldung ist zehn Minuten gültig und an dieselbe Dashboard-Sitzung gebunden.
   Nach Seitenwechsel, Reconnect oder Core-Neustart bei Bedarf erneut beginnen.
5. Einen vorhandenen Spotify-Connect-Player öffnen, **Verbindung prüfen / Geräte laden**
   drücken, das gewünschte Ziel auswählen und **Zielgerät speichern** drücken.
   Die ID wird aus der Geräteauswahl übernommen; es gibt kein manuelles Eingabefeld.
   Es wird nie automatisch ein anderes Gerät gewählt. Die Geräteabfrage startet keine Musik.
6. Musik über die Laufzeitregler oder „Spiele auf Spotify ABBA“ starten.
   Vor Änderungen an App/Zielgerät oder Entfernen des Zugangs laufende Musik stoppen.

Access-/Refresh-Token werden gespeichert und vor weiteren Anfragen bei Bedarf erneuert.
Rotierte Refresh-Tokens werden ebenfalls gespeichert. Bei widerrufener/abgelaufener
Freigabe ist eine neue Anmeldung nötig. Nach Neustart werden Zugang und Ziel geladen;
es erfolgt keine automatische Wiedergabe oder Start-Netzwerkprobe. Nach einer eindeutigen
401-Antwort erfolgt höchstens ein Refresh mit erneutem Versuch. Offlinefehler,
Ratenlimits und unklare Zeitüberschreitungen werden nicht automatisch wiederholt.

Diese Anbindung steuert einen vorhandenen Connect-Player. Sie installiert keinen Player
und erzeugt selbst keinen Spotify-Audiostream auf dem Pi. Soll der Pi den Ton ausgeben,
muss dort zusätzlich ein Connect-Player eingerichtet und als Zielgerät gewählt werden.
Playlists, Shuffle und Warteschlangenverwaltung gehören weiterhin nicht zur Anbindung.

**Abbrechen**, Stopp und Privatsphäre verwerfen die laufende Anmeldung. Bereits
gesendete Spotify-Aufträge können beim Anbieter schon wirksam sein; ein Netzwerk-Stopp
garantiert keine sofortige Unterbrechung am entfernten Player. Eine ausdrückliche Pause
darf auch bei aktivierter Privatsphäre gesendet werden.
**Spotify trennen** im aufklappbaren Bereich benötigt die Bestätigung
„Ja, Spotify-Einrichtung auf Rovo löschen“. Das entfernt die gespeicherte Spotify-App,
Anmeldung und Geräteauswahl auf Rovo. Danach ist eine neue Einrichtung erforderlich.
Spotify-Konto und Abo bleiben bestehen; alte Umgebungszugangsdaten werden danach nicht automatisch aktiviert.
Die App-Freigabe bei Spotify wird damit nicht widerrufen; das erfolgt im Spotify-Konto.

Grundlagen: [PKCE](https://developer.spotify.com/documentation/web-api/tutorials/code-pkce-flow),
[Token-Erneuerung](https://developer.spotify.com/documentation/web-api/tutorials/refreshing-tokens),
[Redirect-URIs](https://developer.spotify.com/documentation/web-api/concepts/redirect_uri).

## Speicherung, Status und Fehler

Die private Datei liegt unter `<Datenordner>/private/connections.json`. Neue Ordner und
Dateien haben unter Linux Rechte `0700` beziehungsweise `0600`; Schreiben erfolgt atomar
über eine temporäre Datei. Die Zugangsdaten sind darin **nicht zusätzlich verschlüsselt**.
Dienstbenutzer, Windows-ACLs und Backups entsprechend schützen. `private/` ist für Git
ausgeschlossen. Keine Zugangsdaten in Flows, Git, Screenshots oder Logs kopieren.
Beschädigte oder unter Linux für andere Benutzer lesbare gespeicherte Verbindungsdateien
werden verweigert. Die Datei dann lokal prüfen; sie wird nicht still überschrieben.

Keys/Tokens erscheinen nicht in Status, Antworten oder Flow-Kontext. Öffentliche App-ID,
Redirect-URI, Modellname und Ziel-ID werden zur Bedienung angezeigt. Ein Teststatus
enthält den Zeitpunkt der letzten erfolgreichen Prüfung, keine dauerhafte Onlinegarantie.
Nach Neustart ist er wieder ungeprüft. Bei fehlender Cloudverbindung bleiben lokale
Befehle verwendbar. Simulation und Safe Mode bleiben unabhängig davon erhalten.

Zur Pi-Abnahme gehören echte Anmeldung, Modelltest, Spielerreichbarkeit/Audioausgabe,
Core-Neustart, Token-Erneuerung, Verbindungsabbruch und Dashboard-Zugriffsschutz.
Diese Abnahme ist zusätzlich zu lokalen Simulations-/Mocktests erforderlich.
