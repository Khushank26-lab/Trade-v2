import sys
from pathlib import Path
import streamlit as st

# Ensures Python can locate your backend modules
ROOT_DIR = Path(__file__).resolve().parent
sys.path.append(str(ROOT_DIR))

# THE FIX IS HERE: We import 'screen' instead of 'run_scanner'
from app.engine import screen 

st.set_page_config(page_title="Weekly Bullish Scanner", layout="wide")

st.title("📈 Weekly Bullish Scanner")
st.write("Welcome to your stock scanner dashboard. Click the button below to run the scan.")

if st.button("Run Scan"):
    with st.spinner("Running market scan... Please wait."):
        try:
            # Pass an empty dictionary so it uses your default parameters
            results = screen({}) 
            
            st.success("Scan completed successfully!")
            
            if results and results.get("ranked"):
                st.dataframe(results["ranked"])
            else:
                st.info("Scan finished, but no matches were found.")
                
        except Exception as e:
            st.error(f"An error occurred while running the scanner: {e}")
