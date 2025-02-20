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

# ✅ Ensure Session Persistence
if "email" not in st.session_state:
    st.session_state["email"] = None

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
    email = st.session_state.get("email", None)
    if not email:
        st.error("⚠️ Please log in before making a payment.")
        return None

    try:
        payment = paypalrestsdk.Payment({
            "intent": "sale",
            "payer": {"payment_method": "paypal"},
            "redirect_urls": {
                "return_url": f"https://shrikrishna.streamlit.app/?page=success&email={email}",
                "cancel_url": f"https://shrikrishna.streamlit.app/?page=cancel&email={email}"
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
    email = query_params.get("email", None)

    if email:
        st.session_state["email"] = email  # Restore session email

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

            st.success("✅ Transaction recorded successfully in Firestore! 🎉")
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

# ✅ Main Page
def main_page():
    email = st.session_state.get("email", None)
    if not email:
        st.warning("Please log in again.")
        st.session_state["current_page"] = "signup"
        return

    st.title("Bhagavad Gita Life Solutions 📖✨")

    if st.button("Upgrade to Premium - $7/month"):
        payment_url = create_paypal_payment()
        if payment_url:
            st.markdown(f"[Click here to pay]({payment_url})")
        else:
            st.error("❌ Payment failed.")

# ✅ Route Based on URL Params
query_params = st.query_params

if "page" in query_params:
    if query_params["page"] == "success":
        payment_success()
        st.stop()
    elif query_params["page"] == "cancel":
        payment_cancel()
        st.stop()
else:
    main_page()
