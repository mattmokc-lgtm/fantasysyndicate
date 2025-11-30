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
import matplotlib.pyplot as plt
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

@st.cache_data(show_spinner=False)

def read_sql_df(query_str, params=None):
    with engine.connect() as conn:
        return pd.read_sql(query_str, conn, params=params)

@st.cache_data(ttl=60)
def load_teams():
    q = "SELECT team_id,  location||team_name as team_name, division, logo_url, banner_url, primary_color, secondary_color, accent_color, neutral_color, additional_color, fantrax_url FROM teams ORDER BY team_name"
    return read_sql_df(q)

@st.cache_data(ttl=60)
def load_matchups():
    q = """WITH GameResults AS (
        SELECT team_id, season, period, matchup, result
        FROM fantasy.game_stats
        GROUP BY team_id, season, period, matchup, result
    ),
    HeadToHeadData AS (
        SELECT
            T1.team_id AS Team_ID,
            T2.team_id AS Opponent_ID,
            SUM(CASE WHEN T1.result = 'W' THEN 1 ELSE 0 END) AS Head_to_Head_Wins,
            SUM(CASE WHEN T2.result = 'W' THEN 1 ELSE 0 END) AS Head_to_Head_Losses
        FROM GameResults T1
        INNER JOIN GameResults T2
            ON T1.matchup = T2.matchup
            AND T1.period = T2.period
            AND T1.season = T2.season
            AND T1.team_id != T2.team_id
        GROUP BY T1.team_id, T2.team_id
    )
    SELECT
        g.Team_ID,
        tm.location || ' ' || tm.team_name AS Team_Name,
        g.Opponent_ID,
        o.location || ' ' || o.team_name AS Opponent_Name,
        Head_to_Head_Wins,
        Head_to_Head_Losses,
        (Head_to_Head_Wins + Head_to_Head_Losses) AS Total_Pairings,
        (Head_to_Head_Wins - Head_to_Head_Losses) AS Win_Differential,
        CAST(Head_to_Head_Wins AS REAL) * 100.0 /
            (Head_to_Head_Wins + Head_to_Head_Losses) AS Win_Percentage,
        ABS(Head_to_Head_Wins - Head_to_Head_Losses) AS Absolute_WinDiff
    FROM HeadToHeadData g
    LEFT JOIN fantasy.teams tm ON tm.team_id = g.Team_ID
    LEFT JOIN fantasy.teams o  ON o.team_id = g.Opponent_ID
    ORDER BY Team_ID, Opponent_ID, Total_Pairings DESC;
    """
    return read_sql_df(q)

df = load_matchups() 
col_left, col_right = st.columns([2, 1])


# =======================================================
# CODE FOR THE LEFT COLUMN (DataFrame/Selectbox)
# =======================================================
with col_left:
    st.subheader("Team Head-to-Head Analytics")
    
    teams = sorted(df["team_name"].unique())
    team_choice = st.selectbox("Select a team", teams)
    
    filtered = df[df["team_name"] == team_choice]
    
    if filtered.empty:
        st.info("No team selected.")
    else:
        # Sort and format the DataFrame for display
        filtered = filtered.sort_values("win_percentage", ascending=False)
        filtered = filtered.reset_index(drop=True)
        filtered.index += 1
        
        # Format win percentage as integer string with % sign
        filtered['win_percentage_formatted'] = filtered['win_percentage'].apply(lambda x: f"{x:.0f}%")
    
        filtered_display = filtered[[
            "opponent_name", "head_to_head_wins", "head_to_head_losses",
            "win_percentage_formatted", "total_pairings"
        ]].rename(columns={
            "opponent_name":"Opponent Name", 
            "head_to_head_wins":"Wins", 
            "head_to_head_losses":"Losses",
            "win_percentage_formatted":"Win Percentage", 
            "total_pairings":"Total Games Played"
        })

        st.dataframe(filtered_display, use_container_width=True, height=492)


# =======================================================
# CODE FOR THE RIGHT COLUMN (Rivalries)
# =======================================================
with col_right:
    st.subheader("Top Rivalries")

    # --- Rivalry Data Processing Logic ---
    # (The custom filtering loop from your previous code block)
    df['team1'] = df.apply(lambda row: min(row['team_name'], row['opponent_name']), axis=1)
    df['team2'] = df.apply(lambda row: max(row['team_name'], row['opponent_name']), axis=1)
    df['pairing_id'] = df['team1'] + ' vs ' + df['team2']
    df_sorted = df.sort_values("total_pairings", ascending=False)

    selected_pairings = []
    teams_accounted_for = set()

    for index, row in df_sorted.iterrows():
        team_a = row['team_name']
        team_b = row['opponent_name']
        
        if team_a not in teams_accounted_for and team_b not in teams_accounted_for:
            selected_pairings.append(row)
            teams_accounted_for.add(team_a)
            teams_accounted_for.add(team_b)
            
            if len(teams_accounted_for) == 14:
                break
                
    rivalries_list = pd.DataFrame(selected_pairings).sort_values("team_name", ascending=True)


    for _, r in rivalries_list.iterrows():
        # Using the zero-decimal format
        card_markdown = f"""
            <div style="padding:15px;border-radius:10px;margin-bottom:10px;
                        background:rgba(255,255,255,0.05);border:1px solid #444;">
                <b>{r['team_name']}</b> vs <b>{r['opponent_name']}</b><br>
                Games: {r['total_pairings']} |
                Record: {r['head_to_head_wins']}-{r['head_to_head_losses']} |
                WinPct: {r['win_percentage']:.0f}%
            </div>
        """
        
        st.markdown(
            card_markdown,
            unsafe_allow_html=True
        )




pivot = df.pivot(
    index="team_name",
    columns="opponent_name",
    values="win_percentage"
)

fig, ax = plt.subplots(figsize=(6, 4))

im = ax.imshow(pivot, cmap="RdYlGn", vmin=0, vmax=100)

# Axis labels
ax.set_xticks(np.arange(len(pivot.columns)))
ax.set_xticklabels(pivot.columns, rotation=45, ha="right", fontsize=6)

ax.set_yticks(np.arange(len(pivot.index)))
ax.set_yticklabels(pivot.index, fontsize=6)

# Cell text with contrast
for i in range(len(pivot.index)):
    for j in range(len(pivot.columns)):
        value = pivot.iloc[i, j]
        if not np.isnan(value):
            text_color = "black"
            ax.text(j, i, f"{value:.0f}%", ha="center", va="center", color=text_color, fontsize=6)

# Add colorbar
cbar = fig.colorbar(im)
cbar.set_label("Win % vs Opponent")

st.pyplot(fig)
