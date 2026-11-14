"""
Dagelijkse automatische run (wordt elke dag door GitHub gestart, zie
.github/workflows/dagelijks.yml).

- stand "proef": zoekt winkels en mailt alleen een overzicht naar jezelf.
- stand "echt":  mailt de gevonden winkels echt, rustig na elkaar, en stuurt
                 daarna een overzicht naar jezelf.

De stand en het aantal mails per dag staan in instellingen.json.
"""

import os
import random
import sys
import time
from datetime import date

import detective
import outreach_core as oc


def omgeving(naam, standaard=None):
    waarde = os.environ.get(naam, "").strip()
    return waarde or standaard


def main():
    inst = oc.laad_instellingen()
    stand = omgeving("STAND_OVERRIDE", inst.get("stand", "proef"))
    smtp_user = omgeving("SMTP_USER")
    wachtwoord = omgeving("SMTP_PASSWORD")
    afzender = omgeving("SENDER_NAME", "Marcel – ShopReels")
    serp = omgeving("SERPAPI_KEY")
    rapport_naar = omgeving("RAPPORT_NAAR", smtp_user)
    ai_sleutel = omgeving("ANTHROPIC_API_KEY")

    bron = inst.get("bron", "shopify-lijst")
    nodig = [("SMTP_USER", smtp_user), ("SMTP_PASSWORD", wachtwoord)]
    if bron == "google":
        nodig.append(("SERPAPI_KEY", serp))
    ontbreekt = [n for n, w in nodig if not w]
    if ontbreekt:
        print("Deze geheimen ontbreken in GitHub:", ", ".join(ontbreekt))
        sys.exit(1)

    max_mails = int(inst.get("mails_per_dag", 15))
    max_zoek = int(inst.get("zoekopdrachten_per_dag", 6))
    link = inst.get("link", oc.SHOPREELS_LINK)

    print(f"Stand: {stand} | max {max_mails} mails | max {max_zoek} zoekopdrachten")

    adressen, domeinen, fout = oc.bekende_contacten(smtp_user, wachtwoord)
    if fout:
        # Zonder mailbox kunnen we niet controleren wie al gemaild is: dan niets versturen.
        print(fout)
        if stand == "echt":
            print("Veiligheidshalve wordt er vandaag niets verstuurd.")
            stand = "proef"
    print(f"Al bekend in de mailbox: {len(adressen)} adressen, {len(domeinen)} domeinen")

    leads, overgeslagen, gebruikt = [], [], 0
    if bron != "google":
        print("Zoeken in de Shopify-lijst, landen:", ", ".join(inst.get("markten", [])))
        leads, overgeslagen, gebruikt, fout = oc.zoek_leads_shopifylijst(
            max_leads=max_mails, landen=inst.get("markten", ["US"]), niche="",
            max_bezoeken=int(inst.get("bezoeken_per_dag", 400)),
            bekende_adressen=adressen, bekende_domeinen=domeinen)
        if fout:
            print("Fout bij zoeken:", fout)
    else:
        # Elke dag een andere combinatie van markt en branche.
        combinaties = []
        for markt in inst.get("markten", ["US"]):
            taal = oc.MARKTEN[markt]["taal"]
            for branche in inst.get("branches", {}).get(taal, []):
                combinaties.append((markt, branche))
        random.Random(42).shuffle(combinaties)
        dag = date.today().toordinal()
        start = (dag * 3) % len(combinaties)
        ronde = (dag * 3) // len(combinaties)
        i = 0
        while len(leads) < max_mails and gebruikt < max_zoek and i < len(combinaties):
            markt, branche = combinaties[(start + i) % len(combinaties)]
            i += 1
            print(f"Zoeken: {branche} in {oc.MARKTEN[markt]['naam']}")
            nieuw, over, g, fout = oc.zoek_leads(
                serp, branche, markt,
                max_leads=max_mails - len(leads),
                max_zoekopdrachten=min(2, max_zoek - gebruikt),
                startpagina=(ronde * 2) % 9,
                bekende_adressen=adressen | {l["email"] for l in leads},
                bekende_domeinen=domeinen | {l["domein"] for l in leads},
            )
            gebruikt += g
            leads += nieuw
            overgeslagen += over
            if fout:
                print("Fout bij zoeken:", fout)
                break

    print(f"Gevonden: {len(leads)} winkels met een echt adres ({gebruikt} zoekopdrachten)")

    # De detective schrijft per winkel een persoonlijke mail (of valt terug op de standaardmail).
    print("Detective aan het werk" + ("" if ai_sleutel else " (geen AI-sleutel: standaardmails)"))
    mails = []
    for lead in leads:
        onderwerp, tekst, rapportje = detective.maak_beste_mail(lead, afzender, link, ai_sleutel)
        mails.append((onderwerp, tekst, rapportje))
        print(f"  {lead['domein']}: {lead.get('detective', '')}")

    resultaten = []
    if stand == "echt":
        for n, (lead, (onderwerp, tekst, _)) in enumerate(zip(leads, mails)):
            ok, melding = oc.verstuur_mail(smtp_user, wachtwoord, afzender, lead["email"], onderwerp, tekst)
            resultaten.append((lead, "verstuurd" if ok else f"mislukt: {melding[:80]}"))
            print(f"{'OK ' if ok else 'MIS'} {lead['email']}")
            if n < len(leads) - 1:
                time.sleep(random.uniform(45, 120))  # rustig aan, niet als spam overkomen
    else:
        resultaten = [(lead, "proef – niet verstuurd") for lead in leads]

    # Overzicht naar jezelf
    regels = [
        f"Outreach-overzicht {date.today().strftime('%d-%m-%Y')}",
        f"Stand: {'ECHT – deze mails zijn verstuurd' if stand == 'echt' else 'PROEF – er is niets naar winkels verstuurd'}",
        f"Winkels met een echt e-mailadres: {len(leads)}",
        f"Persoonlijke mails door de detective: {sum(1 for m in mails if m[2])} van {len(mails)}",
        f"Overgeslagen: {len(overgeslagen)} (geen adres, geen Shopify, te klein of al eerder contact)",
        f"Zoekopdrachten gebruikt: {gebruikt}",
        "",
    ]
    for lead, status in resultaten:
        regels.append(f"- {lead['winkelnaam']} | {lead['website']} | {lead['email']} | "
                      f"{oc.MARKTEN.get(lead.get('markt'), {}).get('naam', lead.get('markt'))} | {lead['niche']} | {status}")
    # Alle mails voluit, zodat je ze kunt meelezen.
    for (lead, _), (onderwerp, tekst, rapportje) in zip(resultaten, mails):
        regels += ["", "=" * 60, f"{lead['winkelnaam']} – {lead['website']} – aan: {lead['email']}"]
        regels.append(f"Detective: {lead.get('detective', '')}")
        if rapportje:
            regels += ["", "RAPPORT:", rapportje]
        regels += ["", f"Onderwerp: {onderwerp}", "", tekst]
    rapport = "\n".join(regels)
    print("\n" + rapport)

    ok, melding = oc.verstuur_mail(smtp_user, wachtwoord, "Outreach Engine", rapport_naar,
                                   f"Outreach-overzicht {date.today().strftime('%d-%m')}: "
                                   f"{len(leads)} winkels ({stand})",
                                   rapport, afmeldbaar=False)
    print("Overzicht gemaild:", ok, "" if ok else melding)


if __name__ == "__main__":
    main()
