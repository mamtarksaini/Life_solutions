import streamlit as st
import firebase_admin
from firebase_admin import firestore
from firebase_config import db
from datetime import datetime, timedelta
import requests
from gtts import gTTS

# ✅ PayPal API Constants
PAYPAL_CLIENT_ID = st.secrets["paypal"]["PAYPAL_CLIENT_ID"]
PAYPAL_SECRET = st.secrets["paypal"]["PAYPAL_CLIENT_SECRET"]
PAYPAL_API_URL = "https://api-m.sandbox.paypal.com"

# ✅ Load API Key securely from Streamlit secrets
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]

# ✅ Constants
FREE_MONTHLY_QUERIES = 10
SUBSCRIBER_MONTHLY_QUERIES = 100
SUBSCRIPTION_COST = "7.00"

# ✅ Ensure Session Persistence
if "email" not in st.session_state:
    st.session_state["email"] = None
if "payment_verified" not in st.session_state:
    st.session_state["payment_verified"] = False  # Prevents duplicate processing

# ✅ Function to get PayPal Access Token
def get_paypal_access_token():
    url = f"{PAYPAL_API_URL}/v1/oauth2/token"
    headers = {
        "Accept": "application/json",
        "Accept-Language": "en_US",
    }
    data = {"grant_type": "client_credentials"}
    response = requests.post(url, headers=headers, data=data, auth=(PAYPAL_CLIENT_ID, PAYPAL_SECRET))
    response.raise_for_status()
    return response.json()["access_token"]

# ✅ Create PayPal Payment
def create_paypal_payment():
    email = st.session_state.get("email", None)
    if not email:
        st.error("⚠️ Please log in before making a payment.")
        return None

    try:
        access_token = get_paypal_access_token()
        url = f"{PAYPAL_API_URL}/v2/checkout/orders"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}",
        }
        order_data = {
            "intent": "CAPTURE",
            "purchase_units": [{"amount": {"currency_code": "USD", "value": SUBSCRIPTION_COST}}],
            "application_context": {
                "return_url": f"https://shrikrishna.streamlit.app/?page=success&email={email}",
                "cancel_url": f"https://shrikrishna.streamlit.app/?page=cancel&email={email}"
            }
        }

        response = requests.post(url, headers=headers, json=order_data)
        response.raise_for_status()
        order = response.json()

        approval_url = next(link["href"] for link in order["links"] if link["rel"] == "approve")
        return approval_url
    except Exception as e:
        st.error(f"❌ PayPal API error: {str(e)}")
        return None

# ✅ Capture Payment
def capture_payment(order_id):
    try:
        access_token = get_paypal_access_token()
        url = f"{PAYPAL_API_URL}/v2/checkout/orders/{order_id}/capture"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}",
        }

        response = requests.post(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"❌ Payment Capture Error: {str(e)}")
        return None

# ✅ Payment Success Logic
def payment_success():
    st.title("✅ Payment Successful!")

    # ✅ Retrieve Query Parameters
    query_params = st.query_params
    order_id = query_params.get("token", [None])[0]
    email = query_params.get("email", [None])[0]

    # ✅ Restore session email
    if email:
        st.session_state["email"] = email  

    # ✅ Check if order_id exists
    if not order_id:
        st.error("⚠️ No valid order details found. Payment may have failed or been canceled.")
        return

    # ✅ Capture Payment
    payment_response = capture_payment(order_id)

    if payment_response and "purchase_units" in payment_response:
        transaction = payment_response["purchase_units"][0]["payments"]["captures"][0]
        transaction_id = transaction["id"]
        transaction_amount = transaction["amount"]["value"]
        transaction_currency = transaction["amount"]["currency_code"]
        transaction_time = transaction["create_time"]
        transaction_status = transaction["status"]

        # ✅ Ensure transaction is completed
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

        # ✅ Auto-refresh UI after successful payment
        st.session_state["payment_verified"] = True
        st.rerun()

    else:
        st.error("⚠️ Payment capture failed. Please try again.")

# ✅ Handle payment cancellation
def payment_cancel():
    st.title("❌ Payment Cancelled")
    st.warning("Your payment was not completed. You can try again anytime.")

# ✅ Main Page
def main_p():
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
page = query_params.get("page", ["main"])[0]

if page == "success":
    payment_success()
    st.stop()
elif page == "cancel":
    st.title("❌ Payment Cancelled")
    st.warning("Your payment was not completed. Please try again.")
    st.stop()
else:
    if st.session_state.get("payment_verified", False):
        payment_success()  # ✅ Show success message immediately if session has it
    else:
        main_p()  # ✅ Load main page if no payment actions
