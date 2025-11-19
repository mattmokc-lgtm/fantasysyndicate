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
SELECT 
    SUM(COALESCE(g.salary, 0)) AS "Salary Total", 
    SUM(COALESCE(g.retained_salary, 0)) AS "Retained Salary",        
    SUM(COALESCE(g.salary, 0) + COALESCE(g.retained_salary, 0)) AS "Total Cap Hit", 
    100 - SUM(COALESCE(g.salary, 0) + COALESCE(g.retained_salary, 0)) AS "Cap Space"
FROM 
    (SELECT 
        p.full_name AS Player,
        COALESCE(c.salary, 0) AS Salary,
        COALESCE(ret.retained_salary, 0) AS Retained_Salary,
        CASE 
            WHEN r.team_id = ? THEN ?
            WHEN ret.team_id = ? THEN ?
            ELSE NULL
        END AS Target_Team_ID
    FROM roster r
    JOIN players p ON r.player_id = p.player_id
    LEFT JOIN contracts c ON p.player_id = c.player_id AND c.team_id = r.team_id
    LEFT JOIN teams t ON c.team_id = t.team_id
    LEFT JOIN retention ret ON ret.player_id = p.player_id
    LEFT JOIN teams debtor_team ON ret.team_id = debtor_team.team_id
    WHERE
        c.status NOT LIKE '%PR%'
        AND c.end_year > 2025
        AND (t.active = 1 OR debtor_team.active = 1)
    ) G
WHERE G.Target_Team_ID = ?
GROUP BY G.Target_Team_ID
""", (team_id, team_id, team_id, team_id, team_id))

prospect = query("""
                     SELECT player_name as 'Player Name', 
    mlb_team AS 'Team', 
    position as Position, 
    age as Age, 
    options as Options, 
    draft_yr as 'Draft Year',  
    COALESCE(overall_pick, (CASE WHEN acquisition = 'top 100 auction' THEN acquisition ELSE 'Old Draft' END)) as 'Overall Draft Pick', 
    COALESCE(bid,'N/A') as 'GC Bid'
    FROM prospects
    WHERE team_id = ? AND rookie_eligible = 0 and acquisition <> 'unowned'""",(team_id,))

st.subheader('Cap Data')

st.dataframe(
    cap,
    # Use column_config to target the 'Salary' column by its displayed name
    column_config={
        "Salary Total": st.column_config.NumberColumn(
            "Salary Total",
            help="The Sum of all current player's annual salary",
            # Format string "$%.2f" enforces 2 decimal places and a dollar sign
            format="$%.2f", 
        ),
        "Cap Space": st.column_config.NumberColumn(
            "Cap Space",
            help="The total amount of money left out of the $100 cap limit",
            format="$%.2f",
        ),
        "Retained Salary": st.column_config.NumberColumn(
            "Retained Salary",
            help="The total amount of money still owed on contracts for traded players",
            format="$%.2f",
        ),
        "Total Cap Hit": st.column_config.NumberColumn(
            "Total Cap Hit",
            help="he Sum of all current player's annual salary plus retention",
            format="$%.2f",
        )
    },
    
    hide_index=True
)

st.subheader("Active Roster")
st.dataframe(
    roster,
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

st.subheader("Prospect List")
st.dataframe(
    prospect,
    column_config={
        "GC Bid": st.column_config.NumberColumn(
            "GC Bid",
            help="Amount of GC bid on a prospect during auction or prospect draft",
            # Format string "$%.2f" enforces 2 decimal places and a dollar sign
            format="$%.2f", 
        )
    },
   
)