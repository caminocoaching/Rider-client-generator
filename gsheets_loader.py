import pandas as pd
import os
import requests
import urllib.parse
from google.oauth2 import service_account
from google.auth.transport.requests import Request
import streamlit as st

def get_service_account_creds():
    """Validates and returns credential object from st.secrets"""
    # Try to load from st.secrets first (handling nesting)
    try:
        # Check for our specific structure
        if "connections" in st.secrets and "gsheets" in st.secrets["connections"]:
            creds_info = st.secrets["connections"]["gsheets"]
        else:
            # Fallback for standard structure if changed
            creds_info = st.secrets
            
        # Helper to fix key if needed (though we fixed content in file)
        private_key = creds_info["private_key"]
        
        # Robustly fix newlines if they are escaped literals (just in case)
        if "\\n" in private_key:
            private_key = private_key.replace("\\n", "\n")
        
        # Mapping to standard service account dict
        service_account_info = {
            "type": creds_info.get("type", "service_account"),
            "project_id": creds_info["project_id"],
            "private_key_id": creds_info["private_key_id"],
            "private_key": private_key,
            "client_email": creds_info["client_email"],
            "client_id": creds_info["client_id"],
            "auth_uri": creds_info.get("auth_uri", "https://accounts.google.com/o/oauth2/auth"),
            "token_uri": creds_info.get("token_uri", "https://oauth2.googleapis.com/token"),
            "auth_provider_x509_cert_url": creds_info.get("auth_provider_x509_cert_url", "https://www.googleapis.com/oauth2/v1/certs"),
            "client_x509_cert_url": creds_info.get("client_x509_cert_url", "")
        }
        
        SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
        
        creds = service_account.Credentials.from_service_account_info(
            service_account_info, scopes=SCOPES)
        return creds
        
    except Exception as e:
        st.error(f"Error creating credentials: {e}")
        return None

def load_google_sheet(sheet_url):
    """Loads a Google Sheet as a pandas DataFrame using direct API"""
    try:
        creds = get_service_account_creds()
        if not creds:
            return None
            
        if not creds.valid or creds.expired:
            creds.refresh(Request())
            
        # Parse ID from URL
        if "/d/" in sheet_url:
            spreadsheet_id = sheet_url.split("/d/")[1].split("/")[0]
        else:
            return None # Invalid URL

        # Check for GID (Worksheet ID) to target specific tab
        target_sheet_name = None
        gid = None
        if "gid=" in sheet_url:
            try:
                # Handle #gid=123 or ?gid=123
                if "#gid=" in sheet_url:
                    gid = sheet_url.split("#gid=")[1].split("&")[0]
                elif "?gid=" in sheet_url:
                    gid = sheet_url.split("?gid=")[1].split("&")[0]
                elif "&gid=" in sheet_url:
                    gid = sheet_url.split("&gid=")[1].split("&")[0]
            except:
                pass

        headers = {"Authorization": f"Bearer {creds.token}"}

        # If we have a GID, we need to find the sheet name
        if gid:
            meta_url = f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}"
            meta_resp = requests.get(meta_url, headers=headers)
            if meta_resp.status_code == 200:
                sheets = meta_resp.json().get('sheets', [])
                for s in sheets:
                    props = s.get('properties', {})
                    if str(props.get('sheetId')) == str(gid):
                        target_sheet_name = props.get('title')
                        break
        
        # Construct Range
        # If we found a name, use it. Otherwise default to 'A:ZZ' (first sheet)
        range_name = f"'{target_sheet_name}'!A:ZZ" if target_sheet_name else "A:ZZ"
        
        # Use simple Values API to get all data
        # URL Encode the range to handle slashes (e.g. '01/25') in sheet names
        # safe='' ensures slashes are encoded to %2F, which is required for path parameters
        encoded_range = urllib.parse.quote(range_name, safe='')
        api_url = f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values/{encoded_range}"
        
        resp = requests.get(api_url, headers=headers)
        
        if resp.status_code != 200:
            raise Exception(f"API Error {resp.status_code}: {resp.text}")
            
        data = resp.json()
        values = data.get('values', [])
        
        if not values:
            return pd.DataFrame()
            
        # Convert to DataFrame
        # Assume first row is header
        header = values[0]
        rows = values[1:]
        
        # Handle rows with varying lengths (API omits trailing empty cells)
        # Pad rows to match header length
        padded_rows = []
        for r in rows:
            if len(r) < len(header):
                r = r + [''] * (len(header) - len(r))
            padded_rows.append(r[:len(header)]) # Truncate if too long?
            
        df = pd.DataFrame(padded_rows, columns=header)
        return df
        
    except Exception as e:
        raise e

def append_row_to_sheet(sheet_url: str, row_data: list):
    """Appends a row of data to the specified Google Sheet"""
    try:
        creds = get_service_account_creds()
        if not creds:
             return False
             
        if not creds.valid or creds.expired:
            creds.refresh(Request())
            
        # Parse ID from URL
        if "/d/" in sheet_url:
            spreadsheet_id = sheet_url.split("/d/")[1].split("/")[0]
        else:
            return False

        # Determine Range (Sheet Name)
        target_sheet_name = None
        gid = None
        
        # Parse GID to find sheet name
        if "gid=" in sheet_url:
             try:
                 if "#gid=" in sheet_url:
                     gid = sheet_url.split("#gid=")[1].split("&")[0]
                 elif "?gid=" in sheet_url:
                     gid = sheet_url.split("?gid=")[1].split("&")[0]
                 elif "&gid=" in sheet_url:
                     gid = sheet_url.split("&gid=")[1].split("&")[0]
             except:
                 pass

        headers = {"Authorization": f"Bearer {creds.token}"}
        
        # Find Sheet Name if GID exists
        if gid:
            meta_url = f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}"
            meta_resp = requests.get(meta_url, headers=headers)
            if meta_resp.status_code == 200:
                sheets = meta_resp.json().get('sheets', [])
                for s in sheets:
                    props = s.get('properties', {})
                    if str(props.get('sheetId')) == str(gid):
                        target_sheet_name = props.get('title')
                        break
        
        # Default range (First sheet or specific sheet)
        range_name = f"'{target_sheet_name}'!A:A" if target_sheet_name else "A:A"
        
        # Prepare URL
        encoded_range = urllib.parse.quote(range_name, safe='')
        api_url = f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values/{encoded_range}:append"
        
        # Add query params
        params = {
            "valueInputOption": "USER_ENTERED",
            "insertDataOption": "INSERT_ROWS"
        }
        
        # Payload
        body = {
            "values": [row_data]
        }
        
        resp = requests.post(api_url, headers=headers, params=params, json=body)
        
        if resp.status_code == 200:
            return True
        else:
            print(f"GSheet Append Error: {resp.text}")
            return False
            
    except Exception as e:
        print(f"GSheet Append Exception: {e}")
        return False

def find_row_by_email(sheet_url: str, email: str, email_col_idx: int = 3):
    """
    Finds the row number (1-based) where the email matches.
    Assumes email is in column D (index 3) by default 'Email Address'
    """
    try:
        # For simplicity, we create a specialized light read
        # Or just reuse load_google_sheet if efficiency isn't critical (3-4k rows is fine)
        df = load_google_sheet(sheet_url)
        if df.empty: return None
        
        # Normalize
        email = email.lower().strip()
        
        # Identify Email Column
        target_col = None
        for col in df.columns:
            if str(col).lower().strip() in ['email address', 'email']:
                target_col = col
                break
        
        if not target_col: return None
        
        # Check for match
        # df index is 0-based, so row in sheet is index + 2 (Header is 1)
        matches = df[df[target_col].astype(str).str.lower().str.strip() == email]
        
        if not matches.empty:
            return matches.index[0] + 2 # +2 for 1-based sheet index + header row
            
        return None
            
    except Exception as e:
        print(f"Find Row Error: {e}")
        return None

def update_cell(sheet_url: str, row_idx: int, col_letter: str, value: str):
    """Updates a single cell"""
    # ... Simplified to use basic update ...
    try:
        creds = get_service_account_creds()
        if not creds: return False
        if not creds.valid: creds.refresh(Request())
        
        # ID and GID
        if "/d/" in sheet_url:
            spreadsheet_id = sheet_url.split("/d/")[1].split("/")[0]
        else: return False
        
        target_sheet_name = "Sheet1" # Fallback
        # (Assuming GID logic similar to append is used or needed, skipping for brevity - relying on default or simplified logic)
        # Re-using the GID finding logic...
        
        gid = None
        if "gid=" in sheet_url:
             try:
                 if "#gid=" in sheet_url: gid = sheet_url.split("#gid=")[1].split("&")[0]
                 elif "?gid=" in sheet_url: gid = sheet_url.split("?gid=")[1].split("&")[0]
                 elif "&gid=" in sheet_url: gid = sheet_url.split("&gid=")[1].split("&")[0]
             except: pass
        
        headers = {"Authorization": f"Bearer {creds.token}"}
        
        # Find Sheet Name
        if gid:
            meta_url = f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}"
            meta_resp = requests.get(meta_url, headers=headers)
            if meta_resp.status_code == 200:
                sheets = meta_resp.json().get('sheets', [])
                for s in sheets:
                    props = s.get('properties', {})
                    if str(props.get('sheetId')) == str(gid):
                        target_sheet_name = props.get('title')
                        break
        
        range_name = f"'{target_sheet_name}'!{col_letter}{row_idx}"
        encoded_range = urllib.parse.quote(range_name, safe='')
        
        api_url = f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values/{encoded_range}?valueInputOption=USER_ENTERED"
        
        body = { "values": [[value]] }
        
        resp = requests.put(api_url, headers=headers, json=body)
        return resp.status_code == 200
        
    except Exception as e:
        print(f"Update Cell Error: {e}")
        return False

def update_cell_by_header(sheet_url: str, row_idx: int, header_name: str, value: str):
    """Updates a cell by finding the column index of the given header name"""
    try:
        creds = get_service_account_creds()
        if not creds: return False
        
        # We need to find the column index for 'header_name'
        # Load just the first row?
        df = load_google_sheet(sheet_url) # Cached ideally, but for now full load
        if df.empty: return False
        
        col_idx = None
        for i, col in enumerate(df.columns):
            if str(col).lower().strip() == header_name.lower().strip():
                col_idx = i
                break
        
        if col_idx is None:
            # Header not found
            return False
            
        # Convert index to Letter (0 -> A, 1 -> B)
        # Simple implementation for A-Z, AA-ZZ
        def get_col_letter(n):
            string = ""
            while n >= 0:
                string = chr((n % 26) + 65) + string
                n = (n // 26) - 1
            return string
            
        col_letter = get_col_letter(col_idx)
        
        return update_cell(sheet_url, row_idx, col_letter, value)
        
    except Exception as e:
        print(f"Update By Header Error: {e}")
        return False

def clear_sheet(sheet_url: str):
    """Clears all values from the sheet"""
    try:
        creds = get_service_account_creds()
        if not creds: return False
        
         # ID and GID parsing (Standardize this helper?)
        if "/d/" in sheet_url:
            spreadsheet_id = sheet_url.split("/d/")[1].split("/")[0]
        else: return False
        
        target_sheet_name = "Sheet1"
        gid = None
        if "gid=" in sheet_url:
             try:
                 if "#gid=" in sheet_url: gid = sheet_url.split("#gid=")[1].split("&")[0]
                 elif "?gid=" in sheet_url: gid = sheet_url.split("?gid=")[1].split("&")[0]
                 elif "&gid=" in sheet_url: gid = sheet_url.split("&gid=")[1].split("&")[0]
             except: pass
             
        headers = {"Authorization": f"Bearer {creds.token}"}
        
        # Find Sheet Name
        if gid:
            meta_url = f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}"
            meta_resp = requests.get(meta_url, headers=headers)
            if meta_resp.status_code == 200:
                sheets = meta_resp.json().get('sheets', [])
                for s in sheets:
                    props = s.get('properties', {})
                    if str(props.get('sheetId')) == str(gid):
                        target_sheet_name = props.get('title')
                        break
        
        range_name = f"'{target_sheet_name}'!A:ZZ"
        encoded_range = urllib.parse.quote(range_name, safe='')
        
        # CLEAR API
        api_url = f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values/{encoded_range}:clear"
        resp = requests.post(api_url, headers=headers)
        
        if resp.status_code == 200:
            return True, "Success"
        else:
            return False, f"API Error {resp.status_code}: {resp.text}"
        
    except Exception as e:
        return False, str(e)

def bulk_update(sheet_url: str, data: list):
    """Overwrites sheet with 2D array data starting at A1"""
    try:
        creds = get_service_account_creds()
        if not creds: return False
        
        if "/d/" in sheet_url:
            spreadsheet_id = sheet_url.split("/d/")[1].split("/")[0]
        else: return False
        
        target_sheet_name = "Sheet1"
        gid = None
        if "gid=" in sheet_url:
             try:
                 if "#gid=" in sheet_url: gid = sheet_url.split("#gid=")[1].split("&")[0]
                 elif "?gid=" in sheet_url: gid = sheet_url.split("?gid=")[1].split("&")[0]
                 elif "&gid=" in sheet_url: gid = sheet_url.split("&gid=")[1].split("&")[0]
             except: pass
             
        headers = {"Authorization": f"Bearer {creds.token}"}
        
        if gid:
            meta_url = f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}"
            meta_resp = requests.get(meta_url, headers=headers)
            if meta_resp.status_code == 200:
                sheets = meta_resp.json().get('sheets', [])
                for s in sheets:
                    props = s.get('properties', {})
                    if str(props.get('sheetId')) == str(gid):
                        target_sheet_name = props.get('title')
                        break
                        
        range_name = f"'{target_sheet_name}'!A1"
        encoded_range = urllib.parse.quote(range_name, safe='')
        
        api_url = f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values/{encoded_range}?valueInputOption=USER_ENTERED"
        
        body = { "values": data }
        
        resp = requests.put(api_url, headers=headers, json=body)
        return resp.status_code == 200
        
    except Exception as e:
        print(f"Bulk Update Error: {e}")
        return False

def delete_row_by_email(sheet_url: str, email: str):
    """
    Deletes a row containing the email by re-writing the sheet.
    WARNING: This clears and rewrites the sheet.
    """
    try:
        # 1. Load Data
        df = load_google_sheet(sheet_url)
        if df is None or df.empty:
            return False, "Empty Sheet or Load Error"
            
        # 2. Identify Email Column (Reuse logic)
        email = email.lower().strip()
        target_col = None
        for col in df.columns:
            if str(col).lower().strip() in ['email address', 'email']:
                target_col = col
                break
        
        if not target_col:
            return False, "Email Column Not Found"
            
        # 3. Filter Data
        # Count before
        count_before = len(df)
        
        # Filter (Keep rows that DO NOT match)
        # Handle non-string types gracefully
        df_filtered = df[df[target_col].astype(str).str.lower().str.strip() != email]
        
        count_after = len(df_filtered)
        
        if count_before == count_after:
            return False, "Email Not Found in Sheet"
            
        # 4. Prepare List of Lists
        # Header + Data
        # Replace NaN with empty string for JSON serialization
        df_filtered = df_filtered.fillna("")
        
        data = [df_filtered.columns.tolist()] + df_filtered.values.tolist()
        
        # 5. Clear & Write
        success_clear, msg = clear_sheet(sheet_url)
        if not success_clear:
            return False, f"Clear Failed: {msg}"
            
        success_write = bulk_update(sheet_url, data)
        
        if success_write:
            return True, f"Deleted {count_before - count_after} row(s)"
        else:
            return False, "Write Failed after Clear (CRITICAL)"
            
    except Exception as e:
        return False, str(e)


def delete_row_by_name(sheet_url: str, first_name: str, last_name: str):
    """
    Deletes a row containing the Name by re-writing the sheet.
    Useful for social-only contacts.
    """
    try:
        if not first_name: return False, "No First Name provided"
        
        # 1. Load Data
        df = load_google_sheet(sheet_url)
        if df is None or df.empty:
            return False, "Empty Sheet or Load Error"
            
        # 2. Identify Name Columns
        f_col = None
        l_col = None
        
        # Heuristic search for columns
        for col in df.columns:
            c = str(col).lower().strip()
            if c in ['first name', 'first_name', 'firstname', 'first']:
                f_col = col
            elif c in ['last name', 'last_name', 'lastname', 'surname', 'last']:
                l_col = col
                
        if not f_col:
             # Try single 'Name' column? 
             # For now, strict First/Last separation as per Rider DB schema
             return False, "First Name Column Not Found"
             
        # 3. Filter Data
        count_before = len(df)
        
        # Target values
        tgt_f = str(first_name).lower().strip()
        tgt_l = str(last_name or "").lower().strip()
        
        # Pandas boolean mask
        try:
            con_f = df[f_col].astype(str).str.lower().str.strip() == tgt_f
            
            con_l = True
            if l_col:
                con_l = df[l_col].astype(str).str.lower().str.strip() == tgt_l
            else:
                # If no last name column in sheet, but target has last name?
                # This logic mismatch might happen.
                pass
                
            # Delete where BOTH match
            # If l_col is missing, we only match first name 
            # (risky, but if sheet only has first name, what choice?)
            mask_to_delete = con_f & con_l
            
            df_filtered = df[~mask_to_delete]
            
        except Exception as filter_err:
             return False, f"Filter Error: {filter_err}"
        
        count_after = len(df_filtered)
        
        if count_before == count_after:
            return False, f"Name '{first_name} {last_name}' Not Found"
            
        # 4. Write Back
        df_filtered = df_filtered.fillna("")
        data = [df_filtered.columns.tolist()] + df_filtered.values.tolist()
        
        success_clear, msg = clear_sheet(sheet_url)
        if not success_clear: return False, f"Clear Failed: {msg}"
        
        success_write = bulk_update(sheet_url, data)
        
        if success_write:
            return True, f"Deleted {count_before - count_after} row(s) (Name Match)"
        else:
            return False, "Write Failed"
            
    except Exception as e:
        return False, str(e)
