import sys
from pathlib import Path

# Ensures Python can locate your backend modules
ROOT_DIR = Path(__file__).resolve().parent
sys.path.append(str(ROOT_DIR))

import streamlit as st
from app.engine import run_scanner  # Imports your scanner engine

st.set_page_config(page_title="Weekly Bullish Scanner", layout="wide")

st.title("📈 Weekly Bullish Scanner")
st.write("Welcome to your stock scanner dashboard. Click the button below to run the scan.")

# Button to trigger your backend scan
if st.button("Run Scan"):
    with st.spinner("Running market scan... Please wait."):
        try:
            # Call your engine function (adjust parameters if your main.py/engine.py requires them)
            results = run_scanner()
            st.success("Scan completed successfully!")
            
            # Display results if returned as a DataFrame or data
            if results is not None:
                st.dataframe(results)
            else:
                st.info("Scan finished, but no results were returned.")
                
        except Exception as e:
            st.error(f"An error occurred while running the scanner: {e}")
