"""
De Bedrijfsdetective – detective en schrijver in één.

Per winkel:
1. Kijkt in robots.txt of de site automatisch lezen toestaat. Zo niet: niets lezen.
2. Leest alleen openbare pagina's van de winkel zelf (homepage, 'over ons',
   een paar producten uit de openbare Shopify-productlijst).
3. Laat de AI (Claude) een kort rapport maken en een eigen, persoonlijke mail
   schrijven in de taal van de winkel.

Lukt iets niet (geen sleutel, site verbiedt lezen, AI-fout), dan geeft
schrijf_persoonlijke_mail() None terug en gebruikt de app de oude standaardmail.
Er gaat dus nooit een dag verloren.

Privacy: we gebruiken alleen bedrijfsinformatie van de eigen website. De AI
krijgt de opdracht geen namen van medewerkers of privégegevens te gebruiken,
en we bewaren niets.
"""

import html as html_lib
import json
import os
import re
from urllib import robotparser
from urllib.parse import urlparse

import requests

import outreach_core as oc

MODEL = os.environ.get("DETECTIVE_MODEL", "claude-sonnet-5-5")
API_URL = "https://api.anthropic.com/v1/messages"
MAX_TEKST = 9000          # zoveel tekens van de site sturen we maximaal naar de AI
BOT_NAAM = "ShopReelsDetective"

TAALNAAM = {"NL": "Nederlands", "EN": "Engels", "DE": "Duits", "ES": "Spaans"}

EXTRA_PAGINAS = ["/pages/about-us", "/pages/about", "/pages/over-ons", "/pages/ons-verhaal",
                 "/pages/our-story", "/pages/uber-uns"]


# ---------------------------------------------------------------------------
# 1+2. Openbare tekst van de winkel verzamelen (alleen als robots.txt het toestaat)
# ---------------------------------------------------------------------------

def html_naar_tekst(tekst):
    tekst = re.sub(r"(?is)<(script|style|noscript|svg|template)[^>]*>.*?</\1>", " ", tekst)
    tekst = re.sub(r"(?s)<!--.*?-->", " ", tekst)
    tekst = re.sub(r"(?i)<br\s*/?>|</(p|div|li|h[1-6]|section|tr)>", "\n", tekst)
    tekst = re.sub(r"<[^>]+>", " ", tekst)
    tekst = html_lib.unescape(tekst)
    tekst = re.sub(r"[ \t\r\f\v]+", " ", tekst)
    tekst = re.sub(r"\n\s*\n+", "\n", tekst)
    return tekst.strip()


def _haal_als_mag(sessie, basis, pad, rp):
    if rp is not None and not (rp.can_fetch(BOT_NAAM, basis + pad) and rp.can_fetch("*", basis + pad)):
        return None
    return oc._haal(sessie, basis + pad, timeout=10)


def verzamel_winkeltekst(website, sessie=None):
    """
    Geeft (tekst, reden) terug. tekst is None als we niet mogen of kunnen lezen.
    """
    sessie = sessie or oc._sessie()
    basis = oc.basis_url(website)

    rp = None
    r = oc._haal(sessie, basis + "/robots.txt", timeout=8)
    if r is not None:
        rp = robotparser.RobotFileParser()
        rp.parse(r.text.splitlines())
        if not (rp.can_fetch(BOT_NAAM, basis + "/") and rp.can_fetch("*", basis + "/")):
            return None, "Site staat automatisch lezen niet toe (robots.txt)"

    delen = []
    home = _haal_als_mag(sessie, basis, "/", rp)
    if home is None:
        return None, "Homepage niet bereikbaar"
    titel = re.search(r"(?is)<title[^>]*>(.*?)</title>", home.text)
    omschrijving = re.search(r'(?is)<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']', home.text)
    if titel:
        delen.append("TITEL: " + html_lib.unescape(titel.group(1)).strip())
    if omschrijving:
        delen.append("OMSCHRIJVING: " + html_lib.unescape(omschrijving.group(1)).strip())
    delen.append("HOMEPAGE:\n" + html_naar_tekst(home.text)[:4000])

    # Kenmerken die we zelf kunnen zien
    video = bool(re.search(r"(?i)<video|youtube\.com/embed|player\.vimeo|\.mp4", home.text))
    socials = sorted({m.lower() for m in re.findall(
        r"(?i)(instagram|tiktok|facebook|youtube|pinterest)\.com/", home.text)})
    delen.append(f"VIDEO OP HOMEPAGE: {'ja' if video else 'nee'}")
    delen.append("SOCIALE MEDIA GELINKT: " + (", ".join(socials) if socials else "geen gevonden"))

    for pad in EXTRA_PAGINAS:
        p = _haal_als_mag(sessie, basis, pad, rp)
        if p is not None:
            delen.append("OVER ONS:\n" + html_naar_tekst(p.text)[:2000])
            break

    pj = _haal_als_mag(sessie, basis, "/products.json?limit=8", rp)
    if pj is not None:
        try:
            regels = []
            for prod in (pj.json().get("products") or [])[:8]:
                prijs = ""
                if prod.get("variants"):
                    prijs = prod["variants"][0].get("price") or ""
                beschrijving = html_naar_tekst(prod.get("body_html") or "")[:200]
                regels.append(f"- {prod.get('title', '')} ({prijs}) {beschrijving}")
            if regels:
                delen.append("PRODUCTEN:\n" + "\n".join(regels))
        except ValueError:
            pass

    return "\n\n".join(delen)[:MAX_TEKST], ""


# ---------------------------------------------------------------------------
# 3. Rapport + persoonlijke mail laten schrijven
# ---------------------------------------------------------------------------

SYSTEEM = """Je bent de verkoopschrijver van Marcel, een ervaren verkoper die ShopReels heeft gemaakt.
ShopReels is een app die van Shopify-producten automatisch korte video's maakt (met voice-over en muziek)
en die op Instagram, TikTok en YouTube plaatst. Je kunt het 7 dagen gratis proberen, inclusief de eerste 3 video's.

Marcels methode: "Verkopen blijft mensenwerk". Dat betekent:
- Schrijf als een mens tegen een mens: kort, warm, eerlijk, geen reclametaal, geen overdreven complimenten.
- Laat zien dat je echt naar DEZE winkel hebt gekeken: noem één of twee concrete dingen van hun site
  (een product, hun verhaal, hun stijl). Verzin nooit iets wat niet in de tekst staat.
- Maak één duidelijke koppeling tussen hun winkel en video (bijvoorbeeld: een product dat je moet zien bewegen,
  een verhaal dat in beeld beter overkomt).
- Geen kritiek op hun website. Geen druk, geen nep-urgentie, geen beloftes over omzet.
- Eindig met een lichte, open vraag of uitnodiging.

Regels die altijd gelden:
- Gebruik geen namen van medewerkers of eigenaren en geen privégegevens. Spreek de winkel aan, niet een persoon.
- Maximaal ongeveer 120 woorden in de mail zelf.
- Schrijf de mail in de gevraagde taal. Het rapport schrijf je altijd in het Nederlands.
- Zet de link precies zoals gegeven in de mail.
- Eindig de mail met de groet en de naam van de afzender, zonder handtekening eronder.

Antwoord ALLEEN met geldige JSON in deze vorm:
{"rapport": "3 tot 5 korte zinnen in het Nederlands: wat voor winkel, wat valt op, waarom video past, welk haakje je gebruikt",
 "onderwerp": "korte, persoonlijke onderwerpregel",
 "mail": "de volledige mailtekst"}"""


def _vraag_ai(api_key, prompt, max_tokens=1200):
    r = requests.post(
        API_URL,
        headers={"x-api-key": api_key, "anthropic-version": "2023-06-01",
                 "content-type": "application/json"},
        json={"model": MODEL, "max_tokens": max_tokens, "system": SYSTEEM,
              "messages": [{"role": "user", "content": prompt}]},
        timeout=90,
    )
    if r.status_code != 200:
        raise RuntimeError(f"AI gaf code {r.status_code}: {r.text[:200]}")
    data = r.json()
    return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")


def _lees_json(tekst):
    m = re.search(r"\{.*\}", tekst, re.S)
    if not m:
        raise ValueError("Geen JSON in het antwoord")
    data = json.loads(m.group(0))
    for veld in ("rapport", "onderwerp", "mail"):
        if not isinstance(data.get(veld), str) or not data[veld].strip():
            raise ValueError(f"Veld '{veld}' ontbreekt")
    return data


def schrijf_persoonlijke_mail(lead, afzender, link=oc.SHOPREELS_LINK, api_key=None, sessie=None,
                              ai=None):
    """
    Geeft dict {rapport, onderwerp, tekst} terug, of None met een reden in lead['detective'].
    ai: optionele functie(prompt) -> tekst, voor testen zonder echte AI.
    """
    api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key and ai is None:
        lead["detective"] = "Geen AI-sleutel: standaardmail gebruikt"
        return None

    tekst, reden = verzamel_winkeltekst(lead["website"], sessie)
    if tekst is None:
        lead["detective"] = reden + ": standaardmail gebruikt"
        return None

    taal = lead.get("taal", "EN")
    naam = lead.get("winkelnaam") or lead.get("domein")
    if oc.is_rare_naam(naam):
        naam = lead.get("domein")
    prompt = (
        f"Winkel: {naam}\nWebsite: {lead['website']}\nTaal van de mail: {TAALNAAM.get(taal, 'Engels')}\n"
        f"Afzender (naam onder de mail): {afzender}\nLink naar ShopReels: {link}\n\n"
        f"Openbare tekst van hun eigen website:\n\"\"\"\n{tekst}\n\"\"\""
    )
    try:
        antwoord = ai(prompt) if ai else _vraag_ai(api_key, prompt)
        data = _lees_json(antwoord)
    except Exception as ex:  # noqa: BLE001 – elke fout = terugvallen op de standaardmail
        lead["detective"] = f"AI-fout ({str(ex)[:80]}): standaardmail gebruikt"
        return None

    mail = data["mail"].strip()
    if link not in mail:
        mail += f"\n\n{link}"
    afmelden = oc.AFMELD_ZIN.get(taal, oc.AFMELD_ZIN["EN"]) + "\n" + oc.afmeld_link()
    lead["detective"] = "Persoonlijke mail geschreven"
    return {"rapport": data["rapport"].strip(), "onderwerp": data["onderwerp"].strip(),
            "tekst": f"{mail}\n\n--\n{afmelden}"}


def maak_beste_mail(lead, afzender, link=oc.SHOPREELS_LINK, api_key=None):
    """Persoonlijke mail als het kan, anders de standaardmail. Geeft (onderwerp, tekst, rapport)."""
    persoonlijk = schrijf_persoonlijke_mail(lead, afzender, link, api_key)
    if persoonlijk:
        return persoonlijk["onderwerp"], persoonlijk["tekst"], persoonlijk["rapport"]
    onderwerp, tekst = oc.maak_mail(lead.get("taal", "EN"), lead.get("winkelnaam", ""), afzender, link)
    return onderwerp, tekst, ""
