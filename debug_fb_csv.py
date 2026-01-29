import pandas as pd
import os

filename = "Facebook Messenger History - Sheet1 (1).csv"
if not os.path.exists(filename):
    print(f"File not found: {filename}")
    exit()

try:
    print(f"Loading {filename}...")
    # Try header=1 as per current logic
    df = pd.read_csv(filename, header=1)
    
    print(f"Rows: {len(df)}")
    print(f"Columns: {list(df.columns)}")
    
    if 'title' in df.columns:
        titles = df['title'].unique()
        print(f"Unique Titles: {len(titles)}")
        print("Sample Titles:", titles[:10])
        
        # Check Craig filter
        filtered_titles = [t for t in titles if str(t).lower().strip() != 'craig muirhead' and str(t).lower() != 'nan']
        print(f"Filtered Unique Titles (Prospects): {len(filtered_titles)}")
    else:
        print("ERROR: 'title' column not found!")
        
except Exception as e:
    print(f"Error loading CSV: {e}")
