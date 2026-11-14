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
            "Liever geen mail meer van mij? Antwoord dan met 'afmelden', dan hoor je niets meer van me."
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
            "Don't want to hear from me again? Reply with 'unsubscribe' and I won't email you again."
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
            "Keine E-Mails mehr von mir? Antworten Sie mit 'abmelden', dann schreibe ich Ihnen nicht mehr."
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
            "¿Prefieres no recibir más correos? Responde con 'baja' y no te escribiré más."
        ),
    },
}


def maak_mail(taal, winkelnaam, afzender, link=SHOPREELS_LINK):
    """Geeft (onderwerp, tekst) terug voor een winkel."""
    tpl = TEMPLATES.get(taal, TEMPLATES["EN"])
    onderwerp = tpl["onderwerp"].format(naam=winkelnaam)
    tekst = tpl["bericht"].format(naam=winkelnaam, link=link, afzender=afzender)
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
        if not dom:
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


def _haal(sessie, url, timeout=10):
    try:
        r = sessie.get(url, timeout=timeout, allow_redirects=True)
        if r.status_code == 200:
            return r
    except requests.RequestException:
        pass
    return None


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


def bekijk_winkel(url, sessie=None):
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
        info["reden"] = "Site niet bereikbaar"
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
    info["shopify"] = ("cdn.shopify.com" in tekst) or ("Shopify.shop" in tekst) or \
        ("x-shopid" in {k.lower() for k in home.headers.keys()})

    # Aantal producten (openbare Shopify-lijst). Een lege winkel is geen klant.
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
        '{niche} "powered by shopify"',
        '{niche} shop inurl:collections',
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
                  smtp_server="smtp.gmail.com", smtp_port=465, afmeldbaar=True):
    afzender = smtp_user.strip()
    msg = MIMEMultipart()
    msg["From"] = f"{afzendernaam} <{afzender}>"
    msg["To"] = aan
    msg["Subject"] = onderwerp
    msg["Reply-To"] = afzender
    msg["Date"] = email.utils.formatdate(localtime=True)
    msg["Message-ID"] = email.utils.make_msgid(domain=afzender.split("@")[1])
    if afmeldbaar:
        msg["List-Unsubscribe"] = f"<mailto:{afzender}?subject=unsubscribe>"
    msg.attach(MIMEText(tekst, "plain", "utf-8"))
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
            info = bekijk_winkel(url, sessie)
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


def laad_instellingen(pad="instellingen.json"):
    with open(pad, encoding="utf-8") as f:
        return json.load(f)
