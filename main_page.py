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
import streamlit as st
import requests
import firebase_admin
from firebase_admin import firestore
from firebase_config import db
from datetime import datetime, timedelta
import paypalrestsdk

# ✅ Load API Key securely from Streamlit secrets
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]

# ✅ PayPal Configuration
paypalrestsdk.configure({
    "mode": "sandbox",  # Change to 'live' for production
    "client_id": st.secrets["paypal"]["PAYPAL_CLIENT_ID"],
    "client_secret": st.secrets["paypal"]["PAYPAL_CLIENT_SECRET"]
})

# ✅ Ensure Session Persistence
if "email" not in st.session_state:
    st.session_state["email"] = None

# ✅ Payment Success Logic
def payment_success():
    st.title("✅ Payment Successful!")

    # ✅ Retrieve Query Parameters
    query_params = st.query_params
    payment_id = query_params.get("paymentId", [None])[0]
    payer_id = query_params.get("PayerID", [None])[0]
    email = query_params.get("email", [None])[0]

    # ✅ Restore session email
    if email:
        st.session_state["email"] = email  

    # ✅ Check if parameters exist
    if not payment_id or not payer_id:
        st.error("⚠️ No valid payment details found. Payment may have failed or been canceled.")
        return

    try:
        # ✅ Execute PayPal Payment
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
            user_ref.update({"plan": "premium", "queries": 100})

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
            st.experimental_rerun()

        else:
            st.error("⚠️ Payment execution failed. Please contact support.")
    except Exception as e:
        st.error(f"❌ Error processing payment: {str(e)}")


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
    main_p()  # ✅ Load main page if no payment actions
