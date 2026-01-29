import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import sys

# Mock secrets if running standalone (but usually st.secrets works if file exists)
# usage: streamlit run check_gsheet_size.py

st.title("GSheet Size Checker")

if "connections" in st.secrets and "gsheets" in st.secrets["connections"]:
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        
        sheet_url = st.secrets["sheets"]["rider_db"]
        st.write(f"Checking URL: {sheet_url}")
        
        df = conn.read(spreadsheet=sheet_url)
        st.metric("Rider DB Rows", len(df))
        st.write("First 5 rows:")
        st.dataframe(df.head())
        
        if len(df) < 500:
            st.warning("Only a few rows found. Is this the right sheet?")
        else:
            st.success(f"Found {len(df)} rows. The data exists!")
            
    except Exception as e:
        st.error(f"Error: {e}")
else:
    st.error("No secrets found!")
