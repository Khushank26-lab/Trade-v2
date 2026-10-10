import sys
import os
import threading
from pathlib import Path
import streamlit as st

ROOT_DIR = Path(__file__).resolve().parent
sys.path.append(str(ROOT_DIR))

from app.engine import screen 

st.set_page_config(page_title="Weekly Bullish Scanner", layout="wide")

# --- 1. AUTOMATIC BACKGROUND DOWNLOADER ---
# @st.cache_resource ensures this only triggers once when the server boots
@st.cache_resource
def auto_update_data():
    def run_worker():
        os.system("python app/worker.py")
    
    # Starts downloading silently in the background so the UI doesn't freeze
    thread = threading.Thread(target=run_worker)
    thread.start()
    return True

# Trigger the auto-downloader
auto_update_data()

# --- 2. MAIN DASHBOARD ---
st.title("📈 Weekly Bullish Scanner")
st.info("🔄 **Auto-Updater Active:** The engine automatically checks for and downloads missing market data in the background.")

col1, col2, col3 = st.columns(3)
with col1:
    target_pct = st.number_input("Target Return (%)", min_value=0.5, max_value=100.0, value=5.0, step=0.5)
with col2:
    holding_days = st.number_input("Holding Period (Days)", min_value=1, max_value=365, value=20, step=1)
with col3:
    stop_pct = st.number_input("Stop Loss (%)", min_value=0.5, max_value=50.0, value=3.0, step=0.5)
st.write("---")

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
            
            funnel = results.get("funnel", {})
            total_scanned = funnel.get("with_history", 0)
            
            if total_scanned == 0:
                st.warning("⏳ Data is currently downloading in the background. Please wait a few minutes and click Scan again.")
            else:
                st.success(f"Scan completed! Analyzed {total_scanned} stocks.")
                
                if results and results.get("ranked"):
                    st.dataframe(results["ranked"])
                else:
                    st.warning("No stocks met your exact criteria. Try adjusting the filters.")
                
        except Exception as e:
            st.error(f"An error occurred while running the scanner: {e}")
