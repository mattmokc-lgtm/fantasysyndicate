# database.py
import sqlite3
import pandas as pd

DB_PATH = "fantasy.db"

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
