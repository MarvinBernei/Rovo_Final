# WLAN-Einrichtung am Handy

## Ablauf

1. ROVO startet. NetworkManager versucht gespeicherte WLAN-Verbindungen.
2. Nach 60 Sekunden ohne WLAN-Verbindung startet der separate Wächter das
   passwortgeschützte Netz `ROVO-Einrichtung`.
3. Am Handy mit diesem Netz verbinden. Das Hotspot-Passwort steht auf einem
   selbst anzubringenden Geräteaufkleber; es ist nicht das Passwort des Ziel-WLANs.
4. Im Einrichtungsportal das Ziel-WLAN auswählen und dessen Passwort eingeben.
5. Bei erfolgreicher Verbindung verschwindet das Einrichtungsnetz. Bei falschem
   Passwort wird es für einen weiteren Versuch wieder geöffnet.

Bekannte WLAN-Zugangsdaten verwaltet NetworkManager, nicht ROVOs Personen- oder
Notizdatenbank. Ein wieder erreichbares, gespeichertes WLAN soll deshalb bereits
vor dem Portalstart automatisch verbunden werden.

Das Popup hängt vom Betriebssystem ab. Falls es ausbleibt: im Browser ausdrücklich
**http://192.168.42.1** öffnen. Das Einrichtungsnetz hat normalerweise kein Internet;
am Handy bei Nachfrage „verbunden bleiben“ wählen. HTTPS-Seiten werden nicht
entschlüsselt oder mit einem eigenen Zertifikat ersetzt.

## Aufteilung und Voraussetzungen

`rovo/network_setup.py` überwacht ausschließlich den WLAN-Zustand auf einem festen
Interface. `config/network_setup.json` ist eine eigene Konfiguration, getrennt
vom Core. Sie ist standardmäßig ausgeschaltet; zusätzlich ist `--apply` erforderlich.
Ohne dieses Flag werden auch keine Netzwerkabfragen durchgeführt.

Als Portal dient das externe **balena WiFi Connect**. Es übernimmt Oberfläche,
WLAN-Auswahl und Verbindungsversuch. Diese Abhängigkeit ist hier weder enthalten
noch installiert. Die Integration richtet sich nach der dokumentierten CLI.
Vor Aktivierung müssen ausführbare Version, vollständige UI-Dateien, NetworkManager,
DNS/DHCP-Abhängigkeiten und AP-Unterstützung des Pi-WLAN-Treibers zusammen geprüft werden.
Pi-5-/aktuelles-Pi-OS-Kompatibilität ist in dieser Sitzung nicht nachgewiesen.

Quellen: [WiFi Connect](https://github.com/balena-os/wifi-connect),
[CLI-Optionen](https://github.com/balena-os/wifi-connect/blob/master/docs/command-line-arguments.md),
[Raspberry-Pi-Netzwerkkonfiguration](https://www.raspberrypi.com/documentation/computers/configuration.html).

## Vorbereitung auf dem Pi

Noch nicht ausgeführte Installationsschritte:

- Den tatsächlichen Interfacenamen mit `nmcli device status` prüfen.
- Eine für OS und CPU passende WiFi-Connect-Version aus dem offiziellen Projekt
  prüfen und installieren; UI ebenfalls bereitstellen. **Das historische
  Stretch-Installationsskript nicht ungeprüft auf aktuellem Pi OS ausführen.**
- Die vorgesehenen Pfade in `config/network_setup.json` prüfen/anpassen.
- Unter `/etc/rovo/network-passphrase` ein individuelles Hotspot-Passwort hinterlegen:
  8–63 druckbare ASCII-Zeichen. Eigentümer root, Rechte 0600. Nicht in Git speichern.
- Die Konfiguration nach `/etc/rovo/network_setup.json` übernehmen, root als Eigentümer
  und `enabled=true` setzen.
- Den Wächter nach `/opt/rovo-network/rovo/network_setup.py` kopieren. Code, ausführbare
  Abhängigkeiten, UI und Konfiguration müssen gegen Änderungen durch normale
  Benutzer geschützt sein. Den Roboter-Core weiterhin ohne root betreiben.

Konfiguration gefahrlos prüfen:

```bash
python3 -m rovo.network_setup --config config/network_setup.json
```

Erster realer Test ausschließlich mit lokaler Konsole am Pi, damit ein Wechsel
des WLANs die einzige Verwaltungsverbindung nicht abschneidet:

```bash
sudo /usr/bin/python3 /opt/rovo-network/rovo/network_setup.py --config /etc/rovo/network_setup.json --apply
```

Erst nach erfolgreichem Gerätetest `scripts/rovo-network.service` prüfen, nach
`/etc/systemd/system/rovo-network.service` übernehmen und bewusst aktivieren.
Die Vorlage ist ein separater Systemdienst; es wird hier kein Dienst installiert.
Auf Port 80 sowie DNS/DHCP dürfen keine konkurrierenden Dienste die Einrichtung
blockieren. Erreichbarkeit des Portals von anderen Interfaces und Firewallregeln
bei gleichzeitigem Ethernet auf dem Gerät prüfen.

## Verhalten und Grenzen

- WLAN-Verbindung wird von Internetzugriff unterschieden. Kein Internet bei
  weiterhin verbundenem WLAN startet keinen Hotspot. Ethernet allein unterdrückt
  die WLAN-Einrichtung nicht.
- Fehlender NetworkManager, unbekannter Zustand, deaktiviertes/unverwaltetes
  Interface oder ein fremder aktiver Hotspot führen nicht zur Netzwerkübernahme.
- Das eingebaute WLAN wird abwechselnd für Portal und Zielverbindung verwendet.
  Beim Umschalten verliert das Handy vorübergehend die Portalverbindung.
- Nach 600 Sekunden ohne Aktivität beendet WiFi Connect das Portal. Danach wartet
  der Wächter 60 Sekunden und erneut die Verbindungsfrist vor einem weiteren Start.
  Während des Portals wird nicht alle paar Sekunden das Netz umgeschaltet.
- Nur eine Wächterinstanz per Dateisperre. Kein eigener ROVO-DNS-/DHCP-Server neben
  WiFi Connect. Keine Zugangsdaten in Kommandozeilen oder Wächterprotokollen.
  Kindprozess-Ausgaben werden nicht ins Journal übernommen.
- Die Portaloberfläche stammt aus WiFi Connect; eine eigene deutsche ROVO-Gestaltung
  ist noch nicht enthalten. WPA-Enterprise, versteckte Netze und Hotel-Portale des
  Zielnetzes sind nicht als unterstützt abgenommen.

## Abnahme am Gerät

Neuer Ort ohne bekanntes WLAN; gespeichertes WLAN beim Start; kurze Funkunterbrechung;
falsches Passwort und erneuter Versuch; Verbindung ohne Internet; Android/iPhone
Popup und manuelle Adresse; Neustart nach erfolgreichem Speichern; rfkill;
Timeout sowie Beenden des Dienstes mit Aufräumen von Hotspot/DNS/DHCP testen.
Die Python-Mocktests ersetzen diese Netzwerkabnahme nicht.
