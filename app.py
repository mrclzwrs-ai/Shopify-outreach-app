import time
from datetime import datetime

import pandas as pd
import streamlit as st

import importlib

import outreach_core as oc

# Na een update altijd de nieuwste versie van de zoekmotor gebruiken (geen herstart nodig).
oc = importlib.reload(oc)

st.set_page_config(page_title="ShopReels Outreach", page_icon="🚀", layout="wide")

st.markdown("""
    <style>
        html, body, [class*="css"] { font-size: 19px !important; }
        h1 { font-size: 2.1rem !important; font-weight: 700 !important; }
        h2, h3 { font-size: 1.45rem !important; font-weight: 600 !important; }
        .stButton>button { font-size: 1.15rem !important; padding: 0.6rem 1.2rem !important;
                           border-radius: 8px !important; font-weight: 600 !important; }
        label p { font-size: 1.1rem !important; font-weight: 600 !important; }
    </style>
""", unsafe_allow_html=True)


def kluis(naam, standaard=""):
    """Haalt een instelling uit de Streamlit-kluis (Secrets)."""
    try:
        if naam in st.secrets:
            return st.secrets[naam]
    except Exception:
        pass
    return standaard


for sleutel, standaard in {
    "serpapi_key": kluis("serpapi_key"),
    "smtp_user": kluis("smtp_user", "info@shopreelsapp.com"),
    "smtp_password": kluis("smtp_password"),
    "sender_name": kluis("sender_name", "Marcel – ShopReels"),
    "link": kluis("app_link", oc.SHOPREELS_LINK),
}.items():
    st.session_state.setdefault(sleutel, standaard)
st.session_state.setdefault("leads", pd.DataFrame())
st.session_state.setdefault("log", [])

try:
    INST = oc.laad_instellingen()
except Exception:
    INST = {}


def bekende_contacten():
    return oc.bekende_contacten(st.session_state.smtp_user, st.session_state.smtp_password)


# ---------------------------------------------------------------------------
st.sidebar.title("🚀 ShopReels Outreach")
menu = st.sidebar.radio("Kies een pagina", [
    "🔍 Winkels zoeken",
    "🚀 Versturen",
    "✉️ De mail",
    "🤖 Automatisch",
    "⚙️ Instellingen",
])
leads = st.session_state.leads
st.sidebar.markdown("---")
st.sidebar.metric("Gevonden winkels", len(leads))
if len(leads):
    st.sidebar.metric("Verstuurd", int((leads["Status"] == "Verstuurd").sum()))


# ---------------------------------------------------------------------------
if menu == "🔍 Winkels zoeken":
    st.title("🔍 Winkels zoeken")
    st.write("De app zoekt Shopify-winkels, kijkt op hun eigen site of het een echte winkel met "
             "producten is, en zoekt daar een **echt** e-mailadres. Winkels zonder adres, en winkels "
             "die we al eens gemaild hebben, worden overgeslagen.")

    c1, c2 = st.columns(2)
    with c1:
        markt = st.selectbox("Land:", list(oc.MARKTEN.keys()),
                             format_func=lambda k: oc.MARKTEN[k]["naam"])
    with c2:
        taal = oc.MARKTEN[markt]["taal"]
        suggesties = INST.get("branches", {}).get(taal, [])
        niche = st.text_input("Branche (in de taal van het land):",
                              value=suggesties[0] if suggesties else "jewelry")
        if suggesties:
            st.caption("Ideeën: " + ", ".join(suggesties))
    aantal = st.slider("Hoeveel winkels wil je vinden?", 3, 20, 10)
    st.caption("Elke zoekronde kost 1 van je SerpApi-zoekopdrachten. De app doet er maximaal 3.")

    if st.button("🔎 Zoeken", type="primary"):
        if not st.session_state.serpapi_key:
            st.error("Er is nog geen SerpApi-sleutel. Zet hem in de kluis of bij Instellingen.")
        else:
            with st.spinner("Even kijken wie we al gemaild hebben..."):
                adressen, domeinen, fout = bekende_contacten()
            if fout:
                st.warning(fout + " — ik zoek wel, maar kan niet controleren wie al gemaild is.")
            bestaand = st.session_state.leads
            if len(bestaand):
                adressen |= set(bestaand["E-mail"])
                domeinen |= set(bestaand["Domein"])

            regels = []
            log_vak = st.empty()

            def log(tekst):
                regels.append(tekst)
                log_vak.code("\n".join(regels[-12:]))

            with st.spinner("Winkels zoeken en bekijken... (dit duurt een paar minuten)"):
                gevonden, overgeslagen, gebruikt, fout = oc.zoek_leads(
                    st.session_state.serpapi_key, niche, markt, max_leads=aantal,
                    max_zoekopdrachten=3, bekende_adressen=adressen,
                    bekende_domeinen=domeinen, log=log)
            log_vak.empty()
            if fout:
                st.error("Fout bij zoeken: " + fout)
            nieuw = pd.DataFrame([{
                "Versturen": True,
                "Winkel": l["winkelnaam"],
                "Website": l["website"],
                "E-mail": l["email"],
                "Land": markt,
                "Taal": l["taal"],
                "Branche": niche,
                "Status": "Klaar",
                "Domein": l["domein"],
            } for l in gevonden])
            st.session_state.leads = pd.concat([st.session_state.leads, nieuw], ignore_index=True)
            st.success(f"{len(gevonden)} winkels met een echt adres gevonden. "
                       f"{len(overgeslagen)} overgeslagen. ({gebruikt} zoekopdrachten gebruikt)")
            with st.expander("Wat heeft hij precies gedaan?"):
                st.code("\n".join(regels) or "Niets gevonden.")
            if overgeslagen:
                with st.expander("Waarom zijn winkels overgeslagen?"):
                    st.dataframe(pd.DataFrame(overgeslagen), hide_index=True, width="stretch")

    if len(st.session_state.leads):
        st.subheader("Gevonden winkels")
        st.write("Haal het vinkje weg bij winkels die je niet wilt mailen.")
        st.session_state.leads = st.data_editor(
            st.session_state.leads, hide_index=True, width="stretch",
            column_config={"Website": st.column_config.LinkColumn("Website"),
                           "Domein": None},
            disabled=["Winkel", "Website", "E-mail", "Land", "Taal", "Branche", "Status"],
            key="editor")


# ---------------------------------------------------------------------------
elif menu == "🚀 Versturen":
    st.title("🚀 Versturen")
    leads = st.session_state.leads
    if not len(leads):
        st.info("Zoek eerst winkels op de pagina 🔍 Winkels zoeken.")
    else:
        klaar = leads[(leads["Status"] == "Klaar") & (leads["Versturen"])]
        st.write(f"Er staan **{len(klaar)}** winkels klaar met een vinkje.")
        st.caption("Tussen elke mail wacht de app ongeveer een halve minuut, zodat Gmail je "
                   "adres niet als spam ziet. Houd deze pagina open tot hij klaar is.")
        hoeveel = st.number_input("Hoeveel nu versturen?", 1, 25, min(10, max(1, len(klaar))))
        if st.button("🚀 Start", type="primary", disabled=len(klaar) == 0):
            if not st.session_state.smtp_password:
                st.error("Er is nog geen app-wachtwoord ingevuld (kluis of Instellingen).")
            else:
                adressen, domeinen, fout = bekende_contacten()
                if fout:
                    st.error(fout + " — veiligheidshalve wordt er niets verstuurd.")
                else:
                    balk = st.progress(0.0)
                    status = st.empty()
                    rijen = klaar.head(int(hoeveel))
                    for n, (idx, rij) in enumerate(rijen.iterrows()):
                        if oc.al_bekend(rij["E-mail"], rij["Domein"], adressen, domeinen):
                            st.session_state.leads.at[idx, "Status"] = "Al eerder contact"
                            continue
                        status.write(f"Versturen naar {rij['Winkel']} ({rij['E-mail']})...")
                        onderwerp, tekst = oc.maak_mail(rij["Taal"], rij["Winkel"],
                                                        st.session_state.sender_name,
                                                        st.session_state.link)
                        ok, melding = oc.verstuur_mail(
                            st.session_state.smtp_user, st.session_state.smtp_password,
                            st.session_state.sender_name, rij["E-mail"], onderwerp, tekst)
                        st.session_state.leads.at[idx, "Status"] = (
                            "Verstuurd" if ok else f"Mislukt: {melding[:50]}")
                        adressen.add(rij["E-mail"])
                        domeinen.add(rij["Domein"])
                        balk.progress((n + 1) / len(rijen))
                        if n < len(rijen) - 1:
                            time.sleep(30)
                    status.success("Klaar!")
        st.subheader("Overzicht")
        st.dataframe(leads.drop(columns=["Domein"]), hide_index=True, width="stretch")
        st.download_button("⬇️ Lijst downloaden (CSV)",
                           leads.to_csv(index=False).encode("utf-8"),
                           f"leads-{datetime.now():%Y-%m-%d}.csv", "text/csv")


# ---------------------------------------------------------------------------
elif menu == "✉️ De mail":
    st.title("✉️ Zo ziet de mail eruit")
    gekozen = st.radio("Taal:", ["NL", "EN", "DE", "ES"], horizontal=True)
    onderwerp, tekst = oc.maak_mail(gekozen, "Voorbeeldwinkel", st.session_state.sender_name,
                                    st.session_state.link)
    st.text_input("Onderwerp:", value=onderwerp, disabled=True)
    st.text_area("Tekst:", value=tekst, height=420, disabled=True)
    st.caption("De winkelnaam wordt automatisch ingevuld. Elke mail heeft onderaan een afmeldregel; "
               "wie antwoordt (ook met 'afmelden') krijgt nooit meer een mail van de app.")


# ---------------------------------------------------------------------------
elif menu == "🤖 Automatisch":
    st.title("🤖 Automatisch elke werkdag")
    stand = INST.get("stand", "proef")
    st.write("Elke werkdag om ongeveer **9:15** zoekt de app zelf nieuwe winkels "
             "(dat draait bij GitHub, dus je iPad hoeft niet aan te staan).")
    if stand == "echt":
        st.success(f"Stand: **ECHT**. Er gaan maximaal {INST.get('mails_per_dag')} mails per dag "
                   "naar winkels. Daarna krijg je een overzicht in je mailbox.")
    else:
        st.info("Stand: **PROEF**. Er gaat nog niets naar winkels. Je krijgt elke werkdag een "
                "overzicht in je mailbox van welke winkels hij gevonden heeft en hoe de mail eruitziet.")
    st.write("**Landen:** " + ", ".join(oc.MARKTEN[m]["naam"] for m in INST.get("markten", [])))
    for taal, lijst in INST.get("branches", {}).items():
        if any(oc.MARKTEN[m]["taal"] == taal for m in INST.get("markten", [])):
            st.write(f"**Branches ({taal}):** " + ", ".join(lijst))
    st.caption("Wil je iets veranderen (aanzetten, ander aantal, andere branches)? Vraag het Claude.")


# ---------------------------------------------------------------------------
elif menu == "⚙️ Instellingen":
    st.title("⚙️ Instellingen")
    st.session_state.sender_name = st.text_input("Afzendernaam:", st.session_state.sender_name)
    st.session_state.smtp_user = st.text_input("Afzender e-mailadres:", st.session_state.smtp_user)
    st.session_state.smtp_password = st.text_input("App-wachtwoord (16 tekens):",
                                                   st.session_state.smtp_password, type="password")
    st.session_state.serpapi_key = st.text_input("SerpApi-sleutel:", st.session_state.serpapi_key,
                                                 type="password")
    st.session_state.link = st.text_input("Link in de mail:", st.session_state.link)

    st.markdown("---")
    st.subheader("Testmail")
    test_adres = st.text_input("Testmail sturen naar:", st.session_state.smtp_user)
    if st.button("✉️ Stuur testmail"):
        onderwerp, tekst = oc.maak_mail("NL", "Voorbeeldwinkel", st.session_state.sender_name,
                                        st.session_state.link)
        ok, melding = oc.verstuur_mail(st.session_state.smtp_user, st.session_state.smtp_password,
                                       st.session_state.sender_name, test_adres.strip(),
                                       "[TEST] " + onderwerp, tekst, afmeldbaar=False)
        if ok:
            st.success("Gelukt! Kijk in de inbox van " + test_adres.strip())
        else:
            st.error("Niet gelukt: " + melding)

    st.subheader("Mailbox-controle")
    if st.button("🔎 Controleer wie we al gemaild hebben"):
        adressen, domeinen, fout = bekende_contacten()
        if fout:
            st.error(fout)
        else:
            st.success(f"Werkt. {len(adressen)} bekende adressen en {len(domeinen)} bedrijfsdomeinen "
                       "worden overgeslagen.")
