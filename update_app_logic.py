import sys
from datetime import datetime
from funnel_manager import FunnelStage 

# Same replacement block
NEW_BLOCK = """                # BRANCH: MATCHED RIDER -> Unified Card
                if r['match_status'] == 'match_found' and r.get('match'):
                    st.success(f"✅ Matched: {r['match'].full_name}")
                    render_unified_card_content(r['match'], dashboard, key_suffix=f"race_{i}", default_event_name=event_name)
                    
                else:
                    # BRANCH: NEW PROSPECT -> Deep Search & Add Form
                    rc1, rc2 = st.columns(2)
                    
                    # LEFT: Draft Message
                    with rc1:
                        st.write("#### 📝 Outreach Draft")
                        msg = dashboard.generate_outreach_message(r, event_name)
                        evt_key = event_name.replace(" ", "_").lower()
                        st.text_area("Message", value=msg, height=100, key=f"msg_{i}_{r['original_name']}_{evt_key}")
                        st.caption("Copy for DM:")
                        st.code(msg, language=None)
                        
                        st.write("---")
                        if st.button("🚀 Confirm Message Sent", key=f"sent_{i}_{r['original_name']}", type="primary"):
                             st.error("Please 'Add Contact' first.")

                    # RIGHT: Search/Add
                    with rc2:
                        st.write("#### 👤 Contact Actions")
                        
                        # Copy of New Prospect Logic
                        st.info("Rider not in database.")
                        search_key = f"search_done_{i}_{r['original_name']}"
                        manual_key = f"manual_add_{i}"
                        
                        c_search, c_manual = st.columns(2)
                        if c_search.button(f"🔍 Find Socials", key=f"btn_search_{i}"):
                            with st.spinner("Searching..."):
                                socials = dashboard.race_manager.find_socials_for_prospect(r['original_name'], event_name)
                                st.session_state[search_key] = socials
                        
                        if c_manual.button("➕ Add Manually", key=f"btn_man_{i}"):
                             st.session_state[manual_key] = True
                        
                        show_form = False
                        found_socials = {}
                        if search_key in st.session_state:
                            found_socials = st.session_state[search_key]
                            show_form = True
                            if found_socials: st.success("Found Profiles!")
                            else: st.warning("No profiles found.")
                        
                        if st.session_state.get(manual_key): show_form = True
                        
                        if found_socials:
                            fb_val = found_socials.get('facebook_url', '')
                            ig_val = found_socials.get('instagram_url', '')
                            if fb_val: st.markdown(f"**Facebook**: [{fb_val}]({fb_val})")
                            if ig_val: st.markdown(f"**Instagram**: [{ig_val}]({ig_val})")
                        else:
                             st.markdown("---")
                             with st.expander("🕵️ Deep Search Toolkit", expanded=False):
                                 deep = dashboard.race_manager.social_finder.generate_deep_search_links(r['original_name'], event_name)
                                 st.markdown(f"[🔍 Core Search]({deep['🔍 Core Discovery']})")
                                 st.markdown(f"[📷 Instagram]({deep['📸 Instagram Profile']})")

                        if show_form:
                             with st.form(key=f"add_contact_{i}"):
                                 st.caption(f"Add **{r['original_name']}**")
                                 parts = r['original_name'].split(' ')
                                 f_geo = parts[0].title()
                                 l_geo = parts[1].title() if len(parts) > 1 else ""
                                 
                                 f = st.text_input("First Name", value=f_geo)
                                 l = st.text_input("Last Name", value=l_geo)
                                 e = st.text_input("Email", value=f"no_email_{f_geo}_{l_geo}".lower())
                                 c = st.text_input("Championship")
                                 fb = st.text_input("Facebook", value=found_socials.get('facebook_url',''))
                                 ig = st.text_input("Instagram", value=found_socials.get('instagram_url',''))
                                 
                                 if st.form_submit_button("💾 Save"):
                                     if dashboard.add_new_rider(e, f, l, fb, ig_url=ig, championship=c):
                                         dashboard.update_rider_stage(e, FunnelStage.CONTACT)
                                         if e in dashboard.riders:
                                             r['match_status'] = 'match_found'
                                             r['match'] = dashboard.riders[e]
                                         st.rerun()
                                     else: st.error("Failed.")
"""

with open('app.py', 'r') as f:
    lines = f.readlines()

# Replace lines 1003 to 1198
start_idx = 1003
end_idx = 1198

print(f"Start Check: {lines[start_idx]}")
print(f"End Check: {lines[end_idx-1]}")

lines[start_idx:end_idx] = [NEW_BLOCK + "\n"]

with open('app.py', 'w') as f:
    f.writelines(lines)
print("Success")
