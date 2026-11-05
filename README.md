# BMV-Pressemitteilungen als RSS

Inoffizieller Feed aus der öffentlichen Presseübersicht des Bundesministeriums für Verkehr. Kein Angebot des BMV. Enthält Titel, Veröffentlichungsdatum und Original-Link, keine Volltexte. Stand der Umsetzung: 05.11.2026.

## In dein vorhandenes Repository übernehmen
1. Optional `.gitignore` und diese Anleitung übernehmen.
6. Alles auf dem Standardbranch speichern (gewöhnlich `main`).
7. Unter **Settings → Pages → Build and deployment → Source** die Option **GitHub Actions** wählen. Dafür kann ein öffentliches Repository im kostenlosen Tarif verwendet werden.
8. Unter **Actions → Update feed → Run workflow** den ersten Lauf starten. Ein durch Dateiänderungen ausgelöster Lauf vor der Pages-Einrichtung kann fehlschlagen; danach manuell neu starten.
9. Nach erfolgreichem Build und Deploy unter **Settings → Pages** die veröffentlichte Adresse öffnen. `feed.xml` an diese Adresse anhängen oder den RSS-Link auf der Startseite kopieren.
10. Diese URL in deinem RSS-Reader abonnieren und gegen die BMV-Übersicht prüfen.

Benutzername und Repository-Name müssen im Skript nicht ersetzt werden: `configure-pages` liefert die tatsächliche Basisadresse. Docker, eine eigene Domain und API-Schlüssel sind nicht erforderlich. 
Repository- oder Organisationsregeln können automatisches Schreiben oder Pages-Deployments untersagen; diese Beschränkungen werden nicht umgangen. Die Workflow-Datei vergibt die benötigten Rechte gezielt pro Job.

## Was automatisch passiert

- Zwei geplante Läufe pro Stunde (Minute 7 und 37), zusätzlich manuell oder bei Änderungen an den Programmdateien.
- Drei Ergebnisseiten werden nacheinander abgerufen; relative Links werden anhand des HTML-`base`-Elements aufgelöst.
- Beim ersten Lauf wird damit ein Ausschnitt des Archivs übernommen (in der geprüften Übersicht 30 Meldungen). Es erfolgt kein vollständiger historischer Import.
- Die Meldungs-URL dient als feste RSS-Kennung. Geänderte Titel oder Daten aktualisieren denselben Eintrag.
- Der Bestand bleibt in `data/items.json` erhalten. Nur Änderungen lösen einen automatischen Commit aus.
- Der Feed enthält bis zu 100 zuletzt datierte Meldungen; der gespeicherte Bestand wird nicht abgeschnitten.
- `public/feed.xml`, `public/index.html` und `public/status.json` werden erzeugt und gemeinsam veröffentlicht. Nur `public` wird veröffentlicht.
- Bei einem Abruf-, Parser-, Test- oder Git-Fehler wird nicht neu veröffentlicht. Der bisherige Pages-Stand bleibt verfügbar.

## Datumsangaben und Vollständigkeit

Die geprüfte Übersicht liefert ein Tagesdatum ohne Uhrzeit. Deshalb verwendet der RSS-Feed `dc:date` mit dem Originaldatum und nennt es zusätzlich im Beschreibungstext. Ein `pubDate` mit erfundener Uhrzeit wird nicht gesetzt. Ob dein Reader `dc:date` zur Sortierung verwendet, muss im ersten Test geprüft werden. `lastBuildDate` bezeichnet den tatsächlichen Zeitpunkt der Feed-Erzeugung und nicht die Veröffentlichung einer Meldung.

Am 05.11.2026 enthielt die direkt abgerufene erste Ergebnisseite als neueste Meldung ein Datum vom 23.10.2026. Das ist eine Beobachtung der Quelle, kein Beleg dafür, dass seitdem nichts veröffentlicht wurde. Vor produktiver Nutzung die gewählte Übersicht mit der gewünschten BMV-Presseübersicht abgleichen. Alternative Quelle bei Bedarf über `--source` übergeben und ihre Struktur prüfen.

Überlappende Abrufe verringern Lücken, garantieren sie aber nicht: Bei mehr neuen Meldungen als innerhalb der drei geprüften Seiten können nach längeren Ausfällen Meldungen fehlen. Dann `--pages 3` im Workflow erhöhen oder einmalig mit einer größeren Seitenzahl nachholen. Die Seitennavigation wird aus dem HTML gelesen, nicht aus fest programmierten Seitenparametern.

## Kontrolle und Grenzen

Die Startseite und `status.json` zeigen den letzten erfolgreichen Abruf und das neueste Veröffentlichungsdatum. Unter **Actions** stehen Protokolle und eine Zusammenfassung. GitHub-Benachrichtigungen für fehlgeschlagene Actions einschalten. Dies ist noch keine unabhängige Überwachung: Ein gar nicht gestarteter Lauf oder ein fehlgeschlagenes Deployment nach erfolgreichem Build benötigt zusätzliche Kontrolle. `status.json` zeigt erst nach erfolgreicher Veröffentlichung den neuen Stand.

GitHub-Zeitpläne sind nicht minutengenau und können ausfallen. Öffentliche Zeitpläne können nach 60 Tagen ohne Repository-Aktivität deaktiviert werden. Automatische Bestands-Commits erfolgen nur bei Änderungen; sie ersetzen keine separate Kontrolle des Zeitplans.

## Lokal ausführen (optional)

Python 3.11 oder neuer, empfohlen 3.12:

```bash
python -m pip install -r requirements.txt
python -m unittest -v
python scraper.py --site-url https://dein-username.github.io/bmv-rss
```

`--site-url` muss der späteren Basisadresse entsprechen. Für einen Test ohne Änderung des eigentlichen Bestands:

```bash
python scraper.py --pages 3 --site-url https://example.github.io/bmv-rss --state /tmp/bmv-items.json --output /tmp/bmv-public
```

## Referenzen

- Quelle: https://www.bmv.de/SiteGlobals/Forms/Suche/DE/Expertensuche_Formular.html?documentType_=PressRelease
- Pages-Workflow: https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages
- Zeitpläne: https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule

Die Python-Abhängigkeit und GitHub Actions verwenden feste Versionsnummern bzw. Major-Tags. Diese sollten bei längerer Nutzung gelegentlich aktualisiert werden. Sollte der Feed dysfunktional sein, gerne bei mir melden oder fix vorschlagen :)
