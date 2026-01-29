
import streamlit as st
from airtable_manager import AirtableManager
from funnel_manager import FunnelDashboard
import pandas as pd
import json
import os

print("🏥 STARTING HEALTH CHECK 🏥")
print("===========================")

# 1. LOAD CONFIG
# (We assume secrets are loaded if running with streamlit run, but here we might need manual loading if CLI)
# Just use FunnelManager which handles it?
# But FunnelManager depends on st.secrets usually.
# We will simulate st.secrets if we can, or rely on them being present if we run via streamlit.

# 1. LOAD CONFIG
import toml
try:
    # Try loading manually if not in streamlit context
    secrets_path = ".streamlit/secrets.toml"
    if os.path.exists(secrets_path):
        with open(secrets_path, "r") as f:
            secrets_dict = toml.load(f)
            # Monkeypatch st.secrets
            # (Crude but works for this diagnostic)
            # Note: recursive AttributeDict needed for "sheets.rider_db" access style
            class AttrDict(dict):
                def __init__(self, *args, **kwargs):
                    super(AttrDict, self).__init__(*args, **kwargs)
                    self.__dict__ = self
                def __getattr__(self, item): # Handle nested
                     val = self.get(item)
                     if isinstance(val, dict): return AttrDict(val)
                     return val
            
            # Wrap in dictionary that allows attribute access
            st.secrets = AttrDict(secrets_dict)
            print("✅ loaded secrets manually")
            print(f"   Keys found: {list(secrets_dict.keys())}")
            if 'airtable' in secrets_dict:
                 print(f"   Airtable Config Found: {list(secrets_dict['airtable'].keys())}")
            else:
                 print("   ❌ 'airtable' key missing in secrets.toml")
                 
except Exception as e:
    print(f"❌ Secret loading failed: {e}")
    # Initialize empty secrets to prevent crash if file missing, but checks will fail
    st.secrets = {}

# Mocking initialization for script context
try:
    dashboard = FunnelDashboard(data_dir=".")
    # Force reload to test connections
    dashboard.reload_data()
except Exception as e:
    print(f"❌ CRITICAL ERROR initializing Dashboard: {e}")
    exit(1)

# 2. CHECK AIRTABLE
print("\n--- CHECKING AIRTABLE CONNECTION ---")
if hasattr(dashboard, 'airtable') and dashboard.airtable:
    try:
        riders = dashboard.airtable.fetch_all_riders()
        print(f"✅ Success: Connected to Airtable.")
        print(f"   Table: {dashboard.airtable.table_name}")
        print(f"   Record Count: {len(riders)}")
        
        # Check Sample Quality
        if riders:
            sample = riders[0]
            print(f"   Sample Record Email: {sample.get('Email', 'MISSING')}")
            print(f"   Sample Record Name: {sample.get('First Name', 'MISSING')} {sample.get('Last Name', 'MISSING')}")
    except Exception as e:
        print(f"❌ Error: Airtable Connection Failed. {e}")
else:
    print("⚠️ Warning: Airtable not configured (API Key or Base ID missing).")


# 3. CHECK GOOGLE SHEETS
print("\n--- CHECKING GOOGLE SHEETS ---")
# Check configured sheets
loader = dashboard.data_loader
if loader:
    has_db_url = "sheets" in st.secrets and "rider_db" in st.secrets["sheets"]
    print(f"   Rider Database URL Configured: {'Yes' if has_db_url else 'No'}")
    
    # We can check specific loader attributes if exposed, or just rely on 'dashboard.riders' count
    # But user wants "Full Functionality" check.
    # Let's check overrides (pipeline sheets)
    
    # We'll inspect the loaded DataFrames in the loader if accessible
    # Access private attrs for diagnosis
    if hasattr(loader, 'df_rider_db'):
         print(f"✅ Rider Database (Main): Loaded {len(loader.df_rider_db) if loader.df_rider_db is not None else 0} rows")
         
    # Check Pipeline Overrides logic
    # (Checking if Pipeline data was merged)
    print(f"   Final Merged Rider Count: {len(dashboard.riders)}")
    
    # Duplicate Check
    emails = [r.email.lower() for r in dashboard.riders.values()]
    dupes = pd.Series(emails).value_counts()
    actual_dupes = dupes[dupes > 1]
    
    if not actual_dupes.empty:
         print(f"❌ Critical: Found {len(actual_dupes)} Duplicate Emails in Final Dataset!")
         print(actual_dupes.head())
    else:
         print(f"✅ Data Integrity: No Duplicate Emails in final set.")

    # Status Breakdown
    stages = pd.Series([r.current_stage.value for r in dashboard.riders.values()]).value_counts()
    print("\n   Pipeline Distribution:")
    print(stages)

print("\n===========================")
print("🏥 HEALTH CHECK COMPLETE 🏥")
