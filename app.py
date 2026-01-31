
import streamlit as st
import pandas as pd
import plotly.express as px
import os
from datetime import datetime
from funnel_manager import FunnelDashboard, FunnelStage, Rider

# --- CONFIGURATION ---
st.set_page_config(page_title="Rider Pipeline", page_icon="🏍️", layout="wide")

# Directory setup
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.abspath(os.path.join(BASE_DIR, "../Client Generator "))

if not os.path.exists(DATA_DIR):
    # Fallback to current dir if sibling not found
    DATA_DIR = BASE_DIR

# --- DATA LOADING ---
try:
    import gsheets_loader
    from gsheets_loader import load_google_sheet
    HAS_GSHEETS = True
except ImportError:
    HAS_GSHEETS = False

# Import Smart Reply
try:
    from smart_reply import SmartReplyManager
    HAS_SMART_REPLY = True
except ImportError:
    HAS_SMART_REPLY = False

# Helper for Smart Reply / Dialog
# We need to define the dialog function *outside* or ensure it captures scope correctly.
# Ideally defined at module level or helper.




# --- CONSTANTS ---
# --- CONSTANTS ---
from ui_components import REPLY_TEMPLATES, render_unified_card_content




@st.cache_resource(ttl=3600) # Resource cache (1 hour) to prevent slow reloads
def load_dashboard_data(overrides=None):
    dashboard = FunnelDashboard(DATA_DIR, overrides=overrides)
    # dashboard.reload_data() # Already called in __init__
    return dashboard

@st.cache_resource
def load_smart_reply(rider_db=None):
    if HAS_GSHEETS:
        # Check if we should use smart reply?
        pass # It's independent.
    
    if HAS_SMART_REPLY:
        # Pass the rider_db to identify winners
        return SmartReplyManager(DATA_DIR, rider_db=rider_db)
    return None


# ==============================================================================
# VIEW FUNCTIONS
# ==============================================================================


# ==============================================================================
# render_unified_card_content Imported from ui_components



@st.dialog("Rider Details", width="large")
def view_unified_dialog(r, dashboard):
    render_unified_card_content(r, dashboard, key_suffix="_dialog")

# HELPER: Social URL Formatter
def _make_clickable_url(val, platform):
    if not val: return None
    s_val = str(val).strip()
    if s_val.lower().startswith("http"): return s_val
    if platform == "fb": return f"https://www.facebook.com/{s_val}"
    if platform == "ig": return f"https://www.instagram.com/{s_val}"
    return s_val


# HELPER: Rider Card Content (Reusable)
def render_rider_card_content(r, dashboard, smart_reply, stage_config):
    st.markdown(f"### {r.full_name}")
    
    # 1. INFO BLOCK
    c1, c2 = st.columns(2)
    with c1:
        if r.phone: st.caption(f"📞 {r.phone}")
        if r.championship: st.caption(f"🏁 {r.championship}")
        
    with c2:
        d_val = getattr(r, stage_config['date_attr'])
        if d_val: st.caption(f"📅 {d_val.strftime('%d %b')}")
        
    if r.notes:
        st.info(f"📝 {r.notes}")
        
    # Badges
    badges = []
    if r.flow_profile_result: badges.append("🌊 Flow Profile") 
    if r.sleep_score: badges.append("😴 Sleep Score") 
    if r.mindset_result: badges.append("🧠 Mindset") 
    if badges: st.write(" | ".join(badges))
    
    st.divider()
    
    # actions
    # ACTIONS ROW
    c_act1, c_act2, c_act3 = st.columns([1, 1, 1], gap="small")
    
    # 1. EDIT
    with c_act1:
        with st.popover("✏️ Edit", use_container_width=True):
            st.markdown(f"**Edit Details**")
            
            # EDIT FORM
            champ_in = st.text_input("Championship", value=r.championship or "", key=f"dlg_ch_{r.email}")
            phone_in = st.text_input("Phone", value=r.phone or "", key=f"dlg_ph_{r.email}") 
                
            notes_in = st.text_area("Notes", value=r.notes or "", key=f"dlg_no_{r.email}")
            
            # Status
            STATUS_OPTIONS = [FunnelStage.CONTACT, FunnelStage.MESSAGED, FunnelStage.RACE_WEEKEND, FunnelStage.LINK_SENT, FunnelStage.BLUEPRINT_STARTED, FunnelStage.DAY1_COMPLETE, FunnelStage.DAY2_COMPLETE, FunnelStage.STRATEGY_CALL_BOOKED, FunnelStage.CLIENT, FunnelStage.NOT_A_FIT, FunnelStage.FOLLOW_UP]
            
            current_idx = 0
            try: current_idx = STATUS_OPTIONS.index(r.current_stage)
            except: pass
            
            new_status = st.selectbox("Stage", STATUS_OPTIONS, index=current_idx, key=f"dlg_st_{r.email}", format_func=lambda x: x.value)
            
            if st.button("Save Changes", key=f"dlg_sv_{r.email}"):
                    dashboard.data_loader.save_rider_details(r.email, championship=champ_in, notes=notes_in, phone=phone_in)
                    if new_status != r.current_stage: dashboard.update_rider_stage(r.email, new_status)
                    st.rerun()

    # 2. REPLY ASSISTANT
    with c_act2:
        with st.popover("💬 Reply", use_container_width=True):
            display_name = r.full_name
            st.markdown(f"**Reply to {display_name}**")
            # Select Template
            tmpl_key = st.selectbox(
                "Choose Template", 
                options=list(REPLY_TEMPLATES.keys()),
                key=f"dlg_rep_sel_{r.email}"
            )
            
            if tmpl_key:
                # Format Message
                raw_msg = REPLY_TEMPLATES[tmpl_key]
                
                # Name Logic
                first_name = r.first_name
                if not first_name:
                    first_name = r.full_name.split(' ')[0] if r.full_name else "Mate"
                    
                final_msg = raw_msg.replace("{name}", first_name)
                
                st.caption("Preview:")
                st.code(final_msg, language=None)
                
                # Option to copy/edit
                st.text_area("Edit before sending:", value=final_msg, height=200, key=f"dlg_rep_edit_{r.email}")
    
    # 3. SOCIALS
    with c_act3:
        # Social Link
        if r.facebook_url or r.instagram_url:
                # Show primary
                url = r.facebook_url or r.instagram_url
                if st.button("↘️ Social", key=f"dlg_go_{r.email}", use_container_width=True, help=f"Open Social Link ({url})"):
                    pass # Link logic handled by user browser mostly or link component
                    st.markdown(f"[Open Link]({url})")

# DIALOG WRAPPER (Keep for backward compatibility if needed, or replace)
@st.dialog("Rider Details")
def view_rider_dialog(r, dashboard, smart_reply, stage_config):
    render_rider_card_content(r, dashboard, smart_reply, stage_config)



def view_rider_dialog(r, dashboard, smart_reply, stage_config):
    # This function contains the full card UI logic previously in the loop
    # We pass 'r' (rider), 'dashboard' (for actions), 'smart_reply', and 'stage_config' (for context)
    print(f"DEBUG: Opening Dialog for {r.email}")
    
    st.markdown(f"### {r.full_name}")
    
    # 1. INFO BLOCK
    c1, c2 = st.columns(2)
    with c1:
        if r.phone: st.caption(f"📞 {r.phone}")
        if r.championship: st.caption(f"🏁 {r.championship}")
        
    with c2:
        d_val = getattr(r, stage_config['date_attr'])
        if d_val: st.caption(f"📅 {d_val.strftime('%d %b')}")
        
    if r.notes:
        st.info(f"📝 {r.notes}")
        
    # Badges
    badges = []
    if r.flow_profile_result: badges.append("🌊 Flow Profile") 
    if r.sleep_score: badges.append("😴 Sleep Score") 
    if r.mindset_result: badges.append("🧠 Mindset") 
    if badges: st.write(" | ".join(badges))
    
    st.divider()
    
    # actions
    # ACTIONS ROW
    c_act1, c_act2, c_act3 = st.columns([1, 1, 1], gap="small")
    
    # 1. EDIT
    with c_act1:
        with st.popover("✏️ Edit", use_container_width=True):
            st.markdown(f"**Edit Details**")
            
            # EDIT FORM
            champ_in = st.text_input("Championship", value=r.championship or "", key=f"dlg_ch_{r.email}")
            phone_in = st.text_input("Phone", value=r.phone or "", key=f"dlg_ph_{r.email}") 
                
            notes_in = st.text_area("Notes", value=r.notes or "", key=f"dlg_no_{r.email}")
            
            # Status
            # Status
            STATUS_OPTIONS = [FunnelStage.CONTACT, FunnelStage.MESSAGED, FunnelStage.REPLIED, FunnelStage.RACE_WEEKEND, FunnelStage.LINK_SENT, FunnelStage.BLUEPRINT_STARTED, FunnelStage.DAY1_COMPLETE, FunnelStage.DAY2_COMPLETE, FunnelStage.STRATEGY_CALL_BOOKED, FunnelStage.CLIENT, FunnelStage.NOT_A_FIT, FunnelStage.FOLLOW_UP]
            
            current_idx = 0
            try: current_idx = STATUS_OPTIONS.index(r.current_stage)
            except: pass
            
            new_status = st.selectbox("Stage", STATUS_OPTIONS, index=current_idx, key=f"dlg_st_{r.email}", format_func=lambda x: x.value)
            
            if st.button("Save Changes", key=f"dlg_sv_{r.email}"):
                    dashboard.data_loader.save_rider_details(r.email, championship=champ_in, notes=notes_in, phone=phone_in)
                    if new_status != r.current_stage: dashboard.update_rider_stage(r.email, new_status)
                    st.rerun()

    # 2. REPLY ASSISTANT
    with c_act2:
        with st.popover("💬 Reply", use_container_width=True):
            display_name = r.full_name
            st.markdown(f"**Reply to {display_name}**")
            # Select Template
            tmpl_key = st.selectbox(
                "Choose Template", 
                options=list(REPLY_TEMPLATES.keys()),
                key=f"dlg_rep_sel_{r.email}"
            )
            
            if tmpl_key:
                # Format Message
                first_name = r.first_name or display_name.split(' ')[0]
                raw_msg = REPLY_TEMPLATES[tmpl_key]
                final_msg = raw_msg.replace("{name}", first_name)
                
                st.caption("Preview:")
                st.code(final_msg, language=None)
                
                # Option to copy/edit
                st.text_area("Edit before sending:", value=final_msg, height=200, key=f"dlg_rep_edit_{r.email}")

            # --- SMART REPLY SECTION ---
            if smart_reply:
                st.divider()
                with st.expander("🧠 Smart Reply (Beta)", expanded=False):
                    st.caption("Paste the prospect's message to find similar past replies.")
                    in_msg = st.text_area("Prospect's Message", height=100, key=f"dlg_sr_in_{r.email}")
                    
                    if st.button("Find Similar Reply", key=f"dlg_sr_btn_{r.email}"):
                        match = smart_reply.find_reply(in_msg)
                        if match:
                            st.success(f"Match found! ({int(match['confidence']*100)}% match)")
                            st.caption(f"Original from **{match['sender']}**:")
                            st.info(match['trigger_matched'])
                            
                            st.markdown("**Suggested Reply:**")
                            reply_txt = match['reply']
                            st.code(reply_txt, language=None)
                            st.text_area("Edit Recommendation:", value=reply_txt, height=150, key=f"dlg_sr_out_{r.email}")
                        else:
                            st.warning("No similar message found.")

    # 3. SOCIALS
    with c_act3:
        # Social Link
        if r.facebook_url or r.instagram_url:
                # Show primary
                url = r.facebook_url or r.instagram_url
                if st.button("↘️ Social", key=f"dlg_go_{r.email}", use_container_width=True, help=f"Open Social Link ({url})"):
                    import webbrowser
                    webbrowser.open_new_tab(url)


def render_dashboard(dashboard, daily_metrics, riders):

    # 2. TOP SECTION: FUNNEL VISUALIZATION (Metrics)
    # ---------------------------------------------------------
    st.markdown("### 🚀 Outreach & Pipeline Activity")
    
    # Calculate MTD (Month to Date)
    now = datetime.now()
    mtd_metrics = {
        'fb': dashboard.daily_stats.get_mtd_total('fb_messages_sent'),
        'ig': dashboard.daily_stats.get_mtd_total('ig_messages_sent'),
        'links': dashboard.daily_stats.get_mtd_total('links_sent'),
        'registered': 0, 'day1': 0, 'day2': 0, 'calls': 0, 'sales': 0
    }
    
    # Scan riders for MTD automated stats
    for r in riders.values():
        if r.registered_date and r.registered_date.month == now.month and r.registered_date.year == now.year: mtd_metrics['registered'] += 1
        if r.day1_complete_date and r.day1_complete_date.month == now.month and r.day1_complete_date.year == now.year: mtd_metrics['day1'] += 1
        if r.day2_complete_date and r.day2_complete_date.month == now.month and r.day2_complete_date.year == now.year: mtd_metrics['day2'] += 1
        if r.strategy_call_booked_date and r.strategy_call_booked_date.month == now.month and r.strategy_call_booked_date.year == now.year: mtd_metrics['calls'] += 1
        if r.sale_closed_date and r.sale_closed_date.month == now.month and r.sale_closed_date.year == now.year: mtd_metrics['sales'] += 1

    # Custom metric container
    c1, c2, c3, c4, c5, c6, c7, c8 = st.columns(8)
    
    # Display: "Today | MTD"
    c1.metric("FB Sent", f"{daily_metrics['fb_sent']} | {mtd_metrics['fb']}", help="Today | Month To Date")
    c2.metric("IG Sent", f"{daily_metrics['ig_sent']} | {mtd_metrics['ig']}", help="Today | Month To Date")
    c3.metric("Links", f"{daily_metrics['links_sent']} | {mtd_metrics['links']}", help="Today | Month To Date")
    
    # Display: MTD Only for these (as requested)
    c4.metric("Blueprint (MTD)", mtd_metrics['registered'])
    c5.metric("Day 1 (MTD)", mtd_metrics['day1'])
    c6.metric("Day 2 (MTD)", mtd_metrics['day2'])
    c7.metric("Calls (MTD)", mtd_metrics['calls'])
    c8.metric("Sales (MTD)", mtd_metrics['sales'])
    
    st.divider()

    # PIPELINE BOARD
    # ---------------------------------------------------------
    c_head, c_filt = st.columns([2, 1])
    c_head.subheader("📅 Pipeline Opportunities")
    
    # Filter Controls
    filter_mode = c_filt.selectbox(
        "Timeframe", 
        ["Current Month", "Last Month", "All Time", "2025 (Full Year)"], 
        index=2 # Default to All Time to ensure they see their data
    )
    
    # Drag & Drop Toggle
    c_toggle1, c_toggle2 = c_head.columns(2)
    enable_drag = c_toggle1.toggle("Enable Drag & Drop Phase (Beta)", value=False, help="Switch to KanBan mode to drag cards between stages.")
    enable_wide = c_toggle2.checkbox("↔️ Wide View", value=False, help="Enable horizontal scrolling for wider columns.")

    if enable_wide:
        st.markdown("""
            <style>
            /* Force horizontal scroll for column containers */
            div[data-testid="stHorizontalBlock"] {
                flex-wrap: nowrap !important;
                overflow-x: auto !important;
                padding-bottom: 10px;
            }
            /* Force minimum width on columns within the block */
            div[data-testid="column"] {
                min-width: 300px !important;
                flex: 0 0 auto !important;
            }
            /* Adjust main container to not clip */
            .block-container {
                max-width: 100% !important;
            }
            </style>
        """, unsafe_allow_html=True)


    
    # --- LOAD SMART REPLY ---
    smart_reply = load_smart_reply(dashboard.riders)
    
    now = datetime.now()
    
    # Logic

    def is_in_timeframe(r, date_attr):
        if filter_mode == "All Time":
            return True
            
        # SPECIAL CASE: For "New Leads" (Contact Stage), show them even if date is missing
        # This ensures CSV uploads appear immediately
        if date_attr == 'outreach_date' and r.current_stage == FunnelStage.CONTACT:
             d = getattr(r, date_attr)
             if not d: return True # Show undated contacts in current view (or maybe restricted? Let's show them).
        else:
             d = getattr(r, date_attr)
             
        # If no date found:
        # For 'All Time', we generally want to see them? 
        # But if they haven't completed the action (e.g. Day 1 Complete Date missing but Stage is Day 1 Complete), it's weird.
        # However, user says "Day 1 Day 2 are blank" -> implies they are stuck there but dates might be missing.
        if not d: 
            return (filter_mode == "All Time") # Allow missing dates in All Time view

        elif filter_mode == "Current Month":
            return d.month == now.month and d.year == now.year
        elif filter_mode == "Last Month":
            last_month = now.month - 1 if now.month > 1 else 12
            target_year = now.year if now.month > 1 else now.year - 1
            return d.month == last_month and d.year == target_year
        elif filter_mode == "2025 (Full Year)":
            return d.year == 2025
        return False

    # 1. Pipeline Stages Definition
    # 1. Pipeline Stages Definition
    STAGES = [
        # REMOVED: "Leads/Contact" as per user request (it's in Database)
        
        {"label": "Messaged", "val": [FunnelStage.MESSAGED, FunnelStage.RACE_WEEKEND], "date_attr": 'outreach_date'},
        {"label": "Replied", "val": [FunnelStage.REPLIED], "date_attr": 'outreach_date'}, # New Stage
        {"label": "Replied", "val": [FunnelStage.REPLIED], "date_attr": 'outreach_date'}, # New Stage
        {"label": "Link Sent", "val": [FunnelStage.LINK_SENT, FunnelStage.BLUEPRINT_LINK_SENT], "date_attr": 'outreach_date'}, # or create link_sent_date if exists, fallback to outreach
        
        {"label": "Flow Profile", "val": [FunnelStage.FLOW_PROFILE_COMPLETED], "date_attr": 'flow_profile_date'},
        {"label": "Registered", "val": [FunnelStage.BLUEPRINT_STARTED, FunnelStage.REGISTERED], "date_attr": 'registered_date'},
        {"label": "Day 1", "val": [FunnelStage.DAY1_COMPLETE], "date_attr": 'day1_complete_date'},
        {"label": "Day 2", "val": [FunnelStage.DAY2_COMPLETE], "date_attr": 'day2_complete_date'},
        {"label": "Call Booked", "val": [FunnelStage.STRATEGY_CALL_BOOKED], "date_attr": 'strategy_call_booked_date'},
        {"label": "Clients / Won", "val": [FunnelStage.CLIENT, FunnelStage.SALE_CLOSED], "date_attr": 'sale_closed_date'}
    ]

    # HELPER: Format for Sortables (Text Representation)
    def _format_kanban_text(r: Rider):
        # Create a detailed string for the draggable card
        status_icon = "🟢"
        if r.is_disqualified: status_icon = "🚫"
        elif r.days_in_current_stage > 3 and r.current_stage != FunnelStage.CLIENT: status_icon = "🔴"
        
        name = r.full_name or r.email.split('@')[0]
        if name.startswith("no_email_"): name = name.replace("no_email_", "").replace("_", " ").title()
        
        details = []
        if r.championship: details.append(f"🏁 {r.championship}")
        if r.phone: details.append(f"📞 {r.phone}")
        if r.notes: details.append(f"📝 {r.notes[:30]}...")
        
        detail_str = " | ".join(details)
        return f"{status_icon} {name}\n{detail_str}" if detail_str else f"{status_icon} {name}"

    # 2. Render Board
    
    if enable_drag:
        # --- DRAG AND DROP VIEW ---
        import streamlit_sortables
        from streamlit_sortables import sort_items
        
        # Prepare Data for Sortables (List of Dicts format required for multi_containers)
        kanban_data = []
        # Map back to rider objects to handle moves (key matches the display string)
        item_to_rider_map = {} 
        
        for stage in STAGES:
            stage_riders = [
                r for r in riders.values() 
                if r.current_stage in stage['val']
                and is_in_timeframe(r, stage['date_attr'])
            ]
            
            # Create list of formatted strings
            items = []
            for r in stage_riders:
                item_str = _format_kanban_text(r)
                # Ensure uniqueness is handled by the map key, collisions in text are possible but unlikely to break logic if mapped correctly (last one wins in map, but visual dupes might exist).
                # ideally add ID to string if needed, but text needs to be clean.
                items.append(item_str)
                item_to_rider_map[item_str] = r
            
            kanban_data.append({
                'header': stage['label'],
                'items': items
            })
            
        # Render the Sortable Component
        sorted_data = sort_items(kanban_data, multi_containers=True)
        
        # Detect Changes
        changes_detected = False
        
        # sorted_data comes back in the same structure: list of dicts with 'header' and 'items'
        for col_data in sorted_data:
            stage_label = col_data['header']
            current_stage_items = col_data['items']
            
            # Find which stage config this header belongs to
            # (In case order changed, though sort_items usually preserves column order if not reorderable)
            stage_config = next((s for s in STAGES if s['label'] == stage_label), None)
            
            if stage_config:
                target_status = stage_config['val'][0] # Take first valid status for this column
                
                for item_str in current_stage_items:
                    rider = item_to_rider_map.get(item_str)
                    if rider:
                        # Check if this rider is currently in one of the statuses for this column
                        if rider.current_stage not in stage_config['val']:
                             # LOGIC FOR MOVING
                             dashboard.update_rider_stage(rider.email, target_status)
                             st.toast(f"Moved {rider.first_name} to {stage_label}!")
                             changes_detected = True
                             
        if changes_detected:
            st.rerun()
            
    else:
        # --- STATIC VIEW (Enhanced) ---
        # Filter by month if needed
        # (Assuming month options logic here...)
        
        # DEBUG: Print counts
        # st.info(f"DEBUG: Total Riders in Dashboard: {len(dashboard.riders)}")
        
        cols = st.columns(len(STAGES)) # Original was STAGES, instruction uses STAGES_TO_SHOW. Assuming STAGES based on context.
        
        for idx, stage in enumerate(STAGES): # Original was STAGES, instruction uses STAGES_TO_SHOW. Assuming STAGES based on context.
            with cols[idx]:
                # Header
                st.markdown(f"**{stage['label']}**") # Original uses stage['label'], instruction uses stage.value. Sticking to original.
                
                # Filter Riders
                target_vals = [s.value for s in stage['val']]
                stage_riders = [
                    r for r in riders.values() 
                    if (r.current_stage in stage['val'] or r.current_stage.value in target_vals)
                    and is_in_timeframe(r, stage['date_attr'])
                ]
                
                # Get riders for this stage (from instruction, but conflicts with existing filter)
                # stage_riders = [r for r in dashboard.riders.values() if r.current_stage == stage] # This line from instruction would overwrite existing logic. Keeping original.
                
                # Filter by Timeframe (if applicable)
                if filter_mode != 'All Time': # Using existing 'filter_mode' variable
                     # ... filtering logic ...
                     pass
                     
                # Count Badge
                st.caption(f"{len(stage_riders)} Opportunities")
                
                # Limit to prevent UI crash
                DISPLAY_LIMIT = 50
                if len(stage_riders) > DISPLAY_LIMIT:
                    st.warning(f"Showing first {DISPLAY_LIMIT} of {len(stage_riders)}")
                    displayed_riders = stage_riders[:DISPLAY_LIMIT]
                else:
                    displayed_riders = stage_riders
                    
                st.divider()
                
                for r in displayed_riders:
                     # COMPACT VIEW LOGIC
                     
                     # 1. Status Indicator
                     is_stalled = False
                     if r.days_in_current_stage > 3 and r.current_stage != FunnelStage.CLIENT: is_stalled = True
                        
                     status_icon = "🔴" if is_stalled else "🟢"
                     if r.is_disqualified: status_icon = "🚫"
                        
                     # 2. Name
                     display_name = r.full_name.strip()
                     if not display_name:
                         # Fallback Logic
                         if r.email.startswith("no_email_"):
                             display_name = r.email.replace("no_email_", "").replace("_", " ").title()
                         elif '@' in r.email:
                             display_name = r.email.split('@')[0]
                         else:
                             display_name = r.email or "Unknown"

                     # 3. Date
                     date_str = ""
                     d_val = getattr(r, stage['date_attr'])
                     if d_val: 
                         date_str = d_val.strftime('%d %b')
                     elif stage['val'][0] == FunnelStage.CONTACT:
                         # Show "New" or similar if no date for Contact stage
                         pass
                     
                     # LABEL
                     # Construct the button label: Icon Name \n Date
                     label = f"{status_icon} {display_name}"
                     if date_str:
                         label += f"\n📅 {date_str}"
                         
                     # BUTTON TRIGGER (DIALOG)
                     # Using Dialog for full-width rich content
                     # Simple label to avoid button formatting issues
                     btn_label = f"{status_icon} {display_name}"
                     if st.button(btn_label, key=f"btn_card_{r.email}", use_container_width=True):
                         view_unified_dialog(r, dashboard)
                         
 
    # FINANCIALS (Bottom)
    st.divider()
    rev_metrics = dashboard.get_revenue_metrics()
    st.header("💰 Monthly Targets & Forecast")
    
    f_col1, f_col2 = st.columns([3, 1])
    
    with f_col1:
        st.subheader(f"Revenue Progress: {rev_metrics['progress_pct']:.1f}%")
        st.progress(min(rev_metrics['progress_pct'] / 100, 1.0))
        
        fm1, fm2, fm3 = st.columns(3)
        fm1.metric("Actual Revenue", f"£{rev_metrics['actual']:,.0f}")
        fm2.metric("Target", f"£{rev_metrics['target']:,.0f}")
        fm3.metric("Remaining Needed", f"£{max(0, rev_metrics['target'] - rev_metrics['actual']):,.0f}")
    
    with f_col2:
        st.subheader("Calculator")
        needed = max(0, rev_metrics['target'] - rev_metrics['actual'])
        avg_sale = 4000
        sales_needed = needed / avg_sale if avg_sale > 0 else 0
        
        st.write(f"To hit target, you need **{sales_needed:.1f}** more sales.")
        
        # Simple conversion calc
        conv_rate_call_to_sale = 0.25 
        calls_needed = sales_needed / conv_rate_call_to_sale
        
        st.caption(f"Estimated Calls Needed: **{int(calls_needed)}**")

def render_race_outreach(dashboard):
    st.subheader("🏁 Race Result Outreach Tool")
    
    # 1. Race Context
    # Load Saved Circuits
    saved_circuits = dashboard.race_manager.get_all_circuits()
    
    # Callback to sync selection to input
    def on_circuit_select():
        if st.session_state.circuit_select:
             st.session_state.event_name_input = st.session_state.circuit_select

    # Layout: History Dropdown | Text Input | Update Button
    rc_hist, rc_input, rc_btn = st.columns([2, 3, 1])
    
    with rc_hist:
        st.selectbox(
            "📜 History", 
            options=[""] + saved_circuits, 
            key="circuit_select", 
            on_change=on_circuit_select,
            help="Select a previously used circuit to auto-fill."
        )
        
    with rc_input:
        event_name_input = st.text_input(
            "Circuit / Event Name", 
            placeholder="e.g. Donington Park", 
            help="Type name and press ENTER to update messages.", 
            key="event_name_input"
        )
        
    with rc_btn:
        st.write("") # Spacer
        st.write("") 
        if st.button("🔄 Update", help="Click to refresh messages and SAVE this circuit name."):
            # Save the new name if valid
            if event_name_input:
                dashboard.race_manager.save_circuit(event_name_input)
            st.rerun()

    if event_name_input:
        event_name = event_name_input
    else:
        event_name = "the circuit" 
        st.caption("⚠️ Type a circuit name above and press **Enter** (or Update) to customize messages.")
    
    # 2. Input Data
    input_method = st.radio("Input Method", ["Paste Text", "Upload CSV (Timing Sheet)"], key="race_input_method")
    
    raw_results_list = []
    
    if input_method == "Upload CSV (Timing Sheet)":
        uploaded_file = st.file_uploader("Upload Timing Sheet CSV", type=['csv'], key="race_file_uploader")
        if uploaded_file:
            try:
                # Ensure we read from start of file
                uploaded_file.seek(0)
                df = pd.read_csv(uploaded_file)
                
                # Try to find relevant columns
                name_col = None
                candidates = ['competitor', 'name', 'rider', 'driver', 'first name', 'last name', 'racer']
                
                # Smart search
                for col in df.columns:
                    if str(col).lower().strip() in candidates:
                        name_col = col
                        break
                    # Partial match
                    if "name" in str(col).lower() or "rider" in str(col).lower():
                        name_col = col 
                
                # UI Fallback
                st.caption(f"Detected {len(df)} rows.")
                col_options = list(df.columns)
                
                # Set default index if we found a candidate
                idx = col_options.index(name_col) if name_col in col_options else 0
                
                selected_col = st.selectbox("Select Name Column", col_options, index=idx, help="Which column contains the names?")
                
                if selected_col:
                    names = df[selected_col].dropna().astype(str).tolist()
                    raw_results_list = names
                    
                    if len(names) > 0:
                         st.success(f"Ready to analyze {len(names)} riders!")
                
            except Exception as e:
                st.error(f"Error reading CSV: {e}")
                
    else: # Paste Text
        text_input = st.text_area("Rider List (Name per line)", height=150)
        if text_input:
            raw_results_list = text_input.split('\n')
    
    if st.button("🔍 Analyze & Match Riders"):
        if not raw_results_list:
            st.error("Please provide rider data.")
        else:
            # Simple cleanup
            clean_names = [n.strip().split(',')[0] for n in raw_results_list if len(n) > 3]
            
            with st.spinner(f"Analyzing {len(clean_names)} riders..."):
                results = dashboard.process_race_results(clean_names, event_name=event_name)
                st.session_state.matched_results = results
                
                # PERSISTENCE: Save to disk for refresh survival
                import pickle
                try:
                    with open(os.path.join(DATA_DIR, "last_race_analysis.pkl"), "wb") as f:
                        pickle.dump(results, f)
                except Exception as e:
                    print(f"Failed to cache analysis: {e}")

    # 3. Processed Results
    # AUTO-LOAD Persistence if session empty
    if 'matched_results' not in st.session_state or not st.session_state.matched_results:
        import pickle
        cache_path = os.path.join(DATA_DIR, "last_race_analysis.pkl")
        if os.path.exists(cache_path):
            try:
                with open(cache_path, "rb") as f:
                    st.session_state.matched_results = pickle.load(f)
            except Exception:
                pass # Corrupt or old file
                
    if 'matched_results' in st.session_state and st.session_state.matched_results:
        st.divider()
        results = st.session_state.matched_results
        
        # BULK IMPORT ACTION
        new_prospects_count = sum(1 for r in results if r['match_status'] == 'new_prospect')
        if new_prospects_count > 0:
             c_bulk1, c_bulk2 = st.columns([2, 1])
             with c_bulk1:
                 st.metric("Total Riders", len(results))
             with c_bulk2:
                 if st.button(f"⚡ Bulk Import {new_prospects_count} New Riders", type="primary", help="Immediately add all new names to the Pipeline as Leads"):
                      added = 0
                      # Use a progress bar for satisfaction
                      progress_bar = st.progress(0)
                      
                      for idx, r in enumerate(results):
                           if r['match_status'] == 'new_prospect':
                               # Generate minimal details
                               name = r['original_name']
                               clean_name = "".join([c for c in name if c.isalnum() or c == ' ']).strip()
                               slug = clean_name.lower().replace(" ", "_")
                               email = f"no_email_{slug}"
                               
                               # Split name
                               parts = clean_name.split(' ')
                               f_name = parts[0].title()
                               l_name = " ".join(parts[1:]).title() if len(parts) > 1 else ""
                               
                               # Add to Dashboard/Memory
                               if dashboard.add_new_rider(email, f_name, l_name, "", "", ""):
                                   dashboard.update_rider_stage(email, FunnelStage.CONTACT)
                                   # Important: Ensure outreach_date is set so they appear in filtered views
                                   if email in dashboard.riders:
                                        dashboard.riders[email].outreach_date = datetime.now()
                                        
                                   # Update localized match status so UI reflects it immediately
                                   r['match_status'] = 'match_found'
                                   r['match'] = dashboard.riders[email]
                                   added += 1
                                   
                           progress_bar.progress((idx + 1) / len(results))
                           
                      st.success(f"Successfully imported {added} riders! They are now in the 'Leads / Contact' stage.")
                      st.rerun()
                      
        else:
             st.metric("Total Riders", len(results))
        
        # Filter Logic
        show_messaged = st.checkbox("Show Sent/Processed Riders", value=False)
        
        filtered = []
        for r in results:
            if show_messaged:
                filtered.append(r)
            else:
                # Exclude if stage is MESSAGED or further (value 2+)
                # Need to check rider object state
                # If match found, check its stage
                if r['match_status'] == 'match_found' and r.get('match'):
                    stage = r['match'].current_stage
                    # If stage is Contact, we show it (it's pending outreach)
                    # If stage is Messaged+, we hide it
                    if stage != FunnelStage.CONTACT:
                         continue
                filtered.append(r)

        st.write(f"Showing {len(filtered)} riders")
        
        # Initialize session state for tracking expanded cards
        if "just_added_names" not in st.session_state:
            st.session_state.just_added_names = set()

        # Paginate to show top 20 by default to avoid lag
        for i, r in enumerate(filtered[:20]): 
            # Color Code / Icon logic
            if r['match_status'] == 'match_found':
                 icon = "✅"
                 label = "MATCHED (Ready)"
            else:
                 icon = "🆕" 
                 label = "NEW PROSPECT"
            
            # Keep expanded if just added
            is_expanded = r['original_name'] in st.session_state.just_added_names
                 
            with st.expander(f"{icon} {r['original_name']}  [{label}]", expanded=is_expanded):
                
                # BRANCH: MATCHED RIDER -> Unified Card
                if r['match_status'] == 'match_found' and r.get('match'):
                    st.success(f"✅ Matched: {r['match'].full_name}")
                    
                    # Clear from "just added" loop triggers (optional cleanup, but maybe keep until closed?)
                    # If we clear it now, it might close on next unrelated interaction. 
                    # Let's keep it in set for this session or until manual close (Streamlit handles manual).
                    
                    render_unified_card_content(r['match'], dashboard, key_suffix=f"race_{i}", default_event_name=event_name)
                    
                else:
                    # BRANCH: NEW PROSPECT -> Deep Search & Add Form
                    rc1, rc2 = st.columns(2)
                    
                    # LEFT: Draft Message (Standard)
                    with rc1:
                        st.write("#### 📝 Outreach Draft")
                        
                    # LEFT: Draft Message (Standard)
                    with rc1:
                        st.write("#### 📝 Outreach Draft")
                        
                        # --- TEMPLATE DEFINITIONS (Restored & Merged) ---
                        f_name = r['original_name'].split(' ')[0]
                        
                        # 1. Custom/Restored Contextual Templates
                        custom_templates = {
                            "1. Cold Outreach (Weekend)": f"Hey {f_name}, I see you were out at {event_name}. How was the weekend for you?",
                            "1. Cold Outreach (Series)": f"Hi {f_name}, I see you were out at {event_name}. How's the series going for you so far?",
                            "1. Cold Outreach (Season)": f"Hey {f_name}, I see you were out at {event_name}. How's the season treating you?",
                            "Blank Hook": f"Hey {f_name}, "
                        }
                        
                        # 2. Add Standard Deck from ui_components
                        # (This is the "message deck" from earlier versions like 'Offer Free Training')
                        from ui_components import REPLY_TEMPLATES
                        
                        # Merge dicts
                        templates = custom_templates.copy()
                        for k, v_raw in REPLY_TEMPLATES.items():
                             # Format the standard templates with name
                             # Some might not have {name}, but safe to try format or replace
                             try:
                                 v_formatted = v_raw.replace("{name}", f_name)
                                 templates[k] = v_formatted
                             except:
                                 templates[k] = v_raw

                        template_options = list(templates.keys())
                        # Sort to keep Cold Outreach at top if possible, or just standard sort
                        # standard sort might put "1." at top which is good.
                        
                        selected_tpl_name = st.selectbox("Select Template", template_options, key=f"tpl_{i}_{r['original_name']}")
                        
                        msg_val = templates[selected_tpl_name]

                        # Key needs to include event_name to force refresh
                        evt_key = event_name.replace(" ", "_").lower()
                        st.text_area("Message", value=msg_val, height=250, key=f"msg_{i}_{r['original_name']}_{evt_key}")
                        
                        st.caption("Copy for DM:")
                        st.code(msg_val, language=None)
                        
                        # MESSAGE SENT ACTION (Disabled for New Prospect until added)
                        st.write("---")
                        if st.button("🚀 Confirm Message Sent", key=f"sent_{i}_{r['original_name']}", type="primary"):
                             st.error("Please 'Add Contact' first before marking sent.")

                    with rc2:
                        st.write("#### 👤 Contact Actions")
                        
                        if r['match_status'] == 'new_prospect':
                            # DEEP SEARCH FUNCTIONALITY
                            st.info("Rider not in database.")

                            # Always show Deep Search Toolkit (No buttons, no expander)
                            st.markdown("---")
                            st.markdown("#### 🕵️ Deep Search Toolkit")
                            st.caption("Copy Name for manual search:")
                            st.code(r['original_name'], language=None)
                            
                            deep_links = dashboard.race_manager.social_finder.generate_deep_search_links(r['original_name'], event_name)
                            
                            c_d1, c_d2 = st.columns(2)
                            with c_d1:
                                st.markdown(f"**Facebook**")
                                fb_link = deep_links.get('👥 Facebook Direct', deep_links.get('👥 Facebook Profile', '#'))
                                st.markdown(f"[👥 Open Search (Auto)]({fb_link})")
                                
                            with c_d2:
                                st.markdown(f"**Instagram**")
                                ig_link = deep_links.get('📸 Instagram Direct', deep_links.get('📸 Instagram Profile', '#'))
                                st.markdown(f"[📷 Open Instagram]({ig_link})")
                                
                                backup_link = deep_links.get('(Backup) IG Google', '#')
                                st.caption(f"[Alternative: Google Search]({backup_link})")

                            st.caption("Validation Tools")
                            c_v1, c_v2 = st.columns(2)
                            with c_v1:
                                if '📋 Racing Org Check' in deep_links:
                                     st.markdown(f"[📋 Org Check]({deep_links['📋 Racing Org Check']})")
                            with c_v2:
                                if '⏱️ Lap Times' in deep_links:
                                     st.markdown(f"[⏱️ Lap Times]({deep_links['⏱️ Lap Times']})")
    
                            # Always Show Form
                            st.markdown("---")
                            with st.form(key=f"add_contact_{i}"):
                                st.caption(f"Add **{r['original_name']}** to Database")
                                # Split name guess
                                parts = r['original_name'].split(' ')
                                f_geo = parts[0].title()
                                l_geo = parts[1].title() if len(parts) > 1 else ""
                                    
                                in_first = st.text_input("First Name", value=f_geo, key=f"first_{i}_{r['original_name']}")
                                in_last = st.text_input("Last Name", value=l_geo, key=f"last_{i}_{r['original_name']}")
                                
                                # UX FIX: Email Optional (Hidden ID generation)
                                in_email = st.text_input("Email (Optional)", key=f"email_{i}_{r['original_name']}", placeholder="e.g. rider@example.com")
                                
                                in_champ = st.text_input("Championship", key=f"champ_{i}_{r['original_name']}")
                                
                                # Pre-fill FB/IG (Manual now, so empty defaults)
                                in_fb = st.text_input("Facebook URL", key=f"fb_{i}_{r['original_name']}")
                                in_ig = st.text_input("Instagram URL", key=f"ig_{i}_{r['original_name']}")
                                
                                if st.form_submit_button("💾 Save to DB"):
                                    # 1. Handle ID Generation
                                    final_email = in_email.strip()
                                    if not final_email:
                                        # Generate ID from name
                                        slug = f"{in_first} {in_last}".lower().strip().replace(' ', '_')
                                        slug = "".join([c for c in slug if c.isalnum() or c == '_'])
                                        final_email = f"no_email_{slug}"
                                    
                                    # 2. Add to DB
                                    success = dashboard.add_new_rider(final_email, in_first, in_last, in_fb, ig_url=in_ig, championship=in_champ)
                                    
                                    if success:
                                        # 3. Update Stage to CONTACT
                                        dashboard.update_rider_stage(final_email, FunnelStage.CONTACT)
                                        
                                        # 3. Update Session State
                                        if final_email in dashboard.riders:
                                            new_rider = dashboard.riders[final_email]
                                            r['match_status'] = 'match_found'
                                            r['match'] = new_rider
                                            
                                            # PERSISTENCE: Save updated results to disk immediately
                                            # This ensures if user refreshes, they stay "Matched"
                                            import pickle
                                            try:
                                                with open(os.path.join(DATA_DIR, "last_race_analysis.pkl"), "wb") as f:
                                                    pickle.dump(st.session_state.matched_results, f)
                                            except Exception:
                                                pass
                                            
                                        # Track this name to keep expander open
                                        st.session_state.just_added_names.add(r['original_name'])
                                            
                                        st.toast(f"Added {in_first}! Now click 'Confirm Message Sent' when ready.")
                                        st.rerun()
                                    else:
                                        st.error("Failed to save.")
# ==============================================================================
# DATABASE VIEW
# ==============================================================================
def render_database_view(dashboard):
    st.subheader("🗃️ Full Rider Database")
    
    riders = dashboard.riders
    st.caption(f"Total Riders: {len(riders)}")
    
    # helper to clean data for display
    data = []
    # Convert riders dict to list
    rider_list = list(riders.values())
    
    for r in rider_list:
        # Robust enum handling
        stage_val = r.current_stage.value if hasattr(r.current_stage, "value") else str(r.current_stage)
        channel_val = r.outreach_channel.value if hasattr(r.outreach_channel, "value") else str(r.outreach_channel)
        
        data.append({
            "First Name": r.first_name,
            "Last Name": r.last_name,
            "Email": r.email,
            "Stage": stage_val,
            "Channel": channel_val,
            "Date Joined": r.outreach_date.strftime('%Y-%m-%d') if r.outreach_date else None,
            "Phone": r.phone,
            "Championship": r.championship,
            "Notes": r.notes
        })
        
    df = pd.DataFrame(data)
    
    if not df.empty:
        # SEARCH
        col1, col2 = st.columns([2, 1])
        with col1:
            search_term = st.text_input("🔍 Search Database", placeholder="Search by name, email, or notes...")
        
        if search_term:
            # Case insensitive search across all columns
            mask = df.apply(lambda x: x.astype(str).str.contains(search_term, case=False).any(), axis=1)
            df = df[mask]
            st.caption(f"Found {len(df)} matches")
            
        # DISPLAY
        # Interactive Dataframe
        event = st.dataframe(
            df, 
            use_container_width=True,
            column_config={
                "Email": st.column_config.TextColumn("Email"),
                "Stage": st.column_config.Column("Stage", help="Current Funnel Stage"),
                "Notes": st.column_config.TextColumn("Notes", width="large")
            },
            hide_index=True,
            height=600,
            on_select="rerun",
            selection_mode="single-row"
        )
        
        # Handle Selection
        if len(event.selection["rows"]):
            selected_idx = event.selection["rows"][0]
            try:
                # Get the row from the (potentially filtered) dataframe
                selected_row = df.iloc[selected_idx]
                email_selected = selected_row["Email"]
                
                # Open Dialog
                if email_selected in dashboard.riders:
                    r_selected = dashboard.riders[email_selected]
                    view_unified_dialog(r_selected, dashboard)
            except Exception as e:
                st.warning(f"Could not open rider: {e}")
        
        # DOWNLOAD
        @st.cache_data
        def convert_df(df):
            return df.to_csv(index=False).encode('utf-8')

        csv_data = convert_df(df)

        st.download_button(
            "📥 Download CSV",
            csv_data,
            "rider_database_export.csv",
            "text/csv",
            key='download-csv'
        )
    else:
        st.info("No riders found in database.")

# ==============================================================================
# ADMIN VIEW
# ==============================================================================
def render_admin(dashboard, overrides, sheet_errors, riders):
    st.subheader("📥 Daily Inputs & Manual Uploads")

    # FILE UPLOADS
    with st.expander("📂 File Uploads (Manual)", expanded=True):
        st.info("Upload new CSVs here for non-synced data.")
        
        # Helper to handle upload
        def handle_upload(uploaded_file, target_filename, label):
            if uploaded_file:
                # Unique Key for Session State
                file_key = f"proc_{target_filename}"
                file_details = f"{uploaded_file.name}_{uploaded_file.size}"
                
                # Check if already processed
                if st.session_state.get(file_key) != file_details:
                    # Save File
                    save_path = os.path.join(DATA_DIR, target_filename)
                    with open(save_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    
                    # Update & Notify
                    dashboard.reload_data()
                    st.session_state[file_key] = file_details
                    
                    # Mark as Forced Local (survive reruns)
                    st.session_state[f"force_local_{target_filename}"] = True
                    
                    st.toast(f"✅ {label} Uploaded successfully!", icon="📂")
                    st.success(f"**{label}** is now live and being used for today's data! (Local Override Active)")
                    
                    return True
            return False

        # Status Helper
        def get_file_status(filename):
            path = os.path.join(DATA_DIR, filename)
            if os.path.exists(path):
                return "✅ Active"
            return "⚪ Missing"

        # Pipeline Activity
        uc1, uc2, uc3, uc4 = st.columns(4)
        
        with uc1:
            st.caption(f"Blueprint Regs ({get_file_status('Podium Contenders Blueprint Registered.csv')})")
            up_bp = st.file_uploader("Blueprint", type=['csv'], label_visibility="collapsed")
            if handle_upload(up_bp, "Podium Contenders Blueprint Registered.csv", "Blueprint Regs"):
                st.rerun()

        with uc2:
            st.caption(f"Day 1 ({get_file_status('7 Biggest Mistakes Assessment.csv')})")
            up_d1 = st.file_uploader("Day 1", type=['csv'], label_visibility="collapsed")
            if handle_upload(up_d1, "7 Biggest Mistakes Assessment.csv", "Day 1 Assessment"):
                st.rerun()
            
        with uc3:
            st.caption(f"Race Reviews ({get_file_status('export (15).csv')})")
            up_race = st.file_uploader("Race Reviews", type=['csv'], label_visibility="collapsed")
            if handle_upload(up_race, "export (15).csv", "Race Reviews"):
                st.rerun()

        with uc4:
            st.caption(f"Season Reviews ({get_file_status('export (16).csv')})")
            up_season = st.file_uploader("Season Reviews", type=['csv'], label_visibility="collapsed")
            if handle_upload(up_season, "export (16).csv", "Season Reviews"):
                st.rerun()
            
        st.caption("Data updates immediately upon upload.")

    # MANUAL STATS
    with st.expander("📝 Daily Activity Stats", expanded=True):
        with st.form("manual_stats_form"):
            date_input = st.date_input("Date", value=datetime.now())
            
            # Load existing for this date?
            existing_stats = dashboard.daily_stats.get_stats_for_date(date_input)
            
            c_i1, c_i2 = st.columns(2)
            fb_in = c_i1.number_input("FB Msgs", value=existing_stats.fb_messages_sent, min_value=0)
            ig_in = c_i2.number_input("IG Msgs", value=existing_stats.ig_messages_sent, min_value=0)
            links_in = st.number_input("Links Sent", value=existing_stats.links_sent, min_value=0)
            
            if st.form_submit_button("Save Daily Stats"):
                dashboard.daily_stats.save_stats(date_input, fb_in, ig_in, links_in)
                st.toast("✅ Stats Saved!")
                st.cache_resource.clear()
                st.rerun()

    # PLATFORM INTEGRATIONS (Xperiencify / Airtable)
    with st.expander("🔌 Platform Integrations & Sync", expanded=True):
        c_plat1, c_plat2 = st.columns(2)
        
        with c_plat1:
            st.markdown("#### Xperiencify Export")
            st.caption("Upload 'Xperiencify.csv' to sync students & progress.")
            xp_file = st.file_uploader("Upload CSV", type=['csv'], key="up_xp")
            if xp_file:
                 if handle_upload(xp_file, "Xperiencify.csv", "Xperiencify Data"):
                     st.rerun()

        with c_plat2:
            st.markdown("#### Airtable Sync")
            st.caption("Push all local data updates to Airtable Master Record.")
            if st.button("🔄 Sync Database to Airtable", use_container_width=True):
                 with st.spinner("Syncing Database to Airtable..."):
                     count = dashboard.data_loader.sync_database_to_airtable()
                     if count > 0:
                         st.success(f"✅ Successfully synced {count} records to Airtable!")
                         st.cache_resource.clear()
                     else:
                         st.warning("No records synced (Check Airtable connection).")

    # CRM IMPORT
    with st.expander("📥 Import External Contacts (CRM / CSV)", expanded=False):
        st.info("Import contacts from other systems. Requires 'Email' column.")
        crm_file = st.file_uploader("Upload CSV", type=['csv'], key="crm_upload")
        if crm_file:
            if st.button("Start Import"):
                with st.spinner("Importing..."):
                    stats = dashboard.import_crm_csv(crm_file)
                    if stats['errors'] > 0 and stats['added'] == 0:
                        st.error("Import failed. Check CSV headers.")
                    else:
                        st.success(f"Import Complete! Added: {stats['added']}, Skipped: {stats['skipped']}, Errors: {stats['errors']}")
                        if stats['added'] > 0:
                            st.balloons()
                            st.cache_resource.clear()
                            # Wait a bit then rerun? No, let them see stats.

    # SYNC APP DATA TO CSV
    with st.expander("💾 Sync Contacts from App to CSV", expanded=True):
        st.write("### 📤 Save Imported Contacts")
        st.info("Many contacts (Facebook, Race Results) exist in memory but are not yet in your `Rider Database.csv` file. Use this to save them.")
        
        c_sync1, c_sync2 = st.columns([3, 1])
        with c_sync1:
            st.write("Click below to find all riders in the app who are missing from your Rider Database CSV and append them.")
        
        with c_sync2:
             if st.button("💾 Sync to Database", type="primary"):
                 with st.spinner("Syncing..."):
                     added_count = dashboard.data_loader.sync_missing_riders_to_db()
                     if added_count > 0:
                         st.success(f"✅ Success! Appended {added_count} new riders to Rider Database.csv")
                         st.balloons()
                         st.cache_resource.clear()
                     else:
                         st.info("No new riders found to sync. Database is up to date.")

    # DB MAINTENANCE
    with st.expander("🧹 Database Maintenance", expanded=True):
        st.write("### 🔍 Database Health Report")
        if hasattr(dashboard.data_loader, 'load_report'):
            rep = dashboard.data_loader.load_report
            st.metric("Total Rows Processed", rep.get('total', 0))
            c1, c2 = st.columns(2)
            c1.metric("✅ Successfully Loaded", rep.get('loaded', 0))
            c2.metric("❌ Skipped Rows", rep.get('skipped', 0))
            
            if rep.get('skipped', 0) > 0:
                st.warning("Skipped Rows Breakdown:")
                st.json(rep.get('reasons', {}))
                st.info("💡 Hint: Skipped rows usually mean missing 'Email', 'Name', or 'no_email_ID'.")
        
        st.divider()

        st.write("### 🗄️ Master Database Replacement")
        st.info("Upload a merged CSV to replace your entire database.")
        
        # Check GSheet Status
        has_gsheet = "Rider Database.csv" in overrides
        if has_gsheet:
            st.warning("⚠️ **Google Sheets Sync ID ACTIVE**")
            st.markdown("""
            You are connected to a Google Sheet. To replace the database, you must **Overwrite** the sheet.
            
            **Instructions:**
            1. Upload your new Merged CSV.
            2. Click the red **'🔥 Overwrite Google Sheet'** button.
            """)
        
        up_db = st.file_uploader("Upload New Database CSV", type=['csv'], key="db_replace")
        
        if up_db:
            # Option 1: Local Replace (Standard)
            if st.button("Update Local File Only"):
                if handle_upload(up_db, "Rider Database.csv", "Master Database"):
                     st.balloons()
            
            # Option 2: Cloud Overwrite (Dangerous)
            if has_gsheet:
                if st.button("🔥 Overwrite Google Sheet (Dangerous)", type="primary"):
                    with st.spinner("⚠️ Overwriting Google Sheet... Do not close tab."):
                        try:
                            # 1. Read CSV to List
                            import io
                            import csv
                            stringio = io.StringIO(up_db.getvalue().decode("utf-8"))
                            csv_reader = csv.reader(stringio)
                            data = list(csv_reader)
                            
                            if not data:
                                st.error("CSV is empty.")
                            else:
                                # 2. Get URL
                                sheet_url = st.secrets["sheets"]["rider_db"]
                                
                                # 3. Clear Sheet
                                success, msg = gsheets_loader.clear_sheet(sheet_url)
                                if success:
                                    # 4. Bulk Update
                                    if gsheets_loader.bulk_update(sheet_url, data):
                                        st.success(f"✅ Google Sheet Overwritten! ({len(data)} rows uploaded)")
                                        st.balloons()
                                        st.cache_resource.clear()
                                        # Update local too for consistency
                                        handle_upload(up_db, "Rider Database.csv", "Master Database")
                                    else:
                                        st.error("Failed to write data to Google Sheet.")
                                else:
                                    st.error(f"Failed to clear Google Sheet: {msg}")
                                    
                        except Exception as e:
                            st.error(f"Overwrite Error: {e}")
        st.write("### Deduplication")
        st.write("Scan the database for duplicate emails and merge them into single records.")
        
        if st.button("♻️ Scan & Fix Duplicates"):
             with st.spinner("Cleaning database..."):
                 removed = dashboard.cleanup_duplicates()
                 if removed > 0:
                     st.success(f"Cleaned {removed} duplicate rows!")
                     st.cache_resource.clear()
                     # st.rerun()
                 else:
                     st.info("Database is clean! No duplicates found.")

    st.divider()

    # Footer / Debug
    with st.expander("⚙️ Debug / System Info"):
        st.write(f"Data Source: {'Google Sheets' if HAS_GSHEETS else 'Local CSV'}")
        
        # Debug Overrides
        st.write("### 📊 Overrides Status")
        if overrides:
            for k, v in overrides.items():
                rows = len(v) if hasattr(v, '__len__') else "N/A"
                st.write(f"- **{k}**: {rows} rows")
                
                # Deep Inspect Rider DB
                if "Rider Database" in k:
                    st.write("#### Rider DB Columns:")
                    if hasattr(v, 'columns'):
                        st.code(list(v.columns))
                        st.write("First Row Sample:", v.iloc[0].to_dict() if len(v) > 0 else "Empty")
        else:
            st.warning("No overrides loaded.")

        if 'sheet_errors' in globals() and sheet_errors:
            st.error(f"Sheet Errors: {sheet_errors}")
        st.write(f"Manual Stats Loaded: {len(dashboard.daily_stats.stats)} days")
        st.write(f"Total Riders in DB: {len(riders)}")

# ==============================================================================
# MAIN LAYOUT (NAVIGATION)
# ==============================================================================

st.title("🏍️ Rider Pipeline Dashboard")

# --- DEBUG: HEALTH CHECK ---
if 'dashboard' in locals() or 'dashboard' in globals():
    # Defensive check if dashboard loaded
    if hasattr(dashboard.data_loader, 'load_report'):
        rep = dashboard.data_loader.load_report
        skipped = rep.get('skipped', 0)
        if skipped > 10:
            st.error(f"⚠️ **DATA LOADING ISSUE DETECTED** ⚠️\n\n{skipped} rows were SKIPPED. Only {rep.get('loaded', 0)} loaded.\nPlease check the 'Skipped Rows Breakdown' below.")
            with st.expander("🔍 VIEW DEBUG INFO (What went wrong?)", expanded=True):
                 st.write("**Skip Reasons:**")
                 st.json(rep.get('reasons', {}))
                 
                 st.write("**Troubleshooting:**")
                 st.markdown("- **Missing Identity**: App couldn't find 'Email' OR 'Full Name' in your columns.")
                 
                 # Show Headers of loaded sheet to debug
                 if dashboard.data_loader.overrides and "Rider Database.csv" in dashboard.data_loader.overrides:
                     df_debug = dashboard.data_loader.overrides["Rider Database.csv"]
                     st.write(f"**Headers Found in Sheet:** `{list(df_debug.columns)}`")
                     st.caption("Ensure your columns match: 'Full Name', 'Email Address', etc.")
            st.divider()

# Force Reload Button (Temporary for debugging/updates)
if 'dashboard' in locals() or 'dashboard' in globals():
    # Cloud Status Indicator
    if hasattr(dashboard, 'airtable') and dashboard.airtable:
         st.sidebar.success("☁️ Cloud Storage: Connected")
    else:
         st.sidebar.warning("💾 Local Storage (CSV)")

if st.sidebar.button("🔄 Force Reload / Clear Cache"):
    st.cache_resource.clear()
    st.rerun()

# 1. AUTO-SYNC GOOGLE SHEETS
# --- CACHED DATA LOADER (Module Level) ---
@st.cache_data(ttl=300) # Cache for 5 minutes
def load_all_sheets_data_cached():
     import concurrent.futures
     
     SHEET_CONFIG = {
         "rider_db": "Rider Database.csv",
         "strategy_apps": "Strategy Call Application.csv",
         "blueprint_regs": "Podium Contenders Blueprint Registered.csv",
         "seven_mistakes": "7 Biggest Mistakes Assessment.csv",
         "day2_assessment": "Day 2 Self Assessment.csv",
         "flow_profile": "Flow Profile.csv",
         "sleep_test": "Sleep Test.csv",
         "mindset_quiz": "Mindset Quiz.csv",
         "race_weekend": "export (15).csv",
         "season_review": "export (16).csv",
         "xperiencify": "Xperiencify.csv"
     }
     
     sheet_secrets = st.secrets.get("sheets", {})
     loaded_data = {}
     missing_keys = []
     load_errors = []
     
     # 1. Identify valid tasks
     tasks = {}
     for secret_key, internal_file in SHEET_CONFIG.items():
         url = sheet_secrets.get(secret_key, "")
         if url:
             tasks[secret_key] = (url, internal_file)
         else:
             missing_keys.append(secret_key)
     
     # 2. Execute in Parallel
     with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
         future_to_key = {
             executor.submit(load_google_sheet, url): (key, internal_file)
             for key, (url, internal_file) in tasks.items()
         }
         
         for future in concurrent.futures.as_completed(future_to_key):
             key, internal_file = future_to_key[future]
             try:
                 df = future.result()
                 if df is not None and not df.empty:
                     loaded_data[internal_file] = df
             except Exception as exc:
                 load_errors.append(f"{key}: {exc}")
                 print(f"Error loading {key}: {exc}")
                 
     return loaded_data, missing_keys, load_errors

if HAS_GSHEETS:
    try:
        # Check for secrets
        if "connections" in st.secrets and "gsheets" in st.secrets["connections"]:
            
            # CACHED CALL
            try:
                 overrides, missing_config, sheet_errors = load_all_sheets_data_cached()
                 
                 # UI STATUS
                 if st.sidebar.checkbox("🔌 Connection Status", value=False): # Collapsed via checkbox to save rendering
                      st.sidebar.write("### GSheets Sync (Cached 5m)")
                      
                      if missing_config:
                           st.sidebar.warning(f"Note: No GSheet synced for: {', '.join(missing_config)}")
                      
                      if sheet_errors:
                          st.sidebar.error(f"⚠️ Connection Errors: {sheet_errors}")

                      for internal_file, df in overrides.items():
                           st.sidebar.caption(f"✅ {internal_file}: {len(df)} rows")
                           
                 if sheet_errors:
                     st.toast(f"⚠️ Some Google Sheets failed to load. Using local data.", icon="⚠️")

            except Exception as e:
                st.error(f"GSheets Cache Error: {e}")
                overrides = {}
                sheet_errors = [str(e)]
        else:
            overrides = {}
            sheet_errors = ["No 'gsheets' connection in secrets.toml"]
    except Exception as e:
        overrides = {}
        sheet_errors = [str(e)]
else:
    overrides = {}
    sheet_errors = ["Missing streamlit_gsheets module"]

# Load Logic
try:
    # APPLY LOCAL OVERRIDES (If User Manually Uploaded)
    cleaned_overrides = overrides.copy()
    forced_files = []
    
    for filename in list(cleaned_overrides.keys()):
        if st.session_state.get(f"force_local_{filename}"):
            del cleaned_overrides[filename]
            forced_files.append(filename)
            
    if forced_files:
        st.toast(f"Using local files for: {len(forced_files)} inputs", icon="📂")

    dashboard = load_dashboard_data(overrides=cleaned_overrides)
    riders = dashboard.riders
    daily_metrics = dashboard.get_daily_metrics()  
except Exception as e:
    st.error(f"Error loading dashboard: {e}")
    st.stop()

# ==============================================================================
# CALENDAR VIEW
# ==============================================================================
def render_calendar_view(dashboard):
    from streamlit_calendar import calendar

    st.subheader("📅 Follow-Up Calendar")
    
    events = []
    
    # Define colors for past/future
    COLOR_FUTURE = "#FF4B4B" # Red/Primary
    COLOR_PAST = "#808080"   # Grey
    COLOR_TODAY = "#00C853"  # Green
    
    now_date = datetime.now().date()
    
    for email, rider in dashboard.riders.items():
        if rider.follow_up_date:
            fu_date = rider.follow_up_date.date()
            
            # Color Logic
            bg_color = COLOR_FUTURE
            if fu_date < now_date: bg_color = COLOR_PAST
            elif fu_date == now_date: bg_color = COLOR_TODAY
            
            # Create Event Object
            event = {
                "title": f"Follow Up: {rider.full_name}",
                "start": rider.follow_up_date.isoformat(),
                "allDay": True,
                "resourceId": email,
                "backgroundColor": bg_color,
                "borderColor": bg_color
            }
            events.append(event)

    calendar_options = {
        "headerToolbar": {
            "left": "today prev,next",
            "center": "title",
            "right": "dayGridMonth,timeGridWeek,listMonth"
        },
        "initialView": "dayGridMonth",
        "editable": True, # Enable Drag & Drop
    }
    
    # Render Calendar
    state = calendar(events=events, options=calendar_options, key="calendar_widget")
    
    # HANDLER: Drag & Drop (Event Change)
    if state.get("eventChange"):
        change = state["eventChange"]
        # Structure: {'event': {'start': 'ISO', ...}, 'oldEvent': {...}}
        event = change.get("event", {})
        email = event.get("extendedProps", {}).get("resourceId")
        new_start_str = event.get("start")
        
        if email and new_start_str:
            try:
                # Parse ISO date (simplified, might need robust parsing for TZ)
                # streamlit-calendar usually returns ISO 8601
                from dateutil import parser
                new_date = parser.parse(new_start_str)
                
                # Update Backend
                dashboard.data_loader.save_rider_details(email, follow_up_date=new_date)
                st.toast(f"Moved follow-up to {new_date.strftime('%d %b')}!")
                
                # Rerun to update local state (rider dict)
                # (save_rider_details updates rider memory too)
                st.rerun()
                
            except Exception as e:
                st.error(f"Failed to update date: {e}")

    # HANDLER: Click
    if state.get("eventClick"):
        event = state["eventClick"]["event"]
        email = event.get("extendedProps", {}).get("resourceId")
        
        if email in dashboard.riders:
            rider = dashboard.riders[email]
            st.divider()
            st.markdown(f"### Selected: {rider.full_name}")
            view_unified_dialog(rider, dashboard)


# NAVIGATION BAR
# Use session state to persist tab selection across reruns
# NAVIGATION BAR
# Use session state to persist tab selection across reruns
nav = st.radio(
    "Navigation", 
    ["📊 Funnel Dashboard", "📅 Calendar", "🏁 Race Outreach", "🗃️ All Riders", "⚙️ Admin / Uploads"], 
    horizontal=True, 
    label_visibility="collapsed", 
    key="main_nav" # This binding ensures persistence
)

# Render View
if nav == "📊 Funnel Dashboard":
    # Pass ALL riders so the internal "Timeframe" filter can work correctly.
    # Previously, this was hardcoded to filter by Current Month, breaking "All Time" view.
    render_dashboard(dashboard, daily_metrics, riders)
elif nav == "🏁 Race Outreach":
    render_race_outreach(dashboard)
elif nav == "🗃️ All Riders":
    render_database_view(dashboard)
elif nav == "⚙️ Admin / Uploads":
    render_admin(dashboard, overrides, sheet_errors, riders)
elif nav == "📅 Calendar":
    render_calendar_view(dashboard)
