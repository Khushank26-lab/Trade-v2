import sys
from pathlib import Path
import streamlit as st

# Ensures Python can locate your backend modules
ROOT_DIR = Path(__file__).resolve().parent
sys.path.append(str(ROOT_DIR))

from app.engine import screen 

st.set_page_config(page_title="Weekly Bullish Scanner", layout="wide")

st.title("📈 Weekly Bullish Scanner")
st.write("Welcome to your stock scanner dashboard. Adjust your trade filters below.")

# --- INTERACTIVE UI FILTERS ---
col1, col2, col3 = st.columns(3)

with col1:
    target_pct = st.number_input("Target Return (%)", min_value=0.5, max_value=100.0, value=5.0, step=0.5)

with col2:
    holding_days = st.number_input("Holding Period (Days)", min_value=1, max_value=365, value=20, step=1)

with col3:
    stop_pct = st.number_input("Stop Loss (%)", min_value=0.5, max_value=50.0, value=3.0, step=0.5)

st.write("---")

# Map your UI inputs into the scanner parameters
scan_parameters = {
    "mode": "standard",
    "days": int(holding_days),
    "target": float(target_pct),
    "stop": float(stop_pct),
    "exchange": "both",
    "min_turnover": 1000000,
    "capital": 100000,
    "risk": 1.0,
    "min_hit": 0.0
}

if st.button("Run Scan"):
    with st.spinner(f"Scanning for {target_pct}% target over {holding_days} days..."):
        try:
            results = screen(scan_parameters) 
            
            st.success("Scan completed successfully!")
            
            if results and results.get("ranked"):
                st.dataframe(results["ranked"])
            else:
                st.warning(f"No stocks found matching a {target_pct}% return in {holding_days} days. Try adjusting the filters (e.g., lower target or higher days).")
                
        except Exception as e:
            st.error(f"An error occurred while running the scanner: {e}")
