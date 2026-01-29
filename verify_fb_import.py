from funnel_manager import DataLoader, OutreachChannel
import os
import pandas as pd

data_dir = os.getcwd() # or specific path
dl = DataLoader(data_dir)

print("Loading standard data...")
dl.load_all_data()
initial_count = len(dl.riders)
print(f"Total Riders in System: {initial_count}")

# Verify FB specifics
fb_count = 0
for email, r in dl.riders.items():
    # Check if key starts with no_email_ AND channel is FB
    # Note: comparing enum to string was the bug.
    if email.startswith("no_email_") and r.outreach_channel == OutreachChannel.FACEBOOK_DM: 
        fb_count += 1
        
print(f"Riders identified as FB imports (clean check): {fb_count}")

# Analyze the Source File
filename = "Facebook Messenger History - Sheet1 (1).csv"
filepath = os.path.join(data_dir, filename)
if os.path.exists(filepath):
    try:
        df = pd.read_csv(filepath, header=1)
        print(f"Total Rows in FB CSV: {len(df)}")
        if 'title' in df.columns:
            unique_titles = df['title'].nunique()
            print(f"Unique Titles (Conversations) in FB CSV: {unique_titles}")
            
            # Check how many are 'Craig Muirhead' or nan
            craig_count = df[df['title'].astype(str).str.lower() == 'craig muirhead']['title'].nunique()
            print(f" - Matches 'Craig Muirhead': {craig_count}")
            
            # Sample titles
            print(f"Sample Titles: {df['title'].unique()[:5]}")
    except Exception as e:
        print(f"Error analyzing CSV: {e}")
else:
    print("FB CSV file not found.")
