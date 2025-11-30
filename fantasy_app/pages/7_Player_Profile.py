import streamlit as st
import sqlite3
import pandas as pd
import os
import altair as alt
import streamlit_authenticator as stauth

# --- Page Access Protection ---
if "authentication_status" not in st.session_state or st.session_state["authentication_status"] != True:
    st.error("You must log in to access this page.")
    st.stop()  # Prevents the rest of the page from rendering

DB_PATH = st.secrets["DB_PATH"]

def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def query(sql, params=()):
    conn = get_conn()
    df = pd.read_sql_query(sql, conn, params=params)
    new_index = range(1, len(df) + 1)
    df.index = new_index
    conn.close()
    return df

def execute(sql, params=()):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(sql, params)
    conn.commit()
    lastrowid = cur.lastrowid
    conn.close()
    return lastrowid

def executemany(sql, data_list):
    conn = get_conn()
    cur = conn.cursor()
    cur.executemany(sql, data_list)
    conn.commit()
    conn.close()

st.title("Player Profile")

# -------------------------------------
# 1) TEAM DROPDOWN
# -------------------------------------
teams = query("SELECT team_id, team_name FROM teams ORDER BY team_name")
team_map = {row["team_name"]: row["team_id"] for _, row in teams.iterrows()}

team_name = st.selectbox("Select a team", list(team_map.keys()))
team_id = team_map[team_name]

# -------------------------------------
# 2) PLAYER DROPDOWN (filtered by team)
# -------------------------------------
players = query("""
    SELECT p.player_id, p.full_name
    FROM roster r
    JOIN players p ON r.player_id = p.player_id
                LEFT JOIN prospects pr on pr.player_id = p.player_id
    WHERE r.team_id = ?
                and pr.player_id is null
    ORDER BY p.full_name
""", (team_id,))

player_map = {row["full_name"]: row["player_id"] for _, row in players.iterrows()}

player_name = st.selectbox("Select a player", list(player_map.keys()))
player_id = player_map[player_name]

# -------------------------------------
# 3) GET bref_id FOR IMAGE LOADING
# -------------------------------------
pid = query("""
    SELECT bref_id
    FROM player_ids
    WHERE player_id = ?
""", (player_id,))

if len(pid) == 0:
    bref_id = None
else:
    bref_id = pid.iloc[0]["bref_id"]

# -------------------------------------
# 4) Load Player Image
# -------------------------------------
image_folder = os.path.join("fantasy_app", "pages", "player_photos")

image_path_jpg = os.path.join(image_folder, f"{bref_id}.jpg")
image_path_png = os.path.join(image_folder, f"{bref_id}.png")

st.subheader("Player Photo")
col1, col2, col3 = st.columns([2, 3, 1]) 
with col2:
    if bref_id is None:
        st.warning("No bref_id found for this player.")
    elif os.path.exists(image_path_jpg):
        st.image(image_path_jpg, width=200)
    elif os.path.exists(image_path_png):
        st.image(image_path_png, width=200)
    else:
        st.warning("No photo available for this player.")

# -------------------------------------
# 5) Contract Information
# -------------------------------------
st.subheader("Contract Information")

contract = query("""
    SELECT salary AS Salary, end_year as 'Contract End'
    FROM contracts
    WHERE player_id = ?
""", (player_id,))

if len(contract) > 0:
    st.dataframe(
        contract,
        column_config={
            "Salary": st.column_config.NumberColumn(
                "Salary",
                help="Player's annual salary",
                # Format string "$%.2f" enforces 2 decimal places and a dollar sign
                format="$%.2f", 
            ),
            "Contract End": st.column_config.NumberColumn(
                "Contract End",
                format="%d",
        
            )
        },
    hide_index=True
    )    
else:
    st.write("No contract found.")
# -------------------------------------
# 6) Career Stats (from game_stats)
# -------------------------------------
st.subheader("Career Stats")

stats = query("""
    SELECT 
        gs.season as Season, 
        sum(gs.fpts) as Points, 
        
        -- Hitting Stats
        sum(gs.[1b]) as Singles, sum(gs.[2b]) as Doubles, sum(gs.[3b]) as Triples, 
        sum(gs.hr) as HR, sum(gs.bb_hbp) as 'BB/HBP', sum(gs.so) as SO, 
        sum(gs.sb) as 'Stolen Base', sum(gs.cs) as 'Caught Stealing', sum(gs.gidp_h) as 'Grounded Into Double Play',
        sum(gs.cyc) as Cycle, sum(gs.mobg) as 'Multi On Base Game', sum(gs.r) as R, 
        sum(gs.rbi) as RBI,
        
        -- Pitching Stats
        sum(gs.cg) as 'Complete Game', sum(gs.sho) as 'Shutout', sum(gs.w) as Win, sum(gs.l) as Loss,
        sum(gs.sv) as Saves, sum(gs.hld) as Holds, sum(gs.ip) as 'Innings Pitched', sum(gs.h_allowed) as 'Hits Allowed',
        sum(gs.r_p) as 'Runs Allowed', sum(gs.er) as 'Earned Runs', sum(gs.bb) as Walks, sum(gs.hb) as 'Hit Batter',
        sum(gs.k) as Strikeouts, sum(gs.gidp_p) as 'Grounded into Double Play Against', sum(gs.nh) as 'No Hitter', sum(gs.pg) as 'Perfect Game',
        
        MAX(p.is_pitcher) AS pflag -- Get the player type flag
    FROM game_stats gs
    LEFT JOIN players p on gs.player_name = p.full_name
    LEFT JOIN prospects pr on p.player_id = pr.player_id
    JOIN roster r ON p.player_id = r.player_id
    WHERE p.player_id = ?
    and pr.player_id IS NULL
    GROUP BY gs.Season
    ORDER BY gs.Season
""", (player_id,))

if len(stats) == 0:
    st.write("No stats available.")
    st.stop()
if stats.pflag.any():
    columns_to_display = [
        'Season', 'Points', 'Complete Game', 'Shutout', 'Win', 'Loss', 'Saves', 'Holds', 'Innings Pitched', 'Strikeouts',
        'Earned Runs', 'Walks', 'Hit Batter', 'Hits Allowed', 'Runs Allowed', 'Grounded into Double Play Against', 'No Hitter', 'Perfect Game'
    ]
else:
    # Define columns for a position player (your original list + the new ones)
    columns_to_display = [
        'Season', 'Points', 'Singles', 'Doubles', 'Triples', 'HR', 'BB/HBP',
        'SO', 'Stolen Base', 'Caught Stealing', 'Grounded Into Double Play', 'Cycle', 'Multi On Base Game', 'R', 'RBI'
    ]
st.dataframe(stats[columns_to_display])    


#st.dataframe(stats)

# -------------------------------------
# 7) Select Stat Category for Graph
# -------------------------------------
# Exclude non-numeric fields
exclude_cols = {"player_id", "Season"}
numeric_cols = [
    col for col in stats.columns 
    if col not in exclude_cols and pd.api.types.is_numeric_dtype(stats[col])
]

category = st.selectbox(
    "Select a stat category to graph",
    numeric_cols
)

# -------------------------------------
# 8) Altair Line Chart
# -------------------------------------
chart = (
    alt.Chart(stats)
    .mark_line(point=True)
    .encode(
        x=alt.X("Season:O", title="Season"),
        y=alt.Y(f"{category}:Q", title=category),
        tooltip=["Season", category]
    )
    .properties(
        width=700,
        height=400,
        title=f"{player_name} — {category} by Season"
    )
)

st.altair_chart(chart)
