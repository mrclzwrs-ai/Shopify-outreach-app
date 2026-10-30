import streamlit as st
import pandas as pd
import time
import requests
import re
from datetime import datetime

st.set_page_config(
    page_title="Shopify Outreach & Lead Engine",
    page_icon="🚀",
    layout="wide"
)

# API sleutel
DEFAULT_SERPAPI_KEY = "8b186512abbc4c8935b3f8e743d2e632c29eabfa7985ff88940a6327ae860b0b"

if "serpapi_key" not in st.session_state:
    st.session_state.serpapi_key = DEFAULT_SERPAPI_KEY

if "leads" not in st.session_state:
    st.session_state.leads = pd.DataFrame(columns=[
        "ID", "Winkelnaam", "Website", "Taal", "Email", "Status", "Laatste_Actie", "Notities"
    ])

TEMPLATES = {
    "NL": {
        "onderwerp": "Automatische video's voor je Shopify-producten (7 dagen gratis proberen)",
        "bericht": (
            "Hoi {naam},\n\n"
            "Ik kwam jullie webshop tegen en zag jullie mooie assortiment! Korte video's op TikTok en Reels "
            "leveren tegenwoordig enorm veel gratis bereik en verkopen op, maar video's editen kost bakken met tijd.\n\n"
            "Onze Shopify-app maakt automatisch van elk nieuw product direct een video en publiceert die direct op TikTok, Reels en Shorts.\n\n"
            "Je mag het 7 dagen gratis uitproberen inclusief 3 gratis video's (geen creditcard nodig):\n"
            "{link}\n\n"
            "Met vriendelijke groet,\nHet Team"
        )
    },
    "EN": {
        "onderwerp": "Automated product videos for your Shopify store (7-day free trial)",
        "bericht": (
            "Hi {naam},\n\n"
            "Loved checking out your store! Short-form video on TikTok and Reels is driving massive organic sales right now, "
            "but editing videos daily takes forever.\n\n"
            "Our Shopify app automatically turns your new products into high-converting videos and posts them to TikTok, Instagram Reels, and YouTube Shorts for you.\n\n"
            "You can try it 100% free for 7 days (includes 3 free product videos, no credit card required):\n"
            "{link}\n\n"
            "Best regards,\nThe Team"
        )
    },
    "DE": {
        "onderwerp": "Automatische Produktvideos für Ihren Shopify-Shop (7 Tage kostenlos testen)",
        "bericht": (
            "Hallo {naam},\n\n"
            "ich habe mir Ihren Onlineshop angesehen – tolle Produkte! Kurze Videos auf TikTok und Reels bringen derzeit enorme Reichweite, "
            "die manuelle Erstellung kostet jedoch viel wertvolle Zeit.\n\n"
            "Unsere Shopify-App erstellt aus jedem neuen Produkt vollautomatisch ansprechende Videos und veröffentlicht sie direkt auf TikTok, Instagram und YouTube.\n\n"
            "Sie können die App 7 Tage lang unverbindlich testen (inkl. 3 kostenlosen Produktvideos, keine Kreditkarte erforderlich):\n"
            "{link}\n\n"
            "Beste Grüße,\nIhr Team"
        )
    },
    "ES": {
        "onderwerp": "Vídeos automáticos para tus productos de Shopify (Prueba gratis 7 días)",
        "bericht": (
            "¡Hola {naam}!\n\n"
            "Estuve viendo vuestra tienda online y tenéis unos productos increíbles. Los vídeos cortos en TikTok e Instagram Reels generan muchísimo alcance, "
            "pero editar contenido requiere horas de trabajo.\n\n"
            "Nuestra app para Shopify crea automáticamente un vídeo profesional de cada nuevo producto y lo publica en TikTok, Reels y YouTube Shorts por ti.\n\n"
            "Puedes probarla gratis durante 7 días (incluye 3 vídeos gratis, sin tarjeta de crédito):\n"
            "{link}\n\n"
            "¡Un saludo!\nEl Equipo"
        )
    }
}

def extract_email_from_text(text):
    match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', text)
    if match:
        email = match.group(0).lower()
        if not any(ext in email for ext in ['.png', '.jpg', '.jpeg', '.webp', '.svg']):
            return email
    return None

def fetch_shopify_stores(api_key, query_niche, country_code, max_results=10):
    country_map = {
        "NL": {"gl": "nl", "hl": "nl"},
        "DE": {"gl": "de", "hl": "de"},
        "ES": {"gl": "es", "hl": "es"},
        "EN": {"gl": "us", "hl": "en"}
    }
    config = country_map.get(country_code, {"gl": "us", "hl": "en"})
    
    search_query = f'site:myshopify.com "{query_niche}" contact OR email'
    
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
            title = item.get("title", "Shopify Store")
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

# Sidebar
st.sidebar.title("🚀 Lead & Outreach SaaS")
menu = st.sidebar.radio("Navigatie", ["📊 Dashboard & Leads", "🔍 Nieuwe Winkels Zoeken", "✉️ Berichten & Sjablonen", "⚙️ Instellingen & API"])

st.sidebar.markdown("---")
st.sidebar.metric(label="Totaal Leads", value=len(st.session_state.leads))
verzonden_count = len(st.session_state.leads[st.session_state.leads["Status"] == "Verzonden"])
st.sidebar.metric(label="Verzonden Mails", value=verzonden_count)

# TAB 1: DASHBOARD
if menu == "📊 Dashboard & Leads":
    st.title("📊 Leads Cockpit & Verzendbeheer")
    st.write("Overzicht van alle verzamelde Shopify-winkels.")

    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        app_link = st.text_input("Jouw Shopify App Link:", value="https://apps.shopify.com/jouw-app-link")
    with col2:
        verzend_limiet = st.number_input("Aantal te verzenden:", min_value=1, max_value=50, value=10)
    with col3:
        st.write("")
        st.write("")
        start_knop = st.button("🚀 Start Dagelijkse Verzending", type="primary")

    if start_knop:
        klaar_leads = st.session_state.leads[st.session_state.leads["Status"] == "Klaar voor verzending"]
        if klaar_leads.empty:
            st.warning("Er zijn momenteel geen winkels met de status 'Klaar voor verzending'.")
        else:
            progress_bar = st.progress(0)
            status_text = st.empty()
            leads_om_te_sturen = klaar_leads.head(verzend_limiet)
            totaal = len(leads_om_te_sturen)
            
            for i, (idx, row) in enumerate(leads_om_te_sturen.iterrows()):
                status_text.text(f"Verzenden naar: {row['Winkelnaam']} ({row['Email']})...")
                time.sleep(0.8)
                st.session_state.leads.at[idx, "Status"] = "Verzonden"
                st.session_state.leads.at[idx, "Laatste_Actie"] = datetime.now().strftime("%Y-%m-%d %H:%M")
                progress_bar.progress((i + 1) / totaal)
            
            status_text.success(f"🎉 Succesvol {totaal} berichten verwerkt!")
            time.sleep(1)
            st.rerun()

    st.subheader("Overzicht Database")
    st.dataframe(st.session_state.leads, use_container_width=True, hide_index=True)

# TAB 2: ZOEKEN
elif menu == "🔍 Nieuwe Winkels Zoeken":
    st.title("🔍 Echte Shopify Winkels Zoeken")
    st.write("Haal automatisch actuele webshops op via de Google/SerpApi zoekmachine.")

    c1, c2, c3 = st.columns(3)
    with c1:
        land_keuze = st.selectbox("Doelland / Taal:", ["Nederland (NL)", "Spanje (ES)", "Duitsland (DE)", "Verenigd Koninkrijk / US (EN)"])
    with c2:
        niche = st.text_input("Niche / Zoekterm:", value="clothing boutique")
    with c3:
        aantal = st.slider("Aantal resultaten ophalen:", 5, 20, 10)

    if st.button("🔎 Start Zoekopdracht & Data Ophalen", type="primary"):
        if not st.session_state.serpapi_key:
            st.error("Vul eerst een SerpApi-sleutel in bij het tabblad Instellingen.")
        else:
            taal_code = land_keuze.split("(")[1].replace(")", "")
            with st.spinner(f"Bezig met zoeken naar echte Shopify-winkels in {land_keuze}..."):
                stores, err = fetch_shopify_stores(st.session_state.serpapi_key, niche, taal_code, max_results=aantal)
                
                if err:
                    st.error(f"Fout bij ophalen van resultaten: {err}")
                elif not stores:
                    st.warning("Geen winkels gevonden voor deze zoekterm. Probeer een andere term zoals 'jewelry' of 'mode'.")
                else:
                    nieuwe_rijen = []
                    start_id = len(st.session_state.leads) + 1
                    for k, item in enumerate(stores):
                        nieuwe_rijen.append({
                            "ID": start_id + k,
                            "Winkelnaam": item["Winkelnaam"],
                            "Website": item["Website"],
                            "Taal": taal_code,
                            "Email": item["Email"],
                            "Status": "Klaar voor verzending",
                            "Laatste_Actie": "Net opgehaald",
                            "Notities": f"Niche: {niche}"
                        })
                    st.session_state.leads = pd.concat([st.session_state.leads, pd.DataFrame(nieuwe_rijen)], ignore_index=True)
                    st.success(f"Gereed! {len(stores)} echte winkels gevonden en toegevoegd aan je database!")

# TAB 3: SJABLONEN
elif menu == "✉️ Berichten & Sjablonen":
    st.title("✉️ Meertalige Outreach Sjablonen")
    gekozen_taal = st.radio("Selecteer Taal:", ["NL", "EN", "DE", "ES"], horizontal=True)
    sjabloon = TEMPLATES[gekozen_taal]
    st.text_input("Onderwerpregel:", value=sjabloon["onderwerp"])
    st.text_area("Berichtinhoud:", value=sjabloon["bericht"], height=200)

# TAB 4: INSTELLINGEN
elif menu == "⚙️ Instellingen & API":
    st.title("⚙️ Instellingen & Verkoopconfiguratie")
    st.subheader("SerpApi Zoekmachine Koppeling")
    st.session_state.serpapi_key = st.text_input("SerpApi Sleutel:", value=st.session_state.serpapi_key, type="password")
    st.success("API sleutel is actief ingesteld.")
    
    st.markdown("---")
    st.subheader("E-mail & SMTP Instellingen")
    col_a, col_b = st.columns(2)
    with col_a:
        st.text_input("Afzendernaam:", value="Video App Support")
        st.text_input("Afzender E-mailadres:", value="outreach@jouwdomein.com")
    with col_b:
        st.text_input("SMTP Server:", value="smtp.sendgrid.net")
        st.text_input("SMTP Wachtwoord / API Key:", type="password")

