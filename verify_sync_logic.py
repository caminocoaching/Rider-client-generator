from funnel_manager import DataLoader
import os
import csv

data_dir = os.getcwd()
dl = DataLoader(data_dir)
dl.load_all_data()

print(f"Total Riders in Memory: {len(dl.riders)}")

# IDENTIFICATION LOGIC REPLICATION
db_file = os.path.join(data_dir, "Rider Database.csv")
existing_emails = set()
if os.path.exists(db_file):
    with open(db_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if 'email' in row and row['email']:
                existing_emails.add(row['email'].strip().lower())

riders_to_add = []
for r in dl.riders.values():
    if r.email.lower() not in existing_emails:
        riders_to_add.append(r)

print(f"Existing Emails in CSV: {len(existing_emails)}")
print(f"Riders Identified for Sync: {len(riders_to_add)}")

if riders_to_add:
    print("\nSample Riders to Add:")
    for r in riders_to_add[:5]:
        print(f" - {r.full_name} ({r.email}) [Source: {r.outreach_channel}]")
