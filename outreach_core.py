"""
Outreach-motor voor ShopReels.

Hier zit al het echte werk, zodat de Streamlit-app (app.py) en de dagelijkse
automatische run (dagelijks.py) precies hetzelfde doen:

1. Winkels zoeken via Google (SerpApi).
2. Controleren of het echt een actieve Shopify-winkel is.
3. Een ECHT e-mailadres op de site van de winkel zelf zoeken.
   Wordt er geen adres gevonden, dan wordt de winkel overgeslagen.
   Er worden nooit meer adressen verzonnen.
4. In de Gmail-mailbox kijken wie we al gemaild hebben of wie ons gemaild
   heeft (ook afmeldingen), zodat niemand twee keer een mail krijgt.
5. De mail versturen, met een afmeldregel.
"""

import email.utils
import html
import imaplib
import json
import random
import re
import smtplib
import time
from datetime import datetime, timedelta
from email.header import decode_header, make_header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from urllib.parse import urljoin, urlparse

import requests

SHOPREELS_LINK = "https://shopreelsapp.com"

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

# Markten: Google-land (gl), Google-taal (hl) en de taal van de mail.
MARKTEN = {
    "NL": {"naam": "Nederland", "gl": "nl", "hl": "nl", "taal": "NL"},
    "BE": {"naam": "België (Vlaanderen)", "gl": "be", "hl": "nl", "taal": "NL"},
    "US": {"naam": "Verenigde Staten", "gl": "us", "hl": "en", "taal": "EN"},
    "UK": {"naam": "Verenigd Koninkrijk", "gl": "uk", "hl": "en", "taal": "EN"},
    "DE": {"naam": "Duitsland", "gl": "de", "hl": "de", "taal": "DE"},
    "ES": {"naam": "Spanje", "gl": "es", "hl": "es", "taal": "ES"},
}

# Grote platforms en marktplaatsen: dat zijn geen kleine winkels.
OVERSLAAN_DOMEINEN = {
    "shopify.com", "apps.shopify.com", "amazon.com", "amazon.nl",
    "amazon.de", "amazon.co.uk", "etsy.com", "ebay.com", "bol.com", "zalando.nl",
    "facebook.com", "instagram.com", "pinterest.com", "youtube.com", "tiktok.com",
    "reddit.com", "google.com", "linkedin.com", "wikipedia.org", "trustpilot.com", "marktplaats.nl",
}

# Adressen die je vaak in websitecode vindt maar die niet van de winkel zijn.
NEP_ADRES_DELEN = (
    "example.", "domain.com", "email.com", "yourstore", "yourdomain", "sentry",
    "wixpress", "shopify.com", "@2x", "u003e", "noreply", "no-reply", "donotreply",
    "privacy@shopify", "user@", "name@", "test@", "@sentry", "jquery", "@email",
)
AFBEELDING_EINDES = (".png", ".jpg", ".jpeg", ".webp", ".svg", ".gif", ".avif", ".css", ".js")

# Gratis maildiensten: daar mag je niet op domein dubbelchecken.
GRATIS_MAIL = {
    "gmail.com", "googlemail.com", "hotmail.com", "outlook.com", "live.com", "live.nl",
    "hotmail.nl", "yahoo.com", "icloud.com", "me.com", "ziggo.nl", "kpnmail.nl",
    "telenet.be", "proton.me", "protonmail.com", "gmx.de", "web.de", "aol.com",
}

# Pagina's op een Shopify-winkel waar meestal een e-mailadres op staat.
CONTACT_PAGINAS = [
    "/",
    "/pages/contact",
    "/pages/contact-us",
    "/pages/kontakt",
    "/pages/contacto",
    "/policies/contact-information",
    "/policies/refund-policy",
    "/policies/terms-of-service",
    "/pages/about-us",
    "/pages/over-ons",
]

EMAIL_REGEX = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")


# ---------------------------------------------------------------------------
# Mailteksten
# ---------------------------------------------------------------------------

TEMPLATES = {
    "NL": {
        "onderwerp": "Een idee voor {naam}",
        "bericht": (
            "Hoi,\n\n"
            "Ik kwam jullie webshop {naam} tegen en vond het een mooi assortiment.\n\n"
            "Wat ik bij veel winkels zie: mensen kopen bij winkels die ze vaak voorbij zien komen. "
            "Korte video's op Instagram, TikTok en YouTube zorgen daarvoor, maar elke dag video's "
            "maken kost veel tijd.\n\n"
            "Daarom heb ik ShopReels gemaakt. Die app maakt van je Shopify-producten automatisch "
            "korte video's met voice-over en muziek, en plaatst ze voor je op je kanalen.\n\n"
            "Je kunt het 7 dagen gratis proberen, inclusief je eerste 3 video's:\n"
            "{link}\n\n"
            "Heb je vragen? Antwoord gewoon op deze mail, ik lees alles zelf.\n\n"
            "Groet,\n"
            "{afzender}\n\n"
            "--\n"
            "{afmelden}"
        ),
    },
    "EN": {
        "onderwerp": "An idea for {naam}",
        "bericht": (
            "Hi,\n\n"
            "I came across your store {naam} and really liked your products.\n\n"
            "Something I see with a lot of stores: shoppers buy from the stores they see often. "
            "Short videos on Instagram, TikTok and YouTube make that happen, but making videos "
            "every day takes a lot of time.\n\n"
            "That's why I built ShopReels. It turns your Shopify products into short videos with "
            "voice-over and music, and posts them to your channels automatically.\n\n"
            "You can try it free for 7 days, including your first 3 videos:\n"
            "{link}\n\n"
            "Any questions? Just reply to this email, I read everything myself.\n\n"
            "Best,\n"
            "{afzender}\n\n"
            "--\n"
            "{afmelden}"
        ),
    },
    "DE": {
        "onderwerp": "Eine Idee für {naam}",
        "bericht": (
            "Hallo,\n\n"
            "ich bin auf Ihren Shop {naam} gestoßen und finde Ihr Sortiment wirklich schön.\n\n"
            "Was ich bei vielen Shops sehe: Kunden kaufen bei Shops, die sie oft sehen. "
            "Kurze Videos auf Instagram, TikTok und YouTube sorgen dafür, aber jeden Tag Videos "
            "zu machen kostet viel Zeit.\n\n"
            "Deshalb habe ich ShopReels gebaut. Die App macht aus Ihren Shopify-Produkten "
            "automatisch kurze Videos mit Sprecher und Musik und veröffentlicht sie auf Ihren Kanälen.\n\n"
            "Sie können es 7 Tage kostenlos testen, inklusive Ihrer ersten 3 Videos:\n"
            "{link}\n\n"
            "Fragen? Antworten Sie einfach auf diese E-Mail, ich lese alles selbst.\n\n"
            "Viele Grüße\n"
            "{afzender}\n\n"
            "--\n"
            "{afmelden}"
        ),
    },
    "ES": {
        "onderwerp": "Una idea para {naam}",
        "bericht": (
            "Hola,\n\n"
            "He visto vuestra tienda {naam} y me han gustado mucho vuestros productos.\n\n"
            "Algo que veo en muchas tiendas: la gente compra en las tiendas que ve a menudo. "
            "Los vídeos cortos en Instagram, TikTok y YouTube lo consiguen, pero hacer vídeos "
            "cada día lleva mucho tiempo.\n\n"
            "Por eso he creado ShopReels. La app convierte automáticamente tus productos de Shopify "
            "en vídeos cortos con voz y música, y los publica en tus canales.\n\n"
            "Puedes probarla gratis 7 días, incluidos tus 3 primeros vídeos:\n"
            "{link}\n\n"
            "¿Alguna pregunta? Responde a este correo, lo leo todo yo mismo.\n\n"
            "Un saludo,\n"
            "{afzender}\n\n"
            "--\n"
            "{afmelden}"
        ),
    },
}


AFMELD_ZIN = {
    "NL": "Is deze mail niet voor jou bedoeld? Tik hier, dan krijg je nooit meer een mail van mij.",
    "EN": "Not relevant for you? Tap here and you'll never hear from me again.",
    "DE": "Nicht relevant für Sie? Tippen Sie hier, dann bekommen Sie keine E-Mails mehr von mir.",
    "ES": "¿No te interesa? Toca aquí y no volverás a recibir correos míos.",
}
AFMELD_ADRES = "info@shopreelsapp.com"


def afmeld_link(adres=AFMELD_ADRES):
    return f"mailto:{adres}?subject=Afmelden%20%2F%20Unsubscribe&body=Please%20remove%20me%20from%20your%20list."


def maak_html(tekst):
    """Maakt van de platte mailtekst een nette HTML-versie met klikbare links.
    Een regel gevolgd door een regel die met 'mailto:' begint wordt één klikbare link."""
    regels = tekst.split("\n")
    uit, i = [], 0
    while i < len(regels):
        r = regels[i]
        if i + 1 < len(regels) and regels[i + 1].startswith("mailto:"):
            uit.append(f'<a href="{html.escape(regels[i + 1])}" style="color:#888">{html.escape(r)}</a>')
            i += 2
            continue
        e = html.escape(r)
        e = re.sub(r"(https?://[^\s<]+)", r'<a href="\1">\1</a>', e)
        uit.append(e)
        i += 1
    lichaam = "<br>\n".join(uit).replace("<br>\n--<br>\n", '<br>\n<hr style="border:none;border-top:1px solid #ddd">\n')
    return f'<div style="font-family:Arial,sans-serif;font-size:15px;line-height:1.5;color:#222">{lichaam}</div>'


JE_WINKEL = {"NL": "jullie webshop", "EN": "your store", "DE": "Ihren Shop", "ES": "vuestra tienda"}


def is_rare_naam(naam):
    """Namen als '518Ac7 2' of 'Zz1r4h 50' zijn automatische Shopify-codes, geen echte winkelnaam."""
    n = (naam or "").replace(" ", "").replace("-", "")
    if not n:
        return True
    cijfers = sum(c.isdigit() for c in n)
    return cijfers >= 2 and cijfers / len(n) > 0.2


def maak_mail(taal, winkelnaam, afzender, link=SHOPREELS_LINK):
    """Geeft (onderwerp, tekst) terug voor een winkel."""
    tpl = dict(TEMPLATES.get(taal, TEMPLATES["EN"]))
    if is_rare_naam(winkelnaam):
        # Geen echte naam bekend: dan gewoon "jullie webshop" / "your store".
        for oud in ("jullie webshop {naam}", "your store {naam}", "Ihren Shop {naam}", "vuestra tienda {naam}"):
            tpl["bericht"] = tpl["bericht"].replace(oud, "{naam}")
        winkelnaam = JE_WINKEL.get(taal, "your store")
    onderwerp = tpl["onderwerp"].format(naam=winkelnaam)
    afmelden = AFMELD_ZIN.get(taal, AFMELD_ZIN["EN"]) + "\n" + afmeld_link()
    tekst = tpl["bericht"].format(naam=winkelnaam, link=link, afzender=afzender, afmelden=afmelden)
    return onderwerp, tekst


# ---------------------------------------------------------------------------
# Hulpjes
# ---------------------------------------------------------------------------

def domein_van(url):
    host = urlparse(url if "://" in url else "https://" + url).netloc.lower()
    host = host.split(":")[0]
    return host[4:] if host.startswith("www.") else host


def echte_link(item):
    """
    Google geeft soms een doorverwijslink (google.com/url?q=...) in plaats van het
    echte adres. Dit haalt het echte adres van de winkel eruit.
    """
    from urllib.parse import parse_qs
    kandidaten = [item.get("link", ""), item.get("redirect_link", ""), item.get("displayed_link", "")]
    for k in kandidaten:
        if not k:
            continue
        k = k.split(" › ")[0].split(" ")[0].strip()
        if "://" not in k:
            k = "https://" + k
        dom = domein_van(k)
        if not dom or not re.fullmatch(r"[a-z0-9.\-]+\.[a-z]{2,}", dom):
            continue
        if dom.startswith("google.") or ".google." in dom:
            qs = parse_qs(urlparse(k).query)
            for sleutel in ("q", "url", "u", "adurl"):
                for w in qs.get(sleutel, []):
                    if w.startswith("http") and not domein_van(w).startswith("google."):
                        return w
            continue
        return k
    return ""


def basis_url(url):
    p = urlparse(url if "://" in url else "https://" + url)
    return f"https://{p.netloc}"


def is_overslaan_domein(domein):
    return any(domein == d or domein.endswith("." + d) for d in OVERSLAAN_DOMEINEN)


def _sessie():
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "en,nl;q=0.8"})
    return s


import threading

_DRAAD = threading.local()


class _LaatsteFout:
    def __getitem__(self, _):
        return getattr(_DRAAD, "fout", "")

    def __setitem__(self, _, waarde):
        _DRAAD.fout = waarde


LAATSTE_FOUT = _LaatsteFout()


def _haal(sessie, url, timeout=12):
    try:
        r = sessie.get(url, timeout=timeout, allow_redirects=True)
        if r.status_code == 200:
            return r
        LAATSTE_FOUT["tekst"] = f"code {r.status_code}"
    except requests.Timeout:
        LAATSTE_FOUT["tekst"] = "duurde te lang"
    except requests.RequestException as ex:
        LAATSTE_FOUT["tekst"] = type(ex).__name__
    return None


SHOPIFY_KENMERKEN = ("cdn.shopify.com", "/cdn/shop/", "Shopify.theme", "Shopify.shop",
                     "window.Shopify", "shopify-section", "shopify-features")


# ---------------------------------------------------------------------------
# E-mailadressen uit een pagina halen
# ---------------------------------------------------------------------------

def _cloudflare_decode(code):
    """Cloudflare verstopt adressen soms als 'data-cfemail'. Dit pakt ze weer uit."""
    try:
        sleutel = int(code[:2], 16)
        return "".join(chr(int(code[i:i + 2], 16) ^ sleutel) for i in range(2, len(code), 2))
    except ValueError:
        return ""


def is_bruikbaar_adres(adres):
    a = adres.lower().strip(".")
    if len(a) > 80 or a.count("@") != 1:
        return False
    if a.endswith(AFBEELDING_EINDES):
        return False
    if any(deel in a for deel in NEP_ADRES_DELEN):
        return False
    lokaal, dom = a.split("@")
    if not lokaal or "." not in dom:
        return False
    # Rare lange codes (bijv. van trackers) overslaan.
    if re.fullmatch(r"[0-9a-f]{16,}", lokaal):
        return False
    return True


def adressen_uit_html(tekst):
    """Alle bruikbare e-mailadressen uit een stuk HTML."""
    gevonden = []
    tekst = html.unescape(tekst or "")
    for code in re.findall(r'data-cfemail="([0-9a-fA-F]+)"', tekst):
        gevonden.append(_cloudflare_decode(code))
    for adres in re.findall(r"mailto:([^\"'?>\s]+)", tekst, flags=re.I):
        gevonden.append(requests.utils.unquote(adres))
    gevonden.extend(EMAIL_REGEX.findall(tekst))

    schoon = []
    for a in gevonden:
        a = a.strip().strip(".,;:").lower()
        if is_bruikbaar_adres(a) and a not in schoon:
            schoon.append(a)
    return schoon


def kies_beste_adres(adressen, winkeldomein):
    """Liefst een adres op het domein van de winkel zelf, en dan info@/hello@/contact@."""
    if not adressen:
        return None
    voorkeur = ("info", "hello", "hallo", "hi", "contact", "kontakt", "shop", "store",
                "support", "service", "klantenservice", "sales", "hola")

    def score(a):
        lokaal, dom = a.split("@")
        s = 0
        kern = winkeldomein.split(".")[0]
        if dom == winkeldomein or dom.endswith("." + winkeldomein) or (kern and kern in dom):
            s += 10
        elif dom in GRATIS_MAIL:
            s += 4
        if lokaal in voorkeur:
            s += 3 + (len(voorkeur) - voorkeur.index(lokaal)) / 100
        if any(w in lokaal for w in ("privacy", "legal", "gdpr", "dpo", "abuse", "jobs", "careers")):
            s -= 5
        return s

    beste = max(adressen, key=score)
    return beste if score(beste) > 0 else None


# ---------------------------------------------------------------------------
# Winkel bekijken: is het Shopify, heeft hij producten, wat is het adres?
# ---------------------------------------------------------------------------

def winkelnaam_uit_html(tekst, domein):
    m = re.search(r'<meta[^>]+property=["\']og:site_name["\'][^>]+content=["\']([^"\']+)', tekst or "", re.I)
    if not m:
        m = re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:site_name', tekst or "", re.I)
    if m:
        naam = html.unescape(m.group(1)).strip()
    else:
        t = re.search(r"<title[^>]*>(.*?)</title>", tekst or "", re.I | re.S)
        naam = html.unescape(t.group(1)).strip() if t else ""
        naam = re.split(r"\s[\-|–—:]\s", naam)[-1].strip() if naam else ""
    if not naam or len(naam) > 40:
        naam = domein.split(".")[0].replace("-", " ").title()
    return naam


# Woorden die laten zien dat het geen winkel is maar een dienstverlener voor winkels.
GEEN_WINKEL_WOORDEN = (
    "shopify theme", "shopify themes", "premium theme", "theme store", "themeforest",
    "shopify agency", "shopify expert", "shopify partner", "shopify developer",
    "web design agency", "ecommerce agency", "e-commerce agency", "development agency",
    "dropshipping course", "dropship course", "shopify apps", "app for shopify",
    "website template", "templates", "theme demo", "webdesign", "webbureau",
)
GEEN_WINKEL_EXTENSIES = (".dev", ".agency", ".io", ".app", ".tech", ".digital")

# Extra woorden per branche, zodat bijv. een sieradenwinkel die "necklace" zegt ook telt.
BRANCHE_WOORDEN = {
    "jewelry": ["jewelry", "jewellery", "necklace", "earring", "bracelet", "ring", "pendant"],
    "jewellery": ["jewelry", "jewellery", "necklace", "earring", "bracelet", "ring"],
    "sieraden": ["sieraden", "ketting", "oorbel", "armband", "ring", "hanger", "jewelry"],
    "schmuck": ["schmuck", "kette", "ohrring", "armband", "ring"],
    "joyería": ["joyería", "joya", "collar", "pendiente", "pulsera", "anillo"],
    "clothing": ["clothing", "dress", "tops", "shirt", "jeans", "apparel"],
    "kleding": ["kleding", "jurk", "broek", "shirt", "trui", "jas"],
    "home decor": ["decor", "home", "vase", "pillow", "cushion", "candle", "wall art"],
    "woonaccessoires": ["woon", "interieur", "vaas", "kussen", "kaars", "decoratie"],
    "candles": ["candle", "wax", "wick"],
    "kaarsen": ["kaars", "kaarsen", "geurkaars"],
}


def branche_woorden(niche):
    niche = (niche or "").lower().strip()
    woorden = set()
    for sleutel, lijst in BRANCHE_WOORDEN.items():
        if sleutel in niche:
            woorden.update(lijst)
    woorden.update(w for w in re.split(r"[\s,/']+", niche) if len(w) > 3)
    return woorden


def is_dienstverlener(domein, homepage_tekst):
    if domein.endswith(GEEN_WINKEL_EXTENSIES):
        return True
    kop = " ".join(re.findall(r"<title[^>]*>(.*?)</title>", homepage_tekst or "", re.I | re.S))
    kop += " " + " ".join(re.findall(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']*)',
                                     homepage_tekst or "", re.I))
    kop = html.unescape(kop).lower()
    return any(w in kop for w in GEEN_WINKEL_WOORDEN)


def past_bij_branche(niche, homepage_tekst, producten_json):
    woorden = branche_woorden(niche)
    if not woorden:
        return True
    tekst = (homepage_tekst or "").lower()
    for p in producten_json or []:
        tekst += " " + " ".join(str(p.get(k, "")) for k in ("title", "product_type", "tags")).lower()
    return any(re.search(r"\b" + re.escape(w), tekst) for w in woorden)


TLD_TAAL = {".nl": "NL", ".be": "NL", ".de": "DE", ".at": "DE", ".es": "ES",
            ".co.uk": "EN", ".uk": "EN", ".us": "EN", ".com.au": "EN", ".ca": "EN", ".ie": "EN"}


def taal_van_winkel(domein, homepage_tekst):
    """NL, EN, DE, ES of iets anders (bijv. FR). Eerst de taal die de site zelf opgeeft."""
    m = re.search(r"<html[^>]*\blang=[\"']?([a-zA-Z]{2})", homepage_tekst or "", re.I)
    if m:
        return m.group(1).upper()
    for tld, taal in TLD_TAAL.items():
        if domein.endswith(tld):
            return taal
    return "EN"


# Markt-code in de app -> landcode die Shopify gebruikt
MARKT_NAAR_LAND = {"NL": "NL", "BE": "BE", "US": "US", "UK": "GB", "DE": "DE", "ES": "ES"}
LAND_NAAR_MARKT = {v: k for k, v in MARKT_NAAR_LAND.items()}


def land_van_winkel(sessie, basis, domein):
    """Land waar de winkel gevestigd is, uit het openbare Shopify-bestandje /meta.json."""
    r = _haal(sessie, basis + "/meta.json")
    if r is not None:
        try:
            land = (r.json().get("country") or "").upper()
            if land:
                return land
        except ValueError:
            pass
    for tld, land in ((".nl", "NL"), (".be", "BE"), (".de", "DE"), (".es", "ES"), (".co.uk", "GB"), (".uk", "GB")):
        if domein.endswith(tld):
            return land
    return ""


def bekijk_winkel(url, sessie=None, niche=None, talen=None, landen=None):
    """
    Bezoekt een winkel en geeft een dict terug:
    domein, website, winkelnaam, shopify (bool), producten (int of None), email, reden
    """
    sessie = sessie or _sessie()
    basis = basis_url(url)
    domein = domein_van(url)
    info = {"domein": domein, "website": basis, "winkelnaam": domein, "shopify": False,
            "producten": None, "email": None, "reden": ""}

    home = _haal(sessie, basis + "/")
    if home is None:
        info["reden"] = f"Site niet bereikbaar ({LAATSTE_FOUT['tekst']})"
        return info
    if "/password" in home.url:
        info["reden"] = "Winkel nog dicht (wachtwoord)"
        return info
    # Volg een eventuele doorverwijzing naar het echte domein.
    echt = domein_van(home.url)
    if echt and echt != domein:
        domein = echt
        basis = basis_url(home.url)
        info.update({"domein": domein, "website": basis})
    if is_overslaan_domein(domein):
        info["reden"] = "Groot platform, geen kleine winkel"
        return info

    tekst = home.text
    info["winkelnaam"] = winkelnaam_uit_html(tekst, domein)
    info["taal"] = taal_van_winkel(domein, tekst)
    if landen:
        land = land_van_winkel(sessie, basis, domein)
        info["land"] = land
        markt = LAND_NAAR_MARKT.get(land)
        if not markt or markt not in landen:
            info["reden"] = f"Ander land ({land or 'onbekend'})"
            return info
        info["markt"] = markt
        verwacht = MARKTEN[markt]["taal"]
        if markt == "BE" and info["taal"] not in ("NL",):
            info["reden"] = f"Belgische winkel, maar niet in het Nederlands ({info['taal']})"
            return info
        info["taal"] = verwacht
    if talen and info["taal"] not in talen:
        info["reden"] = f"Andere taal ({info['taal']})"
        return info
    koppen = {k.lower() for k in home.headers.keys()}
    info["shopify"] = any(k in tekst for k in SHOPIFY_KENMERKEN) or \
        bool(koppen & {"x-shopid", "x-shopify-stage", "x-sorting-hat-shopid", "x-storefront-renderer-rendered"}) or \
        "shopify" in home.headers.get("powered-by", "").lower()

    # Aantal producten (openbare Shopify-lijst). Een lege winkel is geen klant.
    if is_dienstverlener(domein, tekst):
        info["reden"] = "Geen winkel (thema-maker, bureau of dienstverlener)"
        return info

    producten = None
    pj = _haal(sessie, basis + "/products.json?limit=30")
    if pj is not None:
        try:
            producten = pj.json().get("products")
            if isinstance(producten, list):
                info["shopify"] = True
                info["producten"] = len(producten)
        except ValueError:
            pass

    if not info["shopify"]:
        info["reden"] = "Geen Shopify-winkel"
        return info
    if info["producten"] is not None and info["producten"] < 3:
        info["reden"] = "Te weinig producten"
        return info
    if niche and not past_bij_branche(niche, tekst, producten if isinstance(producten, list) else []):
        info["reden"] = "Past niet bij de branche"
        return info

    adressen = adressen_uit_html(tekst)
    for pad in CONTACT_PAGINAS[1:]:
        if kies_beste_adres(adressen, domein) and any(a.split("@")[1] == domein for a in adressen):
            break
        r = _haal(sessie, basis + pad)
        if r is not None:
            for a in adressen_uit_html(r.text):
                if a not in adressen:
                    adressen.append(a)
    info["email"] = kies_beste_adres(adressen, domein)
    if not info["email"]:
        info["reden"] = "Geen e-mailadres gevonden"
    return info


# ---------------------------------------------------------------------------
# Zoeken via SerpApi
# ---------------------------------------------------------------------------

def zoek_websites(api_key, niche, markt="US", pagina=0, log=None):
    """
    Zoekt in Google naar Shopify-winkels in een branche.
    Geeft (lijst met website-urls, foutmelding of None) terug. Kost 1 zoekopdracht.
    """
    m = MARKTEN.get(markt, MARKTEN["US"])
    # Drie manieren van zoeken, om de beurt. Elke winkel wordt daarna toch
    # gecontroleerd, dus een zoekresultaat dat geen Shopify is valt vanzelf af.
    varianten = [
        'site:myshopify.com {niche}',
        '{niche} inurl:"/collections/all"',
        '{niche} store "powered by shopify" -blog -how -apps',
    ]
    vraag = varianten[pagina % len(varianten)].format(niche=niche)
    params = {
        "engine": "google",
        "q": vraag,
        "api_key": api_key,
        "gl": m["gl"],
        "hl": m["hl"],
        "start": (pagina // len(varianten)) * 10,
    }
    try:
        r = requests.get("https://serpapi.com/search.json", params=params, timeout=30)
        data = r.json()
    except Exception as ex:  # netwerk of geen JSON
        return [], f"Zoeken mislukt: {ex}"
    if "error" in data:
        if "hasn't returned any results" in data["error"]:
            if log:
                log(f"Google: '{vraag}' -> 0 resultaten")
            return [], None
        return [], data["error"]

    urls, gezien = [], set()
    for item in data.get("organic_results", []):
        link = echte_link(item)
        dom = domein_van(link) if link else ""
        if not dom or dom in gezien or is_overslaan_domein(dom):
            continue
        gezien.add(dom)
        urls.append(basis_url(link))
    if log:
        log(f"Google: '{vraag}' -> {len(data.get('organic_results', []))} resultaten, "
            f"{len(urls)} bruikbare websites")
        if not urls and data.get("organic_results"):
            eerste = data["organic_results"][0]
            log(f"  (voorbeeld: link={eerste.get('link')} | getoond={eerste.get('displayed_link')})")
    return urls, None


# ---------------------------------------------------------------------------
# Mailbox: wie hebben we al gemaild, wie heeft ons gemaild?
# ---------------------------------------------------------------------------

def _adressen_uit_header(waarde):
    try:
        waarde = str(make_header(decode_header(waarde)))
    except Exception:
        pass
    return [a.lower() for _, a in email.utils.getaddresses([waarde]) if "@" in a]


def _map_met_vlag(imap, vlag):
    typ, mappen = imap.list()
    if typ != "OK":
        return None
    for regel in mappen:
        tekst = regel.decode(errors="ignore")
        if vlag in tekst:
            m = re.search(r'"([^"]+)"\s*$', tekst) or re.search(r"(\S+)\s*$", tekst)
            if m:
                return m.group(1)
    return None


def _verzamel(imap, mapnaam, veld, sinds):
    adressen = set()
    if not mapnaam:
        return adressen
    typ, _ = imap.select(f'"{mapnaam}"', readonly=True)
    if typ != "OK":
        return adressen
    typ, data = imap.search(None, "SINCE", sinds.strftime("%d-%b-%Y"))
    if typ != "OK" or not data or not data[0]:
        return adressen
    nummers = data[0].split()
    for i in range(0, len(nummers), 200):
        stuk = b",".join(nummers[i:i + 200]).decode()
        typ, resp = imap.fetch(stuk, f"(BODY.PEEK[HEADER.FIELDS ({veld})])")
        if typ != "OK":
            continue
        for deel in resp:
            if isinstance(deel, tuple):
                kop = deel[1].decode(errors="ignore")
                kop = re.sub(r"^\s*" + veld + r":\s*", "", kop, flags=re.I).replace("\r\n", " ")
                adressen.update(_adressen_uit_header(kop))
    return adressen


def bekende_contacten(smtp_user, wachtwoord, imap_server="imap.gmail.com", maanden=24):
    """
    Kijkt in de mailbox (zelfde app-wachtwoord als voor versturen):
    - Verzonden: iedereen die we al gemaild hebben
    - Inbox: iedereen die ons gemaild heeft (ook afmeldingen en antwoorden)
    Geeft (set met adressen, set met domeinen, foutmelding of None) terug.
    """
    sinds = datetime.now() - timedelta(days=30 * maanden)
    try:
        imap = imaplib.IMAP4_SSL(imap_server, 993, timeout=30)
        imap.login(smtp_user.strip(), wachtwoord.replace(" ", "").strip())
    except Exception as ex:
        return set(), set(), f"Kon de mailbox niet openen: {ex}"
    try:
        verzonden_map = _map_met_vlag(imap, "\\Sent") or "[Gmail]/Sent Mail"
        adressen = _verzamel(imap, verzonden_map, "TO", sinds)
        adressen |= _verzamel(imap, verzonden_map, "CC", sinds)
        adressen |= _verzamel(imap, "INBOX", "FROM", sinds)
    finally:
        try:
            imap.logout()
        except Exception:
            pass
    eigen = smtp_user.lower().strip()
    adressen.discard(eigen)
    domeinen = {a.split("@")[1] for a in adressen
                if a.split("@")[1] not in GRATIS_MAIL and a.split("@")[1] != eigen.split("@")[1]}
    return adressen, domeinen, None


AFMELD_WOORDEN = ("unsubscribe", "afmelden", "uitschrijven", "remove me", "no thanks", "not interested",
                  "geen interesse", "abmelden", "kein interesse", "darse de baja", "no me interesa")


def _tekst_uit_bericht(bericht):
    """Haalt de leesbare tekst uit een mail (zonder het geciteerde origineel)."""
    tekst = ""
    delen = bericht.walk() if bericht.is_multipart() else [bericht]
    for deel in delen:
        if deel.get_content_type() == "text/plain" and not deel.get("Content-Disposition", "").startswith("attachment"):
            try:
                tekst = deel.get_payload(decode=True).decode(deel.get_content_charset() or "utf-8", errors="ignore")
                break
            except Exception:
                pass
    if not tekst:
        for deel in delen:
            if deel.get_content_type() == "text/html":
                try:
                    ruw = deel.get_payload(decode=True).decode(deel.get_content_charset() or "utf-8", errors="ignore")
                    tekst = re.sub(r"<[^>]+>", " ", ruw)
                    break
                except Exception:
                    pass
    regels = []
    for regel in tekst.splitlines():
        r = regel.strip()
        if r.startswith(">") or re.match(r"^(On .+wrote:|Op .+schreef|Am .+schrieb|El .+escribió|-----Original|From:|Van:)", r):
            break
        regels.append(r)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(regels)).strip()


def zoek_antwoorden(smtp_user, wachtwoord, imap_server="imap.gmail.com", dagen=4, maanden=24):
    """
    Zoekt in de inbox naar antwoorden van winkels die we eerder gemaild hebben.
    Geeft (lijst met antwoorden, foutmelding of None) terug.
    Elk antwoord: {id, van, naam, domein, onderwerp, datum, tekst, afmelding}
    """
    import email as _email
    sinds = datetime.now() - timedelta(days=30 * maanden)
    try:
        imap = imaplib.IMAP4_SSL(imap_server, 993, timeout=30)
        imap.login(smtp_user.strip(), wachtwoord.replace(" ", "").strip())
    except Exception as ex:
        return [], f"Kon de mailbox niet openen: {ex}"
    antwoorden = []
    eigen = smtp_user.lower().strip()
    try:
        verzonden_map = _map_met_vlag(imap, "\\Sent") or "[Gmail]/Sent Mail"
        gemaild = _verzamel(imap, verzonden_map, "TO", sinds)
        gemaild.discard(eigen)
        gemaild_dom = {a.split("@")[1] for a in gemaild if "@" in a and a.split("@")[1] not in GRATIS_MAIL
                       and a.split("@")[1] != eigen.split("@")[1]}
        typ, _ = imap.select("INBOX", readonly=True)
        if typ != "OK":
            return [], "Inbox niet gevonden"
        recent = (datetime.now() - timedelta(days=dagen)).strftime("%d-%b-%Y")
        typ, data = imap.search(None, "SINCE", recent)
        nummers = data[0].split() if typ == "OK" and data and data[0] else []
        for nr in nummers:
            typ, resp = imap.fetch(nr, "(BODY.PEEK[])")
            if typ != "OK" or not resp or not isinstance(resp[0], tuple):
                continue
            bericht = _email.message_from_bytes(resp[0][1])
            naam, adres = email.utils.parseaddr(str(make_header(decode_header(bericht.get("From", "")))))
            adres = adres.lower()
            dom = adres.split("@")[1] if "@" in adres else ""
            if not adres or adres == eigen or not (adres in gemaild or dom in gemaild_dom):
                continue
            onderwerp = str(make_header(decode_header(bericht.get("Subject", ""))))
            tekst = _tekst_uit_bericht(bericht)
            try:
                datum = email.utils.parsedate_to_datetime(bericht.get("Date")).strftime("%d-%m-%Y %H:%M")
            except Exception:
                datum = ""
            klein = (onderwerp + " " + tekst[:400]).lower()
            antwoorden.append({
                "id": (bericht.get("Message-ID") or f"{adres}-{datum}").strip(),
                "van": adres, "naam": naam, "domein": dom, "onderwerp": onderwerp, "datum": datum,
                "tekst": tekst[:1500],
                "afmelding": any(w in klein for w in AFMELD_WOORDEN),
            })
    except Exception as ex:
        return antwoorden, f"Antwoorden zoeken mislukt: {ex}"
    finally:
        try:
            imap.logout()
        except Exception:
            pass
    return antwoorden, None


def al_bekend(adres, domein, bekende_adressen, bekende_domeinen):
    adres = (adres or "").lower()
    if adres in bekende_adressen:
        return True
    mail_dom = adres.split("@")[1] if "@" in adres else ""
    return (domein in bekende_domeinen) or (mail_dom in bekende_domeinen)


# ---------------------------------------------------------------------------
# Versturen
# ---------------------------------------------------------------------------

def verstuur_mail(smtp_user, wachtwoord, afzendernaam, aan, onderwerp, tekst,
                  smtp_server="smtp.gmail.com", smtp_port=465, afmeldbaar=True, html_tekst=None):
    afzender = smtp_user.strip()
    msg = MIMEMultipart("alternative")
    msg["From"] = f"{afzendernaam} <{afzender}>"
    msg["To"] = aan
    msg["Subject"] = onderwerp
    msg["Reply-To"] = afzender
    msg["Date"] = email.utils.formatdate(localtime=True)
    msg["Message-ID"] = email.utils.make_msgid(domain=afzender.split("@")[1])
    if afmeldbaar:
        msg["List-Unsubscribe"] = f"<mailto:{afzender}?subject=unsubscribe>"
    msg.attach(MIMEText(tekst, "plain", "utf-8"))
    msg.attach(MIMEText(html_tekst or maak_html(tekst), "html", "utf-8"))
    try:
        port = int(smtp_port)
        if port == 465:
            server = smtplib.SMTP_SSL(smtp_server, port, timeout=30)
        else:
            server = smtplib.SMTP(smtp_server, port, timeout=30)
            server.starttls()
        server.login(afzender, wachtwoord.replace(" ", "").strip())
        server.send_message(msg)
        server.quit()
        return True, "Verzonden"
    except Exception as ex:
        return False, str(ex)


# ---------------------------------------------------------------------------
# Alles samen: leads zoeken met echte adressen
# ---------------------------------------------------------------------------

def zoek_leads(api_key, niche, markt, max_leads=10, max_zoekopdrachten=2, startpagina=0,
               bekende_adressen=None, bekende_domeinen=None, log=print):
    """
    Zoekt winkels tot er max_leads met een echt adres gevonden zijn
    (of tot de zoekopdrachten op zijn). Geeft (leads, overgeslagen, zoekopdrachten_gebruikt, fout).
    """
    bekende_adressen = bekende_adressen or set()
    bekende_domeinen = bekende_domeinen or set()
    sessie = _sessie()
    leads, overgeslagen, gezien = [], [], set()
    gebruikt = 0
    taal = MARKTEN.get(markt, MARKTEN["US"])["taal"]

    for p in range(startpagina, startpagina + max_zoekopdrachten):
        urls, fout = zoek_websites(api_key, niche, markt, pagina=p, log=log)
        gebruikt += 1
        if fout:
            return leads, overgeslagen, gebruikt, fout
        if not urls:
            continue
        for url in urls:
            dom = domein_van(url)
            if dom in gezien:
                continue
            gezien.add(dom)
            if dom in bekende_domeinen:
                overgeslagen.append({"website": url, "reden": "Al eerder contact"})
                continue
            info = bekijk_winkel(url, sessie, niche=niche)
            if info["reden"]:
                overgeslagen.append({"website": info["website"], "reden": info["reden"]})
                log(f"  - {info['website']}: {info['reden']}")
                continue
            if al_bekend(info["email"], info["domein"], bekende_adressen, bekende_domeinen):
                overgeslagen.append({"website": info["website"], "reden": "Al eerder contact"})
                continue
            info.update({"markt": markt, "taal": taal, "niche": niche})
            leads.append(info)
            log(f"  + {info['winkelnaam']} ({info['website']}) -> {info['email']}")
            if len(leads) >= max_leads:
                return leads, overgeslagen, gebruikt, None
            time.sleep(random.uniform(0.5, 1.5))
    return leads, overgeslagen, gebruikt, None


# ---------------------------------------------------------------------------
# Zoeken via de Shopify-lijst (Common Crawl, gratis openbare webverzameling)
# ---------------------------------------------------------------------------

CC_INDEX = "https://index.commoncrawl.org"


def _cc_indexen(sessie):
    r = sessie.get(CC_INDEX + "/collinfo.json", timeout=30)
    r.raise_for_status()
    return [c["cdx-api"] for c in r.json()]


def shopify_adressen(aantal=300, log=print, rnd=None):
    """
    Haalt een willekeurig stuk uit de lijst van alle winkels met een
    iets.myshopify.com-adres die Common Crawl ooit tegenkwam.
    Geeft (lijst met https://iets.myshopify.com, foutmelding of None).
    """
    rnd = rnd or random.Random()
    # Eerst het bestand dat elke week via GitHub wordt bijgewerkt.
    import os
    pad = os.path.join(os.path.dirname(os.path.abspath(__file__)), "shopify_winkels.txt")
    if os.path.exists(pad):
        with open(pad, encoding="utf-8") as f:
            alle = [r.strip() for r in f if r.strip()]
        if alle:
            keuze = rnd.sample(alle, min(aantal, len(alle)))
            log(f"Shopify-lijst: {len(keuze)} winkels gekozen uit {len(alle)} in de lijst")
            return ["https://" + h for h in keuze], None
    sessie = _sessie()
    try:
        indexen = _cc_indexen(sessie)
    except Exception as ex:
        return [], ("De Shopify-lijst is nog niet gevuld en Common Crawl is vanaf hier niet bereikbaar. "
                    "Hij wordt via GitHub bijgewerkt (elke zondag, of met de hand via Actions).")

    hosts = []
    for poging in range(4):
        api = indexen[rnd.randrange(0, min(4, len(indexen)))]
        try:
            r = sessie.get(api, params={"url": "*.myshopify.com", "output": "json",
                                        "showNumPages": "true"}, timeout=60)
            paginas = int(r.json().get("pages", 1))
            pagina = rnd.randrange(0, max(1, paginas))
            r = sessie.get(api, params={"url": "*.myshopify.com", "output": "json",
                                        "fl": "url", "page": pagina}, timeout=90)
            r.raise_for_status()
        except Exception as ex:
            log(f"Shopify-lijst: poging {poging + 1} mislukt ({type(ex).__name__}), opnieuw...")
            time.sleep(3)
            continue
        gezien = set()
        for regel in r.text.splitlines():
            try:
                u = json.loads(regel).get("url", "")
            except ValueError:
                continue
            host = domein_van(u)
            if host.endswith(".myshopify.com") and host.count(".") == 2 and host not in gezien:
                gezien.add(host)
                hosts.append("https://" + host)
        log(f"Shopify-lijst: {len(hosts)} winkeladressen opgehaald (blok {pagina} van {paginas})")
        if len(hosts) >= 30:
            break
    rnd.shuffle(hosts)
    return hosts[:aantal], (None if hosts else "Shopify-lijst gaf geen adressen terug")


def zoek_leads_shopifylijst(max_leads=10, landen=("NL", "BE", "US", "UK"), niche="", max_bezoeken=200,
                            bekende_adressen=None, bekende_domeinen=None, log=print,
                            gelijktijdig=8):
    """
    Zoekt willekeurige actieve Shopify-winkels (elke branche, tenzij niche ingevuld)
    in de gekozen talen, met een echt e-mailadres.
    Geeft (leads, overgeslagen, 0 zoekopdrachten, fout).
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    bekende_adressen = set(bekende_adressen or set())
    bekende_domeinen = set(bekende_domeinen or set())
    urls, fout = shopify_adressen(aantal=max_bezoeken, log=log)
    if fout:
        return [], [], 0, fout

    leads, overgeslagen = [], []

    def werk(u):
        return bekijk_winkel(u, _sessie(), niche=niche or None, landen=set(landen))

    with ThreadPoolExecutor(max_workers=gelijktijdig) as pool:
        taken = [pool.submit(werk, u) for u in urls]
        for taak in as_completed(taken):
            if len(leads) >= max_leads:
                break
            try:
                info = taak.result()
            except Exception as ex:
                overgeslagen.append({"website": "?", "reden": f"Fout: {type(ex).__name__}"})
                continue
            if info["reden"]:
                overgeslagen.append({"website": info["website"], "reden": info["reden"]})
                continue
            if al_bekend(info["email"], info["domein"], bekende_adressen, bekende_domeinen) \
                    or info["domein"] in {l["domein"] for l in leads}:
                overgeslagen.append({"website": info["website"], "reden": "Al eerder contact"})
                continue
            info.update({"niche": niche or "alles"})
            leads.append(info)
            log(f"  + {info['winkelnaam']} ({info['website']}) -> {info['email']} [{info['markt']}]")
        for t in taken:
            t.cancel()

    # Kort overzicht van de redenen
    tellers = {}
    for o in overgeslagen:
        sleutel = re.sub(r"\s*\(.*\)", "", o["reden"])
        tellers[sleutel] = tellers.get(sleutel, 0) + 1
    for reden, n in sorted(tellers.items(), key=lambda x: -x[1]):
        log(f"  overgeslagen: {n} x {reden}")
    return leads[:max_leads], overgeslagen, 0, None


def laad_instellingen(pad="instellingen.json"):
    with open(pad, encoding="utf-8") as f:
        return json.load(f)
