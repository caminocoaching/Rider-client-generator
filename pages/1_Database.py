import streamlit as st
import pandas as pd
from datetime import datetime
from funnel_manager import FunnelDashboard, FunnelStage
import os
import sys

# Ensure parent directory is in path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ui_components import render_unified_card_content

# Directory setup (replicated from app.py to ensure consistency)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.abspath(os.path.join(BASE_DIR, "../Client Generator "))

if not os.path.exists(DATA_DIR):
    # Fallback to current dir if sibling not found
    DATA_DIR = BASE_DIR

# Page Config
st.set_page_config(page_title="Rider Database", page_icon="🗃️", layout="wide")

# Custom CSS
st.markdown("""
<style>
/* Card Styling */
div[data-testid="stContainer"] {
    
}
div.stButton > button {
    width: 100%;
    border-radius: 6px;
}
.stProgress > div > div > div > div {
    background-color: #E31C25;
}
</style>
""", unsafe_allow_html=True)

# --- HELPER: UNIFIED DIALOG ---
@st.dialog("Rider Details", width="large")
def view_unified_dialog_db(r, dashboard):
    render_unified_card_content(r, dashboard, key_suffix="_db_page")

# Initialize System
@st.cache_resource
def get_dashboard():
    return FunnelDashboard(DATA_DIR)

dashboard = get_dashboard()
# dashboard.reload_data() # Removed for performance: get_dashboard returns cached loaded instance

# --- SIDEBAR: ADD NEW RIDER ---
with st.sidebar:
    st.header("➕ Add New Rider (Direct to Airtable)")
    with st.form("new_rider_form", clear_on_submit=True):
        new_first = st.text_input("First Name")
        new_last = st.text_input("Last Name")
        new_email = st.text_input("Email")
        new_champ = st.text_input("Championship")
        
        submitted = st.form_submit_button("Add Rider")
        if submitted:
            if new_email:
                # Use centralized method which triggers Airtable Sync
                dashboard.add_new_rider(
                    email=new_email,
                    first_name=new_first,
                    last_name=new_last,
                    fb_url="", # Not in form
                    championship=new_champ
                )
                # Ensure stage is set to CONTACT
                dashboard.update_rider_stage(new_email, FunnelStage.CONTACT)
                
                st.success(f"Added {new_first} {new_last}")
                dashboard.reload_data()
                st.rerun()
            else:
                st.error("Email is required.")

# --- MAIN PAGE: DATABASE ---
st.title("🗃️ Rider Database")

riders = list(dashboard.riders.values())
st.markdown(f"**Total Riders:** {len(riders)}")

# 1. Search & Filter
c1, c2 = st.columns([2, 1])
search_query = c1.text_input("🔍 Search by Name, Email, or Championship", placeholder="Type to search...").lower()
filter_stage = c2.selectbox("Filter by Status", ["All"] + [s.value for s in FunnelStage])

# 2. Logic
filtered_riders = []
for r in riders:
    # Text Search
    search_text = f"{r.full_name} {r.email} {r.championship or ''}".lower()
    if search_query and search_query not in search_text:
        continue
        
    # Stage Filter
    if filter_stage != "All" and r.current_stage.value != filter_stage:
        continue
        
    filtered_riders.append(r)

st.divider()

# 3. Grid View
# Pagination (Simple)
items_per_page = 50
total_pages = max(1, (len(filtered_riders) + items_per_page - 1) // items_per_page)
current_page = st.number_input("Page", min_value=1, max_value=total_pages, value=1)
start_idx = (current_page - 1) * items_per_page
end_idx = start_idx + items_per_page

view_riders = filtered_riders[start_idx:end_idx]

st.caption(f"Showing {len(view_riders)} of {len(filtered_riders)} (Total: {len(riders)})")

if not view_riders:
    st.info("No riders found matching your criteria.")
else:
    # Grid Layout
    cols = st.columns(3)
    
    for i, r in enumerate(view_riders):
        col = cols[i % 3]
        with col:
            with st.container(border=True):
                # Header
                if r.championship:
                    st.caption(f"🏁 {r.championship}")
                
                status_icon = "🟢"
                if r.is_disqualified: status_icon = "🚫"
                elif r.current_stage == FunnelStage.CLIENT: status_icon = "🌟"
                
                st.markdown(f"**{status_icon} {r.full_name}**")
                st.caption(r.email)
                st.caption(f"*{r.current_stage.value}*")
                
                # Badges
                badges = []
                if r.flow_profile_result: badges.append("🌊")
                if r.sleep_score: badges.append("😴")
                if r.mindset_result: badges.append("🧠")
                if badges: st.write(" ".join(badges))
                
                # ACTION: Unified Dialog
                if st.button("⚡ Details / Edit", key=f"btn_db_{r.email}", use_container_width=True):
                    view_unified_dialog_db(r, dashboard)
