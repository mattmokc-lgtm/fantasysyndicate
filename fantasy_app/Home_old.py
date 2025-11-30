import streamlit as st
import sqlite3
import streamlit_authenticator as stauth


# --------------------------------------------
# 0. Update Password in Database
# --------------------------------------------
def update_password_in_db(username, new_hashed_password):
    try:
        db_path = st.secrets["DB_PATH"]
        conn = sqlite3.connect(db_path)
        c = conn.cursor()

        c.execute("""
            UPDATE credentials 
            SET password = ?, must_change_pw = 0
            WHERE username = ?
        """, (new_hashed_password, username))

        conn.commit()
        conn.close()

        # Force reload of credentials
        st.cache_resource.clear()

    except Exception as e:
        st.error("Error updating password in database.")
        st.exception(e)




# --------------------------------------------
# 1. Fetch users from DB
# --------------------------------------------
@st.cache_resource
def fetch_users_from_db():
    try:
        db_path = st.secrets["DB_PATH"]
        conn = sqlite3.connect(db_path)
        c = conn.cursor()

        c.execute("SELECT username, email, name, password, must_change_pw FROM credentials")
        rows = c.fetchall()
        conn.close()

        credentials = {"usernames": {}}
        preauth = []

        for username, email, name, pw_hash, must_change in rows:
            credentials["usernames"][username] = {
                "email": email,
                "name": name,
                "password": pw_hash
            }
            preauth.append(email)

        return credentials, preauth, rows

    except Exception as e:
        st.error("🚨 DATABASE ERROR while loading users.")
        st.exception(e)
        return {"usernames": {}}, [], []


# --------------------------------------------
# 2. Configure authenticator
# --------------------------------------------
credentials, preauthorized_emails, user_rows = fetch_users_from_db()

authenticator = stauth.Authenticate(
    credentials=credentials,
    cookie_name="fantasy_syndicate_cookie",
    key=st.secrets["COOKIE_KEY"],
    cookie_expiry_days=30
)

# Required for 0.4.2
authenticator._preauthorized = {"emails": preauthorized_emails}
# Hide sidebar until user is authenticated
if "authentication_status" not in st.session_state or st.session_state["authentication_status"] != True:
    hide_sidebar = """
        <style>
            [data-testid="stSidebar"] {display: none;}
            [data-testid="stSidebarNav"] {display: none;}
        </style>
    """
    st.markdown(hide_sidebar, unsafe_allow_html=True)

# --- 3. LOGIN WIDGET ---

authenticator.login(location='main')
name = st.session_state.get('name')
authentication_status = st.session_state.get('authentication_status')
username = st.session_state.get('username')
# Also pull from session_state if needed
if "authentication_status" in st.session_state:
    authentication_status = st.session_state["authentication_status"]
if "username" in st.session_state:
    username = st.session_state["username"]
if "name" in st.session_state:
    name = st.session_state["name"]


# --- 4. Authentication Flow ---
if authentication_status:
    # Detect must-change-password
    must_change = False
    for row in user_rows:
        if row[0] == username:
            must_change = row[4] == 1
            break

    if must_change:
        st.warning("🚨 First login detected — you must change your password.")

        if authenticator.reset_password(username, fields=("New password", "Repeat password")):
            new_pw = authenticator._new_password  # 0.4.2 internal attribute
            hashed = stauth.Hasher([new_pw]).generate()[0]

            update_password_in_db(username, hashed)
            st.success("Password updated! Please log in again.")
            st.rerun()

    else:
        authenticator.logout("Logout", "sidebar")
       
        # ----------------------
        # Navigation + Home button
        # ----------------------

        pages = {
            # Home recognized as a root page
            "": [
                st.Page("Home.py", title="🏠 Home"),
            ],
            "Rosters/Contracts": [
                st.Page("pages/1_Rosters.py", title="Rosters"),
                st.Page("pages/2_Contracts.py", title="Contracts"),
            ],
            "Prospects/Auction": [
                st.Page("pages/3_Prospects.py", title="Prospects"),
                st.Page("pages/4_Auction.py", title="Auction"),
            ],
            "Teams": [
                        st.Page("pages/AMH.py", title="Amherst Minutemen"),
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
                        ]
        }

        if "logged_rerun_done" not in st.session_state:
            st.session_state["logged_rerun_done"] = True
            st.rerun()

        # Create navigation
        pg = st.navigation(pages)
        active_page = st.session_state.get("st_page", None)

        # 🚨 Only show Home content on the Home page
        if active_page == "Home.py":
            st.title("Welcome to the Fantasy Syndicate App")
            st.write(f"Hello, *{name}*!")
        pg.run()
    if "logged_rerun_done" not in st.session_state:
        st.session_state["logged_rerun_done"] = True
        st.rerun()
elif authentication_status is False:
    st.error("Username/password incorrect")

else:
    st.info("Please log in to continue")