import streamlit as st
import firebase_admin
from firebase_admin import firestore
from firebase_config import db
from datetime import datetime, timedelta
import requests
import paypalrestsdk
from gtts import gTTS

# Load API Key securely from Streamlit secrets
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]

# PayPal Configuration
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
    try:
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
                    return link.href  
        else:
            st.error("❌ Failed to create PayPal payment.")
            st.json(payment.error)
            return None
    except Exception as e:
        st.error(f"❌ PayPal API error: {str(e)}")
        return None

# ✅ Capture & Confirm Payment
def payment_success():
    st.title("✅ Payment Successful!")
    st.success("Your payment is being verified...")

    query_params = st.query_params
    payment_id = query_params.get("paymentId", None)
    payer_id = query_params.get("PayerID", None)

    if not payment_id or not payer_id:
        st.error("⚠️ No valid payment details found. Payment may have failed or been canceled.")
        return

    try:
        payment = paypalrestsdk.Payment.find(payment_id)

        if payment.execute({"payer_id": payer_id}):  
            st.success("✅ Thank you for upgrading to Premium! Your subscription is now active.")

            # 🔹 Extract transaction details
            transaction = payment["transactions"][0]["related_resources"][0]["sale"]
            transaction_id = transaction["id"]
            transaction_amount = transaction["amount"]["total"]
            transaction_currency = transaction["amount"]["currency"]
            transaction_time = transaction["create_time"]
            transaction_status = transaction["state"]

            if transaction_status.lower() != "completed":
                st.error(f"⚠️ Payment failed! PayPal returned status: {transaction_status}")
                return

            # ✅ Show transaction details
            st.subheader("📜 Transaction Details:")
            st.write(f"**Transaction ID:** `{transaction_id}`")
            st.write(f"**Amount Paid:** `{transaction_amount} {transaction_currency}`")
            st.write(f"**Date & Time:** `{transaction_time}`")

            email = st.session_state.get("email", "unknown_user")

            # ✅ Update Firestore User Plan
            user_ref = db.collection("users").document(email)
            user_ref.update({"plan": "premium", "queries": SUBSCRIBER_MONTHLY_QUERIES})

            # ✅ Store Transaction Details in Firestore
            transaction_ref = db.collection("transactions").document(transaction_id)
            transaction_ref.set({
                "email": email,
                "transaction_id": transaction_id,
                "amount": transaction_amount,
                "currency": transaction_currency,
                "status": "Completed",
                "timestamp": transaction_time
            })

            st.success("✅ Transaction recorded successfully in Firestore!")
            st.balloons()

            if st.button("Return to App"):
                st.session_state["current_page"] = "main_page"
                st.rerun()
        else:
            st.error("⚠️ Payment execution failed. Please contact support.")
    except Exception as e:
        st.error(f"❌ Error processing payment: {str(e)}")

# ✅ Handle payment cancellation
def payment_cancel():
    st.title("❌ Payment Cancelled")
    st.warning("Your payment was not completed. You can try again anytime.")

# ✅ AI Solution & TTS
def get_gita_solution(problem, language="en"):
    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-pro:generateContent?key={GEMINI_API_KEY}"
    headers = {"Content-Type": "application/json"}
    
    payload = {
        "contents": [
            {"parts": [{"text": f"Based on the Bhagavad Gita Provide a solution for {problem} in {language} without mentioning the shloka."}]}
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

def generate_audio_response(text, language="English"):
    language_map = {
        "English": "en", "Hindi": "hi", "Sanskrit": "sa", "Tamil": "ta", "Telugu": "te",
        "Marathi": "mr", "Gujarati": "gu", "Bengali": "bn", "Punjabi": "pa", "Kannada": "kn",
        "Malayalam": "ml", "Odia": "or", "Assamese": "as", "Urdu": "ur", "Nepali": "ne",
        "Sindhi": "sd", "Kashmiri": "ks", "Konkani": "gom", "Manipuri": "mni", "Maithili": "mai",
        "Bodo": "brx", "Santali": "sat", "Dogri": "doi", "Rajasthani": "raj", "Chhattisgarhi": "hne",
        "Bhili": "bhb", "Tulu": "tcy"
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
    st.title("Bhagavad Gita Life Solutions 📖✨")
    problem = st.text_area("Describe your problem:")
    language = st.selectbox("Select a Language:", list(generate_audio_response.__annotations__.keys()))

    if st.button("Get Solution"):
        solution = get_gita_solution(problem, language)
        st.subheader("📜 Bhagavad Gita's Wisdom:")
        st.write(solution)
        audio_file = generate_audio_response(solution, language)
        if audio_file:
            st.audio(audio_file)

query_params = st.query_params
if "page" in query_params and query_params["page"] == "success":
    payment_success()
elif "page" in query_params and query_params["page"] == "cancel":
    payment_cancel()
else:
    main_page()
