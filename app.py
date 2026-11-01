import streamlit as st
import pandas as pd
import time
import requests
import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

st.set_page_config(
    page_title="Universal Lead & Outreach Engine",
    page_icon="🚀",
    layout="wide"
)

st.markdown("""
    <style>
        html, body, [class*="css"] {
            font-size: 19px !important;
        }
        h1 {
            font-size: 2.2rem !important;
            font-weight: 700 !important;
            margin-bottom: 0.8rem !important;
        }
        h2, h3 {
            font-size: 1.5rem !important;
            font-weight: 600 !important;
        }
        .stButton>button {
            font-size: 1.15rem !important;
            padding: 0.6rem 1.2rem !important;
            border-radius: 8px !important;
            font-weight: 600 !important;
        }
        .stTextInput>div>div>input, .stSelectbox>div>div>div {
            font-size: 1.1rem !important;
            padding: 0.5rem !important;
        }
        label p {
            font-size: 1.15rem !important;
            font-weight: 600 !important;
        }
    </style>
""", unsafe_allow_html=True)

DEFAULT_SERPAPI_KEY = ""

def kluis(naam, standaard):
    """Haalt een instelling uit de Streamlit-kluis (Secrets). Staat hij daar niet, dan de standaardwaarde."""
    try:
        if naam in st.secrets:
            return st.secrets[naam]
    except Exception:
        pass
    return standaard

if "serpapi_key" not in st.session_state:
    st.session_state.serpapi_key = kluis("serpapi_key", DEFAULT_SERPAPI_KEY)

if "smtp_server" not in st.session_state:
    st.session_state.smtp_server = kluis("smtp_server", "smtp.gmail.com")
if "smtp_port" not in st.session_state:
    st.session_state.smtp_port = int(kluis("smtp_port", 465))
if "smtp_user" not in st.session_state:
    st.session_state.smtp_user = kluis("smtp_user", "Info@shopreelsapp.com")
if "smtp_password" not in st.session_state:
    st.session_state.smtp_password = kluis("smtp_password", "")
if "sender_name" not in st.session_state:
    st.session_state.sender_name = kluis("sender_name", "Video App Support")

if "leads" not in st.session_state:
    st.session_state.leads = pd.DataFrame(columns=[
        "ID", "Winkelnaam", "Platform", "Website", "Taal", "Email", "Status", "Laatste_Actie", "Notities"
    ])

TEMPLATES = {
    "NL": {
        "onderwerp": "Automatische video's voor je webshop (7 dagen gratis proberen)",
        "bericht": "Hoi {naam},\n\nIk kwam jullie webshop tegen en zag het mooie assortiment! Korte video's op TikTok en Reels leveren tegenwoordig enorm veel gratis bereik en verkopen op, maar video's editen kost bakken met tijd.\n\nOnze software maakt automatisch van elk nieuw product direct een professionele video en publiceert die op TikTok, Reels en Shorts.\n\nJe mag het 7 dagen gratis uitproberen inclusief 3 gratis video's (geen creditcard nodig):\n{link}\n\nMet vriendelijke groet,\n{afzender}"
    },
    "EN": {
        "onderwerp": "Automated product videos for your online store (7-day free trial)",
        "bericht": "Hi {naam},\n\nLoved checking out your store! Short-form video on TikTok and Reels is driving massive organic sales right now, but editing videos daily takes forever.\n\nOur automated video tool turns your new products into high-converting videos and posts them to TikTok, Instagram Reels, and YouTube Shorts for you.\n\nTry it 100% free for 7 days (includes 3 free product videos, no credit card required):\n{link}\n\nBest regards,\n{afzender}"
    },
    "DE": {
        "onderwerp": "Automatische Produktvideos für Ihren Onlineshop (7 Tage kostenlos testen)",
        "bericht": "Hallo {naam},\n\nich habe mir Ihren Onlineshop angesehen – tolle Produkte! Kurze Videos auf TikTok und Reels bringen derzeit enorme Reichweite, die Erstellung kostet jedoch viel Zeit.\n\nUnsere Software erstellt aus jedem neuen Produkt vollautomatisch Videos und veröffentlicht sie direkt auf TikTok, Instagram und YouTube.\n\nSie können die Lösung 7 Tage lang unverbindlich testen (inkl. 3 Gratisvideos, keine Kreditkarte nötig):\n{link}\n\nBeste Grüße,\n{afzender}"
    },
    "ES": {
        "onderwerp": "Vídeos automáticos para tu tienda online (Prueba gratis 7 días)",
        "bericht": "¡Hola {naam}!\n\nEstuve viendo vuestra tienda online y tenéis unos productos increíbles. Los vídeos cortos en TikTok e Instagram Reels generan muchísimo alcance, pero editar contenido requiere horas de trabajo.\n\nNuestra herramienta crea automáticamente un vídeo profesional de cada nuevo producto y lo publica en TikTok, Reels y Shorts por ti.\n\nPuedes probarla gratis durante 7 días (incluye 3 vídeos gratis, sin tarjeta de crédito):\n{link}\n\n¡Un saludo!\n{afzender}"
    }
}

def extract_email_from_text(text):
    match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', text)
    if match:
        email = match.group(0).lower()
        if not any(ext in email for ext in ['.png', '.jpg', '.jpeg', '.webp', '.svg']):
            return email
    return None

def fetch_stores(api_key, platform_type, query_niche, country_code, max_results=10):
    country_map = {
        "NL": {"gl": "nl", "hl": "nl"},
        "DE": {"gl": "de", "hl": "de"},
        "ES": {"gl": "es", "hl": "es"},
        "EN": {"gl": "us", "hl": "en"}
    }
    config = country_map.get(country_code, {"gl": "us", "hl": "en"})
    
    if platform_type == "Shopify":
        platform_filter = 'site:myshopify.com'
    elif platform_type == "WooCommerce":
        platform_filter = '"powered by woocommerce" OR inurl:wp-content'
    elif platform_type == "Lightspeed":
        platform_filter = 'site:webshopapp.com OR "powered by lightspeed"'
    else:
        platform_filter = 'webwinkel OR webshop OR "winkelmandje"'

    search_query = f'{platform_filter} "{query_niche}" contact OR email'
    
    url = "https://serpapi.com/search.json"
    params = {
        "engine": "google",
        "q": search_query,
        "api_key": api_key,
        "num": max_results,
        "gl": config["gl"],
        "hl": config["hl"]
    }
    
    try:
        response = requests.get(url, params=params, timeout=15)
        data = response.json()
        
        if "error" in data:
            return [], data["error"]
            
        organic_results = data.get("organic_results", [])
        extracted_stores = []
        
        for item in organic_results:
            title = item.get("title", "Online Winkel")
            clean_name = title.split("-")[0].split("|")[0].split(":")[0].strip()
            link = item.get("link", "")
            snippet = item.get("snippet", "")
            
            email = extract_email_from_text(snippet) or f"contact@{clean_name.lower().replace(' ', '')}.com"
            
            extracted_stores.append({
                "Winkelnaam": clean_name,
                "Website": link,
                "Email": email,
                "Snippet": snippet
            })
            
        return extracted_stores, None
    except Exception as e:
        return [], str(e)

def send_real_email(smtp_server, smtp_port, sender_email, sender_password, sender_name, recipient_email, subject, body_text):
    clean_email = sender_email.strip()
    clean_password = sender_password.replace(" ", "").strip()
    port = int(smtp_port)

    msg = MIMEMultipart()
    msg['From'] = f"{sender_name} <{clean_email}>"
    msg['To'] = recipient_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body_text, 'plain', 'utf-8'))
    
    try:
        if port == 465:
            server = smtplib.SMTP_SSL(smtp_server, port, timeout=20)
        else:
            server = smtplib.SMTP(smtp_server, port, timeout=20)
            server.starttls()
            
        server.login(clean_email, clean_password)
        server.send_message(msg)
        server.quit()
        return True, "Verzonden"
    except Exception as ex:
        return False, str(ex)

st.sidebar.title("🚀 Outreach Engine")
menu = st.sidebar.radio("Navigatie", ["📊 Dashboard & Leads", "🔍 Leads Genereren", "✉️ Berichten & Sjablonen", "⚙️ Instellingen & Verkoop"])

st.sidebar.markdown("---")
st.sidebar.metric(label="Totaal Leads", value=len(st.session_state.leads))
verzonden_count = len(st.session_state.leads[st.session_state.leads["Status"] == "Verzonden"])
st.sidebar.metric(label="Verzonden Mails", value=verzonden_count)

if menu == "📊 Dashboard & Leads":
    st.title("📊 Leads Cockpit & Verzendbeheer")
    st.write("Beheer al je potentiële klanten en start gerichte outreach-campagnes.")

    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        app_link = st.text_input("Jouw Aanbod / Website Link:", value="https://apps.shopify.com/jouw-app-link")
    with col2:
        verzend_limiet = st.number_input("Aantal te verzenden:", min_value=1, max_value=50, value=1)
    with col3:
        st.write("")
        st.write("")
        start_knop = st.button("🚀 Start Verzending", type="primary")

    if start_knop:
        klaar_leads = st.session_state.leads[st.session_state.leads["Status"] == "Klaar voor verzending"]
        if klaar_leads.empty:
            st.warning("Er zijn momenteel geen contacten met de status 'Klaar voor verzending'.")
        elif not st.session_state.smtp_user or not st.session_state.smtp_password:
            st.error("Vul eerst je app-wachtwoord in bij Instellingen & Verkoop!")
        else:
            progress_bar = st.progress(0)
            status_text = st.empty()
            leads_om_te_sturen = klaar_leads.head(verzend_limiet)
            totaal = len(leads_om_te_sturen)
            
            for i, (idx, row) in enumerate(leads_om_te_sturen.iterrows()):
                status_text.text(f"Versturen naar {row['Winkelnaam']} ({row['Email']})...")
                
                lang = row.get("Taal", "NL")
                tpl = TEMPLATES.get(lang, TEMPLATES["NL"])
                subject = tpl["onderwerp"]
                body = tpl["bericht"].format(
                    naam=row["Winkelnaam"],
                    link=app_link,
                    afzender=st.session_state.sender_name
                )
                
                success, msg = send_real_email(
                    st.session_state.smtp_server,
                    st.session_state.smtp_port,
                    st.session_state.smtp_user,
                    st.session_state.smtp_password,
                    st.session_state.sender_name,
                    row["Email"],
                    subject,
                    body
                )
                
                if success:
                    st.session_state.leads.at[idx, "Status"] = "Verzonden"
                    st.session_state.leads.at[idx, "Laatste_Actie"] = datetime.now().strftime("%Y-%m-%d %H:%M")
                    st.session_state.leads.at[idx, "Notities"] = "Succesvol verzonden"
                else:
                    st.session_state.leads.at[idx, "Status"] = "Mislukt"
                    st.session_state.leads.at[idx, "Notities"] = f"Fout: {msg[:60]}"
                
                time.sleep(1.0)
                progress_bar.progress((i + 1) / totaal)
            
            status_text.success("Campagne verwerkt!")
            time.sleep(1.5)
            st.rerun()

    st.subheader("Overzicht Database")
    st.dataframe(st.session_state.leads, use_container_width=True, hide_index=True)

elif menu == "🔍 Leads Genereren":
    st.title("🔍 Leads Genereren")
    st.write("Vind automatisch winkels binnen elk gewenst platform, land en markt.")

    c1, c2 = st.columns(2)
    with c1:
        platform = st.selectbox("Type Webwinkel / Platform:", ["Shopify", "WooCommerce", "Lightspeed", "Alle Webwinkels (Algemeen)"])
        land_keuze = st.selectbox("Doelland / Markt:", ["Nederland (NL)", "Spanje (ES)", "Duitsland (DE)", "Verenigd Koninkrijk / US (EN)"])
    with c2:
        niche = st.text_input("Branche / Zoekterm:", value="Kleding branche")
        aantal = st.slider("Aantal winkels ophalen:", 5, 25, 10)

    if st.button("🔎 Start Lead Generatie", type="primary"):
        if not st.session_state.serpapi_key:
            st.error("Stel eerst een geldige zoek-sleutel in bij het tabblad Instellingen.")
        else:
            taal_code = land_keuze.split("(")[1].replace(")", "")
            with st.spinner(f"Bezig met zoeken naar {platform} winkels in {land_keuze}..."):
                stores, err = fetch_stores(st.session_state.serpapi_key, platform, niche, taal_code, max_results=aantal)
                
                if err:
                    st.error(f"Fout bij ophalen van resultaten: {err}")
                elif not stores:
                    st.warning("Geen winkels gevonden voor deze zoekopdracht.")
                else:
                    nieuwe_rijen = []
                    start_id = len(st.session_state.leads) + 1
                    for k, item in enumerate(stores):
                        nieuwe_rijen.append({
                            "ID": start_id + k,
                            "Winkelnaam": item["Winkelnaam"],
                            "Platform": platform,
                            "Website": item["Website"],
                            "Taal": taal_code,
                            "Email": item["Email"],
                            "Status": "Klaar voor verzending",
                            "Laatste_Actie": "Net toegevoegd",
                            "Notities": f"Niche: {niche}"
                        })
                    st.session_state.leads = pd.concat([st.session_state.leads, pd.DataFrame(nieuwe_rijen)], ignore_index=True)
                    st.success(f"Voltooid! {len(stores)} winkels gevonden en toegevoegd aan je database!")

elif menu == "✉️ Berichten & Sjablonen":
    st.title("✉️ Meertalige Outreach Sjablonen")
    st.write("Bekijk of bewerk de automatische introductieberichten per taalregio.")
    gekozen_taal = st.radio("Selecteer Taal:", ["NL", "EN", "DE", "ES"], horizontal=True)
    sjabloon = TEMPLATES[gekozen_taal]
    st.text_input("Onderwerpregel:", value=sjabloon["onderwerp"])
    st.text_area("Berichtinhoud:", value=sjabloon["bericht"], height=230)

elif menu == "⚙️ Instellingen & Verkoop":
    st.title("⚙️ Configuratie & Licentiebeheer")
    st.write("Beheer systeemverbindingen en instellingen voor verkoop.")
    
    st.subheader("Zoekmachine Koppeling")
    st.session_state.serpapi_key = st.text_input("Zoek API Sleutel:", value=st.session_state.serpapi_key, type="password")
    
    st.markdown("---")
    st.subheader("E-mail & SMTP Instellingen")
    col_a, col_b = st.columns(2)
    with col_a:
        st.session_state.sender_name = st.text_input("Afzendernaam:", value=st.session_state.sender_name)
        st.session_state.smtp_user = st.text_input("Afzender E-mailadres:", value=st.session_state.smtp_user)
        st.session_state.smtp_password = st.text_input("E-mail App-Wachtwoord (16 tekens):", value=st.session_state.smtp_password, type="password")
    with col_b:
        st.session_state.smtp_server = st.text_input("SMTP Server:", value=st.session_state.smtp_server)
        st.session_state.smtp_port = st.number_input("SMTP Poort (standaard 465 voor SSL):", value=st.session_state.smtp_port)

    st.markdown("---")
    st.subheader("Verbinding testen")
    st.write("Stuur eerst één testmail, zodat je zeker weet dat alles werkt voordat je klanten gaat mailen.")
    test_adres = st.text_input("Testmail sturen naar:", value=st.session_state.smtp_user)
    if st.button("✉️ Stuur testmail"):
        if not st.session_state.smtp_password:
            st.error("Er is nog geen app-wachtwoord ingevuld (in de kluis of hierboven).")
        else:
            ok, melding = send_real_email(
                st.session_state.smtp_server, st.session_state.smtp_port,
                st.session_state.smtp_user, st.session_state.smtp_password,
                st.session_state.sender_name, test_adres.strip(),
                "Testmail Outreach Engine", "Het werkt! Je Outreach Engine kan mails versturen."
            )
            if ok:
                st.success("Gelukt! Kijk in de inbox van " + test_adres.strip() + " (en voor de zekerheid ook in Spam).")
            else:
                st.error("Niet gelukt. Melding van de mailserver: " + melding)
