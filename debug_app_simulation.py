import pandas as pd
from funnel_manager import FunnelDashboard
import os

print("--- Debug App Simulation ---")

# 1. Simulate the Override DataFrame (as if it came from GSheets)
# We won't fetch from Google here to save time/complexity, we'll create a dummy DF 
# that mimics the shape of the real one (based on previous debug output).
# Or better, we can read the local file and pass it as an override to prove the ingestion works.

# Let's try to pass the local CSV (89 rows) as an override and see if it loads 89 or 0.
# Then we can verify if the key normalization is working.

csv_path = "Rider Database.csv"
if os.path.exists(csv_path):
    print(f"Reading local CSV {csv_path}...")
    df_local = pd.read_csv(csv_path)
    print(f"Local DF Shape: {df_local.shape}")
    print(f"Columns: {df_local.columns.tolist()}")
    
    overrides = {
        "Rider Database.csv": df_local
    }
    
    print("\nInitializing Dashboard with Override...")
    # Initialize dashboard with overrides
    dashboard = FunnelDashboard(os.getcwd(), overrides=overrides)
    dashboard.reload_data()
    
    # Try to find the loader
    loader = None
    if hasattr(dashboard, 'data_loader'):
        loader = dashboard.data_loader
    elif hasattr(dashboard, 'loader'):
        loader = dashboard.loader
    
    if loader:
        print(f"\nTotal Riders in Dashboard: {len(loader.riders)}")
        
        if len(loader.riders) > 0:
            first_rider = list(loader.riders.values())[0]
            print(f"First Rider: {first_rider.full_name} ({first_rider.email})")
    else:
        print("❌ Could not find loader on dashboard object")
        print(dir(dashboard))
            
    # Check if a specific rider from the CSV is there
    # Pick the first one
    if not df_local.empty:
        # Check column names first to handle local CSV structure
        print(f"Local CSV Columns: {df_local.columns.tolist()}")
        
        # Adjust for local CSV columns if needed
        email_col = 'Email Address' if 'Email Address' in df_local.columns else 'email'
        
        if email_col in df_local.columns:
            first_email = df_local.iloc[0][email_col]
            print(f"Checking for email: {first_email}")
            
            if loader and first_email.lower() in loader.riders:
                print("✅ Found first rider!")
            else:
                print("❌ First rider MISSING.")
        else:
             print(f"❌ '{email_col}' column not found in local CSV")

    # Check Andy
    if loader:
        target = "Andy DiBrino"
        found = False
        for r in loader.riders.values():
            if target.lower() in r.full_name.lower():
                found = True
                break
        print(f"Search for '{target}': {'✅ Found' if found else '❌ Not Found'}")

else:
    print("Rider Database.csv missing locally.")

print("\n--- Testing Key Normalization ---")
# Manually verify one row ingestion logic
test_row = {
    "Email Address": "test@example.com",
    "First Name": "Testy",
    "Last Name": "McTest",
    "Facebook URL": "http://fb.com/test",
    "FB Username": "insta_test"
}
# _get_data_iter will lowercase this
norm_row = {k.lower(): v for k, v in test_row.items()}
print(f"Normalized Row: {norm_row}")

# Check logic from funnel_manager manually
email = norm_row.get("email address", "").strip()
print(f"Extracted email: '{email}'")
    
