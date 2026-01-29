from funnel_manager import DataLoader, RaceResultManager
import os

print("--- Debug Rider Lookup ---")
base_dir = os.getcwd()
loader = DataLoader(base_dir)

# Force load
print("Loading data...")
loader.load_all_data()
manager = RaceResultManager(loader)

print(f"Total Riders Loaded: {len(loader.riders)}")

target_name = "Andy DiBrino"
print(f"\nSearching for: '{target_name}'")

found_exact = False
found_fuzzy = False

# 1. Manual Scan
print("\n--- Manual Scan of Loaded Names ---")
for email, rider in loader.riders.items():
    if "dibrino" in rider.full_name.lower():
        print(f"FOUND IN DB: '{rider.full_name}' (Email: {rider.email})")
        found_exact = True
    
    if "andy" in rider.full_name.lower():
        # print(f"Partial match: {rider.full_name}") 
        pass

if not found_exact:
    print("❌ NOT COMPLETED FOUND in manual scan (case insensitive 'dibrino')")

# 2. Test Manager Match
print("\n--- Testing Manager Match Logic ---")
match = manager.match_rider(target_name)
if match:
    print(f"✅ Manager Match Success: Matched to '{match.full_name}'")
else:
    print("❌ Manager Match FAILED")

# 3. Test Manager Match with lower
match_lower = manager.match_rider(target_name.lower())
if match_lower:
     print(f"✅ Manager Match (Lower Input) Success: Matched to '{match_lower.full_name}'")
else:
     print("❌ Manager Match (Lower Input) FAILED")
