import sys
from pathlib import Path

# Ensures Python can locate your backend modules
ROOT_DIR = Path(__file__).resolve().parent
sys.path.append(str(ROOT_DIR))

import streamlit as st

# THE FIX IS HERE: We import 'screen' because that is the actual name in engine.py
from app.engine import screen 

st.set_page_config(page_title="Weekly Bullish Scanner", layout="wide")

st.title("📈 Weekly Bullish Scanner")
st.write("Welcome to your stock scanner dashboard. Click the button below to run the scan.")

# Button to trigger your backend scan
if st.button("Run Scan"):
    with st.spinner("Running market scan... Please wait."):
        try:
            # Call your engine function with an empty dictionary to use defaults
            results = screen({}) 
            
            st.success("Scan completed successfully!")
            
            # Display the ranked stock results on the screen
            if results and results.get("ranked"):
                st.dataframe(results["ranked"])
            else:
                st.info("Scan finished, but no matches were found.")
                st.write(results) # Show raw output just in case
                
        except Exception as e:
            st.error(f"An error occurred while running the scanner: {e}")
