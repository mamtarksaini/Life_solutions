import firebase_admin
from firebase_admin import credentials, firestore
import streamlit as st

# Load Firebase secrets from Streamlit secrets
firebase_secrets = st.secrets["firebase"]

# Fix private key formatting
firebase_secrets_dict = {
    "type": firebase_secrets["type"],
    "project_id": firebase_secrets["project_id"],
    "private_key_id": firebase_secrets["private_key_id"],
    "private_key": firebase_secrets["private_key"].replace("\\n", "\n"),  # 🔹 Fix formatting!
    "client_email": firebase_secrets["client_email"],
    "client_id": firebase_secrets["client_id"],
    "auth_uri": firebase_secrets["auth_uri"],
    "token_uri": firebase_secrets["token_uri"],
    "auth_provider_x509_cert_url": firebase_secrets["auth_provider_x509_cert_url"],
    "client_x509_cert_url": firebase_secrets["client_x509_cert_url"],
    "universe_domain": firebase_secrets["universe_domain"]
}

try:
    # **Check if Firebase is already initialized**
    if not firebase_admin._apps:  # 🔹 This ensures we don't initialize twice
        cred = credentials.Certificate(firebase_secrets_dict)
        firebase_admin.initialize_app(cred)

    # **Initialize Firestore**
    db = firestore.client()
   # st.success("✅ Firebase Initialized Successfully!")

except Exception as e:
    st.error(f"❌ Firebase Initialization Failed: {e}")
    db = None
