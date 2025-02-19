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
    return None

# ✅ Capture & Confirm Payment
def payment_success():
    st.title("✅ Payment Successful!")
    st.success("Your payment was successful! You are now upgraded to **Premium** 🎉.")

    query_params = st.query_params
    payment_id = query_params.get("paymentId", None)
    payer_id = query_params.get("PayerID", None)

    if payment_id and payer_id:
        payment = paypalrestsdk.Payment.find(payment_id)

        if payment.execute({"payer_id": payer_id}):  
            st.success("✅ Thank you for upgrading to Premium! Your subscription is now active.")

            # 🔹 Extract transaction details
            transaction_id = payment["transactions"][0]["related_resources"][0]["sale"]["id"]
            transaction_amount = payment["transactions"][0]["amount"]["total"]
            transaction_currency = payment["transactions"][0]["amount"]["currency"]
            transaction_time = payment["create_time"]

            st.subheader("📜 Transaction Details:")
            st.write(f"**Transaction ID:** `{transaction_id}`")
            st.write(f"**Amount Paid:** `{transaction_amount} {transaction_currency}`")
            st.write(f"**Date & Time:** `{transaction_time}`")

            email = st.session_state.get("email", "unknown_user")

            user_ref = db.collection("users").document(email)
            user_ref.update({"plan": "premium", "queries": SUBSCRIBER_MONTHLY_QUERIES})

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
    else:
        st.error("⚠️ No valid payment details found. Payment may have failed or been canceled.")

# ✅ Handle payment cancellation
def payment_cancel():
    st.title("❌ Payment Cancelled")
    st.warning("Your payment was not completed. You can try again anytime.")

# ✅ Get AI-based Answer
def get_gita_solution(problem, language="en"):
    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-pro:generateContent?key={GEMINI_API_KEY}"
    headers = {"Content-Type": "application/json"}
    
    payload = {
        "contents": [
            {"parts": [{"text": f"Based on the Bhagavad Gita Provide a solution for {problem} in {language} without mentioning the shloka.Please provide the solution in paragraph form,"}]}
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

# ✅ Generate gTTS Audio Response
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
    if "email" not in st.session_state:
        st.warning("Please log in again.")
        st.session_state["current_page"] = "login"
        return

    email = st.session_state["email"]
    st.title("Bhagavad Gita Life Solutions 📖✨")

    problem = st.text_area("Describe your problem:", key="problem_input")


    # ✅ Language Selection Restored
    language = st.selectbox("Select a Language:", [
        "English", "Hindi", "Sanskrit", "Tamil", "Telugu", "Marathi", "Gujarati", 
        "Bengali", "Punjabi", "Kannada", "Malayalam", "Odia", "Assamese", "Urdu", 
        "Nepali", "Sindhi", "Kashmiri", "Konkani", "Manipuri", "Maithili",
        "Bodo", "Santali", "Dogri", "Rajasthani", "Chhattisgarhi","Bhili", "Tulu"

    ]) 

    if st.button("Get Solution"):
        solution = get_gita_solution(problem, language)
        st.subheader("📜 Bhagavad Gita's Wisdom:")
        st.write(solution)
        audio_file = generate_audio_response(solution, language)
        if audio_file:
            st.audio(audio_file)

    if st.button("Upgrade to Premium - $7/month"):
        payment_url = create_paypal_payment()
        if payment_url:
            st.markdown(f"[Click here to pay]({payment_url})")
        else:
            st.error("❌ Payment failed.")

query_params = st.query_params
if "page" in query_params and query_params["page"] == "success":
    payment_success()
elif "page" in query_params and query_params["page"] == "cancel":
    payment_cancel()
else:
    main_page()
