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

FREE_MONTHLY_QUERIES = 10  # ✅ Free users get 10 queries per month
SUBSCRIBER_MONTHLY_QUERIES = 100
SUBSCRIPTION_COST = 7  # ✅ Subscription costs $7 per month

# Function to check user eligibility for queries
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

    # Reset queries if a month has passed
    if last_query_date:
        last_date = datetime.strptime(last_query_date, "%Y-%m-%d")
        if datetime.now() - last_date > timedelta(days=30):
            user_ref.update({"queries": 0, "last_query_date": datetime.now().strftime("%Y-%m-%d")})
            return True, limit, plan

    return queries < limit, limit - queries, plan

# Function to call Gemini API
def get_gita_solution(problem, language="en"):
    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-pro:generateContent?key={st.secrets['GEMINI_API_KEY']}"

    headers = {"Content-Type": "application/json"}
    
    payload = {
        "contents": [
            {"parts": [{"text": f"Based on the Bhagavad Gita Provide a solution  for the {problem} and respond in {language} without mentioning the shloka. the response should be in paragraph format"}]}
        ]
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        response_json = response.json()

        # 🔹 Print the full response for debugging
        #st.subheader("🔍 API Response Debugging:")
        #st.json(response_json)  # Show the entire response JSON

        # ✅ Extract solution text if response is valid
        if response.status_code == 200 and "candidates" in response_json:
            solution_text = response_json["candidates"][0]["content"]["parts"][0]["text"]
            
            # ✅ Show only extracted text
            st.subheader("📜 Bhagavad Gita's Wisdom:")
            st.write(solution_text)

            return solution_text
        else:
            st.error("⚠️ API returned an empty response. Please check the API key and request format.")
            return "Sorry, I could not generate a response."

    except Exception as e:
        st.error(f"❌ API Error: {str(e)}")
        return f"Error: {str(e)}"




# Function to generate gTTS audio response
def generate_audio_response(text, language="English"):
    # Mapping of languages to gTTS-supported codes
    language_map = {
        "English": "en",
        "Hindi": "hi",
        "Sanskrit": "sa",
        "Tamil": "ta",
        "Telugu": "te",
        "Marathi": "mr",
        "Gujarati": "gu",
        "Bengali": "bn",
        "Punjabi": "pa",
        "Kannada": "kn",
        "Malayalam": "ml",
        "Odia": "or",
        "Assamese": "as",
        "Urdu": "ur",
        "Nepali": "ne"
    }

    # Ensure the selected language is available in gTTS
    selected_lang = language_map.get(language, "en")

    try:
        # Generate speech
        tts = gTTS(text=text, lang=selected_lang)
        audio_file = "response.mp3"
        tts.save(audio_file)
        return audio_file
    except Exception as e:
        return f"Error in TTS generation: {e}"

# Main Page
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

    # PayPal Payment Button
    st.subheader("Upgrade for More Queries 💳")
    if st.button(f"Upgrade to Premium - ${SUBSCRIPTION_COST}/month"):
        payment = paypalrestsdk.Payment({
            "intent": "sale",
            "payer": {"payment_method": "paypal"},
            "redirect_urls": {
                "return_url": "https://shrikrishna.streamlit.app/success",
                "cancel_url": "https://shrikrishna.streamlit.app/cancel"
            },
            "transactions": [{
                "amount": {"total": str(SUBSCRIPTION_COST), "currency": "USD"},
                "description": "Upgrade to Premium Plan"
            }]
        })
        if payment.create():
            st.success("Payment created successfully! Please complete the transaction.")
            for link in payment.links:
                if link.rel == "approval_url":
                    st.markdown(f"[Click here to pay]({link.href})")
        else:
            st.error("Error creating PayPal payment. Try again!")

    problem = st.text_area("Describe your specific problem:", placeholder="Type your problem here...")
    language = st.selectbox("Preferred Language for Audio Response:", [
        "English", "Hindi", "Sanskrit", "Tamil", "Telugu", "Marathi", "Gujarati", 
        "Bengali", "Punjabi", "Kannada", "Malayalam", "Odia", "Assamese", "Urdu", 
        "Nepali"
    ]) 

    if st.button("Get Solution"):
        if problem.strip():
            if is_eligible:
                combined_text = get_gita_solution(problem, language)

                # ✅ Show text response on the screen
                #st.subheader("📜 Bhagavad Gita's Wisdom:")
                #st.write(combined_text)

                # Generate audio response
                audio_file = generate_audio_response(combined_text, language)
                if audio_file:
                    st.audio(audio_file)

                # Update query count
                user_ref = db.collection("users").document(email)
                user_ref.update({"queries": firestore.Increment(1), "last_query_date": datetime.now().strftime("%Y-%m-%d")})
            else:
                st.error("You've reached your monthly limit! Upgrade to Premium for unlimited queries.")
        else:
            st.warning("Please enter a valid problem description.")
    
    if st.button("Log out"):
        st.session_state["current_page"] = "signup"
        st.rerun()
