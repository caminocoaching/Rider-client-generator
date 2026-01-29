import streamlit as st
import pandas as pd
from funnel_manager import DataLoader
import os

st.title(" Pipeline GSheet Debugger")

if "sheets" not in st.secrets:
    st.error("No [sheets] section in secrets.toml")
    st.stop()

secrets = st.secrets["sheets"]
st.write("### 1. Secrets Found")
st.json({k: "***" for k in secrets.keys()})

# Keys we expect
EXPECTED_KEYS = ["strategy_apps", "day2_assessment", "blueprint_regs"]
st.write(f"### 2. Checking Expected Keys: {EXPECTED_KEYS}")

from gsheets_loader import load_google_sheet

overrides = {}

for key in EXPECTED_KEYS:
    url = secrets.get(key)
    st.write(f"#### Checking `{key}`")
    if not url:
        st.warning(f"❌ Key `{key}` not found in secrets!")
        continue
        
    try:
        df = load_google_sheet(url)
        if df is not None:
            st.success(f"✅ Loaded {len(df)} rows.")
            st.write(f"**Columns:** `{list(df.columns)}`")
            
            # Check for email
            has_email = any('email' in c.lower() for c in df.columns)
            if not has_email:
                st.error("❌ No 'email' column found! This file will be skipped.")
            else:
                st.info("✅ Email column present.")
                
            # Check for dates
            date_cols = [c for c in df.columns if 'date' in c.lower() or 'created' in c.lower() or 'finished' in c.lower()]
            st.write(f"**Date Candidates:** `{date_cols}`")
            
            # Store for simulator
            fname_map = {
                "strategy_apps": "Strategy Call Application.csv",
                "day2_assessment": "Day 2 Self Assessment.csv"
            }
            if key in fname_map:
                overrides[fname_map[key]] = df
                
        else:
            st.error("❌ Failed to load DataFrame (None returned).")
    except Exception as e:
        st.error(f"❌ Exception loading: {e}")

st.write("### 3. Simulation")
if st.button("Simulate Pipeline Load"):
    # Init loader with overrides
    # logic from app.py
    data_dir = os.path.dirname(os.path.abspath(__file__))
    dl = DataLoader(data_dir, overrides=overrides)
    
    # Manually run the specific loaders
    st.write("Running `_load_strategy_call_applications`...")
    dl._load_strategy_call_applications()
    
    st.write("Running `_load_day2_assessments`...")
    dl._load_day2_assessments()
    
    # Check results
    strategies = [r for r in dl.riders.values() if r.current_stage.value == "Strategy Call"]
    day2s = [r for r in dl.riders.values() if r.current_stage.value == "Day 2"]
    
    st.metric("Strategy Calls Found", len(strategies))
    st.metric("Day 2s Found", len(day2s))
    
    if len(strategies) > 0:
        st.write("Sample Strategy Call:", strategies[0].__dict__)
