# amt-control

Kleines Python-Kommandozeilenwerkzeug zur Verwaltung von Rechnern über Intel Active Management Technology (Intel AMT).

Mit `amt-control` lassen sich konfigurierte Rechner abfragen und Power-Befehle über die AMT-Schnittstelle ausführen.

## Funktionen

- Konfigurierte AMT-Rechner auflisten
- Rechnerstatus abfragen
- Rechner einschalten
- Rechner ausschalten
- Rechner zurücksetzen
- HTTP oder HTTPS pro Rechner konfigurieren
- AMT-Benutzername bei Bedarf überschreiben
- Kennwort interaktiv oder über eine Umgebungsvariable übergeben
- Optionales Übergeben des Kennworts über einen Kommandozeilenparameter
- Verständliche Fehlermeldungen bei Kommunikationsfehlern und AMT-Fehlerantworten
- Exit-Codes zur Verwendung in Shell-Skripten

## Voraussetzungen

- Python 3
- Ein erreichbarer Rechner mit aktivierter und konfigurierter Intel-AMT-Funktion
- Netzwerkzugriff auf den konfigurierten AMT-Port
- Gültige AMT-Zugangsdaten mit den erforderlichen Berechtigungen

Das Skript verwendet die Python-Standardbibliothek. Zusätzliche Python-Pakete sind nicht erforderlich.

## Installation

Repository über SSH klonen:

```bash
git clone git@github.com:schlusenbaum/amt-control.git
cd amt-control
```

Alternativ kann das Repository über HTTPS geklont werden:

```bash
git clone https://github.com/schlusenbaum/amt-control.git
cd amt-control
```

Beispielkonfiguration kopieren:

```bash
cp hosts.example.json hosts.json
```

Anschließend `hosts.json` an die eigenen AMT-Rechner anpassen.

## Konfiguration

Die Rechner werden in `hosts.json` definiert.

### Beispiel

```json
{
    "unraid": {
        "host": "192.0.2.10",
        "port": 16993,
        "username": "admin",
        "protocol": "https"
    },
    "m920x": {
        "host": "192.0.2.12",
        "port": 16992,
        "username": "admin",
        "protocol": "http"
    }
}
```

Die IP-Adressen sind Platzhalter aus einem für Dokumentationszwecke reservierten Bereich. Sie müssen durch die tatsächlichen Adressen der eigenen AMT-Rechner ersetzt werden.

Die Namen `unraid` und `m920x` sind frei wählbare Bezeichnungen. Sie dienen später als Argument für die Befehle.

### Konfigurationsfelder

| Feld | Beschreibung |
|---|---|
| `host` | IP-Adresse oder Hostname des AMT-Rechners |
| `port` | TCP-Port der AMT-Schnittstelle |
| `username` | AMT-Benutzername |
| `protocol` | Verbindungsprotokoll: `http` oder `https` |

### HTTP und HTTPS

Das Protokoll wird für jeden Rechner separat konfiguriert.

- `http` verwendet eine unverschlüsselte HTTP-Verbindung.
- `https` verwendet HTTPS.

HTTP überträgt die Kommunikation unverschlüsselt und sollte nur in einer entsprechend abgesicherten Umgebung verwendet werden.

Bei HTTPS hängt die Sicherheit auch von der Prüfung des Serverzertifikats ab. Wenn die Zertifikatsprüfung deaktiviert ist, kann die Identität des AMT-Servers nicht zuverlässig anhand des Zertifikats überprüft werden.

### Lokale Konfiguration

Die Datei `hosts.json` ist in `.gitignore` eingetragen und wird deshalb nicht automatisch von Git erfasst.

Die Datei `hosts.example.json` dient als Vorlage und enthält ausschließlich Beispielwerte.

**Die lokale `hosts.json` mit den tatsächlichen Rechnerdaten darf nicht versehentlich in ein öffentliches Repository hochgeladen werden.**

## Verwendung

Die allgemeine Aufrufsyntax lautet:

```text
python3 amt.py [-h] [-u USERNAME] [-p PASSWORD] {list,status,start,stop,reset} [host]
```

### Hilfe anzeigen

```bash
python3 amt.py --help
```

Die Hilfe zeigt die verfügbaren Befehle und Kommandozeilenparameter.

### Konfigurierte Rechner auflisten

```bash
python3 amt.py list
```

Der Befehl listet die in der Konfiguration definierten AMT-Rechner auf.

### Status abfragen

```bash
python3 amt.py status unraid
```

Für einen anderen konfigurierten Rechner:

```bash
python3 amt.py status m920x
```

Der Rechnername muss als Eintrag in `hosts.json` vorhanden sein.

### Rechner einschalten

```bash
python3 amt.py start unraid
```

Der Einschaltbefehl wird über AMT an den angegebenen Rechner übermittelt.

### Rechner ausschalten

```bash
python3 amt.py stop unraid
```

Der Ausschaltbefehl wird über AMT an den angegebenen Rechner übermittelt.

### Rechner zurücksetzen

```bash
python3 amt.py reset unraid
```

Der Reset-Befehl fordert einen Hardware-Reset über AMT an.

**Achtung:** `start`, `stop` und `reset` lösen Power-Aktionen aus. Vor der Ausführung muss sichergestellt sein, dass der richtige Rechner ausgewählt wurde.

## Zugangsdaten

Das Kennwort wird nicht in `hosts.json` gespeichert.

Das Skript unterstützt drei Möglichkeiten zur Kennwortübergabe:

1. Kommandozeilenparameter `-p` beziehungsweise `--password`
2. Umgebungsvariable `AMT_PASSWORD`
3. Interaktive Kennworteingabe

Wenn mehrere Möglichkeiten gleichzeitig verwendet werden, hat der Kommandozeilenparameter Vorrang vor der Umgebungsvariable. Ist beides nicht gesetzt, wird das Kennwort interaktiv abgefragt.

### 1. Interaktive Kennworteingabe

Einfach den gewünschten Befehl ausführen:

```bash
python3 amt.py status unraid
```

Wenn kein Kennwort übergeben wurde, fragt das Skript danach.

Die interaktive Eingabe verhindert, dass das Kennwort direkt im aufgerufenen Kommando steht.

### 2. Umgebungsvariable `AMT_PASSWORD`

Das Kennwort kann über die Umgebungsvariable `AMT_PASSWORD` bereitgestellt werden.

Unter macOS und Linux lässt sich das Kennwort beispielsweise verdeckt einlesen:

```bash
read -s AMT_PASSWORD
export AMT_PASSWORD
```

Das Kennwort wird bei `read -s` nicht auf dem Bildschirm angezeigt. Nach der Eingabe muss Enter gedrückt werden.

Anschließend kann der Befehl ausgeführt werden:

```bash
python3 amt.py status unraid
```

Weitere Befehle können in derselben Shell ausgeführt werden, ohne das Kennwort erneut einzugeben.

Nach Abschluss der Arbeit kann die Umgebungsvariable entfernt werden:

```bash
unset AMT_PASSWORD
```

Die Variable gilt für die aktuelle Shell und wird an gestartete Prozesse weitergegeben, sofern sie exportiert wurde.

**Sicherheitshinweis:** Die Umgebungsvariable ist gegenüber einem direkt angegebenen Kommandozeilenkennwort häufig die bessere Wahl. Sie ist jedoch kein vollständiger Geheimnisschutz: Andere Prozesse mit ausreichenden Berechtigungen können unter Umständen auf Prozessumgebungen zugreifen.

### 3. Kennwort über einen Kommandozeilenparameter

Das Kennwort kann optional mit `-p` übergeben werden:

```bash
python3 amt.py -p 'DEIN_AMT_KENNWORT' status unraid
```

Alternativ kann die ausgeschriebene Option verwendet werden:

```bash
python3 amt.py --password 'DEIN_AMT_KENNWORT' status unraid
```

Diese Variante ist bequem, aber weniger sicher. Das Kennwort kann in der Shell-History oder der Prozessliste sichtbar werden.

Verwende nach Möglichkeit die interaktive Eingabe oder eine geeignete Umgebungsvariable.

## AMT-Benutzername überschreiben

Standardmäßig verwendet das Skript den Benutzernamen aus `hosts.json`.

Für einen einzelnen Aufruf kann der Benutzername mit `-u` überschrieben werden:

```bash
python3 amt.py -u admin status unraid
```

Alternativ:

```bash
python3 amt.py --user admin status unraid
```

Die Änderung gilt nur für diesen Aufruf. Die Konfigurationsdatei wird nicht verändert.

## Rückgabecodes

Das Skript liefert Exit-Codes, sodass es auch aus Shell-Skripten heraus aufgerufen werden kann.

| Exit-Code | Bedeutung |
|---:|---|
| `0` | Der Befehl wurde erfolgreich verarbeitet |
| `1` | Fehler bei einer AMT-Anfrage oder bei der Ausführung eines Power-Befehls |
| `2` | Aufruf- oder Konfigurationsfehler, beispielsweise ein unbekannter Rechner oder ein fehlender Rechnername |

### Exit-Code abfragen

```bash
python3 amt.py status unraid
echo "Exit-Code: $?"
```

Ein Exit-Code von `0` bedeutet bei einem Power-Befehl, dass AMT den Befehl mit einem erfolgreichen Rückgabewert bestätigt hat.

Das garantiert nicht, dass der gewünschte physische Zustand des Rechners bereits erreicht wurde.

## Fehlerbehandlung

Das Skript behandelt unter anderem:

- fehlgeschlagene AMT-Anmeldung
- verweigerten Zugriff
- HTTP-Fehler
- Verbindungsprobleme und Zeitüberschreitungen
- ungültige SOAP-XML-Antworten
- SOAP Faults
- von AMT abgelehnte Power-Befehle
- unbekannte Rechnernamen
- fehlende Pflichtargumente

Die Fehlermeldungen werden auf der Kommandozeile ausgegeben. Bei Fehlern während einer AMT-Anfrage liefert das Skript einen von null verschiedenen Exit-Code.

### Zeitüberschreitung bei Power-Befehlen

Ein Timeout oder Verbindungsabbruch nach dem Absenden eines Power-Befehls bedeutet nicht zwangsläufig, dass AMT den Befehl nicht ausgeführt hat.

In diesem Fall kann der Ausgang der Anfrage unklar sein.

**Empfohlenes Vorgehen:**

1. Den aktuellen Rechnerstatus erneut abfragen.
2. Prüfen, ob der gewünschte Zustand bereits erreicht wurde.
3. Den Power-Befehl nur dann erneut senden, wenn dies erforderlich ist.

Dadurch wird vermieden, dass ein Befehl aufgrund einer unklaren Antwort unnötig wiederholt wird.

## Sicherheit

- Zugangsdaten gehören nicht in den Quellcode.
- Kennwörter sollten nicht in `hosts.json` gespeichert werden.
- Die lokale `hosts.json` darf nicht versehentlich veröffentlicht werden.
- `hosts.example.json` enthält nur Beispielwerte.
- HTTP überträgt die Kommunikation unverschlüsselt.
- Eine deaktivierte HTTPS-Zertifikatsprüfung schützt nicht vor einem gefälschten AMT-Server.
- Power-Befehle sollten nur auf eindeutig identifizierten Zielrechnern ausgeführt werden.
- AMT sollte nur in einer entsprechend abgesicherten Netzwerkumgebung erreichbar sein.

## Lizenz

Dieses Projekt steht unter der [MIT-Lizenz](LICENSE).

Copyright © 2026 Christian Richter.

Die MIT-Lizenz erlaubt die Nutzung, Veränderung und Weiterverbreitung der
Software unter den in der Datei LICENSE genannten Bedingungen.
