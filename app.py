import sys
from pathlib import Path
import streamlit as st

# Ensures Python can locate your backend modules
ROOT_DIR = Path(__file__).resolve().parent
sys.path.append(str(ROOT_DIR))

from app.engine import screen 

st.set_page_config(page_title="Weekly Bullish Scanner", layout="wide")

st.title("📈 Weekly Bullish Scanner")
st.write("Welcome to your stock scanner dashboard. Click the button below to run the scan.")

# Here we define all the default parameters your engine is asking for
scan_parameters = {
    "mode": "standard",
    "days": 20,
    "target": 5.0,
    "stop": 3.0,
    "exchange": "both",
    "min_turnover": 1000000,
    "capital": 100000,
    "risk": 1.0,
    "min_hit": 0.0
}

if st.button("Run Scan"):
    with st.spinner("Running market scan... Please wait."):
        try:
            # Pass the fully populated parameters instead of an empty dictionary
            results = screen(scan_parameters) 
            
            st.success("Scan completed successfully!")
            
            if results and results.get("ranked"):
                st.dataframe(results["ranked"])
            else:
                st.info("Scan finished, but no matches were found.")
                
        except Exception as e:
            st.error(f"An error occurred while running the scanner: {e}")
