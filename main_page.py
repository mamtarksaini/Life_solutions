import streamlit as st
import firebase_admin
from firebase_admin import firestore
from firebase_config import db
from datetime import datetime, timedelta
import requests
import paypalrestsdk
from gtts import gTTS





# ✅ PayPal API Constants
PAYPAL_CLIENT_ID = st.secrets["paypal"]["PAYPAL_CLIENT_ID"]
PAYPAL_SECRET = st.secrets["paypal"]["PAYPAL_CLIENT_SECRET"]
PAYPAL_API_URL = "https://api-m.sandbox.paypal.com"

# ✅ Function to get PayPal Access Token


# ✅ Load API Key securely from Streamlit secrets
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]



# ✅ Constants
FREE_MONTHLY_QUERIES = 10
SUBSCRIBER_MONTHLY_QUERIES = 100
SUBSCRIPTION_COST = 7

# ✅ Ensure Session Persistence
if "email" not in st.session_state:
    st.session_state["email"] = None

if "payment_verified" not in st.session_state:
    st.session_state["payment_verified"] = False  # Prevents duplicate processing

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
        access_token = get_paypal_access_token()
        url = f"{PAYPAL_API_URL}/v2/checkout/orders"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}",
        }
        order_data = {
            "intent": "CAPTURE",
            "purchase_units": [{"amount": {"currency_code": "USD", "value": "7.00"}}],
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

# ✅ Capture Payment Immediately After Return from PayPal
def payment_success():
    st.title("✅ Payment Successful!")

    query_params = st.query_params
    order_id = query_params.get("token", None)  # PayPal now sends "token" as Order ID
    email = query_params.get("email", None)

    if not order_id:
        st.error("⚠️ No valid order ID found. Payment may have failed or been canceled.")
        return

    # ✅ Store email in session
    if email:
        st.session_state["email"] = email  

    try:
        access_token = get_paypal_access_token()
        url = f"{PAYPAL_API_URL}/v2/checkout/orders/{order_id}/capture"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}",
        }

        response = requests.post(url, headers=headers)

        if response.status_code == 201:
            payment_data = response.json()
            st.success("✅ Payment Captured Successfully!")
            
            transaction_id = payment_data["purchase_units"][0]["payments"]["captures"][0]["id"]
            transaction_amount = payment_data["purchase_units"][0]["payments"]["captures"][0]["amount"]["value"]
            transaction_currency = payment_data["purchase_units"][0]["payments"]["captures"][0]["amount"]["currency_code"]

            # ✅ Show transaction details
            st.subheader("📜 Transaction Details:")
            st.write(f"**Transaction ID:** `{transaction_id}`")
            st.write(f"**Amount Paid:** `{transaction_amount} {transaction_currency}`")

            # ✅ Update Firestore
            email = st.session_state.get("email", "unknown_user")
            user_ref = db.collection("users").document(email)
            user_ref.update({"plan": "premium", "queries": 100})

            # ✅ Store Transaction in Firestore
            transaction_ref = db.collection("transactions").document(transaction_id)
            transaction_ref.set({
                "email": email,
                "transaction_id": transaction_id,
                "amount": transaction_amount,
                "currency": transaction_currency,
                "status": "Completed",
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })

            st.success("✅ Transaction recorded successfully in Firestore! 🎉")
            st.balloons()
        else:
            st.error(f"⚠️ Payment Capture Failed: {response.json()}")
    except Exception as e:
        st.error(f"❌ Error processing payment: {str(e)}")

    # ✅ Redirect user to clear query parameters
    st.rerun()

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

if "page" in query_params:
    if query_params["page"] == "success":
        payment_success()
        st.stop()
    elif query_params["page"] == "cancel":
        payment_cancel()
        st.stop()
else:
    main_p()
