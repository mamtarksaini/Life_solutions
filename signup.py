import streamlit as st
from firebase_config import db  # Ensure Firebase is properly imported

def combined_auth_page():
    
    st.title("Bhagwat Geeta Life Solutions")
    st.subheader("-------------------------------------------------------------------")
    st.subheader("Authentication")

    # 🔹 Debug: Check Firestore Initialization
    if db is None:
        st.error("❌ Firestore database is not initialized. Check Firebase setup.")
        st.write("⚠️ Debug Info: Firestore Database (db) is None.")
        return  # Stop execution if Firestore is not initialized

    # Toggle between Signup and Login
    action = st.radio("Select an action", ["Sign Up", "Sign In"])

    if action == "Sign Up":
        # Signup form
        st.subheader("Create a New Account")
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        confirm_password = st.text_input("Confirm Password", type="password")

        if st.button("Sign Up"):
            if password == confirm_password:
                try:
                    user_ref = db.collection("users").document(email)
                    user_doc = user_ref.get()

                    if user_doc.exists:
                        st.error("❌ Email is already registered.")
                    else:
                        user_ref.set({"password": password, "queries": 0, "plan": "free"})
                        st.success("✅ Sign-up successful! Please log in.")
                        st.session_state["current_page"] = "signup"
                except Exception as e:
                    st.error(f"⚠️ Firebase Error: {str(e)}")

            else:
                st.error("⚠️ Passwords do not match.")

    elif action == "Sign In":
        # Login form
        st.subheader("Sign In to Your Account")
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_password")

        if st.button("Login"):
            try:
                user_ref = db.collection("users").document(email)
                user_doc = user_ref.get()

                if user_doc.exists and user_doc.to_dict().get("password") == password:
                    st.success("✅ Login successful!")
                    st.session_state["email"] = email
                    st.session_state["current_page"] = "main_page"
                else:
                    st.error("❌ Invalid credentials.")
            except Exception as e:
                st.error(f"⚠️ Firebase Error: {str(e)}")


