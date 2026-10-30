import streamlit as st
import pandas as pd
import time
from datetime import datetime

# Configuratie van de pagina
st.set_page_config(
    page_title="Shopify Outreach & Lead Engine",
    page_icon="🚀",
    layout="wide"
)

# Initialisatie van data in de sessie
if "leads" not in st.session_state:
    st.session_state.leads = pd.DataFrame([
        {
            "ID": 1,
            "Winkelnaam": "Moda Barcelona",
            "Website": "https://modabarcelona-example.es",
            "Taal": "ES",
            "Email": "info@modabarcelona-example.es",
            "Status": "Klaar voor verzending",
            "Laatste_Actie": "-",
            "Notities": "Boetiek kleding"
        },
        {
            "ID": 2,
            "Winkelnaam": "Berliner Sneaker Loft",
            "Website": "https://sneakerloft-berlin-example.de",
            "Taal": "DE",
            "Email": "contact@sneakerloft-example.de",
            "Status": "Klaar voor verzending",
            "Laatste_Actie": "-",
            "Notities": "Streetwear"
        },
        {
            "ID": 3,
            "Winkelnaam": "Amsterdam Juwelen",
            "Website": "https://amsterdam-juwelen-example.nl",
            "Taal": "NL",
            "Email": "hallo@amsterdamjuwelen-example.nl",
            "Status": "Klaar voor verzending",
            "Laatste_Actie": "-",
            "Notities": "Handgemaakte ringen"
        },
        {
            "ID": 4,
            "Winkelnaam": "London Glow Skincare",
            "Website": "https://londonglow-example.co.uk",
            "Taal": "EN",
            "Email": "support@londonglow-example.co.uk",
            "Status": "Klaar voor verzending",
            "Laatste_Actie": "-",
            "Notities": "Cosmetica drops"
        }
    ])

# 4 Meertalige sjablonen
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

# Navigatie / Menu aan de zijkant
st.sidebar.title("🚀 Lead & Outreach SaaS")
menu = st.sidebar.radio("Navigatie", ["📊 Dashboard & Leads", "🔍 Nieuwe Winkels Zoeken", "✉️ Berichten & Sjablonen", "⚙️ Instellingen & API"])

st.sidebar.markdown("---")
st.sidebar.metric(label="Totaal Leads", value=len(st.session_state.leads))
verzonden_count = len(st.session_state.leads[st.session_state.leads["Status"] == "Verzonden"])
st.sidebar.metric(label="Verzonden Mails", value=verzonden_count)

# TAB 1: DASHBOARD & LEADS
if menu == "📊 Dashboard & Leads":
    st.title("📊 Leads Cockpit & Verzendbeheer")
    st.write("Bekijk alle verzamelde Shopify-winkels, filter op taal of status en verstuur de dagelijkse campagne.")

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
                status_text.text(f"Bezig met verzenden naar: {row['Winkelnaam']} ({row['Email']}) in taal [{row['Taal']}]...")
                time.sleep(0.8)
                
                st.session_state.leads.at[idx, "Status"] = "Verzonden"
                st.session_state.leads.at[idx, "Laatste_Actie"] = datetime.now().strftime("%Y-%m-%d %H:%M")
                
                progress_bar.progress((i + 1) / totaal)
            
            status_text.success(f"🎉 Succesvol {totaal} gepersonaliseerde e-mails verzonden!")
            time.sleep(1)
            st.rerun()

    st.subheader("Overzicht Database")
    st.dataframe(
        st.session_state.leads,
        use_container_width=True,
        hide_index=True
    )

# TAB 2: WINKELS ZOEKEN
elif menu == "🔍 Nieuwe Winkels Zoeken":
    st.title("🔍 Automatische Shopify Finder")
    st.write("Laat de zoekmachine automatisch nieuwe Shopify-webshops vinden per land en niche.")

    c1, c2, c3 = st.columns(3)
    with c1:
        land_keuze = st.selectbox("Kies Doelland / Taal:", ["Nederland (NL)", "Spanje (ES)", "Duitsland (DE)", "Verenigd Koninkrijk / US (EN)"])
    with c2:
        niche = st.text_input("Niche / Productcategorie:", value="Sieraden, Mode, Woonaccessoires")
    with c3:
        aantal = st.slider("Aantal te scrapen winkels:", 10, 50, 25)

    if st.button("🔎 Start Zoekopdracht & Data Ophalen", type="primary"):
        with st.spinner("Scraper zoekt naar Shopify-winkels en extraheert contact-e-mails..."):
            time.sleep(1.5)
            taal_code = land_keuze.split("(")[1].replace(")", "")
            nieuwe_rijen = []
            start_id = len(st.session_state.leads) + 1
            for k in range(3):
                nieuwe_rijen.append({
                    "ID": start_id + k,
                    "Winkelnaam": f"Demo Shop {start_id + k}",
                    "Website": f"https://shop{start_id + k}.myshopify.com",
                    "Taal": taal_code,
                    "Email": f"contact@shop{start_id + k}.com",
                    "Status": "Klaar voor verzending",
                    "Laatste_Actie": "Nieuw toegevoegd",
                    "Notities": f"Gevonden in niche: {niche}"
                })
            st.session_state.leads = pd.concat([st.session_state.leads, pd.DataFrame(nieuwe_rijen)], ignore_index=True)
            st.success("Gereed! 3 nieuwe winkels gevonden en toegevoegd aan je database met status 'Klaar voor verzending'.")

# TAB 3: BERICHTEN & SJABLONEN
elif menu == "✉️ Berichten & Sjablonen":
    st.title("✉️ Meertalige Outreach Sjablonen")
    st.write("Bekijk en bewerk de teksten die automatisch per taal worden verzonden.")

    gekozen_taal = st.radio("Selecteer Taal:", ["NL", "EN", "DE", "ES"], horizontal=True)
    sjabloon = TEMPLATES[gekozen_taal]

    st.text_input("Onderwerpregel:", value=sjabloon["onderwerp"])
    st.text_area("Berichtinhoud (met variabelen {naam} en {link}):", value=sjabloon["bericht"], height=200)

    st.info("💡 Tip: Het programma vervangt {naam} automatisch door de winkelnaam en {link} door jouw Shopify-app link.")

# TAB 4: INSTELLINGEN
elif menu == "⚙️ Instellingen & API":
    st.title("⚙️ Instellingen & Verkoopconfiguratie")
    st.write("Stel je eigen verzendgegevens in, of activeer licentiesleutels voor klanten die jouw tool kopen.")

    st.subheader("E-mail & SMTP Instellingen")
    col_a, col_b = st.columns(2)
    with col_a:
        st.text_input("Afzendernaam:", value="Video App Support")
        st.text_input("Afzender E-mailadres:", value="outreach@jouwdomein.com")
    with col_b:
        st.text_input("SMTP Server (bijv. Gmail / SendGrid):", value="smtp.sendgrid.net")
        st.text_input("SMTP Wachtwoord / API Key:", type="password")

    st.subheader("Verkoop & Licentiebeheer (SaaS optie)")
    st.write("Als je deze tool doorverkoopt aan anderen, kun je hier gebruikerslicenties genereren.")
    st.text_input("Licentiesleutel van klant:", value="LIC-2026-X892-PRO", disabled=True)
    st.success("Licentiestatus: Actief (Pro Plan - Onbeperkt)")
