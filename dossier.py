"""
Het ochtendoverzicht als detectivedossier (HTML-mail voor Marcel zelf).

Alleen voor het overzicht aan jezelf. De mails naar winkels blijven bewust
gewone, menselijke mails.

Gebouwd met tabellen en inline-stijlen, want zo tonen Gmail en Apple Mail het goed.
"""

import html
import re
from datetime import date

MAANDEN = ["januari", "februari", "maart", "april", "mei", "juni", "juli",
           "augustus", "september", "oktober", "november", "december"]

INKT = "#2a2e33"        # rustige leigrijze achtergrond
PAPIER = "#f4eedf"      # dossierpapier
PAPIER_RAND = "#c9b48a"
TEKST = "#2a241c"
ROOD = "#9e2a22"        # stempel
GRIJS = "#7b6f5c"
TYPEMACHINE = "'Courier New', Courier, monospace"
SCHREEF = "Georgia, 'Times New Roman', serif"


def _e(t):
    return html.escape(str(t or ""))


def _alinea(tekst):
    """Platte tekst naar HTML met regeleindes en klikbare links."""
    t = _e(tekst)
    t = re.sub(r"(https?://[^\s<]+)", r'<a href="\1" style="color:#1f4e79">\1</a>', t)
    return t.replace("\n", "<br>")


def _mailtekst_zonder_afmelden(tekst):
    # De afmeldregel onderaan (na '--') hoeft niet in het dossier.
    return tekst.split("\n--\n")[0].strip()


def _veld(label, waarde):
    return (f'<tr><td width="96" style="padding:6px 8px 6px 0;border-bottom:1px solid {PAPIER_RAND};'
            f'color:{GRIJS};font-size:11px;letter-spacing:2px;vertical-align:top;">{label}</td>'
            f'<td style="padding:6px 0;border-bottom:1px solid {PAPIER_RAND};">{waarde}</td></tr>')


def _stempel(tekst, kleur):
    return (f'<span style="display:inline-block;border:3px double {kleur};color:{kleur};'
            f'font-family:{TYPEMACHINE};font-weight:bold;font-size:13px;letter-spacing:3px;'
            f'padding:4px 10px;">{_e(tekst)}</span>')


def maak_dossier_html(stand, leads, mails, statussen, aantal_overgeslagen, markten, vandaag=None, antwoorden=None):
    """
    leads: lijst met winkel-dicts; mails: lijst (onderwerp, tekst, rapport);
    statussen: lijst met de status per winkel (verstuurd / proef / mislukt).
    """
    vandaag = vandaag or date.today()
    datum = f"{vandaag.day} {MAANDEN[vandaag.month - 1]} {vandaag.year}"
    persoonlijk = sum(1 for m in mails if m[2])
    echt = stand == "echt"
    stand_tekst = ("ECHT &mdash; deze brieven zijn verstuurd" if echt
                   else "PROEF &mdash; er is niets naar winkels verstuurd")

    kaarten = []
    for nr, (lead, (onderwerp, tekst, rapport), status) in enumerate(zip(leads, mails, statussen), 1):
        land = markten.get(lead.get("markt"), {}).get("naam", lead.get("markt") or "")
        if rapport:
            stempel = _stempel("ONDERZOCHT", ROOD)
            bevindingen = (f'<div style="font-family:{TYPEMACHINE};font-size:12px;color:{GRIJS};'
                           f'letter-spacing:2px;margin:18px 0 6px;">BEVINDINGEN</div>'
                           f'<div style="font-family:{TYPEMACHINE};font-size:14px;line-height:1.55;'
                           f'color:{TEKST};">{_alinea(rapport)}</div>')
        else:
            stempel = _stempel("STANDAARDBRIEF", GRIJS)
            bevindingen = (f'<div style="font-family:{TYPEMACHINE};font-size:13px;color:{GRIJS};'
                           f'margin-top:14px;">{_e(lead.get("detective", ""))}</div>')
        kaarten.append(f"""
<tr><td style="padding:0 0 26px;">
 <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
  style="background:{PAPIER};border:1px solid {PAPIER_RAND};border-top:6px solid #1f3b57;">
  <tr><td style="padding:20px 22px 22px;">
   <table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
    <td style="font-family:{TYPEMACHINE};font-size:12px;color:{GRIJS};letter-spacing:3px;">DOSSIER NR. {nr:03d}</td>
    <td align="right">{stempel}</td>
   </tr></table>
   <div style="font-family:{SCHREEF};font-size:22px;font-weight:bold;color:{TEKST};margin:12px 0 12px;">{_e(lead.get("winkelnaam"))}</div>
   <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
    style="border-top:1px solid {PAPIER_RAND};font-family:{TYPEMACHINE};font-size:13px;color:{TEKST};">
    {_veld("WEBSITE", f'<a href="{_e(lead.get("website"))}" style="color:#1f4e79">{_e(lead.get("website"))}</a>')}
    {_veld("LAND", _e(land))}
    {_veld("CONTACT", _e(lead.get("email")))}
    {_veld("STATUS", _e(status))}
   </table>
   {bevindingen}
   <div style="font-family:{TYPEMACHINE};font-size:12px;color:{GRIJS};letter-spacing:2px;margin:20px 0 6px;">DE BRIEF</div>
   <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
    style="background:#fbf7ee;border-left:4px solid {ROOD};">
    <tr><td style="padding:14px 16px;font-family:{SCHREEF};font-size:15px;line-height:1.6;color:{TEKST};">
     <b>Onderwerp: {_e(onderwerp)}</b><br><br>{_alinea(_mailtekst_zonder_afmelden(tekst))}
    </td></tr>
   </table>
  </td></tr>
 </table>
</td></tr>""")

    if not kaarten:
        kaarten.append(f'<tr><td style="font-family:{TYPEMACHINE};color:{PAPIER};padding:20px 0;">'
                       f'Vandaag geen nieuwe zaken gevonden.</td></tr>')

    blok = ""
    if antwoorden:
        stukken = []
        for a in antwoorden:
            kleur = "#9aa0a6" if a.get("afmelding") else "#3FE0C5"
            label = "NEGATIEF" if a.get("afmelding") else "POSITIEF"
            stukken.append(f"""<tr><td style="padding:0 0 14px;">
 <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#0f1a22;border-left:4px solid {kleur};">
  <tr><td style="padding:14px 16px;font-family:{TYPEMACHINE};color:{PAPIER};">
   <div style="font-size:11px;letter-spacing:3px;color:{kleur};">{label} &middot; {_e(a.get('datum', ''))}</div>
   <div style="font-family:{SCHREEF};font-size:17px;font-weight:bold;margin:6px 0 2px;">{_e(a.get('naam') or a.get('van', ''))}</div>
   <div style="font-size:12px;color:#b9b2a1;">{_e(a.get('van', ''))} &middot; {_e(a.get('onderwerp', ''))}</div>
   <div style="font-family:{SCHREEF};font-size:15px;line-height:1.55;margin-top:10px;">{_alinea(a.get('tekst', '')[:700])}</div>
  </td></tr></table></td></tr>""")
        echt_int = sum(1 for a in antwoorden if not a.get("afmelding"))
        neg = len(antwoorden) - echt_int
        kop_interesse = f"KOOPSIGNALEN &middot; {echt_int} POSITIEF &middot; {neg} NEGATIEF"
        blok = (f'<tr><td style="font-family:{TYPEMACHINE};font-size:13px;letter-spacing:4px;color:#3FE0C5;'
                f'padding:0 0 12px;">{kop_interesse}</td></tr>' + "".join(stukken)
                + '<tr><td style="height:14px;"></td></tr>')

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<meta name="color-scheme" content="dark"><meta name="supported-color-schemes" content="dark"></head>
<body style="margin:0;padding:0;background:{INKT};">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{INKT};">
<tr><td align="center" style="padding:28px 14px;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:640px;">
 <tr><td style="padding:0 0 26px;border-bottom:1px solid #4a5058;">
  <div style="background:{ROOD};color:#fff;font-family:{TYPEMACHINE};font-size:11px;letter-spacing:6px;text-align:center;padding:5px 0;">VERTROUWELIJK &middot; ALLEEN VOOR INTERN GEBRUIK</div>
  <div style="font-family:{TYPEMACHINE};font-size:12px;letter-spacing:4px;color:#b9b2a1;margin-top:20px;">NOCTURO &middot; AFDELING SEARCH &amp; ANALYZE</div>
  <div style="font-family:{SCHREEF};font-size:30px;font-weight:bold;color:{PAPIER};margin:6px 0 4px;">Ochtendrapport</div>
  <div style="font-family:{TYPEMACHINE};font-size:14px;color:#d6cfbd;">{datum}</div>
  <div style="font-family:{SCHREEF};font-size:16px;color:{PAPIER};margin-top:14px;line-height:1.5;">De afdeling Search &amp; Analyze heeft vandaag {len(leads)} winkels voor je gevonden en verwerkt.</div>
  <table role="presentation" cellpadding="0" cellspacing="0" style="margin-top:18px;"><tr>
   <td style="padding-right:22px;font-family:{TYPEMACHINE};color:{PAPIER};">
    <div style="font-size:28px;font-weight:bold;">{len(leads)}</div><div style="font-size:11px;letter-spacing:2px;color:#b9b2a1;">DOSSIERS</div></td>
   <td style="padding-right:22px;font-family:{TYPEMACHINE};color:{PAPIER};">
    <div style="font-size:28px;font-weight:bold;">{persoonlijk}</div><div style="font-size:11px;letter-spacing:2px;color:#b9b2a1;">PERSOONLIJK</div></td>
   <td style="font-family:{TYPEMACHINE};color:{PAPIER};">
    <div style="font-size:28px;font-weight:bold;">{aantal_overgeslagen}</div><div style="font-size:11px;letter-spacing:2px;color:#b9b2a1;">AFGEVALLEN</div></td>
  </tr></table>
  <div style="margin-top:16px;font-family:{TYPEMACHINE};font-size:13px;color:{'#e8a598' if echt else '#b9b2a1'};">{stand_tekst}</div>
 </td></tr>
 <tr><td style="height:26px;"></td></tr>
 {blok}
 {"".join(kaarten)}
 <tr><td style="font-family:{TYPEMACHINE};font-size:11px;color:#8a8f96;letter-spacing:2px;text-align:center;padding-top:6px;">
  EINDE RAPPORT &middot; ALLEEN OPENBARE BEDRIJFSINFORMATIE GEBRUIKT</td></tr>
</table>
</td></tr></table>
</body></html>"""
