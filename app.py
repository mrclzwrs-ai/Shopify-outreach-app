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

# iPad-vriendelijke styling voor grotere letters en knoppen
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

# API sleutel
DEFAULT_SERPAPI_KEY = "8b186512abbc4c8935b3f8e743d2e632c29eabfa7985ff88940a6327ae860b0b"

if "serpapi_key" not in st.session_state:
    st.session_state.serpapi_key = DEFAULT_SERPAPI_KEY

# SMTP sessiestatus
if "smtp_server" not in st.session_state:
    st.session_state.smtp_server = "smtp.gmail.com"
if "smtp_port" not in st.session_state:
    st.session_state.smtp_port = 465
if "smtp_user" not in st.session_state:
    st.session_state.smtp_user = "Info@shopreelsapp.com"
if "smtp_password" not in st.session_state:
    st.session_state.smtp_password = ""
if "sender_name" not in st.session_state:
    st.session_state.sender_name = "Video App Support"

if "leads" not in st.session_state:
    st.session_state.leads = pd.DataFrame(columns=[
        "ID", "Winkelnaam", "Platform", "Website", "Taal", "Email", "Status", "Laatste_Actie", "Notities"
    ])

TEMPLATES = {
    "NL": {
        "onderwerp": "Automatische video's voor je webshop (7 dagen gratis proberen)",
        "bericht": (
            "Hoi {naam},\n\n"
            "Ik kwam jullie webshop tegen en zag jullie mooie assortiment! Korte video's op TikTok en Reels "
            "leveren tegenwoordig enorm veel gratis bereik en verkopen op, maar video's editen kost bakken met tijd.\n\n"
            "Onze software maakt automatisch van elk nieuw product direct een professionele video en publiceert die direct op TikTok, Reels en Shorts.\n\
