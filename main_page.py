import streamlit as st
import firebase_admin
from firebase_admin import firestore
from firebase_config import db
from datetime import datetime, timedelta
import requests
import os
import paypalrestsdk
from gtts import gTTS  # ✅ Using gTTS for free TTS

# Load API Key securely from Streamlit secrets
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]

# PayPal Configuration from Streamlit secrets
paypalrestsdk.configure({
    "mode": "sandbox",  # Change to 'live' for production
    "client_id": st.secrets["paypal"]["PAYPAL_CLIENT_ID"],
    "client_secret": st.secrets["paypal"]["PAYPAL_CLIENT_SECRET"]
})

# Constants
FREE_MONTHLY_QUERIES = 10
SUBSCRIBER_MONTHLY_QUERIES = 100
SUBSCRIPTION_COST = 7

# ✅ Check user eligibility
def check_user_eligibility(email):
    user_ref = db.collection("users").document(email)
    user_doc = user_ref.get()

    if not user_doc.exists:
        user_ref.set({"queries": 0, "last_query_date": None, "plan": "free"})
        return True, FREE_MONTHLY_QUERIES, "Free"

    user_data = user_doc.to_dict()
    queries = user_data.get("queries", 0)
    last_query_date = user_data.get("last_query_date")
    plan = user_data.get("plan", "free")
    limit = FREE_MONTHLY_QUERIES if plan == "free" else SUBSCRIBER_MONTHLY_QUERIES

    if last_query_date:
        last_date = datetime.strptime(last_query_date, "%Y-%m-%d")
        if datetime.now() - last_date > timedelta(days=30):
            user_ref.update({"queries": 0, "last_query_date": datetime.now().strftime("%Y-%m-%d")})
            return True, limit, plan

    return queries < limit, limit - queries, plan

# ✅ Create PayPal Payment
def create_paypal_payment():
    payment = paypalrestsdk.Payment({
        "intent": "sale",
        "payer": {"payment_method": "paypal"},
        "redirect_urls": {
            "return_url": "https://shrikrishna.streamlit.app/?page=success",
            "cancel_url": "https://shrikrishna.streamlit.app/?page=cancel"
        },
        "transactions": [{
            "amount": {"total": str(SUBSCRIPTION_COST), "currency": "USD"},
            "description": "Upgrade to Premium Plan"
        }]
    })

    if payment.create():
        for link in payment.links:
            if link.rel == "approval_url":
                return link.href  # ✅ PayPal redirects with `paymentId` & `PayerID`
    return None

# ✅ Capture PayPal Payment
def payment_success():
    st.title("✅ Payment Successful!")

    # ✅ Get Payment ID & Payer ID from URL Parameters
    query_params = st.query_params  # 🔹 Fixed deprecated function

    if "paymentId" in query_params and "PayerID" in query_params:
        payment_id = query_params["paymentId"]
        payer_id = query_params["PayerID"]

        payment = paypalrestsdk.Payment.find(payment_id)

        if payment.execute({"payer_id": payer_id}):  # ✅ Capture payment
            st.success("Thank you for upgrading to Premium! Your subscription is now active.")

            email = st.session_state.get("email", "unknown_user")

            # ✅ Update Firestore User Plan
            user_ref = db.collection("users").document(email)
            user_ref.update({"plan": "premium", "queries": SUBSCRIBER_MONTHLY_QUERIES})

            st.balloons()
        else:
            st.error("⚠️ Payment execution failed. Please contact support.")

    else:
        st.error("⚠️ No payment details found. Payment may have failed or been canceled.")

# ✅ Handle payment cancellation
def payment_cancel():
    st.title("❌ Payment Cancelled")
    st.warning("Your payment was not completed. You can try again anytime.")

# ✅ Get AI-Generated Answer
def get_gita_solution(problem, language="en"):
    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-pro:generateContent?key={st.secrets['GEMINI_API_KEY']}"

    headers = {"Content-Type": "application/json"}
    
    payload = {
        "contents": [
            {"parts": [{"text": f"Based on the Bhagavad Gita Provide a solution for {problem} and respond in {language} without mentioning the shloka. The response should be in paragraph format"}]}
        ]
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        response_json = response.json()

        if response.status_code == 200 and "candidates" in response_json:
            return response_json["candidates"][0]["content"]["parts"][0]["text"]
        else:
            return "⚠️ API returned an empty response."

    except Exception as e:
        return f"❌ API Error: {str(e)}"

# ✅ Generate Audio Response (TTS)
def generate_audio_response(text, language="English"):
    language_map = {
        "English": "en", "Hindi": "hi", "Sanskrit": "sa", "Tamil": "ta", "Telugu": "te", "Marathi": "mr",
        "Gujarati": "gu", "Bengali": "bn", "Punjabi": "pa", "Kannada": "kn", "Malayalam": "ml", "Odia": "or",
        "Assamese": "as", "Urdu": "ur", "Nepali": "ne"
    }

    selected_lang = language_map.get(language, "en")

    try:
        tts = gTTS(text=text, lang=selected_lang)
        audio_file = "response.mp3"
        tts.save(audio_file)
        return audio_file
    except Exception as e:
        return f"Error in TTS generation: {e}"

# ✅ Main Page
def main_page():
    if "email" not in st.session_state:
        st.warning("Please log in again.")
        st.session_state["current_page"] = "login"
        return

    email = st.session_state["email"]
    st.title("Bhagavad Gita Life Solutions 📖✨")
    st.write(f"Welcome, **{email}**! 🙏")

    # Check user eligibility
    is_eligible, queries_left, plan = check_user_eligibility(email)

    # Display user plan and queries left
    st.subheader("📜 Your Subscription Details")
    st.write(f"**Plan:** {plan.capitalize()} 🌟")
    st.write(f"**Queries Left This Month:** {queries_left}")

    # ✅ PayPal Payment Button
    st.subheader("Upgrade for More Queries 💳")
    if st.button(f"Upgrade to Premium - ${SUBSCRIPTION_COST}/month"):
        payment_url = create_paypal_payment()
        if payment_url:
            st.success("✅ Payment created successfully! Click below to proceed:")
            st.markdown(f"[Click here to pay]({payment_url})")
        else:
            st.error("❌ Failed to create PayPal payment. Please try again.")

    problem = st.text_area("Describe your specific problem:", placeholder="Type your problem here...")
    language = st.selectbox("Preferred Language for Audio Response:", [
        "English", "Hindi", "Sanskrit", "Tamil", "Telugu", "Marathi", "Gujarati", 
        "Bengali", "Punjabi", "Kannada", "Malayalam", "Odia", "Assamese", "Urdu", 
        "Nepali"
    ]) 

    if st.button("Get Solution"):
        combined_text = get_gita_solution(problem, language)
        audio_file = generate_audio_response(combined_text, language)
        if audio_file:
            st.audio(audio_file)

# ✅ Handle PayPal Redirects
query_params = st.query_params  # 🔹 Fixed function

if "page" in query_params and query_params["page"] == "success":
    payment_success()
elif "page" in query_params and query_params["page"] == "cancel":
    payment_cancel()
else:
    main_page()
