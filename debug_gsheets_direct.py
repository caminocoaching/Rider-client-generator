import toml
import pandas as pd
import requests
from google.oauth2 import service_account
from google.auth.transport.requests import Request
import os

print("--- Debug GSheets Direct ---")

# 1. Load Secrets
secrets_path = ".streamlit/secrets.toml"
if not os.path.exists(secrets_path):
    print("❌ secrets.toml not found")
    exit()

with open(secrets_path, "r") as f:
    secrets = toml.load(f)

if "connections" in secrets and "gsheets" in secrets["connections"]:
    creds_info = secrets["connections"]["gsheets"]
else:
    print("❌ GSheets creds not found in secrets")
    exit()

# 2. Setup Creds
try:
    private_key = creds_info["private_key"]
    if "\\n" in private_key:
        private_key = private_key.replace("\\n", "\n")
        
    service_account_info = {
        "type": creds_info.get("type", "service_account"),
        "project_id": creds_info["project_id"],
        "private_key_id": creds_info["private_key_id"],
        "private_key": private_key,
        "client_email": creds_info["client_email"],
        "client_id": creds_info["client_id"],
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_x509_cert_url": creds_info.get("client_x509_cert_url", "")
    }
    
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']
    creds = service_account.Credentials.from_service_account_info(service_account_info, scopes=SCOPES)
    print("✅ Credentials created")
except Exception as e:
    print(f"❌ Error creating credentials: {e}")
    exit()

# 3. Load Function (Replicated from gsheets_loader.py to verify independently)
def test_load(sheet_url):
    print(f"Loading: {sheet_url}")
    if not creds.valid or creds.expired:
        creds.refresh(Request())
        
    if "/d/" in sheet_url:
        spreadsheet_id = sheet_url.split("/d/")[1].split("/")[0]
    else:
        print("Invalid URL")
        return

    # Check for GID
    target_sheet_name = None
    gid = None
    
    # Simple extraction logic same as deployed code
    if "gid=" in sheet_url:
        try:
             # Look for gid in fragments
             if "#gid=" in sheet_url:
                 gid = sheet_url.split("#gid=")[1].split("&")[0]
             elif "?gid=" in sheet_url:
                 gid = sheet_url.split("?gid=")[1].split("&")[0]
             elif "&gid=" in sheet_url:
                 gid = sheet_url.split("&gid=")[1].split("&")[0]
        except:
            pass
            
    headers = {"Authorization": f"Bearer {creds.token}"}
    
    if gid:
        print(f"Detected GID: {gid}")
        meta_url = f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}"
        meta_resp = requests.get(meta_url, headers=headers)
        if meta_resp.status_code == 200:
            sheets = meta_resp.json().get('sheets', [])
            for s in sheets:
                props = s.get('properties', {})
                if str(props.get('sheetId')) == str(gid):
                    target_sheet_name = props.get('title')
                    print(f"Mapped GID {gid} -> Sheet Name: '{target_sheet_name}'")
                    break
    
    range_name = f"'{target_sheet_name}'!A:ZZ" if target_sheet_name else "A:ZZ"
    print(f"Fetching Range: {range_name}")
    
    api_url = f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values/{range_name}"
    resp = requests.get(api_url, headers=headers)
    
    if resp.status_code != 200:
        print(f"❌ API Error {resp.status_code}: {resp.text}")
        return

    data = resp.json()
    values = data.get('values', [])
    print(f"✅ Rows Fetched: {len(values)}")
    if len(values) > 0:
        print(f"Header: {values[0]}")
        
    return values

# 4. Execute
if "sheets" in secrets and "rider_db" in secrets["sheets"]:
    url = secrets["sheets"]["rider_db"]
    test_load(url)
else:
    print("rider_db url not found")
