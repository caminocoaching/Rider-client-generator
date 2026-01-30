import streamlit as st
import urllib.parse
from datetime import datetime, timedelta
from funnel_manager import FunnelStage

# --- CONSTANTS ---
REPLY_TEMPLATES = {
    # --- COLD OUTREACH RESPONSES ---
    "Great Work (Reply)": """Thanks for the reply {name},
That’s Great work well done!
Not sure if you know — I’m a Flow Performance Coach. A bit different from the usual rider-coach.
I work with riders in many championships on the mental side of racing — helping them access the Flow State, where performance becomes automatic, consistent, and confident under pressure.
I’ve built a free post-race assessment tool that shows exactly where your gains are hiding — and how to unlock them in time for the next round.
Want me to send it over?""",

    "Productive (Reply)": """Thanks for the reply {name},
Sounds like you had a productive weekend
Not sure if you know — I’m a Flow Performance Coach. A bit different from the usual rider-coach.
I work with riders in many championships on the mental side of racing — helping them access the Flow State, where performance becomes automatic, consistent, and confident under pressure.
I’ve built a free post-race assessment tool that shows exactly where your gains are hiding — and how to unlock them in time for the next round.
Want me to send it over?""",

    "Tough Weekend (Reply)": """Thanks for the reply {name}, it Sounds like you had a tough weekend
Not sure if you know — I’m a Flow Performance Coach. A bit different from the usual rider-coach.
I work with riders in many championships on the mental side of racing — helping them access the Flow State, where performance becomes automatic, consistent, and confident under pressure.
I’ve built a free post-race assessment tool that shows exactly where your gains are hiding — and how to unlock them in time for the next round.
Want me to send it over?""",

    "Send Link (Yes)": """Great. Here is the link: https://improve-rider.scoreapp.com/
No pressure to do anything with it right away, but it usually reveals some interesting gaps.
Let me know what your score is once you've done it!""",

    # --- PIPELINE FOLLOW-UPS ---
    "Follow-Up (Review 2 Days) V1": """Hey {name}
Just checking in - did you get a chance to go through the post-race review I sent over?
Takes about 5 minutes and shows exactly where the gains are hiding for you.
Let me know if the link didn't work or if you had any issues with it 👍""",

    "Follow-Up (Review 2 Days) V2": """{name} - wanted to circle back on the race weekend assessment
Most riders who complete it say the same thing: 'I didn't realise THAT was what was holding me back'
If you're still interested, the link's below. If not, no worries - good luck with the rest of the season 👍""",

    "Offer Free Training": """Hey {name}, Great to see you will be lining up on the grid this season
We have some pre-season free training that many riders are using to ensure they are on point from the first round this season.
Want me to send it over?""",

    "Send Blueprint Link": """OK {name} here you go, instant access to the Podium Contenders Blueprint
https://academy.caminocoaching.co.uk/podium-contenders-blueprint/order/

📚 What you'll learn:
✓ Day 1: The 7 biggest mistakes costing you lap times
✓ Day 2: The 5-pillar system for accessing flow state on command
✓ Day 3: Your race weekend mental preparation protocol

Complete all 3 days, and you'll unlock a free strategy call where we'll create your personalised performance roadmap for 2026.
See you inside! 🏁
Craig""",

    # --- TRAINING PROGRESS NUDGES ---
    "Stalled: Signed In": """Hi {name} I see you signed into the free training but didn't go much further was everything ok with the link and the platform for you?""",

    "Stalled: Day 1 Only": """Hey, {name}, Great work on completing the first day of the free training how was it for you?""",

    "Stalled: Day 2 Only": """Hey {name}, I see you completed the first 2 days of the Free Training but missed the third, is everything ok with the link and platform for you?""",

    "Stalled: Day 3 Only": """Hey {name}, I see you completed the Free Training but haven't booked your free strategy call yet.
I have a few slots open this week if you want to dial in your plan for the season?"""
}

def render_unified_card_content(rider, dashboard, key_suffix="", default_event_name=None):
    """
    Renders the rich contact card (2 columns).
    Used in:
    1. Race Outreach (Inline)
    2. Funnel Dashboard (Dialog)
    3. Database Page (Dialog)
    """
    
    uc1, uc2 = st.columns(2)
    
    # --- LEFT COL: MESSAGING ---
    with uc1:
        st.write("#### 📝 Outreach / Reply")
        
        # 1. TEMPLATE SELECTOR
        template_options = ["(Draft / Custom)"] + list(REPLY_TEMPLATES.keys())
        if default_event_name:
            template_options.insert(1, "✨ Auto-Generate (Race Context)")
            
        tmpl_key = st.selectbox(
            "Choose Template", 
            options=template_options,
            key=f"uni_tpl_{rider.email}_{key_suffix}"
        )
        
        # 2. MESSAGE GENERATION
        draft_msg = ""
        
        if tmpl_key == "✨ Auto-Generate (Race Context)" and default_event_name:
             # Generate using race logic
             mock_raw = {'original_name': rider.full_name, 'match_status': 'match_found', 'match': rider}
             draft_msg = dashboard.generate_outreach_message(mock_raw, default_event_name)
             
        elif tmpl_key in REPLY_TEMPLATES:
            raw_msg = REPLY_TEMPLATES[tmpl_key]
            first_name = rider.first_name or (rider.full_name.split(' ')[0] if rider.full_name else "Mate")
            draft_msg = raw_msg.replace("{name}", first_name)
            
        # Session State for Message Body
        msg_key = f"uni_msg_{rider.email}_{key_suffix}"
        
        prev_tpl_key = f"prev_tpl_{rider.email}_{key_suffix}"
        if prev_tpl_key not in st.session_state:
            st.session_state[prev_tpl_key] = "(Draft / Custom)"
            
        # Detect Change
        if tmpl_key != st.session_state[prev_tpl_key]:
             if tmpl_key != "(Draft / Custom)":
                 st.session_state[msg_key] = draft_msg
             st.session_state[prev_tpl_key] = tmpl_key
        
        final_msg = st.text_area(
            "Message", 
            key=msg_key,
            height=250
        )
        
        # Actions
        st.caption("Copy for DM:")
        st.code(final_msg, language=None)
        
        c_act1, c_act2 = st.columns(2)
        with c_act1:
            if st.button("🚀 Mark Messaged", key=f"uni_sent_{rider.email}_{key_suffix}", help="Moves stage to Messaged"):
                 dashboard.update_rider_stage(rider.email, FunnelStage.MESSAGED)
                 st.toast(f"Marked {rider.first_name} as Messaged!")
                 st.rerun()

    # --- RIGHT COL: INFO & ACTIONS ---
    with uc2:
        st.write("#### 👤 Contact Actions")
        
        # Info Block
        st.markdown(f"**Stage:** `{rider.current_stage.value}`")
        if rider.phone: st.markdown(f"**Phone:** `{rider.phone}`")
        
        # Socials
        links = []
        if rider.facebook_url: 
            links.append(f"[Facebook]({rider.facebook_url})")
        if rider.instagram_url: 
            links.append(f"[Instagram]({rider.instagram_url})")
        
        if links:
            st.markdown(f"**Socials:** {' | '.join(links)}")
            
            # --- DEEP DM ACTION BUTTONS ---
            # Try to generate mobile-first DM links if URLs exist
            dm_cols = st.columns(2)
            
            # Init finder locally if needed (lightweight)
            # Ideally passed in, but we can instantiate safely
            from funnel_manager import SocialFinder
            finder = SocialFinder()
            
            # FB DM
            if rider.facebook_url:
                deep_fb = finder.generate_deep_dm_link('facebook', rider.facebook_url, final_msg)
                if deep_fb:
                    with dm_cols[0]:
                        st.markdown(f'''
                            <a href="{deep_fb}" target="_blank" style="text-decoration:none;">
                                <button style="width:100%; border:1px solid #4CAF50; background-color:#4CAF50; color:white; padding:5px; border-radius:5px; cursor:pointer;">
                                   💬 DM on FB (Direct)
                                </button>
                            </a>
                            ''', unsafe_allow_html=True)

            # IG DM
            if rider.instagram_url:
                deep_ig = finder.generate_deep_dm_link('instagram', rider.instagram_url, final_msg)
                if deep_ig:
                    with dm_cols[1]:
                        st.markdown(f'''
                            <a href="{deep_ig}" target="_blank" style="text-decoration:none;">
                                <button style="width:100%; border:1px solid #E1306C; background-color:#E1306C; color:white; padding:5px; border-radius:5px; cursor:pointer;">
                                   📸 DM on IG (Direct)
                                </button>
                            </a>
                            ''', unsafe_allow_html=True)
            
        else:
            query = f"{rider.full_name} motorcycle racing"
            search_url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
            st.markdown(f"[🔎 Search Google]({search_url})")
            
        st.divider()
        
        # QUICK ACTIONS: Follow Up
        st.caption("📅 Quick Follow-Up")
        b1, b2, b3 = st.columns(3)
        
        now = datetime.now()
        
        if b1.button("+3 Days", key=f"fu_3d_{rider.email}_{key_suffix}", use_container_width=True):
            new_date = now + timedelta(days=3)
            dashboard.data_loader.save_rider_details(rider.email, follow_up_date=new_date)
            st.toast(f"Follow-up set for {new_date.strftime('%a %d %b')}")
            st.rerun()
            
        if b2.button("+1 Wk", key=f"fu_1w_{rider.email}_{key_suffix}", use_container_width=True):
            new_date = now + timedelta(weeks=1)
            dashboard.data_loader.save_rider_details(rider.email, follow_up_date=new_date)
            st.toast(f"Follow-up set for {new_date.strftime('%a %d %b')}")
            st.rerun()

        if b3.button("+1 Mo", key=f"fu_1m_{rider.email}_{key_suffix}", use_container_width=True):
            new_date = now + timedelta(days=30)
            dashboard.data_loader.save_rider_details(rider.email, follow_up_date=new_date)
            st.toast(f"Follow-up set for {new_date.strftime('%a %d %b')}")
            st.rerun()
            
        # Update Details Form
        with st.expander("✏️ Update Details", expanded=True):
            with st.form(key=f"uni_upd_{rider.email}_{key_suffix}"):
                u_first = st.text_input("First Name", value=rider.first_name, key=f"uni_first_{rider.email}_{key_suffix}")
                u_last = st.text_input("Last Name", value=rider.last_name, key=f"uni_last_{rider.email}_{key_suffix}")
                u_fb = st.text_input("Facebook URL", value=rider.facebook_url or "", key=f"uni_fb_{rider.email}_{key_suffix}")
                u_ig = st.text_input("Instagram URL", value=rider.instagram_url or "", key=f"uni_ig_{rider.email}_{key_suffix}")
                u_champ = st.text_input("Championship", value=rider.championship or "", key=f"uni_champ_{rider.email}_{key_suffix}")
                
                 # Follow Up Date
                default_date = rider.follow_up_date.date() if rider.follow_up_date else None
                u_follow = st.date_input("📅 Next Follow-Up", value=default_date, key=f"uni_fu_{rider.email}_{key_suffix}")
                
                u_notes = st.text_area("Notes", value=rider.notes or "", key=f"uni_notes_{rider.email}_{key_suffix}")
                
                # --- EXPLICIT MOVE TO AIRTABLE BUTTON (for visuals) ---
                # Although Update does it, user likes the explicit button?
                # The form submit handles Everything.
                # Let's add a note or separate button OUTSIDE form if needed.
                # "Save Updates" implies sync.
                
                if st.form_submit_button("💾 Save Updates (Sync & Migrate)"):
                    ts_follow = datetime.combine(u_follow, datetime.min.time()) if u_follow else None
                    
                    dashboard.add_new_rider(
                        rider.email, u_first, u_last, u_fb, ig_url=u_ig, championship=u_champ, notes=u_notes, follow_up_date=ts_follow
                    )
                    st.toast(f"Updated & Synced {u_first}!")
                    st.rerun()

        # Explicit Move Button (Outside form, for quick action)
        if st.button("✈️ Move to Airtable (Force)", key=f"uni_mv_{rider.email}_{key_suffix}", help="Force sync this rider to Airtable and delete from Google Sheets"):
             count = dashboard.migrate_rider_to_airtable(rider.email)
             if count:
                 st.success("Moved to Airtable!")
                 st.rerun()
             else:
                 st.warning("Already synced or failed.")
