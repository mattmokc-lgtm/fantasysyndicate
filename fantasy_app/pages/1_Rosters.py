import streamlit as st
#import fantasy_app.database import query
import sqlite3
import pandas as pd


DB_PATH = "/workspaces/fantasysyndicate/fantasy_app/pages/fantasy.db"

def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def query(sql, params=()):
    conn = get_conn()
    df = pd.read_sql_query(sql, conn, params=params)
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

st.title("Team Rosters")

teams = query("SELECT team_id, team_name, (location || ' ' || team_name) AS Full_Name FROM teams WHERE active = 1 ORDER BY team_id")
team_map = {row["Full_Name"]: row["team_id"] for _, row in teams.iterrows()}

team_name = st.selectbox("Select your team", list(team_map.keys()))
team_id = team_map[team_name]

roster = query("""
    SELECT p.full_name AS Player, p.position_full AS Position, c.salary AS Salary, c.end_year AS 'Contract End'
    FROM roster r
    JOIN players p ON r.player_id = p.player_id
    LEFT JOIN contracts c ON p.player_id = c.player_id AND c.team_id = r.team_id
    LEFT JOIN teams t on c.team_id = t.team_id
    WHERE r.team_id = ?
    AND c.status NOT LIKE '%PR%'
    AND c.end_year > 2025
    AND t.active = 1
    ORDER BY p.full_name
""", (team_id,))

cap = query("""
    SELECT SUM(Salary) AS 'Salary Total', (100 - SUM(SALARY)) AS 'Cap Space' FROM (SELECT p.full_name AS Player, p.position_full AS Position, c.salary AS Salary, c.end_year AS 'Contract End', r.team_id
    FROM roster r
    JOIN players p ON r.player_id = p.player_id
    LEFT JOIN contracts c ON p.player_id = c.player_id AND c.team_id = r.team_id
    LEFT JOIN teams t on c.team_id = t.team_id
    WHERE r.team_id = ?
    AND c.status NOT LIKE '%PR%'
    AND c.end_year > 2025
    AND t.active = 1
    ) G GROUP BY team_id
""", (team_id,))
st.subheader('Cap Data')

st.dataframe(
    cap,
    # Use column_config to target the 'Salary' column by its displayed name
    column_config={
        "Salary Total": st.column_config.NumberColumn(
            "Salary Total",
            help="The Sum of all player's annual salary",
            # Format string "$%.2f" enforces 2 decimal places and a dollar sign
            format="$%.2f", 
        ),
        "Cap Space": st.column_config.NumberColumn(
            "Cap Space",
            help="The total amount of money left out of the $100 cap limit",
            format="$%.2f",
        )
    },
    
    hide_index=True
)

st.subheader("Active Roster")
st.dataframe(
    roster,
    # Use column_config to target the 'Salary' column by its displayed name
    column_config={
        "Salary": st.column_config.NumberColumn(
            "Salary",
            help="Player's annual salary",
            # Format string "$%.2f" enforces 2 decimal places and a dollar sign
            format="$%.2f", 
        ),
        "Contract End": st.column_config.NumberColumn(
            "Contract End",
            format="%d" # Optional: Format year as an integer with no decimals
        )
    },
   
)