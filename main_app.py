import streamlit as st
from signup import combined_auth_page

from main_page import main_p


#st.write("🔹 Firebase Project ID:", st.secrets["firebase"]["project_id"])
#st.write("🔹 Firebase Client Email:", st.secrets["firebase"]["client_email"])


if "current_page" not in st.session_state:
    st.session_state["current_page"] = "signup"

if st.session_state["current_page"] == "signup":
    combined_auth_page()

elif st.session_state["current_page"] == "main_page":
    main_p()
