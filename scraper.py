"""BMV-Presseübersicht in einen inoffiziellen RSS-Feed umwandeln (Python 3.11+)."""
import argparse
from datetime import datetime, timezone
from email.utils import format_datetime
from html import escape
import json
import logging
import os
from pathlib import Path
import re
import time
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup

SOURCE = "https://www.bmv.de/SiteGlobals/Forms/Suche/DE/Expertensuche_Formular.html?documentType_=PressRelease"
ROOT = Path(__file__).resolve().parent
DC = "http://purl.org/dc/elements/1.1/"
ATOM = "http://www.w3.org/2005/Atom"
ET.register_namespace("dc", DC)
ET.register_namespace("atom", ATOM)


def bmv_url(value, base):
    parts = urlsplit(urljoin(base, value))
    if parts.scheme != "https" or parts.hostname != "www.bmv.de":
        raise ValueError(f"Unerwarteter BMV-Link: {value}")
    return urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, ""))


def fetch(url):
    """Begrenzte Wiederholungen, keine Browserautomation notwendig."""
    for attempt in range(3):
        try:
            request = Request(url, headers={
                "User-Agent": "BMV-RSS/1.0 (unofficial public press-release feed)",
                "Accept": "text/html",
            })
            with urlopen(request, timeout=40) as response:
                bmv_url(response.url, url)
                if "text/html" not in response.headers.get("Content-Type", ""):
                    raise ValueError("Quelle liefert kein HTML")
                return response.read().decode(response.headers.get_content_charset() or "utf-8")
        except Exception:
            if attempt == 2:
                raise
            time.sleep(2 ** (attempt + 1))


def parse_page(html, page_url):
    soup = BeautifulSoup(html, "html.parser")
    base_tag = soup.find("base", href=True)
    base = bmv_url(base_tag["href"], page_url) if base_tag else page_url
    cards = soup.select(".search-results .card-list > li.card")
    if not cards:
        raise ValueError("Keine Ergebniskarten gefunden. Seitenstruktur oder Quelle prüfen.")
    items = []
    for card in cards:
        link = card.select_one(".card-title a.card-link[href]")
        date_tag = card.select_one(".card-date")
        if not link or not date_tag:
            raise ValueError("Ergebniskarte ohne Titel/Link oder Datum")
        url = bmv_url(link["href"], base)
        if not re.search(r"/SharedDocs/DE/Pressemitteilungen/\d{4}/[^/]+\.html$", urlsplit(url).path):
            raise ValueError(f"Unerwarteter Meldungspfad: {url}")
        # BeautifulSoup.get_text(' ') zerlegt z. B. E-<abbr>Pkw</abbr> unnötig.
        title = " ".join(link.get_text().split())
        match = re.search(r"\b\d{2}\.\d{2}\.\d{4}\b", date_tag.get_text(" ", strip=True))
        if not title or not match:
            raise ValueError("Titel oder Veröffentlichungsdatum fehlt")
        date = datetime.strptime(match[0], "%d.%m.%Y").date().isoformat()
        canonical = urlunsplit((*urlsplit(url)[:3], "", ""))
        items.append({"url": canonical, "title": title, "date": date})
    next_tag = soup.select_one(".pagination-link-next[href]")
    next_url = bmv_url(next_tag["href"], base) if next_tag else None
    return items, next_url


def collect(source, pages):
    found, visited = {}, set()
    url = source
    for _ in range(pages):
        if url in visited:
            raise ValueError("Wiederholte URL in der Seitennavigation")
        visited.add(url)
        logging.info("Abruf: %s", url)
        items, next_url = parse_page(fetch(url), url)
        if all(item["url"] in found for item in items):
            raise ValueError("Navigation liefert dieselben Meldungen erneut")
        found.update({item["url"]: item for item in items})
        if not next_url:
            break
        url = next_url
        time.sleep(1)
    return list(found.values())


def load_state(path):
    if not path.exists():
        return []
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return []  # erlaubt ein leeres Dateigerüst beim ersten Start
    items = json.loads(raw)
    if not isinstance(items, list):
        raise ValueError("data/items.json muss eine JSON-Liste enthalten (anfangs []).")
    for item in items:
        if not isinstance(item, dict) or not all(isinstance(item.get(k), str) and item[k] for k in ("url", "title", "date")):
            raise ValueError("Beschädigter Eintrag im gespeicherten Meldungsbestand")
        bmv_url(item["url"], SOURCE)
        datetime.strptime(item["date"], "%Y-%m-%d")
    return items


def render_feed(items, site_url, source, now):
    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")
    for tag, value in (
        ("title", "BMV-Pressemitteilungen (inoffizieller Feed)"),
        ("link", source),
        ("description", "Automatisch erfasste Titel und Links. Kein offizielles Angebot des Bundesministeriums für Verkehr."),
        ("language", "de"),
        ("lastBuildDate", format_datetime(now, usegmt=True)),
    ):
        ET.SubElement(channel, tag).text = value
    ET.SubElement(channel, f"{{{ATOM}}}link", href=f"{site_url}/feed.xml", rel="self", type="application/rss+xml")
    for item in items:
        node = ET.SubElement(channel, "item")
        ET.SubElement(node, "title").text = item["title"]
        ET.SubElement(node, "link").text = item["url"]
        ET.SubElement(node, "guid", isPermaLink="true").text = item["url"]
        # BMV liefert hier nur das Datum. Keine erfundene Uhrzeit in pubDate.
        ET.SubElement(node, f"{{{DC}}}date").text = item["date"]
        date = datetime.strptime(item["date"], "%Y-%m-%d").strftime("%d.%m.%Y")
        ET.SubElement(node, "description").text = f"BMV-Pressemitteilung vom {date}. Volltext über den Original-Link."
    payload = ET.tostring(rss, encoding="utf-8", xml_declaration=True)
    ET.fromstring(payload)  # vor Veröffentlichung auf wohlgeformtes XML prüfen
    return payload


def atomic_write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_bytes(content)
    temp.replace(path)


def run():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default=SOURCE)
    parser.add_argument("--pages", type=int, default=3)
    parser.add_argument("--state", type=Path, default=ROOT / "data/items.json")
    parser.add_argument("--output", type=Path, default=ROOT / "public")
    parser.add_argument("--site-url", default=os.environ.get("SITE_URL", ""))
    args = parser.parse_args()
    if args.pages < 1 or not args.site_url:
        parser.error("--pages muss positiv sein; --site-url oder SITE_URL ist erforderlich")
    site_url = args.site_url.rstrip("/")
    if urlsplit(site_url).scheme != "https" or not urlsplit(site_url).hostname:
        parser.error("Die Feed-Basisadresse muss eine vollständige HTTPS-URL sein")
    bmv_url(args.source, SOURCE)
    old = load_state(args.state)
    incoming = collect(args.source, args.pages)
    merged = {item["url"]: item for item in old}
    new_count = sum(item["url"] not in merged for item in incoming)
    merged.update({item["url"]: item for item in incoming})
    all_items = sorted(merged.values(), key=lambda item: (item["date"], item["url"]), reverse=True)
    feed_items = all_items[:100]
    now = datetime.now(timezone.utc)
    feed = render_feed(feed_items, site_url, args.source, now)
    status = {"last_success_utc": now.isoformat(), "fetched_items": len(incoming),
              "new_items": new_count, "stored_items": len(all_items), "feed_items": len(feed_items),
              "newest_source_date": all_items[0]["date"], "source": args.source}
    latest = "".join(f'<li>{escape(i["date"])}: <a href="{escape(i["url"], quote=True)}">{escape(i["title"])}</a></li>' for i in feed_items[:10])
    index = f'''<!doctype html><html lang="de"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="alternate" type="application/rss+xml" title="BMV-Pressemitteilungen" href="feed.xml">
<title>BMV RSS</title><style>body{{font:17px/1.6 system-ui;max-width:850px;margin:48px auto;padding:0 20px}}li{{margin:12px 0}}</style>
<h1>BMV-Pressemitteilungen</h1><p>Inoffizieller RSS-Feed. Kein Angebot des Ministeriums.</p>
<p><a href="feed.xml">RSS-Feed abonnieren</a> · <a href="status.json">Abrufstatus</a></p>
<p>Letzter erfolgreicher Abruf: {escape(now.isoformat())} (UTC).<br>
Neuestes Veröffentlichungsdatum in der Quelle: {escape(all_items[0]["date"])}.</p>
<p>Ein erfolgreicher Abruf bestätigt nicht, dass das Ministerium seine Übersicht vollständig aktualisiert hat.</p>
<ul>{latest}</ul></html>'''
    # Alle Abrufe und die XML-Prüfung sind abgeschlossen, bevor Dateien ersetzt werden.
    atomic_write(args.output / "feed.xml", feed)
    atomic_write(args.output / "index.html", index.encode())
    atomic_write(args.output / "status.json", (json.dumps(status, ensure_ascii=False, indent=2) + "\n").encode())
    atomic_write(args.state, (json.dumps(all_items, ensure_ascii=False, indent=2) + "\n").encode())
    logging.info("Erfolgreich: %s abgerufen, %s neu, %s gespeichert", len(incoming), new_count, len(all_items))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        run()
    except Exception:
        logging.exception("Abbruch: Bestand/Quelle prüfen. Keine neue Veröffentlichung vornehmen.")
        raise SystemExit(1)
