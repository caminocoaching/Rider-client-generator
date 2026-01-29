
import toml
import os
from google.oauth2 import service_account
from googleapiclient.discovery import build

# Load secrets
try:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    secrets_path = os.path.join(base_dir, ".streamlit/secrets.toml")
    print(f"Loading secrets from: {secrets_path}")
    secrets = toml.load(secrets_path)
    creds_info = secrets["connections"]["gsheets"]
    sheets_info = secrets["sheets"]
except Exception as e:
    print(f"Failed to load secrets: {e}")
    exit(1)

# Construct credentials dictionary manually to ensure correct format
# Specifically handling the private_key to ensure newlines are processed correctly
private_key = creds_info["private_key"]
if "\\n" in private_key:
    print("Detected literal \\n in private_key, replacing with actual newlines...")
    private_key = private_key.replace("\\n", "\n")

service_account_info = {
    "type": creds_info["type"],
    "project_id": creds_info["project_id"],
    "private_key_id": creds_info["private_key_id"],
    "private_key": private_key,
    "client_email": creds_info["client_email"],
    "client_id": creds_info["client_id"],
    "auth_uri": creds_info["auth_uri"],
    "token_uri": creds_info["token_uri"],
    "auth_provider_x509_cert_url": creds_info["auth_provider_x509_cert_url"],
    "client_x509_cert_url": creds_info["client_x509_cert_url"]
}

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

print(f"Attempting to authenticate as: {service_account_info['client_email']}")

try:
    creds = service_account.Credentials.from_service_account_info(
        service_account_info, scopes=SCOPES)
    service = build('sheets', 'v4', credentials=creds)
    print("Authentication successful!")
except Exception as e:
    print(f"Authentication FAILED: {e}")
    exit(1)

# Try to access the rider_db sheet
rider_db_url = sheets_info.get("rider_db")
print(f"\nTesting access into: {rider_db_url}")

# Extract Spreadsheet ID
# Format: https://docs.google.com/spreadsheets/d/SPREADSHEET_ID/edit...
try:
    spreadsheet_id = rider_db_url.split("/d/")[1].split("/")[0]
    print(f"Spreadsheet ID: {spreadsheet_id}")
    
    sheet = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    print(f"SUCCESS! Accessed sheet: {sheet['properties']['title']}")
    
except Exception as e:
    print(f"FAILED to access sheet. Error: {e}")
