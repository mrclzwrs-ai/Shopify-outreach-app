import time
from datetime import datetime

import pandas as pd
import streamlit as st

import importlib

import outreach_core as oc

# Na een update altijd de nieuwste versie van de zoekmotor gebruiken (geen herstart nodig).
oc = importlib.reload(oc)

st.set_page_config(page_title="ShopReels Outreach", page_icon="◆", layout="wide")

# Cockpit-stijl: donker, strak, turquoise accent, oranje voor "let op".
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500&family=JetBrains+Mono:wght@400;500&display=swap');
        :root { --cp-bg:#0A0F14; --cp-paneel:#111A22; --cp-lijn:#1B2631; --cp-tekst:#DCE7F0;
                --cp-grijs:#7FA3BF; --cp-turq:#3FE0C5; --cp-oranje:#F5A623; }
        html, body, [class*="css"] { font-size: 19px !important; font-family: 'Inter', sans-serif !important; }
        .stApp { background: var(--cp-bg) !important; }
        header[data-testid="stHeader"] { background: transparent !important; }

        h1, h2, h3 { font-family: 'JetBrains Mono', monospace !important; font-weight: 500 !important;
                     letter-spacing: 1px; color: var(--cp-tekst) !important; }
        h1 { font-size: 1.9rem !important; text-transform: uppercase;
             border-bottom: 1px solid var(--cp-lijn); padding-bottom: 0.6rem !important; }
        h2, h3 { font-size: 1.3rem !important; color: var(--cp-grijs) !important; text-transform: uppercase; }
        label p { font-size: 1.05rem !important; font-weight: 500 !important; color: var(--cp-grijs) !important; }

        section[data-testid="stSidebar"] { background: #070B0F !important; border-right: 1px solid var(--cp-lijn); }
        section[data-testid="stSidebar"] h1 { font-size: 1.1rem !important; color: var(--cp-turq) !important;
                                              border-bottom: none; }

        div[data-testid="stMetric"] { background: var(--cp-paneel); border: 1px solid var(--cp-lijn);
                                      border-radius: 10px; padding: 14px 16px; }
        span[data-baseweb="tag"], span[data-baseweb="tag"] * { color: #0A0F14 !important; }
        [data-testid="stMetricLabel"], [data-testid="stMetricLabel"] * { font-family: 'JetBrains Mono', monospace !important;
                                             text-transform: uppercase; font-size: 0.8rem !important;
                                             color: var(--cp-grijs) !important; letter-spacing: 1px; }
        div[data-testid="stMetricValue"] { font-family: 'JetBrains Mono', monospace !important;
                                           color: var(--cp-turq) !important; font-size: 2.4rem !important; }

        .stButton>button, .stDownloadButton>button {
            font-family: 'JetBrains Mono', monospace !important; text-transform: uppercase; letter-spacing: 1px;
            font-size: 1.05rem !important; padding: 0.65rem 1.3rem !important; border-radius: 8px !important;
            font-weight: 500 !important; background: transparent !important;
            border: 1px solid var(--cp-turq) !important; color: var(--cp-turq) !important; }
        .stButton>button:hover, .stDownloadButton>button:hover {
            background: rgba(63,224,197,0.12) !important; }
        .stButton>button[kind="primary"] { background: var(--cp-turq) !important; color: var(--cp-bg) !important; }
        .stButton>button[kind="primary"]:hover { background: #6BEBD5 !important; }

        div[data-testid="stProgress"] div[role="progressbar"] > div > div { background: var(--cp-turq) !important; }
        div[data-testid="stDataFrame"], div[data-testid="stDataEditor"] {
            border: 1px solid var(--cp-lijn); border-radius: 10px; }
        div[data-testid="stExpander"] { border: 1px solid var(--cp-lijn) !important; border-radius: 10px;
                                        background: var(--cp-paneel); }
        code, pre { font-family: 'JetBrains Mono', monospace !important; }
        hr { border-color: var(--cp-lijn) !important; }
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
st.sidebar.title("SHOPREELS / OUTREACH")
menu = st.sidebar.radio("Kies een pagina", [
    "Winkels zoeken",
    "Versturen",
    "De mail",
    "Automatisch",
    "Instellingen",
])
leads = st.session_state.leads
st.sidebar.markdown("---")
st.sidebar.metric("Gevonden", len(leads))
if len(leads):
    st.sidebar.metric("Verstuurd", int((leads["Status"] == "Verstuurd").sum()))


# ---------------------------------------------------------------------------
if menu == "Winkels zoeken":
    st.title("Winkels zoeken")
    st.write("De app zoekt Shopify-winkels, kijkt op hun eigen site of het een echte winkel met "
             "producten is, en zoekt daar een **echt** e-mailadres. Winkels zonder adres, en winkels "
             "die we al eens gemaild hebben, worden overgeslagen.")

    bron = st.radio("Waar zoeken?", ["Shopify-lijst (gratis, alle soorten winkels)", "Google (kost zoekopdrachten)"],
                    horizontal=True)
    lijst = bron.startswith("Shopify")

    if lijst:
        landen = st.multiselect("Landen:", list(oc.MARKTEN.keys()), default=["NL", "BE", "US", "UK"],
                                format_func=lambda k: oc.MARKTEN[k]["naam"])
        niche = st.text_input("Branche (mag leeg blijven = alle soorten winkels):", value="")
        st.caption("De mail gaat automatisch in de taal van het land. Let op: Nederlandse en Belgische "
                   "winkels zijn er veel minder dan Amerikaanse, dus die komen minder vaak voorbij.")
    else:
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
    aantal = int(st.number_input("Hoeveel winkels wil je vinden? (1 tot 20)", min_value=1, max_value=20, value=5, step=1))
    if not lijst:
        st.caption("Elke zoekronde kost 1 van je SerpApi-zoekopdrachten. De app doet er maximaal 3.")

    if st.button("Zoeken", type="primary"):
        if not lijst and not st.session_state.serpapi_key:
            st.error("Er is nog geen SerpApi-sleutel. Zet hem in de kluis of bij Instellingen.")
        elif lijst and not landen:
            st.error("Kies minstens één land.")
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

            with st.spinner("Winkels zoeken en bekijken... (dit duurt een paar minuten, laat de pagina open)"):
                if lijst:
                    gevonden, overgeslagen, gebruikt, fout = oc.zoek_leads_shopifylijst(
                        max_leads=aantal, landen=landen, niche=niche.strip(),
                        bekende_adressen=adressen, bekende_domeinen=domeinen, log=log)
                else:
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
                "Land": l.get("markt", ""),
                "Taal": l["taal"],
                "Branche": l.get("niche", niche) or "alles",
                "Status": "Klaar",
                "Domein": l["domein"],
            } for l in gevonden])
            st.session_state.leads = pd.concat([st.session_state.leads, nieuw], ignore_index=True)
            tekst = f"{len(gevonden)} winkels met een echt adres gevonden. {len(overgeslagen)} overgeslagen."
            if not lijst:
                tekst += f" ({gebruikt} zoekopdrachten gebruikt)"
            st.success(tekst)
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
elif menu == "Versturen":
    st.title("Versturen")
    leads = st.session_state.leads
    if not len(leads):
        st.info("Zoek eerst winkels op de pagina Winkels zoeken.")
    else:
        klaar = leads[(leads["Status"] == "Klaar") & (leads["Versturen"])]
        st.write(f"Er staan **{len(klaar)}** winkels klaar met een vinkje.")
        st.caption("Tussen elke mail wacht de app ongeveer een halve minuut, zodat Gmail je "
                   "adres niet als spam ziet. Houd deze pagina open tot hij klaar is.")
        hoeveel = st.number_input("Hoeveel nu versturen?", 1, 25, min(10, max(1, len(klaar))))
        if st.button("Start", type="primary", disabled=len(klaar) == 0):
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
        st.download_button("Lijst downloaden (CSV)",
                           leads.to_csv(index=False).encode("utf-8"),
                           f"leads-{datetime.now():%Y-%m-%d}.csv", "text/csv")


# ---------------------------------------------------------------------------
elif menu == "De mail":
    st.title("Zo ziet de mail eruit")
    gekozen = st.radio("Taal:", ["NL", "EN", "DE", "ES"], horizontal=True)
    onderwerp, tekst = oc.maak_mail(gekozen, "Voorbeeldwinkel", st.session_state.sender_name,
                                    st.session_state.link)
    st.text_input("Onderwerp:", value=onderwerp, disabled=True)
    st.text_area("Tekst:", value=tekst, height=420, disabled=True)
    st.caption("De winkelnaam wordt automatisch ingevuld. Elke mail heeft onderaan een afmeldregel; "
               "wie antwoordt (ook met 'afmelden') krijgt nooit meer een mail van de app.")


# ---------------------------------------------------------------------------
elif menu == "Automatisch":
    st.title("Automatisch elke werkdag")
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
    if INST.get("bron", "shopify-lijst") == "google":
        for taal, lijst in INST.get("branches", {}).items():
            if any(oc.MARKTEN[m]["taal"] == taal for m in INST.get("markten", [])):
                st.write(f"**Branches ({taal}):** " + ", ".join(lijst))
    else:
        st.write("**Soort winkels:** alle soorten (uit de gratis Shopify-lijst)")
    st.caption("Wil je iets veranderen (aanzetten, ander aantal, andere branches)? Vraag het Claude.")


# ---------------------------------------------------------------------------
elif menu == "Instellingen":
    st.title("Instellingen")
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
    if st.button("Stuur testmail"):
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
    if st.button("Controleer wie we al gemaild hebben"):
        adressen, domeinen, fout = bekende_contacten()
        if fout:
            st.error(fout)
        else:
            st.success(f"Werkt. {len(adressen)} bekende adressen en {len(domeinen)} bedrijfsdomeinen "
                       "worden overgeslagen.")
