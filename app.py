import sys
from pathlib import Path
import streamlit as st

ROOT_DIR = Path(__file__).resolve().parent
sys.path.append(str(ROOT_DIR))

from app.engine import screen 

st.set_page_config(page_title="Weekly Bullish Scanner", layout="wide")

st.title("📈 Weekly Bullish Scanner")
st.write("Adjust your trade filters below.")

# --- THE INTERACTIVE UI BOXES ---
col1, col2, col3 = st.columns(3)
with col1:
    # This box captures the target return
    target_pct = st.number_input("Target Return (%)", min_value=0.5, max_value=100.0, value=5.0, step=0.5)
with col2:
    # This box captures the holding days
    holding_days = st.number_input("Holding Period (Days)", min_value=1, max_value=365, value=20, step=1)
with col3:
    # This box captures the stop loss
    stop_pct = st.number_input("Stop Loss (%)", min_value=0.5, max_value=50.0, value=3.0, step=0.5)
st.write("---")

# --- CONNECTING THE BOXES TO YOUR FUNCTION ---
scan_parameters = {
    "mode": "standard",
    "days": int(holding_days),     # Fed directly from UI box
    "target": float(target_pct),   # Fed directly from UI box
    "stop": float(stop_pct),       # Fed directly from UI box
    "exchange": "both",
    "min_turnover": 1000000,
    "capital": 100000,
    "risk": 1.0,
    "min_hit": 0.0
}

if st.button("Run Scan"):
    with st.spinner(f"Scanning for {target_pct}% target over {holding_days} days..."):
        try:
            # Passes the UI parameters to your backend
            results = screen(scan_parameters) 
            
            # --- DIAGNOSTICS: Check if data actually exists ---
            funnel = results.get("funnel", {})
            total_scanned = funnel.get("with_history", 0)
            
            if total_scanned == 0:
                st.error("🚨 CRITICAL ERROR: The scanner searched 0 stocks. Your Streamlit app is missing the historical data file (e.g., features.pkl or database). You need to upload your data file to GitHub or run your data ingester on Streamlit.")
            else:
                st.success(f"Scan completed! Analyzed {total_scanned} stocks.")
                
                if results and results.get("ranked"):
                    st.dataframe(results["ranked"])
                else:
                    st.warning(f"No stocks met your exact criteria of {target_pct}% return in {holding_days} days. Try adjusting the filters.")
                
        except Exception as e:
            st.error(f"An error occurred while running the scanner: {e}")
