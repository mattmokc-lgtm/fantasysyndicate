import streamlit as st
from fantasy_app.database import query

st.title("Team Rosters")

teams = query("SELECT team_id, team_name FROM teams ORDER BY team_name")
team_map = {row["team_name"]: row["team_id"] for _, row in teams.iterrows()}

team_name = st.selectbox("Select your team", list(team_map.keys()))
team_id = team_map[team_name]

roster = query("""
    SELECT p.full_name, p.position_full, c.salary, c.end_year, r.acquired_via
    FROM roster r
    JOIN players p ON r.player_id = p.player_id
    LEFT JOIN contracts c ON p.player_id = c.player_id AND c.team_id = r.team_id
    WHERE r.team_id = ?
    ORDER BY p.full_name
""", (team_id,))

st.subheader("Active Roster")
st.dataframe(roster)
