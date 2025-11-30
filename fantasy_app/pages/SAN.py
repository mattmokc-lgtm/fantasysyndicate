# app.py
import streamlit as st
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
# CONFIG
# -------------------------
st.set_page_config(page_title="League Dashboard", layout="wide")

def get_connection():
    cfg = st.secrets["database"]
    conn_str = (
        f"postgresql+psycopg2://{cfg['username']}:{cfg['password']}"
        f"@{cfg['host']}:{cfg.get('port',5432)}/{cfg['database']}"
        f"?sslmode={cfg.get('sslmode','require')}"
    )
    return create_engine(conn_str)
engine = get_connection()


# -------------------------
# UTILITIES
# -------------------------
@st.cache_data(show_spinner=False)

def read_sql_df(query_str, params=None):
    with engine.connect() as conn:
        return pd.read_sql(query_str, conn, params=params)
def hex_to_rgb_tuple(hex_color):
    if not hex_color:
        return (0, 0, 0)
    hex_color = hex_color.lstrip("#")
    if len(hex_color) == 3:
        hex_color = ''.join([c*2 for c in hex_color])
    return tuple(int(hex_color[i:i+2], 16) for i in (0,2,4))

def readable_text_color(hex_color):
    # luminance check; returns #000000 or #FFFFFF
    r,g,b = hex_to_rgb_tuple(hex_color)
    luminance = (0.299*r + 0.587*g + 0.114*b)/255
    return "#000000" if luminance > 0.6 else "#FFFFFF"

@st.cache_data(show_spinner=False)
def fetch_image_bytes(url):
    if not url:
        return None
    try:
        resp = requests.get(url, timeout=6)
        resp.raise_for_status()
        return resp.content
    except Exception:
        return None
YR = st.secrets["SeasonCode"]
# -------------------------
# DATA LOADERS
# -------------------------
@st.cache_data(ttl=60)
def load_teams():
    q = """SELECT team_id,  location||team_name as team_name, division, logo_url, banner_url, 
            primary_color, secondary_color, accent_color, neutral_color, additional_color, 
            fantrax_url FROM teams where team_id = 12 ORDER BY team_name"""
    return read_sql_df(q)

@st.cache_data(ttl=60)
def load_team_by_team_id(team_id):
    q = "SELECT * FROM teams WHERE team_id = '12' LIMIT 1"
    df = read_sql_df(q)
    if df.empty: return None
    return df.iloc[0].to_dict()

@st.cache_data(ttl=60)
def get_roster(team_id):
    q = """
   SELECT p.player_id as player_id, p.full_name, p.position_full, p.mlb_team, p.age,
           c.salary, 
           c.end_year,
           CASE WHEN EXISTS (SELECT 1 FROM fantasy.prospects pr WHERE pr.player_id = p.player_id) THEN TRUE ELSE FALSE END AS is_prospect,
           CASE WHEN c.status LIKE '%%UFA%%' THEN 'UFA'
           WHEN c.status LIKE '%%RO%%' THEN 'Rookie Contract'
           ELSE '' END AS contract_type
    FROM fantasy.players p
    JOIN fantasy.contracts c ON c.player_id = p.player_id
    WHERE c.team_id = %s  
    AND c.status NOT LIKE '%%PR%%'
    AND c.end_year > %s
    ORDER BY p.full_name
    """
    params = (team_id, YR)
    return read_sql_df(q, params=params)

@st.cache_data(ttl=60)
def get_saltot(team_id):
    q = """
           SELECT 
         c.team_id,  SUM(c.salary) + COALESCE(r.deadmoney,0.00::MONEY)  AS total_salary, 100 - (SUM(c.salary)+ COALESCE(r.deadmoney,0.00::MONEY))::numeric AS cap_space, COALESCE(r.deadmoney,0.00::MONEY) AS dead_money
    FROM fantasy.contracts c 
	LEFT JOIN (select team_id, sum(retained_salary) as deadmoney from fantasy.retention group by team_id) r ON c.team_id = r.team_id
    WHERE c.team_id = %s AND 
	c.status NOT LIKE '%%PR%%'
    AND c.end_year > %s
    GROUP BY
    c.team_id, r.deadmoney"""
    params = (team_id, YR)
    df = read_sql_df(q, params=params)
    return df.iloc[0].to_dict() if not df.empty else None

@st.cache_data(ttl=60)
def get_prospects(team_id):
    q = """
    SELECT pr.player_id as prospect_id, pr.mlb_team,pr.player_name, pr.position, pr.age, pr.options, pr.acquisition, pr.overall_pick, pr.draft_yr, pr.bid, pr.rookie_eligible
    FROM prospects pr
    JOIN players p ON p.player_id = pr.player_id
    WHERE pr.team_id = %s
    --ORDER BY COALESCE(pr.prospect_rank, 999)
    """
    params = (team_id,)
    return read_sql_df(q, params=params)
@st.cache_data(ttl=60)

def get_trades(team_id):
    q = """
    SELECT * 
    FROM trades
    WHERE team_id_to::integer = %s or team_id_from::integer = %s
    ORDER BY trade_date DESC, trade_id_grouped DESC
    """
    params = (team_id, team_id)
    return read_sql_df(q, params=params)
    

@st.cache_data(ttl=60)
def get_trophies(team_id, limit=8):
    q = "SELECT team_id, season, award_id, award_text FROM Awards WHERE team_id = %s ORDER BY season desc, award_id asc"
    params = (team_id,)
    return read_sql_df(q, params=params)

@st.cache_data(ttl=60)
def get_recent_transactions(team_id, limit=10):
    q = "SELECT trade_payload, submitted_by, timestamp, processed FROM trade_history WHERE (trade_payload->>'teamA' = :slug OR trade_payload->>'teamB' = :slug) ORDER BY timestamp DESC LIMIT :lim"
    # Using slug here is simplistic; you can adapt trade_payload structure
    return read_sql_df(q, params={"slug": team_id, "lim": limit})

@st.cache_data(ttl=60)
def get_gc(team_id):
    q = """SELECT team_id, gc_balance FROM fantasy."GC" WHERE team_id = %s"""
    params = (team_id,)
    return read_sql_df(q, params=params)
# -------------------------
# UI: Banner renderer
# -------------------------
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

# Build object key
object_key = f"{R2_DIR}/SAN.png"

def render_banner(team):
    primary = team.get("neutral_color") or "#2d2d2d"
    try:
        response = s3.get_object(Bucket=R2_BUCKET, Key=object_key)
        image_data = response["Body"].read()
        encoded_image = base64.b64encode(image_data).decode()
        image_src = f"data:image/png;base64,{encoded_image}"
    except s3.exceptions.NoSuchKey:
        # Handle case where image isn't found
        image_src = "" # Use an empty src if no image is available
        st.error(f"Image {object_key} not found in R2 bucket for banner.")
    #logo = team.get("logo_url")
    fname = (team.get("location") + " " + team.get("team_name"))
    text_color = readable_text_color(primary)

    logo_size = "120px" 

    left_html = f"""
    <div style="display:flex;align-items:center;gap:16px;">
      <!-- Increased container width/height and removed padding -->
      <div style="width:{logo_size};height:{logo_size};border-radius:0px;overflow:hidden;background:{primary};padding:0px;">
        <!-- Increased image width/height -->
        <img src="{image_src}" style="width:{logo_size};height:{logo_size};object-fit:cover;" />
      </div>
      <div style="display:flex;flex-direction:column;">
        <!-- You might want to increase font size here too if the logo is much bigger -->
        <div style="font-size:32px;font-weight:700;">{fname}</div>
        <div style="font-size:14px;opacity:0.9;">{(team.get('division') or '')} · Record: {(team.get('record') or '')}</div>
      </div>
    </div>
    """

    right_html = f"""
    <div style="display:flex;gap:10px;align-items:center;">
      <div style="padding:8px;border-radius:8px;background:rgba(255,255,255,0.08);text-align:center;">
        <div style="font-weight:700;">{team.get('roster_count', '—')}</div>
        <div style="font-size:12px;opacity:0.9;">Roster</div>
      </div>
      <div style="padding:8px;border-radius:8px;background:rgba(255,255,255,0.08);text-align:center;">
        <div style="font-weight:700;">{team.get('prospect_count', '—')}</div>
        <div style="font-size:12px;opacity:0.9;">Prospects</div>
      </div>
    </div>
    """

    st.markdown(
        f"""
    <div style="padding:18px;border-radius:10px;background:{primary};color:{text_color};display:flex;justify-content:space-between;align-items:center;border: 2px solid {team['accent_color']}; ">
      {left_html}
      {right_html}
    </div>
    """, unsafe_allow_html=True)

# -------------------------
# PAGE: Team Dashboard
# -------------------------
def page_team_dashboard(team_id):
    team = load_team_by_team_id(team_id)
    if not team:
        st.warning("Team not found.")
        return

    # augment team with counts
    roster_df = get_roster(team["team_id"])
    prospects_df = get_prospects(team["team_id"])
    team["roster_count"] = len(roster_df)
    team["prospect_count"] = len(prospects_df)
    

    render_banner(team)

    st.markdown("""
    <div style='
        display: flex;
        justify-content: center;
        flex-wrap: wrap;
        gap: 1.5rem;
        font-size: 0.9rem;
        text-align: center;
        margin-top: 0.5rem;
    '>
    <span>🏆 <a href="/trophy">Trophy Room</a></span>
    <span>🔄 <a href="/trades">Trade History</a></span>
    <span>🎓 <a href="/rookies">Rookie Contracts</a></span>
    <span>📊 <a href='{team.get('fantrax_url')}'>Fantrax</a></span>
    <span>💬 <a href="https://discord.com/channels/941020738092163083/941020738612244503">Discord</a></span>
    <span>🏠 <a href="/">League Home</a></span>
    </div>
    """, unsafe_allow_html=True)

    st.markdown(f"""
            <style>

                /* Section headers */
                h2, h3 {{
                    color: {'#FFFFFF'} !important;
                }}

                /* Proper AG-Grid table header styling */
                [data-testid="stDataFrame"] .ag-header-cell {{
                    background-color: {team['accent_color']} !important;
                    color: white !important;
                    font-weight: 600 !important;
                }}

                /* Body cells */
                [data-testid="stDataFrame"] .ag-cell {{
                    border-color: {team['neutral_color']}55 !important;
                    white-space: nowrap !important; /* prevent wrapping */
                }}

                /* Hover effect for rows */
                [data-testid="stDataFrame"] .ag-row:hover .ag-cell {{
                    background-color: {team['accent_color']}22 !important;
                }}

                /* Section boxes */
                .team-box {{
                    background-color: {team['neutral_color']} !important;
                    padding: 1rem;
                    border-radius: 3px;
                    /* REMOVED: border: 2px solid {team['accent_color']}; */
                    /* REMOVED: margin-bottom: 1rem; */
                }}

            </style>
            """, unsafe_allow_html=True)
    
    salary_metrics = get_saltot(team['team_id']) or {}

    def format_money(value, default='—'):
    # Check if value is a valid number, otherwise return default
        if value is None or (isinstance(value, (int, float)) and value == 0):
            return default
    
        # Format as currency, e.g., $50.50
        return f"${value:,.2f}"

    def format_cap(value, default='—'):
        # Check if value is a valid number
        if value is None or (isinstance(value, (int, float)) and value == 0):
            return default
        return f"${value:,.2f}"
    def format_dead(value, default='—'):
        # Check if value is a valid number
        if value is None or (isinstance(value, (int, float)) and value == 0):
            return default
        return f"${value:,.2f}"
    left_html = f'<div class="team-box"><h3 style="color:{team["primary_color"]}">Roster</h3></div>'

    right_html = f"""
    <div style="display:flex;gap:10px;align-items:center;">
    <div style="padding:8px;border-radius:8px;background:rgba(255,255,255,0.08);text-align:center;">
        <div style="font-weight:700;">{team.get('saltot', '—')}</div>
        <div style="font-size:12px;opacity:0.9;">Salary Total</div>
    </div>
    <div style="padding:8px;border-radius:8px;background:rgba(255,255,255,0.08);text-align:center;">
        <div style="font-weight:700;">{team.get('prospect_count', '—')}</div>
        <div style="font-size:12px;opacity:0.9;">Prospects</div>
    </div>
    </div>
    """
    total_salary_val = salary_metrics.get('total_salary')
    dead_money_val = salary_metrics.get('dead_money')
    cap_space_val = salary_metrics.get('cap_space')
    right_html = f"""
    <div style="display:flex;gap:10px;align-items:center;">
    
    <div style="padding:12px;border-radius:8px;background:rgba(255,255,255,0.08);text-align:center;">
        <div style="font-weight:700;">{(salary_metrics.get('total_salary'))}</div>
        <div style="font-size:12px;opacity:0.9;">Total Salary</div>
    </div>
    
    <div style="padding:12px;border-radius:8px;background:rgba(255,255,255,0.08);text-align:center;">
        <div style="font-weight:700;">{salary_metrics.get('dead_money')}</div>
        <div style="font-size:12px;opacity:0.9;">Dead Money</div>
    </div>
    
    <div style="padding:12px;border-radius:8px;background:rgba(255,255,255,0.08);text-align:center;">
        <div style="font-weight:700;">{format_cap(salary_metrics.get('cap_space'))}</div>
        <div style="font-size:12px;opacity:0.9;">Cap Space</div>
    </div>
    
    </div>
    """

    # 4. Render the full header container
    st.markdown(
        f"""
    <div style="
        padding:8px;
        border-radius:10px;
        background:{team['neutral_color']};
        display:flex;
        justify-content:space-between;
        align-items:center;
        /* ADDED BORDER AND BOTTOM MARGIN */
        border: 2px solid {team['accent_color']}; 
        margin-bottom: 1rem;
    ">
    {left_html}
    {right_html}
    </div>
    """, unsafe_allow_html=True)
    df = roster_df.copy()

    if df.empty:
        st.info("No rostered players.")
    else:
        df.index = np.arange(1, len(df)+1)
        df_display = df[[
            "full_name", "age","position_full", "mlb_team", "salary", "contract_type", "end_year"
        ]].rename(columns={
            "full_name":"Player",
            "age":"Age",
            "position_full":"Position",
            "mlb_team":"MLB",
            "salary":"Salary",
            "contract_type":"Contract Type",
            "end_year":"Contract End"
        })
        
        st.dataframe(df_display, width='stretch', height=420)


        gcmetric_df = get_gc(team['team_id'])
        if gcmetric_df.empty:
            raw_val = "0.00"
        else:
            raw_val = gcmetric_df['gc_balance'].iat[0]

        gc_balance_text = raw_val
        left_html = f'<div style="display:inline-block;"><h3 style="margin:0;color:white;">Prospects</h3></div>'

        right_html = (
            '<div style="display:flex;gap:10px;align-items:center;">'
            f'<div style="padding:12px;border-radius:8px;background:rgba(255,255,255,0.08);text-align:center;display:inline-block;">'
            f'<div style="font-weight:700;margin-bottom:2px;">{raw_val}</div>'
            '<div style="font-size:12px;opacity:0.9;">Griffey Coin</div>'
            '</div>'
            '</div>'
        )
        if prospects_df.empty:
            st.info("No prospects recorded.")
        else:
            # show list with eligibility
            prospects_display = prospects_df[["player_name","mlb_team","position","age","options","acquisition","overall_pick", "draft_yr","bid","rookie_eligible"]].rename(columns={
                "player_name":"Name","mlb_team":"MLB","position":"Position","age":"Age","options":"Options Remaining","acquisition":"Acquisition","overall_pick":"Overall Pick", "draft_yr":"Draft Year","bid":"Bid","rookie_eligible":"Rookie Elligible"
            })
            prospects_display.index = np.arange(1, len(prospects_display) + 1)
            st.markdown(
            f"""
        <div style="
        padding:8px;
        border-radius:10px;
        background:{team['neutral_color']};
        display:flex;
        justify-content:space-between;
        align-items:center;
        /* ADDED BORDER AND BOTTOM MARGIN */
        border: 2px solid {team['accent_color']}; 
        margin-bottom: 1rem;
        ">
        {left_html}
        {right_html}
        </div>
        """, unsafe_allow_html=True)
            st.dataframe(
                prospects_display,
                width='stretch',
                height=420
            )

    # if st.button("Go to Rookie Decisions"):
    #     st.query_params(page="rookie_decisions", team=team_id)

    st.markdown("---")
    trades_df = get_trades(team["team_id"])
    trades_display = trades_df[["player_name","mlb_team","position", "from_name", "to_name", "trade_type", "asset_type", "trade_date"]].rename(columns={
            "player_name":"Player Name/GC Amount","mlb_team":"MLB Team","position":"Position/GC Year", "from_name":"From", "to_name":"To", "trade_type":"Trade Type", "asset_type":"Asset Type", "trade_date":"Trade Date"
    })
    trades_display.index = np.arange(1, len(trades_display) + 1)
    st.markdown(f"""    <div style="
    padding:18px;
    border-radius:10px;
    background:{team['neutral_color']};
    display:flex;
    justify-content:space-between;
    align-items:center;
    /* ADDED BORDER AND BOTTOM MARGIN */
    border: 2px solid {team['accent_color']}; 
    margin-bottom: 1rem;
    "><h3 style="color:{team["neutral_color"]}">Trade History</h3></div>""", unsafe_allow_html=True)
    st.dataframe(
        trades_display,
        width='stretch',
        height=420
    )
    st.markdown("---")
    AWARD_IMAGE_MAP = {
    1: "champion.png",
    2: "runnerup.png",
    3: "reg_season_champ.png",
    4: "division_champ.png",
    5: "mvp.png",
    6: "cy_young.png",
    7: "hi_score.png",
    8: "SOTY.png",
    9: "toy.png",
    10: "poop.png",
    11: "hotdog.png"
    }
    # --- S3/R2 Setup ---
    # (Assuming your R2 keys are loaded from st.secrets or environment variables)
    s3 = boto3.client(
        service_name="s3", # Usually just 's3' for R2 via boto3
        endpoint_url=R2_ENDPOINT,
        aws_access_key_id=R2_ACCESS_KEY_ID,
        aws_secret_access_key=R2_SECRET_ACCESS_KEY,
    )
    DEFAULT_IMAGE = r"Try harder"
    @st.cache_data(ttl=3600) # Cache images for 1 hour to reduce R2 costs/latency
    def get_r2_image_as_base64(filename):
        """
        Fetches an image from R2 and converts it to a base64 string
        compatible with st.image.
        """
        object_key2 = f"{R2_DIR}/{filename}"
        
        try:
            response = s3.get_object(Bucket=R2_BUCKET, Key=object_key2)
            image_data = response["Body"].read()
            encoded_image = base64.b64encode(image_data).decode()
            return f"data:image/png;base64,{encoded_image}"
        except Exception as e:
            # Log error in console if needed: print(f"Error fetching {filename}: {e}")
            return None

        
    #st.subheader("Awards")
    trophies = get_trophies(team["team_id"])
    st.markdown(f"""    <div style="
        padding:18px;
        border-radius:10px;
        background:{team['neutral_color']};
        display:flex;
        justify-content:space-between;
        align-items:center;
        /* ADDED BORDER AND BOTTOM MARGIN */
        border: 2px solid {team['accent_color']}; 
        margin-bottom: 1rem;
        "><h3 style="color:{team["neutral_color"]}">Awards</h3></div>""", unsafe_allow_html=True)
    if trophies.empty:
        st.info("No awards recorded.")
    else:
        # Create grid
        cols = st.columns(8)
        
        for i, (_, row) in enumerate(trophies.iterrows()):
            # 1. Determine filename and text
            award_id = row['award_id']
            file_name = AWARD_IMAGE_MAP.get(award_id, DEFAULT_IMAGE)
            season_text = str(row['season'])
            tooltip_text = row['award_text'].replace("_", " ").title() # This appears on hover
            
            # 2. Fetch image
            img_src = get_r2_image_as_base64(file_name)
            
            # 3. Render using HTML to get the tooltip functionality
            with cols[i % 8]:
                if img_src:
                    # We use HTML <img> because it supports the 'title' attribute (hover text)
                    html_code = f"""
                        <div style="display: flex; flex-direction: column; align-items: center;">
                            <img src="{img_src}" title="{tooltip_text}" style="width: 100px; height: 100px; object-fit: contain; margin-bottom: 5px;">
                            <span style="font-size: 0.8em; color: #888;">{season_text}</span>
                        </div>
                    """
                    st.markdown(html_code, unsafe_allow_html=True)
                else:
                    st.warning("Img Missing")
                    st.caption(season_text)


def main():
    teams_df = load_teams()
    if teams_df.empty:
        st.error("No teams found. Load teams into the `teams` table or use the CSV import.")
        return

    team_slugs = teams_df["team_id"].tolist()
    default_slug = team_slugs[0]

    #st.sidebar.title("League")
    page = "Team Dashboard"
    #team_slug = st.sidebar.selectbox("Select Team", team_slugs, index=team_slugs.index(default_slug))

    if page == "Team Dashboard":
        page_team_dashboard("team_id")
    

if __name__ == "__main__":
    main()

