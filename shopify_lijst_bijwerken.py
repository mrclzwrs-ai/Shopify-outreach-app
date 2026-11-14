"""
Werkt het bestand shopify_winkels.txt bij met adressen van Shopify-winkels
(iets.myshopify.com) uit de gratis, openbare Common Crawl-index.

Draait één keer per week via GitHub (zie .github/workflows/shopify-lijst.yml),
rustig aan, zodat we Common Crawl niet overbelasten.
"""

import json
import random
import sys
import time

import requests

BESTAND = "shopify_winkels.txt"
MAX_ADRESSEN = 60000
PAGINAS_PER_KEER = 12
PAUZE = 10  # seconden tussen verzoeken
MAX_TIJD = 20 * 60  # na 20 minuten netjes stoppen
START = time.time()

sessie = requests.Session()
sessie.headers["User-Agent"] = "ShopReels-outreach/1.0 (weekly, low volume)"


def tijd_op():
    return time.time() - START > MAX_TIJD


def opslaan(bestaand, nieuw):
    alles = sorted(bestaand | nieuw)
    if len(alles) > MAX_ADRESSEN:
        alles = sorted(random.sample(alles, MAX_ADRESSEN))
    with open(BESTAND, "w", encoding="utf-8") as f:
        f.write("\n".join(alles) + ("\n" if alles else ""))
    return len(alles)


def haal(url, params=None, pogingen=3):
    for p in range(pogingen):
        if tijd_op():
            return None
        print(f"  ophalen: {url} {params or ''}", flush=True)
        try:
            r = sessie.get(url, params=params, timeout=60)
            if r.status_code == 200:
                return r
            print(f"  code {r.status_code}, even wachten...", flush=True)
        except requests.RequestException as ex:
            print(f"  {type(ex).__name__}, even wachten...", flush=True)
        time.sleep(PAUZE * (p + 2))
    return None


def main():
    try:
        bestaand = {l.strip() for l in open(BESTAND, encoding="utf-8") if l.strip()}
    except FileNotFoundError:
        bestaand = set()
    print(f"Al in de lijst: {len(bestaand)}", flush=True)

    r = haal("https://index.commoncrawl.org/collinfo.json")
    if r is None:
        print("Common Crawl niet bereikbaar, volgende week opnieuw.", flush=True)
        return 0
    indexen = [c["cdx-api"] for c in r.json()][:3]

    nieuw = set()
    for api in indexen:
        time.sleep(PAUZE)
        r = haal(api, {"url": "*.myshopify.com", "output": "json", "showNumPages": "true"})
        if r is None:
            continue
        paginas = int(r.json().get("pages", 1))
        keuze = random.sample(range(paginas), min(PAGINAS_PER_KEER // len(indexen), paginas))
        for pagina in keuze:
            time.sleep(PAUZE)
            r = haal(api, {"url": "*.myshopify.com", "output": "json", "fl": "url", "page": pagina})
            if r is None:
                continue
            voor = len(nieuw)
            for regel in r.text.splitlines():
                try:
                    u = json.loads(regel).get("url", "")
                except ValueError:
                    continue
                host = u.split("://")[-1].split("/")[0].split(":")[0].lower()
                if host.endswith(".myshopify.com") and host.count(".") == 2:
                    nieuw.add(host)
            totaal = opslaan(bestaand, nieuw)
            print(f"{api.split('/')[-1]} blok {pagina}: +{len(nieuw) - voor} (totaal {totaal})", flush=True)
            if tijd_op():
                break
        if tijd_op():
            print("Tijd om, ik stop en bewaar wat ik heb.", flush=True)
            break

    totaal = opslaan(bestaand, nieuw)
    print(f"Nieuw: {len(nieuw - bestaand)} | Totaal in de lijst: {totaal}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
