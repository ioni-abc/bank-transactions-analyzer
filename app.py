import streamlit as st
import pandas as pd
import sqlite3
from pathlib import Path

DATA_PATH = Path(__file__).parent / "data"
DB_PATH = DATA_PATH / "transactions.db"

@st.cache_resource
def get_connection():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

conn = get_connection()

st.title("Expense Analyzer")

# Get available months
months = pd.read_sql("""
    SELECT DISTINCT strftime('%Y-%m', date) as month
    FROM transactions
    WHERE amount < 0 AND category != 'Self-transfer'
    ORDER BY month DESC
""", conn)["month"].tolist()

selected_month = st.selectbox("Select month", months)

# Get categories for that month
df = pd.read_sql(f"""
    SELECT category,
           ROUND(SUM(amount), 2) as total,
           COUNT(*) as transactions
    FROM transactions
    WHERE amount < 0
      AND strftime('%Y-%m', date) = '{selected_month}'
      AND category != 'Self-transfer'
    GROUP BY category
    ORDER BY total
""", conn)

# Category toggles
exclude = st.multiselect("Exclude categories", df["category"].tolist())

# Filter and display
filtered = df[~df["category"].isin(exclude)]
total = filtered["total"].sum()

st.metric("Total Spending", f"€{total:,.2f}")
st.dataframe(filtered, use_container_width=True, height=(len(filtered) + 1) * 35 + 3)