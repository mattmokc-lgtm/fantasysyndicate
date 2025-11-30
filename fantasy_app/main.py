import streamlit as st
import streamlit_authenticator as stauth
import pandas as pd
from sqlalchemy import create_engine, text
from PIL import Image
from io import BytesIO
import requests
import math
import os
import boto3
import base64
import numpy as np

# -------------------------
# CONFIG / SECRETS
# -------------------------
st.set_page_config(page_title="Fantasy Syndicate", page_icon="⚾")

R2_ENDPOINT = st.secrets["R2_ENDPOINT"] 
R2_ACCESS_KEY_ID = st.secrets["R2_ACCESS_KEY_ID"]
R2_SECRET_ACCESS_KEY = st.secrets["R2_SECRET_ACCESS_KEY"]
R2_BUCKET = st.secrets["R2_BUCKET"]
R2S3 = st.secrets["R2S3"]
R2_DIR = st.secrets["R2_DIR"]

# Initialize S3 client
s3 = boto3.client(
    R2S3,
    endpoint_url=R2_ENDPOINT,
    aws_access_key_id=R2_ACCESS_KEY_ID,
    aws_secret_access_key=R2_SECRET_ACCESS_KEY,
)
object_key = f"{R2_DIR}/FS.png"

# Function to retrieve and encode image as base64
def get_encoded_image_src(bucket_name, key):
    try:
        response = s3.get_object(Bucket=bucket_name, Key=key)
        image_data = response["Body"].read()
        encoded_image = base64.b64encode(image_data).decode()
        image_src = f"data:image/png;base64,{encoded_image}"
        return image_src
    except Exception as e:
        # Don't use st.error here if called during initial layout phase as it can cause issues
        print(f"Error fetching sidebar image: {e}") 
        return None

def get_connection():
    cfg = st.secrets["database"]
    conn_str = (
        f"postgresql+psycopg2://{cfg['username']}:{cfg['password']}"
        f"@{cfg['host']}:{cfg.get('port',5432)}/{cfg['database']}"
        f"?sslmode={cfg.get('sslmode','require')}"
    )
    return create_engine(conn_str)
engine = get_connection()

@st.cache_data(show_spinner=False)
def read_sql_df(query_str, params=None):
    with engine.connect() as conn:
        return pd.read_sql(query_str, conn, params=params)

# ... (Load credentials function, credentials/authenticator setup remain the same) ...

@st.cache_resource
def load_credentials():
    # ... (function body as before) ...
    q = "SELECT username, email, name, password FROM credentials"
    creds_df = read_sql_df(q)
    creds = {"usernames": {}}
    emails = []

    for _, row in creds_df.iterrows():
        u = row['username']
        e = row['email']
        n = row['name']
        pw = row['password']
        
        creds["usernames"][u] = {"email": e, "name": n, "password": pw}
        emails.append(e)

    return creds, emails

credentials, emails = load_credentials()

authenticator = stauth.Authenticate(
    credentials=credentials,
    cookie_name="fantasy_syndicate_cookie",
    key=st.secrets["COOKIE_KEY"], 
    cookie_expiry_days=30
)
authenticator._preauthorized = {"emails": emails}


# --------------------------
# Initialize session state
# --------------------------
if "authentication_status" not in st.session_state:
    st.session_state["authentication_status"] = False

# --------------------------
# Define pages_dict once at the top
# --------------------------
if "pages_dict" not in st.session_state:
    st.session_state["pages_dict"] = {
        # Keep this structure as is. Streamlit handles single-item lists internally now.
        "Home": [st.Page("pages/Home.py", title="🏠 Home")], 
        "Teams": [
            st.Page("pages/AMH.py", title="Amherst Minutemen"),
            # ... (all other 13 teams pages remain here) ...
            st.Page("pages/BEA.py", title="Beamsville Beavers"),
            st.Page("pages/BRK.py", title="Brooklyn Brewers"),
            st.Page("pages/CHI.py", title="Chicago Communists"),
            st.Page("pages/FLA.py", title="Florida Phoenix"),
            st.Page("pages/FW.py", title="Fort Worth Fire"),
            st.Page("pages/HAL.py", title="Halton Huskies"),
            st.Page("pages/LA.py", title="Los Angeles Smog"),
            st.Page("pages/MCK.py", title="McKinney Knights"),
            st.Page("pages/OK.py", title="Oklahoma Schooners"),
            st.Page("pages/PRI.py", title="Princeton Anglers"),
            st.Page("pages/SAN.py", title="Sanger Greys"),
            st.Page("pages/TOR.py", title="Toronto Canucks"),
            st.Page("pages/WAC.py", title="Wachusett Mountaineers"),
        ],
        "H2H Analytics": [st.Page("pages/8_H2H_Analytics.py", title="⚔ H2H Analytics")],
    }

pages = st.session_state["pages_dict"] # Revert back to the dictionary reference

# --------------------------
# Hide sidebar until login (Same as before)
# --------------------------
if not st.session_state["authentication_status"]:
    st.markdown("""
        <style>
            [data-testid="stSidebar"] {display: none !important;}
        </style>
    """, unsafe_allow_html=True)

# --------------------------
# LOGIN FLOW (Same as before)
# --------------------------
if not st.session_state["authentication_status"]:
    login_result = authenticator.login(location="main") or {}
    name = login_result.get("name")
    username = login_result.get("username")
    auth_status = login_result.get("authentication_status")

    if auth_status:
        st.session_state["authentication_status"] = True
        st.session_state["name"] = name
        st.session_state["username"] = username
        st.experimental_rerun()
    elif auth_status is False:
        st.error("Incorrect username or password")
    else:
        st.info("Please enter your credentials")

# --------------------------
# AUTHENTICATED CONTENT (Revised)
# --------------------------
else:
    # --- 1. Display Logo in Sidebar using st.sidebar.image ---
    image_src_encoded = get_encoded_image_src(R2_BUCKET, object_key)
    if image_src_encoded:
        with st.sidebar:
            # Place the image *first* to ensure it is at the top of the render order
            st.image(image_src_encoded, width=150) # Adjust width as needed (e.g., 150px)

    # --- 2. CSS Injection for Sidebar Font and Image Centering ---
    # Inject CSS after the image is rendered but before navigation runs
    st.markdown(
        f"""
        <style>
            /* Set the desired font for all sidebar elements */
            [data-testid="stSidebar"], [data-testid="stSidebarNav"] li a {{
                font-family: 'Courier Prime', monospace !important;
            }}
            /* CSS to center the image placed by st.sidebar.image */
            [data-testid="stSidebar"] .stImage {{
                display: block;
                margin-left: auto;
                margin-right: auto;
                padding-top: 0px; /* Remove top padding */
                padding-bottom: 15px; /* Add space below logo */
            }}
        </style>
        """,
        unsafe_allow_html=True,
    )

    # --- 3. Navigation and Logout ---
    # st.navigation must be called to run the pages dict system
    pg = st.navigation(pages) # Use the correct 'pages' dictionary reference
    pg.run()
    
    # Place the logout button after navigation
    authenticator.logout("Logout", "sidebar")